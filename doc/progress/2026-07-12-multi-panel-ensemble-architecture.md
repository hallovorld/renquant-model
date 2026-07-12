# 2026-07-12 — Multi-panel ensemble architecture: literature survey + falsifiable hypotheses

## Bottom line

Literature survey of 5 papers (2022–2025) + industry practice establishing
plausibility (not efficacy) for the operator's multi-panel ensemble vision:
sector panels + large cross-sectional panel + per-ticker experts with
regime-conditional gating. Framed as three pre-registered, priority-ordered
falsifiable hypotheses (H1 primary/confirmatory, H2/H3 secondary/exploratory)
with a nested walk-forward protocol, not as a validated design.

## Revision note (this pass)

The first version of this doc (committed directly, 574054109c) stated required
baselines and an experiment protocol but did not go far enough on several of
the methodological points the orchestrator-side coordinator specified after
Codex's #493 review. This revision:

1. Names the three baselines as explicit, priority-ordered hypotheses
   (H1 primary/confirmatory vs frozen champion; H2/H3 secondary/exploratory
   context, not independently promotable) instead of an unordered
   "beat all three" bar.
2. Adds an explicit outer/inner nested walk-forward fold protocol (§6.2) — the
   first version's "nested WF" mention did not actually define outer vs inner
   folds or name the gating-layer-as-second-fitting-step leakage vector.
3. Cites the codebase's existing ~30-day embargo-on-fwd_60d-label convention
   by name (§6.3) instead of a generic "same embargo gap" reference, and
   extends it explicitly to the gating layer's own fitting.
4. Gives the sector-panel sample/support threshold a concrete two-part number
   (≥10 stocks AND ≥3 years history, §6.4) and specifies that undersized
   groups defer to the Level 3 panel rather than being merged into a
   different independent model.
5. Splits "calibration" into two distinct things (§6.5): the position-level
   uncertainty cap's required reliability-diagram-style validation against
   realized error (the first version's version of "calibration" was actually
   score normalization, a different mechanism, reusing the same word).
6. States explicitly that H1-vs-champion using the simplest variant is the
   ONE confirmatory test, and ties promotion criteria to this codebase's
   existing placebo-clean/regime-conditional WF-gate rigor rather than a
   generic "preregistered threshold."
7. Restores §4.4 (cross-reference mechanism), §5.1's recommendation paragraph,
   and §5.3 (gating implementation, including the `REGIME_WEIGHTS` fixed-gate
   snippet and learned-gating discussion) — present in the original
   orchestrator memo but dropped in the first rehoming pass.
8. Restores and softens §8 "Connection to F4 Option A (#479)" — dropped
   entirely in the first pass. Reframed per the coordinator's fix: this
   research is potential future input to #479, not something that resolves
   or substitutes for the operator decision #479 requires.
9. Adds an explicit open question (§9 item 5) on whether Phase 1 needs
   ask-first authorization as a live-tree-adjacent research action, beyond
   the "is per-ticker unfreezing authorized" phrasing the first pass used.

## What this PR contains

- `doc/research/2026-07-12-multi-panel-ensemble-architecture.md` — the research
  memo: academic survey (MIGA, PPFM, AlphaMix, AlphaCrafter, Two-Level
  Uncertainty), current system assessment, candidate Hierarchical MoE
  architecture (incl. cross-reference mechanism, §4.4), practical constraints
  (104-stock universe, sector sample sizes, gating implementation), the three
  falsifiable hypotheses (H1/H2/H3), full experiment protocol (nested WF,
  leakage controls, sample/support thresholds, calibration, multiple-comparison
  treatment, promotion criteria), a 4-phase staging plan, the softened #479
  connection, and open questions.
- This progress note.

## Key design choices

1. H1 (Phase 1+2, fixed gating, vs frozen champion) is the ONE confirmatory
   test; H2/H3 are secondary/exploratory context, never independently
   promotable
2. Phase 4 (learned gating) is explicitly CONTINGENT on a validated H1 edge;
   a negative H1 result ends the program there, not a fallback to Phase 4
3. Nested outer/inner WF folds: outer folds reserved for the H1/H2/H3
   confirmatory comparison only; gating-weight/network selection happens on
   inner folds exclusively
4. ~30-day embargo on fwd_60d label (existing WF-gate convention) applies at
   every level, including the gating layer's own fitting
5. Sector groups need ≥10 stocks AND ≥3 years history for their own WF gate;
   below that, defer to the Level 3 panel
6. The uncertainty cap needs its own realized-error calibration check before
   Phase 3 ships it — separate from score normalization
7. Sector grouping fixed before training (no data-driven sector assignment)

## Verification

- Research-only: no code, config, or behavioral change. `[VERIFIED]`
- All paper citations checked against source URLs (unchanged from the first
  pass). `[VERIFIED]`
- Rehomed from orchestrator (PR #493, closed) to model repo per codex review
  on repo ownership; this revision addresses methodological gaps found on
  audit of the first rehoming pass against the coordinator's full spec.
