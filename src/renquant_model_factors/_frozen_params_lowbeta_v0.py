"""The lowbeta v0 params constants — FROZEN prereg content (orch#984 §5/§5b).

Frozen in the build PR itself, BEFORE any scoring run (see the high52w
module's freeze rationale — identical). A different window, return
construction, or estimator is a NEW params version, never an edit here.

The formula (Frazzini–Pedersen betting-against-beta, simple-sort form):

    score = -beta_hat

where beta_hat is the OLS slope of the ticker's daily returns on SPY's
daily returns over the trailing BETA_WINDOW=252 PAIRED return observations
at or before the cutoff. Returns are simple close-to-close returns derived
from the injected close series (``pct_change(fill_method=None)`` — a gap
yields NaN and the pair is dropped, never forward-filled); this diverges
from momentum's TOTAL-return series deliberately: v0 freezes the close-only
surface, and a dividend-adjusted variant would be a new params version. The
SPY series is an INPUT (``FactorReaders.market_close``), never fetched.
RAW score — the blend machinery z-scores at serve time.

BETA_WINDOW/MIN_OBS equal momentum v0's formation clock (model#164 §2) by
design — one estimation horizon across the sibling factors;
``test_lowbeta_v0_shares_the_momentum_v0_clock`` holds the equality.
"""
from __future__ import annotations

#: Trailing PAIRED daily-return observations (ticker, SPY) used by the OLS.
BETA_WINDOW = 252

#: Fewer than this many pairs -> NaN score (fail-closed).
MIN_OBS = 200

#: Coverage floor, measured into names_floor_ok — refusal belongs to consumers.
NAMES_PER_DATE_FLOOR = 50

#: What the params block reports as its provenance.
PARAMS_SOURCE = (
    "design orch#984 §4 (candidate lowbeta) + the impl-step-1 build spec; "
    "BETA_WINDOW/MIN_OBS/NAMES_PER_DATE_FLOOR adopted from momentum v0's "
    "frozen clock (model#164 §2) by design; frozen in "
    "renquant_model_factors._frozen_params_lowbeta_v0 BEFORE any scoring run"
)
