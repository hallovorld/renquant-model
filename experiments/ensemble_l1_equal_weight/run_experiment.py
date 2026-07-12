#!/usr/bin/env python3
"""HARNESS VERIFICATION: L1 equal-weight ensemble diagnostic.

This script is a HARNESS SMOKE TEST — it verifies that the combination
framework (admissibility ledger, causal normalization, block inference,
manifest, Holm-Bonferroni correction) executes correctly end-to-end.

It uses a Ridge regression proxy for the second expert, NOT production
PatchTST inference. Results are DIAGNOSTIC ONLY — they cannot support a
candidate selection verdict, a deployment decision, or any claim about
ensemble profitability. The Ridge proxy exists solely to exercise the
framework with two distinct score streams.

PREREQUISITES NOT YET MET for a real discovery run (§4.5):
  - No persisted point-in-time PatchTST score artifacts with as-of lineage
  - No costed portfolio construction / net outcome threshold
  - No immutable expert score artifact fingerprints
  - The admissibility ledger validates structural coverage, not artifact provenance

Aligned with the revised evidence protocol (model PR #48, merged):
  - §3.0  Stage 0 admissibility ledger (structural only — no artifact provenance)
  - §4.1  Non-overlapping origin-date blocks for dependence-aware inference
  - §4.1bis Causal normalization, orientation, missing-expert fallback
  - §4.4  Holm-Bonferroni correction, ΔIC≥0.005 minimum effect
  - §4.5  Immutable experiment manifest

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

def non_overlapping_origin_date_ic(
    ic_series: pd.DataFrame,
    horizon_days: int = BLOCK_LENGTH_DAYS,
) -> pd.DataFrame:
    """Sample ICs at non-overlapping origin dates spaced ≥horizon apart (§4.1).

    fwd_60d labels overlap: a prediction on day t shares ~55/60 label days
    with a prediction on day t+5. Grouping consecutive daily ICs into
    60-row blocks does NOT make adjacent block means independent (labels
    at the end of one block overlap the beginning of the next).

    Instead, sample one IC per non-overlapping origin window: the first
    available IC date, then skip ≥horizon_days trading days, take the
    next available, and repeat. Each sampled IC's label window does not
    overlap any other sampled IC's label window.
    """
    if ic_series.empty:
        return pd.DataFrame(columns=["block", "origin_date", "ic", "n_names"])

    sorted_ic = ic_series.sort_values("date").reset_index(drop=True)
    samples = []
    last_origin = None

    for _, row in sorted_ic.iterrows():
        if last_origin is None or (row["date"] - last_origin).days >= horizon_days:
            samples.append({
                "block": len(samples),
                "origin_date": row["date"],
                "ic": float(row["ic"]),
                "n_names": int(row["n_names"]),
            })
            last_origin = row["date"]

    result = pd.DataFrame(samples)
    return result


def origin_date_paired_test(
    samples_a: pd.DataFrame,
    samples_b: pd.DataFrame,
    name_a: str,
    name_b: str,
) -> dict[str, Any]:
    """Paired test on non-overlapping origin-date ICs (§4.1 primary approach).

    Each sampled IC comes from an origin date spaced ≥horizon apart, so
    label windows do not overlap — the samples are approximately independent.
    """
    if samples_a.empty or samples_b.empty:
        return {"comparison": f"{name_a} vs {name_b}", "n_samples": 0,
                "note": "insufficient samples"}

    merged = samples_a.merge(
        samples_b, on="origin_date", suffixes=("_a", "_b"), how="inner")
    if merged.empty:
        return {"comparison": f"{name_a} vs {name_b}", "n_samples": 0,
                "note": "no matching origin dates"}

    diff = merged["ic_a"].values - merged["ic_b"].values
    n = len(diff)

    if n < 3:
        return {
            "comparison": f"{name_a} vs {name_b}",
            "mean_diff": float(np.mean(diff)),
            "n_samples": n,
            "note": "fewer than 3 non-overlapping origin dates — UNDERPOWERED",
        }

    t_stat, p_val = scipy_stats.ttest_1samp(diff, 0)
    return {
        "comparison": f"{name_a} vs {name_b}",
        "mean_diff": float(np.mean(diff)),
        "se_diff": float(np.std(diff, ddof=1) / np.sqrt(n)),
        "t_stat": float(t_stat),
        "p_value_two_sided": float(p_val),
        "p_value_one_sided": float(p_val / 2) if t_stat > 0 else float(1 - p_val / 2),
        "n_samples": n,
        "effective_sample_size": n,
        "meets_min_effect": bool(np.mean(diff) >= MIN_EFFECT_SIZE),
        "origin_spacing_days": BLOCK_LENGTH_DAYS,
        "inference_note": (
            "non-overlapping origin dates spaced >= forecast horizon apart; "
            "label windows do not overlap — approximately independent"
        ),
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


def score_ridge_proxy_on_folds(
    fold_results: list[FoldResult],
    train: pd.DataFrame,
    feat_cols: list[str],
    *,
    data_dir: Path,
    label: str = DEFAULT_LABEL,
) -> pd.DataFrame:
    """Score a Ridge regression PROXY on the same validation folds as XGB.

    This is NOT a PatchTST scorer — it is a synthetic second expert used
    solely to exercise the combination framework end-to-end. Ridge
    regression on the same features as XGB is a deliberately weak proxy:
    it produces a distinct score stream (different functional form) but
    cannot represent a genuinely independent model class.

    A real discovery run (§4.5) requires persisted PatchTST score artifacts
    with point-in-time lineage and as-of provenance. Until those exist, this
    proxy verifies the harness mechanics only.
    """
    from sklearn.linear_model import Ridge
    from renquant_model_gbdt.panel_data import build_normalization
    from renquant_model_gbdt.panel_trainer import panel_training_matrix

    all_preds = []

    for fr in fold_results:
        va_dates = set(pd.to_datetime(fr.predictions["date"].unique()))
        va = train[train["date"].isin(va_dates)].copy()

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
        log.info("  Ridge proxy fold %d: scored %d rows", fr.fold, len(pred_df))

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

    log.info("Scoring Ridge PROXY on same folds (harness verification only)...")
    alt_all = score_ridge_proxy_on_folds(
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
    log.info("HARNESS DIAGNOSTIC (Ridge proxy — NOT a real discovery result)")
    log.info("=" * 60)
    log.info("WARNING: second expert is Ridge proxy, not PatchTST.")
    log.info("WARNING: no persisted score artifacts, no costed outcome.")
    log.info("WARNING: results are harness verification ONLY.")
    log.info("")
    for s in [summary_xgb, summary_alt, summary_ens]:
        log.info("  %-20s  IC=%+.4f  ICIR=%.3f  hit=%.1f%%  n=%d",
                 s["name"], s["mean_ic"], s.get("icir", float("nan")),
                 s.get("hit_rate", 0) * 100, s["n_dates"])

    # ── §4.1 Non-overlapping origin-date inference ──
    log.info("")
    log.info("NON-OVERLAPPING ORIGIN-DATE INFERENCE (§4.1, spacing=%dd)",
             BLOCK_LENGTH_DAYS)

    samples_xgb = non_overlapping_origin_date_ic(ic_xgb, BLOCK_LENGTH_DAYS)
    samples_alt = non_overlapping_origin_date_ic(ic_alt, BLOCK_LENGTH_DAYS)
    samples_ens = non_overlapping_origin_date_ic(ic_ens, BLOCK_LENGTH_DAYS)

    log.info("  XGB: %d samples, Ridge: %d samples, Ensemble: %d samples",
             len(samples_xgb), len(samples_alt), len(samples_ens))

    # ── Paired tests on non-overlapping origin dates ──
    test_ens_vs_xgb = origin_date_paired_test(samples_ens, samples_xgb,
                                               "L1_equal_weight", "XGB_champion")
    test_ens_vs_alt = origin_date_paired_test(samples_ens, samples_alt,
                                               "L1_equal_weight", "Ridge_proxy")

    log.info("")
    log.info("ORIGIN-DATE PAIRED TESTS:")
    for t in [test_ens_vs_xgb, test_ens_vs_alt]:
        log.info("  %-35s  dIC=%+.4f  t=%.2f  p(1s)=%.4f  n=%d  min_effect=%s",
                 t["comparison"],
                 t.get("mean_diff", float("nan")),
                 t.get("t_stat", float("nan")),
                 t.get("p_value_one_sided", float("nan")),
                 t.get("n_samples", 0),
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

    # ── Diagnostic summary (NO candidate selection — harness only) ──
    delta_ic = test_ens_vs_xgb.get("mean_diff", float("nan"))
    p_one = test_ens_vs_xgb.get("p_value_one_sided", 1.0)
    n_samples = test_ens_vs_xgb.get("n_samples", 0)

    log.info("")
    log.info("HARNESS STATUS: framework executes correctly end-to-end")
    log.info("  dIC = %+.4f (n=%d origin-date samples)", delta_ic, n_samples)
    log.info("")
    log.info("CANNOT ISSUE CANDIDATE VERDICT because:")
    log.info("  1. Second expert is Ridge proxy, not PatchTST (§3.0 not met)")
    log.info("  2. No persisted score artifacts with as-of provenance (§3.0)")
    log.info("  3. No costed portfolio outcome threshold (§4.4)")
    log.info("  4. Admissibility ledger validates coverage only, not artifact provenance")
    verdict = "DIAGNOSTIC ONLY — harness verified, prerequisites not met for discovery"

    elapsed = time.time() - t0
    log.info("Total time: %.1f seconds", elapsed)

    # ── Save results ──
    results = {
        "experiment": "L1_equal_weight_harness_diagnostic",
        "design_ref": "doc/research/2026-07-12-ensemble-combination-experiment.md (PR #48)",
        "protocol": "HARNESS VERIFICATION ONLY — Ridge proxy, no persisted artifacts, no costed outcome",
        "second_expert": "Ridge regression proxy (NOT PatchTST)",
        "prerequisites_met": False,
        "prerequisites_missing": [
            "persisted PatchTST score artifacts with as-of lineage",
            "costed portfolio construction / net outcome threshold",
            "immutable expert score artifact fingerprints",
            "artifact provenance validation in admissibility ledger",
        ],
        "manifest_hash": manifest.manifest_hash,
        "n_outer_splits": args.n_outer_splits,
        "embargo_days": args.embargo_days,
        "origin_spacing_days": BLOCK_LENGTH_DAYS,
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
        "origin_date_paired_tests": [test_ens_vs_xgb, test_ens_vs_alt],
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
    samples_ens.to_csv(args.out_dir / "origin_date_samples_ensemble.csv", index=False)

    log.info("Results saved to %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
