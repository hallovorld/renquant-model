# Design Amendment: v2-block-rebalance

Experiment version: `v2-block-rebalance`
Amendment date: 2026-07-13
Amends: `doc/research/2026-07-12-ensemble-combination-experiment.md` (model PR #48)

## Block-rebalance arm definition (frozen)

Phase A evaluates L1 (equal-weight combination of admitted experts) against
the frozen champion under a **block-rebalance** policy:

- Portfolios are selected every `block_length_days` sessions (default: 60).
- Holdings are carried between rebalance points with no intermediate trades.
- Turnover costs are charged only at rebalance points.
- Non-overlapping blocks are spaced by `block_length_days + embargo_sessions`
  positions in a frozen session calendar.
- The embargo buffer (default: 10 sessions) ensures no forward-return overlap
  between adjacent evaluation blocks.

## Non-production claim

The block-rebalance evaluation is a **distinct estimand** from the daily
production champion's rebalance policy. Results from this arm:

1. **Cannot** establish improvement over the daily-rebalance production
   champion — the estimands differ.
2. **Cannot** be promoted to `L1_BEATS_CHAMPION` without a separate
   daily-policy validation step (not implemented in this PR).
3. Are always capped at `EXPLORATORY_ONLY` until the nested WF/purging
   harness exists and produces verifiable evidence (design doc §5.1).

A favorable block-rebalance result is necessary but not sufficient
evidence for deployment. The production champion's daily rebalance policy
remains the binding comparison for any deployment decision.

## Immutable policy artifact

The champion's frozen policy is bound to the experiment via
`champion_policy_artifact_digest` in the manifest. The runner verifies
the artifact's SHA-256 digest against the manifest at runtime — a missing
or mismatched artifact is a hard failure.

## Known scope boundaries

Phase A is a discovery-stage signal presence test. It answers: "does the
ensemble contain cross-sectional information worth investigating?" It does
NOT answer: "should we deploy the ensemble in production?" The following
limitations are intentional scope boundaries, not oversights.

### Known estimand gap

The production champion rebalances daily. Phase A uses block-rebalance
(every 60 sessions) to produce non-overlapping evaluation windows for
statistically independent comparison. These are different estimands:

- Block-rebalance carries stale positions between rebalance points; the
  daily champion responds to new information every session.
- Block-rebalance has lower turnover by construction, which flatters its
  cost-adjusted returns relative to a daily policy.
- A Phase A win proves cross-sectional signal presence under a simplified
  regime. It does NOT prove the ensemble would outperform the champion
  under the champion's own daily rebalance policy.

**A positive Phase A result is necessary but NOT sufficient.** Phase B
(daily rebalance under nested WF) is required before any production claim.

### Forward-looking bias controls

Nested walk-forward with combinatorial purging (the gold standard for
temporal cross-validation in financial ML) is NOT built in Phase A. What
Phase A does have:

- **Non-overlapping blocks**: evaluation windows do not share any sessions,
  preventing return-sharing between test folds.
- **Embargo sessions** (default 10): buffer between adjacent blocks ensures
  no forward-return overlap even when labels extend beyond block boundaries.
- **Frozen session calendar**: all evaluation dates verified against a
  pre-declared calendar with digest verification; missing sessions are a
  hard failure, not a silent compression.
- **PIT score admission**: scores enter Phase A only through the Stage 0
  admissibility ledger, which requires artifact provenance and digest
  verification before any score is used.

These controls are weaker than nested WF with purging but sufficient for
a discovery-stage signal presence test where the goal is to screen out
ensemble configurations with no signal at all. Phase B must implement
proper nested WF with combinatorial purging before any production claim.

### Portfolio construction limitations

Phase A uses Top-N equal-weight portfolio construction. This is
deliberately simple:

- **Rationale**: if equal-weight Top-N ensemble cannot outperform the
  champion, no amount of portfolio optimization will save it. Top-N is
  a lower bound on achievable performance, not a realistic production
  portfolio.
- **No adverse selection cost**: Phase A does not execute real trades.
  It uses PIT scores with the same sim cost model as production. Adverse
  selection (market impact, information leakage from order flow) is a
  real-execution concern that Phase B must model when evaluating
  deployable portfolio construction.
- **No portfolio optimizer**: mean-variance, risk parity, or
  Black-Litterman optimization would introduce optimizer estimation
  error and make it harder to attribute performance to signal quality
  vs. portfolio construction. Phase A isolates signal quality.

## Phase A → Phase B graduation requirements

A Phase A GO result **does not authorize progression to production**. It
authorizes only manual follow-up design work: an independent review of
Phase A's output and, if warranted, the specification of a Phase B
experiment with its own pre-registration. Phase A cannot emit a promotable
production GO — it can only establish whether the ensemble signal contains
cross-sectional information worth investigating further.

Any positive Phase A result requires **independent review** (not automated
promotion) before Phase B design begins.

Phase B must address ALL of the following before any production deployment claim:

1. **Daily rebalance estimand**: match the production champion's rebalance
   cadence exactly. No block-rebalance shortcuts.
2. **Nested walk-forward with purging**: combinatorial purged
   cross-validation (de Prado, 2018) with expanding or rolling training
   windows. No re-use of Phase A's simplified block structure.
3. **Portfolio optimizer**: replace Top-N equal-weight with the production
   portfolio construction pipeline (QP, sector/correlation caps, position
   sizing). Test both L1 (equal-weight combination) and L2+ (learned
   combination weights) under realistic constraints.
4. **Adverse selection / market impact cost model**: model information
   leakage from order flow, price impact as a function of participation
   rate, and slippage beyond the flat 5 bps base cost.
5. **Minimum 12 non-overlapping blocks under Phase B protocol**: the same
   statistical rigor as Phase A, but under the daily rebalance estimand.

Phase B is a separate experiment with its own pre-registration, manifest,
and design amendment. Phase A's results are input evidence, not binding.

## References

- Experiment manifest: `experiment_manifest.py` (`experiment_version: "v2-block-rebalance"`)
- Phase A runner: `phase_a_runner.py` (§4.2 non-overlapping outer blocks)
- Design doc: `doc/research/2026-07-12-ensemble-combination-experiment.md`
- Codex review round 12 (2026-07-13): fail-closed calendar + verified policy artifact
- Codex review round 13 (2026-07-13): return-date coverage + typed policy schema + GO language fix
- Operator design review (2026-07-13): estimand mismatch, nested WF, portfolio construction
