"""The v1_fast params constants — the FAST momentum clock (model#199).

Frozen in renquant-model#199 BEFORE any production run (operator ask
2026-08-03: "能不能再做一个快动量模型放shadow里负责每天给我发几个ntfy就行";
architecture fixed the same night: fast momentum is a SHADOW-ONLY patrol
lane, separate from the slow v0 lane that is bound for the prod MoE — the
two are never blended into one signal).

Unlike ``_frozen_params_v0`` there is NO sealed runner to mirror: the
AUTHORITY for these numbers is the #199 issue text itself, and
``test_params_v1_fast_matches_the_frozen_issue`` pins this module to those
literals so a drive-by edit fails loudly. Changing a value here means
amending #199 FIRST — the same freeze-then-run discipline, with the issue
standing where the sealed runner stands for v0.

Why these numbers (recorded, not re-arguable in code review):
- WINDOW=63: three-month formation — the standard fast/intermediate
  momentum horizon.
- SKIP=5: one-week skip. Short-term reversal is documented at the weekly
  horizon (Jegadeesh 1990, Lehmann 1990); a 21-day skip would defeat the
  "fast" purpose.
- MIN_OBS=50: the same ~79% coverage ratio v0 uses (200/252) applied to the
  63-day window, as #199 specifies ("min_obs scaling (>=50)").
- MIN_FEATURES / NAMES_PER_DATE_FLOOR / MIN_SIDE_OBS: identical to v0 —
  one construction, two clocks; only the clock changes.
"""

from __future__ import annotations

WINDOW = 63
SKIP = 5
MIN_OBS = 50
MIN_FEATURES = 3
NAMES_PER_DATE_FLOOR = 50
MIN_SIDE_OBS = 30

PARAMS_SOURCE = (
    "renquant-model#199 (frozen 2026-08-03 before any run; the issue is the "
    "authority — no sealed runner exists for this clock); held to the #199 "
    "literals by test_params_v1_fast_matches_the_frozen_issue"
)
