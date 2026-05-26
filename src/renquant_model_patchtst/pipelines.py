"""Pipeline contracts for PatchTST/PatchTXT training and validation."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from renquant_common import Job, Pipeline, Task
from renquant_artifacts import validate_artifact_manifest, validate_model_evidence_contract
from renquant_base_data import validate_data_manifest


@dataclass
class PatchTstTrainingContext:
    dataset_manifest: dict[str, Any]
    model_config: dict[str, Any]
    output_dir: Path
    sequence_frame: Any | None = None
    checkpoint_artifact: dict[str, Any] | None = None
    calibration_artifact: dict[str, Any] | None = None
    artifact_manifest: dict[str, Any] | None = None
    sanity_report: dict[str, Any] = field(default_factory=dict)


SequenceLoader = Callable[[dict[str, Any]], Any]
SequenceTrainer = Callable[[Any, dict[str, Any], Path], tuple[dict[str, Any], dict[str, Any]]]
SanityValidator = Callable[[dict[str, Any], Any, dict[str, Any]], dict[str, Any]]


class ValidateSequenceManifestTask(Task):
    """Require the split and label contract before training starts."""

    def run(self, ctx: PatchTstTrainingContext) -> bool | None:
        required = (
            "label_col",
            "lookahead_days",
            "split_policy",
        )
        missing = [key for key in required if not ctx.dataset_manifest.get(key)]
        if missing:
            raise ValueError(f"dataset_manifest missing required keys: {missing}")
        validate_data_manifest(ctx.dataset_manifest)
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        return True


class LoadSequenceFrameTask(Task):
    def __init__(self, loader: SequenceLoader) -> None:
        self.loader = loader

    def run(self, ctx: PatchTstTrainingContext) -> bool | None:
        ctx.sequence_frame = self.loader(ctx.dataset_manifest)
        return True


class TrainPatchTstTask(Task):
    def __init__(self, trainer: SequenceTrainer) -> None:
        self.trainer = trainer

    def run(self, ctx: PatchTstTrainingContext) -> bool | None:
        if ctx.sequence_frame is None:
            raise ValueError("sequence_frame must be loaded before TrainPatchTstTask")
        checkpoint, calibration = self.trainer(ctx.sequence_frame, ctx.model_config, ctx.output_dir)
        ctx.checkpoint_artifact = checkpoint
        ctx.calibration_artifact = calibration
        return True


class RunSanityTriadTask(Task):
    def __init__(self, validator: SanityValidator) -> None:
        self.validator = validator

    def run(self, ctx: PatchTstTrainingContext) -> bool | None:
        if ctx.sequence_frame is None or ctx.checkpoint_artifact is None:
            raise ValueError("sequence_frame and checkpoint_artifact are required")
        ctx.sanity_report = self.validator(ctx.checkpoint_artifact, ctx.sequence_frame, ctx.model_config)
        return True


class BuildPatchTstArtifactManifestTask(Task):
    """Convert checkpoint output into a registry-valid artifact manifest."""

    def run(self, ctx: PatchTstTrainingContext) -> bool | None:
        if ctx.checkpoint_artifact is None:
            raise ValueError("checkpoint_artifact is required before artifact manifest build")
        required = ("artifact_id", "model_family", "fingerprint", "uri")
        missing = [key for key in required if not ctx.checkpoint_artifact.get(key)]
        if missing:
            raise ValueError(f"checkpoint_artifact missing required keys: {missing}")
        evidence_contract = validate_model_evidence_contract(
            ctx.checkpoint_artifact,
            strict=bool(ctx.model_config.get("strict_model_evidence_contract", True)),
            runtime_config=ctx.model_config,
        )
        if not evidence_contract.ok:
            raise ValueError(
                "checkpoint_artifact model evidence contract failed: "
                f"errors={evidence_contract.errors}; warnings={evidence_contract.warnings}"
            )
        ctx.sanity_report.setdefault("model_evidence_contract_ok", evidence_contract.ok)
        ctx.sanity_report.setdefault("model_evidence_contract_details", evidence_contract.details)
        manifest = {
            "artifact_id": ctx.checkpoint_artifact["artifact_id"],
            "model_family": ctx.checkpoint_artifact["model_family"],
            "strategy": ctx.model_config.get("strategy", "renquant_104"),
            "fingerprint": ctx.checkpoint_artifact["fingerprint"],
            "uri": ctx.checkpoint_artifact["uri"],
            "promotion_status": ctx.checkpoint_artifact.get("promotion_status", "shadow"),
            "metrics": dict(ctx.sanity_report),
            "data_fingerprint": ctx.dataset_manifest["fingerprint"],
            "config_fingerprint": ctx.model_config.get("config_fingerprint", "unfingerprinted"),
            "code_commit": ctx.model_config.get("code_commit", "uncommitted"),
        }
        validate_artifact_manifest(manifest)
        ctx.artifact_manifest = manifest
        return True


class PatchTstTrainingJob(Job):
    def __init__(
        self,
        loader: SequenceLoader,
        trainer: SequenceTrainer,
        validator: SanityValidator,
    ) -> None:
        self._tasks = [
            ValidateSequenceManifestTask(),
            LoadSequenceFrameTask(loader),
            TrainPatchTstTask(trainer),
            RunSanityTriadTask(validator),
            BuildPatchTstArtifactManifestTask(),
        ]

    @property
    def tasks(self) -> list[Task]:
        return self._tasks


class PatchTstTrainingPipeline(Pipeline):
    """Sequence-model training pipeline shell."""

    def __init__(
        self,
        loader: SequenceLoader,
        trainer: SequenceTrainer,
        validator: SanityValidator,
    ) -> None:
        super().__init__([PatchTstTrainingJob(loader, trainer, validator)], name="patchtst-training")
