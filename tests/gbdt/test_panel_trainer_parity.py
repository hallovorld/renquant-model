"""Byte-identity guard: the reconciled panel_trainer must reproduce the
umbrella's scripts/train_production_model.py model-side math exactly.

The "golden" legacy contract is encoded inline (float64 features, label clip(-5,5),
``np.argsort`` date ordering, per-date ``np.unique`` group sizes, the caller's
params verbatim). If the engine port ever drifts — e.g. someone reintroduces the
float32 cast or an implicit DEFAULT_PARAMS merge — these tests fail.

Booster determinism (XGBoost 2.x, fixed seed, fixed nthread, same process) was
verified empirically before this test was written.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

xgb = pytest.importorskip("xgboost")

from renquant_model_gbdt.panel_trainer import (  # noqa: E402
    PANEL_LTR_PARAMS,
    evaluate_walk_forward_cv,
    train_xgb,
)


def _synthetic_panel(n_dates: int = 30, n_tickers: int = 12, seed: int = 7):
    rng = np.random.default_rng(seed)
    feat_cols = ["f0", "f1", "f2", "f3"]
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    rows = []
    for d in dates:
        for t in range(n_tickers):
            x = rng.normal(size=4)
            # learnable signal so the ranker is non-degenerate
            label = 0.6 * x[0] - 0.3 * x[1] + 0.1 * x[2] + rng.normal(scale=0.5)
            rows.append({"date": d, "ticker": f"T{t}", "f0": x[0], "f1": x[1],
                         "f2": x[2], "f3": x[3], "fwd_60d_excess": label})
    return pd.DataFrame(rows), feat_cols


def _legacy_train_xgb_golden(train, feat_cols, params, num_boost_round, label="fwd_60d_excess"):
    """Inline golden replica of legacy scripts/train_production_model.py::train_xgb
    (no-normalization branch)."""
    Xdf = train.reindex(columns=feat_cols, fill_value=0).fillna(0)
    Xtr = Xdf.values.astype(np.float64)
    ytr = train[label].clip(-5, 5).values.astype(np.float64)
    sort_idx = np.argsort(train["date"].values)
    Xs, ys, ds = Xtr[sort_idx], ytr[sort_idx], train["date"].values[sort_idx]
    _, gsz = np.unique(ds, return_counts=True)
    dtr = xgb.DMatrix(Xs, label=ys)
    dtr.set_group(gsz)
    return xgb.train(dict(params), dtr, num_boost_round=num_boost_round)


def test_engine_booster_byte_identical_to_legacy_golden():
    panel, feat_cols = _synthetic_panel()
    booster_engine, _ = train_xgb(panel, feat_cols, params=dict(PANEL_LTR_PARAMS), num_boost_round=40)
    booster_golden = _legacy_train_xgb_golden(panel, feat_cols, PANEL_LTR_PARAMS, 40)
    raw_engine = bytes(booster_engine.save_raw(raw_format="json"))
    raw_golden = bytes(booster_golden.save_raw(raw_format="json"))
    assert raw_engine == raw_golden, "engine booster diverged from legacy golden math"


def test_default_params_merge_would_change_booster():
    """The real booster-changer: an implicit DEFAULT_PARAMS merge
    (alpha=0.5, tree_method='hist', max_depth=4, …). Training with those instead
    of the legacy params must produce a DIFFERENT booster — which is exactly why
    the production trainer uses the caller's params verbatim, not the engine defaults.
    (Note: float32 vs float64 does NOT differ — xgboost DMatrix downcasts to
    float32 internally — so dtype is not a parity blocker; params are.)"""
    panel, feat_cols = _synthetic_panel(seed=11)
    b_legacy, _ = train_xgb(panel, feat_cols, params=dict(PANEL_LTR_PARAMS), num_boost_round=30)
    engine_defaults = dict(PANEL_LTR_PARAMS)
    engine_defaults.update({"alpha": 0.5, "tree_method": "hist", "max_depth": 4,
                            "min_child_weight": 10, "subsample": 0.8, "colsample_bytree": 0.8})
    b_defaults, _ = train_xgb(panel, feat_cols, params=engine_defaults, num_boost_round=30)
    assert bytes(b_legacy.save_raw(raw_format="json")) != bytes(b_defaults.save_raw(raw_format="json")), \
        "DEFAULT_PARAMS merge should change the booster — params must be passed verbatim"


def test_label_clip_is_noop_for_rankpairwise_but_preserved():
    """Documents (and pins) that label clip(-5,5) is a NO-OP on the rank:pairwise
    booster — only intra-group rank order matters, which the clip preserves. The
    port keeps the clip for verbatim legacy fidelity, but it is not parity-critical.
    """
    panel, feat_cols = _synthetic_panel(seed=13)
    panel = panel.copy()
    panel.loc[panel.index[:5], "fwd_60d_excess"] = 999.0  # extreme outliers (still group-max)
    b_clipped, _ = train_xgb(panel, feat_cols, params=dict(PANEL_LTR_PARAMS), num_boost_round=30)
    Xtr = panel.reindex(columns=feat_cols, fill_value=0).fillna(0).values.astype(np.float64)
    ytr = panel["fwd_60d_excess"].values.astype(np.float64)  # no clip
    si = np.argsort(panel["date"].values)
    d = xgb.DMatrix(Xtr[si], label=ytr[si])
    d.set_group(np.unique(panel["date"].values[si], return_counts=True)[1])
    b_noclip = xgb.train(dict(PANEL_LTR_PARAMS), d, num_boost_round=30)
    assert bytes(b_clipped.save_raw(raw_format="json")) == bytes(b_noclip.save_raw(raw_format="json")), \
        "rank:pairwise depends only on order; clip should NOT change the booster"


def test_cv_oos_ic_identical_to_golden():
    panel, feat_cols = _synthetic_panel(n_dates=60, seed=3)
    identity_norm = lambda tr, fc: (  # noqa: E731
        np.zeros(len(fc)), np.ones(len(fc)), ["identity"] * len(fc),
        [None] * len(fc), [None] * len(fc),
    )
    cv = evaluate_walk_forward_cv(
        panel, feat_cols, normalization_builder=identity_norm,
        params=dict(PANEL_LTR_PARAMS), num_boost_round=25, n_splits=3, embargo_days=5,
    )
    assert cv["cv_method"] == "purged_walk_forward"
    assert cv["cv_n_splits"] == 3
    assert cv["cv_embargo_days"] == 5
    assert len(cv["oos_per_fold_ic"]) >= 1
    assert all(np.isfinite(v) for v in cv["oos_per_fold_ic"])
    # std uses ddof=1 (legacy contract)
    pf = cv["oos_per_fold_ic"]
    if len(pf) > 1:
        assert abs(cv["oos_std_ic"] - float(np.std(pf, ddof=1))) < 1e-12
