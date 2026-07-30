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

| | approach | dependence validity | blocks / dropped | critical value | MDE |
|---|---|---|---:|---|---|
| **A** | gap-separated blocks, `L = 120`, `gap = 120` | **valid** — `gap >= h`, so no block's label window reaches the next | **4** / 122d | `max(P95_null, t(.975, 3) = 3.1824)` | must be measured; almost certainly too coarse to conclude |
| **B** | HAC / Newey–West on the per-date series | **valid only once specified** — see §3.2 | n/a (uses all 1 082 dates) | **`P95` of `\|t_HAC\|` under within-date permutation.** No Student bar. | must be measured by the same calibration |
| **C′** | `h = 20`, gap-separated, `L = 60`, `gap = 20` | **valid** — `gap >= h` | **13** / 42d | `max(P95_null, t(.975, 12) = 2.1788)` | must be measured |
| **C″** | `h = 20`, gap-separated, `L = 40`, `gap = 20` | **valid** — `gap >= h` | **18** / 2d | `max(P95_null, t(.975, 17) = 2.1098)` | must be measured |
| **D** | wait for post-2021 data to leave the burned region | n/a | grows | — | zero today |

`C′` and `C″` trade block length against block count on the same window; both remain a
**different question** from the 120-day hypothesis (§4), and that objection is
unaffected by fixing their arithmetic.

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

## §4 The real decision, and why it is not mine alone

**A and D need no argument** — A is underpowered by construction, D is a fallback not a
design.

The decision is **B versus C** (now `C′`/`C″`), and it is not a technical choice.
**Ordering note added at revision:** it cannot be *settled* until §3.2's calibration
runs, because until then `B` has no measured MDE and the comparison would be an
argument about method rather than about power. What follows is the framing of the
choice, not a claim that it can be closed today.

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
