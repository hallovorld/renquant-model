"""PatchTST flows through PatchTstTrainingPipeline via the SequenceTrainer adapter.

Verifies (without a multi-minute torch run): the adapter shapes train_one's
summary into a model-evidence-contract checkpoint, and the full
PatchTstTrainingPipeline (manifest → load → train → sanity → build-manifest)
accepts it. A real MPS smoke is exercised separately by the orchestrator driver.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

from renquant_model_patchtst.pipelines import PatchTstTrainingContext  # noqa: E402
from renquant_model_patchtst.training import (  # noqa: E402
    build_training_pipeline, sanity_validator, summary_to_checkpoint,
)

_SUMMARY = {
    "kind": "hf_patchtst", "cut": "cut1_covid", "seed": 42,
    "best_val_ic": 0.07, "n_params": 68036, "n_features": 3,
    "feature_cols": ["a", "b", "c"], "label_col": "fwd_60d_excess",
    "lookahead_days": 60, "config_fingerprint": "sha256:cfg",
    "per_regime_ic": {"BULL_VOLATILE": 0.138, "CHOPPY": 0.101, "BEAR": 0.070},
    "training_contract": {"trained_date": "2026-05-28"},
}


def _manifest() -> dict:
    return {
        "dataset_id": "transformer_v4_fixture", "fingerprint": "sha256:data",
        "schema_version": "fixture-v1",
        "uri": "object://renquant-data/transformer_v4_fixture.parquet",
        "asset_class": "equity", "label_col": "fwd_60d_excess",
        "lookahead_days": 60, "split_policy": "purged-walk-forward",
    }


def test_summary_to_checkpoint_shape():
    ck = summary_to_checkpoint(_SUMMARY, {"seq_len": 32, "embargo_days": 60})
    assert ck["model_family"] == "patchtst"
    assert ck["artifact_id"] == "patchtst-cut1_covid-seed42"
    assert ck["fingerprint"].startswith("sha256:")
    assert ck["oos_mean_ic"] == 0.07
    assert ck["oos_per_fold_ic"] == [0.138, 0.101, 0.070]
    assert ck["lookahead_days"] == 60 and ck["cv_embargo_days"] == 60
    assert ck["input_feature_cols"] == ["a", "b", "c"]


def test_pipeline_runs_with_adapter_checkpoint(tmp_path: Path):
    ck = summary_to_checkpoint(_SUMMARY, {"seq_len": 32, "embargo_days": 60})

    def stub_trainer(frame, config, out_dir):
        # The lineage determination is attached HERE, by the stub trainer, and not
        # inside summary_to_checkpoint(): that adapter converts a real training
        # summary, so having it emit kind="none" would make production code
        # synthesise a determination it has no standing to make. A stub trainer
        # over a synthetic summary genuinely has no lineage, so "none" is accurate.
        return {**ck, "provenance": {"kind": "none"}}, {
            "kind": "patchtst-distributional-head",
            "promotion_status": "shadow",
        }

    pipeline = build_training_pipeline(loader=lambda m: m, trainer=stub_trainer,
                                       validator=sanity_validator)
    ctx = PatchTstTrainingContext(
        dataset_manifest=_manifest(), model_config={"architecture": "hf_patchtst"},
        output_dir=tmp_path / "out",
    )
    result = pipeline.run(ctx)

    assert result.ok and result.name == "patchtst-training"
    assert ctx.checkpoint_artifact["model_family"] == "patchtst"
    assert ctx.artifact_manifest is not None
    assert ctx.artifact_manifest["promotion_status"] == "shadow"
    assert ctx.sanity_report["passed"] is True
    assert ctx.sanity_report["model_evidence_contract_ok"] is True
