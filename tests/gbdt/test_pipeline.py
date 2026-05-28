"""The structured ModelTrainingJob must equal the bare function calls.

Running the Task/Job orchestration over a GbdtTrainingContext produces the same
booster + artifact as calling train_xgb / evaluate_walk_forward_cv /
build_model_artifact directly — the Job is orchestration, not new logic. Guards
the byte-identity is not lost when training is expressed as Tasks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

xgb = pytest.importorskip("xgboost")

from renquant_model_gbdt import (  # noqa: E402
    GbdtTrainingContext,
    ModelTrainingJob,
    build_model_artifact,
    evaluate_walk_forward_cv,
    train_xgb,
)
from renquant_model_gbdt.panel_trainer import PANEL_LTR_PARAMS  # noqa: E402


def _panel(n_dates=40, n_tickers=12, seed=5):
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range("2020-01-01", periods=n_dates, freq="B"):
        for t in range(n_tickers):
            x = rng.normal(size=4)
            rows.append({"date": d, "ticker": f"T{t}", "f0": x[0], "f1": x[1],
                         "f2": x[2], "f3": x[3],
                         "fwd_60d_excess": 0.6 * x[0] - 0.3 * x[1] + rng.normal(scale=0.5)})
    return pd.DataFrame(rows), ["f0", "f1", "f2", "f3"]


def _identity_norm(tr, fc):
    return (np.zeros(len(fc)), np.ones(len(fc)), ["identity"] * len(fc),
            [None] * len(fc), [None] * len(fc))


def test_job_artifact_matches_direct_calls():
    panel, feat_cols = _panel()
    mu, sd, norm_kind, lo, hi = _identity_norm(panel, feat_cols)

    # Direct function calls (the reference path).
    cv = evaluate_walk_forward_cv(panel, feat_cols, normalization_builder=_identity_norm,
                                  params=dict(PANEL_LTR_PARAMS), num_boost_round=25,
                                  n_splits=3, embargo_days=5)
    booster, train_ic = train_xgb(panel, feat_cols, params=dict(PANEL_LTR_PARAMS),
                                  num_boost_round=25, feature_means=mu, feature_stds=sd,
                                  feature_norm_kind=norm_kind)
    direct = build_model_artifact(booster, feat_cols, mu, sd, panel,
                                  params=dict(PANEL_LTR_PARAMS), num_boost_round=25,
                                  feature_norm_kind=norm_kind, feature_raw_clip_low=lo,
                                  feature_raw_clip_high=hi, train_ic=train_ic, cv_result=cv,
                                  train_run_id="fixed", training_notes="t")

    # Structured Job path.
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=25, cv_n_splits=3, cv_embargo_days=5,
        train=panel, feat_cols=feat_cols, normalization_builder=_identity_norm,
        mu=mu, sd=sd, norm_kind=norm_kind, raw_clip_low=lo, raw_clip_high=hi,
        train_run_id="fixed", training_notes="t",
    )
    ModelTrainingJob().run(ctx)

    assert ctx.artifact is not None
    assert ctx.artifact["booster_raw_json"] == direct["booster_raw_json"], "Job booster diverged"
    assert ctx.artifact["oos_per_fold_ic"] == direct["oos_per_fold_ic"]
    # full dict identical (Job adds no extra fields when extra_artifact_fields empty)
    assert ctx.artifact == direct


def test_job_respects_skip_cv():
    panel, feat_cols = _panel()
    mu, sd, norm_kind, lo, hi = _identity_norm(panel, feat_cols)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=20, skip_cv=True,
        train=panel, feat_cols=feat_cols, normalization_builder=_identity_norm,
        mu=mu, sd=sd, norm_kind=norm_kind, raw_clip_low=lo, raw_clip_high=hi,
        train_run_id="x",
    )
    ModelTrainingJob().run(ctx)
    assert ctx.cv_result is None
    assert ctx.artifact is not None and "oos_mean_ic" not in ctx.artifact


def test_extra_artifact_fields_appended_in_order():
    panel, feat_cols = _panel()
    mu, sd, norm_kind, lo, hi = _identity_norm(panel, feat_cols)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=15, skip_cv=True,
        train=panel, feat_cols=feat_cols, normalization_builder=_identity_norm,
        mu=mu, sd=sd, norm_kind=norm_kind, raw_clip_low=lo, raw_clip_high=hi,
        train_run_id="x",
        extra_artifact_fields={"side_label": "wf", "cutoff_date": "2020-01-01"},
    )
    ModelTrainingJob().run(ctx)
    assert ctx.artifact["side_label"] == "wf"
    assert ctx.artifact["cutoff_date"] == "2020-01-01"
