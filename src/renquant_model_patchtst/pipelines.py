"""Pipeline contracts for PatchTST/PatchTXT training and validation."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from renquant_common import Job, Pipeline, Task


@dataclass
class PatchTstTrainingContext:
    dataset_manifest: dict[str, Any]
    model_config: dict[str, Any]
    output_dir: Path
    sequence_frame: Any | None = None
    checkpoint_artifact: dict[str, Any] | None = None
    calibration_artifact: dict[str, Any] | None = None
    sanity_report: dict[str, Any] = field(default_factory=dict)


SequenceLoader = Callable[[dict[str, Any]], Any]
SequenceTrainer = Callable[[Any, dict[str, Any], Path], tuple[dict[str, Any], dict[str, Any]]]
SanityValidator = Callable[[dict[str, Any], Any, dict[str, Any]], dict[str, Any]]


class ValidateSequenceManifestTask(Task):
    """Require the split and label contract before training starts."""

    def run(self, ctx: PatchTstTrainingContext) -> bool | None:
        required = (
            "dataset_id",
            "fingerprint",
            "schema_version",
            "label_col",
            "lookahead_days",
            "split_policy",
        )
        missing = [key for key in required if not ctx.dataset_manifest.get(key)]
        if missing:
            raise ValueError(f"dataset_manifest missing required keys: {missing}")
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
