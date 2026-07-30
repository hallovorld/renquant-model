# RESULTS — GOAL-7 Stage 1: is the payoff TWO-SIDED rather than a ranking?

> **VERDICT: VOLATILITY-TILT.** The raw two-sided arm clears its bar
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
sits at the 87.5th percentile of its own permutation null — i.e. more than one
draw in eight of *pure noise* through the identical harness produces a larger
statistic.

Pooling addendum required by §4: the residual statistic computed inside each
`vol_60_tr` decile and averaged is **+0.0533 SD, `|t| = 0.861`** — the sign is
preserved (as §4 requires), but the magnitude falls by a further ~54% relative
to the full-cross-section residual `[VERIFIED — results.json
vol_decile_pooled_residual]`. The sign check passes; it does not rescue the arm.

Context for the collapse: `corr(u, |z(vol_60_tr)|) = +0.4066` pooled
`[VERIFIED — run.log §4 setup]`. `|z|` of momentum really is largely a
dispersion ranking on this corpus, which is precisely what §4 was written to
catch.

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

`α = 2·sin(π·0.05/6) = 0.0523538966`, and `(6/π)·asin(α/2) = 0.0500000000`
`[VERIFIED — run.log §5.1]`.

**One thing the control got away with, stated because it nearly voided the run
for a reason unrelated to the data.** §5.1's `α` inverts the *asymptotic*
Spearman–Pearson relation, but the registered construction builds `u_pc` from
**normal scores** (a permutation of a fixed vector), and that construction is
downward-biased at finite cross-section width. Measured on synthetic panels
through the same code: mean IC ≈ **+0.020** at `n = 31`, **+0.043** at
`n = 128`, **+0.049** at `n = 512`, **+0.050** at `n = 4096`
`[VERIFIED — Monte-Carlo of the §5.1 construction, 20,000/5,000/3,000 dates per
width, this session]`. This corpus's width (median 128) put the realised
+0.044347 inside the ±0.01 tolerance with 0.0043 to spare. On a narrower
cross-section the *same, correct* code would have VOIDed the screen. That is a
defect in the registered constant, not in the run, and it is reported rather
than fixed — §5.1 forbids adjusting `α`, and adjusting it after seeing the
number is exactly what the clause exists to prevent.

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
> removes 51% of the spread (+0.2381 → +0.1161 SD) and half the `t`
> (3.270 → 1.644), leaving a statistic that a permutation of `u` beats 12.5% of
> the time. §4 registers this as a kill condition, so the verdict stands
> **whatever the raw arm says**.
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

1. **§6's fourth self-check is void, not skipped.** It asks for "the
   screen/holdout partition … with a 60-trading-day embargo, and the embargoed
   row count". A4.2 voids the 60-day embargo for this design (there is no second
   partition for an embargo to separate). The equivalent quantity is reported
   instead: the excluded band of **120 dates / 16,226 rows**, 2021-04-20 →
   2021-10-07, excluded because their labels would be built from burned returns.
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

---

## 9 Suite

| tree | result |
|---|---|
| `origin/main` @ `6658078` (separate worktree) | **1047 passed, 2 skipped** |
| this branch | **1058 passed, 2 skipped** (+11 = `tests/test_goal7_stage1_estimator.py`) |

`[VERIFIED — make test PYTHON=<RenQuant venv python>, both trees, this session]`

---

## 10 Adversarial review (§8) — appended verbatim with its disposition

<!-- ADVERSARIAL-REVIEW-BEGIN -->
*(pending — the verdict above is WITHHELD until this section is filled)*
<!-- ADVERSARIAL-REVIEW-END -->
