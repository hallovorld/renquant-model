"""Momentum TRAIN pipeline package (GOAL-7 pipeline slice 2).

Implements §1 (TRAIN) of the momentum pipeline architecture
(doc/design/2026-08-02-momentum-pipeline-architecture.md): ONE
artifact-producing entry over the existing frozen mechanism pieces
(`renquant_model_common.momentum_features`, `renquant_model_common.total_return`
— imported, never copied), plus the append-only digest-chained artifact ledger.

Nothing here schedules anything (that is slice 5, operator-gated) and nothing
here evaluates anything (that is slice 3, the recurring TEST harness).
"""
from __future__ import annotations

from renquant_model_momentum.ledger import (LedgerIntegrityError,
                                            append_to_artifact_ledger,
                                            load_and_verify_ledger)
from renquant_model_momentum.train import (ARTIFACT_KIND, MomentumReaders,
                                           content_sha256_of, params_v0,
                                           train_momentum_artifact,
                                           verify_artifact_content_sha)

__all__ = [
    "ARTIFACT_KIND",
    "MomentumReaders",
    "LedgerIntegrityError",
    "append_to_artifact_ledger",
    "content_sha256_of",
    "load_and_verify_ledger",
    "params_v0",
    "train_momentum_artifact",
    "verify_artifact_content_sha",
]
