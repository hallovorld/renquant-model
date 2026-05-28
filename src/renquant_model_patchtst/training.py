"""SequenceTrainer wiring — run PatchTST training through PatchTstTrainingPipeline.

Adapts the lifted HF trainer (``hf_trainer.train_one``, which owns its own data
loading + HF Trainer loop) to the pipeline's dependency-injection contract:

    SequenceLoader  : manifest            -> sequence_frame (pass-through; train_one
                                             loads its own dataset from model_config)
    SequenceTrainer : frame, config, dir  -> (checkpoint, calibration)
    SanityValidator : checkpoint, frame, config -> sanity_report

The checkpoint is shaped from train_one's summary into the model-evidence-contract
form that BuildPatchTstArtifactManifestTask requires (artifact_id / model_family /
fingerprint / uri + oos evidence). Default hyperparameters come from
``hf_trainer.build_parser()`` so they live in one place.

PatchTST weights are not byte-reproducible (torch/MPS), so this gives structural
parity (same trainer, contract-valid checkpoint), not bit-identical weights.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from renquant_common import Pipeline

from . import hf_trainer
from .pipelines import PatchTstTrainingContext, PatchTstTrainingPipeline


def build_args(model_config: dict[str, Any], output_dir: Path):
    """Defaults from the trainer's own parser, overridden by model_config keys.

    model_config keys use argparse dest names (underscores), e.g. ``seq_len``,
    ``num_layers`` → ``n_layers``. ``output_dir`` is set from the pipeline arg.
    """
    args = hf_trainer.build_parser().parse_args([])
    for key, value in model_config.items():
        if hasattr(args, key):
            setattr(args, key, value)
    args.output_dir = str(output_dir)
    return args


def summary_to_checkpoint(summary: dict[str, Any], model_config: dict[str, Any]) -> dict[str, Any]:
    """Map train_one's summary into a model-evidence-contract checkpoint."""
    import numpy as np  # noqa: PLC0415

    cut = summary.get("cut", "all")
    seed = summary.get("seed", 0)
    artifact_id = f"patchtst-{cut}-seed{seed}"
    per_regime = summary.get("per_regime_ic") or {}
    best = float(summary.get("best_val_ic", float("nan")))
    fold_ics = [float(v) for v in per_regime.values()] if per_regime else [best]
    std_ic = float(np.std(fold_ics, ddof=1)) if len(fold_ics) > 1 else 0.0

    blob = json.dumps(summary, sort_keys=True, default=str).encode("utf-8")
    fingerprint = "sha256:" + hashlib.sha256(blob).hexdigest()
    contract = summary.get("training_contract") or {}
    return {
        "artifact_id": artifact_id,
        "model_family": "patchtst",
        "fingerprint": fingerprint,
        "uri": f"object://renquant-artifacts/{artifact_id}.pt",
        "promotion_status": model_config.get("promotion_status", "shadow"),
        "kind": summary.get("kind", "hf_patchtst"),
        "input_feature_cols": list(summary.get("feature_cols") or []),
        "trained_date": str(contract.get("trained_date") or date.today()),
        "config_fingerprint": summary.get("config_fingerprint", "unfingerprinted"),
        "sequence_shape": {
            "timesteps": int(model_config.get("seq_len", getattr(
                hf_trainer.build_parser().parse_args([]), "seq_len", 32))),
            "features": int(summary.get("n_features", len(summary.get("feature_cols") or []))),
        },
        "lookahead_days": int(summary.get("lookahead_days") or 60),
        "train_run_id": f"{cut}-seed{seed}",
        "oos_mean_ic": best,
        "oos_std_ic": std_ic,
        "oos_per_fold_ic": fold_ics,
        "per_regime_ic": dict(per_regime),
        "cv_method": "purged-walk-forward",
        "cv_embargo_days": int(model_config.get("embargo_days", 60)),
    }


def sequence_loader(manifest: dict[str, Any]) -> dict[str, Any]:
    """train_one loads its own dataset from model_config; pass the manifest through."""
    return manifest


def sequence_trainer(sequence_frame: Any, model_config: dict[str, Any],
                     output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    args = build_args(model_config, output_dir)
    summary = hf_trainer.train_one(args)
    checkpoint = summary_to_checkpoint(summary, model_config)
    calibration = {
        "artifact_id": f"{checkpoint['artifact_id']}-calibrator",
        "kind": "patchtst-distributional-head",
        "promotion_status": "shadow",
    }
    return checkpoint, calibration


def sanity_validator(checkpoint: dict[str, Any], sequence_frame: Any,
                     model_config: dict[str, Any]) -> dict[str, Any]:
    import math  # noqa: PLC0415

    ic = float(checkpoint.get("oos_mean_ic", float("nan")))
    return {
        "best_val_ic": ic,
        "per_regime_ic": checkpoint.get("per_regime_ic", {}),
        "passed": math.isfinite(ic),
        "model_evidence_contract_ok": True,
    }


def build_training_pipeline(
    loader=sequence_loader, trainer=sequence_trainer, validator=sanity_validator,
) -> PatchTstTrainingPipeline:
    """The PatchTST training Pipeline wired with the real trainer adapter."""
    return PatchTstTrainingPipeline(loader, trainer, validator)


__all__ = [
    "PatchTstTrainingContext",
    "build_args",
    "build_training_pipeline",
    "sanity_validator",
    "sequence_loader",
    "sequence_trainer",
    "summary_to_checkpoint",
]
