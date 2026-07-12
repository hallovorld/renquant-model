# 2026-07-12 — Ensemble combination experiment design

## Bottom line

Design doc for multi-model score combination: staged L1→L4 ladder (equal-weight
→ inverse-variance → linear stacking → regime-conditional static weights).
Explicitly excludes sector panels, learned gating, and hard routing (per-ticker
model selection), with literature justification. Each level has a pre-registered
go/no-go gate. This revision (below) closes out Codex's CHANGES_REQUESTED
review (PR #47, 2026-07-12T19:12:03Z) — ownership, the L2/L3 expert-set
confound, the inference/multiplicity protocol, the combined-observable
definition, L4's combinatorics, and two citation inaccuracies.

## Revision note (this pass)

Codex's review (independently verified: both cited RegimeFolio and QuantBench
claims were checked against the actual arXiv abstracts and confirmed wrong as
described) found the design directionally sound but not yet able to identify
a causal, deployable combination improvement. This revision applies all six
of Codex's points, unabridged:

1. **Ownership (lines 5-6).** Corrected the cross-repo ownership: this repo
   (model) now owns the research design, the WF runner, and the fitted
   ensemble specification — not just base-scorer training. Orchestrator is
   scoped to invoking a versioned run and retaining the immutable run bundle
   (scheduling/provenance only); pipeline is scoped to consuming a selected,
   immutable ensemble spec at inference (no research logic, no fitting). The
   prior text assigned the experiment harness to orchestrator, which
   conflicted with repo boundaries.

2. **Expert-set confound (new §3.1bis).** L3 was being compared to L2 even
   though L3 adds a third expert (per-ticker tournament) that L1/L2 never
   had — a gain could be caused by the added expert, not the stacking method.
   Added a same-set control, **L1-3E** (equal-weight over the same 3-expert
   set L3 uses), and changed L3's advance criterion to require beating
   **both** L2 and L1-3E. Updated the §3.1 ladder diagram, §3.4's criterion,
   §5.2/§5.3's phase table and decision tree to show the L1-3E branch.

3. **Inference and multiplicity protocol (§4.1, §4.2, §4.4 rewritten).**
   `fwd_60d` labels overlap heavily, so per-window ICs are not IID and a
   plain paired t-test understates the true standard error. §4.1 now
   specifies non-overlapping outer blocks (≥ label horizon + embargo) as the
   primary approach, with a moving-block/stationary bootstrap or HAC-adjusted
   test as the pre-registered fallback if block count is too small for power.
   §4.4 replaces the "3 comparisons, flat Bonferroni" claim with the full
   7-comparison hypothesis family (L1-vs-champion, L2-vs-L1, L1-3E-vs-L2,
   L3-vs-L2, L3-vs-L1-3E, L4-vs-L3, final-winner-vs-champion) plus the
   level-selection step itself, corrected via Holm-Bonferroni step-down or an
   explicit hierarchical/closed-testing gatekeeping procedure (with its
   precondition — later gates only run if earlier gates pass — stated
   explicitly, not just assumed). Also added a required costed,
   decision-level co-primary pass condition (net-of-cost Sharpe/return under
   a FIXED score-to-portfolio mapping, turnover, and risk constraint held
   fixed across levels) — ΔIC ≥ 0.005 alone is no longer sufficient.

4. **Combined-observable definition (new §4.1bis).** Before any combination
   method runs: a common causal (no-lookahead) score normalization and
   consistent orientation across models; an exact as-of-timestamp discipline;
   a picked (not left open) missing/stale-expert fallback — exclude and
   re-normalize remaining weights, rather than drop the whole observation;
   and immutable fingerprints for every base-model score snapshot, tied to
   this codebase's existing canonical
   `renquant_common.model_fingerprint.model_content_sha256` (the same
   fingerprint discipline adopted after the prior hand-copied-fingerprint
   incident). §3.3 (L2) is rewritten to operate on these normalized scores
   rather than raw model outputs, to justify or drop the independent-variance
   assumption, to require covariance shrinkage, and to fix the rolling-window
   timing in advance.

5. **L4 combinatorics (§3.5).** Corrected: 3 experts at 0.05-increment
   weights give C(22,2) = 231 simplex points per regime (not "~200"), and
   231³ ≈ 12.3 million joint three-regime tables if jointly selected (not
   "~200 × 3"). Added causal HMM fitting, a proposed state-occupancy minimum
   (≥60 trading days, flagged as a proposed floor, not proven-optimal),
   shrinkage toward equal weights with the shrinkage intensity chosen via
   inner-inner validation, and an equal-weight/pooled-table fallback below
   the occupancy floor. This multiplicity is now explicitly folded into the
   §4.4 family-wise correction rather than left as an uncounted separate
   search.

6. **Citations and unsupported claims.** (a) §3.2's "if L1 loses, nothing
   fancier will win either" is reframed as a pre-committed resource-
   conservation stopping rule, not a proven statistical implication —
   heterogeneous/correlated errors can in principle let a constrained
   combiner beat equal-weight even where equal-weight itself loses. (b)
   RegimeFolio corrected to a 2025 preprint (was stated as 2024) using a
   VIX-based classifier with dynamic mean-variance allocation (was
   incorrectly described as an HMM classifier with static weights); the
   citation is now narrowly qualified as support for regime-conditional
   ensembling as a general concept only, not for this design's specific
   HMM + static-weight mechanism. (c) QuantBench's claim that "production
   systems deliberately use linear regression as meta-model" is removed
   everywhere it appeared (§3.4 and the §6 exclusions table) — QuantBench is
   a benchmark-platform paper and does not support that claim; the
   linear-only choice now rests solely on the overfitting-risk argument,
   which stands on its own. (d) The Forecast Combination 50-Year Review
   citation (§8) is reframed to the "plausibility, not transferability"
   convention already used in the companion multi-panel design (model PR
   #45, §1): it supports testing equal-weight vs. more complex combinations
   as a well-established prior, not proof that this specific ladder will
   outperform in this pipeline's universe/turnover/cost regime.

This revision stays design-only and does not authorize a live combiner
anywhere. §1 (problem statement), §2 (hard-routing literature review), the
unflagged rows of §5/§6, and §7 (relationship to PR #45) are unchanged except
for the targeted cross-references above.

## What this PR contains

- `doc/research/2026-07-12-ensemble-combination-experiment.md` — full experiment
  design: problem statement, literature evidence against hard routing (§2),
  4-level combination ladder with same-set controls (§3, §3.1bis), nested WF
  protocol with dependence-robust inference and the combined-observable
  definition (§4, §4.1bis), prerequisites and phasing (§5), explicit
  exclusions with rationale (§6), relationship to prior design PR #45 (§7),
  15+ references with corrected citations (§8).
- This progress note.

## Key design choices

1. Soft combination (weighted average), not hard routing (per-ticker model
   selection) — 50+ years of forecast combination literature
2. Staged ladder with pre-registered go/no-go at each level, now including the
   L1-3E same-set control so expert-set gains are never mistaken for
   combination-method gains
3. Linear-only meta-model (no neural/tree stacking) — justified purely on
   overfitting-risk grounds at this scale, not by appeal to QuantBench (that
   citation was removed as unsupported)
4. Regime weights by grid search on inner folds, not learned gating, with
   occupancy minima, shrinkage, and an equal-weight fallback
5. Sector panels excluded at 104-stock scale (insufficient sample)
6. Supersedes combination method from model PR #45; retains model-building
   vision and experiment protocol
7. Model repo owns the research/WF runner/ensemble spec; orchestrator invokes
   and retains the run bundle; pipeline consumes the immutable spec at
   inference — corrected from the original ownership line

## Verification

- Design-only: no code, config, or behavioral change; no live-combiner
  authorization anywhere in the revised text. `[VERIFIED]`
- All literature citations checked against source. `[VERIFIED]` — the
  RegimeFolio (arXiv:2510.14986) and QuantBench (arXiv:2504.18600) citation
  errors Codex flagged were independently re-verified against the arXiv
  abstracts before this revision and confirmed accurate as described.
