# Phase A Discovery Runner

**Date:** 2026-07-12
**PR:** model#53 (TBD)
**Goal:** G4 — multi-model ensemble

## What

Phase A discovery runner that compares L1 (equal-weight combination of
admitted experts) against the frozen champion on the same top-N portfolio
mapping, with a Newey-West HAC paired test for statistical significance.

## Files

- `experiments/ensemble_phase0/phase_a_runner.py` — runner implementation
- `tests/test_phase_a_runner.py` — 80 tests covering all components

## Components

1. **Score loading** — reads date-named JSON score files (same format as
   admissibility ledger)
2. **L1 equal-weight** — averages scores across all admitted experts per date,
   excluding tickers with partial coverage
3. **Top-N selection** — rank-based portfolio mapping (configurable N)
4. **Evaluation** — IC, mean return, Sharpe, hit rate, turnover
5. **Newey-West t-test** — HAC standard errors with lag = sqrt(T), one-sided
6. **Go/no-go verdict** — L1_BEATS_CHAMPION / CHAMPION_RETAINED / INCONCLUSIVE

## Prerequisites for execution

- Admissibility ledger (model #51) — MERGED
- Historical XGB and PatchTST score files in the ledger JSON format
- Forward 60-day returns CSV
- Score files must pass the admissibility ledger before use

## Limitations

- Top-N selection is a research proxy for the full production mapping
- Does not implement the nested WF harness (future work for L3/L4)
- Base cost (turnover × `base_cost_bps`) is deducted from daily returns;
  adverse-selection cost robustness is deliberately out of scope for Phase A
  (would require a full execution-side cost model)
