"""The quality_gp v0 params constants — FROZEN prereg content (orch#984 §5/§5b).

Frozen in the build PR itself, BEFORE any scoring run (see the high52w
module's freeze rationale — identical).

FIELD AVAILABILITY, ENUMERATED FIRST (the impl-step-1 spec's precondition —
no silent proxy substitution). The target formula is Novy-Marx gross
profitability = gross_profit / total_assets. That EXACT ratio already
exists on the data surface as the column ``gross_profitability``, computed
UPSTREAM by ``renquant_base_data.sec_fundamentals.compute_derived_features``
as ``_safe_ratio(gp, assets)`` where:

  * gp     = the SEC ``GrossProfit`` concept, falling back to the accounting
             identity Revenue − CostOfRevenue (both legs required — no
             partial math) ONLY when the issuer never tags a GrossProfit
             subtotal; the fallback is the identity, not a proxy;
  * assets = the SEC ``Assets`` concept (total assets).

The same column name is served by ``renquant_base_data.loaders.fundamentals``
(FACTOR_COLS) and carried through the alpha158 fund panel (FUND_COLS). This
emitter therefore consumes the UPSTREAM ratio verbatim; it does not
recompute it and it does not substitute any proxy. SOURCE_COLUMN below is
part of the frozen recipe — a different column is a new params version.

The score: the most recent finite ``gross_profitability`` value at or
before the cutoff, REFUSED (NaN, fail-closed) when the snapshot is older
than MAX_AGE_DAYS calendar days. RAW level score — cross-sectional z
happens in the blend machinery at serve time. Near-zero turnover is the
roster's expectation for this factor (design orch#984 §4); the staleness
ceiling is what keeps a delisted or filing-dark name from serving a fossil
value forever.

MAX_AGE_DAYS = 400 is a design choice frozen here: annual filing cadence
(365d) plus filing-lag headroom — a value older than that no longer
reflects even the prior fiscal year on time.
"""
from __future__ import annotations

#: The upstream-computed Novy-Marx ratio column (see module docstring).
SOURCE_COLUMN = "gross_profitability"

#: At least this many finite snapshots at/before the cutoff (fail-closed).
MIN_OBS = 1

#: Calendar-day staleness ceiling on the newest snapshot (fail-closed).
MAX_AGE_DAYS = 400

#: Coverage floor, measured into names_floor_ok — refusal belongs to consumers.
NAMES_PER_DATE_FLOOR = 50

#: What the params block reports as its provenance.
PARAMS_SOURCE = (
    "design orch#984 §4 (candidate quality_gp) + the impl-step-1 build spec; "
    "SOURCE_COLUMN is the upstream Novy-Marx ratio from "
    "renquant_base_data.sec_fundamentals.compute_derived_features "
    "(GrossProfit or the Revenue−CostOfRevenue identity fallback, over "
    "Assets); frozen in renquant_model_factors._frozen_params_quality_gp_v0 "
    "BEFORE any scoring run"
)
