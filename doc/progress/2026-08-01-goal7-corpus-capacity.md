# GOAL-7 — h=120 cannot have an identifiable bar on this corpus, and no amount of data fixes it

**Date:** 2026-08-01 · `renquant-model` · GOAL-7 Stage 1 (design capacity)

## Bottom line

model#147 measured that the registered `t_{0.975,17} = 2.1098` bar is **not identifiable**
on the one design that was run. This answers the design question behind it: *which horizon
could this corpus ever support?* Same two requirements — preserve the label's dependence
(`Lb ≥ h`) and leave enough draws to estimate a 5% tail (`⌈n/Lb⌉ ≥ floor`) — applied across
horizons `[本次实测 2026-08-01]`:

```
corpus calendar          3 161 dates   2014-01-02 → 2026-07-29
admissible (≥20 names)   2 407 dates   2016-12-29 → 2026-07-29
```

| h | scope | available | need @ floor 20 | |
|--:|---|--:|--:|---|
| 20 | pre-burn | 1 182 | 400 | OK |
| 60 | pre-burn | 1 142 | 1 200 | SHORT |
| **120** | **pre-burn** | **1 082** | **2 400** | **SHORT** |
| **120** | **whole corpus** | **2 287** | **2 400** | **SHORT** |

**`h = 120` cannot be rescued by data.** Discarding the registered burn boundary entirely
and using every admissible date through 2026-07-29 still leaves it short. That closes a
design family on this corpus rather than deferring it.

## The floor is mine, so its sensitivity is the finding's real strength

`draws_floor = 20` is a convention **I** chose in model#147, not a standard. A verdict
resting on it is only as good as the choice, so it is swept over 10 / 20 / 30:

| | verdict across all three floors |
|---|---|
| `h = 120`, pre-burn | **INFEASIBLE** — short at every floor |
| `h = 20`, pre-burn | **FEASIBLE** — clears at every floor |
| `h = 60`, pre-burn | **FLOOR-DEPENDENT** — OK at 10, SHORT at 20 and 30 |
| `h = 120`, whole corpus | **FLOOR-DEPENDENT** — OK only at 10 |

`FLOOR_DEPENDENT` is a real third value, and `h = 60` gets it. Reporting it as either
"feasible" or "infeasible" would launder my convention into a finding. It is **not
settled**, and the way to settle it is to justify a floor, not to pick the one that gives
the answer you want.

The `h = 120` pre-burn verdict is the one that matters and it is **robust** — it does not
depend on me at all.

## Two things this must not be read as

**Capacity is not power.** Clearing this test means a bar *could be calibrated*, not that a
design *could detect anything*. GOAL-6 Stage 0 already measured that the shorter horizon
buys no statistical power (H2 NOT SUPPORTED: ~3× the independent blocks, proportionately
smaller effect, flat ratio). So `h = 20` passing here argues for **nothing** about a 20-day
design; treating it as an argument would be substituting one instrument for another, which
is a standing correction on this programme's register.

**The burn boundary is not mine to lift.** `2021-10-08` is registered (AMENDMENT 2, A2.2).
The `whole corpus` rows exist to *bound* the question — to show that even unlimited data
does not rescue `h = 120` — and are not a licensed design.

## Verification that this is the study's own admissibility rule

The pre-burn `h = 120` count reproduces the frozen run exactly: **1 082 dates, last usable
`t` = 2021-04-19**, matching the registered `PIN_N_EVAL` and `EVAL_END`. If the rule here
differed from the study's, that number would not land. The matrix is bound by sha256
`85c27fc1…`.

## Tests

12, including the one that would catch the laundering: `h = 60` must report
`FLOOR_DEPENDENT` and neither of the two answers. Suite: **1171 passed, 2 skipped**, run
before the push.


---

## Addendum 2026-08-01 — is the shortfall the corpus, or my admissibility rule?

The verdict above only means something if `h = 120`'s shortfall is the **data**. The
obvious objection is that 754 of the corpus's 3 161 dates are excluded by an admissibility
rule I did not have to choose. Measured `[本次实测 2026-08-01]`:

| cause | dates | span |
|---|--:|---|
| the corpus has **fewer than 20 names at all** | **504** | 2014-01-02 … 2015-12-31 |
| ≥20 names present, **features not yet computable** | **250** | 2016-01-04 … 2016-12-28 |
| | **754** | |

**Three would-be remedies, all foreclosed:**

1. *Extend the window backwards.* The 504 dates before 2016 have **almost no names** —
   median **1** ticker per date in 2014 and 2015. There is nothing there to recover.
2. *The warm-up is too conservative.* The gap between the first date with ≥20 names
   (2016-01-04) and the first admissible date (2026-12-29 → **2016-12-29**) is **250
   sessions** — one year, which is exactly what `mom_12_1` means. Shortening it would
   compute the feature from history that does not exist.
3. *Relax the name floor.* Re-run at `MIN_NAMES` ∈ {20, 10, 5}: **2 407 admissible dates in
   all three**. The floor recovers **zero** dates and is not what binds.

**So the shortfall behind `h = 120` is the corpus itself**, not a rule I picked — which is
what makes the INFEASIBLE verdict above a fact about this programme's data rather than
about my choices. That is the second convention in this document falsified rather than
defended (the first being the draws floor).

5 more tests (17 total). Suite: **1176 passed, 2 skipped**.
