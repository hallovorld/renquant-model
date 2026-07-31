# GOAL-7's dividend blocker cleared — and its one independent check never ran

**Bottom line, both halves.** The blocker the GOAL-7 anchor names — *"the −66.7 bp
dividend gap must collapse to ~0"* — **did collapse**. And the single validation that
was not self-referential **measured nothing**, on 0 usable rows out of 15 948, and
recorded `nan` instead of a failure.

## The gate result `[早前实测 2026-07-30, read 2026-07-31]`

| | raw close | total-return |
|---|---:|---:|
| ex-div-day gap | **−66.58 bp** | **−4.84 bp** |
| SE | 3.23 bp | 3.12 bp |
| **t** | **−20.62** | **−1.55** |

`|t| = 1.55 < 1.96` — **no longer significant**. Supporting:
`V2` non-payers max abs diff **0.0** (exact); `V3` identity error **4.4e-16** over
**4 344** events. On its own terms the construction is right.

## What did not run

`V5` is described in the tool as *"INDEPENDENT CROSS-CHECK against the vendor's own
`adj close` … **Not self-referential**."* Its selector was:

```python
both = [t for t in series if "vendor_adj_close" in series[t].columns ...]
```

**It tested the column's presence, not its content.** Measured 2026-07-31
`[本次实测]`:

| ticker | column | rows | non-null |
|---|---|---:|---:|
| APH, ATI, BWXT, EME, GLW, GRMN | `adj close` | 2 658 each | **0** |

So V5 correlated two all-NaN series six times and wrote `nan` for `corr`,
`mean_abs_bp` and `max_abs_bp`. **In a results bundle a NaN reads as "ran".** This one
meant "measured nothing".

> **Why it matters more than a missing row.** V1, V2, V3 and V7 all check the
> construction **against its own identity** — they can confirm the formula was applied
> consistently, never that the formula is the right one. V5 was the only external
> anchor, and it does not exist in this corpus.

## What landed

The selector now requires **≥ 2 usable rows**, and the bundle carries `V5_status`,
`V5_candidates_with_column` and `V5_usable_rows_by_ticker`, so a run states whether
its own independent check happened. A NaN can no longer impersonate a result.

## Honest reading for GOAL-7

The dividend confound is **discharged for the purpose it was raised** — a momentum
result on the TR series is no longer attributable to a dividend-yield tilt at the
ex-div-day level. What is **not** established is external agreement with an
independent adjuster. That is now recorded as *unavailable*, not as *checked*.

One more thing not glossed: `V7` gives ΔCAGR **0.02597** against realised yield
**0.02150** — a **0.45 pp** gap the tool describes as "must equal". Compounding is the
obvious candidate (a geometric effect against an arithmetic mean), but that is a
**hypothesis, not a measurement**, and is left flagged rather than explained away.

Tests: 5, pinned to a frozen coverage CSV and to the published bundle.
