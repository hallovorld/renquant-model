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
