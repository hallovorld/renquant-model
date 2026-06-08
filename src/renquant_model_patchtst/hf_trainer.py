#!/usr/bin/env python3
"""PatchTST cross-sectional ranker — HuggingFace Trainer + multi-task head.

REPLACES hand-rolled training loop (376 LOC) with HF Trainer + canonical
3rd-party machinery per repository architecture guidance.

Architecture (HF native + minimal custom):
  backbone : transformers.PatchTSTModel  (Nie 2023 ICLR)
  heads    : Linear(d_model, 1) for ranking
             Linear(d_model, 3) for (df, loc, scale) Student-t distribution
  loss     : torch.nn.functional.margin_ranking_loss (CIKM 2025 arXiv 2510.14156
                 — Margin Ranking + ListNet beat pairwise BCE on portfolio Sharpe)
             + λ * Student-t NLL (per-ticker μ/σ for downstream Kelly/QP)
  trainer  : transformers.Trainer with TrainingArguments
              load_best_model_at_end=True   → solves prior best-epoch save bug
              metric_for_best_model="eval_min_regime_ic"  → PRIME DIRECTIVE
              lr_scheduler_type="cosine_with_warmup"     → no manual schedule
  callback : PerRegimeICCallback  computes per-HMM-regime IC each eval
              (BULL_CALM / BULL_VOLATILE / CHOPPY / BEAR)
              selection metric = min(per_regime_ic.values()) per PRIME DIRECTIVE

References:
  - Nie et al 2023 ICLR "A Time Series is Worth 64 Words" (PatchTST)
  - Burges et al 2005 ICML "Learning to Rank using Gradient Descent" — superseded
    by Margin Ranking per CIKM 2025 portfolio-Sharpe benchmark
  - CIKM 2025 (arXiv 2510.14156) "On Evaluating Loss Functions for Stock Ranking"
  - HF Trainer https://huggingface.co/docs/transformers/main_classes/trainer

Usage::

    .venv/bin/python scripts/patchtst_hf.py \\
        --dataset data/transformer_v4_wl200_clean.parquet \\
        --cut cut1_covid --epochs 5 --device mps --output-dir artifacts/hf_smoke
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import (
    EarlyStoppingCallback,  # noqa: F401 - re-exported for sequence_training
    PatchTSTConfig,
    PatchTSTModel,
    Trainer,
    TrainerCallback,
    TrainingArguments,  # noqa: F401 - re-exported for sequence_training
)

# Runtime data may still live in the RenQuant checkout, but model code and
# strategy config are independent subrepos. Keep these roots explicit so
# scheduled retrains do not depend on the caller's cwd being the umbrella repo.
MODEL_REPO = Path(__file__).resolve().parents[2]
GITHUB_ROOT = MODEL_REPO.parent
DEFAULT_RENQUANT_ROOT = GITHUB_ROOT / "RenQuant"
DEFAULT_STRATEGY_REPO_CONFIG = (
    GITHUB_ROOT / "renquant-strategy-104" / "configs" / "strategy_config.json"
)
DEFAULT_DATASET_REL = Path("data/transformer_v4_wl200_clean.parquet")


def _default_data_root() -> Path:
    raw = os.environ.get("RENQUANT_DATA_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    legacy_strategy = os.environ.get("RENQUANT_STRATEGY_DIR")
    if legacy_strategy:
        root = Path(legacy_strategy).expanduser().resolve().parent.parent
        if (root / DEFAULT_DATASET_REL).exists():
            return root
    if (DEFAULT_RENQUANT_ROOT / DEFAULT_DATASET_REL).exists():
        return DEFAULT_RENQUANT_ROOT.resolve()
    return Path.cwd().resolve()


REPO = _default_data_root()
_strat_env = os.environ.get("RENQUANT_STRATEGY_DIR")
STRATEGY_DIR = (
    Path(_strat_env).expanduser().resolve()
    if _strat_env
    else DEFAULT_RENQUANT_ROOT / "backtesting" / "renquant_104"
)
if str(MODEL_REPO / "src") not in sys.path:
    sys.path.insert(0, str(MODEL_REPO / "src"))
if STRATEGY_DIR.exists() and str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

# NOTE: kernel.* imports deferred to point-of-use so HFPatchTSTPanelScorer
# can `importlib` this script without triggering kernel namespace conflicts.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("patchtst-hf")


# ─── Model ──────────────────────────────────────────────────────────────────

# Canonical ordering for one-hot regime context. Must match the regime emitter
# (BULL_STRONG is config-legacy phantom — detector doesn't emit it). RegimeLabel
# is the single source of truth (renquant_common contract).
from renquant_common.contracts.regime import RegimeLabel  # noqa: E402

from renquant_model_patchtst.splits import assign_patchtst_split  # noqa: E402

REGIMES = (RegimeLabel.BULL_CALM.value, RegimeLabel.BULL_VOLATILE.value,
           RegimeLabel.CHOPPY.value, RegimeLabel.BEAR.value)


def regime_to_onehot(regime_label: str) -> np.ndarray:
    """Map categorical regime label → (K=4,) one-hot float32. Unknown
    label → all zeros (model gets no regime signal; safer than guess)."""
    out = np.zeros(len(REGIMES), dtype=np.float32)
    if regime_label in REGIMES:
        out[REGIMES.index(regime_label)] = 1.0
    return out


class FiLMLayer(nn.Module):
    """Feature-wise Linear Modulation (Perez 2017, arXiv 1709.07871).

    γ, β = MLP(context); h' = γ ⊙ h + β. Lightweight regime conditioning:
    shared backbone learns cross-regime features; FiLM modulates them
    per-regime via ~500 extra params for K=4 regimes, d_model=64.

    Init: last layer zero-init → at start (γ, β) = (1, 0) → FiLM is
    identity → strict superset of no-FiLM baseline.
    """

    def __init__(self, d_model: int, n_regimes: int = len(REGIMES),
                 hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_regimes, hidden), nn.ReLU(),
            nn.Linear(hidden, 2 * d_model),
        )
        # Zero-init final layer → (γ, β) = (0, 0) at output, then γ ← 1+γ
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, h: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        gb = self.net(context)
        delta_gamma, beta = gb.chunk(2, dim=-1)
        return (1.0 + delta_gamma) * h + beta


class CrossStockAttentionLayer(nn.Module):
    """iTransformer-style variate-as-token attention across tickers (Liu 2024,
    arXiv 2310.06625). Addresses PatchTST's documented #1 failure mode for
    cross-sectional finance: channel-independence (each ticker forward
    independently, no cross-stock information sharing per arXiv 2502.09683).

    For one day's batch of N tickers each represented by `d_model`-dim vec:
      input h: (N, d_model)
      query/key/value: each ticker as token
      attention: each ticker attends to ALL other tickers on the same day
      output: (N, d_model) — each ticker enriched with cross-stock context

    Residual + LayerNorm (canonical transformer block). Init: zero-init
    output projection so the residual passes through unchanged at start →
    strict superset of no-cross-stock baseline.

    Compute: O(N²) per day in attention. N=142 (wl200) → ~20k pairs.
    Fine on MPS/CPU.
    """

    def __init__(self, d_model: int, n_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout,
                                           batch_first=True)
        self.norm1 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Linear(d_model * 2, d_model),
        )
        self.norm2 = nn.LayerNorm(d_model)
        # IDENTITY-AT-INIT via learnable scalar gate (FiLM pattern):
        # output = h + alpha * (transformed(h) - h). With alpha=0 at init,
        # output exactly equals h. Pure zero-init of attn+ffn alone
        # doesn't suffice because LayerNorm transforms h regardless.
        self.alpha = nn.Parameter(torch.zeros(1))
        # Also zero-init final projections for cleaner gradient signal early
        nn.init.zeros_(self.ffn[-1].weight)
        nn.init.zeros_(self.ffn[-1].bias)
        nn.init.zeros_(self.attn.out_proj.weight)
        nn.init.zeros_(self.attn.out_proj.bias)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        # h: (N, d_model)  — N tickers on one day
        h_batched = h.unsqueeze(0)  # (1, N, d_model)
        attn_out, _ = self.attn(h_batched, h_batched, h_batched)
        h_attn = self.norm1(h_batched + attn_out)
        h_ffn = self.norm2(h_attn + self.ffn(h_attn))
        transformed = h_ffn.squeeze(0)  # (N, d_model)
        # Gated residual: alpha=0 at init → exactly h
        return h + self.alpha * (transformed - h)


class HFPatchTSTRanker(nn.Module):
    """HF PatchTST backbone + dual head: ranking + Student-t distribution.

    Optional FiLM regime conditioning (Perez 2017) between encoder and
    heads. forward() returns dict with always-present "score" key. When
    `use_distributional_head=True`, also returns (df, loc, scale) for
    Student-t NLL training and downstream σ-aware Kelly/QP.
    """

    def __init__(self, cfg: PatchTSTConfig, use_distributional_head: bool = True,
                 use_film_regime: bool = False,
                 use_cross_stock_attn: bool = False,
                 n_regimes: int = len(REGIMES)):
        super().__init__()
        self.backbone = PatchTSTModel(cfg)
        self.use_distributional_head = use_distributional_head
        self.use_film_regime = use_film_regime
        self.use_cross_stock_attn = use_cross_stock_attn
        self.rank_head = nn.Linear(cfg.d_model, 1)
        self.dist_head = nn.Linear(cfg.d_model, 3) if use_distributional_head else None
        self.film = FiLMLayer(cfg.d_model, n_regimes) if use_film_regime else None
        # Cross-stock attention layer between backbone and heads
        self.cross_stock = (
            CrossStockAttentionLayer(cfg.d_model, n_heads=cfg.num_attention_heads)
            if use_cross_stock_attn else None
        )

    def forward(self, past_values: torch.Tensor,
                labels: torch.Tensor | None = None,
                regime_context: torch.Tensor | None = None,
                dates=None) -> dict:
        out = self.backbone(past_values=past_values)
        # (B, n_ch, n_patches, d_model) → pool to (B, d_model)
        h = out.last_hidden_state.mean(dim=(1, 2))
        if self.film is not None and regime_context is not None:
            h = self.film(h, regime_context)
        # Cross-stock attention: each ticker attends to all other tickers
        # on the same day (since batch IS one day's tickers per identity_collator)
        if self.cross_stock is not None:
            h = self.cross_stock(h)
        result: dict = {"score": self.rank_head(h).squeeze(-1)}
        if self.dist_head is not None:
            d = self.dist_head(h)
            result["df"] = F.softplus(d[..., 0]) + 2.0   # df > 2 → finite variance
            result["loc"] = d[..., 1]
            result["scale"] = F.softplus(d[..., 2]) + 1e-6
        return result


# ─── Losses (canonical 3rd-party) ───────────────────────────────────────────

def margin_ranking_loss(scores: torch.Tensor, labels: torch.Tensor,
                        margin: float = 0.1) -> torch.Tensor:
    """torch.nn.functional.margin_ranking_loss over all within-batch pairs.
    CIKM 2025 (arXiv 2510.14156): Margin Ranking is best ranking loss on
    portfolio Sharpe across PortfolioMASTER × S&P 500 benchmark.
    """
    n = scores.shape[0]
    if n < 2:
        return torch.tensor(0.0, device=scores.device, requires_grad=True)
    iu, ju = torch.triu_indices(n, n, offset=1, device=scores.device)
    s_i, s_j = scores[iu], scores[ju]
    l_i, l_j = labels[iu], labels[ju]
    target = torch.sign(l_i - l_j)  # ∈ {-1, 0, +1}
    return F.margin_ranking_loss(s_i, s_j, target, margin=margin)


def student_t_nll(df: torch.Tensor, loc: torch.Tensor, scale: torch.Tensor,
                  target: torch.Tensor) -> torch.Tensor:
    """Student-t negative log-likelihood (canonical torch.distributions)."""
    dist = torch.distributions.StudentT(df, loc, scale)
    return -dist.log_prob(target).mean()


# ─── Preprocessing (Kelly-Gu-Xiu 2020 RFS standard) ─────────────────────────

def csrank_norm_per_day(panel: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    """Per-day cross-sectional rank-norm to [-0.5, +0.5]. Removes scale drift +
    outlier sensitivity. No temporal leakage."""
    panel = panel.copy()
    panel[feat_cols] = (panel.groupby("date")[feat_cols].rank(pct=True) - 0.5)
    panel[feat_cols] = panel[feat_cols].fillna(0.0)
    return panel


def label_winsor_bounds(panel: pd.DataFrame, label_col: str,
                        pct: float = 0.005,
                        fit_mask: pd.Series | None = None) -> tuple[float, float]:
    """Fit label clipping bounds on an explicit sample.

    For walk-forward validation this must be the training split only; using
    validation/test labels to choose clipping quantiles is a small but real
    lookahead channel.
    """
    fit = panel.loc[fit_mask, label_col] if fit_mask is not None else panel[label_col]
    fit = fit.dropna()
    if fit.empty:
        raise ValueError(f"cannot fit winsor bounds: no non-null {label_col}")
    return float(fit.quantile(pct)), float(fit.quantile(1 - pct))


def winsorize_label(panel: pd.DataFrame, label_col: str,
                    pct: float = 0.005,
                    bounds: tuple[float, float] | None = None) -> pd.DataFrame:
    """Winsorize label ±pct percentile (default 0.5% each side ≈ ±3σ)."""
    panel = panel.copy()
    lo, hi = bounds or label_winsor_bounds(panel, label_col, pct=pct)
    panel[label_col] = panel[label_col].clip(lower=lo, upper=hi)
    panel.attrs["label_winsor"] = {
        "enabled": True,
        "fit_split": "train" if bounds is not None else "all_rows",
        "pct": pct,
        "lower": lo,
        "upper": hi,
    }
    return panel


def load_panel_with_split(dataset_path: Path, cut_name: str, label_col: str,
                          preprocess: bool = True,
                          val_tail_pct: float = 0.0,
                          embargo_days: int = 60,
                          train_cutoff: str | None = None,
                          data_end: str | None = None,
                          exclude_features: list[str] | None = None,
                          shuffle_labels: bool = False,
                          label_shift_days: int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Load panel + assign train/val/test split.

    cut_name = "all": full-data PROD training; last val_tail_pct dates -> val.
    cut_name = "cut1_covid" etc: walk-forward validation through
                                   renquant_common.walk_forward_splits.
    """
    panel = pd.read_parquet(dataset_path)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel = panel.dropna(subset=[label_col])
    cutoff_ts = pd.Timestamp(train_cutoff) if train_cutoff else None
    end_ts = pd.Timestamp(data_end) if data_end else None
    if cutoff_ts is not None and end_ts is None:
        m = re.search(r"fwd_(\d+)d", label_col)
        end_ts = cutoff_ts - pd.offsets.BDay(int(m.group(1)) if m else 60)
    if end_ts is not None:
        panel = panel[panel["date"] < end_ts].copy()
        if panel.empty:
            raise ValueError(
                f"no rows with date < {end_ts.date()} "
                f"(train_cutoff={train_cutoff}, data_end={data_end})"
            )
        panel.attrs["data_window_end_exclusive"] = str(end_ts.date())
    if cutoff_ts is not None:
        panel.attrs["train_cutoff_date"] = str(cutoff_ts.date())
    panel["split_label"] = assign_patchtst_split(
        panel,
        cut_name,
        embargo_days=embargo_days,
        val_tail_pct=val_tail_pct,
    )
    _excluded = {"date", "ticker", "split_label",
                 "fwd_5d_excess", "fwd_20d_excess", "fwd_60d_excess"}
    _excluded.update(exclude_features or ())
    feat_cols = [c for c in panel.columns
                 if c not in _excluded
                 and panel[c].dtype.kind in "fiub"]
    if exclude_features:
        log.info("excluded %d feature(s): %s",
                 len(exclude_features), ",".join(exclude_features))
    train_mask = panel["split_label"].eq("train")
    if label_shift_days:
        # Time-shift placebo: break the train feature→label alignment while
        # preserving validation labels for honest IC computation.
        #
        # Bug 2026-05-31: the panel was already ``dropna(subset=[label_col])``
        # at load time, so ``shift(-N)`` walks N positions forward in the
        # NaN-dropped panel — NOT N calendar days. At the train/val boundary,
        # the shifted source can land in val/embargo rows. The "placebo"
        # then trained on val labels, producing placebo IC > real IC and
        # blocking Tier-3 verdicts. Fix: also track the SOURCE row's
        # split_label and drop train rows whose shifted source is not in
        # train. This keeps the placebo's "decorrelate within train"
        # semantics without cross-split leak.
        n_shift = int(label_shift_days)
        ticker_groups = panel.groupby("ticker", sort=False)
        shifted_label = ticker_groups[label_col].shift(-n_shift)
        shifted_split = ticker_groups["split_label"].shift(-n_shift)
        panel.loc[train_mask, label_col] = shifted_label.loc[train_mask]
        # Drop train rows where the shifted source was NaN (off the end of
        # the ticker's series) OR was a non-train split row.
        before = len(panel)
        cross_split_leak = train_mask & shifted_split.ne("train")
        nan_after_shift = train_mask & panel[label_col].isna()
        panel = panel.loc[~(cross_split_leak | nan_after_shift)].copy()
        log.info(
            "PLACEBO label_shift_days=%d: shifted train '%s'; dropped %d "
            "train rows (cross-split-leak guard + NaN tail)",
            label_shift_days, label_col, before - len(panel),
        )
    if shuffle_labels:
        # Train-only placebo: permute TRAIN labels only. Validation labels remain
        # aligned so the reported IC still measures the original target.
        train_idx = panel.index[panel["split_label"].eq("train")]
        panel.loc[train_idx, label_col] = np.random.permutation(
            panel.loc[train_idx, label_col].to_numpy()
        )
        log.info(
            "PLACEBO shuffle_labels: permuted train '%s' across %d rows (expect IC≈0)",
            label_col, len(train_idx),
        )
    if preprocess:
        panel = csrank_norm_per_day(panel, feat_cols)
        winsor_bounds = label_winsor_bounds(
            panel, label_col, pct=0.005,
            fit_mask=panel["split_label"].eq("train"))
        panel = winsorize_label(panel, label_col, pct=0.005,
                                bounds=winsor_bounds)
        log.info("preprocessing: CSRankNorm + train-fit Winsorize(±0.5%%) "
                 "applied bounds=[%+.6f, %+.6f]", *winsor_bounds)
    log.info("panel %d rows | cut=%s | train=%d val=%d test=%d | n_feat=%d",
             len(panel), cut_name,
             (panel["split_label"] == "train").sum(),
             (panel["split_label"] == "val").sum(),
             (panel["split_label"] == "test").sum(),
             len(feat_cols))
    return panel, feat_cols


def git_head() -> str | None:
    """Best-effort source stamp for model artifacts."""
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=MODEL_REPO,
                           capture_output=True, text=True, check=False)
    except Exception:
        return None
    return r.stdout.strip() or None


def resolve_runtime_path(raw: str | Path) -> Path:
    """Resolve dataset/SPY inputs without assuming the caller's cwd."""
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    cwd_path = Path.cwd().resolve() / path
    if cwd_path.exists():
        return cwd_path
    return REPO / path


def resolve_strategy_config_path(raw: str | Path | None = None) -> Path:
    """Resolve the strategy config stamped into PatchTST artifacts."""
    raw = raw or os.getenv("RENQUANT_STRATEGY_CONFIG")
    if raw:
        path = Path(raw).expanduser()
        if path.is_absolute():
            return path
        for base in (Path.cwd().resolve(), REPO, MODEL_REPO):
            candidate = base / path
            if candidate.exists():
                return candidate
        return REPO / path

    candidates = [
        DEFAULT_STRATEGY_REPO_CONFIG,
        STRATEGY_DIR / "strategy_config.shadow.json",
        STRATEGY_DIR / "strategy_config.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0]


def build_config_contract(args: argparse.Namespace) -> dict:
    """Stamp the model-relevant strategy config used by runtime preflight."""
    path = resolve_strategy_config_path(getattr(args, "strategy_config", None))
    cfg = json.loads(path.read_text())
    from renquant_common.config_consistency import (  # noqa: PLC0415
        fingerprint_config, _model_relevant_fields,
    )
    fields = _model_relevant_fields(cfg)
    display_path = path
    for base in (MODEL_REPO, REPO):
        if path.is_relative_to(base):
            display_path = path.relative_to(base)
            break
    return {
        "config_path": str(display_path),
        "config_fingerprint": fingerprint_config(cfg),
        "config_fingerprint_fields": fields,
        "trained_watchlist_n": len(fields.get("watchlist") or []),
    }


def build_training_contract(args: argparse.Namespace, feat_cols: list[str],
                            panel: pd.DataFrame, n_params: int,
                            total_steps: int, warmup_steps: int,
                            metric_for_best: str,
                            final_metrics: dict) -> dict:
    """Compact, auditable model contract persisted with every artifact."""
    split_counts = panel["split_label"].value_counts().to_dict()
    split_days = (panel.groupby("split_label")["date"].nunique()
                  .astype(int).to_dict())
    split_ranges = {}
    for split, g in panel.groupby("split_label"):
        dates = pd.to_datetime(g["date"])
        split_ranges[split] = {
            "start": str(dates.min().date()),
            "end": str(dates.max().date()),
        }
    lookahead_match = re.search(r"fwd_(\d+)d", args.label)
    lookahead_days = int(lookahead_match.group(1)) if lookahead_match else None
    fit_mask = panel["split_label"].isin(["train", "val"])
    fit_dates = pd.to_datetime(panel.loc[fit_mask, "date"])
    fit_splits = ["train"]
    if panel["split_label"].eq("val").any():
        fit_splits.append("val")
    return {
        "contract_version": 1,
        "trained_date": str(dt.date.today()),
        "git_head": git_head(),
        "dataset": str(args.dataset),
        "cut": args.cut,
        "train_cutoff_date": getattr(args, "train_cutoff", None),
        "data_window_end_exclusive": (
            panel.attrs.get("data_window_end_exclusive")
            or getattr(args, "data_end", None)
        ),
        "label_col": args.label,
        "lookahead_days": lookahead_days,
        "seed": args.seed,
        "n_features": len(feat_cols),
        "n_params": n_params,
        "split_counts": {k: int(v) for k, v in split_counts.items()},
        "split_days": {k: int(v) for k, v in split_days.items()},
        "split_date_ranges": split_ranges,
        "effective_train_cutoff_date": (
            str(fit_dates.max().date()) if not fit_dates.empty else None
        ),
        "selection_fit_splits": fit_splits,
        "preprocessing": {
            "csrank_norm_per_day": True,
            "label_winsor": panel.attrs.get("label_winsor", {}),
        },
        "hyperparameters": {
            "seq_len": args.seq_len,
            "patch_length": args.patch_length,
            "d_model": args.d_model,
            "n_heads": args.n_heads,
            "n_layers": args.n_layers,
            "epochs": args.epochs,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "lr_scheduler": args.lr_scheduler,
            "warmup_ratio": args.warmup_ratio,
            "warmup_steps": warmup_steps,
            "total_steps": total_steps,
            "early_stopping_patience": args.early_stopping_patience,
            "embargo_days": args.embargo_days,
            "nll_loss_weight": args.nll_loss_weight,
            "ranking_margin": args.ranking_margin,
            "distributional_head": args.distributional_head,
            "film_regime_cond": args.film_regime_cond,
            "cross_stock_attn": args.cross_stock_attn,
            "device": args.device,
            "shuffle_labels": bool(getattr(args, "shuffle_labels", False)),
            "label_shift_days": int(getattr(args, "label_shift_days", 0)),
            "detector_version": str(getattr(args, "detector_version", "v2026-05-31")),
        },
        "selection": {
            "metric_for_best_model": metric_for_best,
            "best_val_ic": float(final_metrics.get("eval_min_regime_ic", float("nan"))),
            "final_metrics": {k: float(v) if isinstance(v, (int, float)) else v
                              for k, v in final_metrics.items()},
        },
    }


# ─── Dataset (per-day batching) ─────────────────────────────────────────────

class PerDayDataset(torch.utils.data.Dataset):
    """One Dataset sample = one day's all-ticker batch. With identity_collator
    and Trainer batch_size=1, each Trainer step processes one day's pairwise
    ranking loss.

    If `hmm_labels` is provided, each day's dict gets a `regime_context`
    tensor of shape (N_tickers, K=4) — one-hot for the day's HMM regime.
    All tickers on the same day share the same regime row (regime is a
    market-wide signal, broadcast for FiLM convenience)."""

    def __init__(self, panel: pd.DataFrame, feat_cols: list[str],
                 label_col: str, seq_len: int, split: str,
                 hmm_labels: pd.DataFrame | None = None):
        feat_arr = panel[feat_cols].astype(np.float32).fillna(0.0).values
        lab_arr = panel[label_col].astype(np.float32).values
        split_arr = panel["split_label"].astype(str).to_numpy()
        samples_by_date: dict[int, list[tuple[np.ndarray, float, pd.Timestamp]]] = {}
        tkr_arr = panel["ticker"].to_numpy()
        skipped_cross_split = 0
        for ticker, idxs in panel.groupby("ticker", sort=False).indices.items():
            idxs = np.asarray(sorted(idxs))
            for i in range(seq_len, len(idxs)):
                end_pos = idxs[i]
                if split_arr[end_pos] != split:
                    continue
                window_idxs = idxs[i - seq_len: i]
                if not np.all(split_arr[window_idxs] == split):
                    skipped_cross_split += 1
                    continue
                window = feat_arr[window_idxs]
                if window.shape[0] != seq_len:
                    continue
                d = panel.iloc[end_pos]["date"]
                samples_by_date.setdefault(d.value, []).append(
                    (window, lab_arr[end_pos], d, tkr_arr[end_pos]))
        if skipped_cross_split:
            log.info(
                "PerDayDataset[%s]: skipped %d cross-split lookback window(s) "
                "for split-pure PatchTST tensors",
                split, skipped_cross_split,
            )

        # Build per-day regime context lookup (if HMM labels provided)
        regime_map: dict[int, str] | None = None
        if hmm_labels is not None:
            regime_map = {pd.Timestamp(d).value: r
                          for d, r in zip(hmm_labels["date"], hmm_labels["regime"])}

        self.days: list[dict] = []
        for d_ns, samples in samples_by_date.items():
            if len(samples) < 5:
                continue
            day = {
                "past_values": torch.from_numpy(np.stack([s[0] for s in samples])),
                "labels": torch.tensor([s[1] for s in samples], dtype=torch.float32),
                "dates": np.array([s[2].value for s in samples], dtype="int64"),
                "tickers": np.array([s[3] for s in samples], dtype=object),
            }
            if regime_map is not None:
                regime = regime_map.get(int(d_ns), RegimeLabel.BULL_CALM.value)  # fallback
                onehot = regime_to_onehot(regime)
                n = len(samples)
                day["regime_context"] = torch.from_numpy(
                    np.broadcast_to(onehot, (n, len(REGIMES))).copy())
                day["regime_label"] = regime
            self.days.append(day)

    def __len__(self):
        return len(self.days)

    def __getitem__(self, idx):
        return self.days[idx]


def identity_collator(batch):
    """No collation — each DataLoader batch is exactly one day's dict."""
    assert len(batch) == 1, f"batch_size must be 1 for per-day batching, got {len(batch)}"
    return batch[0]


# ─── Trainer subclass (multi-task loss) ─────────────────────────────────────

class PatchTSTRankerTrainer(Trainer):
    """HF Trainer with multi-task compute_loss: Margin Ranking + Student-t NLL."""

    def __init__(self, *args, nll_loss_weight: float = 0.5,
                 ranking_margin: float = 0.1, **kw):
        super().__init__(*args, **kw)
        self._nll_loss_weight = nll_loss_weight
        self._ranking_margin = ranking_margin

    def compute_loss(self, model, inputs, return_outputs=False,
                     num_items_in_batch=None):
        labels = inputs["labels"]
        fwd_kwargs = {"past_values": inputs["past_values"], "labels": labels}
        if "regime_context" in inputs:
            fwd_kwargs["regime_context"] = inputs["regime_context"]
        outputs = model(**fwd_kwargs)
        loss = margin_ranking_loss(outputs["score"], labels,
                                    margin=self._ranking_margin)
        if "loc" in outputs and self._nll_loss_weight > 0:
            nll = student_t_nll(outputs["df"], outputs["loc"], outputs["scale"],
                                labels)
            loss = loss + self._nll_loss_weight * nll
        return (loss, outputs) if return_outputs else loss


# ─── Per-regime IC callback (PRIME DIRECTIVE) ───────────────────────────────

class PerRegimeICCallback(TrainerCallback):
    """After each eval, run a second forward pass on val set, compute per-HMM-
    regime IC (BULL_CALM / BULL_VOLATILE / CHOPPY / BEAR), and inject
    `eval_min_regime_ic` into metrics — this is the selection metric for
    `load_best_model_at_end=True` per PRIME DIRECTIVE.
    """

    def __init__(self, eval_dataset: PerDayDataset, hmm_labels: pd.DataFrame):
        self.eval_dataset = eval_dataset
        self.hmm_labels = hmm_labels

    def on_evaluate(self, args, state, control, model=None, metrics=None, **kw):
        if model is None or metrics is None:
            return
        from renquant_common.hmm_regime_labels import per_hmm_regime_ic  # noqa: PLC0415
        device = next(model.parameters()).device
        model.eval()
        all_p, all_y, all_d = [], [], []
        with torch.no_grad():
            for day in self.eval_dataset.days:
                x = day["past_values"].to(device)
                fwd_kwargs = {"past_values": x}
                if "regime_context" in day:
                    fwd_kwargs["regime_context"] = day["regime_context"].to(device)
                outputs = model(**fwd_kwargs)
                all_p.append(outputs["score"].cpu().numpy())
                all_y.append(day["labels"].numpy())
                all_d.append(day["dates"])
        if not all_p:
            return
        preds_df = pd.DataFrame({
            "date": pd.to_datetime(np.concatenate(all_d)),
            "pred": np.concatenate(all_p),
            "label": np.concatenate(all_y),
        })
        per_regime = per_hmm_regime_ic(preds_df, self.hmm_labels)
        if per_regime:
            min_ic = float(min(per_regime.values()))
            metrics["eval_min_regime_ic"] = min_ic
            for r, ic in per_regime.items():
                metrics[f"eval_ic_{r}"] = float(ic)
            log.info("per-regime IC: %s | min=%+.4f",
                     {r: f"{v:+.4f}" for r, v in per_regime.items()}, min_ic)
        else:
            log.warning("per-regime IC: no regime had ≥5 days in val — "
                        "falling back to pooled eval_loss for selection")


# ─── Train entrypoint ───────────────────────────────────────────────────────

def train_single_run(args: argparse.Namespace) -> dict:
    """Train one PatchTST run via the decomposed sequence-training Pipeline.

    The body is split into single-responsibility Tasks in ``sequence_training``
    (DataPrep → Train → Evaluate → Persist Jobs) per the Task/Job/Pipeline
    architecture; this stays the stable entrypoint for the CLI + SequenceTrainer.
    """
    from .sequence_training import run_sequence_training  # noqa: PLC0415
    return run_sequence_training(args)


def build_parser() -> argparse.ArgumentParser:
    """The trainer's CLI parser — reused by main() and by the SequenceTrainer
    adapter (training.py) so default hyperparameters live in exactly one place."""
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="patchtst",
                   choices=["patchtst", "patchtsmixer"],
                   help="Backbone model family. 'patchtst' (default) keeps "
                        "the existing PatchTST + FiLM + cross-stock-attn + "
                        "distributional-head stack. 'patchtsmixer' swaps in "
                        "HFPatchTSMixerRanker (W1 MLP-mixer baseline from "
                        "PR #16) — same data/loss/eval pipeline, only the "
                        "backbone differs. PatchTST-specific knobs "
                        "(--film-regime-cond, --cross-stock-attn, NLL head) "
                        "are accepted-but-ignored for patchtsmixer.")
    p.add_argument("--dataset", default="data/transformer_v4_wl200_clean.parquet")
    p.add_argument("--cut", default="cut1_covid",
                   help="walk-forward cut name OR 'all' for full-data prod")
    p.add_argument("--val-tail-pct", type=float, default=0.10)
    p.add_argument("--embargo-days", type=int, default=60,
                   help="Business-day embargo before validation when --cut all "
                        "uses a tail validation split.")
    p.add_argument("--train-cutoff", default=None,
                   help="Selection cutoff for a point-in-time WF fold. When "
                        "--data-end is omitted, data_end is inferred as "
                        "train_cutoff - label lookahead business days.")
    p.add_argument("--data-end", default=None,
                   help="Exclusive max feature/label row date for WF training.")
    p.add_argument("--label", default="fwd_60d_excess")
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--patch-length", type=int, default=4)
    p.add_argument("--d-model", type=int, default=64)
    p.add_argument("--n-heads", type=int, default=4)
    p.add_argument("--n-layers", type=int, default=2)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--weight-decay", type=float, default=1e-3)
    p.add_argument("--lr-scheduler", default="cosine",
                   help="HF TrainingArguments.lr_scheduler_type "
                        "(cosine | linear | constant_with_warmup)")
    p.add_argument("--warmup-ratio", type=float, default=0.1,
                   help="Fraction of total steps for LR warmup (HF default 0.0)")
    p.add_argument("--distributional-head", action="store_true", default=True,
                   help="Enable Student-t (df, μ, σ) head + NLL loss")
    p.add_argument("--no-distributional-head", dest="distributional_head",
                   action="store_false",
                   help="Disable distributional head (ranking loss only)")
    p.add_argument("--nll-loss-weight", type=float, default=0.5,
                   help="λ in L = margin_rank + λ * student_t_nll")
    p.add_argument("--ranking-margin", type=float, default=0.1,
                   help="margin in torch.nn.functional.margin_ranking_loss")
    p.add_argument("--film-regime-cond", action="store_true",
                   help="FiLM regime conditioning (Perez 2017): γ, β = MLP(regime) "
                        "modulates encoder output. Identity at init → strict "
                        "superset of FiLM-OFF baseline. Requires --spy-path.")
    p.add_argument("--cross-stock-attn", action="store_true",
                   help="iTransformer-style cross-stock attention (Liu 2024, "
                        "arXiv 2310.06625). Each ticker attends to all other "
                        "tickers on the same day. Addresses PatchTST channel-"
                        "independence — documented #1 failure mode for cross-"
                        "sectional finance (arXiv 2502.09683). Identity-at-init "
                        "via zero-init output projections → strict superset of "
                        "baseline.")
    p.add_argument("--spy-path", default="data/ohlcv/SPY/1d.parquet",
                   help="SPY OHLCV parquet for HMM regime labels")
    from renquant_common.hmm_regime_labels import (  # noqa: PLC0415
        DETECTOR_VERSION_LEGACY,
        DETECTOR_VERSION_V20260531,
    )
    p.add_argument("--detector-version",
                   default=DETECTOR_VERSION_V20260531,
                   choices=[DETECTOR_VERSION_LEGACY, DETECTOR_VERSION_V20260531],
                   help="HMM regime detector version "
                        "(renquant_common.hmm_regime_labels). 'v2026-05-31' "
                        "uses the corrected vol-based BULL_CALM path; "
                        "'legacy' preserves pre-2026-05-31 hurst-only "
                        "behavior. Research runs should keep the default; "
                        "production callers may pass 'legacy' for parity "
                        "with daily cron until task #28 default flip ships.")
    p.add_argument("--early-stopping-patience", type=int, default=2,
                   help="EarlyStopping patience (epochs); 0=disabled. "
                        "Stops training when eval_min_regime_ic doesn't improve "
                        "for N epochs. Saves 25-40% wallclock; convergence "
                        "typically reached by epoch 5-6 of 8.")
    p.add_argument("--exclude-features", default=None,
                   help="comma-separated feature columns to drop before training "
                        "(mirrors GBDT exclude_features; e.g. the 3 sentiment "
                        "feats for the E_drop_senti lever)")
    p.add_argument("--shuffle-labels", action="store_true",
                   help="Train-only placebo from doc/research/promotion-methodology.md: "
                        "permute train labels while validation labels stay aligned.")
    p.add_argument("--label-shift-days", type=int, default=0,
                   help="Time-shift placebo from doc/research/promotion-methodology.md: "
                        "replace TRAIN labels with the "
                        "same ticker's label shifted by N business rows while "
                        "leaving validation labels aligned.")
    p.add_argument("--training-window-years", type=float, default=None,
                   help="Diagnostic: width of the training window in years. "
                        "Stamped into training_runs.training_window_years for "
                        "post-hoc analysis; does NOT change training behaviour.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cpu", choices=["cpu", "mps", "cuda"])
    p.add_argument("--save-model", action="store_true")
    p.add_argument("--output-dir", default="artifacts/hf_patchtst")
    p.add_argument("--strategy-config", default=None,
                   help="Strategy config JSON whose model-relevant fingerprint "
                        "is stamped into the summary/checkpoint. Defaults to "
                        "renquant_104 strategy_config.shadow.json.")
    return p


def main():
    args = build_parser().parse_args()
    print(json.dumps(train_single_run(args), indent=2, default=str))


# Back-compat alias (D6 rename 2026-05-30) — external callers can still use train_one.
train_one = train_single_run


if __name__ == "__main__":
    main()
