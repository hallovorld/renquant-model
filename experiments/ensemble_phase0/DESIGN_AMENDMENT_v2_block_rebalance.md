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

## References

- Experiment manifest: `experiment_manifest.py` (`experiment_version: "v2-block-rebalance"`)
- Phase A runner: `phase_a_runner.py` (§4.2 non-overlapping outer blocks)
- Design doc: `doc/research/2026-07-12-ensemble-combination-experiment.md`
- Codex review round 12 (2026-07-13): fail-closed calendar + verified policy artifact
