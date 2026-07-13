# Phase A Discovery Runner

**Date:** 2026-07-12 (last updated 2026-07-13, round 9 review)
**PR:** model#53
**Goal:** G4 — multi-model ensemble

## What

Phase A discovery runner that compares L1 (equal-weight combination of
admitted experts) against the frozen champion on the same top-N portfolio
mapping, with a Newey-West HAC paired test for statistical significance.

## Files

- `experiments/ensemble_phase0/phase_a_runner.py` — runner implementation
- `experiments/ensemble_phase0/experiment_manifest.py` — manifest builder
- `tests/test_phase_a_runner.py` — 105 tests covering all components
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

## Round 9 changes (rebalance cadence + one_sided)

1. **Rebalance cadence (option 2):** changed manifest `rebalance_cadence`
   from `"daily"` to `"block_rebalance"` and merged the dual evaluation
   (daily descriptive + block-spaced test) into a single block-rebalance
   evaluation. All reported metrics (delta_ic, delta_return, delta_sharpe,
   and the primary test's delta_net_return_test) now come from the same
   block-rebalance evaluation, so the estimand is unambiguous. Intermediate
   daily selections are never computed — costs are charged only at rebalance
   points.

2. **`statistical_test.one_sided` validation:** the runner now validates
   that the manifest's `statistical_test.one_sided` field is `True`,
   matching the implemented one-sided Newey-West paired t-test
   (H1: mean(L1) > mean(champion)). A missing or False value is rejected.

3. **Adversarial regression test:** proves that intermediate daily scores
   (between block endpoints) do not affect the primary test result. Two
   expert sets with identical block-date scores but different intermediate
   scores produce identical primary test statistics (t-stat, p-value,
   verdict), confirming the block-rebalance policy is correctly
   implemented.

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
