# GOAL-4: the Phase-0 screen has a power wall. Four ways forward — for DISCUSSION

**STATUS: NOT A PREREGISTRATION. Nothing here is frozen.** No arm is registered,
no threshold is committed, no run may cite this document as authority. It exists
so the *choice* is made in review before any prereg is written — the sequence the
operator asked for on 2026-07-30 after I froze 44 prereg commits against 3 design
commits in 20 hours.

**Date:** 2026-07-30 · GOAL-4 (multi-model ensemble) · `renquant-model`

---

## 1. Bottom line

The Phase-0 screen did not fail because of a calibration bug. It has a
**structural power wall**: the smallest ensemble gain it could ever have declared
is **+0.0257 IC**, and it is measuring a quantity whose observed value is
**−0.0109 IC** (t = −1.0029, 8 blocks). Re-running it, with more compute or a
repaired positive control, cannot change that. The wall is set by the geometry —
508 evaluation dates, a 60-day label, therefore 8 independent blocks.

So the open question is **not** "is the ensemble good?" It is **"what size of gain
is worth buying, and are we willing to pay what it costs to see one?"** That is a
decision for review, not for me to settle inside another prereg.

## 2. The wall, in numbers

All from the committed probe
`doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/control_power_probe.json`.

| quantity | value | provenance |
|---|---|---|
| evaluation dates | 508 | `[VERIFIED — probe, `independent_main_arm.n_eval`]` |
| independent blocks (60d label) | **8** (28 dates dropped) | `[VERIFIED — same]` |
| observed ensemble gain | **−0.01090 IC** | `[VERIFIED — same, `mean`]` |
| its block-t | **−1.0029** | `[VERIFIED — same, `t`]` |
| block-mean standard error | 0.010870 | `[DERIVED — \|mean\|/\|t\|]` |
| `T_crit` = t(0.975, 7) | 2.3646 | `[VERIFIED — probe, `t_crit_student_leg`]` |
| **minimum detectable gain** | **+0.02570 IC** | `[DERIVED — T_crit x s.e.]` |
| best member (benchmark) IC | 0.07312 | `[VERIFIED — probe, `benchmark_mean_ic`]` |

The registered α-sweep agrees from the other direction: the control was **not
detected** at member IC 0.1018 (t = 2.211 < 2.3646) and **first detected** at
member IC 0.1794 (t = 4.601) `[VERIFIED — probe, `alpha_sweep`]`. To fire, the
screen needs an ensemble gain of **+0.098 IC** — larger than the best member's
entire IC.

### What each detectable gain would cost

First integer `n` satisfying `g >= t(0.975, n-1) x s.e._8 x sqrt(8/n)`, holding the
current 63.5 dates/block `[DERIVED — integer scan, 2026-07-30]`:

| target gain `g` | blocks needed | eval dates | ≈ years | vs today |
|---|---|---|---|---|
| +0.0257 | 9 | 572 | 2.3 | 1.1x |
| +0.0200 | 12 | 762 | 3.0 | 1.5x |
| +0.0100 | 39 | 2 476 | 9.8 | 4.9x |
| +0.0050 | 148 | 9 398 | 37.3 | 18.5x |
| +0.0020 | 911 | 57 848 | 229.6 | 113.9x |
| +0.0008 | 5 677 | 360 490 | 1 430.5 | 709.6x |

**Method note, stated because I got it wrong first.** My initial solver was a
fixed-point iteration that diverged and returned a **non-monotone** table —
`g = 0.098` appeared to need *more* blocks (16) than `g = 0.020` (12), which is
impossible. Discarded and replaced with the integer scan above, which is monotone
by inspection. The wrong table was never published.

## 3. Why this is not "my design broke, let's stop"

Two of the three failures on this line were mine and are already retracted in the
record (the asymptotic-α control, the amendment that fixed the wrong term). This
document is a different claim: **the geometry itself bounds what any screen of
this shape can see**, and that bound is now measured rather than suspected. A
power wall is a finding about the question, not an excuse about the answer.

The point estimate being **negative** matters too. It is not evidence against the
ensemble — at t = −1.0029 it is indistinguishable from zero — but it does mean
nobody should cite `t = −1.0029` as anti-ensemble evidence. It is a *no-information*
result, and the screen's own MDE is why.

## 4. Four options

Costs are order-of-magnitude, for discussion, not commitments.

### Option A — buy the sample: extend the out-of-sample window
Take `g = +0.010` as the smallest gain worth deploying → 39 blocks, ~2 476 eval
dates. The panel carries **2 570 dates total**
`[VERIFIED — prod artifact `panel_shape.dates`]`, so this consumes essentially the
entire panel as out-of-sample and leaves no training data.
**Verdict for discussion: arithmetically dead at h=60.** Worth stating explicitly
so nobody proposes it again.

### Option B — shrink the label horizon to buy blocks
The 60-day label is what forces 60-day blocks. At h=20 the same 508 dates give
~25 blocks instead of 8, and s.e. scales by `sqrt(8/25)` = 0.566 → MDE falls
**+0.0257 → ~+0.0145** `[DERIVED]`. Nearly 2x for free.
**The catch, and it is the same one GOAL-7 hit:** h=20 is a *different question*.
The live book trades a 60-day estimand; a 20-day answer does not transfer without
its own argument. This must be entered as a horizon study, not smuggled in as a
power fix.

### Option C — change the estimand to the decision boundary
An ensemble only earns anything where it **flips a buy/no-buy**. Measuring
realised return on flipped decisions has far fewer units but a far larger
per-unit effect than a cross-sectional IC difference.
**Open question this option must answer first:** how many flips actually occur.
If the answer is single digits per year, this trades one power wall for another —
and that count is cheap to measure before committing.

### Option D — accept the wall as the answer
If no gain below +0.0257 is worth deploying, the screen already answered: nothing
that large is present. GOAL-4 then closes on *power* grounds with the honest
statement "an ensemble of these three members is not measurable at a size worth
deploying", not on a KILL verdict it never earned.
**This is a real option, not a retreat** — but it is the operator's call, not
mine, which is precisely why it is listed here rather than acted on.

## 5. What I recommend, and what I need

**Recommend C, gated on one cheap measurement first**: count the decision flips
the ensemble would have caused over the 508 dates. That number is a day's work,
costs nothing, and it decides between C and D without any preregistration. If
flips are plentiful, C is the highest-power route to a *tradeable* answer. If they
are rare, D is honest and we stop paying for this line.

**Needed from review:** agreement on (a) the smallest gain worth deploying — every
row of the §2 table hangs on it — and (b) whether to run the flip count.

## 6. Explicitly not proposed

No new prereg. No re-run of the voided screen. No change to any production
surface. No claim that the ensemble is bad.
