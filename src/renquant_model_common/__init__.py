"""Shared scaffolding across RenQuant model families.

Cross-family utilities (feature assembly, training-ledger writer, global
calibrator, acceptance helpers) land here as they are ported from the
umbrella per RFC §"Backfill Plan" P3 / task "Lift training_panel".

Empty for now beyond this marker — the GBDT and PatchTST families
currently import shared CV primitives directly from
``renquant_common.purged_cv``.
"""
from __future__ import annotations

__all__: list[str] = []
