"""Cross-repo regression guard for the 2026-07-01 fingerprint-unification fix.

Root cause of the recurring production incident (2026-05-27, 2026-06-22,
2026-07-01): renquant-model's calibrator-fit script
(`fit_calibrator_alpha158_fund.py`) and renquant-pipeline's runtime
scorer-binding check (`panel_scorer.py`, called from
`_assert_calibrator_matches_scorer` in `job_panel_scoring.py`) each
hand-copied `model_content_sha256` with DIFFERENT included/excluded field
sets — an ALLOWLIST here vs. a DENYLIST there. A calibrator fit in this
repo could never match the runtime check in renquant-pipeline, by
construction.

Fix: both repos now import the identical function from
`renquant_common.model_fingerprint`. This test is the guard that should
have caught the original bug — it pins that the renquant-model fit-time
path and the renquant-pipeline runtime path produce the IDENTICAL hash on
a synthetic panel-LTR payload. If someone re-forks a local copy in either
repo in the future without noticing, this test fails.
"""
from __future__ import annotations

import pytest

renquant_pipeline_panel_scorer = pytest.importorskip(
    "renquant_pipeline.kernel.panel_pipeline.panel_scorer"
)

from renquant_common.model_fingerprint import model_content_sha256 as common_model_content_sha256  # noqa: E402
from renquant_model_gbdt.fit_calibrator_alpha158_fund import (  # noqa: E402
    model_content_sha256 as model_repo_model_content_sha256,
)


def _payload() -> dict:
    return {
        "kind": "panel_ltr_xgboost",
        "version": 3,
        "feature_cols": ["a", "b", "c"],
        "params": {"objective": "rank:pairwise", "max_depth": 4},
        "booster_raw_json": '{"fake": "booster"}',
        "label_col": "fwd_60d_excess",
        "trained_date": "2026-06-01",
        "metadata": {"note": "irrelevant"},
    }


def test_model_and_pipeline_fingerprint_entry_points_are_the_shared_function() -> None:
    """Not just value-equal — the SAME function object on both sides. This
    is what structurally guarantees fit-time and runtime agree forever,
    instead of merely agreeing today by coincidence."""
    assert model_repo_model_content_sha256 is common_model_content_sha256
    assert renquant_pipeline_panel_scorer.model_content_sha256 is common_model_content_sha256


def test_calibrator_fit_fingerprint_matches_runtime_scorer_fingerprint() -> None:
    """The actual bug scenario: fit-time (this repo) computes a fingerprint
    for a scorer artifact; runtime (renquant-pipeline) computes a
    fingerprint for the same artifact payload at scorer-load time. They
    MUST match, or `_assert_calibrator_matches_scorer` fail-closes on a
    freshly-fit, otherwise-valid calibrator."""
    payload = _payload()
    fit_time_fp = model_repo_model_content_sha256(payload)
    runtime_fp = renquant_pipeline_panel_scorer.model_content_sha256(payload)
    assert fit_time_fp == runtime_fp


def test_metadata_only_drift_does_not_break_the_binding_across_repos() -> None:
    """Simulates the WF-gate / promotion stamping that happens AFTER
    calibrator fitting: the scorer artifact accrues promotion metadata, but
    the runtime fingerprint (recomputed at scorer-load time from the now
    heavier payload) must still equal the fingerprint the calibrator was
    fit against (computed from the lighter pre-promotion payload)."""
    pre_promotion_payload = _payload()
    fit_time_fp = model_repo_model_content_sha256(pre_promotion_payload)

    post_promotion_payload = dict(pre_promotion_payload)
    post_promotion_payload.update({
        "wf_gate_metadata": {"tier": 3},
        "promotion_status": "promoted",
        "cv_method": "purged_kfold",
        "train_run_id": "run-456",
        "oos_mean_ic": 0.041,
    })
    runtime_fp_after_promotion = renquant_pipeline_panel_scorer.model_content_sha256(
        post_promotion_payload
    )
    assert fit_time_fp == runtime_fp_after_promotion
