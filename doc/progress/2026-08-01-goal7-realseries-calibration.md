# GOAL-7 — the calibration codex asked for three times CANNOT be run on this series, and here is the arithmetic

**Date:** 2026-08-01 · `renquant-model` · GOAL-7 Stage 1 (bar validity)

## Bottom line

Three reviews `[codex on model#124, #128, #135]` made one demand: the registered
`t_{0.975,17} = 2.1098` bar is not established on 18 contiguous 60-day block means of a
120-trading-day forward label, and the size that priced it was simulated under an
**assumed** `ρ₁`. The remedy named was a *"dependence-preserving, pre-registered null
calibration for the real pre-2021 series."*

**It is not identifiable on this series.** Not "I did not run it" — run, and the two
requirements provably do not overlap `[本次实测 2026-08-01]`:

| requirement | forces |
|---|---|
| preserve the 120-day label dependence | bootstrap block `Lb ≥ 120` |
| estimate a 5% tail | `⌈1080 / Lb⌉ ≥ 20` draws per resample → `Lb ≤ 54` |

At `Lb = 120` a resample is built from **9** independent draws. **The two conditions have
no common `Lb`.** A design with a 120-day label needs `≥ 20 × 120 = 2 400` dates for an
identifiable bar; this window has **1 080** — **2.22× short**. That last number is
**arithmetic on the two stated requirements `[推导]`**, and it says what a design would
*need*, not that such a design would then pass.

## The series exists now, and the warrant is bit-identity

The calibration was previously unreconstructible for exactly one reason: the frozen run
persisted only the 18 block means. §7 of the redesign made persisting the per-date series
a design requirement because of this. It is discharged retroactively: **6 480 rows, 6
series × 1 080 block-covered dates.**

Nothing is re-decided. The panel and the deterministic arms are rebuilt from the two
**pinned** derived inputs, and the warrant is that **all 6 arm statistics reproduce
bit-identically** against the frozen `results.json` across `mean_per_date`, `block_mean`,
`block_sd`, `t`, `abs_t`, `n_blocks`. A reconstruction that diverged anywhere would not
match to the last digit; one that does not reproduce is reported and calibrates nothing.

## A separate fact, stated rather than stepped around

**Re-running the frozen Stage 1 today ABORTS.** The raw OHLCV corpus fingerprint moved
since 2026-07-30 — manifest pins `48728e24…`, actual `0cee3698…`. The guard is right and
is **not bypassed**; this tool never reads the raw corpus. The two derived parquets the
estimator actually reads are still sha256-identical to their §2A pins. So the estimator's
own inputs are unchanged while **the provenance chain above them no longer verifies**, and
the identity warrant here is the reproduction, *not* the upstream pin.

## The measured curve

Realised two-sided size of the 2.1098 bar, 4 000 circular block bootstraps of the demeaned
real series, per bootstrap block length `[本次实测 2026-08-01]`:

| series | 1 | 5 | 10 | 20 | 30 | 60 | 120 | 180 | 240 | ρ₁ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| draws per resample | 1080 | 216 | 108 | 54 | 36 | 18 | 9 | 6 | 5 | |
| `z/treatment_u` | .051 | .052 | .060 | .055 | .043 | .056 | .080 | .065 | .034 | **0.941** |
| `z/treatment_u_residualised` | .049 | .052 | .057 | .049 | .049 | .063 | .087 | .063 | .037 | 0.938 |
| `z/reference_z_mom` | .052 | .057 | .046 | .047 | .053 | .054 | .104 | .076 | .034 | 0.971 |
| `raw/treatment_u` | .056 | .047 | .043 | .052 | .052 | .054 | .111 | .118 | .097 | 0.937 |
| `raw/treatment_u_residualised` | .050 | .054 | .056 | .060 | .056 | .072 | .111 | .108 | .097 | 0.943 |
| `raw/reference_z_mom` | .052 | .051 | .049 | .049 | .049 | .053 | .105 | .093 | .053 | 0.972 |

`identified = False` on all six. Two readings must both be refused:

- **The right half is not evidence the bar is inflated 2.2×.** `Lb ≥ 60` draws ≤ 18
  blocks per resample; below 20 draws a 95th percentile is not estimable.
- **The `0.034` at `Lb = 240` is not evidence the bar is conservative either.** It comes
  from **five** draws. A checker that rejected only the inflated cells would let the
  flattering one through, and that asymmetry is how a design gets talked into looking
  correctly sized. Both ends are excluded, and a test pins that.
- **The left half is near nominal (.043–.060) and proves nothing about the bar**, because
  `Lb ≤ 30` is precisely the regime that fails to preserve the dependence under objection.

**`ρ₁` measured on the real series is 0.937–0.972.** codex's 0.94 was not an assumption —
it is a property of this series, and it is confirmed on all six arms.

## What this settles, and what it does not

**Settles:** no amount of post-hoc calibration rescues the registered bar on a 1 082-date
window with a 120-day label. Any Stage-1 redesign must change the **geometry** — span or
horizon — not the critical value. That removes a whole class of candidate from #128's
B-versus-C question without needing the B-versus-C decision itself.

**Does not settle:** whether a 2 400-date design would be correctly sized (that is a
requirement, not a result); anything about GOAL-7's *effect*; and `#133`'s missing
external total-return validation, which is untouched here.

## Tests

16, run before the push. The two load-bearing ones: a **divergent** reconstruction is
reported and calibrates nothing, and an all-degenerate sweep returns `None` rather than
`0.0` or a raised exception — a size of zero reads as "the bar never fires", which is the
opposite of unknown, and a scheduled caller cannot tell a thrown exception from a
deliberate alarm. Writing that test is what found the crash: `np.percentile` on an empty
array raised `IndexError`.


---

## Addendum 2026-08-01 — the persisted series was not machine-readable

The whole point of §7 is that the per-date series can be re-used. It could not be: the
emitter wrote `f"{v!r}"` on a NumPy scalar, so under NumPy 2 every row read

```
2016-12-29,z,treatment_u,np.float64(0.4928851274964489)
```

`pd.read_csv(...)` returns that column as **object**, and `astype(float)` raises. I found
it by crashing on my own evidence one round later.

Fixed to `float(v)!r` — full double precision, no wrapper. Regenerated: **6 480 rows parse
as `float64`**, and all **6 arm statistics still reproduce bit-identically** against the
frozen `results.json`, so the fix touched the serialisation and nothing else.

The lesson is narrow and worth keeping: *persisted* is not *reusable*. A file written for a
future consumer should be read back by that consumer's parser in the same commit that
writes it.
