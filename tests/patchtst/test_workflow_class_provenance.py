"""F-7 round 4: verified workflow-classification -> manifest provenance
(PatchTST twin of ``tests/gbdt/test_workflow_class_provenance.py`` -- see
that file's module docstring for the full Codex-review rationale).

``BuildPatchTstArtifactManifestTask`` had the SAME bug as its GBDT twin:
hardcoded ``provenance = {"kind": "none"}`` regardless of whether the
invocation was genuine canonical training or a registered experiment writing
to a fresh path. This file proves the adversarial scenario Codex asked for
against the PatchTST producer specifically.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from renquant_model_patchtst import (
    WORKFLOW_CLASS_CANONICAL,
    WORKFLOW_CLASS_EXPERIMENT,
    PatchTstTrainingContext,
    PatchTstTrainingPipeline,
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
        "dataset_id": "transformer_v4_fixture",
        "fingerprint": "sha256:test",
        "schema_version": "fixture-v1",
        "uri": "object://renquant-data/transformer_v4_fixture.parquet",
        "asset_class": "equity",
        "label_col": "fwd_60d_excess",
        "lookahead_days": 60,
        "split_policy": "purged-walk-forward",
    }


def _loader(manifest: dict):
    return {"seq_rows": 10, "label_col": manifest["label_col"]}


def _trainer(frame, config: dict, output_dir: Path):
    return {
        "artifact_id": "patchtst-workflow-class-fixture",
        "model_family": "patchtst",
        "fingerprint": "sha256:patchtst",
        "uri": "object://renquant-artifacts/patchtst-workflow-class-fixture.pt",
        "promotion_status": "shadow",
        "input_feature_cols": ["alpha_1", "alpha_2"],
        "trained_date": "2026-05-25",
        "config_fingerprint": "sha256:config",
        "sequence_shape": {"rows": 1000, "timesteps": 64, "features": 2},
        "lookahead_days": 60,
        "train_run_id": "patchtst-run-workflow-class",
        "oos_mean_ic": 0.03,
        "oos_std_ic": 0.01,
        "oos_per_fold_ic": [0.02, 0.04],
        "cv_method": "purged-walk-forward",
        "cv_embargo_days": 60,
    }, {"kind": "patchtst_calibrator"}


def _validator(checkpoint: dict, frame, config: dict):
    return {"real_ic": 0.03, "placebo_ic": 0.001, "passed": True}


def _write_registry_index(path: Path, *, experiment_id: str, manifest_digest: str) -> None:
    path.write_text(json.dumps({
        experiment_id: {"digest": manifest_digest, "path": "irrelevant/for/this/test.json"},
    }))


def test_workflow_class_has_no_default_and_is_required(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        PatchTstTrainingContext(  # type: ignore[call-arg]
            dataset_manifest=_dataset_manifest(),
            model_config={"architecture": "hf_patchtst"},
            output_dir=tmp_path / "out",
        )


def test_invalid_workflow_class_is_rejected(tmp_path: Path) -> None:
    ctx = PatchTstTrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"architecture": "hf_patchtst"},
        output_dir=tmp_path / "out",
        workflow_class="bogus",
    )

    with pytest.raises(ValueError, match="workflow_class must be one of"):
        PatchTstTrainingPipeline(_loader, _trainer, _validator).run(ctx)


def test_experiment_declaration_without_on_disk_marker_is_rejected(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    registry_index_path = tmp_path / "registry_index.json"
    _write_registry_index(registry_index_path, experiment_id="exp-x", manifest_digest="sha256:x")

    ctx = PatchTstTrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "architecture": "hf_patchtst",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="no.*marker exists"):
        PatchTstTrainingPipeline(_loader, _trainer, _validator).run(ctx)


def test_registered_experiment_at_fresh_path_is_never_none(tmp_path: Path) -> None:
    """Adversarial integration test (Codex, 2026-07-14), PatchTST producer:
    run the real ``BuildPatchTstArtifactManifestTask`` (via
    ``PatchTstTrainingPipeline``) under a registered experiment context at a
    FRESH artifact path, and prove it cannot obtain canonical/none
    classification -- see the GBDT twin
    (``tests/gbdt/test_workflow_class_provenance.py``) for the full
    rationale.
    """
    output_dir = tmp_path / "fresh_experiment_run"
    assert not output_dir.exists(), "path must be genuinely fresh for this test to be meaningful"

    registry_index_path = tmp_path / "manifest_registry_index.json"
    experiment_id = "exp-patchtst-adversarial-fresh-path-2026-07-14"
    manifest_digest = "sha256:patchtst-adversarial-fresh-path-digest"
    _write_registry_index(registry_index_path, experiment_id=experiment_id, manifest_digest=manifest_digest)

    write_experiment_classification(
        output_dir,
        experiment_id=experiment_id,
        manifest_path="irrelevant/for/this/test.json",
        manifest_digest=manifest_digest,
        config_digest="sha256:config-digest",
    )

    ctx = PatchTstTrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "architecture": "hf_patchtst",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="Cannot promote output of registered experiment"):
        PatchTstTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    assert ctx.artifact_manifest is not None
    assert ctx.artifact_manifest["provenance"]["kind"] == "experiment"
    assert ctx.artifact_manifest["provenance"] != {"kind": "none"}
    assert ctx.artifact_manifest["provenance"]["dir"] == str(output_dir)
    assert ctx.artifact_manifest["provenance"]["registry_index_path"] == str(registry_index_path)


def test_canonical_workflow_class_still_succeeds_with_none_provenance(tmp_path: Path) -> None:
    """Positive control: genuine canonical publication still succeeds and
    still gets kind="none" through the PatchTST producer.
    """
    ctx = PatchTstTrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"architecture": "hf_patchtst"},
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )

    result = PatchTstTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    assert result.ok is True
    assert ctx.artifact_manifest is not None
    assert ctx.artifact_manifest["provenance"] == {"kind": "none"}
