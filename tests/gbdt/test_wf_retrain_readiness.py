from __future__ import annotations

import json
from pathlib import Path

import pytest

from renquant_model_gbdt import (
    WORKFLOW_CLASS_CANONICAL,
    PanelGbdtTrainingPipeline,
    TrainingContext,
)
from renquant_model_gbdt.wf_retrain_readiness import (
    main as readiness_main,
    require_full_wf_retrain_readiness,
    validate_full_wf_retrain_readiness,
)
from renquant_model_gbdt.panel_data import TRACK_B_FEATURES


def _config() -> dict:
    return {
        "mode": "full_wf_retrain",
        "full_wf_retrain": True,
        "required_features": list(TRACK_B_FEATURES),
        "required_artifact_metadata": {
            "one_of": ["sanity_triad", "verdict + verdict_metadata", "verdict + verdict_inputs"],
        },
        "strategy": "renquant_104",
    }


def _artifact(*, metadata: dict | None = None) -> dict:
    return {
        "artifact_id": "track-b-full-wf",
        "model_family": "gbdt-panel-ltr",
        "fingerprint": "sha256:model",
        "uri": "object://renquant-artifacts/track-b-full-wf.json",
        "promotion_status": "candidate",
        "kind": "panel_ltr_xgboost",
        "trained_date": "2026-06-05",
        "config_fingerprint": "sha256:config",
        "feature_cols": ["a0", *TRACK_B_FEATURES],
        "feature_means": [0.0] * (1 + len(TRACK_B_FEATURES)),
        "feature_stds": [1.0] * (1 + len(TRACK_B_FEATURES)),
        "feature_norm_kind": ["global_z"] * (1 + len(TRACK_B_FEATURES)),
        "feature_addendum_v1": {
            "track_b_features_active": list(TRACK_B_FEATURES),
            "source": "renquant-base-data:track_b_features",
        },
        "panel_shape": {"rows": 1000, "cols": 1 + len(TRACK_B_FEATURES)},
        "lookahead_days": 60,
        "train_run_id": "track-b-full-wf",
        "oos_mean_ic": 0.031,
        "oos_std_ic": 0.012,
        "oos_per_fold_ic": [0.02, 0.04, 0.033],
        "cv_method": "purged_walk_forward",
        "cv_embargo_days": 60,
        "metadata": {
            "sanity_triad": {
                "shuffle_label": {"passed": True},
                "time_shift": {"passed": True},
                "placebo_feature": {"passed": True},
            }
        } if metadata is None else metadata,
    }


def _dataset_manifest() -> dict:
    return {
        "dataset_id": "alpha158_track_b_fixture",
        "fingerprint": "sha256:data",
        "schema_version": "fixture-v1",
        "uri": "object://renquant-data/alpha158_track_b_fixture.parquet",
        "asset_class": "equity",
    }


def test_readiness_config_requires_all_four_track_b_features() -> None:
    config = _config()
    config["required_features"] = ["mom_carry_12_1", "beta_dm", "rvar_total"]

    report = validate_full_wf_retrain_readiness(config)

    assert report["ok"] is False
    failed = {check["name"]: check for check in report["checks"] if not check["ok"]}
    assert failed["config_requires_track_b_features"]["detail"]["missing"] == ["idio_vol_market"]
    with pytest.raises(ValueError, match="idio_vol_market"):
        require_full_wf_retrain_readiness(config)


def test_readiness_artifact_requires_track_b_addendum_and_triad_or_verdict_metadata() -> None:
    artifact = _artifact(metadata={})
    del artifact["feature_addendum_v1"]

    report = validate_full_wf_retrain_readiness(_config(), artifact)

    assert report["ok"] is False
    failed = {check["name"]: check for check in report["checks"] if not check["ok"]}
    assert "artifact_stamps_track_b_addendum" in failed
    assert "artifact_has_triad_or_verdict_metadata" in failed


def test_readiness_accepts_verdict_metadata_instead_of_sanity_triad() -> None:
    artifact = _artifact(metadata={
        "verdict": "promote_to_confirm",
        "verdict_inputs": {"dsr": 0.82, "pbo": 0.08},
    })

    report = validate_full_wf_retrain_readiness(_config(), artifact)

    assert report["ok"] is True
    evidence = [c for c in report["checks"] if c["name"] == "artifact_has_triad_or_verdict_metadata"][0]
    assert evidence["detail"]["kind"] == "verdict"


def test_full_wf_pipeline_writes_readiness_report_to_manifest_metrics(
    tmp_path: Path, canonical_run_intent_fixture,
) -> None:
    calls: list[str] = []

    def loader(manifest: dict):
        calls.append("load")
        return {"manifest": manifest}

    def trainer(dataset, config: dict, output_dir: Path):
        calls.append("train")
        return _artifact(), {"kind": "global_calibrator"}

    def validator(artifact: dict, dataset, config: dict):
        calls.append("validate")
        return {"oos_mean_ic": artifact["oos_mean_ic"]}

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            **_config(),
            # F-7 round 6 (renquant-model#55, step 2/4): canonical now
            # requires a real, independently-verifiable run_intent.json.
            "canonical_run_intent_path": str(canonical_run_intent_fixture.run_intent_path),
        },
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )
    result = PanelGbdtTrainingPipeline(loader, trainer, validator).run(ctx)

    assert result.ok is True
    assert calls == ["load", "train", "validate"]
    assert ctx.artifact_manifest is not None
    readiness = ctx.artifact_manifest["metrics"]["wf_retrain_readiness"]
    assert readiness["ok"] is True
    assert readiness["required_track_b_features"] == list(TRACK_B_FEATURES)
    assert ctx.artifact_manifest["feature_addendum_v1"]["track_b_features_active"] == list(TRACK_B_FEATURES)


def test_readiness_cli_outputs_json_report_without_training(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "readiness.json"
    artifact_path = tmp_path / "artifact.json"
    config_path.write_text(json.dumps(_config()))
    artifact_path.write_text(json.dumps(_artifact()))

    rc = readiness_main(["--config", str(config_path), "--artifact", str(artifact_path), "--json"])

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert [c["name"] for c in report["checks"]] == [
        "full_wf_retrain_config",
        "config_requires_track_b_features",
        "config_requires_triad_or_verdict_metadata",
        "artifact_contains_track_b_features",
        "artifact_stamps_track_b_addendum",
        "artifact_has_triad_or_verdict_metadata",
    ]
