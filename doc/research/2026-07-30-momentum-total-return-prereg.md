# PREREG (FROZEN): momentum on a DIVIDEND-ADJUSTED total-return series

**Frozen:** 2026-07-30, before the primary arm was computed and before the
holdout was touched in this study. **This revision contains NO result.** The git
order is the evidence: this document and `tools/momentum_total_return_run.py`
are committed first, the results are appended in a separate later commit.

**Operator constraints, registered as binding:** at most **10 factors**; a
passing model goes to **SHADOW ONLY**, never straight to live.

**Supersedes nothing.** `2026-07-30-momentum-horizon-prereg.md` is
`ABORTED — INVALID CONTROL` and its verdict is not revised by this document.
This is a **new registration** with a new primary test, as that erratum
required.

---

## 0. Known-trap checklist

| # | the failure | how THIS design avoids it |
|---|---|---|
| T1 | a placebo sitting on the signal's own peak | placebos are within-date **label permutations**, not time shifts, so there is no shift length to land on a peak |
| T2 | naive per-date `t` on overlapping labels | `dependence_aware_mean`, `block_length = h = 120` = the label overlap; block `t` + bootstrap CI + leave-one-block-out must agree in sign |
| T3 | an invocation frozen without an end-to-end smoke | `--smoke` was run on this exact environment before this freeze: self-check PASS, both pins OK, label built, screen measurement + baseline + Holm paths all exercised. It does **not** compute the primary and does **not** read holdout dates |
| T4 | a multi-hour local run without `caffeinate` | the run is launched under `caffeinate -i` |
| T5 | an absolute effect quoted without its matched null | every arm carries its own 5 within-date placebos on its own sample; the primary additionally carries a 40-replication false-flag calibration (§5) |
| T6 | post-hoc subgroup or window search rescuing a dead result | the horizon is **declared from theory** (§2); §6 forbids revising the verdict by changing horizon, `k`, block length or split |
| T7 | an experiment mutating a production input | the umbrella is READ-ONLY; every artifact is written under the scratchpad; no `git` is run in the live tree |
| T8 | model/panel internals in the orchestrator | this lives in `renquant-model`, the model factory, which owns research |
| T9 | acting on a striking by-product of a different study | the only by-product reported (D1) is registered **in advance** as a DATA diagnostic that cannot license any action |
| T10 | confusing "the score is stale" with "the signal is long-horizon" | no scores here; the factor is recomputed at every date from a trailing window |
| T11 | cross-lag statistics on a drifting sample | the label is `shift(-h)`, so the newest `h` dates are null and are dropped by `dropna`; block length is the horizon, never a lag |
| T12 | paired arms drawn from different score windows | D1's TR and price arms are the same construction on the same `(date, ticker)` rows in ONE frame (`_tr` / `_px` columns), so the pairing is exact by construction |
| T13 | the estimand named only after seeing which one gives the preferred answer | E2 (top-decile spread) is named here as **the** primary estimand; E1 is registered as secondary and cannot change the verdict |
| T14 | a control that cannot fail | §5 measures the control's own false-flag rate on 40 clean shuffles and **VOIDs the run** if it exceeds 10% |
| T15 | a digest cited against a bundle later appended to | both inputs are single immutable parquet files, sha256-pinned in §3; the runner **aborts** on mismatch |
| T16 | all placebos clean and the effect is still a one-column tilt | §5b: a naive `div_yield_252` baseline, a neutralised arm, a conditional-pooling arm, and a **paired Holm-corrected contrast** the subject must win |
| **T17** | **a placebo that leaks across dates because the frame is not date-contiguous.** Cost the entire previous run (`ABORTED — INVALID CONTROL`). | Defect 1 fix, §4.2: rows are sorted by date before any shuffle; the shuffle is a direct per-group permutation; and a self-check runs on two deliberately INTERLEAVED frames **and is proven to reject the old broken implementation** before any data is read |
| **T18** | **selecting the arm on block `t` when the block count itself depends on the horizon.** The old rule picked the horizon where the effect was smallest. | Defect 2 fix, §2: there is **no empirical selection at all**. One horizon, declared from theory, with a data-independent block-count floor |
| **T19** | **a "total-return" series that is not one.** A dividend adjustment that is subtly wrong quietly rewrites every price-derived factor. | Part 1 validation battery: the ex-div-day gap must collapse; non-payers must be bit-identical; the return identity must hold to machine precision; the price twin must reproduce the pinned library exactly |

## 1. The question

Does 12−1 formation momentum, measured on a **dividend-adjusted total-return**
price series, order the cross-section of forward 6-month excess returns — and
does it do so **better than the trailing dividend-yield column** that the
adjustment itself is built from?

The decision that changes: whether a momentum factor is built and deployed to
**shadow**. Nothing else. No capital, no sizing, no live path, at any outcome.

## 2. The horizon and the arm, DECLARED FROM THEORY BEFORE RUNNING (T18)

The previous run's fatal design error was selecting the (arm, horizon) pair
empirically on block `t`. With `block_length = h`, the independent block count
falls ~12× from `h=20` (≈57 blocks) to `h=250` (≈4.8), so `t` **falls as the
horizon rises even while the effect grows**. Maximising `t` therefore
systematically prefers short horizons, and the rule picked the horizon where the
measured effect was smallest. **The fix is to remove the choice, not to
re-tune it.**

**Declared, from the literature, with no reference to any number measured on
this corpus:**

* **Formation: 12−1.** `close[t−20] / close[t−250] − 1` — twelve months of
  formation skipping the most recent month.
  `[ASSUMED — literature, not measured here: Jegadeesh & Titman 1993]`
* **Holding horizon: `h = 120` trading days (≈ 6 months).** Classic momentum is
  evaluated over a 1–12 month holding band; `J=12 / K=6` is Jegadeesh &
  Titman's own headline cell and 6 months is the midpoint of that band.
  `[ASSUMED — literature]`
* **A data-independent tie-breaker inside the theory band, declared now:** the
  estimator needs enough independent blocks to mean anything. Registered floor:
  **≥ 8 blocks** of length `h` on the test window. `1205 / 120 = 10`
  `[DERIVED]` clears it; `1205 / 250 = 4.8` does not. So the long end of the
  theory band is excluded **by the estimator's requirement, stated before the
  run**, not by any measured effect. If the floor is not met the run is `VOID`.

**Primary arm: `A1 = mom_12_1_tr`.** One arm, one horizon, one estimand, one
test. The other arms in §5 are descriptive and are computed on **screen dates
only**; they cannot alter the primary, because the primary was fixed here.

## 3. Data, subjects, and the exact input manifest

| input | sha256 | bytes |
|---|---|---|
| `momentum_factor_matrix_tr.parquet` | `85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a` | 76,310,040 |
| `total_return_close.parquet` | `8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9` | 4,007,937 |

The runner re-verifies both digests and **REFUSES to proceed** on a mismatch.
Code revision: this branch's commit, `tools/momentum_total_return_run.py`.

Provenance of those two files, both built read-only from
`RenQuant/data/ohlcv/<T>/1d.parquet` (145 watchlist names + `SPY`), 364,736 rows
× 3,161 dates, 2014-01-02 → 2026-07-29:

* `total_return_close.parquet` — `date, ticker, close, dividend, tr_close`.
* `momentum_factor_matrix_tr.parquet` — every price-derived factor built
  **twice**, on `tr_close` (`_tr`) and on raw `close` (`_px`), in one frame, plus
  `div_yield_252`, `sector`, `n_bars_available`, `split`.

### 3.1 The `dividend` column's semantics, established EMPIRICALLY before use

A sibling task was bitten by assuming `split_ratio`'s no-event sentinel was
`1.0` when it is `0.0`. So `dividend` was measured, not assumed
`[all VERIFIED-now]`:

* **Presence:** 240 of 2,790 ticker files carry a `dividend` column;
  **111 of the 145** watchlist names do. 72 files carry `split_ratio` (39 of
  the watchlist). The column set is not uniform across the corpus.
* **No-event sentinel is exactly `0.0`** — 289,014 of 294,120 watchlist rows
  (98.264%). **Not** `1.0`, and **not** NaN.
* **NaN is rare and structural:** 759 rows (0.258%), and they are a *contiguous
  trailing block* of 253 rows on exactly three names — ATI, BA, INTC,
  2025-07-28 → 2026-07-29. In each case the block follows **≥ 300 rows of
  explicit `0.0`** and the name's last positive dividend is years earlier (ATI
  2016-08, BA 2020-02, INTC 2024-08). Filled with `0.0`; the fill is bounded,
  recorded, and cannot inject a phantom dividend.
* **Zero negatives.** 4,347 positive values (1.478%).
* **A real dividend is per-share cash on the same axis as `close`:** median
  \$0.53, p95 \$1.88, max \$15.00 (Costco's 2023 special). Median gap between
  events **91 calendar days** for 95 of 111 names ⇒ quarterly. Per-event yield
  median 56 bp, p99 203 bp, max 388 bp — no absurd values.
* **The flagged date is the EX-date, and `close` excludes the dividend:** mean
  same-day return on the 4,344 ex-div days is **−58.2 bp** vs **+8.5 bp**
  otherwise, a **−66.7 bp (SE 3.2 bp)** gap against a mean per-event yield of
  **+61.5 bp**. The gap ≈ −(yield), which is the signature of an ex-date on an
  unadjusted series.
* **`dividend` is on the SAME split-back-adjusted axis as `close`** — the trap
  that would otherwise wreck old dates for names that split. Checked two ways:
  per-event yield does **not** inflate in early years (mean 66 bp in 2016 vs
  50 bp in 2025), and on every splitter the pre/post-split mean yield moves with
  the company's known dividend history rather than by the split factor (AAPL
  4:1 in 2020: 39 bp → 13 bp; GE: 76 bp → 11 bp across its 2018 cut; NVDA 10:1:
  7 bp → 2 bp). A raw-cash-vs-back-adjusted mismatch would have shown as a
  factor-of-N yield jump at the split. It does not.
* **`SPY` carries 42 dividend events.** This matters: the label is excess
  vs SPY, so leaving the benchmark on price while adjusting the names would
  inject SPY's ≈1.85%/yr yield into every name's excess return. **Both legs are
  adjusted.**

### 3.2 The total-return construction, and why it is right for RETURNS

For each ex-dividend date `s`, gross-up factor `g[s] = 1 + D[s] / P[s]`
(`P` = raw split-adjusted close). Backward-cumulative factor, anchored so the
most recent bar keeps its true traded price:

```
R[t]  = prod over s > t of g[s]        (empty product = 1 at the last bar)
TR[t] = P[t] / R[t]
```

Then for **any** adjacent pair the simple return of `TR` is the **exact** total
return:

```
TR[k]/TR[k-1] = (P[k]/P[k-1]) * g[k] = (P[k] + D[k]) / P[k-1]
```

which is what an investor who held from close `k−1` through the ex-date earned.
(Single event at `k`: `R[k−1] = g[k]`, `R[k] = 1`.)

**Why backward-cumulative, and why for returns and not levels.** The factor is a
*ratio* correction: across any window with no event it is a single
multiplicative per-ticker constant, so it cancels out of every return, ratio and
rank; across a window containing events it injects exactly the reinvested cash.
Anchoring `R = 1` at the last bar keeps the live-relevant end of the series on
the real price axis, and makes `mom_n` — a ratio — invariant to the anchor. The
cost is that `TR[t]` at old `t` is a **rebased index, not a price anyone paid**
(it sits systematically below the historical close). So this series is valid for
momentum, volatility, beta and drawdown, and **invalid** for anything
denominated in dollars: share counts, "was it above \$50", round lots, tax lots.
That is exactly why it is built as a research artifact in scratch and is **not**
written back into the corpus.

Note `g` uses `P[s]`, the post-drop close on the ex-date, **not** `P[s−1]`. The
`P[s−1]` form (what Yahoo's `adj_close` does) is a first-order approximation;
`P[s]` makes the identity above hold to machine precision.

### 3.3 Part-1 validation results, reported here because they GATE the study

These are Part 1 and are already measured `[all VERIFIED-now]`. If the first one
had failed, the study would not be run at all.

* **THE ONE THAT MATTERS — ex-div-day gap re-run on the adjusted series:**
  **−66.6 bp (t = −20.6) → −4.8 bp (t = −1.55)**. 92.7% of the gap removed; the
  residual is not distinguishable from zero at 1.6σ. With **ticker AND date
  fixed effects** (which strips the composition/calendar tilt of who pays and
  when): **−63.7 bp (t = −25.1) → −3.2 bp (t = −1.33)**. **The gap collapses.**
* **NEGATIVE CONTROL:** over all 34 non-paying names, `max|new − old| = 0.0`
  exactly, and the series are **bitwise** identical (checked explicitly on
  TSLA, AMZN, NFLX). Converse: all 111 payers moved, so the adjustment is not
  inert.
* **Return identity:** `max |TR[k]/TR[k−1] − (P[k]+D[k])/P[k−1]| = 4.44e−16`
  over all 4,344 events.
* **The `_px` twin reproduces the pinned price-only library
  (`544701ba…`) EXACTLY** — `max|diff| = 0.000e+00` on all 14 factors over
  364,736 paired rows. So the only thing that changed is the input series, not
  the factor code.
* **Factor-level negative control:** for non-payers, all 12 own-series factors
  are identical to `0.000e+00`. `beta_*_spy` is **expected** to move (max 0.57)
  because its benchmark leg is SPY, itself a payer — a two-legged statistic
  changes when the benchmark is adjusted. That is correct, not a defect.
* **Economic sanity:** mean TR−price CAGR gap 2.60% vs mean realised yield
  2.15%, `corr = 0.975`; zero names where TR CAGR < price CAGR. SPY: 12.97% →
  14.82%.
* **Effect on the factors:** `mom_12_1` shifts by a mean **+0.0194**
  (p99 +0.0778), Spearman 0.998 — a real level shift with a near-preserved
  ordering. `vol_*` barely moves.

### 3.4 What could NOT be established, stated plainly

* **No independent vendor-adjusted series exists in this corpus to corroborate
  the construction on the watchlist.** 49 files carry both `adj close` and
  `dividend`, but the `adj close` column is **100% NaN in 41 of them**,
  including all 6 watchlist names that have it. A cross-check was possible only
  on 3 **out-of-universe** names, where an independent writer's adjusted series
  tracks this one at `corr` 0.9993–0.99999 with mean |daily return difference|
  0.05 / 0.16 / 1.11 bp (GOOGL / TER / SWKS). Suggestive, not a corroboration of
  the 145-name universe.
* **Whether the 34 names lacking a `dividend` column truly paid nothing cannot
  be verified from inside this corpus** `[ASSUMED]`. All 34 are names for which
  non-payment over 2016–2026 is the documented norm (TSLA, AMZN, NFLX, PANW,
  SNOW, CRWD, GLD, …), and every one of the 111 files that *has* the column has
  ≥ 1 event, so column-presence tracks payment. But a name that paid and has no
  column would have its total return understated, and I cannot rule that out
  from here. Registered as a limitation.
* **A per-event yield-slope test is NOT a valid validation instrument, and is
  not used as one.** Regressing the ex-div-day return on the event yield gives
  −1.41 raw → −0.41 adjusted, but the **+1.000 shift is an algebraic identity**
  (`r_tr = r_raw + D/P[s−1]` exactly), so it validates nothing. The residual
  −0.41 (t = −5.4) is confounded by the yield's own denominator — a price that
  already fell mechanically raises measured yield on a fixed cash dividend (OXY,
  March 2020: 32.5% trailing yield on a price that fell from \$48 to \$9.69).
  Consistent with that: the **median** same-day TR return is flat across yield
  quintiles (+18.6, 0.0, +9.5, +7.2, 0.0 bp) while only the mean slopes, and the
  slope loses significance once events above 1.5% yield are trimmed
  (−0.15, t = −1.69). Reported as **inconclusive by construction**; the verdict
  on the adjustment rests on the ex-div-day gap collapse and the negative
  control.

## 4. Statistics, nulls, and the estimator

### 4.1 Label, estimands, estimator

Label, for `h ∈ {20, 60, 120, 250}` trading days:

```
fwd_h_excess(t) = (C[t+h]/C[t] − 1) − (SPY[t+h]/SPY[t] − 1),
then per-date cross-sectional z-score
```

built **twice**: `_tr` (both legs on the total-return series) and `_px` (both
legs on raw price). Mixing legs would smuggle the dividend back in. The last `h`
dates carry no label and are dropped. **Units are standard deviations of the
per-date cross-section, not return, so NO P&L CLAIM IS POSSIBLE from this
document.**

* **E2 — PRIMARY:** top-decile spread, `k = round(0.10 · n)`, `k ≥ 1`; dates
  with `n < 20` dropped.
* **E1 — SECONDARY, cannot change the verdict:** full cross-section Spearman IC
  per date.
* **Estimator, named exactly:** `dependence_aware_mean` on the per-date
  statistic series in date order, **`block_length = h = 120`** (the label
  overlap, never a lag), `n_boot = 2000` (600 for controls), reporting block
  `t`, moving-block bootstrap CI and leave-one-block-out bounds. `resolves`
  requires all three to agree in sign.
* **Nulls:** each arm's null is 5 **within-date label permutations on that arm's
  own sample**, bar `|t| < 2.0`.

### 4.2 The placebo must be a WITHIN-DATE permutation (Defect 1 / T17)

The previous run's shuffle sorted the frame into `(_dcode, random)` order and
wrote that sorted sequence back into original row positions **positionally** —
correct only if rows already arrive grouped by date. The frame was ticker-major,
so labels leaked across dates. Registered fixes, all three:

1. **Sort by date before any shuffle.** `prep()` sorts by `(date, ticker)` and
   only then assigns `_dcode`.
2. **A direct per-group permutation**, `f.groupby("_dcode").indices`, which is
   correct regardless of row order.
3. **A self-check that runs on two deliberately INTERLEAVED frames and is
   PROVEN TO REJECT the unsorted-frame implementation.** The runner calls
   `selfcheck_shuffle()` **before it reads any data** and `SystemExit`s unless:
   the shipped shuffle respects every date's label pool, is a permutation within
   every group, and is seed-sensitive on both interleaved frames; **and** the
   old broken lexsort implementation — kept in the file purely as this negative
   control — **fails** that same check. If the broken reference stops failing,
   the guard aborts with `FAILED TO REJECT`, because a check that cannot fail is
   not a check. `tests/test_momentum_total_return_shuffle.py` carries 11 tests
   including three that point the guard at a broken shuffle and assert it
   aborts, and one that documents *why the defect survived review*: on a
   date-sorted fixture the broken code is perfectly fine, so any natural fixture
   passes it.

## 5. Control calibration (T14)

**CONFIRMATORY tier — mandatory, and it is a VOID gate, not a report.** Before
reading the primary's verdict the runner measures the control's own false-flag
rate: **40 clean within-date shuffles** (≥ the 40 the template requires and ≥ the
30 a prior amendment requires) of the primary arm's label on the primary window,
each scored through the identical estimator. Reported: the mean, p50, p95 and max
of `|t|`, the fraction with `|t| ≥ 2.0` over all 40, and separately over the
first 30. **If that rate exceeds 10% the run is `VOID`** — this is exactly the
corpus-geometry dependence that the traded-estimand prereg's Amendment 1
registered and that the previous run tripped over at long horizons.

### Arms

`z(·)` = per-date cross-sectional z-score. **A1 is the only confirmatory arm.**
A2–A7 are computed on **screen dates only** and §6 forbids any claim from them;
they exist so the table is comparable to the aborted run's, which is what makes
the dividend effect on that table visible.

| id | arm | role |
|---|---|---|
| **A1** | `mom_12_1_tr` | **THE PRIMARY**, h=120, holdout |
| A2 | `mom_6_1_tr` | descriptive, screen only |
| A3 | `hi52_prox_tr` | descriptive, screen only |
| A4 | `ma200_ratio_tr` | descriptive, screen only |
| A5 | `mom_12_1_tr / vol_250_tr` | descriptive — volatility scaling |
| A6 | `mom_12_1_tr` where `vol_60_tr >` per-date median, else 0 | descriptive — volatility gating |
| A7 | `z(mom_12_1_tr)` within sector | descriptive — sector-neutral |
| **B1** | `div_yield_252` | §5b naive baseline |
| **C1** | `mom_12_1_px` | D1 control twin |

Distinct factor columns consumed: `mom_12_1_tr, mom_6_1_tr, hi52_prox_tr,
ma200_ratio_tr, vol_60_tr, vol_250_tr, sector, div_yield_252, mom_12_1_px` =
**9 ≤ 10** `[DERIVED]`. The `_px` twin is not a candidate model input; it is the
control series for the §5b/D1 data diagnostic.

**A3 caveat, registered:** `hi52_prox` on a total-return series is not the
classic George–Hwang factor, whose premise is anchoring on the *nominal observed
price*. The TR version is the consistent one for this study and is what is
reported; it is not the literature's construction. A3 is descriptive only, so
nothing turns on it.

## 5b. NAIVE-BASELINE ARM (T16)

This study's subject **is** a single raw column, so "could this be a one-column
tilt?" is not the question — it plainly is one. The question T16 forces here is
sharper and is the whole reason Part 1 exists: **is the effect momentum, or is it
the dividend yield that the adjustment just injected?** Long-horizon momentum on
a TR series rises mechanically with accumulated yield, and high-yield names are a
sector-correlated block (utilities, telecom, energy, tobacco, REITs).

Frozen before execution:

1. **Baseline B1 = `div_yield_252`**, a single raw column:
   `sum(dividend[t−251..t]) / close[t]`, 252 bars inclusive, NaN before that,
   strictly backward-looking, computed from the **same** `dividend` column the
   adjustment consumes. Transform: per-date percentile rank. Missing-value rule:
   rows with NaN dropped pairwise. **Direction: long HIGH yield** (the classic
   yield-value tilt). Construction: the same rank-sorted top-decile spread as
   the subject, so the two are commensurable. It is frozen inside the pinned
   matrix `85c27fc1…` (§3), not computed at run time from a knob. Chosen because
   it is the mechanical alternative explanation named in the aborted run's own
   §3 — it could not have been picked to lose, because a win for it *destroys*
   the subject.
2. **Neutralised arm:** the subject's per-date rank **orthogonalised** to B1's
   per-date rank (OLS residual within each date). Both raw and neutralised
   effects reported.
3. **Conditional-pooling arm:** the subject's E2 computed **within quintiles** of
   B1 (quintiles not deciles: `n ≈ 145` per date gives ≈ 29 names per bucket),
   averaged across buckets per date. An effect that survives shuffling but dies
   inside its own yield buckets is a tilt.
4. **The gate is a PAIRED contrast, not two separate significances.** Per-date
   `delta = E2(subject) − E2(B1)` on the **same dates**, aggregated with §4's
   estimator at `block_length = 120`; the verdict requires the subject to win
   *that difference*. Family-wise handling across the three registered §5b arms
   (paired contrast, neutralised, conditional) is **Holm–Bonferroni at α=0.05**.
   A verdict is licensed only if the subject beats its baseline under that
   corrected paired comparison — never by each side independently clearing
   significance.

## 5c. Registered DATA diagnostic D1 — no verdict attached

The aborted run reported the traded spread rising monotonically with horizon in
4 of 7 arms and named the missing dividend adjustment as "the single most likely
alternative explanation … not ruled out by anything measured here". D1 rules on
it: for A1 at each `h ∈ {20,60,120,250}`, the **paired** per-date difference
`E2(mom_12_1_tr on fwd_h_tr) − E2(mom_12_1_px on fwd_h_px)` on identical rows,
with block `t`. A large positive delta ⇒ the price-only series understated
momentum; a delta ≈ 0 ⇒ the dividend adjustment does not change the momentum
conclusion either way. **D1 is a statement about the DATA, not about momentum.
It cannot license any action and does not enter the momentum multiplicity.**

## 6. Decision rule

**Multiplicity, stated honestly and up front.** The primary window
2021-10-08 → 2026-07-29 is **NOT a virgin holdout**. The aborted run already
spent it once, on `A2 mom_6_1 @ h=20`. This is a **second test on the same
dates** and is registered as such. Two consequences:

* the single-test tier is Bonferroni-corrected for `m=2` within this window:
  **`|t| ≥ 2.2414`**, not 1.96 `[DERIVED]`;
* programme-wide, 25 tests were registered before this one, so this is #26:
  **`|t| ≥ 3.1019`** `[DERIVED]`.

| outcome | verdict | licensed action |
|---|---|---|
| block count `< 8` | **VOID** | nothing |
| primary placebos not all `< 2.0` | **VOID** | nothing |
| false-flag rate `> 10%` (§5) | **VOID** — the control bar is decorative at this geometry | nothing |
| `\|t\| < 2.2414` | **UNRESOLVED** | nothing. A statement about **power**, never about momentum |
| three views disagree in sign | **UNRESOLVED** | nothing |
| `\|t\| ≥ 2.2414` but loses the §5b.4 paired Holm contrast | **UNRESOLVED / TILT-NOT-EXCLUDED** | nothing |
| `\|t\| ≥ 2.2414`, placebos clean, views agree, beats baseline | **SHADOW-ELIGIBLE** | build the model, deploy to **SHADOW ONLY**. No capital, no sizing, no live path |
| `\|t\| ≥ 3.1019` and all of the above | **RESOLVED** in the programme sense | still shadow-first; promotion out of shadow needs its own registration on **forward** dates |

Ties, ambiguity, broken arms and invalid controls all resolve to the
conservative branch named above. **No verdict may be revised by changing the
horizon, `k`, the block length, the arm set, the split boundaries or the
baseline.** Re-executing the runner on this selection is the **same** test, not a
new one.

## 7. Publication discipline

CONFIRMATORY tier. **An adversarial review is commissioned BEFORE the verdict is
published**, with the brief "assume the conclusion is wrong and try to break
it"; a review listing no residual risk is a failed review. Its findings are
recorded in the results section whatever they say. The 2026-07-29 precedent is
the reason: withholding a CLOSE pending attack is what prevented a second
retraction in one day.

## 8. Discipline

Read-only over production — the umbrella is never written, never `git`-ed,
never symlinked into. All writes are under the session scratchpad. Every number
carries `[VERIFIED-now]` / `[VERIFIED-prior]` / `[DERIVED]` / `[ASSUMED]`.
Negative and inconclusive results are reported with the same prominence as
positive ones. Frozen: any change is a timestamped amendment written BEFORE the
affected run, never an edit.

## 9. What NO outcome of this study licenses

No capital action. No sizing change. No expected-return claim — §4's units are
standard deviations. No claim that momentum beats the incumbent scorer, which
was never measured on this estimand. No claim from the §5 descriptive screen
table. And no live deployment: the ceiling is **shadow**, per the operator's
binding constraint.

---

**Nothing in this revision is a result.**
