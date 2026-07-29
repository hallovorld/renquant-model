# PREREG (FROZEN) — PatchTST signal-existence over the 43-fold WF corpus

Frozen: 2026-07-28, before any evaluation run over the corpus.
Corpus: run-id `wf-pt-b4e47e2c-batch1` (43/43 folds trained on Modal,
$18.30 of the $25 cap; 43/43 calibrators fitted locally).
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
across folds; significance from the ACROSS-FOLD dispersion (43 windows),
never from per-date counts within a fold. Report both the naive per-date t
(for comparability with prior docs) and the fold-level t; **the fold-level
t is the decision statistic.**

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

Let `d` = fold-level mean of (real IC − shift-placebo IC), with fold-level
t-statistic `t_d` over the 43 folds.

- **GO (third blend leg)** — `t_d ≥ 2.0` AND the decile-spread arm agrees in
  sign AND the calibrated arm is not materially weaker than the raw arm.
  Next step on GO: the standard blend gate chain (screen → frozen
  confirmatory prereg on disjoint seeds → shadow). NOT a promotion.
- **KILL (as an alpha source)** — `t_d ≤ 0.5` with the 90% CI upper bound
  below the smallest economically useful effect. PatchTST is then closed as
  a scorer; the corpus is kept as a PIT artefact.
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
