"""GBDT panel-LTR model-training package."""

from .feature_transform import transform_feature_frame
from .legacy_panel_trainer import (
    build_model_artifact,
    cross_sectional_ic,
    evaluate_walk_forward_cv,
    train_xgb,
)
from .pipelines import (
    BuildArtifactManifestTask,
    PanelGbdtTrainingPipeline,
    TrainingContext,
    ValidateManifestTask,
)
from .scorer import XGBoostPanelScorer
from .scorer import load as load_xgboost_panel_scorer
from .trainer import train_panel_ltr_artifact, validate_panel_ltr_artifact

__all__ = [
    "BuildArtifactManifestTask",
    "PanelGbdtTrainingPipeline",
    "TrainingContext",
    "ValidateManifestTask",
    "XGBoostPanelScorer",
    "build_model_artifact",
    "cross_sectional_ic",
    "evaluate_walk_forward_cv",
    "load_xgboost_panel_scorer",
    "train_panel_ltr_artifact",
    "train_xgb",
    "transform_feature_frame",
    "validate_panel_ltr_artifact",
]
