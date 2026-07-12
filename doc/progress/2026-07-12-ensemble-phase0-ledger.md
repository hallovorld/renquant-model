# Ensemble Phase 0: admissibility ledger and experiment manifest

**Date:** 2026-07-12
**PR:** model feat/ensemble-phase0-ledger
**Design:** model PR #48 (merged), §3.0 and §4.5A

## What

Built the two Phase 0 blocking prerequisites for the ensemble experiment:

1. **Admissibility ledger builder** (`experiments/ensemble_phase0/admissibility_ledger.py`)
   - Per-expert, per-date validation: fingerprint, training cutoff, feature/data
     cutoff, score timestamp, universe coverage, missingness, score orientation
   - Lookahead detection (training cutoff >= prediction date)
   - Missingness threshold (>20% = rejected)
   - Deterministic SHA-256 fingerprinted ledger output
   - Complementarity report (cross-sectional correlation, rank disagreement)
   - 12 tests

2. **Experiment manifest builder** (`experiments/ensemble_phase0/experiment_manifest.py`)
   - Immutable pre-registered manifest encoding the full §4.5A contract
   - 3 experts, 2 expert sets, 6-hypothesis family, hierarchical gatekeeping
   - Tamper detection via fingerprint verification
   - 7 tests

## Why

Per §5.1, the Stage 0 admissibility ledger and immutable manifest BLOCK every
L1-L3 comparison. Without them, any experiment result is not credible.

## Status

- 19/19 new tests pass.
- These are experiment-side tools, not production code changes.
- Next: run the ledger against actual XGB + PatchTST score histories to produce
  the first admissibility audit.
