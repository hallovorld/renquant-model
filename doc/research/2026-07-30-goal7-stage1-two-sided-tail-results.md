# RESULTS — GOAL-7 Stage 1: is the payoff TWO-SIDED rather than a ranking?

> # ⚠️ VERDICT WITHDRAWN AS A PREREGISTERED RESULT — see CORRECTION 1 at the end
>
> The registered estimator treats 60-trading-day blocks as independent while every
> label is a **120-trading-day** forward return, so adjacent block means share half of
> each label horizon. `df = 17` and the registered permutation null are **not valid
> inferential units** for this estimand. The defect is in the frozen design — mine —
> not in the execution.
>
> **This run may NOT be cited as a preregistered result, and VOLATILITY-TILT may not be
> reported as an established verdict.** What survives is stated in Correction 1: under
> dependence-aware corrections the same *direction* holds, but a conclusion that
> survives an unregistered correction is not a preregistered finding. A
> dependence-valid Stage 1 must be separately preregistered.
>
> The original verdict block is retained verbatim below for auditability.

> **VERDICT (WITHDRAWN — see above): VOLATILITY-TILT.** The raw two-sided arm clears its bar
> (`|t| = 3.270 ≥ T_crit = 2.1098`); orthogonalised to `|z_t(vol_60_tr)|` per §4
> it does not (`|t| = 1.644`). §4 registers that as a **kill condition, not a
> caveat**, so the two-sided hypothesis is **NOT supported** whatever the raw arm
> says. **Nothing is licensed.**
>
> **§8: THIS VERDICT IS WITHHELD PENDING ADVERSARIAL REVIEW.** The commissioned
> review and its disposition are appended verbatim at the end of this file.

Executes `doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md` (merged
as model#117) exactly as frozen. The authoritative partition is **AMENDMENT 4**;
A4.6 makes *both* sections titled "AMENDMENT 3" non-executable, and neither was
used as the specification.

Runner: `tools/goal7_stage1_two_sided_run.py`. Raw output:
`doc/research/data/2026-07-30-goal7-stage1-two-sided-tail/{results.json,run.log}`.
Estimator regression tests: `tests/test_goal7_stage1_estimator.py` (11 tests).

---

## 1 What was fixed before the run, and what it resolved to

| object | frozen text | realised |
|---|---|---|
| transform (§1) | `u = \|z_t(mom_12_1_tr)\|`, no free parameters | as written |
| label (§2A) | forward 120-trading-day excess return vs SPY, both legs on the TR series | identical to model#110's `fwd_120_tr` on 346,807 paired rows, `max\|diff\| = 0.0` |
| estimand (§3) | top-decile spread, `k = round(0.10·n)`, `k ≥ 1`, **minus the cross-sectional mean** | as written |
| estimator (§3) | contiguous non-overlapping 60-day blocks, remainder **dropped**, one-sample two-sided `t` | 18 blocks × 60, 2 dates dropped |
| kill condition (§4) | per-date OLS of `u` on `\|z_t(v)\|` **with intercept**; arm = top decile by residual **rank**, ties by ascending ticker | as written |
| `v` (§4) | **`vol_60_tr`** — the document explicitly rejects "STD60" as a column that does not exist in this corpus | `vol_60_tr` |
| partition (A4.2/A4.4) | last `t` whose 120th following corpus trading day precedes the 2021-10-08 burn | 2021-04-19 (120th following day 2021-10-07) |
| critical value (§3) | `T_crit = max(P95_null, t_{0.975,n_blocks−1})`, 200 within-date permutations | see §3 below |

`[VERIFIED — tools/goal7_stage1_two_sided_run.py, run.log, results.json]`

**Inputs, re-verified rather than transcribed** `[VERIFIED — shasum -a 256, this run]`:

| input | sha256 | bytes |
|---|---|---|
| `momentum_factor_matrix_tr.parquet` | `85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a` | 76,310,040 |
| `total_return_close.parquet` | `8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9` | 4,007,937 |

The committed raw-input pin
(`doc/research/data/2026-07-30-momentum-total-return/raw_input_manifest.json`)
was checked through `raw_input_manifest.verify_or_abort()`, which aborts on a
**missing or malformed** manifest and not only on a mismatching one:
`corpus_fingerprint = 48728e24bf2a043a…`, `config_sha256 = f52d096e0a491008…`,
145 raw inputs `[VERIFIED — run.log "RAW INPUT PIN OK"]`.

---

## 2 The partition, realised against A4.4 (§3's mandatory check)

| quantity | realised | pinned (A4.4) | |
|---|---|---|---|
| `N_eval` | **1082** | 1082 | MATCH |
| `n_blocks` | **18** | 18 | MATCH |
| dropped remainder | **2** — 2021-04-16, 2021-04-19 | 2, same two dates | MATCH |
| evaluation window | 2016-12-29 → 2021-04-19 | 2016-12-29 → 2021-04-19 | MATCH |
| blocks span | 2016-12-29 → 2021-04-15 | → 2021-04-15 | MATCH |
| admissible names / date | min **126**, median **128**, max 135 | A4.5: min 126, median 128 | MATCH |
| dates lost to the `<20`-name rule | **0** | A4.5: 0 | MATCH |
| excluded band (label would touch the burn) | 120 dates, 2021-04-20 → 2021-10-07, **16,226 rows** | 120 dates, same range | MATCH |

`[VERIFIED — run.log "A4.4 PARTITION — realised vs pinned"]`

**No shortfall to attribute.** A3-b §A3.3 left exactly one degree of freedom —
the `<20`-name rule can only reduce `N_eval` — and it removed nothing, so
`n_blocks = 18` is realised, not provisional, and the §7 `n_blocks < 6`
UNRESOLVED (underpowered) branch does not fire (18 ≥ 6).

Two facts the runner asserts rather than assumes:

* **no undersized block**: 18 × 60 = 1080 dates used, 2 dropped, never
  equal-weighted (the model#110 ERRATUM failure mode) `[VERIFIED — run.log]`;
* **the 120-day forward window is complete**: 0 of 145 tickers have an interior
  gap in the corpus trading-day calendar, so a 120-row forward shift *is* a
  120-trading-day window `[VERIFIED — run.log "contiguity"]`. Without this the
  label could silently reach past the burn boundary on a gapped name.

---

## 3 Critical value — both legs, and which one bound

`P95_null` is the 95th percentile of `|t|` over **200** within-date permutations
of `u` pushed through the identical harness.

| harness | `P95_null` | `t_{0.975,17}` | `T_crit` | bound by |
|---|---|---|---|---|
| raw (no orthogonalisation) | 2.0960 | 2.1098 | **2.1098** | **Student-t leg** |
| §4 residual | 2.0562 | 2.1098 | **2.1098** | **Student-t leg** |

`[VERIFIED — results.json T_crit; scipy.stats.t.ppf(0.975,17) = 2.1098155778]`

The Student-t leg bound `T_crit` in **both** harnesses, which incidentally
disposes of the one ambiguity in §3's wording — "the identical harness" could
mean each arm's own permutation null or a single null from the raw harness, and
here the two nulls differ by 0.04 and **neither reaches the Student-t leg**, so
`T_crit = 2.1098` under either reading and no arm's verdict turns on it
`[DERIVED — max(2.0960, 2.1098) = max(2.0562, 2.1098) = 2.1098]`.

**Is 200 permutations enough for `P95_null` to be trusted?** No — and it does
not matter here, which is worth showing rather than asserting. Resampling the
200 stored `|t|` draws: `P95_null` has a bootstrap 95% CI of **[1.824, 2.454]**
(raw harness) and **[1.760, 2.244]** (residual harness); **30.4% / 42.3%** of
bootstrap resamples put `P95_null` above the Student-t leg — a dispersion
statement about the *estimator*, not a probability about the true quantile
`[VERIFIED — 5,000-draw bootstrap of results.json T_crit.z.*.all_abs_t, this
session]`. But `T_crit = max(P95_null, 2.1098)` makes the Student-t leg a
**floor**, so:

* the **residual** arm (`|t| = 1.644`) fails under *every* realisation of
  `P95_null`, because `T_crit ≥ 2.1098 > 1.644` unconditionally;
* the **raw** arm (`|t| = 3.270`) would need `P95_null > 3.270` to fail; the
  bootstrap upper bound is 2.454 `[VERIFIED — same bootstrap]` and the single
  largest of the 200 null draws is 3.290
  `[VERIFIED — max(results.json T_crit.z.raw.all_abs_t)]`.

Both legs of the verdict are therefore insensitive to `P95_null` sampling error.
The permutation null's real contribution here is the **quantile** reading in §4,
not the bar.

**But the registered null is the wrong null for a persistent score, and this
weakens the RAW leg.** The adversarial review (§10, finding 5) measured what the
design did not: `u`'s per-date statistic has lag-1 autocorrelation **0.94** and
the 120-day label spans two consecutive 60-day blocks, while §3's null permutes
`u` **independently within each date** — which destroys exactly that
persistence. Under two persistence-preserving nulls the raw arm's permutation
p-value is **0.044** and **0.24**, not the 0.010 the registered null reports
`[VERIFIED — prior work, §10 adversarial review finding 5]`. This is a defect in
the *registered design*, not in the execution, and it is bounded — Newey-West on
the 1080-date series leaves the raw arm at `t = +3.22` (lag 60) and `+2.92`
(lag 120), and every alternative block length keeping `n_blocks ≥ 6` clears
`[VERIFIED — prior work, same review]`. Two consequences, stated because they
cut in opposite directions:

* **the kill leg is untouched** — `T_crit ≥ 2.1098 > 1.644` regardless of the
  null, and under both persistence-preserving nulls the residual arm's p-value
  *rises* to 0.30 / 0.39;
* **the raw leg is fragile** — and it is the raw leg that selects
  VOLATILITY-TILT over UNRESOLVED under §7. The honest reading is that the
  raw arm's clearance is a statement about the **registered bar**, not a robust
  finding. Both outcomes license nothing, so this does not change what follows
  from the run; it changes how much weight the raw arm's `|t|` can carry.

---

## 4 The arms

Primary label = the per-date z-scored forward 120-day excess return (units: SD
of the cross-section), the object §0's decile table was measured on.

| arm | role | harness | spread | `t` | `\|t\|` | `T_crit` | clears? | `\|t\|` as a quantile of the null |
|---|---|---|---|---|---|---|---|---|
| `u = \|z(mom_12_1_tr)\|` | **treatment, raw** | raw | +0.2381 SD | +3.2702 | 3.270 | 2.1098 | **YES** | **0.990** |
| `u` ⟂ `\|z(vol_60_tr)\|` | **treatment, §4 residual — the one that decides** | resid | +0.1161 SD | +1.6437 | 1.644 | 2.1098 | **NO** | **0.875** |
| `z(mom_12_1_tr)` | reference (not a bar) | raw | +0.2116 SD | +2.0092 | 2.009 | 2.1098 | no | 0.935 |
| `u_pc` | positive control (must pass) | raw | +0.0547 SD | +8.1375 | 8.137 | 2.1098 | **YES** | 1.000 |

`[VERIFIED — results.json arms.z]`

**The §4 residual is the arm the verdict turns on, and it fails.** Its `|t|`
sits at the 87.5th percentile of its own permutation null — **25 of 200** draws
of *pure noise* through the identical harness produce a larger statistic, i.e.
exactly one in eight `[VERIFIED — results.json T_crit.z.resid.all_abs_t]`.

Neither arm is a one-block artifact, and neither is the failure: **13 of 18**
block means are positive for the raw arm and **11 of 18** for the residual arm,
with the same block (the 9th) largest in both `[VERIFIED — results.json
arms.z.*.block_means]`. The residual arm's problem is size, not a single
outlier — the effect thins across the same blocks rather than disappearing from
a few.

Pooling addendum required by §4: the residual statistic computed inside each
`vol_60_tr` decile and averaged is **+0.0533 SD, `|t| = 0.861`** — the sign is
preserved (as §4 requires), but the magnitude falls by a further **54%** relative
to the full-cross-section residual `[VERIFIED — results.json
vol_decile_pooled_residual]` `[DERIVED — 1 − 0.0533/0.1161 = 0.541]`. The sign
check passes; it does not rescue the arm. Note its own limit: at ~13 names per
volatility decile the within-bucket `k = round(0.10 × 13) = 1`, so this is a
single-name pick per bucket and is noisy by construction
`[DERIVED — median 128 names / 10 buckets]`. §7 does not make it a VOID
condition and it is report-only.

### 4.1 Which way does the explanation run? (the asymmetry test)

`corr(u, |z(vol_60_tr)|) = +0.4066` pooled, mean per-date `R² = 0.183`
`[VERIFIED — tools/goal7_stage1_postreview_diagnostics.py, postreview_diagnostics.json]`.
That is **not** enough to say `u` "is" a volatility ranking — volatility
explains under a fifth of it. The claim §4 actually needs is narrower and
stronger: that *the part of `u` that pays* is the vol-loaded part. The
adversarial review (§10, finding 4) demanded the test that decides it, and it
was re-measured independently here through the identical harness:

| score (same window, same label, same estimator) | spread | `t` | clears 2.1098 |
|---|---|---|---|
| `u = \|z(mom_12_1_tr)\|` — registered treatment | +0.2381 | +3.270 | yes |
| `u` ⟂ `\|z(vol_60_tr)\|` — **registered §4 kill** | +0.1161 | +1.644 | **no** |
| `z(vol_60_tr)` alone | **+0.3477** | **+4.610** | yes |
| `\|z(vol_60_tr)\|` alone | +0.2728 | +3.911 | yes |
| `z(vol_60_tr)` ⟂ `u` | **+0.2300** | **+2.597** | **yes** |
| `\|z(vol_60_tr)\|` ⟂ `u` | +0.1440 | +2.105 | no (marginal) |

`[VERIFIED — tools/goal7_stage1_postreview_diagnostics.py, this session;
independently reproduced by the §10 review]`

**The asymmetry is the finding.** A plain high-volatility sort out-earns the
two-sided momentum transform on the transform's own estimand, and volatility
**survives** being orthogonalised to `u` while `u` **does not** survive being
orthogonalised to volatility. That is the same signature §4 cites from the
prod-XGB/STD60 precedent, reproduced on this corpus, and it closes the obvious
objection to the kill condition — "the control is a mediator, so the kill is
unfair" — with a measurement rather than an assertion.

These six rows are **post-verdict diagnostics, not registered arms.** They were
computed after the verdict was committed (97245c2), none of them is a two-sided
transform, and none of them could have produced a pass for the registered
hypothesis. They are reported because §8's review required them.

---

## 5 Controls

| control | requirement | realised | |
|---|---|---|---|
| positive control construction (§5.1) | `\|mean per-date Spearman IC − 0.05\| ≤ 0.01`, **α never re-calibrated** | mean IC = **+0.044347**, dev **0.005653** | PASS |
| positive control power (§5) | must clear `T_crit` | `\|t\| = 8.137 ≥ 2.1098` | PASS |
| null control (§5) | false-pass rate ≤ **10%** | **4.5%** (raw harness), **5.0%** (residual harness) | PASS |
| non-tautology (§5.1) | permutation changes the statistic on ≥95% of dates | **100.0000%** | PASS |
| within-date permutation (§6) | must be **proven to reject** an unsorted frame | the known-broken lexsort implementation is rejected on seeds 0–5 on both a 4-row and a 77-row interleaved frame | PASS |
| input digests (§2A) | abort on mismatch | both match | PASS |
| dividend adjustment (§6) | cited, not re-assumed | ex-dividend-day gap **−66.6bp (t=−20.6) → −4.8bp (t=−1.55)** `[VERIFIED — prior work, model#110 §4]` | cited |

Every figure in the table above `[VERIFIED — results.json
positive_control_construction / T_crit / non_tautology / selfcheck_shuffle /
pins; run.log]`, except the dividend-adjustment row, which is tagged in place.

`α = 2·sin(π·0.05/6) = 0.0523538966`, and `(6/π)·asin(α/2) = 0.0500000000`
`[VERIFIED — run.log §5.1]`.

**One thing the control got away with, stated because it nearly voided the run
for a reason unrelated to the data.** §5.1's `α` inverts the *asymptotic*
Spearman–Pearson relation, but the registered construction builds `u_pc` from
**normal scores** (a permutation of a fixed vector), and that construction is
downward-biased at finite cross-section width:

| cross-section width `n` | mean per-date Spearman IC of `u_pc` | MC draws / s.e. |
|---|---|---|
| 31 | **+0.02122** | 20,000 / ±0.00129 |
| **128 (this corpus's median)** | **+0.04149** | 20,000 / ±0.00062 |
| 512 | **+0.04841** | 20,000 / ±0.00031 |
| 4096 | **+0.04962** | 3,000 / ±0.00029 |

`[VERIFIED — tools/goal7_stage1_postreview_diagnostics.py, postreview_diagnostics.json,
this session]`

The realised **+0.044347** cleared the ±0.01 tolerance with **0.0043** of margin
`[VERIFIED — results.json positive_control_construction]`. **That margin was
luck, and the size of the luck is measurable.** At width 128 the *expected* mean
IC is 0.04149 with a standard error over 1080 dates of 0.00268, so the expected
margin above the VOID floor of 0.040 was only ≈0.0015, and the prior probability
that this correctly-implemented run VOIDed on the construction's own artifact
was **≈29%** `[DERIVED — Φ((0.040 − 0.04149)/0.00268) + Φ̄((0.060 − 0.04149)/0.00268),
postreview_diagnostics.json]`. The §10 review put the same quantity at ≈21%
using its own Monte-Carlo estimate of the expected mean (0.04220); the two
differ only through Monte-Carlo error in that mean, and the conclusion — roughly
a one-in-four chance of a spurious VOID — is the same either way. On a narrower
cross-section the *same, correct* code VOIDs outright (at `n = 31` the deviation
is 0.029 against a 0.010 tolerance). That is a defect in the registered
constant, not in the run, and it is reported rather than fixed — §5.1 forbids
adjusting `α`, and adjusting it after seeing the number is exactly what the
clause exists to prevent.

---

## 6 Sensitivity: the one ambiguity in the frozen text that had to be resolved

§3 says "the mean forward **excess return** of the top-`k` names … minus the
cross-sectional mean". §0's motivating decile table, §4's quoted "+0.2534 SD"
and every number in the document are in units of the **per-date z-scored**
label. Those are two different objects (the z-scored one reweights each date by
`1/sd_t`), and the document does not disambiguate them.

**Pre-committed in the runner before the run** (`LABEL_PRIMARY = "z"`): the
z-scored label is primary, on the ground that it is the object §0 measured. The
raw-excess-return reading was computed in full alongside, with its own 200-
permutation null and its own `T_crit`, so neither reading is hidden:

| arm | primary label (z-scored) | secondary label (raw excess return) |
|---|---|---|
| treatment `u`, raw | +0.2381 SD, `\|t\| = 3.270`, **clears** | +0.0580, `\|t\| = 3.440`, **clears** |
| treatment `u`, **§4 residual** | +0.1161 SD, `\|t\| = 1.644`, **fails** | +0.0345, `\|t\| = 1.990`, **fails** |
| reference `z(mom)` | +0.2116 SD, `\|t\| = 2.009`, fails | +0.0553, `\|t\| = 2.069`, fails |
| positive control | `\|t\| = 8.137`, clears | `\|t\| = 7.133`, clears |
| `T_crit` (both harnesses) | 2.1098, Student-t leg binds | 2.1098, Student-t leg binds |

`[VERIFIED — results.json arms.z / arms.raw]`

**The verdict is identical under both readings: VOLATILITY-TILT.** The choice of
label does not move it.

---

## 7 Verdict, against §7's table

| outcome | condition | met? |
|---|---|---|
| TWO-SIDED-SUPPORTED | `\|t\| ≥ T_crit` **after** §4 orthogonalisation, controls valid | **no** — 1.644 < 2.1098 |
| **VOLATILITY-TILT** | raw arm clears but the §4 residual does not | **YES** — 3.270 ≥ 2.1098, 1.644 < 2.1098 |
| UNRESOLVED | `\|t\| < T_crit` | n/a |
| VOID | any control fails, digest mismatch, false-pass > 10%, non-tautology fails, `n_blocks < 6` | no — every gate passed |

> ### VOLATILITY-TILT
>
> The two-sided transform's apparent edge on 2016-12-29 → 2021-04-19 is not
> separable from a volatility ranking. `|z|` of 12-1 momentum is large where the
> cross-section is dispersed; orthogonalising it to `|z(vol_60_tr)|` per date
> removes **51%** of the spread (+0.2381 → +0.1161 SD) and **half** the `t`
> (3.270 → 1.644), leaving a statistic that a permutation of `u` beats **12.5%**
> of the time `[DERIVED — 1 − 0.1161/0.2381 = 0.512; 1 − 1.6437/3.2702 = 0.497;
> 1 − 0.875 = 0.125, from results.json arms.z]`. §4 registers this as a kill
> condition, so the verdict stands **whatever the raw arm says**.
>
> **Nothing is licensed.** Not a Stage-2 design, not a scorer, not a config,
> artifact, state or launchd change, not capital. The ten-factor budget is
> unspent.

Worth recording because it is the document's own prediction: §7 said
"**VOLATILITY-TILT is the outcome I expect to have to report if the raw arm
looks good**", and registered it as a distinct verdict precisely so it could not
be narrated away. It was not.

Two further observations, neither of which changes anything:

* the **reference** linear arm `z(mom_12_1_tr)` also fails (`|t| = 2.009 <
  2.1098`), so §0's claim that the linear statistic is weak on this corpus is
  not contradicted — but the two-sided transform does not survive the control
  that the linear one was never subjected to;
* the raw two-sided arm beats the linear reference (+0.2381 vs +0.2116 SD), and
  that gap is exactly what §4 attributes to dispersion. §5 explicitly says
  beating the linear arm is **not** a bar.

**And the limit the document places on any positive result applies a fortiori
here:** this window is 2016-12-29 → 2021-04-19. Even a pass would have been
"SCREEN-INTERESTING on a pre-2021 regime" (A2.3), not a claim about the regime
the book trades today.

---

## 8 What could not be satisfied, stated plainly

0. **THE RESIDUAL ARM WAS UNDERPOWERED AGAINST THE EFFECT IT OBSERVED, and this
   is the most important limitation in the list.** With `n_blocks = 18` and a
   residual block sd of 0.29972, the smallest spread that could have cleared the
   Student-t leg is **MDE = 2.1098 × 0.29972 / √18 = 0.1490 SD**. The observed
   residual spread is **0.1161 SD = 77.9% of the MDE**, and the design's power
   against a true effect of exactly that size is **34.2%**. Equivalently: the §4
   kill condition as calibrated demanded the residual retain **≥62.6%** of the
   raw arm's spread; it retained **48.8%**
   `[VERIFIED — tools/goal7_stage1_postreview_diagnostics.py,
   postreview_diagnostics.json.power, this session; noncentral-t, ncp 1.6437,
   df 17]`. **So "the residual did not clear" and "the residual is a real
   0.116 SD effect this window could not see" are NOT distinguishable here.**
   The verdict is the registered rule's own output, correctly applied — but it
   is a decision under a pre-committed bar, not an identification. This was
   raised by the §10 review (finding 7) and the document did not carry it
   before.
1. **§6's fourth self-check is void, not skipped.** It asks for "the
   screen/holdout partition … with a 60-trading-day embargo, and the embargoed
   row count". A4.2 voids the 60-day embargo for this design (there is no second
   partition for an embargo to separate). The equivalent quantity is reported
   instead: the excluded band of **120 dates / 16,226 rows**, 2021-04-20 →
   2021-10-07 `[VERIFIED — results.json partition.excluded_band_dates /
   excluded_band_rows]`, excluded because their labels would be built from
   burned returns.
2. **The §3 label ambiguity** (§6 above) had to be resolved by a pre-commitment
   rather than by the frozen text. Both readings are reported; the verdict is
   the same under each.
3. **The §5.1 positive-control constant is mis-calibrated at finite `n`** (§5
   above). It passed here with 0.0043 of margin, by a property of this corpus's
   width rather than by design.
4. **The residual risk §2 named cannot be removed.** The U-shape was observed on
   the full sample; this window is carved from that same sample. A2.3 states the
   price and it is unchanged by the outcome.
5. **`n_blocks = 18` is the whole sample.** A VOLATILITY-TILT verdict at 18
   blocks is a statement about this window and this control, not a proof that no
   two-sided effect exists anywhere. The window is now spent — §2's "used ONCE"
   binds, and re-testing this hypothesis needs dates outside this corpus.
6. **No control here certifies that the harness can detect a U-SHAPE.** §5.1
   says so explicitly ("no control here does, and the report must not claim
   it"), the positive control `u_pc` is monotone, and this document does not
   claim otherwise — but the limitation belongs in this list and was missing
   until the §10 review flagged it (finding 10). The mitigant is empirical: the
   raw arm cleared at `|t| = 3.27` *using the two-sided score itself*, so the
   machinery demonstrably registers a `u`-driven effect.
7. **The registered null does not preserve the score's persistence** (§3 above,
   §10 finding 5). It is anti-conservative for a score with lag-1
   autocorrelation 0.94. The kill leg is unaffected; the raw leg's `|t|`
   quantile is not a robust p-value.
8. **On this window the motivating U-shape is much flatter than §0's
   full-sample profile.** The §10 review re-measured the decile profile here as
   `+0.102 −0.008 −0.082 −0.098 −0.071 −0.046 −0.030 +0.019 +0.013 +0.196`
   against §0's `+0.135 … +0.375`, with `u`'s top decile 63.9% winners / 36.1%
   losers `[VERIFIED — prior work, §10 adversarial review finding 10]`. The
   "two-sided" framing is doing less work on the uncontaminated window than §0
   implies — which is itself what §2's HARKing warning predicted.
9. **`run.log` is a transcription, not a live tee.** It was copied into the
   results directory after `results.json` was written (§10 finding 13). Every
   number in it that also appears in `results.json` matches, and the two claims
   sourced only to it (`corr = +0.4066`, `0 of 145 tickers gapped`) were
   independently re-derived by the reviewer. It is not independent evidence.
10. **A gate that could not fail.** The runner's `input_digests_match` gate was
    a literal `True` in the gates dict (§10 finding 14) — the real enforcement
    is `check_pin()`, which aborts, and both digests do match. This is the
    "guard that validates the wrong object" shape, and it is repaired in a
    follow-up commit that changes no statistic. **The code that produced
    `results.json` is the version committed at `97245c2`**, unmodified since the
    run.

---

## 9 Suite

| tree | result |
|---|---|
| `origin/main` @ `6658078` (the branch point, separate worktree) | **1047 passed, 2 skipped** |
| `origin/main` @ `5ea9450` (re-measured after the tip moved mid-run) | **1047 passed, 2 skipped** |
| this branch | **1058 passed, 2 skipped** (+11 = `tests/test_goal7_stage1_estimator.py`) |

`[VERIFIED — make test PYTHON=<RenQuant venv python>, both trees, this session]`

`origin/main` advanced from `6658078` to `5ea9450` while this run was in
progress (a concurrent automated loop is active on this repo). The two commits
are docs-only — `doc/research/data/2026-07-29-clf-wf-closure-bundle/{README.md,
bundle_index.json}` — and touch no code, no test and nothing this study reads
`[VERIFIED — git diff --stat 6658078..5ea9450]`. The baseline was re-measured at
the new tip anyway rather than assumed unchanged.

---

## 10 Adversarial review (§8) — appended verbatim with its disposition

The review below was **commissioned adversarially** — the reviewer was
instructed to destroy the conclusion if it could be destroyed, was given the
frozen prereg, the runner, the raw output and the pinned corpus, and was told
that two verdicts on this programme have already been retracted by exactly this
procedure. It is reproduced **VERBATIM and unedited**. My disposition follows
it, item by item.

<!-- ADVERSARIAL-REVIEW-BEGIN -->

# Adversarial review — GOAL-7 Stage 1 (commissioned under §8)

**Reviewed artifacts** (worktree `/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/g7run-62780`): the frozen prereg (all 642 lines, Amendments 2 / 3-a / 3-b / 4), `tools/goal7_stage1_two_sided_run.py`, `tests/test_goal7_stage1_estimator.py`, `doc/research/data/2026-07-30-goal7-stage1-two-sided-tail/{results.json,run.log}`, and the results document at sha256 `1dfb550c1f3b…`, 310 lines (the document was edited under me mid-review — I first read a 282-line version; the two additions, §3's bootstrap paragraph and §4's block-mean sign counts, are both checked below and both correct).

## Bottom line

**The VOLATILITY-TILT verdict survives. I found no FATAL defect and no deviation between the registered object and the executed one.** I re-implemented the entire estimand independently from the pinned parquets — my own label build, my own per-date OLS via `numpy.linalg.lstsq`, my own pandas group-by selection loop — and reproduced every headline to six decimal places: raw arm `+0.238124 / t=+3.270184`, §4 residual `+0.116120 / t=+1.643724`, reference `+0.211593 / t=+2.009184`, and both secondary-label arms. The A4.2 partition reproduces exactly (1082 / 18 / 2, dropped `2021-04-16` and `2021-04-19`) and the burn separation is exactly tight and not breached. Two attacks land as MATERIAL. First, the **kill leg is stronger than the document argues** — I ran the asymmetry test the document never ran, and it identifies the direction of explanation: a single sort on `z(vol_60_tr)` pays **+0.3477 SD, `t=+4.61`** — *more* than the two-sided momentum arm — and volatility **survives** being orthogonalised to `u` (`+0.2300, t=+2.60`, clears) while `u` **dies** when orthogonalised to volatility. Second, the **raw leg is weaker than the document's `0.990` null quantile implies**: the registered within-date permutation null destroys `u`'s cross-date persistence, and under two persistence-preserving nulls the raw arm's p-value is 0.044 and 0.24 rather than 0.010. That can only move VOLATILITY-TILT toward UNRESOLVED — both license nothing — and it cannot rescue the two-sided hypothesis, which dies harder under every calibration I tried. Separately, the document **omits a power statement it should carry**: the residual arm's minimum detectable spread was 0.1490 SD and it observed 0.1161 SD, so the design had **34% power** against the effect it actually measured.

## Findings

### 1. CLEARED — the executed object is the registered object

I checked the runner line-by-line against the frozen text. Every registered element matches:

| registered | runner | checked |
|---|---|---|
| §1 `u = |z_t(mom_12_1_tr)|` | L391 `np.abs(p.gz(mom))`, `gz` ddof=1 (L137-145) | reproduced |
| §2A eligibility (mom & vol non-null, label exists, ≥20 names) | L308-311 | reproduced: 1082 dates, min 126 names |
| §3 `k = round(0.10·n)`, `k ≥ 1` | L127 | realised `k ∈ {13,14}`; `np.round`'s banker's tie-break is never exercised (no `n` gives `0.1n` a `.5` at a half-even boundary — I checked `int(round(n/10))==floor(n/10+0.5)` on every realised `n`) |
| §3 estimand = top-k mean **minus the cross-sectional mean** | L151-160 | pinned by `test_top_spread_is_versus_the_cross_sectional_mean_not_the_complement`; my naive loop agrees to 1e-12 |
| §4 tie-break ascending ticker | L149 `np.lexsort((ticker_code, -score, date_code))`, `factorize(sort=True)` | correct key order (last key is primary) |
| §4 per-date OLS **with intercept** | L162-173 | equals `lstsq` on `[1, x]` per date, ≤1e-10; residual ⊥ regressor within date |
| §3 blocks of 60, contiguous, **remainder dropped** | L176-185 | `poisoned` test proves the tail enters at zero weight; matches `scipy.ttest_1samp` |
| §3 `T_crit = max(P95_null, t_{0.975,n_b−1})`, 200 within-date permutations | L434-470, L380-384 | `t.ppf(0.975,17) = 2.1098155778`, pin-checked and aborting |
| §5.1 `α = 2·sin(π·0.05/6)`, seed `20260730 + YYYYMMDD`, normal scores with ticker tie-break | L79, L188-196, L403-410 | `(6/π)·asin(α/2) = 0.05` exactly |
| §7 VOID list (6 conditions) | L549-555 | all six present |

The prereg was frozen in git **before** the run and I can date it: `9df1a28` at 07:54:04, merged as `1d7bf70` at 07:58:49; `results.json` was written at 08:46:29. The design was 48 minutes cold when the run started.

### 2. CLEARED — partition and burn separation, verified independently and found exactly tight

Recomputed from the corpus's own trading-day index without reference to the runner: the last `t` whose 120th following corpus day precedes 2021-10-08 is **2021-04-19** (120th day `2021-10-07`); the *next* candidate, 2021-04-20, lands on **2021-10-08 itself** — the boundary is not merely satisfied, it is saturated. `N_eval = 1082`, `n_blocks = 18`, remainder 2 (`2021-04-16`, `2021-04-19`), block span end `2021-04-15`, eval rows 140,134, names/date min 126 / median 128 / max 135, zero dates lost to the `<20` rule, excluded band 120 dates / **16,226 rows** — all identical to A4.4 and to `results.json`.

**Does any evaluation date's label reach the burn?** No. Max label end over all 1082 eval dates = `2021-10-07`; over the 1080 *used* dates = `2021-10-05`. I also re-verified the contiguity premise that makes a 120-row shift a 120-trading-day window: **0 of 145 tickers** have an interior gap in the corpus calendar. And both input digests re-hash to the §2A pins (`85c27fc1…`, `8c23496e…`).

### 3. CLEARED — the §4 residual arm is a fair test, not a rigged one

I attacked this four ways and it holds:

* **Collinearity is moderate, not destructive.** `corr(u, |z(vol_60_tr)|) = +0.40656` pooled (I reproduce the runner's `+0.4066`); **mean per-date R² = 0.183**, so residualisation leaves **82% of `u`'s within-date variance** intact. Nothing is mechanically annihilated.
* **The residual top decile is not degenerate.** Mean overlap with the raw top decile is **72.6%** (min 21.4%, max 100%); **110 distinct names** are ever selected by the residual arm versus 100 by the raw arm, out of a 135-name universe. It is a *wider*, not a narrower, selection.
* **The collapse is in the mean, not the variance.** Block sd is essentially unchanged (0.30894 raw → 0.29972 residual, −3%); the spread falls 51%. The `t` drop is entirely signal loss, not noise inflation.
* **The control does not over-remove.** The residual arm's picks still sit at the **72.7th** volatility percentile on average (raw arm: 81.4th). The orthogonalisation removes part of the vol tilt, not all of it — if anything the control is *lenient*.

### 4. CLEARED, and the document under-argues its own case — the asymmetry test identifies the direction of explanation

The document justifies VOLATILITY-TILT with one number (`corr = +0.4066`). That is the weakest available argument. The decisive test — which the prereg does not require and the document does not run — is whether the explanation runs the other way. It does not:

| score (same harness, same window, same label) | spread | `t` | clears 2.1098 |
|---|---|---|---|
| `u = |z(mom_12_1_tr)|` | +0.2381 | +3.270 | yes |
| `u` ⟂ `|z(vol_60_tr)|` (registered kill) | +0.1161 | +1.644 | **no** |
| **`z(vol_60_tr)` alone** | **+0.3477** | **+4.610** | **yes** |
| `|z(vol_60_tr)|` alone | +0.2728 | +3.911 | yes |
| **`z(vol_60_tr)` ⟂ `u`** | **+0.2300** | **+2.597** | **yes** |
| `|z(vol_60_tr)|` ⟂ `u` | +0.1440 | +2.105 | marginal |

A plain high-volatility sort out-earns the two-sided momentum transform on its own estimand, and volatility **survives** being orthogonalised to `u` while `u` does not survive being orthogonalised to volatility. That is the same signature §4 cites from the prod-XGB/STD60 precedent, reproduced here on this corpus. This closes the "the control is a mediator, so the kill is unfair" objection empirically rather than by assertion. **Recommend adding this table to §4 of the results document.**

### 5. MATERIAL — the registered null control cannot calibrate a persistent score, and the *raw* leg depends on it

`u`'s per-date statistic has lag-1 autocorrelation **0.9405** and remains **0.47** at lag 20; the 120-day label overlaps 2 consecutive 60-day blocks. The registered null — an independent within-date permutation of `u` (L437) — destroys exactly that persistence, so it calibrates a *different* estimator than the one the treatment arm uses. I measured the gap on a balanced panel (1082 dates × 126 tickers present on every date), 500 draws each:

| null | preserves persistence? | P95 of `|t|`, raw arm | perm-p for the raw arm |
|---|---|---|---|
| within-date permutation (**registered**) | no | 1.97 | ~0.01 |
| one global ticker relabel applied to every date | yes | **3.235** | **0.044** |
| circular date-rotation of the score panel | yes | **5.608** | **0.240** |

(Balanced-panel baseline: raw `|t| = 3.345`, residual `|t| = 1.579`.)

So the document's headline "`|t|` as a quantile of the null = **0.990**" for the raw arm is an artifact of a null that is easier than the arm it certifies. Two mitigations, both of which I ran and which stop this short of fatal: parametric HAC corrections leave the raw arm clearing (Newey-West on the 1080-date series: `t = +3.22` at lag 60, `+2.92` at lag 120), and every alternative block length that keeps `n_blocks ≥ 6` also clears (`B=90 → 2.714`, `B=120 → 3.380`, `B=180 → 4.087`). The block-mean lag-1 autocorrelation is only **+0.224**, which is why the damage is bounded.

**Consequences, stated exactly.** (a) The **kill leg is untouched**: `T_crit = max(P95_null, 2.1098) ≥ 2.1098 > 1.644` unconditionally, and under both persistence-preserving nulls the residual arm's p-value is 0.30 and 0.39 — it fails harder, not softer. (b) The **raw leg is fragile**: it is what selects VOLATILITY-TILT over UNRESOLVED under §7, and under a null that respects persistence it is marginal (p = 0.044) or absent (p = 0.24). (c) This is a defect in the *registered design*, not in the execution — the runner implemented §3/§5 as written. (d) It cannot rescue the hypothesis: the only direction it moves the verdict is toward UNRESOLVED, which also licenses nothing. **Recommend the document state that its raw-arm null quantile is conditional on a null that removes the score's persistence, and that the raw arm's clearance is therefore a statement about the registered bar rather than a robust finding.**

### 6. MATERIAL — "largely a dispersion ranking" overstates `corr = +0.4066`

Results §4 line 159: *"`|z|` of momentum really is **largely** a dispersion ranking on this corpus"*, sourced to `corr = +0.4066`. That correlation implies **R² = 0.165 pooled / 0.183 per date** — volatility explains under a fifth of `u`. The correct statement is that the *part of `u` that pays* is largely the vol-loaded part (which finding 4 establishes properly), not that `u` largely *is* volatility. As written it is the narrative overshooting the number, in the direction that makes the kill look inevitable.

### 7. MATERIAL — the document never states that the residual arm was underpowered against the effect it observed

With `n_blocks = 18` and residual block sd 0.29972, the smallest spread that could have cleared the Student-t leg is

> **MDE = 2.1098 × 0.29972 / √18 = 0.1490 SD** `[DERIVED — results.json arms.z.treatment_u_residualised.block_sd, t.ppf(0.975,17)]`

The observed residual spread is **0.1161 SD = 77.9% of the MDE**, and the design's power against a *true* effect of exactly that size is **34.2%** (noncentral-t, ncp 1.6437, df 17). Equivalently: the §4 kill condition, as calibrated, demanded that the residual retain **≥62.6%** of the raw arm's spread; it retained **48.8%**. So "the residual does not clear" and "the residual is a real 0.116 SD effect the design could not see" are not distinguishable on this window. §8.5 gestures at this (*"not a proof that no two-sided effect exists anywhere"*) but gives no number, and §7's blockquote reads as a positive identification. **Recommend §8.5 carry the MDE, the 78%-of-MDE ratio and the 34% power figure explicitly.** This is an under-disclosure of uncertainty, not an overclaim of result — the verdict itself is the registered rule's own output and is correctly applied.

### 8. CLEARED — the label pre-commitment is real enough, and nothing turns on it

I recomputed the secondary reading from scratch: raw excess-return label gives treatment `+0.058024 / t=+3.440006` (clears), residual `+0.034548 / t=+1.989892` (fails), reference `+0.055256 / t=+2.069008` (fails) — matching `results.json` exactly. **The verdict is VOLATILITY-TILT under both readings**, so the choice of primary label is decision-irrelevant and the HARK surface is nil.

On the pre-commitment itself: the runner is **uncommitted** (`git status`: `A tools/goal7_stage1_two_sided_run.py`), so there is no VCS proof that `LABEL_PRIMARY = "z"` predates the run. The circumstantial case is consistent: the runner's mtime is `08:45:53`, `results.json` `08:46:29` — a 36-second window, and I timed the runner's workload on this machine at **≈19 s** for the dominant pieces (sha256 both pins 0.03 s, both parquet reads 0.10 s, label build 0.09 s, the 200-permutation loop 18.9 s), leaving room for the sibling `build_labels` and the manifest verify. It fits. I record it as unprovable-but-consistent, and moot given the invariance.

The document's §1 identity claim also checks out arithmetically: 346,807 paired rows is the full corpus minus ≈145×120 unlabelled tail rows.

### 9. CLEARED, with one correction and one number the document should add — the positive control's finite-`n` bias

I Monte-Carlo'd the exact §5.1 construction myself (fresh code: `w` = the fixed normal-score grid in return order, `e` = the same grid randomly permuted, `u_pc = αw + √(1−α²)e`, Spearman against the return ranks):

| `n` | my MC mean IC (dates, MC s.e.) | document |
|---|---|---|
| 31 | **0.02079** (20,000; ±0.00128) | +0.020 ✔ |
| 128 | **0.04220** (20,000; ±0.00063) / 0.04321 (5,000) | +0.043 ✔ |
| 512 | **0.04767** (5,000; ±0.00061) | +0.049 — **≈2 MC-σ high; should read +0.048** |
| 4096 | **0.04976** (3,000; ±0.00028) | +0.050 ✔ |

So the document's characterisation is correct in direction and essentially correct in magnitude, and its claim that a narrower cross-section would have VOIDed the screen is confirmed (at `n = 31` the deviation is 0.029 against a 0.010 tolerance). Its tag `[VERIFIED — Monte-Carlo …, 20,000/5,000/3,000 dates per width…]` lists three date-counts for four widths — under-specified.

**The document understates the danger.** At this corpus's width the *expected* mean IC is 0.0422 with a 1080-date standard error of 0.00271, so the expected margin above the 0.040 VOID floor was **0.0022, not the realised 0.0043**, and the prior probability that this correctly-implemented run VOIDed on a construction artifact was **≈21%** `[DERIVED — Φ((0.040−0.04220)/0.00271)]`. The realised +0.044347 sits 0.79 s.e. above expectation — it got lucky. **Recommend §8.3 carry the 21%.**

### 10. MINOR — the missing U-shape control is not claimed, but not disclosed either

§5.1 of the prereg states that `u_pc` *"does not certify that the harness can detect a U-shape; no control here does, and the report must not claim it."* The results document does not claim it — I checked every control statement — but §8's otherwise-complete limitations list omits it. Mitigant, which is why this is MINOR rather than MATERIAL: the raw arm cleared at `|t| = 3.27` **using the two-sided score itself**, which demonstrates empirically that the machinery registers a `u`-driven effect; the positive control only ever had to certify the blocking and `T_crit`.

Relatedly, and worth adding because it *strengthens* the negative verdict: on the uncontaminated window the motivating U-shape is much flatter than §0's full-sample profile. Re-measured by `z(mom_12_1_tr)` decile, the label profile here is `+0.102 −0.008 −0.082 −0.098 −0.071 −0.046 −0.030 +0.019 +0.013 +0.196` against §0's `+0.135 … +0.375`, the losers-only arm (`−z(mom)` top decile) is `+0.0892, t=+0.719`, and `u`'s top decile is **63.9% winners / 36.1% losers** paying `+0.284` and `+0.104` respectively. The "two-sided" framing is doing less work on this window than §0 implies — which is itself consistent with the HARKing risk §2 named.

### 11. CLEARED — the null / `T_crit` arithmetic, including the document's new bootstrap paragraph

I reproduced §3's newly added bootstrap exactly from `results.json`'s stored 200 draws (5,000 resamples): raw-harness P95 CI **[1.8243, 2.4540]** (doc: [1.824, 2.454]), residual **[1.7596, 2.2443]** (doc: [1.760, 2.244]), P(bootstrap P95 > 2.1098) = **30.4% / 42.3%** (doc: 30%/42%), largest single null draw **3.2897** (doc: 3.290). P(bootstrap P95 > 3.2702) = **0.0000** over 5,000 resamples. The document's reasoning is right: the Student-t leg is a floor, so the residual arm fails under every realisation, and the raw arm would need P95 > 3.270.

**The false-pass rate is not a tautology**, and it is worth saying why: because the t-leg bound `T_crit` in both harnesses, the rate is measured against a value *not* estimated from the same draws. 9/200 and 10/200 draws exceed 2.1098 → 4.5% (exact 95% CI 2.08–8.37%) and 5.0% (2.42–9.00%) against a 5% nominal. That is a genuine, passing calibration check of the Student-t leg — **under the permutation null only** (see finding 5). Had P95 bound, the same figure would have been ≈5% by construction; the runner's separate reporting of `false_pass_rate_vs_t_student` is the right design.

Two arm-level readings the document should keep in view: the raw arm's permutation p-value is **2/200 = 1.0%**, not vanishing, and the residual arm's is **25/200 = 12.5%**.

### 12. MINOR — provenance-tag defects

No illegal tag forms are present: I grepped for `[VERIFIED-now]`, `[VERIFIED-prior]`, bare `[VERIFIED]`, bare `[DERIVED]` and bare `[ASSUMED]` — zero hits. Remaining defects:

1. **§5's controls table carries no tag at all** (lines 167-175): `+0.044347`, `0.005653`, `|t| = 8.137`, `4.5%`, `5.0%`, `100.0000%` are all untagged measured numbers. All six are true — I verified each against `results.json` — but the house rule requires the tag.
2. **Line 117, `3.290 [VERIFIED — same bootstrap]` is mis-attributed.** 3.290 is `max(all_abs_t)` over the 200 stored draws, not an output of the bootstrap.
3. **Line 108's wording is an inferential slip**: *"the probability that the true P95 exceeds the Student-t leg is 30%/42%"* is a bootstrap frequency of the *estimator*, not a probability statement about the true quantile.
4. §8's `0.0043 of margin` and the repeated `120 dates / 16,226 rows` are untagged where they appear (both are tagged elsewhere in the document).
5. Line 140-142: *"more than one draw in eight"* — 25/200 is **exactly** one in eight.

### 13. MINOR — `run.log` is a transcription, not a live tee

`run.log`'s mtime is `08:49:54`, **3 m 25 s after** `results.json` (`08:46:29`), so it was saved after the fact rather than written by the process that produced `results.json`. Every number in it that also appears in `results.json` matches. Two claims the document sources *only* to `run.log` I therefore re-derived myself rather than trusting: `corr(u, |z(vol_60_tr)|) = +0.4065562` ✔ and `0 of 145 tickers have interior calendar gaps` ✔. Nothing turns on it, but `run.log` is not independent evidence.

### 14. MINOR — a gate that cannot fail, and a pedantic burn-window touch

* Runner L552 sets `"input_digests_match": True` as a **literal constant** in the gates dict. It cannot fail as written; the real enforcement is `check_pin()` aborting at L104-109. This is the "guard that validates the wrong object" shape the programme has been bitten by six times. Immaterial here — I re-hashed both files and they match — but the gate should read from the pin check.
* A2.2 forbids the burned period *"in any arm, including descriptive ones."* Two lines technically touch it: the label-identity check (346,807 paired rows spans the corpus to 2026-07-29) and `R["corpus"]`'s reported extent. Both are plumbing identities carrying zero information about the hypothesis, and no statistic in any arm reads a post-burn date. I record it, I do not fault it.

### 15. CLEARED — the estimator test suite

`tests/test_goal7_stage1_estimator.py`: **11 passed in 0.94 s** (run with `PYTHONDONTWRITEBYTECODE=1 … -p no:cacheprovider`, nothing written). The two tests that would have caught a silently-different statistic — top-minus-cross-sectional-mean versus top-minus-rest, and the ascending-ticker tie-break — both pin the correct object, and my independent naive-loop implementation agrees with `Panel.top_spread` to 1e-12.

### 16. CLEARED — the two "AMENDMENT 3" sections were not used

The runner pins A4.4's values (L54-63) and cites A4.2 as the cutoff rule (L251-258); no 60-day and no 120-day *embargo band* is constructed anywhere. §8.1's disposal of §6's fourth self-check (the embargoed row count) as voided-and-replaced-by-the-120-date-excluded-band is the correct reading of A4.2/A4.6. The 120-date band is reported as a consequence, exactly as A4.4 frames it.

### 17. CLEARED — the §4 pooling addendum

`+0.053290 / |t| = 0.861` (primary) and `+0.021808 / |t| = 1.328` (secondary), both reproduced independently; sign preserved, as §4 requires. Note that with ~13 names per volatility decile the within-bucket `k = round(0.1·13) = 1`, so the pooled statistic is a single-name pick per bucket — noisier by construction. §7 does not make this a VOID condition, and the runner correctly treats it as report-only.

## What I could not check

* **The §9 suite counts (1047 / 1058).** Running `make test` would have written pytest cache and possibly test artifacts, which my read-only mandate forbids. I verified only the 11-test delta file (11 passed) and that 1047 + 11 = 1058.
* **That the runner on disk is byte-identical to the code that produced `results.json`.** The runner is uncommitted, so there is no VCS or hash evidence. The mtime gap (36 s) versus my measured workload (≈19 s of dominant cost) is consistent, and the label pre-commitment is decision-irrelevant regardless (finding 8), but I cannot prove it.
* **The upstream corpus construction.** I verified both parquets against the §2A digests and the manifest fields recorded in `results.json`, but I did not re-derive `mom_12_1_tr`, `vol_60_tr` or `tr_close` from `RenQuant/data/ohlcv/`, and I did not re-run `raw_input_manifest.verify_or_abort()`. The dividend-adjustment validation (−66.6bp → −4.8bp) is cited from model#110 and I took it as given.
* **Whether the two persistence-preserving nulls in finding 5 are themselves correctly sized.** They disagree with each other (p = 0.044 vs 0.24) and with the HAC corrections (which leave the raw arm clearing), and both are my diagnostics, not registered objects. What I can assert is the *gap*: P95 moves from 1.97 to 3.24/5.61 when persistence is preserved, so the registered null is anti-conservative for a persistent score by a wide margin. Sizing the correct bar precisely is beyond what this window supports.
* **Whether the 2016-2021 window generalises.** Not checkable in principle here — A2.3 and results §8.4/§8.5 state the limit correctly and the window is now spent.

## Disposition

**NOT UPHELD as a challenge to the verdict — VOLATILITY-TILT stands.** The kill leg is robust to every attack I ran and is better supported than the document argues (finding 4). Four changes are recommended before merge, none of which alter the verdict: state the MDE/power for the residual arm (7), disclose that the raw arm's null quantile rests on a persistence-destroying null (5), soften "largely a dispersion ranking" (6), and repair the tag defects (12) plus the `n = 512` Monte-Carlo figure (9). Adding the finding-4 asymmetry table would materially strengthen §4.

<!-- ADVERSARIAL-REVIEW-END -->

### 10.1 Disposition (author)

**The review is ACCEPTED IN FULL. It does not overturn the verdict — it makes
the kill leg better supported and the raw leg explicitly weaker, and both
changes are now in the document above.** Every quantitative claim bearing on the
outcome I re-measured myself rather than accepting; the re-measurements are in
`tools/goal7_stage1_postreview_diagnostics.py` and
`doc/research/data/2026-07-30-goal7-stage1-two-sided-tail/postreview_diagnostics.json`.

| finding | grade | disposition |
|---|---|---|
| 1, 2, 3, 8, 11, 15, 16, 17 | CLEARED | No action. The reviewer independently re-implemented the estimand from the pinned parquets and reproduced every headline to six decimals. |
| **4** — asymmetry test; kill leg under-argued | CLEARED + recommendation | **ADOPTED.** Re-measured independently and reproduced the reviewer's numbers exactly: `z(vol_60_tr)` alone +0.3477 / t=+4.610; `z(vol_60_tr) ⟂ u` +0.2300 / t=+2.597 (survives); `\|z(vol_60_tr)\| ⟂ u` +0.1440 / t=+2.105 (does not clear). Added as **§4.1**, marked post-verdict and non-registered. |
| **5** — the registered null destroys the score's persistence | MATERIAL | **ACCEPTED; it makes the RAW leg weaker.** Added to §3 and §8.7. I did NOT adopt either alternative null as the bar: they are unregistered, they disagree with each other (p = 0.044 vs 0.24), and swapping the bar after seeing the result is the exact move prereg discipline exists to forbid. What I adopt is the direction, which is unambiguous: the raw arm's 0.990 quantile is a statement about the registered bar, not a robust p-value. The kill leg is untouched — `T_crit ≥ 2.1098 > 1.644` under every null, and the residual arm fails *harder* under both alternatives. |
| **6** — "largely a dispersion ranking" overstates `corr = +0.4066` | MATERIAL | **ACCEPTED.** I was narrating past my own number: mean per-date R² = 0.183, so volatility explains under a fifth of `u`. The sentence is deleted and replaced by §4.1, which makes the narrower claim the data supports — that the part of `u` that *pays* is the vol-loaded part. |
| **7** — no power statement for the residual arm | MATERIAL | **ACCEPTED, and promoted to item 0 of §8.** Re-measured, identical to the reviewer: MDE 0.1490 SD, observed 0.1161 SD = 77.9% of MDE, power 34.2%, retention required 62.6% vs achieved 48.8%. "Did not clear" and "a real 0.116 SD effect this window could not see" are not distinguishable here, and §8 now leads with that. |
| **9** — positive-control MC and the VOID prior | CLEARED + correction | **ACCEPTED.** Re-ran at 20,000 draws for three of four widths: `n = 512` is **+0.04841 ± 0.00031**, so my "+0.049" was high and is corrected to **+0.048**; the table now carries all four widths with MC standard errors. The reviewer's headline point is adopted: the *expected* margin above the VOID floor was ≈0.0015, not the realised 0.0043. My VOID prior is 29% against the reviewer's 21%; the gap is MC error in the expected mean (0.04149 vs 0.04220) and both are reported. |
| **10** — missing U-shape control undisclosed | MINOR | **ACCEPTED.** Added as §8.6 with the reviewer's mitigant; the flatter on-window decile profile is added as §8.8, cited to the review rather than re-measured by me, and tagged as such. |
| **12** — provenance-tag defects (5 items) | MINOR | **ACCEPTED, all five repaired**: §5's control table now carries a tag; `3.290` is re-attributed to `max(all_abs_t)`; the bootstrap-frequency wording no longer reads as a probability about the true quantile; the excluded-band and 0.0043-margin figures are tagged where they appear; "more than one draw in eight" is corrected to **exactly** one in eight (25/200). |
| **13** — `run.log` is a transcription | MINOR | **ACCEPTED**, disclosed as §8.9. It is not independent evidence and the document no longer implies it is. |
| **14** — `input_digests_match` was a literal `True` | MINOR | **ACCEPTED and FIXED in code.** The gate now reads back from the recorded digests. Disclosed as §8.10, with the fact that matters stated plainly: the fix is post-run and changes no statistic — **the code that produced `results.json` is the version committed at `97245c2`**, unmodified between the run and that commit. The second bullet (label-identity check touching post-burn rows) I accept as recorded-not-faulted: no statistic in any arm reads a post-burn date, and the reviewer independently confirmed the max label end over the 1080 used dates is 2021-10-05. |

**One thing I decline to manufacture.** The review notes it cannot prove the
on-disk runner is byte-identical to the code that produced `results.json`,
because the runner was uncommitted when it read it. I have not produced an
after-the-fact proof. The runner is now in git at `97245c2`; the `LABEL_PRIMARY`
pre-commitment is decision-irrelevant (the verdict is identical under both label
readings); and the reviewer reproduced every headline number from the pinned
parquets with **its own independent implementation**, which is a stronger
guarantee than any hash of mine would have been.

**Verdict after review: VOLATILITY-TILT, unchanged. Nothing licensed.** The
review's own disposition is "NOT UPHELD as a challenge to the verdict", and the
four changes it required before merge are all made.

---

# CORRECTION 1 — the registered inferential unit is invalid (adversarial review, 2026-07-30)

**Accepted.** The reviewer's core finding is correct and it lands on the frozen design,
not the execution: every label is a **120-trading-day** forward return while the
estimator averages **60-trading-day** blocks and treats them as independent. Adjacent
blocks therefore share 60 days of each label horizon, so `n_blocks = 18` is not 18
independent observations, `t_{0.975,17} = 2.1098` is not the right bar, and the
registered within-date permutation null destroys the very temporal dependence the
treatment arm carries — it calibrates a different estimator than the one it certifies.

**This is my defect.** I amended this design twice (Amendments 3 and 4), pinning the
partition, the calendar and the critical value to four decimal places, and did not
notice that a 60-day block against a 120-day label makes the inferential unit invalid.
Both amendments made the *wrong* quantity more precise. Pinning the bar harder does not
help when the bar is computed on the wrong unit — the same guard-validates-the-wrong-
object shape this programme keeps hitting, committed here by the person writing the
guards.

## C1.1 One number in the review is the wrong statistic, and it matters for scope

The review cites *"the reported lag-1 autocorrelation of 0.94"* as confirming the
severity. **0.94 is the autocorrelation of the per-date statistic**, not of the block
means. The quantity that governs whether block means may be treated as independent is
the **block-mean** lag-1 autocorrelation, which is

| arm | block-mean lag-1 autocorrelation |
|---|---:|
| raw `u` | **+0.2311** |
| §4 residual | **+0.2592** |

`[VERIFIED — recomputed from results.json arms.z.*.block_means, this session]`,
consistent with the **+0.224** the results document already reported at L525. The
dependence is real and disqualifying for `df = 17`; it is not 0.94-severe. Recording
this because the correct scope of the remedy depends on it — and because citing a
per-date autocorrelation as if it were a block-mean one is the same class of error as
the defect being corrected.

## C1.2 The direction of the bias, and what survives

Ignoring positive dependence **understates** the variance of the mean, so it
**inflates** `|t|`. Every arm's `t` in this document is therefore optimistic. Applying
a first-order correction, `Var_eff = Var_iid · (1+ρ₁)/(1−ρ₁)`:

| arm | `t` as registered | `ρ₁` (blocks) | `t` dependence-adjusted | vs `T_crit = 2.1098` |
|---|---:|---:|---:|---|
| raw `u` | +3.2702 | +0.2311 | **+2.5843** | still clears |
| §4 residual | +1.6437 | +0.2592 | **+1.2607** | still fails |

`[VERIFIED — computed from results.json block_means, this session]`, and consistent
with the Newey-White/HAC and alternative-block-length checks already reported at L525
(`B=90 → 2.714`, `B=120 → 3.380`, `B=180 → 4.087`; Newey-West `t = +3.22` at lag 60,
`+2.92` at lag 120).

So the *direction* is stable: the kill leg fails under every correction tried, and it
fails **more** once dependence is honoured, because the correction can only shrink
`|t|`. The two-sided hypothesis being unsupported is the robust half.

## C1.3 Why that does NOT rescue the verdict

**A conclusion that survives an unregistered correction is not a preregistered
finding.** The whole value of this document was that its bar was fixed before the run;
if the bar has to be recomputed afterwards — by HAC, by a variance inflation factor, by
re-blocking — then the protection §2 was written to provide is gone, and what remains
is an ordinary post-hoc analysis with the usual degrees of freedom. Reporting
"VOLATILITY-TILT, and it survives corrections I chose after seeing the data" would
claim exactly the credibility the design failed to earn.

**Registered disposition, replacing §7's outcome for this execution:**

> **UNRESOLVED — invalid inferential unit.** VOLATILITY-TILT is **withdrawn** as a
> verdict. This execution licenses **nothing**, may not be cited as a preregistered
> result, and may not be used to support or reject the two-sided hypothesis, the
> volatility-tilt reading, or any Stage-2 work. The dependence-adjusted numbers in
> C1.2 are recorded as diagnostics only and carry no licence of their own.

## C1.4 What a valid Stage 1 requires

Not attempted here, and deliberately not designed on the fly against results already
seen — that is the HARKing failure this line has been fighting since §2:

* blocks whose **label windows** are disjoint (block length ≥ the 120-day horizon, or a
  ≥120-day gap between blocks), costing power that must be budgeted before freezing;
* a null that preserves temporal dependence rather than permuting it away — a
  block/circular bootstrap on the date axis, not a within-date permutation;
* the power calculation redone on whatever inferential unit results, since the current
  one inherits `n = 18` and is void with it.

At the pinned 1,082-date window the arithmetic is unforgiving
`[VERIFIED — computed this session]`:

| rule | `n_blocks` |
|---|---:|
| current: contiguous 60d (labels overlap 2 blocks) | 18 |
| contiguous 120d (labels still reach into the next block) | **9** |
| 120d blocks + 120d gap (label windows genuinely disjoint) | **4** |
| 180d + 120d gap | 3 |

So a genuinely dependence-free design on this window gives **4 blocks**, below §7's
`n_blocks < 6` VOID floor — and 9 only by tolerating the same overlap in weaker form.
The honest expectation is that a valid Stage 1 here is **underpowered by construction**,
which is a finding about the corpus rather than about momentum, and it should be
established at design time rather than discovered as another retraction. This is the
third consecutive line on this programme where the correctly-specified test turns out
not to have the power to run.
