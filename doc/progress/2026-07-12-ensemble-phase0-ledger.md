# Ensemble Phase 0: admissibility ledger and experiment manifest (v2)

**Date:** 2026-07-12
**PR:** model feat/ensemble-phase0-ledger-v2 (supersedes #50)
**Design:** model PR #48 (merged), §3.0 and §4.5A

## What

Phase 0 prerequisite tooling for the ensemble experiment: admissibility ledger
and immutable experiment manifest. This v2 PR strips the L1 experiment runner
code that was out of scope and fixes three review issues from Codex on PR #50.

### Components

1. **Admissibility ledger builder** (`experiments/ensemble_phase0/admissibility_ledger.py`)
   - Per-expert, per-date validation: fingerprint, training cutoff, feature/data
     cutoff, score timestamp, universe coverage, missingness, score orientation
   - Lookahead detection (training cutoff >= prediction date)
   - Score timestamp validation against prediction date
   - Missingness threshold (>20% = rejected)
   - Deterministic SHA-256 fingerprinted ledger output
   - Complementarity report (cross-sectional correlation, rank disagreement)
   - CLI discovers dates from score directories and runs complementarity analysis

2. **Experiment manifest builder** (`experiments/ensemble_phase0/experiment_manifest.py`)
   - Immutable pre-registered manifest encoding the full §4.5A contract
   - 3 experts, 2 expert sets, 6-hypothesis family, hierarchical gatekeeping
   - Tamper detection via fingerprint verification

### Fixes from PR #50 review (Codex CHANGES_REQUESTED)

1. **Removed L1 experiment runner** -- `experiments/ensemble_l1_equal_weight/`
   and related progress docs removed. Only Phase 0 prerequisite tooling remains.

2. **CLI fail-open bug fixed** -- `build_ledger` with zero dates/records now sets
   `all_experts_fully_admitted = False` (no vacuous truth). CLI discovers
   prediction dates from score directories; exits 1 if zero dates found or
   experts not fully admitted.

3. **Validation gaps closed**:
   - `has_realized_labels` defaults to `False` (fail-closed, was `True`)
   - `score_timestamp` validated against prediction date (rejects if scored
     before prediction date or if timestamp is missing)
   - CLI computes and writes the complementarity report

## Why

Per §5.1, the Stage 0 admissibility ledger and immutable manifest BLOCK every
L1-L3 comparison. Without them, any experiment result is not credible.

## Status

- 22/22 tests pass (15 ledger + 7 manifest).
- These are experiment-side tools, not production code changes.
- Next: run the ledger against actual XGB + PatchTST score histories to produce
  the first admissibility audit.
