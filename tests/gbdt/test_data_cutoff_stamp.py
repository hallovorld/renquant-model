"""orch#906: the panel trainer stamps a MEASURED binding data cutoff.

The daily rq104 model-freshness monitor fails closed to UNKNOWN on an artifact
with no binding data cutoff, and refuses ``trained_date`` by design ("a fresh
build over stale data is not fresh"). These tests pin that
``build_model_artifact`` stamps ``metadata.data_cutoff_date`` (max LABELED row
date) and ``metadata.feature_cutoff_date`` (max row date) COMPUTED from the
training frame it consumed — never asserted from the wall clock — and that the
Job driver's ``extra_artifact_fields`` merge cannot clobber them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb

from renquant_model_gbdt.panel_data import attach_inference_smoke
from renquant_model_gbdt.panel_trainer import (
    PANEL_LTR_PARAMS,
    build_model_artifact,
    train_xgb,
    training_data_cutoffs,
)
from renquant_model_gbdt.pipeline import GbdtTrainingContext, ModelTrainingJob

LABEL = "fwd_60d_excess"


def _frame_with_unlabeled_tail() -> tuple[pd.DataFrame, list[str]]:
    """30 labeled business days ending 2026-02-27, then 5 UNLABELED feature
    days ending 2026-03-06 — the shape a loader that keeps unlabeled rows
    would hand over (today's ``load_panel`` drops them; both stamps must stay
    independently measured either way)."""
    rng = np.random.default_rng(906)
    labeled = pd.bdate_range(end="2026-02-27", periods=30)
    unlabeled = pd.bdate_range(start="2026-03-02", periods=5)
    rows = []
    for d in labeled:
        for t in range(4):
            x = rng.normal(size=2)
            rows.append({"date": d, "ticker": f"T{t}", "f0": x[0], "f1": x[1],
                         LABEL: 0.5 * x[0] + rng.normal(scale=0.3)})
    for d in unlabeled:
        for t in range(4):
            x = rng.normal(size=2)
            rows.append({"date": d, "ticker": f"T{t}", "f0": x[0], "f1": x[1],
                         LABEL: np.nan})
    return pd.DataFrame(rows), ["f0", "f1"]


def _booster(frame: pd.DataFrame, feat_cols: list[str]):
    mu = np.zeros(len(feat_cols))
    sd = np.ones(len(feat_cols))
    kinds = ["identity"] * len(feat_cols)
    booster, train_ic = train_xgb(
        frame.dropna(subset=[LABEL]), feat_cols, label=LABEL,
        params=dict(PANEL_LTR_PARAMS), num_boost_round=5,
        feature_means=mu, feature_stds=sd, feature_norm_kind=kinds)
    return booster, train_ic, mu, sd, kinds


# ── the pure computation ─────────────────────────────────────────────────────

def test_cutoffs_are_measured_from_the_frame_not_the_clock():
    frame, _ = _frame_with_unlabeled_tail()
    stamps = training_data_cutoffs(frame, LABEL)
    assert stamps["data_cutoff_date"] == "2026-02-27"     # max LABELED row
    assert stamps["feature_cutoff_date"] == "2026-03-06"  # max row overall
    assert "never asserted" in stamps["data_cutoff_date_rule"]
    assert "NOT a freshness axis" in stamps["feature_cutoff_date_rule"]


def test_no_label_complete_row_stamps_no_data_cutoff():
    # An unusable frame must leave the key ABSENT (downstream fails closed) —
    # a fabricated date would defeat the trained_date-is-not-freshness rule.
    frame, _ = _frame_with_unlabeled_tail()
    frame[LABEL] = np.nan
    stamps = training_data_cutoffs(frame, LABEL)
    assert "data_cutoff_date" not in stamps
    assert stamps["feature_cutoff_date"] == "2026-03-06"  # still measurable


def test_empty_or_dateless_frame_stamps_nothing():
    assert training_data_cutoffs(None, LABEL) == {}
    assert training_data_cutoffs(pd.DataFrame({"x": [1]}), LABEL) == {}
    empty = pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"),
                          LABEL: pd.Series(dtype=float)})
    assert training_data_cutoffs(empty, LABEL) == {}


# ── the artifact carries the stamp ───────────────────────────────────────────

def test_build_model_artifact_stamps_metadata_cutoffs():
    frame, feat_cols = _frame_with_unlabeled_tail()
    booster, train_ic, mu, sd, kinds = _booster(frame, feat_cols)
    artifact = build_model_artifact(
        booster, feat_cols, mu, sd, frame, params=dict(PANEL_LTR_PARAMS),
        num_boost_round=5, feature_norm_kind=kinds, label_used=LABEL,
        train_ic=train_ic, train_run_id="t906")
    assert artifact["metadata"]["data_cutoff_date"] == "2026-02-27"
    assert artifact["metadata"]["feature_cutoff_date"] == "2026-03-06"
    # The stamp lives under metadata (OPERATIONAL / hash-neutral), never at
    # the top level where it would be an unclassified content-hash key.
    assert "data_cutoff_date" not in artifact


def test_smoke_attach_merges_and_keeps_the_stamp():
    frame, feat_cols = _frame_with_unlabeled_tail()
    booster, train_ic, mu, sd, kinds = _booster(frame, feat_cols)
    artifact = build_model_artifact(
        booster, feat_cols, mu, sd, frame, params=dict(PANEL_LTR_PARAMS),
        num_boost_round=5, feature_norm_kind=kinds, label_used=LABEL,
        train_ic=train_ic, train_run_id="t906")
    attach_inference_smoke(artifact, booster, feat_cols)
    assert artifact["metadata"]["data_cutoff_date"] == "2026-02-27"
    assert artifact["metadata"]["inference_smoke_test"]["n"] == 32


def test_content_hash_is_neutral_to_the_stamp():
    # ``metadata`` is classified OPERATIONAL in renquant_common — the stamp
    # must not move the model content hash (identity stays byte-stable).
    from renquant_common.model_fingerprint import model_content_sha256
    frame, feat_cols = _frame_with_unlabeled_tail()
    booster, train_ic, mu, sd, kinds = _booster(frame, feat_cols)
    artifact = build_model_artifact(
        booster, feat_cols, mu, sd, frame, params=dict(PANEL_LTR_PARAMS),
        num_boost_round=5, feature_norm_kind=kinds, label_used=LABEL,
        train_ic=train_ic, train_run_id="t906")
    stamped = model_content_sha256(artifact)
    stripped = {k: v for k, v in artifact.items() if k != "metadata"}
    assert model_content_sha256(stripped) == stamped


# ── the Job driver merge cannot clobber the stamp ────────────────────────────

def test_extra_metadata_fields_merge_instead_of_clobbering():
    # The Job path trains on the frame, so hand it the labeled slice the real
    # loader produces (load_panel drops unlabeled rows; xgboost refuses NaN
    # labels) — the stamps then coincide BY CONSTRUCTION, which is the
    # production shape.
    frame, feat_cols = _frame_with_unlabeled_tail()
    frame = frame.dropna(subset=[LABEL]).reset_index(drop=True)
    mu = np.zeros(len(feat_cols))
    sd = np.ones(len(feat_cols))
    ctx = GbdtTrainingContext(
        label=LABEL, params=dict(PANEL_LTR_PARAMS), num_boost_round=5,
        skip_cv=True, train=frame, feat_cols=feat_cols,
        mu=mu, sd=sd, norm_kind=["identity"] * len(feat_cols),
        train_run_id="t906",
        extra_artifact_fields={
            "effective_train_cutoff_date": "2026-02-27",
            "metadata": {"training_contract": {"n_rows": 120}},
        },
    )
    ModelTrainingJob().run(ctx)
    md = ctx.artifact["metadata"]
    # Both the driver's layered record AND the trainer's measured stamps live.
    assert md["training_contract"] == {"n_rows": 120}
    assert md["data_cutoff_date"] == "2026-02-27"
    assert md["feature_cutoff_date"] == "2026-02-27"  # labeled slice: coincide
    assert ctx.artifact["effective_train_cutoff_date"] == "2026-02-27"


def test_job_path_equals_direct_build_when_no_extra_fields():
    # The pre-existing byte-identity pin: the Job adds nothing beyond the
    # direct call when extra_artifact_fields is empty (stamps included).
    frame, feat_cols = _frame_with_unlabeled_tail()
    frame = frame.dropna(subset=[LABEL]).reset_index(drop=True)  # xgb: no NaN labels
    booster, train_ic, mu, sd, kinds = _booster(frame, feat_cols)
    direct = build_model_artifact(
        booster, feat_cols, mu, sd, frame, params=dict(PANEL_LTR_PARAMS),
        num_boost_round=5, feature_norm_kind=kinds, label_used=LABEL,
        train_ic=None, train_run_id="fixed")
    ctx = GbdtTrainingContext(
        label=LABEL, params=dict(PANEL_LTR_PARAMS), num_boost_round=5,
        skip_cv=True, train=frame, feat_cols=feat_cols,
        mu=mu, sd=sd, norm_kind=kinds, train_run_id="fixed",
    )
    ModelTrainingJob().run(ctx)
    assert ctx.artifact["metadata"] == direct["metadata"]
    assert set(ctx.artifact) == set(direct)
