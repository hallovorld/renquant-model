# ERRATUM — `block_length = h` was registered as the REMEDY for label overlap. It is the defect.

**Date:** 2026-07-30 · GOAL-7 · `renquant-model`
**Applies to:** `doc/research/2026-07-30-momentum-total-return-prereg.md` (frozen,
merged) and the results it licensed in `doc/progress/2026-07-30-momentum-total-return.md`
(merged, model#110).
**Nothing is licensed by this document.** It withdraws support from an inference; it
does not create one.

---

## 1. Bottom line

The frozen prereg's threat table answers **T2 — "naive per-date `t` on overlapping
labels"** with:

> `dependence_aware_mean`, **`block_length = h = 120`** = the label overlap; block
> `t` + bootstrap `[VERIFIED — prereg line 25, restated at line 275]`

Setting the block length **equal to** the label horizon does not remove the overlap.
It produces the **maximum** of it. Crossing fraction is
`min(1, h/L) = 120/120 =` **1.00** `[DERIVED]`: block *i* covers dates `[iL, (i+1)L)`,
its labels reach to `(i+1)L − 1 + h = (i+2)L − 1`, so **block *i*'s label window fully
covers block *i+1***. Consecutive block means are measuring overlapping stretches of
the same future, by construction, at every horizon.

So the registered remedy for T2 is T2.

## 2. What is NEW here, and what was already on the record

This matters, because a restated known defect is not a finding.

**Already recorded** — `2026-07-30-momentum-total-return.md` erratum item (2): *"selecting
the arm on block `t` was structurally biased because `block_length=h` makes the block
count fall ~12× as the horizon rises."* That is a **horizon-SELECTION** bias: maximising
`t` over horizons systematically prefers short ones. It was correctly identified and
the corrected registration fixed it by **declaring the horizon from theory**.

**Not recorded, and not fixed by declaring the horizon** — that at `L = h` the block
means are **not independent at ANY horizon**, including the declared one. Declaring the
horizon from theory removes the *selection* problem and leaves the *dependence* problem
untouched. The two defects share a symptom and have different remedies.

## 3. What this withdraws

`model#110`'s bottom line states the primary *"cleared every bar it owns"*, citing
**E2 = +0.4310 SD, block `t` = +3.767 on 10 blocks against a programme bar of 3.1019**
`[VERIFIED — model#110 body]`.

**That comparison is not established.** The 10 blocks are not 10 independent units, so
no critical value taken over them — 3.1019, `t(0.975, 9) = 2.2622`, or any other — is
supported. The point estimate stands as a description; the **inference** does not.

**No published verdict flips.** §6 returned `UNRESOLVED / TILT-NOT-EXCLUDED` with
nothing licensed, no model built, no shadow deployment and no capital action. This
erratum removes a *supporting* claim from a document whose conclusion was already the
conservative one. That is the only reason this is an erratum and not a retraction.

## 4. Third instance today. The pattern is the finding.

Measured this session `[VERIFIED — each document's own frozen text]`:

| study | block `L` | label `h` | crossing `min(1, h/L)` |
|---|---:|---:|---:|
| GOAL-7 Stage 1 | 60 | 120 | **1.00** |
| GOAL-4 Phase-0 ensemble screen | 60 | 60 | **1.00** |
| momentum total-return (this erratum) | 120 | 120 | **1.00** |

Three independently authored designs, three different programmes, one arithmetic
mistake — and in the third it is written down as the *fix* for the very threat it
creates. The intuition behind it is seductive and wrong: *"make the block as long as
the overlap, so the overlap fits inside one block."* The overlap does not fit inside
the block; it **starts** at the end of each date's own window and reaches `h` beyond
it, so a block of length `h` pushes exactly one full block's worth of label into its
neighbour.

**The rule that would have caught all three, stated once:**

> Independence requires a **gap of at least `h` between blocks**, not a block of
> length `h`. `L ≥ h` with contiguous blocks is not a condition on anything —
> crossing is `min(1, h/L)`, which is 1.00 whenever `L ≤ h` and only falls below 1
> when `L > h`, reaching a *residual*, never zero, without a gap.

## 5. What a corrected registration owes

Not proposed here — this document only withdraws. For the record, the same three
routes the GOAL-7 redesign discussion (model#128) is weighing apply:

1. **Gap-separated blocks**, `gap ≥ h`. Dependence-valid, costs blocks.
2. **A permutation-calibrated bar** through the identical harness, which absorbs
   whatever overlap remains — this is what rescued the GOAL-4 screen's *conclusion*
   even after its Student bar was withdrawn.
3. **A HAC estimator with a registered bandwidth and its own finite-sample
   calibration** — and explicitly **not** `N/h` used as degrees of freedom.

Whichever is chosen, the critical value must be **re-derived at the realised
geometry**, never recognised from a previous study.
