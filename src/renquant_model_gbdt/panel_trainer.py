"""Panel-LTR trainer (model-side) — the canonical GBDT training engine.

The model-side training logic from the umbrella's
``scripts/train_production_model.py`` lives here so ``renquant-model`` owns one
engine that reproduces the production artifact **byte-for-byte** (booster +
OOS/CV metadata + version:3 schema), excluding the two fields the umbrella script
intentionally randomizes (``train_run_id`` = ``uuid4``, ``trained_date`` =
``utcnow``).

Byte-identity contract — the booster depends on exactly: ``float64`` features
(xgboost ``DMatrix`` downcasts to float32 internally, so this is moot, but kept),
label ``clip(-5, 5)``, the caller's params dict used verbatim (no implicit
defaults merge — a stray ``alpha`` / ``tree_method`` changes the tree), date-
sorted rows via ``np.argsort``, and per-date ``np.unique`` group sizes for
rank:pairwise pairing.

Data-side pieces (normalization built from on-disk stats/fund files, config
fingerprint, sentiment gate, inference-smoke) stay in the driver and are injected
— this module reads no files and imports no ``kernel.*``. The only shared
dependency is :func:`transform_feature_frame`, already lifted byte-identically
into this package.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from .feature_transform import transform_feature_frame

log = logging.getLogger("renquant_model_gbdt.panel_trainer")

# Production defaults (scripts/train_production_model.py). Callers may
# override via ``config``; defaults preserve byte-identity with production.
PANEL_LTR_PARAMS: dict[str, Any] = {
    "objective": "rank:pairwise", "eta": 0.05, "max_depth": 5,
    "min_child_weight": 50, "subsample": 0.7, "colsample_bytree": 0.7,
    "verbosity": 0, "seed": 42,
}
DEFAULT_N_ROUNDS = 100
DEFAULT_LABEL = "fwd_60d_excess"

# A builder that, given (train_df, feat_cols), returns
# (feature_means, feature_stds, feature_norm_kind, raw_clip_low, raw_clip_high).
NormalizationBuilder = Callable[
    [pd.DataFrame, list[str]],
    tuple[np.ndarray, np.ndarray, list[str], list[Optional[float]], list[Optional[float]]],
]


def _feature_meta(
    mu: np.ndarray,
    sd: np.ndarray,
    kind: list[str],
    raw_clip_low: list[float | None] | None = None,
    raw_clip_high: list[float | None] | None = None,
) -> dict:
    meta = {
        "feature_means": np.asarray(mu, dtype=float).tolist(),
        "feature_stds": np.asarray(sd, dtype=float).tolist(),
        "feature_norm_kind": list(kind),
    }
    if raw_clip_low is not None and raw_clip_high is not None:
        meta["feature_raw_clip_low"] = list(raw_clip_low)
        meta["feature_raw_clip_high"] = list(raw_clip_high)
        meta["feature_raw_clip_fit_split"] = "train"
        meta["feature_preprocess_version"] = 2
    return meta


def panel_training_matrix(
    frame: pd.DataFrame,
    feat_cols: list[str],
    mu: np.ndarray,
    sd: np.ndarray,
    norm_kind: list[str],
) -> pd.DataFrame:
    return transform_feature_frame(
        frame.reindex(columns=feat_cols, fill_value=float("nan")),
        feat_cols,
        _feature_meta(mu, sd, norm_kind),
        source_space="panel",
    )


def train_xgb(
    train: pd.DataFrame,
    feat_cols: list[str],
    label: str = DEFAULT_LABEL,
    *,
    params: dict[str, Any] | None = None,
    num_boost_round: int = DEFAULT_N_ROUNDS,
    feature_means: np.ndarray | None = None,
    feature_stds: np.ndarray | None = None,
    feature_norm_kind: list[str] | None = None,
):
    """Train rank:pairwise XGB and return (booster, in-sample IC).

    Verbatim port of the production ``train_xgb`` — float64 features, label
    ``clip(-5, 5)``, date-sorted rows, per-date ``np.unique`` group sizes.
    """
    import xgboost as xgb  # noqa: PLC0415
    from scipy.stats import spearmanr  # noqa: PLC0415

    xgb_params = dict(PANEL_LTR_PARAMS if params is None else params)

    if feature_means is not None and feature_stds is not None and feature_norm_kind is not None:
        Xdf = panel_training_matrix(train, feat_cols, feature_means, feature_stds, feature_norm_kind)
    else:
        Xdf = train.reindex(columns=feat_cols, fill_value=0).fillna(0)
    Xtr = Xdf.values.astype(np.float64)
    ytr = train[label].clip(-5, 5).values.astype(np.float64)

    sort_idx = np.argsort(train["date"].values)
    Xs, ys, ds = Xtr[sort_idx], ytr[sort_idx], train["date"].values[sort_idx]
    _, gsz = np.unique(ds, return_counts=True)

    log.info("Training XGB rank:pairwise (params=%s)...", xgb_params)
    dtr = xgb.DMatrix(Xs, label=ys)
    dtr.set_group(gsz)
    booster = xgb.train(xgb_params, dtr, num_boost_round=num_boost_round)

    # In-sample IC sanity (uses unclipped label, per group, min 5 names).
    train_pred = booster.predict(xgb.DMatrix(Xtr))
    train_check = train.copy()
    train_check["pred"] = train_pred
    train_ics = []
    for _, g in train_check.groupby("date"):
        if len(g) < 5:
            continue
        ic, _ = spearmanr(g["pred"], g[label])
        if not np.isnan(ic):
            train_ics.append(ic)
    train_ic_mean = float(np.mean(train_ics)) if train_ics else float("nan")
    log.info("In-sample train IC: %+.4f (sanity check, not OOS)", train_ic_mean)
    return booster, train_ic_mean


def cross_sectional_ic(pred: np.ndarray, y: np.ndarray, dates: np.ndarray) -> dict:
    """Mean daily Spearman IC for a prediction vector (verbatim port)."""
    from scipy.stats import spearmanr  # noqa: PLC0415

    df = pd.DataFrame({"pred": pred, "y": y, "date": dates})
    ics = []
    for _, g in df.groupby("date"):
        if len(g) < 5:
            continue
        ic, _ = spearmanr(g["pred"], g["y"])
        if not np.isnan(ic):
            ics.append(float(ic))
    return {
        "mean_ic": float(np.mean(ics)) if ics else float("nan"),
        "n_dates": int(len(ics)),
        "per_date_ic": ics,
    }


def evaluate_walk_forward_cv(
    train: pd.DataFrame,
    feat_cols: list[str],
    *,
    normalization_builder: NormalizationBuilder,
    label: str = DEFAULT_LABEL,
    params: dict[str, Any] | None = None,
    num_boost_round: int = DEFAULT_N_ROUNDS,
    n_splits: int = 3,
    embargo_days: int = 60,
) -> dict:
    """Purged expanding-window CV (verbatim port of the production artifact-contract CV).

    Each fold trains only on dates strictly before the validation fold, leaving
    ``embargo_days`` trading dates between train and validation, and rebuilds
    train-only normalization per fold (via the injected ``normalization_builder``)
    to avoid leakage.
    """
    import xgboost as xgb  # noqa: PLC0415

    n_splits = max(1, int(n_splits))
    embargo_days = max(0, int(embargo_days))
    dates = np.array(sorted(pd.to_datetime(train["date"].unique())))
    if len(dates) < (n_splits + 1) * 5:
        raise ValueError(f"not enough dates for {n_splits} folds: {len(dates)}")

    fold_indices = np.array_split(np.arange(len(dates)), n_splits + 1)[1:]
    folds = []
    for fold_no, val_idx in enumerate(fold_indices, start=1):
        if len(val_idx) == 0:
            continue
        train_end_pos = int(val_idx[0]) - embargo_days
        if train_end_pos <= 0:
            log.warning("CV fold %d skipped: embargo leaves no train dates", fold_no)
            continue
        tr_dates = set(dates[:train_end_pos])
        va_dates = set(dates[val_idx])
        tr = train[train["date"].isin(tr_dates)]
        va = train[train["date"].isin(va_dates)]
        if tr["date"].nunique() < 20 or va.empty:
            log.warning(
                "CV fold %d skipped: n_train_dates=%d n_val_rows=%d",
                fold_no, tr["date"].nunique(), len(va),
            )
            continue

        mu, sd, norm_kind, _, _ = normalization_builder(tr, feat_cols)
        booster, train_ic = train_xgb(
            tr, feat_cols, label=label, params=params, num_boost_round=num_boost_round,
            feature_means=mu, feature_stds=sd, feature_norm_kind=norm_kind,
        )
        Xva = panel_training_matrix(va, feat_cols, mu, sd, norm_kind)
        pred = booster.predict(xgb.DMatrix(Xva.values.astype(np.float64)))
        y = va[label].clip(-5, 5).values.astype(np.float64)
        ic_info = cross_sectional_ic(pred, y, va["date"].values)
        fold_ic = float(ic_info["mean_ic"])
        folds.append({
            "fold": fold_no,
            "train_start": pd.Timestamp(tr["date"].min()).date().isoformat(),
            "train_end": pd.Timestamp(tr["date"].max()).date().isoformat(),
            "val_start": pd.Timestamp(va["date"].min()).date().isoformat(),
            "val_end": pd.Timestamp(va["date"].max()).date().isoformat(),
            "n_train_rows": int(len(tr)),
            "n_val_rows": int(len(va)),
            "train_ic": float(train_ic),
            "ic": fold_ic,
            "n_ic_dates": int(ic_info["n_dates"]),
        })
        log.info("CV fold %d/%d IC=%+.4f train_dates=%d val_dates=%d",
                 fold_no, n_splits, fold_ic, tr["date"].nunique(), va["date"].nunique())

    per_fold = [f["ic"] for f in folds if np.isfinite(f["ic"])]
    if not per_fold:
        raise ValueError("walk-forward CV produced no finite folds")
    return {
        "cv_method": "purged_walk_forward",
        "cv_n_splits": n_splits,
        "cv_embargo_days": embargo_days,
        "oos_mean_ic": float(np.mean(per_fold)),
        "oos_std_ic": float(np.std(per_fold, ddof=1)) if len(per_fold) > 1 else 0.0,
        "oos_per_fold_ic": [float(v) for v in per_fold],
        "folds": folds,
    }


def training_data_cutoffs(train: "pd.DataFrame | None", label: str | None) -> dict:
    """MEASURED data-cutoff stamps for the training frame — computed, never asserted.

    Returns (possibly empty) ``metadata`` entries:

    * ``data_cutoff_date`` — max ``date`` over rows whose ``label`` column is
      non-null (the last LABELED training row; the freshness axis orch#906 /
      the rq104 model-freshness monitor's 28-day fast-axis SLA key on).
    * ``feature_cutoff_date`` — max ``date`` over EVERY row of the frame (the
      last feature row the trainer consumed). Data-pipeline-health provenance
      only, never a freshness axis (umbrella #423 round-3: fresh unlabeled
      rows must not make a stale model read fresh). With the current
      ``load_panel`` (which drops unlabeled rows) the two coincide BY
      CONSTRUCTION; both stay independently measured so a loader that keeps
      unlabeled rows stamps them honestly apart.

    An unusable frame (no ``date`` column, empty, no label-complete row for
    ``data_cutoff_date``) leaves the corresponding key ABSENT — a consumer
    that requires the stamp then fails closed, which is the correct refusal;
    a fabricated date would defeat the entire ``trained_date``-is-not-a-
    freshness-axis discipline (orch#745/#906).
    """
    out: dict[str, Any] = {}
    if train is None:
        return out
    columns = getattr(train, "columns", [])
    if "date" not in columns or len(train) == 0:
        return out
    dates = pd.to_datetime(train["date"], errors="coerce")
    feature_max = dates.max()
    if not pd.isna(feature_max):
        out["feature_cutoff_date"] = pd.Timestamp(feature_max).date().isoformat()
        out["feature_cutoff_date_rule"] = (
            "MEASURED max(date) over every training-frame row consumed — "
            "data-pipeline-health provenance, NOT a freshness axis (#423 r3)")
    if label and label in columns:
        labeled = dates[train[label].notna()]
        if len(labeled):
            label_max = labeled.max()
            if not pd.isna(label_max):
                out["data_cutoff_date"] = pd.Timestamp(label_max).date().isoformat()
                out["data_cutoff_date_rule"] = (
                    "MEASURED max(date) over training rows with a non-null "
                    f"{label!r} label — never asserted from window arithmetic "
                    "or the wall clock (orch#906)")
    return out


def build_model_artifact(
    booster: Any,
    feat_cols: list[str],
    mu: np.ndarray,
    sd: np.ndarray,
    train: pd.DataFrame,
    *,
    params: dict[str, Any],
    num_boost_round: int = DEFAULT_N_ROUNDS,
    feature_norm_kind: list[str] | None = None,
    feature_raw_clip_low: list[float | None] | None = None,
    feature_raw_clip_high: list[float | None] | None = None,
    label_used: str = DEFAULT_LABEL,
    lookahead_days: int = 60,
    train_ic: float | None = None,
    cv_result: dict | None = None,
    train_run_id: str | None = None,
    training_notes: str = "",
) -> dict:
    """Assemble the model-side artifact dict (verbatim port of the production build_artifact).

    Data/contract-side fields (cutoff, side_label, sentiment, fingerprint, smoke)
    are layered on by the driver to preserve byte-identity with the production script (scripts/train_production_model.py).

    One deliberate addition over the production script (orch#906): the trainer
    itself stamps ``metadata.data_cutoff_date`` / ``metadata.feature_cutoff_date``
    MEASURED from the training frame it consumed (see
    :func:`training_data_cutoffs`), because the daily rq104 model-freshness
    monitor fails closed to UNKNOWN on an artifact with no binding data cutoff
    ("a fresh ``trained_date`` over stale data is not fresh"). ``metadata`` is
    classified OPERATIONAL in ``renquant_common.model_fingerprint`` (and
    denylisted in the legacy 0.8.1 hash), so the stamp is hash-neutral in both
    fingerprint implementations — the byte-identity that matters (booster math,
    predictive keys, content hash) is untouched.
    """
    raw_json = bytes(booster.save_raw(raw_format="json")).decode("utf-8")
    artifact = {
        "version": 3,
        "kind": "panel_ltr_xgboost",
        "trained_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "feature_cols": feat_cols,
        "feature_means": mu.tolist(),
        "feature_stds": sd.tolist(),
        "feature_norm_kind": list(feature_norm_kind or ["legacy_full_z"] * len(feat_cols)),
        "feature_source_contract": {
            "raw": (
                "apply feature_raw_clip_low/high when present, then "
                "feature_means/stds, fillna, and z-clip before scoring "
                "live/sim rows"
            ),
            "panel": "apply only feature_norm_kind entries that are raw in the prebuilt panel",
        },
        "params": dict(params),
        "best_iter": num_boost_round,
        "booster_raw_json": raw_json,
        "panel_shape": {
            "rows": int(train.shape[0]),
            "tickers": int(train["ticker"].nunique()),
            "dates": int(train["date"].nunique()),
        },
        "label_col": label_used,
        "lookahead_days": lookahead_days,
        "train_run_id": train_run_id,
        "training_train_ic": train_ic,
        "training_notes": training_notes,
    }
    if cv_result:
        artifact.update({
            "oos_mean_ic": cv_result.get("oos_mean_ic"),
            "oos_std_ic": cv_result.get("oos_std_ic"),
            "oos_per_fold_ic": cv_result.get("oos_per_fold_ic"),
            "cv_method": cv_result.get("cv_method"),
            "cv_n_splits": cv_result.get("cv_n_splits"),
            "cv_embargo_days": cv_result.get("cv_embargo_days"),
            "cv_folds": cv_result.get("folds"),
            "eval_ic": (
                cv_result.get("oos_per_fold_ic")[-1]
                if cv_result.get("oos_per_fold_ic") else None
            ),
        })
    if feature_raw_clip_low is not None and feature_raw_clip_high is not None:
        if len(feature_raw_clip_low) != len(feat_cols) or len(feature_raw_clip_high) != len(feat_cols):
            raise ValueError("feature_raw_clip_low/high length must match feature_cols")
        artifact["feature_raw_clip_low"] = list(feature_raw_clip_low)
        artifact["feature_raw_clip_high"] = list(feature_raw_clip_high)
        artifact["feature_raw_clip_fit_split"] = "train"
        artifact["feature_preprocess_version"] = 2
    # orch#906: the binding data cutoff, MEASURED from the consumed frame. An
    # unusable frame stamps nothing (fail-closed downstream), never a guess.
    cutoffs = training_data_cutoffs(train, label_used)
    if cutoffs:
        artifact["metadata"] = cutoffs
    return artifact
