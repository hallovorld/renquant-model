# 2026-07-12 — G4 L1 equal-weight ensemble experiment script

## Bottom line

Phase A experiment code for GOAL-4 multi-model ensemble: WF CV harness that
produces OOS per-date cross-sectional IC for XGB champion, an alternative model,
and their L1 equal-weight average. Pre-registered go/no-go: ΔIC ≥ 0.005 at
p < 0.05 (one-sided). Design reference: #47 §3.2.

## What this PR contains

- `experiments/ensemble_l1_equal_weight/run_experiment.py` — complete experiment
  runner: expanding-window CV (reuses `panel_trainer` infrastructure), z-score
  normalization per date, paired IC t-test with fwd_60d overlap caveat, automated
  verdict (GO / MARGINAL / NO-GO).

## Key design choices

1. Z-normalizes both model predictions per date before averaging — prevents scale
   domination
2. Falls back to ridge regression when PatchTST scorer unavailable — validates
   harness end-to-end with a real second model before requiring PatchTST checkpoint
3. Paired test flagged PRELIMINARY — fwd_60d overlap makes successive ICs
   non-IID; design doc §4.1 requires non-overlapping outer blocks for confirmatory

## Verification

- Script parses and imports with no errors `[VERIFIED]`
- Follows the L1 definition in #47 §3.2 exactly `[VERIFIED]`
