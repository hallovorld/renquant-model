"""Structured Task/Job for the byte-identical production panel-LTR training.

This expresses the model-side of the production trainer (CV → booster → artifact) as
fine-grained ``renquant_common`` Tasks orchestrated by a Job, rather than a bare
function. The data-side and contract-side Tasks (panel load, normalization,
fingerprint, smoke, write) live in the umbrella driver and import this context +
``ModelTrainingJob`` to assemble the full GBDT training Pipeline.

Boundary: this module imports only engine code (panel_trainer) + the
``renquant_common`` Task/Job primitives — no ``kernel.*``, no umbrella. The
data-side inputs (normalization callable, fitted stats, sentiment/cutoff artifact
fields) are populated on the shared :class:`GbdtTrainingContext` by the umbrella
Tasks before the model Tasks run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from renquant_common import Job, Task

from .panel_trainer import (
    NormalizationBuilder,
    build_model_artifact,
    evaluate_walk_forward_cv,
    train_xgb,
)


@dataclass
class GbdtTrainingContext:
    """Shared context threaded through the GBDT training pipeline.

    Data-side fields are set by the umbrella Tasks (LoadPanel / SentimentGate /
    BuildNormalization); model-side fields (cv_result, booster, artifact) are set
    by the engine Tasks below; contract-side Tasks then stamp + write ``artifact``.
    """

    # ── inputs / config ──
    label: str = "fwd_60d_excess"
    params: dict[str, Any] = field(default_factory=dict)
    num_boost_round: int = 100
    cv_n_splits: int = 3
    cv_embargo_days: int = 60
    skip_cv: bool = False
    lookahead_days: int = 60
    train_run_id: Optional[str] = None
    training_notes: str = ""

    # ── data-side config (consumed by panel_data Tasks; leave None when injecting
    #    a pre-loaded frame instead of loading from disk) ──
    data_dir: Optional[str] = None
    cutoff_date: Any = None            # pd.Timestamp | None
    watchlist: Optional[list[str]] = None
    cutoff_embargo_days: Optional[int] = None
    side_label: Optional[str] = None
    output_path: Optional[str] = None
    # Feature columns to drop from the panel before training (e.g. low/negative-IC
    # families found to dilute the signal). Empty/None = keep all panel features.
    exclude_features: Optional[list[str]] = None
    # Production config fingerprint, injected by the orchestrator (computed from the
    # strategy config so the runtime scorer's live-fingerprint check matches). When
    # None the contract Task falls back to a self-describing content hash.
    config_fingerprint: Optional[str] = None
    config_fingerprint_fields: Optional[dict[str, Any]] = None

    # ── data-side (set by data-prep Tasks) ──
    train: Optional[pd.DataFrame] = None
    feat_cols: list[str] = field(default_factory=list)
    normalization_builder: Optional[NormalizationBuilder] = None
    mu: Optional[np.ndarray] = None
    sd: Optional[np.ndarray] = None
    norm_kind: Optional[list[str]] = None
    raw_clip_low: Optional[list[Optional[float]]] = None
    raw_clip_high: Optional[list[Optional[float]]] = None
    # cutoff/side_label/sentiment fields layered onto the artifact, IN ORDER, to
    # preserve byte-identity with the production build_artifact key ordering.
    extra_artifact_fields: dict[str, Any] = field(default_factory=dict)

    # ── model-side outputs (set by engine Tasks) ──
    cv_result: Optional[dict[str, Any]] = None
    booster: Any = None
    train_ic: Optional[float] = None
    artifact: Optional[dict[str, Any]] = None


class WalkForwardCVTask(Task):
    """Compute the OOS walk-forward CV contract (skipped when ctx.skip_cv)."""

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.skip_cv:
            return True
        if ctx.train is None or not ctx.feat_cols:
            raise ValueError("WalkForwardCVTask: train panel + feat_cols required")
        if ctx.normalization_builder is None:
            raise ValueError("WalkForwardCVTask: normalization_builder required for per-fold renorm")
        ctx.cv_result = evaluate_walk_forward_cv(
            ctx.train, ctx.feat_cols,
            normalization_builder=ctx.normalization_builder,
            label=ctx.label, params=ctx.params, num_boost_round=ctx.num_boost_round,
            n_splits=ctx.cv_n_splits, embargo_days=ctx.cv_embargo_days,
        )
        return True


class TrainBoosterTask(Task):
    """Fit the final rank:pairwise booster on the full (normalized) train panel."""

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.train is None or not ctx.feat_cols:
            raise ValueError("TrainBoosterTask: train panel + feat_cols required")
        if ctx.mu is None or ctx.sd is None or ctx.norm_kind is None:
            raise ValueError("TrainBoosterTask: normalization (mu/sd/norm_kind) required")
        ctx.booster, ctx.train_ic = train_xgb(
            ctx.train, ctx.feat_cols, label=ctx.label,
            params=ctx.params, num_boost_round=ctx.num_boost_round,
            feature_means=ctx.mu, feature_stds=ctx.sd, feature_norm_kind=ctx.norm_kind,
        )
        return True


class BuildArtifactTask(Task):
    """Assemble the version:3 model artifact, then layer cutoff/side/sentiment fields."""

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.booster is None:
            raise ValueError("BuildArtifactTask: booster required (run TrainBoosterTask first)")
        artifact = build_model_artifact(
            ctx.booster, ctx.feat_cols, ctx.mu, ctx.sd, ctx.train,
            params=ctx.params, num_boost_round=ctx.num_boost_round,
            feature_norm_kind=ctx.norm_kind,
            feature_raw_clip_low=ctx.raw_clip_low, feature_raw_clip_high=ctx.raw_clip_high,
            label_used=ctx.label, lookahead_days=ctx.lookahead_days,
            train_ic=ctx.train_ic, cv_result=ctx.cv_result,
            train_run_id=ctx.train_run_id, training_notes=ctx.training_notes,
        )
        # Insertion order matters for byte-identity: base → cutoff → side_label → sentiment.
        artifact.update(ctx.extra_artifact_fields)
        ctx.artifact = artifact
        return True


class ModelTrainingJob(Job):
    """Orchestrate the engine model-side: CV → booster → artifact."""

    @property
    def tasks(self) -> list[Task]:
        return [WalkForwardCVTask(), TrainBoosterTask(), BuildArtifactTask()]
