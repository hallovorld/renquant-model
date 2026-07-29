# PREREG (FROZEN) — PatchTST signal-existence over the 43-fold WF corpus

Frozen: 2026-07-28, before any evaluation run over the corpus.
Corpus: EXISTS, quarantined outside git (see RECONCILIATION below); not yet
committed to a stable path this evaluation script can read from. The frozen
dispatch plan was renquant-model#82 / renquant-backtesting#81-#82 (43 folds,
T4, train-only, recipe `b4e47e2c`, $16.8 projected against a $20 hard cap
enforced at execute time; a 1-fold staged smoke test under this exact recipe
ran and passed feasibility — `wf-pt-b4e47e2c-20260727T195313Z`, 1/1 fold).
CORRECTION (visible, per long-term-agreements.md entry 10, not a silent
overwrite): an earlier version of this line claimed a completed corpus
under run-id `wf-pt-b4e47e2c-batch1`, "43/43 folds trained on Modal,
$18.30 of the $25 cap," "audited on disk as 43 manifest retrains = 43
fold dirs." At the time, no run by that name could be found in this repo's
git history, so it was retracted as unlocatable.
RECONCILIATION (this pass, per model#91's queued corpus-index evidence):
that retraction was itself imprecise. model#91 (queued, unmerged) commits
a content-addressed index — `[VERIFIED — doc/research/evidence/2026-07-29-
patchtst-43fold-corpus-index.json` on the model#91 branch, read directly
this session]` — whose `corpus_id` is literally `wf-pt-b4e47e2c-batch1`,
recipe `b4e47e2c`, cutoff range 2023-10-02 → 2026-03-02, counts
`{fold_dirs: 43, model_pt: 43, calibration_json: 43}`, `failed_folds: []`,
and `budget_contract.max_total_usd = 25.0` — matching the earlier claim's
run-id, fold count, and $25 cap exactly. The batch is real; it is
quarantined in Claude-session scratch BY the governing dispatch design
("must not enter any repo or the umbrella tree"), which is why a
git-history-only check found nothing — quarantined-from-git is not the
same as nonexistent, and the original retraction over-read it that way.
Net effect: the corpus exists (43/43 folds, root digest `b8aa2d99...`),
but remains outside any committed/citable path, so this prereg's own
evaluation script still cannot run against it until it is pinned to a
stable location (model#91's NEXT) or promoted from the quarantined path.
This document's own frozen design and decision rule are unaffected by
this reconciliation — only the corpus-status claim changes.
Author: claude · Adversarial reviewer: codex.
**Alignment with model#86 (GOAL-6 Stage 0):** the `shift+120d` placebo T1
finding (documented in model#86) landed the shift near the score's own
predictive peak (IC lag-100d = +0.078, t=3.21), making `real − shift120`
structurally negative, not a null comparison — it is retired below as this
document's decision statistic (kept only as a descriptive report) in favour
of the within-date-shuffle null, matching Stage 0's own frozen null choice
(model#86 §3: within-date permutation + persistence-matched control). This
document commits to IC as its primary statistic and the 60d training
horizon independently of Stage 0's H1/H2 (which choose among IC/spread/hit
and 20d/60d for GENERAL measurement use, a different question); it borrows
only Stage 0's null selection, which needed no run to freeze.

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
+0.043 and 0.00 are not separable. **Re-measured directly this session**
(a prior review round could not locate this file and the claim was
provisionally treated as unverified pending re-measurement; found at
`ptserve/2026-07-21/hf_patchtst_all_seed44_val_preds.parquet` in local
scratch, real file, `ls -la` confirms it on disk): loading the parquet and
recomputing per-date Spearman IC from its own `pred`/`label` columns
independently reproduces every number above exactly — 33,370 rows, 235
dates × 142 tickers, 2025-05-20 → 2026-04-27, mean IC 0.04305, naive t
5.393 (n=235), block-adjusted t 0.696 (n_eff=235/60=3.92) `[VERIFIED —
recomputed directly from hf_patchtst_all_seed44_val_preds.parquet this
session, not carried over from an earlier draft]`.

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
within-date-shuffle-placebo IC per fold (i = 1..43, ordered by cutoff
date), Bartlett kernel, truncation lag **L = 2** — fixed by the known
overlap order above, not selected from the data (equivalent to treating
each independent block as 3 folds / 63 trading days, matching
Hansen-Hodrick (1980, *JPE* 88(5):829) practice for overlapping-horizon
regressions). Denote this `t_d`. The naive per-date t and a naive
iid-across-fold t are still reported for comparability with prior docs,
but carry no decision weight. The shuffle placebo has the full 43-fold
`df=42` (no tail-truncation issue — every fold's own dates support a
within-date shuffle, unlike a 120d-forward shift).

**Secondary statistic:** top-decile minus bottom-decile forward-return
spread per date, aggregated the same way (this is the statistic the panel
line is actually traded on — see the 2026-07-24 finding that IC and spread
disagree, IC t=1.15 vs spread t=2.92).

**Placebo arms (run per fold, matched to the gate's convention):**
1. `within-date shuffle` placebo — 5 seeds, destroys cross-sectional
   ordering only. **This is the decision-weighted null** (§3) — verified
   clean in prior single-fold work (−0.0008), and, unlike `shift120`, has
   no lag-dependent structural bias (T1).
2. `shift` placebo — labels shifted by 120 trading days, matching the WF
   gate's own placebo. **Descriptive only, never decision-weighted** (T1:
   the shift lands near the score's own predictive peak at lag ≈100d,
   making `real − shift120` structurally negative rather than a null
   comparison — retired as a decision statistic, kept only to report the
   defect itself, consistent with model#86's T1 remediation). The fold-
   eligibility rule below still applies to this arm's reporting.
3. **Persistence-matched control (veto, added per model#86 §3's frozen
   null pair)** — for each (date, ticker) cell, the persistence-arm score
   is that ticker's own score from 60 trading days earlier, evaluated
   against the SAME label as the real arm; cells with no eligible `t-60`
   score are dropped from this arm only (never imputed), with the arm's
   own coverage and block-level SE reported independently (same alignment
   and variance rules as model#86 §3.2). **Veto:** if `real − persistence`
   is not positive at t ≥ 1.0, GO cannot be declared regardless of the
   shuffle-based `t_d`, per §3 — an apparent edge that is really stale-
   score persistence is not fresh information.

Report REAL − PLACEBO differences with their fold-level dispersion; never
an absolute IC alone.

**Fold eligibility for the (now descriptive-only) `shift120` arm (frozen
rule, decided before any run — codex r3 finding).** A fold's `shift120`
placebo needs label dates 120 trading days past its own OOS window; for
cutoffs near the end of the 43-fold span (2023-10-02 → 2026-03-02), that
shifted window can run past the last date the served panel actually
covers. A fold is **eligible** for the `real − shift120` difference (and
therefore counted in `n_folds` / `df` for THAT specific report only) iff
its full shift120-shifted label window is `<=` the panel's max available
date, checked programmatically at evaluation time against the panel's
actual max date — never hand-counted or hardcoded in this document, and
never chosen after seeing results. Folds excluded from `shift120` are NOT
excluded from any other arm (`real` alone, `shuffle`, `persistence`): those
always use their own full/eligible coverage per their own rule. The `real`
arm's own `t_fold`/CI uses `n=43`/`df=42` throughout, unaffected by
`shift120` eligibility. `real − shift120` uses
`df = n_eligible_shift120_folds − 1`, computed by the same eligibility
check, applied identically to the `raw` and `calibrated` arms — this
number is reported for the record (T1's defect) but **carries no decision
weight**; §3's `t_d` is built from `real − shuffle`, not from this arm. The
evaluation script must print `n_eligible_shift120_folds` and the excluded
cutoff dates in its output for audit alongside the descriptive `shift120`
report.

**Calibrated-vs-raw:** compute both. The serving path consumes calibrated
probabilities, so a signal visible only in raw scores is not tradeable and
must be reported as such.

## 3. Decision rule (frozen)

Let `d` = fold-level mean of (real IC − within-date-shuffle-placebo IC),
over the full 43 folds (no eligibility exclusion — shuffle has no missing-
data case, unlike `shift120`), with the Newey-West HAC t-statistic `t_d`
defined in §2 (Bartlett kernel, lag L = 2). The 90% CI on `d` is
`mean(d) ± t_{0.95}(df=42) × SE_HAC(d)`, critical value from
`scipy.stats.t.ppf(0.95, df=42)`, a conservative small-sample adjustment on
top of the HAC-corrected SE. The `shift120` arm (§2) and its own
`n_eligible_shift120_folds`/`df` are reported alongside for the T1 record
but do not feed `t_d`, the CI, or any GO/KILL/UNDERPOWERED branch below.

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
  calibrated shuffle-placebo IC) and `d_raw` is `d` as defined above, AND
  the persistence veto (§2, arm 3) does NOT fire. Anchoring the bound to
  the already-frozen `d_min` (rather than a second, ad hoc ratio) means
  calibration is allowed to cost at most one "smallest economically useful
  effect" of edge before the calibrated (tradeable) arm fails GO on its
  own. Next step on GO: the standard blend gate chain (screen → frozen
  confirmatory prereg on disjoint seeds → shadow). NOT a promotion.
- **KILL (as an alpha source)** — `t_d ≤ 0.5` with the 90% CI upper bound
  of `d` (per the §3 CI construction above) below `d_min = 0.01`. PatchTST
  is then closed as a scorer; the corpus is kept as a PIT artefact.
- **UNDERPOWERED** — anything between. Then the honest finding is that 43
  folds still cannot resolve it, and the decision is a COST question
  (more seeds / a larger model / more folds), not a signal question. No
  promotion, no kill, and no third run without a new frozen prereg.

**Persistence veto** (§2, placebo arm 3, mirroring model#86 §3.2/§5's
frozen null): if `real − persistence` is not positive at t ≥ 1.0 on its own
eligible-date coverage, GO cannot be declared even if `t_d` clears 2.0 —
an apparent edge from a stale 60-trading-day-old score is not fresh
information. A vetoed GO resolves to UNDERPOWERED, not KILL (the veto
diagnoses the SOURCE of an apparent edge, it does not itself certify
there is none).

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
