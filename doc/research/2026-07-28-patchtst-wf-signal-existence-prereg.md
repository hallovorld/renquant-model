# PREREG (FROZEN) — PatchTST signal-existence over the 43-fold WF corpus

Frozen: 2026-07-28, before any evaluation run over the corpus AND before the
corpus itself has been generated.
Corpus: NOT YET GENERATED. The frozen dispatch plan is renquant-model#82 /
renquant-backtesting#81-#82 (43 folds, T4, train-only, recipe
`b4e47e2c`, $16.8 projected against a $20 hard cap enforced at execute
time; a 1-fold staged smoke test under this exact recipe has run and
passed feasibility — `wf-pt-b4e47e2c-20260727T195313Z`, 1/1 fold — the
remaining 42 have not been dispatched).
CORRECTION (visible, per long-term-agreements.md entry 10, not a silent
overwrite): an earlier version of this line claimed a completed corpus
under run-id `wf-pt-b4e47e2c-batch1`, "43/43 folds trained on Modal,
$18.30 of the $25 cap," "audited on disk as 43 manifest retrains = 43
fold dirs." No run by that name exists in this repo's history and no
such corpus exists on disk (checked: the only `walkforward_patchtst_runs`
namespace found anywhere contains the single 07-27 smoke fold, and the
production manifest this doc's own evaluation script would read from has
1 retrain, not 43). Retracted, not restated.
Author: claude · Adversarial reviewer: codex.

## 1. The question this exists to answer

Does the PatchTST recipe carry **any** cross-sectional signal, measured with
enough power to distinguish it from zero?

Motivating measurement (2026-07-28, single serving fold, val window
2025-05-20 → 2026-04-27, 235 dates × ~142 tickers):

| statistic | value |
|---|---|
| per-date rank IC (Spearman) | **+0.0430** |
| naive t | +5.39 |
| **block-adjusted t** (60-trading-day label overlap → n_eff ≈ 235/60 ≈ 4) | **+0.70** |
| within-date label-shuffle placebo (5 seeds) | −0.0008 |
| real − placebo | +0.0438 |

The point estimate is not small; the POWER is the problem. One validation
window with 60-day overlapping labels is ~4 independent observations, so
+0.043 and 0.00 are not separable. `[VERIFIED — direct read of
hf_patchtst_all_seed44_val_preds.parquet, 33,370 rows]`

The same recipe scored an entire live cross-section at calibrated
conviction ≈ 0.50 (IQR 0.011) and correctly sized to zero. That is the
expected behaviour of an unresolvable signal — it is NOT independent
evidence that the signal is absent.

## 2. Design (frozen before running)

**Unit of evidence:** each of the 43 folds contributes ONE out-of-sample
window (its own post-cutoff period, disjoint from its training data by the
recipe's embargo). Cutoffs span 2023-10-02 → 2026-03-02 at 21-day cadence.

**Primary statistic:** the fold-level mean of per-date rank IC, aggregated
across folds. Significance is NOT the naive across-fold dispersion treating
the 43 folds as independent — cutoffs are spaced 21 trading days apart
while the label horizon overlaps 60 trading days, so adjacent folds share
label window for `⌈60/21⌉ − 1 = 2` lags (fold i is dependent with fold
i+1 and i+2; fold i+3, at 63 trading days, is the first fold outside the
horizon). **Decision statistic (frozen):** a Newey-West (1987, *Econometrica*
55(3):703) HAC t-statistic on the fold-level series `d_i` = real IC −
shift-placebo IC per fold (i = 1..43, ordered by cutoff date), Bartlett
kernel, truncation lag **L = 2** — fixed by the known overlap order above,
not selected from the data (equivalent to treating each independent block
as 3 folds / 63 trading days, matching Hansen-Hodrick (1980, *JPE* 88(5):829)
practice for overlapping-horizon regressions). Denote this `t_d`. The naive
per-date t and a naive iid-across-fold t are still reported for
comparability with prior docs, but carry no decision weight.

**Secondary statistic:** top-decile minus bottom-decile forward-return
spread per date, aggregated the same way (this is the statistic the panel
line is actually traded on — see the 2026-07-24 finding that IC and spread
disagree, IC t=1.15 vs spread t=2.92).

**Placebo arms (run per fold, matched to the gate's convention):**
1. `shift` placebo — labels shifted by 120 trading days, matching the WF
   gate's own placebo, to capture the embargo/overlap leakage floor
   (documented ≈ +0.04 for this horizon; if the real arm does not clear
   its OWN placebo, the corpus says nothing).
2. `within-date shuffle` placebo — 5 seeds, destroys cross-sectional
   ordering only.
Report REAL − PLACEBO differences with their fold-level dispersion; never
an absolute IC alone.

**Calibrated-vs-raw:** compute both. The serving path consumes calibrated
probabilities, so a signal visible only in raw scores is not tradeable and
must be reported as such.

## 3. Decision rule (frozen)

Let `d` = fold-level mean of (real IC − shift-placebo IC), with the
Newey-West HAC t-statistic `t_d` defined in §2 (Bartlett kernel, lag
L = 2). The 90% CI on `d` is `mean(d) ± t_{0.95}(df=42) × SE_HAC(d)`,
critical value from `scipy.stats.t.ppf(0.95, df=42)` (df = n_folds − 1 = 42,
a conservative small-sample adjustment on top of the HAC-corrected SE).

**Smallest economically useful effect (frozen numeric threshold):**
`d_min = 0.01` (IC units). This is `min_oos_mean_ic` — the OOS mean-IC
floor coded as the production model-admission bar in the
`renquant-pipeline` repo (`renquant_pipeline.model_admission._check_oos_ic`,
mirrored to the umbrella's `kernel/panel_pipeline/admission_tasks.py`;
exercised at this value in `tests/test_panel_scoring_contract.py` and
`tests/test_model_admission.py`). It is the one number the RenQuant
codebase already treats as "the OOS edge floor below which a scorer does
not clear admission for live sizing," and it sits inside the standard
equity cross-sectional-IC usefulness band (Grinold & Kahn, *Active
Portfolio Management*, 2nd ed. — IC ≈ 0.02-0.05 "good," IC < 0.01
noise-level for a single signal). Reusing it here avoids inventing a
second, prereg-only bar with no operational meaning.

- **GO (third blend leg)** — `t_d ≥ 2.0` AND the decile-spread arm agrees in
  sign AND the calibrated arm is not materially weaker than the raw arm,
  frozen as: `d_raw − d_calibrated ≤ d_min` (0.01 IC units), where
  `d_calibrated` is the same fold-level mean of (calibrated real IC −
  calibrated shift-placebo IC) and `d_raw` is `d` as defined above. Anchoring the
  bound to the already-frozen `d_min` (rather than a second, ad hoc ratio)
  means calibration is allowed to cost at most one "smallest economically
  useful effect" of edge before the calibrated (tradeable) arm fails GO on
  its own. Next step on GO: the standard blend gate chain (screen → frozen
  confirmatory prereg on disjoint seeds → shadow). NOT a promotion.
- **KILL (as an alpha source)** — `t_d ≤ 0.5` with the 90% CI upper bound
  of `d` (per the §3 CI construction above) below `d_min = 0.01`. PatchTST
  is then closed as a scorer; the corpus is kept as a PIT artefact.
- **UNDERPOWERED** — anything between. Then the honest finding is that 43
  folds still cannot resolve it, and the decision is a COST question
  (more seeds / a larger model / more folds), not a signal question. No
  promotion, no kill, and no third run without a new frozen prereg.

Ties, ambiguity, or a broken run resolve to UNDERPOWERED. No post-hoc
subgroup search (regimes, sectors, date ranges) may change the verdict;
regime breakdowns are reported as descriptive only.

## 4. Discipline

- No production surface is touched; evaluation is read-only over the
  quarantined corpus and the frozen input bundle
  (`g4-rerun-inputs-20260727`, root `8072ca77…`).
- Every arm reports its own placebo. Absolute ICs are never quoted as
  evidence without their matched placebo difference.
- Negative or underpowered results are reported in full, with the same
  prominence as a GO.
- This document is frozen. Any change is an AMENDMENT file with its own
  timestamp, written before the affected run.
