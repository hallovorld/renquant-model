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

With a 120-day forward label, that window contains roughly **`1082 / 120 ≈ 9`
independent-equivalent observations** — no matter which method is used
`[DERIVED — N/h]`. **No estimator recovers information the overlap destroyed.** What a
correct method buys is not power; it is *not overstating* the power that exists.

I want that stated plainly at the top of the design rather than discovered again at review.

## §3 Four candidate designs

| | approach | independent-equivalent obs | `t` bar | honest assessment |
|---|---|---:|---:|---|
| **A** | gap-separated blocks (120 block + 120 gap) | **~4** | 3.1824 | genuinely independent, and almost certainly too few to conclude anything |
| **B** | **HAC / Newey-West on the per-date series, lag ≥ 120** | **~9** | 2.3060 | the textbook treatment for overlapping forward returns. Uses every date rather than discarding into blocks. **This is what I should have written the first time.** |
| **C** | shorter horizon (`h = 20`), 60-day blocks | **~18** | 2.1098 | far more information from the same window — **but it is a different question** |
| **D** | wait for post-2021 data to age out of the burned region | 0 today, grows | — | costs nothing now, delivers nothing now |

## §4 The real decision, and why it is not mine alone

**A and D need no argument** — A is underpowered by construction, D is a fallback not a
design.

The decision is **B versus C**, and it is not a technical choice:

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
