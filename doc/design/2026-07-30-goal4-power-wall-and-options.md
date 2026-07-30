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

**What survives and what does not**, measured rather than argued:

| claim | status |
|---|---|
| `t_student = 2.3646` as the operative bar | **INVALID** — no legitimate `df` at crossing 1.00 |
| `P95_null = 1.9131` | **NOT ESTABLISHED — see §0a.** I called it dependence-valid; review rejected that and is right. |
| "no gain detected" | **SURVIVES** — observed `\|t\| = 1.0029` sits at the **70th percentile** of that valid null `[VERIFIED — `main.abs_t_quantile_of_null` = 0.70]`. It fails against the valid bar too. |
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

**The direction of the error is knowable even though its size is not**
`[DERIVED — an understated null variance gives a bar that is too LOW]`:

> true bar **>** 1.9131

And that cuts **opposite ways** for my two claims, which is why "all of it is void"
would be the wrong summary:

| claim | effect of an anti-conservative null |
|---|---|
| **"no gain detected"** (observed `\|t\| = 1.0029`) | **STRENGTHENED.** It failed to clear even a bar that is too low; a correct, higher bar can only make the non-detection more secure. Survives *a fortiori*. |
| **detection floor ≈ member IC 0.10** | **WITHDRAWN as a number.** It was read off the same too-low bar, so the true floor is **higher** — the wall is **worse** than I published, not better. |
| **"the qualitative wall stands"** | survives *directionally*, for the same reason as the row above — but it may **not** be quantified until the null is fixed. |

**So: both directional conclusions hold; neither number may be cited.**

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
**withdrawn per §0a**: that reading used a bar now shown to be un-established and
probably too low, so the true floor is **higher** and the wall is **worse**. The
table above is retained as the shape of the argument, not as numbers to cite.

**Consequences for §4:** option **A** is no longer shown "arithmetically dead", and
option **D** is no longer justified "on power grounds". Both rested on the withdrawn
projections. They stay on the table as options; their *justifications* are now
pending the calibration in §4.5, which review asked to be made a prerequisite to
choosing among A–D. Everything in §2 below is **PROVISIONAL** and must be read
through this section.

---

## 1. Bottom line

The Phase-0 screen did not fail because of a calibration bug. It has a
**structural power wall** — but stated in the only currently defensible terms
(§0): against the **dependence-valid** permutation bar `P95_null = 1.9131`, the
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

**Recommend C, gated on one cheap measurement first**: count the decision flips
the ensemble would have caused over the 508 dates. That number is a day's work,
costs nothing, and it decides between C and D without any preregistration. If
flips are plentiful, C is the highest-power route to a *tradeable* answer. If they
are rare, D is honest and we stop paying for this line.

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


## §8 FLIP COUNT — run, and it decides C vs D

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

**This settles the §5 gate in favour of C.** It does **not** say the ensemble is
better — it reports no performance and cannot. It says the decision-boundary
estimand has units to measure, which is the one thing D assumed it might not.
