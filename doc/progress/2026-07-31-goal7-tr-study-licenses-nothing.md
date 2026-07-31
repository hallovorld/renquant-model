# GOAL-7's own frozen study does not license a standalone momentum model

**Bottom line.** The dividend blocker is **discharged** — but discharging it made the
signal *slightly worse*, and the arm then **fails its own preregistered baseline
contrast**. The frozen verdict is `UNRESOLVED / TILT-NOT-EXCLUDED — Nothing licensed.`
`[早前实测 2026-07-30 bundle, read and decomposed 本次实测 2026-07-31]`

## Four gates; three pass; the fourth is the one that matters

| gate | value |
|---|:--|
| `placebos_clean` | True |
| `false_flag_rate_ok` | True (rate **0.025** over 40 draws) |
| `three_views_agree` | True |
| **`beats_baseline_holm`** | **False** |

The momentum arm **does not beat a naive dividend-yield sort** under the paired
Holm-corrected contrast. Paired subject-minus-baseline: mean **+0.3455**, **t = 1.682**.

## Removing the dividend tilt made momentum WORSE, at every horizon

| h | TR | price | Δ (TR − px) | t |
|---:|---:|---:|---:|---:|
| 20 | 0.2058 | 0.2134 | **−0.0075** | −1.74 |
| 60 | 0.3022 | 0.3110 | **−0.0088** | −1.35 |
| 120 | 0.4310 | 0.4417 | **−0.0107** | −0.97 |
| 250 | 0.4885 | 0.4988 | **−0.0103** | −0.79 |

> **The dividend tilt was contributing to the price-based edge, not masking it.** The
> §3 reminder said a positive could not be attributed to momentum rather than to a
> dividend-yield tilt. Measured on total-return prices, the answer is the
> uncomfortable one: take the tilt away and the number goes **down** at all four
> horizons, and what remains cannot outrun a dividend-yield sort.

## The two views disagree

`E2` (top-decile spread) resolves at **t = 3.767**. `E1` (rank IC) does **not**:
**t = 0.589**. A spread that moves while the rank correlation does not is a statement
about the **tail**, not about the panel.

## And the strong-looking half is weaker than it reads

`n_blocks_primary = 10` at `L = h = 120` ⇒ crossing `min(1, h/L)` = **1.00**, the
maximum label overlap. The realised size at that geometry was measured at **0.1034**
against a nominal 0.05 — roughly **2× over-rejection**. With 10 blocks the correct
Student bar is `t(9) ≈ 2.262`, not 1.96; **3.767 clears even that**, so this does not
overturn the E2 result — it means "clears the bar" was never as strong as the number
suggests.

**And it cannot be recalibrated from the bundle**, because this run did **not persist
its per-date series**. That is exactly the omission `model#131` fixes — the value of
that PR is now concrete rather than hypothetical.

## What GOAL-7 should conclude

Its own frozen, preregistered study says **nothing is licensed**. A standalone
momentum model deployed to shadow is **not supported** by this evidence:

- the dividend confound is real and, once removed, the signal is smaller;
- what survives does not beat the naive dividend-yield baseline;
- only the tail view resolves, and on an uncalibrated geometry.

**Not claimed:** that momentum is dead on this panel. `UNRESOLVED` is not `REFUTED`,
and the paired contrast at `t = 1.682` is an un-resolved positive. What is claimed is
that **this study licenses no deployment**, which is what its own verdict string says.

Tests: 4, pinning the verdict, the two-view disagreement, the negative Δ at all four
horizons, and the crossing caveat.
