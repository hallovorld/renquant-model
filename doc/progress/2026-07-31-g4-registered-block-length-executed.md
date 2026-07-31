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

## The registered verdict, applied

| geometry | crossing | n_blocks | size @ b=35 | z vs the 0.06 bar | **registered verdict** |
|---|---:|---:|---:|---:|---|
| **`L=60, gap=0`** — Phase-0's own | **1.00** | 8 | **0.0783** | **+4.30** | **NOT CALIBRATED** |
| `L=60, gap=60` | 0.00 | 4 | 0.0635 | +0.91 | **NOT CALIBRATED** |
| `L=30, gap=60` | 0.00 | 6 | 0.0678 | +1.95 | **NOT CALIBRATED** |
| `L=20, gap=60` | 0.00 | 7 | 0.0568 | −0.89 | **within the band** |

**So, by the rule registered before the number was seen:**

> **Phase-0's own geometry (`L = h = 60`, `gap = 0`, crossing 1.00) is NOT CALIBRATED,
> and no GOAL-4 member verdict may cite a block-`t` computed on it.**

That is not a close call: **+4.30 MC standard errors** above the bar, ~1.6× the nominal
rate. `L60 gap60` and `L30 gap60` also fail, though at +0.91 and +1.95 they are near the
boundary and a larger draw count could move them.

**Exactly one geometry survives:** `L = 20, gap = 60` at **0.0568** (−0.89 SE inside the
bar). It is the only one on which a block-`t` may be cited, and even it sits in the upper
half of the band.

## What this settles and what it does not

**Settles:** the instrument to use, if GOAL-4 ever computes a block-`t` — `L = 20`,
`gap = 60`, `b = 35`. And it retires the geometry the Phase-0 screen actually used.

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
