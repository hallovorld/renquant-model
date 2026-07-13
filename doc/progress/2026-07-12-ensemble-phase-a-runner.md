# Phase A Discovery Runner

**Date:** 2026-07-12 (last updated 2026-07-13, round 6 review)
**PR:** model#53
**Goal:** G4 — multi-model ensemble

## What

Phase A discovery runner that compares L1 (equal-weight combination of
admitted experts) against the frozen champion on the same top-N portfolio
mapping, with a Newey-West HAC paired test for statistical significance.

## Files

- `experiments/ensemble_phase0/phase_a_runner.py` — runner implementation
- `tests/test_phase_a_runner.py` — 97 tests covering all components
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

## Prerequisites for execution

- Admissibility ledger (model #51) — MERGED
- Historical XGB and PatchTST score files in the ledger JSON format
- Forward 60-day returns CSV
- Score files must pass the admissibility ledger before use
- Every ledger-admitted score record must actually load (missing or
  digest-mismatched admitted records now hard-reject rather than warn)

## Limitations

- Top-N selection is a research proxy for the full production mapping
- Base cost (turnover × `base_cost_bps`) is deducted from daily returns;
  adverse-selection cost robustness is deliberately out of scope for Phase A
  (would require a full execution-side cost model)
- **The nested WF/purging harness (design doc §5.1) does not exist yet.**
  `nested_wf_harness_status` is accepted, threaded through, and persisted
  on the result as a versioned manifest fact, but it is **not** used to gate
  promotability: as of the round 6 review (Codex, 2026-07-13T17:00:21Z,
  finding 1), the cap to `EXPLORATORY_ONLY` is now **unconditional** —
  every Phase A verdict is `EXPLORATORY_ONLY` regardless of what the
  manifest attests, because `nested_wf_harness_status` is a self-attested
  string with no independent verifier behind it. Setting it to
  `NESTED_WF_HARNESS_APPLIED` previously escaped the cap; it no longer does.
  The underlying (non-promotable) statistics are still computed and
  reported in `verdict_detail` for research visibility. Un-capping requires
  a future PR that builds both the real harness AND a runner-side verifier
  for a typed, immutable, harness-generated WF-evidence reference — not
  merely flipping this field.
- Locator binding (`verify_returns_file_digest`) still compares only
  `Path(expected_locator).name`, so a same-named file at an unrelated
  directory would pass; full-path/canonical-locator resolution is real
  design work and remains an open, explicitly-flagged gap (not fixed in
  round 6).
