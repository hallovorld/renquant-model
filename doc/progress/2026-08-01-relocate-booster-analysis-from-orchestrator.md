# One boundary error, committed four times in one night — relocated

**Date:** 2026-08-01 · `renquant-model`

## What happened

Four PRs opened in `renquant-orchestrator` tonight put **model-artifact analysis** in the
orchestrator. All four drew the same review `[codex on orch#712, #713, #716, #718]`, in
four separate messages:

> *"model-artifact evidence belongs in renquant-model … orchestrator should consume a
> versioned gate result and fingerprints, not host a parallel evaluator."*

Correct, and it is a rule I already hold: `CLAUDE.md`'s Hard Boundaries say *"Do not
implement model training internals here. Do not implement signal/decision tree internals
here"*, and my own register carries *"respect pipeline boundaries — never encode other
repos' internals in orchestrator."* I did not violate it once and get caught; I violated it
**four times in one night** without noticing, because each PR looked like the previous
one's natural next question.

## What moved

| tool | what it measures |
|---|---|
| `tools/booster_real_panel_divergence.py` | 12 same-recipe boosters disagree on **35.7%** of the real top decile (median over 20 sessions), 67% worst pair |
| `tools/booster_consensus_structure.py` | **66.9%** of traded slots carry a majority, **25.9%** unanimity; union 2.50× one arm |
| `tools/gate_projection_blindspot.py` | all **6** fields the gate hashes are constant across the 12; per-artifact OOS IC exists and is unread, and is **under-powered** (0.51–0.65 SE at 3 folds) |
| `tools/wf_corpus_recipe_match.py` | clf's recipe matches **0 of 85** corpus folds; dropping `params` alone said 82 |

Tests and evidence corpora moved with them. **44 tests pass in the new home**; the suite is
**1203 passed, 2 skipped**. Only the test import roots changed (`ops/renquant104` →
`tools`) — no tool logic was edited, so the published numbers are the same objects.

## What stays behind, and what is NOT done here

Each orchestrator PR is reduced to a **pointer progress-doc** recording the finding and
naming this home, per the standing rule *"relocate, don't just close"*.

**Not done:** the half of #713/#718 that codex assigns to `renquant-backtesting` — the WF
gate/admission *contract* itself. Nothing here changes gate behaviour; these tools only
read artifacts the gate already stamped. Defining a versioned gate-result handoff that the
orchestrator consumes is a separate design task in the owning repo, and inventing one here
would repeat the error in a third place.

## The pattern worth keeping

The boundary is easy to hold when a PR is obviously about training. It is hard when the PR
is *"measure what the gate did"* — that reads like orchestration and is not. The
discriminator that would have caught all four: **does this open a model artifact and
compute a number from its contents?** If yes, it is model-repo work regardless of what
question prompted it.
