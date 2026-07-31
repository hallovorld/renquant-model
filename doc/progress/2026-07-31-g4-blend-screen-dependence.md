# GOAL-4: the blend screen's advantage does not survive a dependence-aware bar

**Bottom line.** The 2026-07-25 blend construction screen reports `diff_mean = +0.0627`
over 2 161 dates. A naive t on that series is **+6.19**. Under every gap-honest block
geometry it is **~1.5**, and after winsorization **~0.95**. Its published verdict —
**INCONCLUSIVE** — is **upheld**, and this says precisely why.

## The bar, by geometry `[本次实测 2026-07-31]`

Label horizon **h = 60d** (the bundle quotes both spreads "/60d" and the prereg fixes a
60d embargo), so crossing is `min(1, h/L)`.

| series | L | blocks | block t | Student bar | crossing | resolves |
|---|---:|---:|---:|---:|---:|:--|
| diff | 20 | 108 | **2.08** | 1.982 | **1.00** | *"yes"* |
| diff | 60 | 36 | 1.47 | 2.030 | 1.00 | no |
| diff | 90 | 24 | 1.51 | 2.069 | 0.67 | no |
| diff | 120 | 18 | 1.46 | 2.110 | 0.50 | no |
| diff | 250 | 8 | 1.35 | 2.365 | 0.24 | no |
| winsorized | 20…250 | — | **0.93–1.31** | — | — | **no, anywhere** |

**The single row that "resolves" is the least trustworthy one.** `L = 20 < h = 60`
gives crossing **1.00** — the maximum label overlap — over the largest block count. A
Student bar there is not calibrated. Independence needs a **gap ≥ h**, not a block
*shorter* than `h`.

## Why the naive t was so large

`ρ₁` of the diff series is **+0.5799**. Naive-to-block ratio at L=60 is
**6.19 / 1.47 = 4.2×**. Nothing about the effect changed; the naive t was counting
2 161 dates as 2 161 independent observations when the labels overlap 60 days.

## The second finding: it is a tail effect

```
diff_mean            = +0.062650
winsorized (w50)     = +0.009573      ->  84.7% of the advantage is in the tails
```

The blend's edge over `rank60` is **85% tail-driven**. And the two arms correlate
**ρ = 0.831** day to day — they are not independent views of the panel, which is the
condition an ensemble needs to buy anything.

## What this does to GOAL-4's premise

Earlier tonight I corrected the Phase-0 power claim from a *47×* wall to **0.91×**
(model#132) — *"marginally powered, not hopeless."* That correction stands, and this
result sits beside it without contradiction:

> The screen that showed a blend advantage does **not** clear a correct bar, and the
> advantage it did show is tail-concentrated between two arms correlating 0.83. The
> ensemble premise is **not refuted** — it is **unmeasured**, and the existing evidence
> does not move it.

**Not claimed:** that the blend is worse. `+0.0627` with a block t of 1.5 is an
un-resolved positive, not a negative.

Tests: 6, pinned to a frozen summary + per-geometry CSV.
