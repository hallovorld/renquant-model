"""M6 fingerprint-unification guard for panel_data.py.

Verifies that the StampFingerprintTask fallback (when no production
config_fingerprint is injected) uses the canonical
``renquant_common.model_fingerprint.model_content_sha256`` — the same
function the calibrator-fit and runtime scorer-binding sides use. The
old LOCAL ``content_fingerprint()`` hashed only 4 fields with different
serialization semantics, causing the 3 recurring fail-closed incidents
(2026-05-27, 06-22, 07-01).

Also guards:
* ``content_fingerprint`` (deprecated wrapper) delegates to the canonical
  impl and emits a DeprecationWarning.
* The ``StampFingerprintTask`` stamps a fingerprint identical to what the
  calibrator fit and pipeline runtime compute for the same payload.
"""
from __future__ import annotations

import warnings

import pytest

from renquant_common.model_fingerprint import (
    model_content_sha256 as canonical_model_content_sha256,
)
from renquant_model_gbdt.panel_data import (
    StampFingerprintTask,
    content_fingerprint,
    model_content_sha256 as panel_data_model_content_sha256,
)


def _minimal_artifact() -> dict:
    """A minimal panel-LTR artifact with all keys classified by the
    canonical PREDICTIVE_KEYS / OPERATIONAL_KEYS tables."""
    return {
        "kind": "panel_ltr_xgboost",
        "version": 3,
        "feature_cols": ["a0", "a1", "a2"],
        "feature_means": [0.0, 0.0, 0.0],
        "feature_stds": [1.0, 1.0, 1.0],
        "feature_norm_kind": ["global_z", "global_z", "global_z"],
        "feature_source_contract": {"raw": "clip+normalize", "panel": "identity"},
        "params": {"objective": "rank:pairwise", "max_depth": 4},
        "best_iter": 25,
        "booster_raw_json": '{"fake": "booster"}',
        "label_col": "fwd_60d_excess",
        "lookahead_days": 60,
        "panel_shape": {"rows": 720, "tickers": 12, "dates": 60},
        "trained_date": "2026-07-01",
        "train_run_id": "selftest",
        "training_train_ic": 0.15,
        "training_notes": "",
    }


def test_panel_data_imports_canonical_model_content_sha256() -> None:
    """The ``model_content_sha256`` imported in panel_data.py is the SAME
    function object as renquant-common's — not a re-fork."""
    assert panel_data_model_content_sha256 is canonical_model_content_sha256


def test_content_fingerprint_delegates_to_canonical() -> None:
    """The deprecated ``content_fingerprint`` wrapper must produce the SAME
    hash as the canonical ``model_content_sha256``."""
    artifact = _minimal_artifact()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy_fp = content_fingerprint(artifact)
    canonical_fp = canonical_model_content_sha256(artifact)
    assert legacy_fp == canonical_fp


def test_content_fingerprint_emits_deprecation_warning() -> None:
    """Callers still using the old name get a deprecation notice."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        content_fingerprint(_minimal_artifact())
    dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(dep_warnings) == 1
    assert "deprecated" in str(dep_warnings[0].message).lower()


class _FakeCtx:
    """Minimal stand-in for GbdtTrainingContext (avoids xgboost import)."""

    def __init__(self, artifact: dict, config_fingerprint: str | None = None,
                 config_fingerprint_fields: list[str] | None = None):
        self.artifact = artifact
        self.config_fingerprint = config_fingerprint
        self.config_fingerprint_fields = config_fingerprint_fields


def test_stamp_fingerprint_task_fallback_uses_canonical() -> None:
    """When no production config_fingerprint is injected, the task must
    stamp the artifact with the canonical model_content_sha256 hash."""
    artifact = _minimal_artifact()
    ctx = _FakeCtx(artifact)
    task = StampFingerprintTask()
    task.run(ctx)

    expected = canonical_model_content_sha256(artifact)
    assert ctx.artifact["config_fingerprint"] == expected


def test_stamp_fingerprint_task_injected_overrides_canonical() -> None:
    """When the orchestrator injects a production config_fingerprint, the
    task stamps that — not the canonical hash."""
    artifact = _minimal_artifact()
    injected_fp = "sha256:injected_by_orchestrator"
    ctx = _FakeCtx(artifact, config_fingerprint=injected_fp,
                   config_fingerprint_fields=["f1", "f2"])
    task = StampFingerprintTask()
    task.run(ctx)

    assert ctx.artifact["config_fingerprint"] == injected_fp
    assert ctx.artifact["config_fingerprint_fields"] == ["f1", "f2"]


def test_stamp_fingerprint_stable_across_operational_drift() -> None:
    """Adding OPERATIONAL-classified fields after stamping must not change
    the fingerprint — the exact property the old 4-field local impl broke
    when the pipeline's denylist diverged."""
    artifact = _minimal_artifact()
    ctx = _FakeCtx(artifact)
    task = StampFingerprintTask()
    task.run(ctx)
    fp_before = ctx.artifact["config_fingerprint"]

    # Accrue post-training operational metadata (WF gate, promotion).
    artifact.update({
        "wf_gate_metadata": {"tier": 3},
        "promotion_status": "promoted",
        "cv_method": "purged_walk_forward",
        "oos_mean_ic": 0.031,
        "train_run_id": "run-456",
    })
    fp_after = canonical_model_content_sha256(artifact)
    assert fp_before == fp_after


def test_stamp_fingerprint_changes_on_predictive_drift() -> None:
    """A change in a PREDICTIVE field (e.g. feature_cols) MUST produce a
    different fingerprint — the whole point of content hashing."""
    artifact_a = _minimal_artifact()
    artifact_b = _minimal_artifact()
    artifact_b["feature_cols"] = ["a0", "a1"]  # dropped a2

    fp_a = canonical_model_content_sha256(artifact_a)
    fp_b = canonical_model_content_sha256(artifact_b)
    assert fp_a != fp_b
