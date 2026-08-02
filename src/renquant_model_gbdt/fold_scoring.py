"""PUBLIC fold-scoring contract for lineage evaluation.

This is the ONE supported way for external consumers (the WF gate's lineage lane,
renquant-backtesting#96) to score rows with a persisted fold artifact using the
RECIPE transform — the transform that produced the committed evidence corpora.
Everything else in ``renquant_model_gbdt`` remains training-internal; consumers
must not import ``panel_trainer`` directly (review finding on backtesting#96:
an undeclared cross-repo training-internal import is not a stable interface).

Contract:
* input artifact = a persisted fold artifact dict self-carrying
  ``feature_cols`` / ``feature_means`` (dict) / ``feature_stds`` (dict) /
  ``feature_norm_kind`` (LIST of per-feature kinds) / ``booster_raw_json``;
* the returned scorer takes a TICKER-INDEXED frame carrying the feature columns
  and returns a float Series on exactly that index;
* validation is FAIL-CLOSED at load: missing fields, non-list ``norm_kind``
  (the 2026-08-01 stringified-norm_kind incident's exact shape), key-set
  mismatches, or length mismatches raise ``ValueError`` — never a silent
  best-effort score.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

_REQUIRED = ("feature_cols", "feature_means", "feature_stds",
             "feature_norm_kind", "booster_raw_json")
_KIND_VOCAB = {"global_z", "robust_z", "identity"}


def load_fold_scorer(artifact: dict) -> Callable[[pd.DataFrame], "pd.Series"]:
    """Validate a fold artifact and return the recipe-transform scorer."""
    import xgboost as xgb  # noqa: PLC0415 — heavyweight, load on use

    from .panel_trainer import panel_training_matrix  # noqa: PLC0415

    missing = [k for k in _REQUIRED if k not in artifact]
    if missing:
        raise ValueError(f"fold artifact missing required fields: {missing}")
    feat_cols = list(artifact["feature_cols"])
    norm_kind = artifact["feature_norm_kind"]
    if not isinstance(norm_kind, list):
        raise ValueError(
            "feature_norm_kind must be a LIST of per-feature kinds; got "
            f"{type(norm_kind).__name__} (the stringified-norm_kind incident shape)")
    if len(norm_kind) != len(feat_cols):
        raise ValueError(
            f"feature_norm_kind length {len(norm_kind)} != feature_cols {len(feat_cols)}")
    unknown = set(norm_kind) - _KIND_VOCAB
    if unknown:
        raise ValueError(f"unknown norm kinds: {sorted(unknown)}")
    for key in ("feature_means", "feature_stds"):
        stats = artifact[key]
        if not isinstance(stats, dict) or set(stats) != set(feat_cols):
            raise ValueError(f"{key} must be a dict keyed exactly by feature_cols")
    mu = np.array([artifact["feature_means"][c] for c in feat_cols], dtype=float)
    sd = np.array([artifact["feature_stds"][c] for c in feat_cols], dtype=float)
    booster = xgb.Booster()
    booster.load_model(bytearray(artifact["booster_raw_json"].encode("utf-8")))

    def _score(frame: pd.DataFrame) -> pd.Series:
        if frame.index.name != "ticker" and "ticker" in frame.columns:
            raise ValueError("scorer contract: frame must be TICKER-INDEXED")
        X = panel_training_matrix(frame.reset_index(), feat_cols, mu, sd, norm_kind)
        prob = booster.predict(xgb.DMatrix(X.values.astype(np.float64)))
        return pd.Series(prob, index=frame.index, dtype=float)

    return _score
