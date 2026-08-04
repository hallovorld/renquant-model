"""Momentum TRAIN + TEST pipeline package (GOAL-7 pipeline slices 2-3).

Implements §1 (TRAIN) and §2 (TEST) of the momentum pipeline architecture
(doc/design/2026-08-02-momentum-pipeline-architecture.md): ONE
artifact-producing entry over the existing frozen mechanism pieces
(`renquant_model_common.momentum_features`, `renquant_model_common.total_return`
— imported, never copied), the append-only digest-chained artifact ledger,
and the recurring evaluator (`evaluate_momentum_artifact`) over the sealed v2
gap-block machine with the mandatory causal maturity contract, plus its own
chained evaluation ledger (same chain helper, shared not duplicated).

Nothing here schedules anything (that is slice 5, operator-gated) and nothing
here serves anything (that is slice 4, the strategy-104 shadow config).
"""
from __future__ import annotations

from renquant_model_momentum.evaluate import (EVAL_KIND, EvalSeriesReaders,
                                              append_eval_ledger,
                                              eligible_last_date,
                                              evaluate_momentum_artifact)
from renquant_model_momentum.ledger import (LedgerIntegrityError,
                                            append_chained_row,
                                            append_to_artifact_ledger,
                                            load_and_verify_ledger)
from renquant_model_momentum.train import (ARTIFACT_KIND, MomentumReaders,
                                           content_sha256_of, params_v0, params_v1_fast,
                                           train_momentum_artifact,
                                           verify_artifact_content_sha)

__all__ = [
    "ARTIFACT_KIND",
    "EVAL_KIND",
    "EvalSeriesReaders",
    "MomentumReaders",
    "LedgerIntegrityError",
    "append_chained_row",
    "append_eval_ledger",
    "append_to_artifact_ledger",
    "content_sha256_of",
    "eligible_last_date",
    "evaluate_momentum_artifact",
    "load_and_verify_ledger",
    "params_v0",
    "params_v1_fast",
    "train_momentum_artifact",
    "verify_artifact_content_sha",
]
