# GOAL-4: the frozen prereg executed — Phase-0's own geometry is NOT calibrated

**Date:** 2026-07-31 · `renquant-model` · GOAL-4 requirement (3)

model#144 registered the bootstrap block-length rule **before the answer was known**:
`b` = the first lag where the sample ACF crosses zero = **35**, with a pass band of
**[0.04, 0.06]** fixed in the same frozen document. model#144 merged; this executes it.

**The result is negative for the geometry that matters.**

## The registered number, and the band it must be read against

`[本次实测 2026-07-31, 4 000 draws, seed 20260731, MC standard error ≈ 0.0034 at p ≈ 0.05]`

| bootstrap `b` | `L60 gap0` | `L60 gap60` | `L30 gap60` | `L20 gap60` |
|---:|---:|---:|---:|---:|
| 20 | 0.0527 | 0.0580 | 0.0645 | 0.0638 |
| **35 — REGISTERED** | **0.0783** | **0.0635** | **0.0678** | **0.0568** |
| 40 | 0.0715 | 0.0597 | 0.0700 | 0.0590 |
| 60 | 0.0798 | 0.0688 | 0.0688 | 0.0560 |
| 90 | 0.0710 | 0.0650 | 0.0717 | 0.0478 |
| 120 | 0.0500 | 0.0643 | 0.0437 | 0.0420 |

The band is reported beside the registered value because §4 of the prereg requires it —
**the registered cell never replaces the band.**

**Harness control unchanged:** i.i.d. Normal series, same procedure → **0.0490**
(`L60 gap0`) and **0.0542** (`L20 gap60`). The machinery is right; what follows is the
data's dependence.

## The registered verdict, applied — with the Monte Carlo uncertainty it needs

**Corrected after codex on model#145.** The first version of this section compared point
estimates to the 0.06 bar and licensed one geometry. **That was wrong in both
directions**, and the licensing direction is the dangerous one.

At 4 000 draws the MC standard error is ~0.0037–0.0042. A **one-sided 95% bound**
(`p ± 1.645·SE`) is what the comparison actually supports:

| geometry | crossing | size @ b=35 | SE | one-sided 95% band | **verdict** |
|---|---:|---:|---:|---|---|
| **`L=60, gap=0`** — Phase-0's own | **1.00** | 0.0783 | 0.0042 | [0.0714, 0.0853] | **NOT CALIBRATED** — bound excludes 0.06 |
| `L=30, gap=60` | 0.00 | 0.0678 | 0.0040 | [0.0612, 0.0743] | **NOT CALIBRATED** — bound excludes 0.06 |
| `L=60, gap=60` | 0.00 | 0.0635 | 0.0039 | [0.0571, **0.0698**] | **INCONCLUSIVE** — straddles 0.06 |
| `L=20, gap=60` | 0.00 | 0.0568 | 0.0037 | [0.0507, **0.0628**] | **INCONCLUSIVE** — straddles 0.06 |

> **NO GEOMETRY IS LICENSED.** Two fail decisively; two are inconclusive at this draw
> count. **`L = 20, gap = 60` is NOT calibrated** — its point estimate sits **less than
> one MC standard error inside the bar**, and a one-sided 95% upper bound of **0.0628
> exceeds 0.06**.

**What the prereg did and did not authorise.** §4 registered what to report when a point
estimate falls **outside** the band. It registered **no precision rule**, so it cannot be
read as licensing an estimate that is marginally inside. Treating 0.0568 as calibration
was me supplying a decision rule after seeing the number — the exact move the whole
registration exists to prevent, committed in the document that executes it.

**Symmetrically:** my first version also called `L=60, gap=60` (0.0635) *"NOT
CALIBRATED"*. On the same standard that is **inconclusive** too. Codex flagged only the
licensing direction; the same bar applies to the negative one, and both are corrected.

**What would resolve the two inconclusive cases**, stated so it cannot be chosen after
the fact: a **pre-specified** precision rule and draw count. At `p ≈ 0.0568`, a one-sided
95% upper bound falls below 0.06 only at **B ≥ ~25 000** `[推导]` (B=10 000 still gives
0.0606). **That run is NOT performed here** — choosing a sample size after seeing which
way an estimate leans is sample-size-after-peeking, and it would need its own frozen
amendment first.

## What this settles and what it does not

**Settles:** that **Phase-0's own geometry is not usable** — `L = h = 60`, `gap = 0`,
crossing 1.00, size bound excluding 0.06. That retirement is decisive and is the finding.

**Does NOT settle: which geometry to use instead.** Two candidates are inconclusive at
this draw count and **none is licensed**.

**Does NOT settle:** any member verdict. No member's `t` is recomputed here, and the
model#136 freeze rests on prior discipline — *the premise is unmeasured* — not on any
size number. Requirements **(2)** paired by-date resampling and **(4)** geometry
declaration remain open; this closes only **(3)**, and only for one geometry.

**Does NOT claim** `b = 35` is the right block length. The band is still wide
(0.0500–0.0798 on `L60 gap0`). What the prereg bought is that **35 was chosen before this
table existed**, so the cell that decides the verdict was not selected to produce it.

## Reproduce

```
python3 tools/g4_null_size_study.py \
    --series doc/research/evidence/2026-07-31-g4-null-calibration/per_date_g_real_copy.csv \
    --draws 4000 --seed 20260731 \
    --out doc/research/evidence/2026-07-31-g4-null-calibration/size_study_b35.json
```
