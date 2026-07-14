"""PatchTST/PatchTXT sequence-model package."""

from .pipelines import (
    BuildPatchTstArtifactManifestTask,
    PatchTstTrainingContext,
    PatchTstTrainingPipeline,
    ValidateSequenceManifestTask,
)
# Re-exported for caller convenience (F-7 round 4): every
# PatchTstTrainingContext construction must declare one of these explicitly
# -- see renquant_model_common.workflow_provenance for the full contract.
from renquant_model_common.workflow_provenance import (
    WORKFLOW_CLASS_CANONICAL,
    WORKFLOW_CLASS_EXPERIMENT,
)

__all__ = [
    "WORKFLOW_CLASS_CANONICAL",
    "WORKFLOW_CLASS_EXPERIMENT",
    "BuildPatchTstArtifactManifestTask",
    "PatchTstTrainingContext",
    "PatchTstTrainingPipeline",
    "ValidateSequenceManifestTask",
]
