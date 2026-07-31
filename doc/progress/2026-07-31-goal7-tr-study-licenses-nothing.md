# GOAL-7: the frozen RULE returns UNRESOLVED — and that is a rule output, not a verdict

**Bottom line — SEPARATED 2026-07-31 after codex on #135.** Two different things were
run together here and only one of them is supportable today.

**(a) The frozen preregistered rule output — deterministic, reportable as-is.**
`beats_baseline_holm: False`, and the registered verdict string is
`UNRESOLVED / TILT-NOT-EXCLUDED — Nothing licensed.` That is what the rule returns on
the frozen inputs. It is a **rule output**, not an evidential conclusion.

**(b) What I additionally claimed, and now defer.**

| claim | why it is deferred |
|---|---|
| *"removing the dividend tilt made momentum WORSE"* | a **causal** reading of four deltas whose own t are **−1.74 / −1.35 / −0.97 / −0.79** — not one clears any bar, and all sit on `gap = 0` geometry |
| *"the study licenses nothing"* as an **evidential verdict** | it is the frozen rule's output. Treating it as evidence about momentum requires the E2 inference to be calibrated, and it is not: `gap = 0`, realised size **0.1034** |
| any conclusion resting on the TR series being confound-free | **#133** narrowed that to *internal construction verified*; the external adjuster check never ran |

**Deferred pending:** a valid external source validation (#133) and a dependence-aware
calibration at `gap ≥ h` (#134, #137). Neither exists today.

## Four gates; three pass; the fourth is the one that matters

| gate | value |
|---|:--|
| `placebos_clean` | True |
| `false_flag_rate_ok` | True (rate **0.025** over 40 draws) |
| `three_views_agree` | True |
| **`beats_baseline_holm`** | **False** |

The momentum arm **does not beat a naive dividend-yield sort** under the paired
Holm-corrected contrast. Paired subject-minus-baseline: mean **+0.3455**, **t = 1.682**.

## The TR-minus-price deltas — reported, NOT interpreted

| h | TR | price | Δ (TR − px) | t |
|---:|---:|---:|---:|---:|
| 20 | 0.2058 | 0.2134 | **−0.0075** | −1.74 |
| 60 | 0.3022 | 0.3110 | **−0.0088** | −1.35 |
| 120 | 0.4310 | 0.4417 | **−0.0107** | −0.97 |
| 250 | 0.4885 | 0.4988 | **−0.0103** | −0.79 |

> **NOT claimed: that the tilt was contributing.** All four deltas are negative and
> all four are **un-adjudicated** (|t| ≤ 1.74, on `gap = 0` geometry with no calibrated
> null). What can be said is only the arithmetic: **the TR series does not score higher
> than the price series in this run, at any of the four horizons.**
>
> The §3 reminder said a positive could not be attributed to momentum rather than to a
> dividend-yield tilt. That reminder is **not discharged** by these numbers. An earlier
> version of this paragraph said *"take the tilt away and the number goes down"* and
> that *"what remains cannot outrun a dividend-yield sort"* — both **withdrawn**
> (codex on model#135). The first is causal: it attributes the sign of a delta to the
> removal, when the delta is a difference between two runs on two price series and no
> arm was randomised. The second reads `t = 1.682` — an **un-resolved positive** — as a
> settled negative.

## The two views disagree — as frozen rule inputs

`E2` (top-decile spread) has block `t = 3.767`; `E1` (rank IC) has **t = 0.589**. The
registered rule consumed both, and `E2` satisfied its `resolves` predicate while `E1`
did not. A spread that moves while the rank correlation does not is a statement about
the **tail**, not about the panel.

> **`resolves` is not significance, and this document previously read it as if it were**
> (codex on model#135; the predicate itself is documented on model#137).
> `DependenceAwareResult.resolves` requires the bootstrap CI, the LOBO bounds and the
> block-`t` to **agree in sign**. It never compares the block-`t` magnitude to any
> critical value. So *"E2 resolves at t = 3.767"* states sign agreement — **not** that
> 3.767 cleared anything.

## And the strong-looking half is weaker than it reads

`n_blocks_primary = 10` at `L = h = 120` ⇒ crossing `min(1, h/L)` = **1.00**, the
**maximum** label overlap — every block shares its label window with its neighbour.
The realised size at that geometry was measured at **0.1034** against a nominal 0.05 —
roughly **2× over-rejection**.

An earlier version of this section said the Student bar is `t(9) ≈ 2.262` and that
**"3.767 clears even that"**. **Withdrawn.** `t(n−1)` is the correct bar only if the
block means are i.i.d. Normal; at crossing 1.00 they demonstrably are not, which is
precisely what the measured 0.1034 shows. Comparing 3.767 to 2.262 substitutes a
reference threshold for a calibrated one and reads the result in the flattering
direction — the same asymmetry corrected on model#136. **3.767 is a descriptive
statistic on a geometry with no valid null. It is neither cleared nor rejected.**

**And it cannot be recalibrated from the bundle**, because this run did **not persist
its per-date series** — the omission `model#131` fixes.

## What GOAL-7 should conclude — a RULE outcome, not an evidential verdict

**The study licenses no deployment.** That conclusion is available without any
calibrated inference, and it is the only one claimed here: the decision rule was frozen
before the run, the run produced its inputs, the rule was applied, and it returned
`UNRESOLVED / TILT-NOT-EXCLUDED — nothing licensed`. Applying a preregistered rule is a
**procedure**, and it is valid whether or not the statistics it consumed can support
inference. That is what preregistration is for.

What this document **does not** claim, and previously did:

| withdrawn phrasing | why |
|---|---|
| *"a standalone momentum model is **not supported** by this evidence"* | an inferential claim against the model. The rule declined to license; that is not the same as evidence against |
| *"the dividend confound is real and, once removed, the signal is **smaller**"* | causal, and the four deltas have `t` = **−1.74 / −1.35 / −0.97 / −0.79** on `gap = 0` geometry — none adjudicated |
| *"what survives **does not beat** the naive dividend-yield baseline"* | the paired contrast is `t = 1.682`, an **un-resolved positive**; "does not beat" reads it as a settled negative |
| *"only the tail view **resolves**"* | true as sign agreement, misleading as significance — see the `resolves` note above |

**Not claimed:** that momentum is dead on this panel, or alive on it. `UNRESOLVED` is
neither `REFUTED` nor `CONFIRMED`. The measured quantities are **descriptive
statistics on geometries with no valid null**, and they stay that way until a
dependence-preserving calibration on a `gap ≥ h` geometry exists.

**What would change the conclusion:** not a bigger `t`. A `gap ≥ h` re-run that
persists its per-date series (`model#131`), plus a bootstrap null from those rows.
Until then GOAL-7's status is *unmeasured*, which is a different lane state from
*negative* and implies different next work.

Tests: 6 — the frozen verdict string, the two-view disagreement as rule inputs, the
four negative Δ as descriptive values, the crossing caveat, and two regressions holding
the withdrawn causal and inferential phrasings out.
