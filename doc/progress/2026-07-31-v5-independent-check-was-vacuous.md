# GOAL-7: the INTERNAL construction is verified; the dividend DATA is not

**Bottom line — NARROWED 2026-08-01 after codex on #133.** What is cleared is the
**internal construction**: the total-return series does, on its own data, what it was
built to do. What is **not** cleared, and cannot be with what exists here, is the
dividend confound **as a fact about the source data** — because the only external check
never ran.

## The INTERNAL result `[早前实测 2026-07-30, read 2026-07-31]`

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

## Why V1–V3 and V7 are all internal — the line of code that settles it

`exdiv_gap()` identifies ex-dividend days as `s["dividend"] > 0` — **the same
`dividend` column the TR construction consumes to build the series**
`[VERIFIED — 本次实测 2026-08-01, tools/build_total_return_series.py:250]`.

> **So if the dividend feed is wrong — a missing event, a wrong amount, a wrong date —
> the construction will not adjust for it AND V1 will not look for it**, because it
> reads the event calendar off the same column. V1 tests *"did we remove what our own
> data says was there."* It cannot fail on a bad feed.

The same holds for the rest: `V3` is the identity `TR[k]/TR[k-1] == (P[k]+D[k])/P[k-1]`
over the same `D`; `V2` compares non-payers to themselves; `V7` reconciles CAGR against
a yield computed from that same column. **Every surviving validation is
self-referential.** `V5` — the vendor's independently-built `adj close` — is the only
one that could contradict the feed, and it produced nothing (column present, **0**
non-null rows over 2 658 rows × 6 tickers).

## The narrowed status, and what may be said downstream

| claim | status |
|---|---|
| the TR construction is internally correct | **supported** — V1 −66.58→−4.84 bp, V2 exact 0.0, V3 4.4e-16 |
| the dividend confound is removed **from the source data** | **NOT established** — no external check ran |
| a momentum result on this TR series is free of a dividend-yield tilt | **NOT established**, and downstream claims must say so |

**This supersedes the earlier phrasing** — *"the dividend confound is discharged for the
purpose it was raised"*. That over-reached: it is discharged **for the construction**,
which is a smaller claim than it sounded.
