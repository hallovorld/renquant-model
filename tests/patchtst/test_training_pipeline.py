from __future__ import annotations

from pathlib import Path

import pytest

from renquant_model_patchtst import PatchTstTrainingContext, PatchTstTrainingPipeline


def test_patchtst_training_pipeline_runs_sanity_stage(tmp_path: Path) -> None:
    calls: list[str] = []

    def loader(manifest: dict):
        calls.append("load")
        return {"seq_rows": 10, "label_col": manifest["label_col"]}

    def trainer(frame, config: dict, output_dir: Path):
        calls.append("train")
        assert frame["label_col"] == "fwd_60d_excess"
        assert config["architecture"] == "hf_patchtst"
        assert output_dir.exists()
        return {
            "artifact_id": "patchtst-fixture",
            "model_family": "patchtst",
            "fingerprint": "sha256:patchtst",
            "uri": "object://renquant-artifacts/patchtst-fixture.pt",
            "promotion_status": "shadow",
            "input_feature_cols": ["alpha_1", "alpha_2"],
            "trained_date": "2026-05-25",
            "config_fingerprint": "sha256:config",
            "sequence_shape": {"rows": 1000, "timesteps": 64, "features": 2},
            "lookahead_days": 60,
            "train_run_id": "patchtst-run-1",
            "oos_mean_ic": 0.03,
            "oos_std_ic": 0.01,
            "oos_per_fold_ic": [0.02, 0.04],
            "cv_method": "purged-walk-forward",
            "cv_embargo_days": 60,
        }, {"kind": "patchtst_calibrator"}

    def validator(checkpoint: dict, frame, config: dict):
        calls.append("sanity")
        assert checkpoint["model_family"] == "patchtst"
        return {"real_ic": 0.03, "placebo_ic": 0.001, "passed": True}

    ctx = PatchTstTrainingContext(
        dataset_manifest={
            "dataset_id": "transformer_v4_fixture",
            "fingerprint": "sha256:test",
            "schema_version": "fixture-v1",
            "uri": "object://renquant-data/transformer_v4_fixture.parquet",
            "asset_class": "equity",
            "label_col": "fwd_60d_excess",
            "lookahead_days": 60,
            "split_policy": "purged-walk-forward",
        },
        model_config={"architecture": "hf_patchtst"},
        output_dir=tmp_path / "out",
    )
    result = PatchTstTrainingPipeline(loader, trainer, validator).run(ctx)

    assert result.ok is True
    assert result.name == "patchtst-training"
    assert calls == ["load", "train", "sanity"]
    assert ctx.checkpoint_artifact["model_family"] == "patchtst"
    assert ctx.artifact_manifest is not None
    assert ctx.artifact_manifest["promotion_status"] == "shadow"
    assert ctx.sanity_report["passed"] is True
    assert ctx.sanity_report["model_evidence_contract_ok"] is True


def test_patchtst_training_pipeline_requires_split_and_label_contract(tmp_path: Path) -> None:
    ctx = PatchTstTrainingContext(
        dataset_manifest={"dataset_id": "bad"},
        model_config={},
        output_dir=tmp_path / "out",
    )

    with pytest.raises(ValueError, match="dataset_manifest missing"):
        PatchTstTrainingPipeline(lambda _: object(), lambda *_: ({}, {}), lambda *_: {}).run(ctx)


def test_patchtst_training_pipeline_requires_model_evidence_contract(tmp_path: Path) -> None:
    def loader(manifest: dict):
        return {"seq_rows": 10, "label_col": manifest["label_col"]}

    def trainer(frame, config: dict, output_dir: Path):
        return {
            "artifact_id": "patchtst-bad",
            "model_family": "patchtst",
            "fingerprint": "sha256:patchtst",
            "uri": "object://renquant-artifacts/patchtst-bad.pt",
            "promotion_status": "shadow",
        }, {}

    def validator(checkpoint: dict, frame, config: dict):
        return {"real_ic": 0.03, "placebo_ic": 0.001, "passed": True}

    ctx = PatchTstTrainingContext(
        dataset_manifest={
            "dataset_id": "transformer_v4_fixture",
            "fingerprint": "sha256:test",
            "schema_version": "fixture-v1",
            "uri": "object://renquant-data/transformer_v4_fixture.parquet",
            "asset_class": "equity",
            "label_col": "fwd_60d_excess",
            "lookahead_days": 60,
            "split_policy": "purged-walk-forward",
        },
        model_config={"architecture": "hf_patchtst"},
        output_dir=tmp_path / "out",
    )

    with pytest.raises(ValueError, match="model evidence contract failed"):
        PatchTstTrainingPipeline(loader, trainer, validator).run(ctx)
