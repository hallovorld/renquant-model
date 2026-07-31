# PREREG (FROZEN): the bootstrap block-length rule for GOAL-4's null

**Date:** 2026-07-31 · `renquant-model` · GOAL-4 requirement (1)

model#136 requires, before any calibrated null can mean anything, *"a null-generating
mechanism, **stated in advance**"*. model#143 then measured why that is not pedantry: the
realised size of the Phase-0 block-`t` procedure moves from **0.049 to 0.078** purely
with the bootstrap block length, on the same data and the same geometry.

**This document registers that choice before it is used, and it is frozen on merge.**

## Disclosure, stated first because it is the main threat to this document

**I have already seen the sensitivity table.** model#143 published sizes at bootstrap
block lengths 20 / 40 / 60 / 90 / 120. A rule chosen after seeing which lengths give
which answers can be steered — not by dishonesty, but by finding the justification that
lands where one wants. Three guards, all binding:

1. The rule below is a **window-free functional of the sample ACF**, computable without
   reference to any size result.
2. **The size at the registered block length has NOT been computed.** 35 is not one of the
   five lengths measured in model#143, and this document is committed before running it.
3. The **full sensitivity band is reported regardless** of what the registered rule
   yields (§4). The registered value is the headline; the band is not optional.

## 1. The series

`[本次实测 2026-07-31, per_date_g_real.csv, N = 508]`

| | |
|---|---:|
| `ρ₁` | **0.7331** |
| `ρ₅` | 0.5785 |
| `ρ₂₀` | 0.2104 |
| `ρ₆₀` | −0.2290 |
| first lag with `ρ ≤ 1/e` | **13** |
| **first lag where `ρ` crosses zero** | **35** |

## 2. The rule that was CONSIDERED AND REJECTED — and why it matters

The textbook choice is a multiple of the **integrated autocorrelation time**
`τ_int = 1 + 2Σρ_k`. It is rejected here because **`τ_int` is itself not identified on
this series** — it depends on the summation window:

| window `M` | 10 | 20 | 30 | 40 | 60 | automatic (`M ≥ 5τ`) |
|---|---:|---:|---:|---:|---:|---:|
| `τ_int` | 12.84 | 18.95 | **21.17** | 20.99 | 12.71 | 11.86 |

**A τ-based rule would move the arbitrariness from "pick a block length" to "pick a
window", not remove it** — the same non-identification model#143 found, one level down.
Recording this is the point: the obvious principled answer does not work here.

## 3. THE REGISTERED RULE

> **Bootstrap block length `b` = the first lag at which the sample autocorrelation of the
> per-date series crosses zero.**
>
> For this series that is **`b = 35`** `[本次实测 2026-07-31]`.

**Why this functional.** Beyond the first zero crossing the sample ACF no longer
indicates positive dependence, so blocks of that length span the positively-dependent
range and resampling them preserves it. It is a **single integer determined by the
series**, with no window, threshold or tuning constant — which is exactly the property
`τ_int` lacks.

**Its known weakness, stated rather than hidden:** the first zero crossing of a *sample*
ACF is itself noisy at `N = 508`, and this rule does not quantify that. It is chosen for
being **pre-committable and non-tunable**, not for being optimal.

## 4. What must be reported, whatever the answer

1. The realised size at **`b = 35`**, at every geometry model#143 tested.
2. The **full sensitivity band** across `b ∈ {20, 40, 60, 90, 120}` beside it — the
   registered value never replaces the band.
3. The **i.i.d. harness control** (model#143: 0.0490 / 0.0542), so a miscalibration
   reading can be distinguished from a broken harness.
4. If the size at `b = 35` falls outside **[0.04, 0.06]**, the procedure is reported as
   **NOT calibrated at this geometry**, and no member verdict may cite a block-`t`.
   *This threshold is registered here, before the number is known.*

## 5. What this does NOT do

It does not satisfy requirements (2) or (4) of model#136 — paired by-date resampling and
the geometry declaration are separate obligations. It does not license any GOAL-4 member
verdict: the freeze in model#136 rests on prior discipline, not on any size number. And
it does not claim `b = 35` is correct — only that it was **chosen before the answer was
seen**, which is the whole of what a preregistered choice buys.
