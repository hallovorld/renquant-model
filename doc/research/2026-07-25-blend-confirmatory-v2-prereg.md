# Prereg v2 — CONFIRMATORY: blend objective, FRESH SEEDS (independent draw)

Date: 2026-07-25
Status: PREREGISTRATION — frozen on merge; the run and results land in a
SEPARATE PR that may not amend this document.
Chain: step 2 of the model#73 reopening condition. Screen (step 1, PASS,
committed evidence): `doc/research/2026-07-25-blend-construction-screen-prereg.md`
+ `evidence/2026-07-25-blend-construction-screen/screen-bundle.json`.

## What makes this an independent confirmation

Every prior run of this line (informal screens, the withdrawn #70/#73
sequence, the step-1 screen) used seeds 42-51. This confirmatory uses
**seeds 60-69 — never used anywhere in this line** — so the model-noise
draw is independent of everything previously observed. Combined with the
frozen rule below, a PASS here is a genuine out-of-draw confirmation, not
a replay of known numbers.

## Frozen spec (identical to #68 except the seeds and the citations)

- H: `blend` = per-date z(rank:pairwise@fwd60) + z(top-decile clf@fwd60)
  beats production rank:pairwise on the clean top-10 spread.
- Executor: `scripts/research_objective_blend_confirm.py` (merged,
  guard-faithful, replayable-bundle emitting), with SEEDS = (60..69);
  the seed change lands as a reviewed diff in THIS PR, nothing else may
  change in the executor.
- Same 5 purged folds, 60d embargo, per-arm matched within-date
  shuffled-label placebos.
- Inference: block bootstrap b=60, boot-seed 20260725, 90% CI on the mean
  paired per-date clean-spread difference.

## Decision rule — FROZEN

- CONFIRMED: CI lower bound > 0 AND ≥8/10 seeds positive AND
  winsorized-±50% diff ≥ 0. Consequence: the PARKED shadow design
  (renquant-pipeline#213) unblocks at its step-2 gate; rollout PRs proceed
  per its §5 (still no production change; still the normal WF-promote gate
  for any promotion).
- REFUTED: point estimate ≤ 0 → the line closes; the historical +24%
  is registered as seed-draw-fragile.
- INCONCLUSIVE: CI spans 0 with positive point → one extension to seeds
  70-79 is pre-authorized (single extension, both draws reported jointly,
  Bonferroni over the two reads); a second inconclusive closes the line
  as NOT-CONFIRMABLE-ON-CORPUS with the shadow question dead unless a
  materially different construction is preregistered.

## Boundaries

Survivorship panel; the +0.06 point estimates carry ~±0.05 CI half-widths
at 10 seeds (known from the seed-42-51 draw); fresh seeds may legitimately
land INCONCLUSIVE — the extension rule exists for exactly that, and is
capped at one use.
