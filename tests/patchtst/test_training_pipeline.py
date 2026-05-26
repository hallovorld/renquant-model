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
        return {"kind": "hf_patchtst", "checkpoint": "model.pt"}, {"kind": "patchtst_calibrator"}

    def validator(checkpoint: dict, frame, config: dict):
        calls.append("sanity")
        assert checkpoint["kind"] == "hf_patchtst"
        return {"real_ic": 0.03, "placebo_ic": 0.001, "passed": True}

    ctx = PatchTstTrainingContext(
        dataset_manifest={
            "dataset_id": "transformer_v4_fixture",
            "fingerprint": "sha256:test",
            "schema_version": "fixture-v1",
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
    assert ctx.checkpoint_artifact["kind"] == "hf_patchtst"
    assert ctx.sanity_report["passed"] is True


def test_patchtst_training_pipeline_requires_split_and_label_contract(tmp_path: Path) -> None:
    ctx = PatchTstTrainingContext(
        dataset_manifest={"dataset_id": "bad"},
        model_config={},
        output_dir=tmp_path / "out",
    )

    with pytest.raises(ValueError, match="dataset_manifest missing"):
        PatchTstTrainingPipeline(lambda _: object(), lambda *_: ({}, {}), lambda *_: {}).run(ctx)
