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

Families also import shared CV primitives from ``renquant_common.purged_cv``.
"""
from __future__ import annotations

__all__: list[str] = []
