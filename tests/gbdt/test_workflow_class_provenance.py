"""F-7 round 4: verified workflow-classification -> manifest provenance.

Codex review 2026-07-14 on PR #55 (quoted in full in
``renquant_model_common.workflow_provenance``'s module docstring) found that
``BuildArtifactManifestTask`` hardcoded ``provenance = {"kind": "none"}``
unconditionally, regardless of whether the invocation was genuine canonical
production training or part of a registered exploratory/experiment run
writing to a brand-new path with no pre-existing classification marker for
the round-3 on-disk check to find -- "the producer is therefore
self-classifying an experiment artifact as none, precisely the bypass the
gate must prevent."

This file proves the fix with the EXACT adversarial scenario Codex asked for:
run the SAME real producer (``BuildArtifactManifestTask`` via
``PanelGbdtTrainingPipeline``, not a mock) under a genuinely registered
experiment context, writing to a FRESH path, and prove it does NOT get
``"none"`` -- it must correctly detect and honestly report ``"experiment"``.
It also proves the guard rails around that: an "experiment" declaration with
no registry index reference, or no on-disk marker, is rejected rather than
trusted; and an unrecognized ``workflow_class`` is rejected too.

The positive control -- genuine canonical publication still succeeds and
still gets ``kind="none"`` -- lives in ``test_training_pipeline.py`` (it
already asserted this for the round-3 fix; F-7 round 4 only changed HOW that
"none" is derived, from a hardcoded default to an explicit
``workflow_class=WORKFLOW_CLASS_CANONICAL`` declaration).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from renquant_model_gbdt import (
    WORKFLOW_CLASS_EXPERIMENT,
    PanelGbdtTrainingPipeline,
    TrainingContext,
)

# renquant_artifacts.experiment_registry only exists on the (as of this PR,
# unmerged) renquant-artifacts#24 branch -- skip these tests, rather than
# hard-erroring the whole collection, when the local sibling checkout is
# still on main. Same idiom this repo already uses for torch/transformers
# (see tests/patchtst/test_training_wiring.py).
experiment_registry = pytest.importorskip("renquant_artifacts.experiment_registry")
write_experiment_classification = experiment_registry.write_experiment_classification


def _dataset_manifest() -> dict:
    return {
        "dataset_id": "alpha158_fund_fixture",
        "fingerprint": "sha256:test",
        "schema_version": "fixture-v1",
        "uri": "object://renquant-data/alpha158_fund_fixture.parquet",
        "asset_class": "equity",
    }


def _loader(manifest: dict):
    return {"rows": [1, 2, 3], "manifest": manifest}


def _trainer(dataset, config: dict, output_dir: Path):
    return {
        "artifact_id": "gbdt-workflow-class-fixture",
        "model_family": "gbdt-panel-ltr",
        "fingerprint": "sha256:model",
        "uri": "object://renquant-artifacts/gbdt-workflow-class-fixture.json",
        "promotion_status": "candidate",
        "feature_cols": ["alpha_1", "alpha_2"],
        "local_artifact_path": str(output_dir / "gbdt-workflow-class-fixture.json"),
        "trained_date": "2026-05-25",
        "config_fingerprint": "sha256:config",
        "panel_shape": {"rows": 1000, "cols": 2},
        "lookahead_days": 5,
        "train_run_id": "run-workflow-class",
        "oos_mean_ic": 0.031,
        "oos_std_ic": 0.012,
        "oos_per_fold_ic": [0.02, 0.04, 0.033],
        "cv_method": "purged-walk-forward",
        "cv_embargo_days": 5,
    }, {"kind": "global_calibrator"}


def _validator(artifact: dict, dataset, config: dict):
    return {"oos_mean_ic": 0.031, "train_ic": 0.154}


def _write_registry_index(path: Path, *, experiment_id: str, manifest_digest: str) -> None:
    path.write_text(json.dumps({
        experiment_id: {"digest": manifest_digest, "path": "irrelevant/for/this/test.json"},
    }))


# ---------------------------------------------------------------------------
# workflow_class is a required, no-default, auditable declaration
# ---------------------------------------------------------------------------


def test_workflow_class_has_no_default_and_is_required(tmp_path: Path) -> None:
    """TrainingContext must not silently default workflow_class -- this is
    the literal bug Codex flagged: a caller must make an explicit,
    per-invocation, auditable declaration.
    """
    with pytest.raises(TypeError):
        TrainingContext(  # type: ignore[call-arg]
            dataset_manifest=_dataset_manifest(),
            model_config={},
            output_dir=tmp_path / "out",
        )


def test_invalid_workflow_class_is_rejected(tmp_path: Path) -> None:
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"strategy": "renquant_104"},
        output_dir=tmp_path / "out",
        workflow_class="bogus",
    )

    with pytest.raises(ValueError, match="workflow_class must be one of"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


# ---------------------------------------------------------------------------
# workflow_class="experiment" is independently verified, never trusted
# ---------------------------------------------------------------------------


def test_experiment_declaration_without_registry_index_path_is_rejected(tmp_path: Path) -> None:
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"strategy": "renquant_104"},  # no experiment_registry_index_path
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="experiment_registry_index_path"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


def test_experiment_declaration_without_on_disk_marker_is_rejected(tmp_path: Path) -> None:
    """A bare workflow_class='experiment' claim with no real marker on disk
    must be rejected, not trusted -- this is the "independently verify, not
    just trust" requirement.
    """
    output_dir = tmp_path / "out"
    registry_index_path = tmp_path / "registry_index.json"
    _write_registry_index(registry_index_path, experiment_id="exp-x", manifest_digest="sha256:x")

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="no.*marker exists"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


def test_experiment_declaration_with_unregistered_marker_is_rejected(tmp_path: Path) -> None:
    """A real on-disk marker whose digest is NOT in the immutable registry
    index must also be rejected -- the marker's self-reported content alone
    is not sufficient, it must cross-check against the immutable index.
    """
    output_dir = tmp_path / "out"
    registry_index_path = tmp_path / "registry_index.json"
    # Index registers a DIFFERENT experiment than the one the marker claims.
    _write_registry_index(registry_index_path, experiment_id="some-other-exp", manifest_digest="sha256:other")

    write_experiment_classification(
        output_dir,
        experiment_id="exp-not-registered",
        manifest_path="irrelevant.json",
        manifest_digest="sha256:not-registered",
        config_digest="sha256:cfg",
    )

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="registration could not be verified"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


# ---------------------------------------------------------------------------
# THE adversarial integration test Codex asked for
# ---------------------------------------------------------------------------


def test_registered_experiment_at_fresh_path_is_never_none(tmp_path: Path) -> None:
    """Adversarial integration test (Codex, 2026-07-14): execute the SAME
    model producer (the real ``BuildArtifactManifestTask``, via
    ``PanelGbdtTrainingPipeline`` -- not a mock) under a registered
    experiment context at a FRESH artifact path, and prove it cannot obtain
    canonical/none classification.

    The path is genuinely fresh: nothing else has ever written to
    ``output_dir`` before this test's own
    ``write_experiment_classification()`` call, mirroring exactly the gap
    Codex described -- "an exploratory or registered-experiment invocation
    can write to a fresh path with no prior EXPLORATORY_ONLY marker."

    Two things are proven together:

    1. The manifest built by ``BuildArtifactManifestTask`` correctly reports
       ``provenance == {"kind": "experiment", ...}`` -- NOT the old
       unconditional ``{"kind": "none"}`` bug -- verified via the real,
       non-mocked ``renquant_artifacts.experiment_registry`` machinery
       (on-disk marker + immutable registry-index cross-check).
    2. That correctly-classified manifest is THEN unconditionally rejected
       by the real, non-mocked registry-side promotion gate
       (``validate_artifact_manifest`` ->
       ``verify_artifact_provenance`` -> ``reject_exploratory_promotion``),
       proving a registered-experiment invocation cannot obtain
       canonical/none classification through this producer end-to-end, not
       merely that a field happens to say the right string.
    """
    output_dir = tmp_path / "fresh_experiment_run"
    assert not output_dir.exists(), "path must be genuinely fresh for this test to be meaningful"

    registry_index_path = tmp_path / "manifest_registry_index.json"
    experiment_id = "exp-adversarial-fresh-path-2026-07-14"
    manifest_digest = "sha256:adversarial-fresh-path-digest"
    _write_registry_index(registry_index_path, experiment_id=experiment_id, manifest_digest=manifest_digest)

    # The registered-experiment harness writes its classification marker
    # BEFORE any reusable output is produced -- exactly like the real
    # run_sim_104.py experiment-mode contract -- at the SAME fresh path this
    # training run uses as its output_dir.
    write_experiment_classification(
        output_dir,
        experiment_id=experiment_id,
        manifest_path="irrelevant/for/this/test.json",
        manifest_digest=manifest_digest,
        config_digest="sha256:config-digest",
    )

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="Cannot promote output of registered experiment"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    # The manifest WAS correctly built and correctly classified as
    # "experiment" before the registry-side promotion gate independently
    # rejected it for promotion -- this is NOT the old bug (silent "none"),
    # it is a correctly-detected, correctly-rejected "experiment".
    assert ctx.artifact_manifest is not None
    assert ctx.artifact_manifest["provenance"]["kind"] == "experiment"
    assert ctx.artifact_manifest["provenance"] != {"kind": "none"}
    assert ctx.artifact_manifest["provenance"]["dir"] == str(output_dir)
    assert ctx.artifact_manifest["provenance"]["registry_index_path"] == str(registry_index_path)
