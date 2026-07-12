# Ensemble Phase 0 + Phase A Discovery Harness

**Date:** 2026-07-12
**PR:** model (this PR)
**Design ref:** `doc/research/2026-07-12-ensemble-combination-experiment.md` (PR #48, merged)

## What

Implements the Phase 0 admissibility + Phase A discovery experiment harness
for the L1 equal-weight ensemble, aligned with the revised evidence protocol
from PR #48.

## Key changes from the prior version (closed PR #49)

| Aspect | Prior (#49) | This version |
|---|---|---|
| Admissibility | None | §3.0 ledger: per-expert coverage, missingness, fingerprint, admit/reject |
| Inference | Plain paired t-test (assumes IID — WRONG for fwd_60d) | Non-overlapping 60-day block paired test (§4.1a) |
| Multiple comparisons | None | Holm-Bonferroni step-down (§4.4 option i) |
| Manifest | None | §4.5A immutable experiment manifest with hash |
| Normalization | Ad-hoc per-date z-score | Causal z-score with orientation control (§4.1bis) |
| Missing-expert | Inner join drops rows | Re-normalize weights to sum=1 (§4.1bis) |
| Complementarity | None | §3.0 diagnostics: rank correlation, top-20% overlap, disagreement coverage |
| Framing | "GO / NO-GO" verdict | "DISCOVERY — not deployment evidence" (§4.5) |
| Stopping rules | Implicit | Pre-registered in manifest (§4.5A) |

## Remaining work

- Wire real PatchTST scoring (currently ridge proxy)
- Phase B chronological confirmation holdout (requires untouched window)
- Costed decision-level outcome under fixed portfolio mapping (§4.4)
- White's Reality Check / Deflated Sharpe diagnostic (§4.5C)
