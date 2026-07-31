# GOAL-4 requirement (3): I tried to calibrate the null. It is not identified yet.

**Date:** 2026-07-31 · `renquant-model` · GOAL-4 Phase-0

model#136 (merged) lists four requirements for a validated dependence-preserving null.
This attempts **(3) — the empirical calibration target** — on GOAL-4's own 508-row
per-date series. **The attempt fails in an informative way, and that is the deliverable.**

## What was run

No-effect construction: the real series **minus its mean**, so the true mean is exactly
0 while the empirical dependence is retained. Draws: circular block bootstrap. Statistic:
block means with `gap` dropped between blocks, one-sample `t` vs `t(0.975, n_blocks−1)` —
exactly the Phase-0 prereg's rule (`n_blocks = floor(N_eval/60)`, `L = h = 60`, i.e.
**`gap = 0`, crossing `min(1, h/L) = 1.00`**). 4 000 draws, seed 20260731.

The series `[本次实测 2026-07-31]`: `N = 508`, mean **−0.008550**, sd **0.054846**,
`ρ₁ = +0.7321`, `ρ₅ = +0.5826`, `ρ₂₀ = +0.2136`, `ρ₆₀ = −0.2314`.

## The harness is right

Same procedure on an **i.i.d. Normal** series of the same length and sd:

| geometry | n_blocks | realised size |
|---|---:|---:|
| `L=60, gap=0` | 8 | **0.0490** |
| `L=20, gap=60` | 7 | **0.0542** |

Both ≈ nominal 0.05. So a miscalibrated reading below is **the data's dependence**, not
my machinery.

## And the answer is not identified

A block bootstrap needs **its own** block length. That is a nuisance parameter, and the
realised size moves with it — same data, same statistic, same geometry:

| bootstrap block | `L=60, gap=0` (Phase-0's own) | `L=20, gap=60` |
|---:|---:|---:|
| 20 | 0.0527 | 0.0638 |
| 40 | **0.0783** | 0.0605 |
| 60 | 0.0772 | 0.0570 |
| 90 | 0.0650 | 0.0423 |
| 120 | 0.0490 | **0.0393** |
| **spread** | **0.0292** | **0.0245** |

**Phase-0's geometry reads anywhere from 0.049 to 0.078 depending on a parameter nobody
registered.** Quoting any single cell as *"the realised size"* would be picking a number
out of a range I generated myself.

> **This is requirement (1) demonstrated, not evaded.** #136 asked for *"a
> null-generating mechanism, stated in advance… the argument has to be made for the
> realised geometry, not asserted."* The spread above is what that requirement is
> protecting against: **the calibration answer is a function of an unregistered choice**,
> so a bootstrap run after seeing the data can be steered — not by dishonesty, just by
> picking the block length that looks principled afterwards.

## What this does and does not establish

**Establishes:** requirement (3) **cannot be met by "just bootstrap the series."**
A registered rule for the bootstrap block length — and a reported sensitivity band —
is a precondition, not a refinement.

**Does NOT establish:** that Phase-0's geometry is or is not over-rejecting. The honest
reading is *unresolved with a range*: **0.049–0.078 at nominal 0.05** across defensible
nuisance choices. It also does **not** show that `gap ≥ h` fixes anything — the
`L=20, gap=60` column spans 0.039–0.064 and is **not** uniformly closer to 0.05. Gap is
necessary, and this is one more measurement showing it is not sufficient.

**No GOAL-4 verdict changes.** The freeze holds on the prior-discipline ground #136
already states, not on any number here.

## Next, concretely

Requirement (1) needs a **registered block-length rule** before (3) is meaningful. The
two candidates worth preregistering are a rule keyed to the measured decay of the
series' own autocorrelation, and a fixed multiple of `h`. **Both must be chosen before
the next run and reported with this same sensitivity table**, or the calibration is
re-openable by whoever runs it next.

## Reproduce

```
python3 tools/g4_null_size_study.py \
    --series doc/research/evidence/2026-07-31-g4-null-calibration/per_date_g_real_copy.csv \
    --out    doc/research/evidence/2026-07-31-g4-null-calibration/size_study.json
```
