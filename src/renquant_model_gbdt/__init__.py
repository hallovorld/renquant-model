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

__all__ = [
    "DEFAULT_LABEL",
    "DEFAULT_N_ROUNDS",
    "PANEL_LTR_PARAMS",
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
    "build_model_artifact",
    "build_normalization",
    "build_training_pipeline",
    "content_fingerprint",
    "cross_sectional_ic",
    "evaluate_walk_forward_cv",
    "infer_label_lookahead_days",
    "load_panel",
    "train_xgb",
    "transform_feature_frame",
]
