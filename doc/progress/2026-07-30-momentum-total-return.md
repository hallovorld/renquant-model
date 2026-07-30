# 2026-07-30 — dividend-adjusted total-return series, and a re-registered momentum study

## What this commit is

**A FREEZE. It contains no result.** The prereg
`doc/research/2026-07-30-momentum-total-return-prereg.md`, the runner
`tools/momentum_total_return_run.py`, the data builders and the shuffle tests,
committed **before** the primary arm is computed. Results are appended in a
separate later commit; the git order is the evidence.

## Why

`2026-07-30-momentum-horizon-prereg.md` is `ABORTED — INVALID CONTROL`. Its own
erratum listed what a corrected registration would have to fix. Three items:

1. the placebo was not a within-date permutation (leaked across dates on the
   interleaved frame it was actually called on);
2. selecting the arm on block `t` was structurally biased, because
   `block_length = h` makes the block count fall ~12× as the horizon rises, so
   the rule picked the horizon where the effect was *smallest*;
3. the price series was **not dividend-adjusted**, and the aborted run named that
   as "the single most likely alternative explanation" for its own headline
   pattern — a monotone rise of the spread with the holding horizon, which is
   also exactly what an omitted, horizon-accumulating dividend produces.

Item 3 is a **data defect**, and it made even the screen table uninterpretable.
So it is fixed first.

## Part 1 — the data fix (measured, and it gates the study)

`TR[t] = close[t] / prod_{s>t} (1 + dividend[s]/close[s])`, anchored so the last
bar keeps its true price. Exact for returns:
`TR[k]/TR[k-1] = (P[k]+D[k])/P[k-1]`.

`dividend` semantics were established **empirically** first, because a sibling
task was bitten by assuming `split_ratio`'s no-event sentinel was `1.0` when it
is `0.0`. Findings `[VERIFIED-now]`: the sentinel is exactly **`0.0`** (98.264%
of rows), not NaN; the column exists on only **111 of 145** watchlist names (240
of 2,790 files); NaN is a contiguous trailing block on exactly 3 names
(ATI/BA/INTC, 253 rows each) following ≥300 rows of explicit zeros; values are
per-share cash on the **same split-back-adjusted axis as `close`** (verified on
every splitter — AAPL 4:1, GE, NVDA 10:1 — where a raw-cash mismatch would have
shown as a factor-of-N yield jump and does not); the flagged date **is the
ex-date**; and **SPY carries 42 events**, which matters because the label is
excess-vs-SPY and adjusting only the names would inject SPY's ≈1.85%/yr yield
into every excess return. Both legs are adjusted.

Validation `[all VERIFIED-now]`:

| check | result |
|---|---|
| **ex-div-day gap, raw → adjusted** | **−66.6 bp (t=−20.6) → −4.8 bp (t=−1.55)** — 92.7% removed |
| same, with ticker+date fixed effects | **−63.7 bp (t=−25.1) → −3.2 bp (t=−1.33)** |
| negative control, 34 non-payers | `max\|new−old\| = 0.0`, **bitwise** identical |
| converse: payers must move | 111/111 moved |
| return identity, 4,344 events | `max` error `4.44e−16` |
| `_px` twin vs the pinned price library `544701ba…` | `0.000e+00` on **all 14** factors, 364,736 rows |
| non-payer factors | 12 own-series factors identical to `0.000e+00`; `beta_*_spy` moves, correctly, via the SPY leg |
| TR−price CAGR vs realised yield | `corr = 0.975`, 0 names with TR < price |

**Could not be established, recorded in the prereg §3.4:** no independent
vendor-adjusted series exists to corroborate this on the watchlist — `adj close`
is present in 49 files that also have `dividend` but is **100% NaN in 41 of
them**, including all 6 watchlist names; a cross-check was possible only on 3
out-of-universe names (GOOGL/TER/SWKS: corr 0.9993–0.99999, mean |daily return
diff| 0.05–1.11 bp). And a per-event yield-slope test is **inconclusive by
construction** — the raw→TR shift of exactly +1.000 is an algebraic identity, and
the residual slope is confounded by the yield's own denominator (OXY, Mar-2020:
32.5% trailing yield on a price that fell \$48→\$9.69). Reported as such rather
than dressed up as a pass.

## Part 2 — the two defects, fixed structurally

**Defect 1 (placebo leaked across dates).** Three fixes, all registered:
rows sorted by date before any shuffle; a direct per-group permutation; and
`selfcheck_shuffle()`, which runs on two deliberately **interleaved** frames
before any data is read and **aborts unless the old broken lexsort
implementation FAILS the same check**. If the broken reference stops failing the
guard aborts with `FAILED TO REJECT`, because a check that cannot fail is not a
check. `tests/test_momentum_total_return_shuffle.py` — 11 tests, including three
that point the guard at a broken shuffle and assert `SystemExit`, and one that
documents *why the defect survived review*: on a date-sorted fixture the broken
code is perfectly fine, so any natural fixture passes it.

**Defect 2 (biased empirical selection).** Removed, not re-tuned. The horizon is
**declared from theory before running** — 12−1 formation, `h = 120` trading days
(≈6 months, Jegadeesh–Titman's headline `J=12/K=6` cell and the midpoint of the
classic 1–12 month holding band) — with a data-independent block-count floor of
≥8 blocks that excludes the long end of the band *by the estimator's
requirement*, stated in advance. One arm, one horizon, one estimand, one test.

**Holdout honesty.** The primary window 2021-10-08 → 2026-07-29 is **not virgin**
— the aborted run spent it on `A2 mom_6_1 @ h=20`. Registered as a **second test
on the same dates**: the single-test tier is Bonferroni `m=2` ⇒ `|t| ≥ 2.2414`,
not 1.96; programme-wide this is test #26 ⇒ `|t| ≥ 3.1019`.

**Also registered:** per-arm placebos; a 40-replication false-flag calibration
that **VOIDs** the run if the control bar false-flags above 10%; a §5b naive
`div_yield_252` baseline with neutralised and conditional-pooling arms and a
**paired Holm-corrected contrast the subject must win**; and D1, a pre-declared
paired TR-vs-price diagnostic that answers whether the aborted run's monotone
pattern was a dividend tilt.

Operator constraints honoured: **9 distinct factors ≤ 10**; ceiling is
**SHADOW ONLY** at every outcome.

## Discipline

Umbrella read-only — no writes, no `git`, no symlinks into it. All artifacts in
the session scratchpad. `--smoke` was run on this exact environment before the
freeze (self-check PASS, both pins OK, label built, screen + baseline + Holm
paths exercised) without computing the primary or reading holdout dates.
