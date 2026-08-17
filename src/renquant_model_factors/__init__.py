"""Simple-sort factor emitters for the G-I MoE roster (orch#984 §4–5, step 1).

THREE momentum-grade candidates — ``high52w`` (52-week-high proximity,
George–Hwang), ``lowbeta`` (betting-against-beta, Frazzini–Pedersen) and
``quality_gp`` (gross profitability, Novy-Marx) — as clones of the momentum
emitter PATTERN, not of its code: one shared machine
(``machine.build_factor_artifact``) assembles a momentum-shaped artifact
(kind / params / config_fingerprint / measured effective cutoff / RAW
scores / read digests / content_sha256), and each factor module contributes
only its FROZEN params (prereg content, frozen before any scoring run) and
its per-ticker formula.

The chained ledger and the content-sha helpers are IMPORTED from
``renquant_model_momentum`` and re-exported here for callers — there is
deliberately NO ledger code in this package. Each factor appends to its
OWN ledger file (single-kind lane per file, like momentum/momentum_fast):
the chain's (cutoff_date, params_version) uniqueness key assumes exactly
that.

Scores are RAW: the serving-side blend machinery z-scores every component
cross-sectionally at serve time (``BlendPanelScorer.score``, ddof=0) — the
same consumption path as the momentum ledger today.

Nothing here schedules anything, reads production data, or screens IC —
scheduling and deploys are operator-gated later steps, and the cheap IC
screen is impl step 2 with its own frozen spec (orch#984 §5).
"""
from __future__ import annotations

# The ledger IS momentum's — imported and re-exported, never reimplemented
# (the chain idiom has exactly one implementation; momentum ledger.py).
from renquant_model_momentum.ledger import (LedgerIntegrityError,
                                            append_to_artifact_ledger,
                                            load_and_verify_ledger)
from renquant_model_momentum.train import (content_sha256_of,
                                           verify_artifact_content_sha)

from renquant_model_factors.high52w import (
    build_high52w_artifact, params_v0 as params_high52w_v0)
from renquant_model_factors.lowbeta import (
    build_lowbeta_artifact, params_v0 as params_lowbeta_v0)
from renquant_model_factors.machine import (ARTIFACT_SCHEMA_VERSION,
                                            FactorDef, FactorReaders,
                                            TickerScore, artifact_kind_for,
                                            build_factor_artifact,
                                            factor_config_fingerprint)
from renquant_model_factors.quality_gp import (
    build_quality_gp_artifact, params_v0 as params_quality_gp_v0)

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "FactorDef",
    "FactorReaders",
    "LedgerIntegrityError",
    "TickerScore",
    "append_to_artifact_ledger",
    "artifact_kind_for",
    "build_factor_artifact",
    "build_high52w_artifact",
    "build_lowbeta_artifact",
    "build_quality_gp_artifact",
    "content_sha256_of",
    "factor_config_fingerprint",
    "load_and_verify_ledger",
    "params_high52w_v0",
    "params_lowbeta_v0",
    "params_quality_gp_v0",
    "verify_artifact_content_sha",
]
