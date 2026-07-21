# Progress — G4 walkforward-sim admissibility (extraction-layer leakage fix)

**Date:** 2026-07-20
**Goal:** GOAL-4 Phase 0 evidence pipeline. **Type:** model-only portable logic + tests.

## STATUS
Adds the leakage-correct admissibility a sim-DB→Phase-A extraction needs, as a
pure, model-owned module. Unblocks using the existing 558-date XGB walkforward
history (and any future PatchTST WF history) as G4 evidence.

## WHAT
`experiments/ensemble_phase0/walkforward_admissibility.py`:
`load_walkforward_folds` / `select_walkforward_fold` / `walkforward_admissibility`
+ `WalkforwardFold`/`WalkforwardAdmission`. Given a walkforward manifest's
`retrains` (cutoff_date + lookahead_days) and a prediction date, admits the date
iff a fold with `cutoff_date+lookahead_days` strictly before it exists (mirrors
`WalkForwardModelLoader.model_as_of`), and stamps `training_cutoff` = that fold's
`cutoff_date`. Pure stdlib, no DB read, no cross-repo import.
`tests/test_walkforward_admissibility.py` — 11 tests.

## WHY-DIR
The Stage-0 ledger admits by `created_at <= session-close cutoff` — correct for
the LIVE forward DB (created_at ~= run_date), WRONG for a walkforward-SIM DB. In
`data/sim_runs.db` all 1089 sim runs share `created_at=2026-05-11` (one batch
execution) while run_date spans 2024-01..2026-03, so the created_at test would
reject ALL 558 PIT-clean sim dates. The sim's point-in-time cleanliness comes
from the model VINTAGE (per-fold cutoff), not created_at; this reproduces the
fold selection from the manifest and admits by vintage — not a blind "trust the
sim" (a date before walkforward coverage is still rejected).

## EVIDENCE
`pytest tests/test_walkforward_admissibility.py` → 11 passed. Against the REAL
43-fold manifest (`walkforward_manifest_gbdt_prod_recipe_v2.calibrated.json`): all
558 sim dates 2024-01-02..2026-03-27 admit with truthful training_cutoffs (e.g.
2026-03-27 → cutoff 2026-01-19); 2023-11-01 (pre-coverage) rejects.
`[VERIFIED — 11/11 tests + empirical real-manifest run]`

## NEXT
- The umbrella extraction harness (the #63 part-B forward-consumer, umbrella-owned)
  consumes this to emit the XGB score-dir + a truthful ledger from `sim_runs.db`.
- Same module admits the future PatchTST WF-sim scores once that history is built
  (awaiting the operator's local-MPS compute go).

## CODEX REVIEW FIX (2026-07-21)

Codex's PR review found two P0 gaps in the first cut above; both fixed in this
follow-up commit.

**1. Date-semantics drift.** The real `WalkForwardModelLoader.entry_as_of`
(RenQuant `backtesting/renquant_104/kernel/walk_forward/loader.py`) selects
using `effective_train_cutoff_date or cutoff_date` plus
`pandas.tseries.offsets.BDay(lookahead_days)` — BUSINESS days — strictly
before the prediction date. This module's first cut used
`cutoff_date + datetime.timedelta(lookahead_days)` (calendar days) and never
read `effective_train_cutoff_date`, silently diverging around weekends and
for pre-embargoed folds. Fixed by extracting the pure selection semantics into
a new canonical module, `renquant_common.walk_forward_fold_selection`
(renquant-common 0.15.0: `feature_cutoff_date`, `safe_last_label_date`,
`is_fold_eligible`, `select_latest_eligible_fold`), and having
`walkforward_admissibility.py` import and call it instead of reimplementing
the date math. This drops the module's original "pure stdlib, no cross-repo
import" design goal (traded for correctness per the review) but keeps it out
of a direct dependency on RenQuant (the umbrella) — renquant-common already
sits below both RenQuant and renquant-model in the dependency graph, so this
is the addition, not a new edge. `pyproject.toml` bumped
`renquant-common>=0.15.0` (structural — the module does not exist below it).
**Not yet done** (flagged honestly, not papered over): the real umbrella
loader (`RenQuant/backtesting/renquant_104/kernel/walk_forward/loader.py`)
still carries its OWN inline copy of this date arithmetic — it was not
refactored to import `renquant_common.walk_forward_fold_selection` in this
PR, since that is a change to a different repo's live scoring/sim kernel,
out of this PR's scope. Until that follow-up lands, two implementations still
exist (the loader's inline one, now IDENTICAL by inspection/tests to the
canonical one, and the canonical one this module now uses) — the loader-side
refactor is the natural next step to fully close the fork Codex flagged
(F-2 in `doc/arch/2026-07-04-umbrella-compliance-audit.md`).

**2. No provenance verification.** Fold-coverage alone only proved SOME
eligible fold existed for a date, never that the extracted sim record was
actually produced by that fold's artifact. Fixed by adding
`ObservedFoldProvenance` (`training_cutoff`, `artifact_sha256`) as an explicit
input to `walkforward_admissibility()`: a record with no observed provenance
at all is rejected (`missing_observed_provenance`), one whose
`training_cutoff` doesn't match the eligibility-selected fold's cutoff (or
`effective_train_cutoff_date`, when the fold declares one) is rejected
(`missing_observed_training_cutoff` / the mismatch reason), and when the
fold's manifest stamps `artifact_sha256`, a missing or mismatched observed
digest is also rejected. Schema investigation (RenQuant
`doc/components/databases.md` + `kernel/persistence.py` +
`kernel/artifact_contract.py::build_run_bundle`): the sim DB's
`pipeline_runs.candidate_scores.panel_ltr_artifact` /
`config["ranking"]["panel_scoring"]["artifact_path"]` is a STATIC
config-declared value that does not vary per walk-forward bar, so it cannot
prove which fold scored a given date. The real per-bar signal is
`pipeline_runs.run_bundle_json` (`build_run_bundle()`'s output persisted
verbatim), whose `training_cutoff` / `model_content_sha256` keys are sourced
from the ACTIVE scorer's own runtime metadata
(`effective_train_cutoff_date` / `trained_date` /
`model_content_fingerprint`) — this is what the extraction harness must build
`ObservedFoldProvenance` from. Honest caveat documented in the module's
docstring: `trained_date` (wall-clock training-finish date) and `cutoff_date`
(last in-sample label date) are distinct manifest fields, so an extraction
harness comparing them must be explicit about which one it is matching; this
module cannot resolve that ambiguity on the caller's behalf and fails a
record closed rather than guessing.

New tests (25 total, up from 11): Friday/weekend business-day boundary
(`test_usable_from_is_business_day_not_calendar_day`,
`test_weekend_prediction_date_around_fold_boundary`), effective-cutoff
preference end-to-end
(`test_effective_train_cutoff_date_entry_selected_correctly`,
`test_admits_when_observed_training_cutoff_matches_effective_cutoff`), and the
provenance-mismatch negative tests
(`test_rejects_when_observed_provenance_missing_entirely`,
`test_rejects_when_observed_training_cutoff_is_a_different_fold`,
`test_rejects_when_artifact_sha256_mismatches`, and 3 more). Companion tests
added in renquant-common: `tests/test_walk_forward_fold_selection.py` (14
tests) for the new shared module itself.

`[VERIFIED]` — renquant-common: 435 passed / 7 skipped / 1 pre-existing
unrelated failure (`test_registry_lift.py::test_byte_equivalent_to_umbrella`,
an MLflow-registry byte-diff check against a sibling umbrella checkout,
unrelated to this change). renquant-model: 647 passed (full suite excluding
9 `tests/patchtst/*` files that hard-import `torch`, an optional heavy
dependency not installed in the verification sandbox — unrelated to this
change).

Cross-repo note: the renquant-common addition needs its own PR merged first
(renquant-common is a separate repo with its own release/version process);
this renquant-model PR's `renquant-common>=0.15.0` pin does not resolve until
that PR merges and 0.15.0 is available.
