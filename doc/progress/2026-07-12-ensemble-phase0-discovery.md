# Ensemble Harness Verification (diagnostic only)

**Date:** 2026-07-12
**PR:** model #50
**Design ref:** `doc/research/2026-07-12-ensemble-combination-experiment.md` (PR #48, merged)

## What

Harness smoke test for the L1 equal-weight ensemble framework. Verifies
that the combination machinery (admissibility ledger, causal normalization,
non-overlapping origin-date inference, Holm-Bonferroni correction, manifest)
executes correctly end-to-end using a Ridge regression proxy as the second
expert. This is NOT a discovery run and cannot produce a candidate verdict.

## Framing: harness verification, not discovery

The script uses Ridge regression (same features as XGB, different functional
form) as a synthetic second expert. This is a deliberately weak proxy that
exists solely to exercise the framework with two distinct score streams.
It cannot support any claim about PatchTST ensemble value.

## What this PR validates (framework mechanics)

- §3.0 admissibility ledger: coverage, missingness, fingerprint, admit/reject
- §4.1 non-overlapping origin-date inference (spaced >= 60 trading days)
- §4.1bis causal z-score normalization with orientation control
- §4.1bis missing-expert re-normalization fallback
- §3.0 complementarity diagnostics (rank correlation, disagreement coverage)
- §4.4 Holm-Bonferroni step-down correction
- §4.5A immutable experiment manifest with content hash

## What this PR does NOT validate (prerequisites not met)

- No persisted PatchTST score artifacts with as-of lineage
- No costed portfolio construction / net outcome threshold
- No immutable expert score artifact fingerprints
- Admissibility ledger validates structural coverage only, not artifact provenance
- Cannot issue candidate selection or deployment verdict
