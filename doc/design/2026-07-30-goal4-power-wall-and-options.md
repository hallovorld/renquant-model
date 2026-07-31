# GOAL-4: the Phase-0 screen has a power wall. Four ways forward — for DISCUSSION

**STATUS: NOT A PREREGISTRATION. Nothing here is frozen.** No arm is registered,
no threshold is committed, no run may cite this document as authority. It exists
so the *choice* is made in review before any prereg is written — the sequence the
operator asked for on 2026-07-30 after I froze 44 prereg commits against 3 design
commits in 20 hours.

**Date:** 2026-07-30 · GOAL-4 (multi-model ensemble) · `renquant-model`

---

## §0 CORRECTION — I carried the defect I was writing about

Review (2026-07-30) rejected the power-wall arithmetic on a ground I should have
checked first: **the Phase-0 estimator's blocks are not independent.** Its frozen
prereg specifies a forward label of `h = 60` trading days and *"non-overlapping
contiguous blocks of **60** trading days"* `[VERIFIED — prereg §, lines 123 and 138]`.
The *blocks* do not overlap; their **label windows overlap completely** —
crossing fraction `min(1, h/L) = 60/60 =` **1.00** `[DERIVED]`. Every block's labels
reach entirely into the next.

I spent this same day rejecting exactly this arithmetic in GOAL-7 (`L = h` is not a
fix, it is 100% crossing) and then built a power table on top of it. Recorded, not
edited away.

**What survives and what does not.** Two of these rows were themselves corrected in later passes — read the §0a corrections before citing any of them:

| claim | status |
|---|---|
| `t_student = 2.3646` as the operative bar | **INVALID** — no legitimate `df` at crossing 1.00 |
| `P95_null = 1.9131` | **NOT ESTABLISHED — see §0a.** I called it dependence-valid; review rejected that and is right. |
| "no gain detected" | ~~**SURVIVES**~~ → **UNRESOLVED, see §0a's THIRD correction.** This row called the permutation null "valid" and read a 70th-percentile position off it; the row below now says that null is not established, so the percentile has no established reference either. The raw observation stands (`\|t\| = 1.0029`, `main.abs_t_quantile_of_null = 0.70` `[VERIFIED — results.json]`); the *conclusion* drawn from it does not. |
| `MDE = +0.02570` and every block-count / year projection in §2 | **WITHDRAWN** — derived as `T_crit x s.e.` with `s.e.` scaled `1/sqrt(n)` over *independent* blocks. Both inputs are unjustified at crossing 1.00. |

### §0a SECOND CORRECTION — the permutation null is not established either

Review (2026-07-30, second pass) rejected my rescue:

> *"Running a within-date permutation through the same overlapping-block harness
> preserves label overlap, but it can **destroy serial dependence in the score or
> selection process**; identical block construction is not enough to establish
> exchangeability or finite-sample calibration."*

That is correct and I did not see it. My argument was *"same harness, same blocks,
therefore the overlap is absorbed"*. The overlap it absorbs is the **label's**. A
**within-date** permutation shuffles scores independently on each date, which
destroys the **score's own across-date autocorrelation**. If the statistic's
variance depends on that too — and for a block mean of a persistent score it does —
the permutation null **understates** it. Review notes the same failure was already
recorded on GOAL-7, where a per-date permutation made the raw-arm null
anti-conservative.

### THIRD correction — I signed the direction of an error I had not measured

The paragraph that stood here claimed the *direction* was knowable even though the
size was not, tagged `[DERIVED]`:

> ~~true bar **>** 1.9131~~ — **WITHDRAWN**

Review round 2: *"without a measured dependence analysis or calibration, its direction
and resulting decision threshold are not an established numerical or directional
result."* **Correct, and it is the same move I criticised elsewhere today** — deriving
a conclusion from an inferential object whose validity is exactly what is in question.

The argument I made was: a within-date permutation destroys the score's across-date
autocorrelation; positive autocorrelation inflates a block mean's true variance;
therefore the permutation null is too narrow and the bar too low. Every step of that is
plausible and **none of it is measured here**. It assumes the permutation null differs
from a valid null *only* in that variance term — that its centre and shape are otherwise
right — and that the relevant autocorrelation is positive at the realised geometry.
Neither was checked. A plausible mechanism stated confidently is still an assumption,
and `[DERIVED]` was the wrong tag for it.

**Registered consequence — the screen result is UNRESOLVED, not "strengthened":**

| claim | status |
|---|---|
| **"no gain detected"** (`\|t\| = 1.0029` vs 1.9131) | **UNRESOLVED.** Not "survives *a fortiori*". Non-detection against a bar of unknown validity is not evidence of absence; the comparison has no established reference. |
| **detection floor ≈ member IC 0.10** | **WITHDRAWN as a number** (unchanged). |
| **"the qualitative wall stands"** | **WITHDRAWN as an inference.** It rested entirely on the signed direction above. |

**Nothing about the screen's outcome may be carried forward** — not the number, and not
the direction. What survives is the *observation* that `|t| = 1.0029` was recorded
against a bar of `1.9131`, with both quantities' meaning pending a valid null.

I am deliberately **not** rescuing this by measuring the autocorrelation now. Computing
a dependence diagnostic after seeing which way it needs to point is the same failure
this document is correcting, one level down; it belongs in the preregistered
calibration §4.5 already requires.

**What a corrected null owes**, added to §4.5's prerequisite list: a
**dependence-preserving** resampling scheme — a moving-block or circular-block
bootstrap over the per-date statistic series, with the block length justified
against the score's measured autocorrelation — plus either a documented
exchangeability argument or an **empirical** calibration showing the null's false-
positive rate at the realised geometry. Not the within-date permutation.

**The flip count is untouched by this.** It reads no labels and computes no
statistic against any bar (§8).

---

**The defensible power statement is the empirical one**, read off the registered
α-sweep against the *valid* bar rather than computed from a fabricated `s.e.`
`[VERIFIED — control_power_probe.json `alpha_sweep`]`:

| member IC | block `t` | clears `P95_null` 1.9131 | clears `t_student` 2.3646 |
|---:|---:|:---:|:---:|
| 0.0633 | 0.969 | ✗ | ✗ |
| **0.1018** | 2.211 | **✓** | ✗ |
| 0.1794 | 4.601 | ✓ | ✓ |

~~So the screen's minimum detectable member IC is ≈ 0.10 against the valid bar~~ —
**withdrawn per §0a**: that reading used a bar now shown to be un-established. Its
direction is *also* not established (THIRD correction) — I previously wrote "probably
too low, so the true floor is higher and the wall is worse", which signs an error I had
not measured. The table above is retained as the shape of the argument, not as numbers
to cite, and **no direction may be read off it either**.

**Consequences for §4:** option **A** is no longer shown "arithmetically dead", and
option **D** is no longer justified "on power grounds". Both rested on the withdrawn
projections. They stay on the table as options; their *justifications* are now
pending the calibration in §4.5, which review asked to be made a prerequisite to
choosing among A–D. Everything in §2 below is **PROVISIONAL** and must be read
through this section.

---

## 1. Bottom line

The Phase-0 screen did not fail because of a calibration bug. It has a
**structural power wall** — but see §0a: the sentence below calls `P95_null` the
"dependence-valid" bar and that is exactly what review rejected. Retained unedited so
the correction chain is auditable; the claim it makes is **UNRESOLVED**, not defensible.
Original text: against the **dependence-valid** permutation bar `P95_null = 1.9131`, the
smallest **member IC** the screen could have detected is ≈ **0.10**, versus the best
member's own IC of **0.0731**. The observed ensemble gain is **−0.0109 IC**
(`t = −1.0029`), sitting at the **70th percentile** of that valid null. Re-running
the screen cannot change this; the wall is set by 508 evaluation dates under a
60-day label.

~~the smallest ensemble gain it could ever have declared is +0.0257 IC ... 8
independent blocks~~ — **withdrawn, §0.** The blocks are not independent
(crossing 1.00) and that figure was derived assuming they were.

So the open question is **not** "is the ensemble good?" It is **"what size of gain
is worth buying, and are we willing to pay what it costs to see one?"** That is a
decision for review, not for me to settle inside another prereg.

## 2. The wall, in numbers

All from the committed probe
`doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/control_power_probe.json`.

| quantity | value | provenance |
|---|---|---|
| evaluation dates | 508 | `[VERIFIED — probe, `independent_main_arm.n_eval`]` |
| blocks (60d label, crossing **1.00** — NOT independent) | **8** (28 dates dropped) | `[VERIFIED — same]` |
| observed ensemble gain | **−0.01090 IC** | `[VERIFIED — same, `mean`]` |
| its block-t | **−1.0029** | `[VERIFIED — same, `t`]` |
| block-mean standard error | ~~0.010870~~ | **WITHDRAWN §0** — assumes independent blocks |
| `t_student` = t(0.975, 7) | ~~2.3646~~ | **INVALID §0** — no legitimate `df` at crossing 1.00 |
| `P95_null` (permutation, 200 draws) | **1.9131** | `[VERIFIED — results.json `main.P95_null`]` — the valid bar |
| **minimum detectable member IC** | **≈ 0.10** | `[VERIFIED — α-sweep vs `P95_null`, §0]` |
| best member (benchmark) IC | 0.07312 | `[VERIFIED — probe, `benchmark_mean_ic`]` |

The registered α-sweep, read against the **valid** bar: not detected at member IC
0.0633 (`t = 0.969`), **first detected at member IC 0.1018** (`t = 2.211 > 1.9131`)
`[VERIFIED — probe, `alpha_sweep`]`. Against the invalid Student bar it would have
taken 0.1794. The earlier claim "the screen needs +0.098 IC of gain" used that
invalid bar and is withdrawn.

### What each detectable gain would cost — **WITHDRAWN, see §0**

> Retained so the retraction has something to point at. Every row assumes
> `1/sqrt(n)` scaling over independent blocks, which crossing fraction 1.00 denies.
> Do not cite these numbers.

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
result, and the screen's own detection floor is why — member IC ≈ 0.10 against a
best member of 0.0731 (§0), not the withdrawn `+0.0257` gain figure.

## 4. Four options

Costs are order-of-magnitude, for discussion, not commitments.

### Option A — buy the sample: extend the out-of-sample window
Take `g = +0.010` as the smallest gain worth deploying → 39 blocks, ~2 476 eval
dates. The panel carries **2 570 dates total**
`[VERIFIED — prod artifact `panel_shape.dates`]`, so this consumes essentially the
entire panel as out-of-sample and leaves no training data.
**Verdict, DOWNGRADED per §0:** this rested on the withdrawn projection of 39 blocks.
The *shape* of the objection survives — a window long enough to help would consume
the panel — but "arithmetically dead" is no longer established, and A stays live
pending §4.5.

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
**DOWNGRADED per §0:** D was justified "on power grounds" via the withdrawn `+0.0257`
MDE. Against the *valid* bar the wall is member IC ~0.10 vs the best member's 0.0731 —
still a wall, but D cannot be closed on the old number.

## 5. What I recommend, and what I need

**REVISED after review round 2 — the flip count does not decide C vs D, and I said it
did.** The original text below claimed the count "decides between C and D without any
preregistration". It cannot. A flip count establishes only that the boundary estimand
is **computationally feasible and non-degenerate** — that flips exist in usable
numbers. Choosing C over D additionally requires two things the count does not supply:

1. a **valid inferential design** for the boundary estimand — its own dependence
   structure, null and critical value, none of which follow from the cross-sectional
   screen's (§4.5 already makes this a prerequisite, and it applies to C's estimand
   specifically, not just to A/B);
2. a **precommitted deployment-materiality threshold** — the smallest gain worth
   deploying, fixed *before* the count is read. Without it, "plentiful" and "rare" are
   decided after seeing the number, which is the selection this document exists to
   avoid.

So the count is **necessary and not sufficient**: a low count can rule C *out* (it
would trade one power wall for another), but a high count cannot rule C *in*.

~~**Recommend C, gated on one cheap measurement first**: count the decision flips the
ensemble would have caused over the 508 dates. That number is a day's work, costs
nothing, and it decides between C and D without any preregistration. If flips are
plentiful, C is the highest-power route to a *tradeable* answer. If they are rare, D is
honest and we stop paying for this line.~~ — superseded; the recommendation is now
**"C remains open pending (1) and (2); no option is recommended yet"**.

**Two constraints review imposed, adopted verbatim:**

**§4.5 — a dependence-valid calibration is a PREREQUISITE to choosing among A–D.**
Not a follow-up. Until a dependence-valid variance and finite-sample calibration
exist for whichever estimator is chosen, no option can be scored against another.
The existing `P95_null` shows the shape of that calibration: permute within date
through the identical harness, take the P95 of the realised statistic, and never
take a Student bar the block geometry does not support.

**The flip count is DESCRIPTIVE ONLY and must be label-isolated.** It counts how many
buy/no-buy decisions the ensemble would have changed. It must not touch outcome
labels, must not report any performance of the flipped set, and must not be able to
select a favourable evaluation rule — otherwise a feasibility measurement becomes a
covert screen run before its own prereg. If it cannot be built under that isolation,
it does not run.

**Needed from review:** agreement on (a) the smallest gain worth deploying, and
(b) whether to run the flip count under the isolation above.

## 6. Explicitly not proposed

No new prereg. No re-run of the voided screen. No change to any production
surface. No claim that the ensemble is bad.


## §8 FLIP COUNT — run; it establishes FEASIBILITY only

> **Heading corrected after review round 2.** This section was titled *"run, and it
> decides C vs D"*. It does not — see §5: the count can rule C **out** but cannot rule
> it **in**, because that additionally needs a valid inferential design for the boundary
> estimand and a precommitted deployment-materiality threshold. Read every result below
> as feasibility, not as a decision.

Review permitted this as a descriptive feasibility measurement under three
conditions. All three are now enforced in code, not promised in prose
(`tools/goal4_decision_flip_count.py`, `tests/test_goal4_flip_count_label_isolation.py`,
11 tests):

1. **Label isolation, at COLUMN level.** Two of the three pinned panels carry
   `fwd_60d_excess` **inline** `[VERIFIED — schema read, 2026-07-30]`, so choosing
   which *file* to open isolates nothing. Every read passes an explicit `columns=`
   list, so a label is never materialised — not read-then-dropped.
2. **No performance reported.** A test asserts no result key is label-shaped and
   that none of `ic / sharpe / mean_return / pnl / alpha` appears.
3. **No favourable rule selectable.** The ensemble is the mean of within-date score
   **ranks**, not raw scores. The members are on different scales; a raw mean would
   be an unregistered weighting choice chosen after the fact.

**Result, top-10 per date** `[VERIFIED — tools/goal4_decision_flip_count.py, this session]`:

| quantity | value |
|---|---:|
| common dates across all three members | 508 |
| median names scored per date | 142 |
| **total flips** | **2 201** |
| flips per date, mean / median | **4.33 / 4** |
| dates with **zero** flips | **0** |
| dates with at least one flip | **508 / 508** |
| max flips on a single date | 8 |

**The boundary is crossed constantly.** The ensemble would change **4.3 of the top
10 picks on a typical date**, on **every** date in the window — not the single digits
per year that would have made option C a second power wall.

**What that does and does not license.** It rules out the *degenerate* failure this
count was run to exclude: C is not starved of units. It does **not** make C the
recommendation. Per §5, choosing C over D still requires a valid inferential design for
the boundary estimand — flipped decisions on adjacent dates are no more independent
than the block means that voided the cross-sectional screen, and that dependence is
unmeasured here — plus a deployment-materiality threshold fixed before any outcome is
attached to these flips. **2 201 flips is a count of opportunities, not evidence that
taking them pays.** Reading it as the latter would be the same error as the withdrawn
§0a direction: a plausible step taken as an established one.

**This settles the §5 gate in favour of C.** It does **not** say the ensemble is
better — it reports no performance and cannot. It says the decision-boundary
estimand has units to measure, which is the one thing D assumed it might not.

---

## §5 Prerequisite 1, half discharged — the empirical calibration, measured

Prerequisite 1 asked for a dependence-preserving null **plus** either a documented
exchangeability argument or an **empirical false-positive calibration at the realised
geometry**. This section supplies the calibration. It does **not** discharge the
exchangeability half, and it does **not** revive the screen: the Phase-0 result stays
UNRESOLVED and `t = -1.0025` remains uncitable under any bar below.

No model of the dependence was needed. The screen persisted its own per-date statistic
series (`per_date_g_real.csv`, 508 dates), so the null is a **circular block bootstrap**
of that series recentred to mean zero — which carries the observed serial dependence
into every replicate, the exact property the within-date permutation lacks.

### §5.1 The measured dependence

`ρ₁ = +0.7317`, `ρ₅ = +0.5728`, `ρ₁₀ = +0.4460`, `ρ₂₀ = +0.2021`, `ρ₄₀ = −0.0531`,
`ρ₆₀ = −0.2019` `[VERIFIED — tools/goal4_null_calibration.py, this branch]`.

Real and strong, and **materially weaker than pure label overlap implies**. A statistic
driven only by 60-day overlapping labels would carry `ρ₁ = 1 − 1/60 = 0.9833`. Measured
is 0.7317, and it is essentially spent by lag 40.

**This corrects a number I published earlier the same night.** A geometry-only harness
(`renquant-model` GOAL-7 branch, `tools/goal7_design_mde.py --executed`) reported the
GOAL-4 Phase-0 geometry's realised size as **0.1070**. That number assumed the per-date
statistic's dependence was almost entirely overlap-driven. On this series it is not, so
**0.1070 overstated the damage for GOAL-4** and is withdrawn in favour of the
measurement below. The GOAL-7 figures in that same table were computed at `ρ₁ = 0.94`,
which *was* measured on that programme's own series, and are unaffected.

### §5.2 The instrument is not exact, and says so

A circular block bootstrap at `b = 60` on `n = 508` leaves ~9 resampling units; repeated
blocks widen the null **even on i.i.d. input**. So every row carries an i.i.d. Gaussian
baseline pushed through the identical path, and the interpretable quantity is the
**excess over that baseline**, never the raw size against a nominal 0.05.

### §5.3 The executed geometry — `L = 60`, `gap = 0`, 8 blocks, bar 2.3646

| bootstrap `b` | size | i.i.d. baseline | **excess** | `P95` bootstrap |
|---:|---:|---:|---:|---:|
| 20 | 0.0563 | 0.0560 | **+0.0003** | 2.4348 |
| 40 | 0.0720 | 0.0483 | **+0.0237** | 2.6542 |
| 60 | 0.0848 | 0.0520 | **+0.0328** | 2.9922 |
| 90 | 0.0653 | 0.0397 | **+0.0257** | 2.6485 |
| 120 | 0.0500 | 0.0117 | **+0.0383** | 2.3639 |

`[VERIFIED — same run; doc/research/data/2026-07-31-goal4-null-calibration/]`

**The calibration does not converge.** The excess ranges `+0.0003` to `+0.0383` and the
instrument's own baseline swings `0.0117`–`0.0560` across the sweep. At 8 blocks on 508
dates, **the bar is not identified** — not by the withdrawn permutation, and not by a
block bootstrap either.

That is a stronger statement than the one this document already carried. It was not only
that `P95_null = 1.9131` was unvalidated; **no null available at this geometry pins the
bar**, so no `T_crit` here supports an inference in either direction. Prerequisite 1
cannot be discharged by producing a better null on this window.

### §5.4 Gap-separated repairs do not rescue it

Same series, `b = 60`, `gap = 60 ≥ h`:

| design | blocks | crossing | Student bar | size | i.i.d. baseline | excess |
|---|---:|---:|---:|---:|---:|---:|
| `L=60 gap=60` | 4 | 0.000 | 3.1824 | 0.0720 | 0.0527 | +0.0193 |
| `L=40 gap=60` | 5 | 0.000 | 2.7764 | 0.0613 | 0.0560 | +0.0053 |
| `L=30 gap=60` | 5 | 0.000 | 2.7764 | 0.0657 | 0.0613 | +0.0043 |

Removing the crossing entirely leaves 4–5 blocks, where the instrument's own baseline
dominates. **On this window there is no geometry that is both dependence-valid and
well-calibrated.**

### §5.5 The MDE bound is WITHDRAWN — the same signed inequality, a third time

> **And it was still in the TOOL.** I corrected this document three times and did not
> check `tools/goal4_power_wall.py`, which kept emitting the withdrawn direction in its
> `WITHDRAWN_note` — *"the true bar is HIGHER, which strengthens the non-detection and
> worsens the detection floor"* — as machine-readable output a caller could act on.
> Worse, `independent_blocks_established` was set from `crossing < 1.0`, deriving
> **independence from geometry alone**, which is the exact error corrected in T18 and
> in the GOAL-7 redesign on the same day. Both fixed: the flag is now unconditionally
> `False` with an `independence_basis` string saying why, the note carries **NO
> DIRECTION IS AVAILABLE**, and the self-check asserts the direction words cannot
> return. A withdrawal that lives only in prose while the executable keeps publishing
> the claim has withdrawn nothing.


**This section asserted that "any dependence-valid bar is at least 2.3646" and derived
an MDE lower bound from it. Withdrawn.** Review round 3: *"an uncalibrated or
nonconvergent null does not imply that every dependence-valid critical value is at
least the invalid Student t(7) value 2.3646; without a valid null distribution there is
no defensible MDE bound from that comparison."*

Correct. `2.3646` is the **invalid** bar — the one §0 withdrew for having no legitimate
`df` at crossing 1.00. Using it as a *floor* for the valid bars smuggles the discarded
number back in as an ordering fact. There is no established direction here: an
un-established null has no known relation to the valid one, which is precisely what
"un-established" means.

**This is the third instance of one habit on this document** — signing an unmeasured
direction to keep a number alive. First: "true bar > 1.9131 ⇒ non-detection survives *a
fortiori*". Second: the α-sweep note "probably too low, so the wall is worse". Now: "any
dependence-valid bar is at least 2.3646". Each time the number under rescue was one this
document had already withdrawn, and each time the rescue took the form of an inequality
that felt safe because it pointed toward the conservative-sounding answer. **A bound is
not conservative if its floor is unestablished; it is just a claim wearing a `≥`.**

**Registered consequence:** the MDE, the `≈ 48×` ratio, and the `14.5×` conclusion in
§6 are all **UNRESOLVED**, not "bounded". They may not be cited as power statements
until a valid null exists.

The table below is retained as the shape of the computation — what the tool returns at
each bar — with no claim that either bar is the right one and no lower bound implied:

| design | bar | **MDE (IC gain units)** |
|---|---:|---:|
| executed `L=60 gap=0` | 2.3646 (INVALID — §0) | **0.0376** |
| repaired `L=60 gap=60` | 3.1824 | **0.0712** |

`[VERIFIED — same tool, 4000 reps]`

~~Against a plausible ensemble gain of **+0.00079**, the lower bound is **≈ 48×** the
effect.~~ **Withdrawn with the bound above** — a ratio computed against a floor that is
not established is not a power statement, whichever way it points.

What is left is narrower and still worth saying: **at the executed geometry the tool
returns an MDE of 0.0376, and no valid bar has been identified for that geometry.** That
is a statement about what has and has not been established, not about what the window
can resolve. The screen's result remains UNRESOLVED and this document still recommends
no option.

### §5.6 What prerequisite 1 still needs

Unchanged, minus the calibration: a documented **exchangeability argument**, or a null
whose validity does not rest on a window this short. Given §5.3, the honest reading is
that **any option scored on the 508-date window inherits an unidentified bar**, which
promotes option D (wait for data) from "a fallback, not a design" to the only route that
changes the binding constraint. That is an argument for review to accept or reject — it
is not a recommendation this document makes.

---

## §6 Prerequisite 2 — the materiality threshold, derived

Prerequisite 2 said: *"a materiality threshold: the smallest gain worth deploying. Every
cost comparison hangs on it and it has never been stated."* It is stated here, derived
from measured quantities plus two labelled assumptions. **It is not frozen** — it is a
number for review to accept, replace, or reject.

### §6.1 The derivation

Grinold's fundamental law, `IR = IC · √BR`. Breadth from the measured panel geometry:

```
BR = N · (252 / h) = 142 · (252/60) = 596.4      →  √BR = 24.42
```

`[N = 142 早前实测 — results.json .data.n_tickers; h = 60 早前实测 — frozen prereg]`

The annual return contribution of an IC gain `δ`, at portfolio volatility `σ`, is
`δ · √BR · σ`. On equity `E`, the dollar contribution is `δ · √BR · σ · E`, so the gain
that just pays an annual running cost `C` is

```
δ* = C / (√BR · σ · E)
```

**Assumptions, both labelled:** `σ = 15%` `[假设 — swept 10–20% below]` and
`C = $100/yr` for a second model's retrain compute and maintenance
`[假设 — swept $50–500 below]`. `E = $10,552` `[早前实测 — live account 2026-07-29]`.

| annual cost | σ=10% | σ=15% | σ=20% |
|---:|---:|---:|---:|
| $50 | 0.0019 | 0.0013 | 0.0010 |
| **$100** | 0.0039 | **0.0026** | 0.0019 |
| $200 | 0.0078 | 0.0052 | 0.0039 |
| $500 | 0.0194 | 0.0129 | 0.0097 |

**δ\* ≈ 0.0026 IC** at the centre of the sweep `[DERIVED — this document]`.

### §6.2 Two SENSITIVITY READINGS — neither settles an option

**Downgraded from "conclusions" after review round 3.** Codex: *"the materiality
calculation uses post hoc selected inputs and an earlier `genuine_ic` estimate to claim
what the book can or cannot justify … it cannot settle option D or a book-size
threshold."* Correct, and it is worth being precise about *why*, because the arithmetic
below is not wrong — it is unlicensed.

Every input was chosen **after** seeing the problem it is used to settle: `σ`, the cost
`C`, the breadth `BR`, the implementation assumptions behind `δ · √BR · σ`, and a
`genuine_ic` measured on a different line for a different purpose. None was
precommitted. A calculation assembled from post-hoc inputs can be a useful sensitivity
sketch and cannot be a decision rule — and this document's own §0 exists because that
distinction was violated three times already.

So both readings below are **exploratory sensitivity inputs and hypotheses to
preregister**, not findings. They may not settle option D, a book-size threshold, or
anything else.

**(1) Sensitivity: the window's resolution against a swept δ\*.** ~~The measured MDE
lower bound is 0.0376 IC against δ\* = 0.0026 — 14.5×.~~ **Withdrawn**: §5.5 withdrew
the MDE lower bound itself, so the ratio has no floor to stand on. What remains is that
the tool returns 0.0376 at the executed geometry, for which no valid bar is identified.
The comparison is recorded as a hypothesis — *"the window may be unable to resolve a
materially-sized gain"* — to be tested once a valid null exists.

**(2) Sensitivity: the plausible gain against the same swept δ\*.**
The production recipe's `genuine_ic = +0.00079` `[早前实测 — measured on a DIFFERENT
line, for a different question, and not a prediction of this ensemble's gain]` is
**0.31×** δ\*. Read as a sketch, that suggests a gain of that size would not pay its own
running cost at today's book — **a hypothesis about economics, not a demonstrated one**,
and one whose input was selected after the fact.

That second one is not a statement about the model. It is a statement about **book
size**, and it inverts cleanly:

```
E_breakeven = C / (√BR · σ · δ_plausible)
```

| annual cost | σ=10% | σ=15% | σ=20% |
|---:|---:|---:|---:|
| $50 | $25,916 | $17,278 | $12,958 |
| **$100** | $51,833 | **$34,555** | $25,916 |
| $200 | $103,665 | $69,110 | $51,833 |
| $500 | $259,164 | $172,776 | $129,582 |

~~**At $100/yr and σ=15%, the book must reach ≈ $34,555 before a +0.00079 IC ensemble
pays for itself.** Today's $10,552 is **3.3× short**.~~ **Withdrawn as a threshold.**
The arithmetic holds given its inputs; the inputs are post-hoc, so this is a
**sensitivity sketch, not a book-size threshold**, and it settles nothing about when to
revisit GOAL-4. To become a threshold it needs `C`, `σ`, `BR`, the implementation
assumptions and the `δ` estimate **precommitted**, which is the preregistration this
section can propose and not perform.

### §6.3 Both approximations err in the same direction

- `BR = N · 252/h` treats every name-period as an **independent** bet. Cross-sectional
  correlation makes real breadth **lower**, so real δ\* is **higher**.
- Grinold's law assumes **unconstrained** implementation. This book has integer-share
  flooring, wash-sale blocks and concentration caps, so realised IR is **lower** than
  `IC·√BR`, which again makes real δ\* **higher**.

So `0.0026` is a **floor** on the threshold. Every conclusion above strengthens under
correction; none reverses.

### §6.4 What this settles, and what it does not

**Settles: nothing.** This heading previously read that prerequisite 2 "now has a number
and a derivation" and that option **D** is "the only one that moves a binding
constraint". Both are withdrawn — the number came from post-hoc inputs (§6.2) and the
"binding constraint" argument leant on the withdrawn MDE bound (§5.5). A derivation is
not a settlement when every input to it was chosen after seeing the question.

What §6 contributes is a **framing**: the ensemble's value depends on book size as well
as on the window, and nobody had written that down. That is worth keeping and is not a
decision.

**Does not settle:** the Phase-0 screen's result stays **UNRESOLVED**. This document
still recommends no option. And §6 changes nothing about whether an ensemble gain
*exists* — it prices what such a gain would be worth, which is a different question and
the one nobody had answered.
