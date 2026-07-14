"""Shared scaffolding across RenQuant model families.

Cross-family utilities (feature assembly, training-ledger writer, global
calibrator, acceptance helpers) land here as they are ported from the
umbrella per RFC §"Backfill Plan" P3 / task "Lift training_panel".

Lifted cross-family model utilities (copy-not-move, stdlib + numpy/pandas/
scipy only):

* ``calibrator_quality``  — calibrator health metrics
* ``global_calibrator``   — pooled panel score calibration
* ``triple_barrier``      — triple-barrier label construction
* ``acceptance_entry_ic`` — entry-IC acceptance metric
* ``challenger``          — challenger-window model ledger
* ``workflow_provenance`` — verified workflow-classification -> artifact
  manifest ``provenance`` record (F-7 round 4, depends on
  ``renquant_artifacts.experiment_registry``); the ONE shared
  ``build_verified_provenance`` implementation both
  ``renquant_model_gbdt.pipelines.BuildArtifactManifestTask`` and
  ``renquant_model_patchtst.pipelines.BuildPatchTstArtifactManifestTask`` call

Families also import shared CV primitives from ``renquant_common.purged_cv``.
"""
from __future__ import annotations

__all__: list[str] = []
