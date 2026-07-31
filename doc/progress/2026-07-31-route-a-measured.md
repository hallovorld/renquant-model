# GOAL-7 §7.1: route (a) IS accumulating — and the thing it accumulates defeats it

**Date:** 2026-07-31 · `renquant-model` · GOAL-7 / PatchTST closure line

The closure v2 run ended `UNRESOLVED (underpowered)`: §0.1 admitted only the
digest-verified live score dates, **which numbered 2**, giving `n_blocks = 0`. §7.1's own
prescribed deliverable is *"what would raise `n_blocks`"*, and route (a) was *"let
`shadow_scorer_health.jsonl` accumulate ~420 contiguous scored trading days behind a
stable checkpoint (~20 months)"*.

**Measured today, and the news is mixed in a way the estimate did not capture.**

## Route (a) is running

`[本次实测 2026-07-31, shadow_scorer_health.jsonl sha256 6063ed225826280b…, 13 rows]`

The served digest §0.1 admits — `sha256:07046963994dbb8d` — scored on **four consecutive
dates**: 2026-07-27, 07-28, 07-29, 07-30 (**five rows**; 07-28 ran twice). At v2's
execution it was **2**. So the accumulation is real and running at **1 date per trading
day** — counted by DATE, because it is dates, not rows, that `n_blocks` is built from.

## And every one of those dates is a staleness breach that grows 1:1 with it

| run_date | state | n_scored | staleness_days |
|---|---|---:|---:|
| 2026-07-27 | `degraded` | 80 | **621** |
| 2026-07-28 | `degraded` | 77, 78 | **622** |
| 2026-07-29 | `degraded` | 78 | **623** |
| 2026-07-30 | `degraded` | 77 | **624** |

The limit is **28 days** (model-freshness governance, RFC #210). The checkpoint is
already **596 days past it**, and `staleness_days` increases by exactly **1 per scored
day** — the same clock that produces the evidence.

## So route (a) is self-defeating as written `[推导 from the two measured rates above]`

`n_blocks ≥ 6` on a **gap-honest** geometry (`gap ≥ h`, `h = 60`) needs
`6L + 5×60` contiguous trading days:

| block length `L` | trading days | ≈ months | checkpoint staleness at completion |
|---:|---:|---:|---:|
| 20 | 420 | 19.3 | **~1 212 d** |
| 30 | 480 | 22.1 | **~1 296 d** |
| 60 | 660 | 30.4 | **~1 548 d** |

The ~20-month figure in §7.1 was right for `L = 20`. What it did not carry is the
**second axis**: at the finish line the instrument is a model **~3.3 years** past a
28-day freshness bar. The study would resolve a question about a checkpoint nobody would
serve.

**This is not an argument for abandoning route (a). It is an argument for stating what
route (a) is:** either

* **a deliberately frozen research instrument** — the checkpoint is pinned *because* it
  must not move, the staleness alarm for it is dispositioned with that reason and an
  explicit expiry, and no one reads its scores as a live model; or
* **a live shadow** — in which case it must be retrained, and every retrain **resets the
  contiguous span to zero**, so `n_blocks` never grows and route (a) can never complete.

**These two cannot both be true of one artifact, and today it is being run as both.**
That is the frozen-rule adjudication this lane has been waiting for, and it does not
need any new statistics — only the two rates above.

## Two further measured facts, recorded without interpretation

1. A **second** shadow digest, `sha256:1e644354e0981f47`, scores on the same dates at
   `stale_91d → 93d`. Also degraded, also growing 1:1. Not part of §0.1's admitted
   series; noted because any "just use the other shadow" move inherits the same
   structure.
2. **Every date also emits a `no_shadow_models` row** (`n_candidates = 0`, reason
   *"no shadow_models configured"*). Two lanes are logged into one file and one of them
   is configured with nothing. Not diagnosed here.

   > **Correction to my own first reading.** I originally cited `actionable = true` on
   > that row as if it meant *"this needs attention."* **It does not.** The producer
   > contract is `actionable == (status != "fault")`: `ok` **and** `expected_skip` both
   > carry `actionable = true`, and a real `fault` carries `actionable = false`. Measured
   > across these 13 rows: the **10 `degraded` fault rows are `actionable = false`**, the
   > **3 `no_shadow_models` rows are `actionable = true`**, and the invariant holds
   > 13/13. The field means *"this lane is serviceable this run"*, not *"act on this"* —
   > a naming trap I walked into, and the reason this note now states the polarity
   > explicitly instead of quoting the flag.

## Not claimed

That the checkpoint's staleness invalidates its scores — that is a modelling question
this document does not touch. That route (b) or (c) is better; they are unmeasured.
That the closure verdict changes: it remains **UNRESOLVED (underpowered)**, `n_blocks`
is now what 4 dates give (still 0), and **no verdict is computed here**.

## Evidence

`doc/research/evidence/2026-07-31-route-a/shadow_scorer_health_snapshot.json` — the rows
this rests on, with the source path, byte count and **sha256 of the exact bytes read**.
The log is a live append-only surface, so a later read *will* differ; the digest is what
makes this finding checkable rather than re-measurable-into-agreement.
