"""Legacy-parity panel-LTR trainer (model-side), reconciled into the engine.

This is a **verbatim port** of the model-side training logic from the umbrella's
``scripts/train_production_model.py`` (the production GBDT trainer), moved here so
``renquant-model`` owns one canonical engine that reproduces the legacy artifact
**byte-for-byte** (booster + OOS/CV metadata + schema), excluding the two fields
the legacy script intentionally randomizes (``train_run_id`` = ``uuid4``,
``trained_date`` = ``utcnow``).

Why a dedicated module rather than reusing :class:`PanelLTRModel`:
``PanelLTRModel`` is a *different* trainer — it casts features to ``float32``,
force-merges ``DEFAULT_PARAMS`` (``alpha=0.5``, ``tree_method="hist"``, …), does
not clip the label, and bucketizes for ndcg/map. Any of those changes the
booster. Byte-identity requires the legacy math exactly: ``float64`` features,
label ``clip(-5, 5)``, the caller's params dict verbatim, date-sorted rows via
``np.argsort``, and per-date ``np.unique`` group sizes.

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

log = logging.getLogger("renquant_model_gbdt.legacy_panel_trainer")

# Legacy production defaults (scripts/train_production_model.py). Callers may
# override via ``config``; defaults preserve byte-identity with production.
LEGACY_PARAMS: dict[str, Any] = {
    "objective": "rank:pairwise", "eta": 0.05, "max_depth": 5,
    "min_child_weight": 50, "subsample": 0.7, "colsample_bytree": 0.7,
    "verbosity": 0, "seed": 42,
}
LEGACY_N_ROUNDS = 100
LEGACY_LABEL = "fwd_60d_excess"

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
    label: str = LEGACY_LABEL,
    *,
    params: dict[str, Any] | None = None,
    num_boost_round: int = LEGACY_N_ROUNDS,
    feature_means: np.ndarray | None = None,
    feature_stds: np.ndarray | None = None,
    feature_norm_kind: list[str] | None = None,
):
    """Train rank:pairwise XGB and return (booster, in-sample IC).

    Verbatim port of the legacy ``train_xgb`` — float64 features, label
    ``clip(-5, 5)``, date-sorted rows, per-date ``np.unique`` group sizes.
    """
    import xgboost as xgb  # noqa: PLC0415
    from scipy.stats import spearmanr  # noqa: PLC0415

    xgb_params = dict(LEGACY_PARAMS if params is None else params)

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
    label: str = LEGACY_LABEL,
    params: dict[str, Any] | None = None,
    num_boost_round: int = LEGACY_N_ROUNDS,
    n_splits: int = 3,
    embargo_days: int = 60,
) -> dict:
    """Purged expanding-window CV (verbatim port of the legacy artifact-contract CV).

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


def build_model_artifact(
    booster: Any,
    feat_cols: list[str],
    mu: np.ndarray,
    sd: np.ndarray,
    train: pd.DataFrame,
    *,
    params: dict[str, Any],
    num_boost_round: int = LEGACY_N_ROUNDS,
    feature_norm_kind: list[str] | None = None,
    feature_raw_clip_low: list[float | None] | None = None,
    feature_raw_clip_high: list[float | None] | None = None,
    label_used: str = LEGACY_LABEL,
    lookahead_days: int = 60,
    train_ic: float | None = None,
    cv_result: dict | None = None,
    train_run_id: str | None = None,
    training_notes: str = "",
) -> dict:
    """Assemble the model-side artifact dict (verbatim port of legacy build_artifact).

    Data/contract-side fields (cutoff, side_label, sentiment, fingerprint, smoke)
    are layered on by the driver to preserve byte-identity with the legacy script.
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
    return artifact
