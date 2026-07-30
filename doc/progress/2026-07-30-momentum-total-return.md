# 2026-07-30 — dividend-adjusted total-return series, and a re-registered momentum study

## What this is

**Two commits, deliberately in this order.**

1. **`048975f` — THE FREEZE, containing no result.** The prereg
   `doc/research/2026-07-30-momentum-total-return-prereg.md`, the runner
   `tools/momentum_total_return_run.py`, the data builders and the shuffle
   tests, committed **before** the primary arm was computed. It carries zero
   files under `doc/research/data/`.
2. **the results commit**, which appends the `RESULTS` sections to that prereg
   and to this doc and adds the run artifacts. It changes exactly 3 lines of the
   frozen §§0–9 (a header note saying results were appended) and is otherwise
   pure addition.

The git order is the evidence that nothing was selected after seeing a number.
Sections below up to `# RESULTS` are the freeze; everything after it is the run.

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

---

# RESULTS (appended after the freeze `048975f`)

## Bottom line

**Part 1 VALIDATED. Part 2 returned nothing.**

1. **The dividend adjustment validated.** Ex-div-day gap **−66.6 bp (t=−20.6) →
   −4.8 bp (t=−1.55)**, 92.7% removed; with ticker+date fixed effects −63.7 →
   **−3.2 bp (t=−1.33)**. Negative control exactly 0.0, bitwise, on all 34
   non-payers.
2. **§6 verdict: `UNRESOLVED / TILT-NOT-EXCLUDED`. NOTHING IS LICENSED.** No
   model, no shadow deployment, no capital action.
3. The primary cleared every bar it owns — E2 = **+0.4310 SD**, block
   `t = +3.767` on 10 blocks (programme bar 3.1019), CI `[+0.2705, +0.6256]`,
   three views agree, placebos max \|t\| 1.25 vs bar 2.0, 40-shuffle false-flag
   rate **2.5%**, leave-one-block-out `t ∈ [+3.26, +5.34]` with zero sign flips
   — and then **failed the §5b paired baseline gate** (`t = +1.682`, Holm
   p = 0.093). The frozen rule maps that to UNRESOLVED and I did not override it.
4. **The dividend confound is REFUTED as the explanation of the aborted run's
   monotone-with-horizon pattern.** Paired TR-minus-price delta is
   −0.0075/−0.0088/−0.0107/−0.0103 at h=20/60/120/250, all \|t\| ≤ 1.74 — ≈2% of
   the effect and *negative*. The `_px` twin reproduces the aborted run's
   published screen table to **0.0000**, which is what licenses reading that
   delta as the dividend effect and nothing else.

## Two things I got wrong, recorded

* **My §5b gate was mis-designed and it is why the study is UNRESOLVED.** The
  baseline arm B1 `div_yield_252` had **dirty placebos of its own** (max
  \|t\| = 2.56 vs bar 2.0), and I gated the verdict on a paired contrast against
  it without ever calibrating the noise floor of the difference. The contrast
  failed on power (delta +0.3455, CI `[+0.0887, +0.7090]` excluding zero,
  `resolves = True`, but `t = 1.68`), not on effect size. Meanwhile the two arms
  that actually test the tilt hypothesis — orthogonalising to the yield column
  and pooling *within* yield quintiles — both survive at `t = +4.26` and
  `+3.83`. So the failing gate is **not** evidence that momentum is a yield tilt;
  it is my own uncalibrated control.
* **My W4 factor-level negative control was wrong on first write** and asserted
  that a non-payer's `beta_*_spy` must be unchanged. It must not: beta's
  benchmark leg is SPY, which is itself a payer. Split into own-series factors
  (exactly 0.0) and benchmark-dependent factors (correctly non-zero).

## A post-hoc caveat that undercuts even the passing statistic

Mean label z by `mom_12_1_tr` decile is **U-shaped, not monotone**: d0 = +0.135,
d1–d8 ≈ −0.03…−0.09, d9 = +0.375; profile/decile rank correlation only **+0.27**;
full-cross-section IC `t = +0.589` ≈ 0. So the *lowest* momentum decile also
outperforms and the middle is flat. **Even where E2 passes, "momentum orders the
cross-section" is not supported** — what the corpus shows is a tail effect. Not
pre-registered; reported because it can only make the reading more conservative,
and the verdict is already "nothing licensed".

## Verification of the git order

Freeze commit `048975f` carries **zero** files under `doc/research/data/`. The
results commit changes exactly **3 lines** of §§0–9 (the header note saying
results were appended) and is otherwise pure addition — checkable with
`git diff 048975f -- doc/research/2026-07-30-momentum-total-return-prereg.md`.

## No look-ahead — proven, not asserted

`R[t] = prod_{s>t} g[s]` uses FUTURE dividends, so this needed settling. Every
factor is a *ratio* of TR values, and the anchor cancels: e.g.
`mom_12_1(t) = (P[t−20]/P[t−250]) · prod_{t−250<s≤t−20} g[s]`, i.e. only
dividends **inside the formation window**. Verified numerically by rebuilding a
forward-cumulative index that at each `t` uses only dividends up to `t`:
`max|backward − forward|` = 3.6e−15 (`mom_12_1`), 5.6e−16 (`hi52_prox`), 8.9e−16
(`ma200_ratio`), 2.6e−15 (`vol_250`), and the two series differ by a pure
per-ticker constant (max relative spread 1.8e−15). The only anchor-sensitive
quantity is the TR **level**, which prereg §3.2 forbids using — that prohibition
is load-bearing, not stylistic.
