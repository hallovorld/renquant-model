# GOAL-7 Stage 1 redesign — DESIGN FOR DISCUSSION, nothing frozen

**STATUS: NOT A PREREGISTRATION. Nothing here is frozen and no run may execute against
it.** This document exists to be argued with *before* it becomes a prereg. That ordering
is the point — see §0.

## §0 Why this document exists at all

Over the last day this line produced **44 prereg commits and 3 design commits**
`[VERIFIED — git log origin/main --since=20h, grep -c prereg vs design]`. I have been
**freezing designs at roughly 15:1 over discussing them**, and the result is a queue of
preregistrations that were correctly rejected one after another — for a threshold that was
adjustable, a control that could not fire, a plausibility bound with no source, a holdout
that was contaminated, and finally an inferential unit that was invalid.

Every one of those was a **design** error caught at **review of a frozen artifact**. A
freeze is the wrong place to discover a design is wrong: by then the only options are
amend-in-place (which I did, repeatedly, and which re-opened defects as fast as it closed
them) or void.

**So this one gets reviewed as a design first.** No `§`-numbered decision rules, no
thresholds, no frozen text. Those come *after* the approach is agreed.

## §1 What actually broke, in one paragraph

Stage 1 asked whether a two-sided momentum statistic predicts a **forward 120-trading-day**
return. It chopped the timeline into **60-day blocks** and treated the 18 block averages as
18 independent pieces of evidence. They are not: each block's labels look 120 days ahead,
so **neighbouring blocks measure overlapping stretches of the same future**. The run's own
lag-1 autocorrelation of **0.94** was the symptom. Both arms are therefore uncomputed —
this is not evidence for the hypothesis *or* against it.

## §2 The constraint that no design escapes

The only uncontaminated window is **2016-12-29 → 2021-04-19, 1082 trading days**. Later
dates are burned: the U-shape that motivated the hypothesis was *observed* on
2021-10-08 onward, so testing there is marking my own homework.

With a 120-day forward label, `1082 / 120 ≈ 9.02` `[DERIVED — N/h]` is a **power
heuristic** — a rough sense of how much non-redundant information the window holds.
**It is not a degrees-of-freedom count, and no `t` bar may be taken from it.** The
first version of this document did exactly that and review rejected it; see §3.0.
**No estimator recovers information the overlap destroyed.** What a correct method
buys is not power; it is *not overstating* the power that exists.

I want that stated plainly at the top of the design rather than discovered again at review.

## §3 Four candidate designs

### §3.0 REVISION — the first version of this table embedded the error it was written to fix

Review (2026-07-30) rejected two of the four rows, correctly. Both are recorded here
rather than silently edited, because this is a recurring shape on this programme and
the pattern matters more than the fix:

- **Row B claimed `~9` independent-equivalent observations and a `t` bar of `2.3060`.**
  Both came from `N / h = 9.02` used as a **degrees-of-freedom count**. HAC does not
  convert 1 082 serially dependent dates into 9 independent ones. It corrects the
  **variance**; it says nothing about the reference distribution. The `2.3060` was a
  borrowed constant with no derivation behind it.
- **Row C claimed `~18` observations and `2.1098` from `h = 20` in contiguous 60-day
  blocks.** Crossing fraction `min(1, h/L) = 20/60 =` **0.3333** `[DERIVED]` — one
  third of each block's labels reach into the next block. The blocks are not
  independent, so no Student bar over them is justified.

An uncomfortable detail worth stating: a **valid** `h = 20` design does exist that
yields *exactly* `2.1098` — `L = 40` with a `20`-day gap gives 18 blocks, `df = 17`
`[DERIVED — 1082 // 60 = 18]`. So the number in the rejected row was right by
coincidence and wrong by derivation. That is precisely why a bar must be re-derived
from the realised geometry rather than recognised.

### §3.1 The revised candidates

Two columns replace "independent-equivalent obs" and "`t` bar": what makes the design
**dependence-valid**, and where its **critical value** comes from. Every block count
below is `N // (L + gap)` at `N = 1082`, remainder dropped
`[DERIVED — integer arithmetic, this document]`.

| | approach | dependence validity | blocks / dropped | critical value | MDE (`σ_x`) |
|---|---|---|---:|---|---:|
| **A** | gap-separated blocks, `L = 120`, `gap = 120` | **valid** — `gap >= h`, so no block's label window reaches the next | **4** / 122d | `max(P95_null, t(.975, 3) = 3.1824)` → **3.2004** | **1.714** |
| **B** | HAC / Newey–West on the per-date series | **valid only once specified** — see §3.2 | n/a (uses all 1 082 dates) | **`P95` of `\|t_HAC\|` under within-date permutation** → **3.0173**. No Student bar. | **0.995** |
| **C′** | `h = 20`, gap-separated, `L = 60`, `gap = 20` | **valid** — `gap >= h` | **13** / 42d | `max(P95_null, t(.975, 12) = 2.1788)` → **2.1801** | **0.447** |
| **C″** | `h = 20`, gap-separated, `L = 40`, `gap = 20` | **valid** — `gap >= h` | **18** / 2d | `max(P95_null, t(.975, 17) = 2.1098)` → **2.1564** | **0.447** |
| **D** | wait for post-2021 data to leave the burned region | n/a | grows | — | zero today |

`[VERIFIED — python3 tools/goal7_design_mde.py --reps-null 8000 --reps-power 4000
--executed --sensitivity, this branch; log + JSON in
doc/research/data/2026-07-30-goal7-design-mde/]`

**Units.** `σ_x` is the per-date statistic's own standard deviation. Converting an MDE
into an economically meaningful number needs `σ_x` from a **clean** run, and no clean run
exists — the only one that produced it is void. In `σ_x` units the comparison review
asked for is exact and leans on nothing that has been retracted.

`C′` and `C″` trade block length against block count on the same window; both remain a
**different question** from the 120-day hypothesis (§4), and that objection is
unaffected by fixing their arithmetic.

### §3.1a Two measured facts that change the decision

**1 — the gap-separated designs need no rescue.** Their plain Student bars are already
correctly sized: realised false-positive rate **0.0473 / 0.0508 / 0.0495** for A / C′ / C″
against a nominal 0.05. That is the first *measured* confirmation that `gap >= h` does
what §3.1 claims of it. Until now that was an assertion.

**2 — B is the design that genuinely needed its permutation bar, and it is still NOT the
most powerful.** A naive `|t_HAC| > 1.96` rejects **17.9%** of the time under the null —
3.6× nominal — so §3.2 item 3 was right and now has a number. The calibrated bar
(**3.0173**) restores size to 0.050. But using all 1 082 dates buys **less** power than 18
gap-separated 40-day blocks: **0.995 vs 0.447 `σ_x`**. The information the overlap
destroyed is not recoverable by a better estimator, exactly as §2 said — and the price of
asking the 120-day question is now measured rather than argued.

**A is close to unusable**: MDE **1.714 `σ_x`** on 4 blocks.

**Sensitivity.** The `h = 20` rows carry the overlap/idiosyncratic variance ratio over from
the measured `h = 120` value (`ρ₁ = 0.94 ⇒ c² = 0.9479`); there is no measured `ρ₁` at
`h = 20`, and that carry-over is an **assumption**. Across `c² ∈ {0.80, 0.9479, 0.99}` the
MDEs move A `1.617 → 1.813`, B `0.932 → 1.019`, C′ `0.416 → 0.454`, C″ `0.407 → 0.461`
`[VERIFIED — same run, --sensitivity]`. **The ordering A ≫ B ≫ C holds across the whole
band**, so the assumption does not drive the comparison it feeds.

### §3.1b What the executed designs actually cost, measured

The same harness pointed at the geometries this programme really ran, at the bars those
runs really used `[VERIFIED — same run, --executed]`:

| study | `h` | `L` | gap | crossing | blocks | bar used | **realised size** |
|---|---:|---:|---:|---:|---:|---:|---:|
| GOAL-7 Stage 1 as executed | 120 | 60 | 0 | 1.000 | 18 | 2.1098 | **0.2162** |
| momentum total-return as executed | 120 | 120 | 0 | 1.000 | 9 | 2.3060 | **0.1034** |
| GOAL-4 Phase-0 ensemble screen | 60 | 60 | 0 | 1.000 | 18 | 2.1098 | **0.1070** |
| C row rejected at review | 20 | 60 | 0 | 0.333 | 18 | 2.1098 | **0.0615** |
| repaired: A / C′ / C″ | — | — | ≥ `h` | 0.000 | 4 / 13 / 18 | own | **0.047 / 0.051 / 0.050** |

Two things follow that were previously only argued:

1. **Crossing 1.00 is worth a 2×–4.3× inflation of the false-positive rate**, not a
   rounding error. Stage 1's own bar was a **21.6%** test, not a 5% one.
2. **Crossing fraction is not a severity ranking.** The rejected `C` row crosses only
   0.333 and costs **0.0615** — inflated, but nowhere near the others. The review was
   right to reject it, *and* the erratum's three-study table must not be read as three
   equally damaged studies: Stage 1 is far the worst, because it combined full crossing
   with the **largest** block count.

Note that `crossing = min(1, h/L)` as published is the `gap = 0` special case. With a gap
it is `min(1, max(0, h − gap)/L)` — which is why the repaired rows read 0.000 and not the
value their `L` alone would suggest.

### §3.2 What Option B must specify before it is a design at all

The review's demand, restated as the checklist a prereg would have to satisfy:

1. **Estimator and kernel** — Newey–West with the Bartlett kernel, stated explicitly.
2. **Bandwidth** — a registered rule, not a run-time choice. The overlap is `h = 120`,
   so the bandwidth must be **at least** 120; whether it is exactly `h`, `h + 1`, or an
   automatic rule (Newey–West 1994, Andrews 1991) is a decision this review should make,
   because a bandwidth chosen after seeing the series is a researcher degree of freedom.
3. **Reference distribution — the part that was missing.** `t_HAC` is compared to `P95`
   of `|t_HAC|` computed through the **identical** harness on **≥ 200 within-date
   permutations** of the score. Exact for the harness, assumes no distribution, and
   absorbs both the realised overlap and any residual serial dependence the bandwidth
   failed to capture. Same construction already registered for GOAL-4
   (`T_crit = max(P95_null, t(.975, n−1))`) — here the Student leg **drops out**,
   because there is no legitimate `df` to take it from.
4. **MDE, measured not asserted** — inject a known effect of size `g` through the same
   harness and report the smallest `g` the calibrated bar detects. Without this number
   `B` cannot be compared to `A`, `C′` or `C″` at all, and a verdict of "cannot tell"
   would be unattributable between *no effect* and *no power*.

**Consequence for the decision:** `B` cannot be scored against `C` until items 2–4 are
run. That is a small calibration job on already-committed data, and it should happen
**before** this PR is settled rather than inside a frozen prereg.

> **STATUS at revision 2: items 2–4 have now been run** — `tools/goal7_design_mde.py`,
> results in §3.1/§3.1a/§3.1b. Item 2 (bandwidth) was executed at **`M = h = 120`**;
> that is a *choice this document makes and review should confirm or replace*, not a
> settled registration. Items 3 and 4 are measured. One thing the calibration does
> **not** discharge: it is a calibration of the *harness geometry*, run on a simulated
> per-date series whose dependence is pinned by the one measured input `ρ₁ = 0.94`. It
> is not a run of the hypothesis and touches no score, label or panel.

## §4 The real decision, and why it is not mine alone

**A and D need no argument** — A is underpowered by construction, D is a fallback not a
design.

The decision is **B versus C** (now `C′`/`C″`), and it is not a technical choice.
**Ordering note added at revision:** it cannot be *settled* until §3.2's calibration
runs, because until then `B` has no measured MDE and the comparison would be an
argument about method rather than about power. What follows is the framing of the
choice, not a claim that it can be closed today.

**Revision 2 — the calibration has run, and it did not settle the question; it priced
it.** `B` needs **0.995 `σ_x`** where `C″` needs **0.447 `σ_x`** — asking the original 120-day
question costs a factor of **2.2× in detectable effect** `[VERIFIED — §3.1]`. That is
the size of the temptation to switch horizons, stated as a number instead of a feeling,
and it is *precisely why* the switch has to be justified on its own terms rather than
taken because it is easier. The measurement does not weaken the §4 objection to `C`; it
quantifies what refusing `C` costs. My recommendation below is unchanged.

- **B tests the hypothesis that was actually raised**, at whatever power the honest window
  supports. Likely outcome: *"cannot tell"*. That is a real answer and it is cheap.
- **C tests a different hypothesis** — that the two-sided pattern exists at a **20-day**
  horizon. It would have far more statistical grip. But the U-shape was observed at
  **120 days**, so asking about 20 days after seeing the 120-day picture is a **horizon
  search** (the template's T6). It is only legitimate if registered as a *new, independent*
  question with its own justification for why 20 days is interesting on its own terms —
  **not** as a rescue of the 120-day result.

**My recommendation: B, and if B returns "cannot tell", say so and stop.** Then C becomes
available later as a genuinely separate question rather than a consolation prize.

But I am putting both on the table because **C is the option that could actually produce a
usable model**, and I do not think I should quietly discard it because it is harder to
justify. If C is wanted, the honest route is to design it as its own question, and I will
write that design.

## §5 What I am asking review to settle

1. **B or C** — test the original question honestly at low power, or register the
   short-horizon question properly as its own thing?
2. **Is `~9` observations worth spending a cycle on at all**, or is the useful move to run
   B once, get the likely *"cannot tell"*, and let that be the recorded state?
3. **Anything in §3 I have mis-stated.** The point of a design PR is that this is cheap to
   correct here and expensive to correct after a freeze.

## §6 What this design does NOT do

- It does not touch the dividend-adjusted total-return series, which is validated and
  stands independently (ex-dividend gap −66.6bp → −4.8bp).
- It does not re-block, re-run, or re-analyse the voided execution. Those numbers have been
  seen; changing the estimator on them now is exactly the post-hoc move a freeze exists to
  prevent.
- It licenses nothing. No scorer, no shadow deployment, no capital, and no factor budget is
  spent by agreeing an approach.
