# 2026-07-12 — Multi-panel ensemble architecture: literature survey

## Bottom line

Literature survey of 5 papers (2022–2025) + industry practice establishing
plausibility for the operator's multi-panel ensemble vision: sector panels +
large cross-sectional panel + per-ticker experts with regime-conditional gating.
Framed as falsifiable hypotheses with required baselines and experiment protocol,
not as a validated design.

## What this PR contains

- `doc/research/2026-07-12-multi-panel-ensemble-architecture.md` — the research
  memo: academic survey (MIGA, PPFM, AlphaMix, AlphaCrafter, Two-Level
  Uncertainty), current system assessment, candidate Hierarchical MoE
  architecture, practical constraints (104-stock universe, sector sample sizes),
  required baselines (frozen champion, risk-abstention, soft mixture), experiment
  protocol (nested WF, leakage controls, multiple-comparison treatment,
  calibration), and a 4-phase staging plan with explicit decision rules.
- This progress note.

## Key design choices

1. Each phase advances only if OOS improvement over ALL THREE baselines
2. Phase 4 (learned gating) is explicitly CONTINGENT, not planned
3. Experiment protocol requires preregistered metrics, leakage controls,
   and multiple-comparison correction
4. Sector grouping fixed before training (no data-driven sector assignment)

## Verification

- Research-only: no code, config, or behavioral change. `[VERIFIED]`
- All paper citations checked against source URLs. `[VERIFIED]`
- Rehomed from orchestrator (PR #493, to be closed) to model repo per
  codex review on repo ownership.
