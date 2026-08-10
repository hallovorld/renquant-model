# xgb_mom_60d — prereg v2: embargoed folds (the admissibility repair)

STATUS: frozen before any run. v1 (model#211) executed once and was
recorded NO ADMISSIBLE VERDICT (model#212): its fold gaps (~32 calendar
days) were shorter than the fwd_60d_excess label window (~84 calendar
days), so training labels realized inside every test interval. v2 amends
EXACTLY the fold calendar and the run-time integrity duties; every other
element of v1 — the 70-column feature list, params, seeds, guards, the
four PASS/KILL legs, the baseline's descriptive role — is inherited
verbatim.

## 1 · The amended folds `[DERIVED — gap ≥ 90 calendar days > the ~84-day realization window of a 60-trading-day label]`

Train ends 12-31; test starts 04-01 of the following year (gap 91 calendar
days), test ends 12-31 of that year. Eight folds:

| fold | train | test |
|---|---|---|
| 1..7 | 2016-01-01..YYYY-12-31 for YYYY in 2018..2024 (expanding) | (YYYY+1)-04-01..(YYYY+1)-12-31 |
| 8 | 2016-01-01..2025-12-31 | 2026-04-01..2026-05-07 (corpus end; ~26 sessions — the min_test=100-row guard applies and fold 8 drops out if unmet, COUNTED) |

The shuffle placebo runs on the SAME folds (v1 rule). No other calendar
freedom exists.

## 2 · Run-time integrity duties (the v1 lessons, now frozen as duties)

0. **PER-ROW PURGE IS THE GUARANTEE (review r1)** — the calendar gap in §1
   is design intent, not the enforcement. The committed harness
   (`doc/design/frozen/2026-08-09-xgbmom-v2-harness.py`, committed BEFORE
   any run) computes every training row's realized label endpoint as the 60th
   trading session after its date ON THE CORPUS'S OWN CALENDAR and drops
   any row whose endpoint is not strictly before the fold's test start;
   fold-wise purge counts and the max surviving endpoint are persisted in
   the result artifact. The controls under the new folds are committed
   beside it (positive PASS +0.3752 / null KILL +0.0017, hard exit codes;
   purge machinery exercised — endpoints computed and bounded per fold).
1. The harness asserts the corpus sha256 == `870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e`
   BEFORE reading (v1 added this only post-hoc);
2. the result JSON carries `corpus_sha256`, the literal fold table, and
   `admissible_verdict` (null until review confirms; the verifier fails
   if a non-null verdict appears without the doc's counter-signature —
   the model#210/#212 machine-surface rule);
3. pre-run synthetic controls (positive planted + null) re-run under the
   NEW folds and their JSONs are committed with the result.

## 3 · Gates — inherited verbatim from v1 §3

Seed-mean real signal > 0; positive folds ≥ ⌈0.75 × n_realized⌉ (8
realized → 6; 7 realized → 6 — the proportional form of v1's 6-of-8,
stated now, not chosen later); the committed harness persists the frozen
feature-list sha256 in every control and result artifact; A/A
seed std ≤ 0.01; recency guard on the surviving recent folds. PASS earns a
shadow-candidacy memo gated on orch#937/#931 (unchanged); KILL is a
completed outcome. Expectation-setting, recorded before the run: part of
v1's +0.022 diagnostic signal may have been leak — a weaker v2 number is
the EXPECTED direction, and no gate moves because of it.
