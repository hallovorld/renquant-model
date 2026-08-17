"""The high52w v0 params constants — FROZEN prereg content (orch#984 §5/§5b).

Frozen in the build PR itself, BEFORE any scoring run: the §5b
candidate-manifest freeze requires every candidate's EXACT formula/variant
committed before any corpus score is computed, and these constants ARE the
formula's free parameters. A different window, floor, or formula is a NEW
params version (v1, ...) with its own frozen module and its own explicit
domain validator — never an edit here.

The formula (George–Hwang 2004, 52-week-high proximity):

    score_t = close_t / max(close over the trailing WINDOW=252 trading-day
              observations, inclusive of t)

where close_t is the most recent valid (finite, strictly positive) close at
or before the cutoff, and the max runs over the valid closes in that same
window. RAW ratio in (0, 1] — the blend machinery z-scores components
cross-sectionally at serve time, so the emitter never z-scores.

WINDOW/MIN_OBS deliberately equal momentum v0's formation clock (model#164
§2): high52w is momentum's closest sibling (design orch#984 §4) and shares
its 12-month horizon by design, not by accident —
``test_high52w_v0_shares_the_momentum_v0_clock`` holds the equality so a
drifted copy fails loudly. NAMES_PER_DATE_FLOOR is likewise momentum v0's
floor: measured and recorded (``names_floor_ok``), never silently enforced.
"""
from __future__ import annotations

#: Trailing trading-day observations, inclusive of the cutoff observation
#: (= momentum v0's 252-day formation window, shared by design).
WINDOW = 252

#: Fewer than this many valid closes in the window -> NaN score (fail-closed).
MIN_OBS = 200

#: Coverage floor, measured into names_floor_ok — refusal belongs to consumers.
NAMES_PER_DATE_FLOOR = 50

#: What the params block reports as its provenance.
PARAMS_SOURCE = (
    "design orch#984 §4 (candidate high52w) + the impl-step-1 build spec; "
    "WINDOW/MIN_OBS/NAMES_PER_DATE_FLOOR adopted from momentum v0's frozen "
    "clock (model#164 §2) by design; frozen in "
    "renquant_model_factors._frozen_params_high52w_v0 BEFORE any scoring run"
)
