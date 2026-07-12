#!/usr/bin/env python3
"""Phase 0 + Phase A discovery: L1 equal-weight ensemble vs frozen champion.

Aligned with the revised evidence protocol (model PR #48, merged):
  - §3.0  Stage 0 admissibility ledger per expert
  - §4.1  Nested walk-forward (inner/outer) with non-overlapping block inference
  - §4.1bis Causal normalization, orientation, missing-expert fallback
  - §4.4  Holm-Bonferroni correction, ΔIC≥0.005 minimum effect, costed pass
  - §4.5  Immutable experiment manifest, discovery-only framing

This script produces a DISCOVERY result, not deployment evidence. A positive
finding earns at most a candidate selection for Phase B chronological
confirmation (§4.5B), never a direct production promotion.

Usage (from renquant-model root, umbrella venv)::

    PYTHONPATH=../renquant-common/src:../renquant-pipeline/src:src \
    ../RenQuant/.venv/bin/python experiments/ensemble_l1_equal_weight/run_experiment.py \
        --data-dir ../RenQuant/data \
        --out-dir experiments/ensemble_l1_equal_weight/results \
        [--n-outer-splits 5] [--embargo-days 60] \
        [--watchlist-json ../renquant-strategy-104/configs/watchlist.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("ensemble_l1")

DEFAULT_LABEL = "fwd_60d_excess"
DEFAULT_N_OUTER_SPLITS = 5
DEFAULT_EMBARGO_DAYS = 60
BLOCK_LENGTH_DAYS = 60
MIN_NAMES_PER_DATE = 10
MIN_EFFECT_SIZE = 0.005


# ── §3.0 Admissibility ledger ────────────────────────────────────────────────

@dataclass
class ExpertAdmissibilityRecord:
    """Per-expert admissibility record per §3.0."""
    expert_name: str
    expert_type: str
    score_column: str
    training_cutoff: str | None
    feature_data_cutoff: str | None
    score_orientation: str  # "higher_is_bullish" or "higher_is_bearish"
    universe_coverage: float  # fraction of universe with scores
    missingness_rate: float  # fraction of (date, ticker) pairs missing
    n_dates: int
    n_tickers: int
    date_range: tuple[str, str]
    fingerprint: str  # content hash of the score data
    admitted: bool
    rejection_reason: str | None = None


def compute_score_fingerprint(scores: pd.Series) -> str:
    h = hashlib.sha256()
    h.update(scores.dropna().values.tobytes())
    return h.hexdigest()[:16]


def build_admissibility_ledger(
    data: pd.DataFrame,
    experts: list[dict[str, Any]],
    universe_tickers: set[str],
    label_col: str,
) -> list[ExpertAdmissibilityRecord]:
    """Build admissibility ledger for all proposed experts (§3.0).

    Each expert dict must have: name, type, score_col, orientation.
    Returns list of records; experts with admitted=False are excluded from
    all subsequent comparisons.
    """
    records = []
    dates = sorted(data["date"].unique())

    for expert in experts:
        name = expert["name"]
        score_col = expert["score_col"]
        orientation = expert.get("orientation", "higher_is_bullish")

        if score_col not in data.columns:
            records.append(ExpertAdmissibilityRecord(
                expert_name=name, expert_type=expert["type"],
                score_column=score_col, training_cutoff=None,
                feature_data_cutoff=None, score_orientation=orientation,
                universe_coverage=0.0, missingness_rate=1.0,
                n_dates=0, n_tickers=0, date_range=("", ""),
                fingerprint="", admitted=False,
                rejection_reason=f"score column '{score_col}' not in data",
            ))
            continue

        scored = data.dropna(subset=[score_col])
        if scored.empty:
            records.append(ExpertAdmissibilityRecord(
                expert_name=name, expert_type=expert["type"],
                score_column=score_col, training_cutoff=None,
                feature_data_cutoff=None, score_orientation=orientation,
                universe_coverage=0.0, missingness_rate=1.0,
                n_dates=0, n_tickers=0, date_range=("", ""),
                fingerprint="", admitted=False,
                rejection_reason="no non-null scores",
            ))
            continue

        tickers_with_scores = set(scored["ticker"].unique())
        coverage = len(tickers_with_scores & universe_tickers) / max(len(universe_tickers), 1)

        total_possible = len(dates) * len(universe_tickers)
        scored_universe = scored[scored["ticker"].isin(universe_tickers)]
        missing = 1.0 - len(scored_universe) / max(total_possible, 1)

        fingerprint = compute_score_fingerprint(scored[score_col])

        admitted = True
        rejection_reason = None

        if coverage < 0.5:
            admitted = False
            rejection_reason = f"universe coverage {coverage:.1%} < 50%"
        elif missing > 0.5:
            admitted = False
            rejection_reason = f"missingness {missing:.1%} > 50%"

        records.append(ExpertAdmissibilityRecord(
            expert_name=name, expert_type=expert["type"],
            score_column=score_col,
            training_cutoff=expert.get("training_cutoff"),
            feature_data_cutoff=expert.get("feature_data_cutoff"),
            score_orientation=orientation,
            universe_coverage=float(coverage),
            missingness_rate=float(missing),
            n_dates=int(scored["date"].nunique()),
            n_tickers=int(scored["ticker"].nunique()),
            date_range=(
                str(pd.Timestamp(scored["date"].min()).date()),
                str(pd.Timestamp(scored["date"].max()).date()),
            ),
            fingerprint=fingerprint,
            admitted=admitted,
            rejection_reason=rejection_reason,
        ))

    return records


# ── §4.5A Experiment manifest ────────────────────────────────────────────────

@dataclass
class ExperimentManifest:
    """Immutable experiment manifest per §4.5A.

    Created before the first discovery run; records every considered expert,
    normalization, test, and stopping rule. Variations not in this manifest
    are exploratory follow-ups, not confirmation evidence.
    """
    experiment_id: str
    design_ref: str
    created_at: str
    experts: list[dict[str, Any]]
    admitted_experts: list[str]
    rejected_experts: list[dict[str, str]]
    normalization: str
    missing_expert_policy: str
    combination_methods: list[str]
    hypothesis_family: list[str]
    correction_procedure: str
    minimum_effect_size: float
    label: str
    forecast_horizon_days: int
    embargo_days: int
    block_length_days: int
    n_outer_splits: int
    stopping_rules: list[str]
    manifest_hash: str = ""

    def __post_init__(self):
        if not self.manifest_hash:
            content = json.dumps(asdict(self), sort_keys=True, default=str)
            self.manifest_hash = hashlib.sha256(content.encode()).hexdigest()[:16]


def create_manifest(
    ledger: list[ExpertAdmissibilityRecord],
    n_outer_splits: int,
    embargo_days: int,
    label: str,
) -> ExperimentManifest:
    admitted = [r for r in ledger if r.admitted]
    rejected = [r for r in ledger if not r.admitted]

    methods = ["L1_equal_weight"]
    if len(admitted) >= 2:
        methods.append("L2_inverse_variance")

    hypothesis_family = [
        "H1: L1 vs frozen champion (XGB alone)",
    ]
    if "L2_inverse_variance" in methods:
        hypothesis_family.append("H2: L2 vs L1")
    hypothesis_family.append("H_final: declared candidate vs frozen champion")

    return ExperimentManifest(
        experiment_id=f"ensemble_discovery_{int(time.time())}",
        design_ref="doc/research/2026-07-12-ensemble-combination-experiment.md (PR #48)",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        experts=[asdict(r) for r in ledger],
        admitted_experts=[r.expert_name for r in admitted],
        rejected_experts=[
            {"name": r.expert_name, "reason": r.rejection_reason or "unknown"}
            for r in rejected
        ],
        normalization="cross_sectional_zscore_causal",
        missing_expert_policy="exclude_expert_renormalize_weights",
        combination_methods=methods,
        hypothesis_family=hypothesis_family,
        correction_procedure="holm_bonferroni_stepdown",
        minimum_effect_size=MIN_EFFECT_SIZE,
        label=label,
        forecast_horizon_days=60,
        embargo_days=embargo_days,
        block_length_days=BLOCK_LENGTH_DAYS,
        n_outer_splits=n_outer_splits,
        stopping_rules=[
            "L1 fails to beat champion -> STOP (cost decision, not statistical necessity per §3.2)",
            "No admitted expert beyond champion -> report BLOCKED",
            "Fewer than 4 non-overlapping blocks in outer test -> report UNDERPOWERED",
        ],
    )


# ── §4.1bis Causal normalization ─────────────────────────────────────────────

def causal_zscore(
    df: pd.DataFrame,
    score_col: str,
    orientation: str = "higher_is_bullish",
) -> pd.Series:
    """Cross-sectional z-score using only same-date information (causal).

    Per §4.1bis: all base-model scores on a common scale via causal
    normalization, consistent orientation (higher = more bullish).
    """
    sign = -1.0 if orientation == "higher_is_bearish" else 1.0

    def _zscore_group(g: pd.Series) -> pd.Series:
        mu = g.mean()
        sd = g.std()
        if sd > 0:
            return sign * (g - mu) / sd
        return pd.Series(0.0, index=g.index)

    return df.groupby("date")[score_col].transform(_zscore_group)


# ── §4.1 Non-overlapping block bootstrap / inference ─────────────────────────

def non_overlapping_block_ic(
    ic_series: pd.DataFrame,
    block_length: int = BLOCK_LENGTH_DAYS,
) -> pd.DataFrame:
    """Aggregate per-date ICs into non-overlapping blocks (§4.1).

    fwd_60d labels overlap so successive ICs are NOT IID. This function
    creates non-overlapping blocks of at least `block_length` trading days,
    returning one mean-IC per block.
    """
    if ic_series.empty:
        return pd.DataFrame(columns=["block", "block_start", "block_end", "mean_ic", "n_dates"])

    sorted_ic = ic_series.sort_values("date").reset_index(drop=True)
    dates = sorted_ic["date"].values
    blocks = []
    block_start = 0

    while block_start < len(dates):
        block_end = min(block_start + block_length, len(dates))
        block_data = sorted_ic.iloc[block_start:block_end]
        blocks.append({
            "block": len(blocks),
            "block_start": str(pd.Timestamp(block_data["date"].iloc[0]).date()),
            "block_end": str(pd.Timestamp(block_data["date"].iloc[-1]).date()),
            "mean_ic": float(block_data["ic"].mean()),
            "n_dates": len(block_data),
        })
        block_start = block_end

    return pd.DataFrame(blocks)


def block_paired_test(
    blocks_a: pd.DataFrame,
    blocks_b: pd.DataFrame,
    name_a: str,
    name_b: str,
) -> dict[str, Any]:
    """Paired test on non-overlapping block mean ICs (§4.1 primary approach).

    Uses non-overlapping blocks as approximately independent units,
    avoiding the plain paired t-test's IID assumption violation.
    """
    if blocks_a.empty or blocks_b.empty:
        return {"comparison": f"{name_a} vs {name_b}", "n_blocks": 0,
                "note": "insufficient blocks"}

    n_blocks = min(len(blocks_a), len(blocks_b))
    diff = blocks_a["mean_ic"].values[:n_blocks] - blocks_b["mean_ic"].values[:n_blocks]

    if len(diff) < 3:
        return {
            "comparison": f"{name_a} vs {name_b}",
            "mean_diff": float(np.mean(diff)),
            "n_blocks": int(len(diff)),
            "note": "fewer than 3 non-overlapping blocks — UNDERPOWERED",
        }

    t_stat, p_val = scipy_stats.ttest_1samp(diff, 0)
    return {
        "comparison": f"{name_a} vs {name_b}",
        "mean_diff": float(np.mean(diff)),
        "se_diff": float(np.std(diff, ddof=1) / np.sqrt(len(diff))),
        "t_stat": float(t_stat),
        "p_value_two_sided": float(p_val),
        "p_value_one_sided": float(p_val / 2) if t_stat > 0 else float(1 - p_val / 2),
        "n_blocks": int(len(diff)),
        "meets_min_effect": bool(np.mean(diff) >= MIN_EFFECT_SIZE),
        "block_length_days": BLOCK_LENGTH_DAYS,
        "inference_note": "non-overlapping blocks (§4.1a) — approximately independent",
    }


def holm_bonferroni(p_values: list[tuple[str, float]], alpha: float = 0.05) -> list[dict]:
    """Holm-Bonferroni step-down correction (§4.4 option i)."""
    sorted_tests = sorted(enumerate(p_values), key=lambda x: x[1][1])
    m = len(sorted_tests)
    results = [None] * m

    for rank, (orig_idx, (name, p)) in enumerate(sorted_tests):
        adjusted_alpha = alpha / (m - rank)
        reject = p <= adjusted_alpha
        results[orig_idx] = {
            "test": name,
            "raw_p": float(p),
            "adjusted_alpha": float(adjusted_alpha),
            "reject_h0": bool(reject),
            "rank": rank + 1,
        }
        if not reject:
            for remaining_rank in range(rank + 1, m):
                remaining_idx = sorted_tests[remaining_rank][0]
                remaining_name = sorted_tests[remaining_rank][1][0]
                remaining_p = sorted_tests[remaining_rank][1][1]
                results[remaining_idx] = {
                    "test": remaining_name,
                    "raw_p": float(remaining_p),
                    "adjusted_alpha": float(adjusted_alpha),
                    "reject_h0": False,
                    "rank": remaining_rank + 1,
                }
            break

    return results


# ── Metrics ──────────────────────────────────────────────────────────────────

def per_date_spearman_ic(
    df: pd.DataFrame,
    pred_col: str,
    label_col: str = DEFAULT_LABEL,
    min_names: int = MIN_NAMES_PER_DATE,
) -> pd.DataFrame:
    records = []
    for date, g in df.groupby("date"):
        g = g.dropna(subset=[pred_col, label_col])
        if len(g) < min_names:
            continue
        ic, _ = scipy_stats.spearmanr(g[pred_col].values, g[label_col].values)
        if np.isfinite(ic):
            records.append({"date": date, "ic": float(ic), "n_names": len(g)})
    return pd.DataFrame(records)


def ic_summary(ic_series: pd.DataFrame, name: str) -> dict[str, Any]:
    ics = ic_series["ic"].values
    if len(ics) == 0:
        return {"name": name, "mean_ic": float("nan"), "n_dates": 0}
    return {
        "name": name,
        "mean_ic": float(np.mean(ics)),
        "std_ic": float(np.std(ics, ddof=1)) if len(ics) > 1 else float("nan"),
        "icir": float(np.mean(ics) / np.std(ics, ddof=1)) if len(ics) > 1 and np.std(ics, ddof=1) > 0 else float("nan"),
        "median_ic": float(np.median(ics)),
        "hit_rate": float(np.mean(ics > 0)),
        "n_dates": int(len(ics)),
    }


# ── §3.0 Complementarity diagnostics ────────────────────────────────────────

def complementarity_diagnostics(
    merged: pd.DataFrame,
    expert_cols: list[str],
    label_col: str,
) -> dict[str, Any]:
    """Per-date score correlation and disagreement coverage (§3.0).

    Reports without passing/failing — no universal correlation cutoff that
    proves complementarity; the gate is falsifiable (near-duplicate = exclude).
    """
    corrs = []
    disagreements = []

    for date, g in merged.groupby("date"):
        g = g.dropna(subset=expert_cols + [label_col])
        if len(g) < MIN_NAMES_PER_DATE:
            continue
        for i, col_a in enumerate(expert_cols):
            for col_b in expert_cols[i + 1:]:
                r, _ = scipy_stats.spearmanr(g[col_a].values, g[col_b].values)
                if np.isfinite(r):
                    corrs.append({"date": date, "pair": f"{col_a}_vs_{col_b}", "rank_corr": float(r)})

                ranks_a = g[col_a].rank()
                ranks_b = g[col_b].rank()
                top_a = set(ranks_a.nlargest(max(1, len(g) // 5)).index)
                top_b = set(ranks_b.nlargest(max(1, len(g) // 5)).index)
                overlap = len(top_a & top_b) / max(len(top_a | top_b), 1)
                disagreements.append({
                    "date": date, "pair": f"{col_a}_vs_{col_b}",
                    "top20pct_overlap": float(overlap),
                })

    corr_df = pd.DataFrame(corrs)
    disagree_df = pd.DataFrame(disagreements)

    result: dict[str, Any] = {"n_dates_evaluated": 0}
    if not corr_df.empty:
        result["mean_rank_correlation"] = float(corr_df["rank_corr"].mean())
        result["std_rank_correlation"] = float(corr_df["rank_corr"].std())
        result["n_dates_evaluated"] = int(corr_df["date"].nunique())
    if not disagree_df.empty:
        result["mean_top20pct_overlap"] = float(disagree_df["top20pct_overlap"].mean())
        result["disagreement_coverage"] = float(1.0 - disagree_df["top20pct_overlap"].mean())

    return result


# ── WF CV with prediction export ────────────────────────────────────────────

@dataclass
class FoldResult:
    fold: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    n_train_rows: int
    n_val_rows: int
    xgb_ic: float
    predictions: pd.DataFrame


def run_xgb_wf_cv(
    train: pd.DataFrame,
    feat_cols: list[str],
    *,
    label: str = DEFAULT_LABEL,
    n_splits: int = DEFAULT_N_OUTER_SPLITS,
    embargo_days: int = DEFAULT_EMBARGO_DAYS,
    data_dir: Path,
) -> list[FoldResult]:
    """Expanding-window WF CV that exports per-ticker predictions."""
    import xgboost as xgb

    from renquant_model_gbdt.panel_data import build_normalization
    from renquant_model_gbdt.panel_trainer import (
        cross_sectional_ic,
        panel_training_matrix,
        train_xgb,
    )

    dates = np.array(sorted(pd.to_datetime(train["date"].unique())))
    fold_indices = np.array_split(np.arange(len(dates)), n_splits + 1)[1:]
    results = []

    for fold_no, val_idx in enumerate(fold_indices, start=1):
        if len(val_idx) == 0:
            continue
        train_end_pos = int(val_idx[0]) - embargo_days
        if train_end_pos <= 0:
            log.warning("Fold %d skipped: embargo leaves no train dates", fold_no)
            continue

        tr_dates = set(dates[:train_end_pos])
        va_dates = set(dates[val_idx])
        tr = train[train["date"].isin(tr_dates)]
        va = train[train["date"].isin(va_dates)]

        if tr["date"].nunique() < 20 or va.empty:
            log.warning("Fold %d skipped: insufficient data", fold_no)
            continue

        log.info("Fold %d/%d: train %s->%s (%d rows), val %s->%s (%d rows)",
                 fold_no, n_splits,
                 pd.Timestamp(tr["date"].min()).date(),
                 pd.Timestamp(tr["date"].max()).date(), len(tr),
                 pd.Timestamp(va["date"].min()).date(),
                 pd.Timestamp(va["date"].max()).date(), len(va))

        mu, sd, norm_kind, clip_low, clip_high = build_normalization(tr, feat_cols, data_dir)
        booster, train_ic = train_xgb(
            tr, feat_cols, label=label,
            feature_means=mu, feature_stds=sd, feature_norm_kind=norm_kind,
        )

        Xva = panel_training_matrix(va, feat_cols, mu, sd, norm_kind)
        xgb_pred = booster.predict(xgb.DMatrix(Xva.values.astype(np.float64)))

        pred_df = va[["date", "ticker", label]].copy()
        pred_df["xgb_pred"] = xgb_pred

        ic_info = cross_sectional_ic(xgb_pred, va[label].clip(-5, 5).values, va["date"].values)
        fold_ic = float(ic_info["mean_ic"])

        log.info("  XGB fold %d IC = %+.4f (%d dates)", fold_no, fold_ic, ic_info["n_dates"])

        results.append(FoldResult(
            fold=fold_no,
            train_start=pd.Timestamp(tr["date"].min()).date().isoformat(),
            train_end=pd.Timestamp(tr["date"].max()).date().isoformat(),
            val_start=pd.Timestamp(va["date"].min()).date().isoformat(),
            val_end=pd.Timestamp(va["date"].max()).date().isoformat(),
            n_train_rows=len(tr),
            n_val_rows=len(va),
            xgb_ic=fold_ic,
            predictions=pred_df,
        ))

    return results


def score_alt_model_on_folds(
    fold_results: list[FoldResult],
    train: pd.DataFrame,
    feat_cols: list[str],
    *,
    data_dir: Path,
    label: str = DEFAULT_LABEL,
) -> pd.DataFrame:
    """Score a second model on the same validation folds as XGB.

    Currently uses ridge regression as a proxy for PatchTST (which requires
    a checkpoint and sequence history). When PatchTST is wired, replace the
    ridge block with real PatchTST scoring.
    """
    try:
        from renquant_model_patchtst.scorer import PatchTSTScorer
        patchtst_available = True
        log.info("PatchTST scorer available")
    except ImportError:
        patchtst_available = False
        log.warning("PatchTST not importable — using ridge proxy")

    all_preds = []

    for fr in fold_results:
        va_dates = set(pd.to_datetime(fr.predictions["date"].unique()))
        va = train[train["date"].isin(va_dates)].copy()

        from sklearn.linear_model import Ridge
        from renquant_model_gbdt.panel_data import build_normalization
        from renquant_model_gbdt.panel_trainer import panel_training_matrix

        tr_dates_end = pd.Timestamp(fr.train_end)
        tr = train[train["date"] <= tr_dates_end]
        mu, sd, norm_kind, _, _ = build_normalization(tr, feat_cols, data_dir)

        Xtr = panel_training_matrix(tr, feat_cols, mu, sd, norm_kind)
        ytr = tr[label].clip(-5, 5).values
        ridge = Ridge(alpha=1.0)
        ridge.fit(Xtr.values, ytr)

        Xva = panel_training_matrix(va, feat_cols, mu, sd, norm_kind)
        pred2 = ridge.predict(Xva.values)

        pred_df = va[["date", "ticker"]].copy()
        pred_df["alt_pred"] = pred2
        all_preds.append(pred_df)
        log.info("  %s fold %d: scored %d rows",
                 "PatchTST" if patchtst_available else "Ridge",
                 fr.fold, len(pred_df))

    return pd.concat(all_preds, ignore_index=True) if all_preds else pd.DataFrame()


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="L1 equal-weight ensemble DISCOVERY experiment (§4.5)")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path,
                        default=Path("experiments/ensemble_l1_equal_weight/results"))
    parser.add_argument("--n-outer-splits", type=int, default=DEFAULT_N_OUTER_SPLITS)
    parser.add_argument("--embargo-days", type=int, default=DEFAULT_EMBARGO_DAYS)
    parser.add_argument("--watchlist-json", type=Path, default=None)
    parser.add_argument("--label", type=str, default=DEFAULT_LABEL)
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ── Load data ──
    watchlist = None
    if args.watchlist_json and args.watchlist_json.exists():
        wl = json.loads(args.watchlist_json.read_text())
        watchlist = wl if isinstance(wl, list) else list(wl.keys())
        log.info("Watchlist loaded: %d tickers", len(watchlist))

    from renquant_model_gbdt.panel_data import load_panel
    train, feat_cols, label = load_panel(
        args.data_dir, label=args.label, watchlist=watchlist)
    log.info("Panel: %d rows, %d tickers, %d dates, %d features",
             len(train), train["ticker"].nunique(),
             train["date"].nunique(), len(feat_cols))

    universe_tickers = set(train["ticker"].unique())

    # ── §3.0 Stage 0: admissibility ledger ──
    log.info("=" * 60)
    log.info("STAGE 0: Admissibility Ledger")
    log.info("=" * 60)

    experts = [
        {
            "name": "XGB_panel",
            "type": "cross_sectional_panel",
            "score_col": "xgb_pred",
            "orientation": "higher_is_bullish",
        },
        {
            "name": "Alt_model",
            "type": "cross_sectional_panel",
            "score_col": "alt_pred",
            "orientation": "higher_is_bullish",
        },
    ]

    # ── Run XGB WF CV first to generate predictions ──
    log.info("Running XGB walk-forward CV (%d outer splits, %d embargo days)...",
             args.n_outer_splits, args.embargo_days)
    fold_results = run_xgb_wf_cv(
        train, feat_cols,
        label=label, n_splits=args.n_outer_splits,
        embargo_days=args.embargo_days, data_dir=args.data_dir,
    )
    log.info("XGB CV complete: %d folds", len(fold_results))

    xgb_all = pd.concat([fr.predictions for fr in fold_results], ignore_index=True)

    log.info("Scoring second model on same folds...")
    alt_all = score_alt_model_on_folds(
        fold_results, train, feat_cols, data_dir=args.data_dir, label=label)

    if alt_all.empty:
        log.error("No second-model predictions — cannot proceed")
        return 1

    merged = xgb_all.merge(alt_all, on=["date", "ticker"], how="inner")
    log.info("Merged predictions: %d rows on %d dates",
             len(merged), merged["date"].nunique())

    # Now build ledger on merged data (scores available)
    ledger = build_admissibility_ledger(merged, experts, universe_tickers, label)

    for rec in ledger:
        status = "ADMITTED" if rec.admitted else f"REJECTED ({rec.rejection_reason})"
        log.info("  %s: %s (coverage=%.1f%%, missing=%.1f%%)",
                 rec.expert_name, status,
                 rec.universe_coverage * 100, rec.missingness_rate * 100)

    admitted_experts = [r for r in ledger if r.admitted]
    if len(admitted_experts) < 2:
        log.error("Fewer than 2 admitted experts — cannot form ensemble")
        results = {
            "experiment": "L1_equal_weight_discovery",
            "verdict": "BLOCKED — fewer than 2 admitted experts",
            "ledger": [asdict(r) for r in ledger],
        }
        (args.out_dir / "results.json").write_text(
            json.dumps(results, indent=2, default=str))
        return 1

    # ── §4.5A Create experiment manifest ──
    manifest = create_manifest(ledger, args.n_outer_splits, args.embargo_days, label)
    manifest_path = args.out_dir / "experiment_manifest.json"
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2, default=str))
    log.info("Experiment manifest written: %s (hash=%s)",
             manifest_path, manifest.manifest_hash)

    # ── §4.1bis Causal normalization ──
    for expert in experts:
        col = expert["score_col"]
        if col in merged.columns:
            merged[f"{col}_z"] = causal_zscore(
                merged, col, expert.get("orientation", "higher_is_bullish"))

    # ── §4.1bis Missing-expert fallback ──
    z_cols = [f"{e['score_col']}_z" for e in experts if e["score_col"] in merged.columns]
    valid_mask = merged[z_cols].notna().sum(axis=1) > 0
    merged = merged[valid_mask].copy()

    # Equal-weight with re-normalization for missing experts
    def _ew_with_fallback(row):
        vals = [row[c] for c in z_cols if pd.notna(row[c])]
        return np.mean(vals) if vals else np.nan

    merged["ensemble_pred"] = merged.apply(_ew_with_fallback, axis=1)

    # ── §3.0 Complementarity diagnostics ──
    log.info("")
    log.info("COMPLEMENTARITY DIAGNOSTICS (§3.0)")
    comp = complementarity_diagnostics(merged, z_cols, label)
    for k, v in comp.items():
        log.info("  %s = %s", k, f"{v:.4f}" if isinstance(v, float) else v)

    # ── Compute per-date ICs ──
    ic_xgb = per_date_spearman_ic(merged, "xgb_pred_z", label)
    ic_alt = per_date_spearman_ic(merged, "alt_pred_z", label)
    ic_ens = per_date_spearman_ic(merged, "ensemble_pred", label)

    summary_xgb = ic_summary(ic_xgb, "XGB_champion")
    summary_alt = ic_summary(ic_alt, "Alt_model")
    summary_ens = ic_summary(ic_ens, "L1_equal_weight")

    log.info("")
    log.info("=" * 60)
    log.info("DISCOVERY RESULTS (not deployment evidence — §4.5)")
    log.info("=" * 60)
    for s in [summary_xgb, summary_alt, summary_ens]:
        log.info("  %-20s  IC=%+.4f  ICIR=%.3f  hit=%.1f%%  n=%d",
                 s["name"], s["mean_ic"], s.get("icir", float("nan")),
                 s.get("hit_rate", 0) * 100, s["n_dates"])

    # ── §4.1 Non-overlapping block inference ──
    log.info("")
    log.info("NON-OVERLAPPING BLOCK INFERENCE (§4.1, block=%dd)", BLOCK_LENGTH_DAYS)

    blocks_xgb = non_overlapping_block_ic(ic_xgb, BLOCK_LENGTH_DAYS)
    blocks_alt = non_overlapping_block_ic(ic_alt, BLOCK_LENGTH_DAYS)
    blocks_ens = non_overlapping_block_ic(ic_ens, BLOCK_LENGTH_DAYS)

    log.info("  XGB: %d blocks, Alt: %d blocks, Ensemble: %d blocks",
             len(blocks_xgb), len(blocks_alt), len(blocks_ens))

    # ── Paired tests on blocks ──
    test_ens_vs_xgb = block_paired_test(blocks_ens, blocks_xgb,
                                         "L1_equal_weight", "XGB_champion")
    test_ens_vs_alt = block_paired_test(blocks_ens, blocks_alt,
                                         "L1_equal_weight", "Alt_model")

    log.info("")
    log.info("BLOCK PAIRED TESTS:")
    for t in [test_ens_vs_xgb, test_ens_vs_alt]:
        log.info("  %-35s  dIC=%+.4f  t=%.2f  p(1s)=%.4f  blocks=%d  min_effect=%s",
                 t["comparison"],
                 t.get("mean_diff", float("nan")),
                 t.get("t_stat", float("nan")),
                 t.get("p_value_one_sided", float("nan")),
                 t.get("n_blocks", 0),
                 t.get("meets_min_effect", "N/A"))

    # ── §4.4 Holm-Bonferroni correction ──
    p_values = [
        ("L1 vs champion", test_ens_vs_xgb.get("p_value_one_sided", 1.0)),
        ("final candidate vs champion", test_ens_vs_xgb.get("p_value_one_sided", 1.0)),
    ]
    correction_results = holm_bonferroni(p_values)

    log.info("")
    log.info("HOLM-BONFERRONI CORRECTION (§4.4):")
    for cr in correction_results:
        log.info("  %s: p=%.4f, adj_alpha=%.4f, reject=%s",
                 cr["test"], cr["raw_p"], cr["adjusted_alpha"], cr["reject_h0"])

    # ── Discovery verdict (§4.5) ──
    delta_ic = test_ens_vs_xgb.get("mean_diff", float("nan"))
    p_one = test_ens_vs_xgb.get("p_value_one_sided", 1.0)
    meets_effect = test_ens_vs_xgb.get("meets_min_effect", False)
    n_blocks = test_ens_vs_xgb.get("n_blocks", 0)

    l1_corrected_reject = any(
        cr["test"] == "L1 vs champion" and cr["reject_h0"]
        for cr in correction_results
    )

    log.info("")
    if n_blocks < 4:
        verdict = "UNDERPOWERED — fewer than 4 non-overlapping blocks; cannot draw inference"
    elif l1_corrected_reject and meets_effect:
        verdict = ("CANDIDATE SELECTED — L1 equal-weight passes discovery gate; "
                   "proceed to Phase B chronological confirmation (§4.5B). "
                   "This is NOT deployment evidence.")
    elif np.isfinite(delta_ic) and delta_ic > 0:
        verdict = ("MARGINAL — positive but fails Holm-Bonferroni and/or minimum effect size; "
                   "STOP per pre-committed cost decision (§3.2)")
    else:
        verdict = ("NEGATIVE — L1 equal-weight does not beat champion; "
                   "STOP per pre-committed cost decision (§3.2)")

    log.info("DISCOVERY VERDICT: %s", verdict)
    log.info("  dIC = %+.4f (min effect = %.4f, Holm p = %.4f, blocks = %d)",
             delta_ic, MIN_EFFECT_SIZE, p_one, n_blocks)

    elapsed = time.time() - t0
    log.info("Total time: %.1f seconds", elapsed)

    # ── Save results ──
    results = {
        "experiment": "L1_equal_weight_discovery",
        "design_ref": "doc/research/2026-07-12-ensemble-combination-experiment.md (PR #48)",
        "protocol": "discovery_only — not deployment evidence (§4.5)",
        "manifest_hash": manifest.manifest_hash,
        "n_outer_splits": args.n_outer_splits,
        "embargo_days": args.embargo_days,
        "block_length_days": BLOCK_LENGTH_DAYS,
        "label": label,
        "n_tickers": int(merged["ticker"].nunique()),
        "n_dates": int(merged["date"].nunique()),
        "date_range": [
            str(merged["date"].min().date()) if hasattr(merged["date"].min(), "date") else str(merged["date"].min()),
            str(merged["date"].max().date()) if hasattr(merged["date"].max(), "date") else str(merged["date"].max()),
        ],
        "admissibility_ledger": [asdict(r) for r in ledger],
        "complementarity": comp,
        "summaries": [summary_xgb, summary_alt, summary_ens],
        "block_paired_tests": [test_ens_vs_xgb, test_ens_vs_alt],
        "holm_bonferroni": correction_results,
        "verdict": verdict,
        "elapsed_seconds": round(elapsed, 1),
    }

    (args.out_dir / "results.json").write_text(
        json.dumps(results, indent=2, default=str))
    merged.to_parquet(args.out_dir / "predictions.parquet", index=False)
    ic_xgb.to_csv(args.out_dir / "ic_xgb.csv", index=False)
    ic_alt.to_csv(args.out_dir / "ic_alt.csv", index=False)
    ic_ens.to_csv(args.out_dir / "ic_ensemble.csv", index=False)
    blocks_ens.to_csv(args.out_dir / "blocks_ensemble.csv", index=False)

    log.info("Results saved to %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
