# Phase A Discovery Runner

**Date:** 2026-07-12 (last updated 2026-07-13, round 14 review)
**PR:** model#53
**Goal:** G4 — multi-model ensemble

## What

Phase A discovery runner that compares L1 (equal-weight combination of
admitted experts) against the frozen champion on the same top-N portfolio
mapping, with a Newey-West HAC paired test for statistical significance.

## Files

- `experiments/ensemble_phase0/phase_a_runner.py` — runner implementation
- `experiments/ensemble_phase0/experiment_manifest.py` — manifest builder
- `tests/test_phase_a_runner.py` — 146 tests covering all components
- `tests/test_experiment_manifest.py` — 15 tests for the manifest loader

## Components

1. **Score loading** — reads date-named JSON score files (same format as
   admissibility ledger)
2. **L1 equal-weight** — averages scores across all admitted experts per date,
   excluding tickers with partial coverage
3. **Top-N selection** — rank-based portfolio mapping (configurable N)
4. **Evaluation** — IC, mean return, Sharpe, hit rate, turnover
5. **Newey-West t-test** — HAC standard errors with lag = sqrt(T), one-sided
6. **Go/no-go verdict** — L1_BEATS_CHAMPION / CHAMPION_RETAINED / INCONCLUSIVE
   / EXPLORATORY_ONLY

## Review round summary

### Round 9 (rebalance cadence + one_sided)

1. Merged daily+block evaluation into single block-rebalance estimand.
2. Validated `statistical_test.one_sided == True`.
3. Adversarial regression test proving intermediate daily scores do not
   affect block-rebalance test statistics.

### Round 10 (session-index spacing + estimand versioning)

1. Spacing measured in session-index positions (not calendar days).
2. Embargo fields persisted on result for auditability.
3. Estimand policy versioning (`block_rebalance_paired` vs champion's
   `daily` production policy), with caveat in verdict_detail on mismatch.

### Round 11 (frozen session calendar + positive embargo + versioning)

1. Spacing measured against a frozen, manifest-bound session calendar
   (SHA-256 digest-verified). Missing sessions in loaded data preserve
   real calendar-index gaps instead of compressing them.
2. `embargo_sessions` must be positive (zero/negative rejected).
3. Block-rebalance is a separately versioned experiment
   (`experiment_version` required, non-empty).
4. Champion policy artifact: required, digest-verified against manifest.

### Round 12 (fail-closed calendar + verified champion policy)

1. Session calendar: required CLI arg, sorted/unique, digest-verified,
   unknown evaluation dates raise hard errors.
2. Champion policy artifact: required, file must exist, digest must match
   manifest. Typed schema validation (champion_name, top_n,
   rebalance_cadence checked against manifest).

### Round 13 (return-date coverage + typed policy schema)

1. Return-date coverage: every required prediction date (intersection of
   admitted expert dates and session calendar) must be present in the
   returns file. Missing dates fail closed (no silent calendar shrinkage).
2. Champion policy required fields: `champion_name`, `top_n`,
   `rebalance_cadence`, `cost_model`, `score_normalization`.

### Round 14 (champion policy schema + e2e return coverage test)

1. `validate_champion_policy()` now enforces `cost_model` and
   `score_normalization` schema: `cost_model` must be a dict with
   `base_cost_bps` matching `manifest.cost_assumptions.base_cost_bps`;
   `score_normalization` method must match
   `manifest.score_normalization.method`. Mismatch tests for both.
2. Missing-return-date test replaced with a full e2e fixture: shortened
   returns file with re-fingerprinted ledger/manifest, asserting
   `main()` returns 1 specifically because a required prediction date is
   absent (not because of a digest mismatch).

## Prerequisites for execution

- Admissibility ledger (model #51) — MERGED
- Historical XGB and PatchTST score files in the ledger JSON format
- Forward 60-day returns CSV
- Score files must pass the admissibility ledger before use
- Every ledger-admitted score record must actually load (missing or
  digest-mismatched admitted records now hard-reject rather than warn)

## Limitations

- Top-N selection is a research proxy for the full production mapping
- Base cost (turnover x `base_cost_bps`) is deducted at rebalance points;
  adverse-selection cost robustness is deliberately out of scope for Phase A
  (would require a full execution-side cost model)
- **The nested WF/purging harness (design doc §5.1) does not exist yet.**
  Every Phase A verdict is unconditionally capped at `EXPLORATORY_ONLY`.
- Artifact identity uses SHA-256 content digest (option 1, round 8);
  locator is informational audit trail only.
