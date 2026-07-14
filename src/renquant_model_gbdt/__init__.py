"""GBDT panel-LTR training engine — one production-faithful implementation.

Trainer math lives in :mod:`panel_trainer` (booster + walk-forward CV + version:3
artifact); it is wrapped as fine-grained Tasks → :class:`ModelTrainingJob` in
:mod:`pipeline`. The umbrella driver supplies the data-side + contract-side Tasks
and assembles the end-to-end training Pipeline.
"""

from .feature_transform import transform_feature_frame
from .panel_trainer import (
    DEFAULT_LABEL,
    DEFAULT_N_ROUNDS,
    PANEL_LTR_PARAMS,
    NormalizationBuilder,
    build_model_artifact,
    cross_sectional_ic,
    evaluate_walk_forward_cv,
    train_xgb,
)
from .pipeline import (
    BuildArtifactTask,
    GbdtTrainingContext,
    ModelTrainingJob,
    TrainBoosterTask,
    WalkForwardCVTask,
)
# Self-contained data-side pipeline (reads data_dir; no umbrella / kernel.*).
from .panel_data import (
    ArtifactContractJob,
    BuildNormalizationTask,
    DataPrepJob,
    LoadPanelTask,
    build_normalization,
    build_training_pipeline,
    content_fingerprint,
    infer_label_lookahead_days,
    load_panel,
)
# Vol/trend feature-set v2 recipe (C1 returns-based vol + C2 trend interactions;
# candidate implementation for the preregistered baseline-vs-vol_trend_v2
# experiment specified in orchestrator #476 §7 — NOT a validated replacement).
# Spec + reference implementation — columns enter production only via a
# base-data panel rebuild + a gated retrain that satisfies the experiment-
# contract promotion gate in wf_retrain_readiness (declared experiment_id +
# a matching, run-bundle-referenced artifact stamp).
from .vol_trend_features import (
    RET_VOL_FEATURES,
    TREND_INTERACTION_FEATURES,
    VOL_TREND_FEATURE_SET_VERSION,
    VOL_TREND_FEATURES,
    augment_panel_with_vol_trend_features,
    compute_vol_trend_features,
)
# Generic training-pipeline shell (Task/Job/Pipeline with trainer DI). Consumed by
# renquant-orchestrator's DailyRunPipeline, which injects its own loader/trainer/
# validator. The default trainer it is paired with is the canonical engine above.
from .pipelines import (
    BuildArtifactManifestTask,
    DatasetLoader,
    PanelGbdtTrainingPipeline,
    Trainer,
    TrainingContext,
    Validator,
)
# Re-exported for caller convenience (F-7 round 4): every TrainingContext
# construction must declare one of these explicitly -- see
# renquant_model_common.workflow_provenance for the full contract.
from renquant_model_common.workflow_provenance import (
    WORKFLOW_CLASS_CANONICAL,
    WORKFLOW_CLASS_EXPERIMENT,
)

__all__ = [
    "DEFAULT_LABEL",
    "DEFAULT_N_ROUNDS",
    "PANEL_LTR_PARAMS",
    "RET_VOL_FEATURES",
    "TREND_INTERACTION_FEATURES",
    "VOL_TREND_FEATURES",
    "VOL_TREND_FEATURE_SET_VERSION",
    "WORKFLOW_CLASS_CANONICAL",
    "WORKFLOW_CLASS_EXPERIMENT",
    "ArtifactContractJob",
    "BuildArtifactManifestTask",
    "BuildArtifactTask",
    "BuildNormalizationTask",
    "DataPrepJob",
    "DatasetLoader",
    "GbdtTrainingContext",
    "LoadPanelTask",
    "ModelTrainingJob",
    "NormalizationBuilder",
    "PanelGbdtTrainingPipeline",
    "TrainBoosterTask",
    "Trainer",
    "TrainingContext",
    "Validator",
    "WalkForwardCVTask",
    "augment_panel_with_vol_trend_features",
    "build_model_artifact",
    "build_normalization",
    "build_training_pipeline",
    "compute_vol_trend_features",
    "content_fingerprint",
    "cross_sectional_ic",
    "evaluate_walk_forward_cv",
    "infer_label_lookahead_days",
    "load_panel",
    "train_xgb",
    "transform_feature_frame",
]
