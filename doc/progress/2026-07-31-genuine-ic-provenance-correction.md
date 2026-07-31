# `genuine_ic = +0.00079` — the number is real, my sourcing was not

**Bottom line.** `+0.00079` exists and I have now traced it to the byte. But the sentence I
published around it was wrong in **three** ways at once, and correcting it **reverses the
GOAL-4 conclusion I drew from it** — though that conclusion is itself now withdrawn
(see "Review round 1" below). The original claim was: the Phase-0 screen is *marginally powered*, not short by
a factor of 47.

## What I published, and what is actually true

> *"the production recipe's `genuine_ic` above the placebo floor is **+0.00079**
> `[VERIFIED — prior work, renquant-backtesting#83]`"* — 2026-07-30 prereg, twice.

| | claimed | measured 2026-07-31 |
|---|---|---|
| source | `renquant-backtesting#83` | #83 contains the string **0 times**; it is titled *"the WF gate admits on RECIPE identity only"* |
| subject | *the production recipe* | the newest weekly retrain **candidate** (staging) |
| the deployed recipe's value | — | **+0.04153** — **52.5×** larger |
| wording | *"above the placebo floor"* | `genuine_ic = aligned_real_ic − placebo_ic`, i.e. above the **placebo IC**. Its margin against the enforced **floor** is a different number, and for that candidate it is **−0.02868** |

The true source `[VERIFIED — 本次实测]`:

```
panel-ltr.alpha158_fund.weekly_20260726T170001Z.staging.json
  sanity_placebo_aligned_real_ic = 0.05893637993269222
  sanity_placebo_ic              = 0.05814571512436258
  difference                     = 0.0007906648083296358
```
identical in the `20260729T201003Z` and `20260730T201007Z` staging artifacts.

## The finding I did not go looking for

Ordering every distinct `(aligned, placebo)` pair by its `train_end` gives a collapse that is **strictly decreasing between distinct `train_end`
groups** (two artifacts tie at 2018-04-30, and their order inside the tie is not
asserted):

| train_end | aligned_real_ic | placebo_ic | genuine_ic | enforced floor | enforced |
|---|---:|---:|---:|---:|:--|
| 2018-04-26 | 0.07588 | 0.03435 | **0.04153** | 0.03794 | **PASS** — and this is the **deployed** artifact |
| 2018-04-30 | 0.06542 | 0.05618 | 0.00924 | 0.03271 | FAIL |
| 2018-04-30 | 0.06514 | 0.05705 | 0.00809 | 0.03257 | FAIL |
| 2018-05-01 | 0.06495 | 0.05918 | 0.00577 | 0.03248 | FAIL |
| 2018-05-02 | 0.06464 | 0.05939 | 0.00525 | 0.03232 | FAIL |
| 2018-05-03 | 0.06309 | 0.05980 | 0.00329 | 0.03155 | FAIL |
| 2018-05-04 | 0.05894 | 0.05815 | **0.00079** | 0.02947 | FAIL |

Criterion: `placebo_ic < max(0.005, 0.5·|aligned_real_ic|)`.

**The decay is not the real IC falling.** `aligned_real_ic` drifts down 22% (0.0759 → 0.0589)
while `placebo_ic` climbs **+69%** (0.0343 → 0.0582). The candidates are not getting weaker
at ranking; they are getting **better at ranking a shuffled label**, which is the leakage
signature the criterion exists to catch.

**Every vintage after the deployed one fails.** The deployed row's fingerprint appears in
12 files — including **every `weekly_rollback_*` from 2026-07-16 through 07-30**. So the
chronic "every retrain rejected" is visible here as a mechanical fact: each weekly attempt
rolled back to this same 2018-04-26 vintage. That is a *sanity-battery* observation (one
fold's `sanity_placebo_*`), not the full gate verdict, and is reported as such.

## What this does to GOAL-4

The Phase-0 power analysis compared its MDE lower bound (**0.0376 IC**
`[早前实测 — model#129 tools/goal4_null_calibration.py]`) against `+0.00079` and concluded a
**47×** wall. Against the number that sentence *claimed* to be — the **deployed** recipe's
`genuine_ic` — the ratio is

```
0.0376 / 0.04153 = 0.91x
```

**The MDE is BELOW the deployed recipe's leakage-adjusted IC.** The honest restatement:

> The Phase-0 screen is **marginally powered**, not hopeless. The 47× wall was an artefact
> of dividing by a *failing candidate's* residual. And neither number is an **ensemble
> gain** — a member's `genuine_ic` and the increment from blending members are different
> quantities. The achievable increment remains **unmeasured**.

This **weakens my own earlier negative claim.** Recording it that way is the point.

## Not done here

`model#129` carries `assert m / 0.00079 > 20`, which encodes the withdrawn yardstick. That
PR is **awaiting review and is frozen** — the assertion is flagged on the PR, not amended in
place.

---

## Review round 1 — the correction reached its conclusion by the route that caused the error

Codex: *"the claimed reversal to marginally powered is not supportable. The 0.0376 MDE
comes from model#129 calibration whose null and MDE are unresolved … a deployed
single-recipe `genuine_ic` is not an ensemble increment."* Accepted.

**What survives: the provenance correction.** The prereg cited `+0.00079` as "the
production recipe's `genuine_ic`". That named the wrong subject; the deployed recipe
reads **+0.04153** `[VERIFIED — 本次实测, evidence/2026-07-31-genuine-ic-provenance/]`.
Source, subject and wording are corrected and stay corrected.

**What is withdrawn: the 0.91× and everything read off it.** Neither side of that ratio
can carry a power conclusion:

* the **numerator** is not a valid detection floor — `0.0376` comes from model#129's
  calibration, which is itself unresolved: its null is a *dependence-sensitivity
  diagnostic*, not a calibration, and its MDE is marked non-decisional in the emitted
  artifact. **A ratio inherits the standing of its inputs.**
* the **denominator** is the wrong estimand — a deployed **single-recipe** `genuine_ic`
  is not an **ensemble increment**. The screen asks what combining members *adds* over
  the incumbent; one recipe's own IC is not that quantity, so the two are not
  commensurable whatever their ratio.

**The uncomfortable part.** This PR corrected a citation that paired the MDE with the
wrong `genuine_ic` — and then reached its headline by pairing the MDE with a different
`genuine_ic`. Same move, one number later. Finding a wrong denominator is not the same
as having found the right one, and "the corrected version of my error" is the easiest
conclusion to believe.

The test no longer pins a replacement ratio. It asserts the provenance fact the evidence
does support and that the prereg carries **no** power conclusion from this comparison —
pinning `0.91` would have re-committed the error in the artifact meant to prevent it.

`[VERIFIED — this session]` 5 tests pass. Screen power **remains UNRESOLVED** pending a
valid ensemble-specific inference design.
