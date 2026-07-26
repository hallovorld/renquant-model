# Results — blend confirmatory v2 (fresh seeds 60-69): CONFIRMED, independent draw

Date: 2026-07-26
Prereg (FROZEN, merged): `doc/research/2026-07-25-blend-confirmatory-v2-prereg.md` (model#75)
Evidence (REPLAYABLE): `doc/research/evidence/2026-07-25-blend-confirmatory-v2/confirmatory-bundle.json`
Chain: step 3 of the model#73 reopening condition — screen (#74, PASS, committed
evidence) → re-frozen prereg (#75) → THIS run.

## Verdict — CONFIRMED [VERIFIED, replayable, out-of-draw]

Executed with the prereg's verbatim frozen command line (seeds 60-69 —
never used anywhere in this line; `--prereg-path` bound; manifest stamps
freeze commit `4a040a9`, frozen-section digest, ancestor check True).

| condition | frozen requirement | measured |
|---|---|---|
| primary | CI90 lower bound > 0 | **+0.0156** (diff +0.0687, CI [+0.0156, +0.1269]) |
| guard (a) | ≥8/10 seed signs positive | **9/10** |
| guard (b) | winsorized-±50% diff ≥ 0 | **+0.0117** |

blend +0.2558/60d vs rank60 +0.1870/60d on this draw. Replay verified
pre-submission: `deserialize_result(bundle["series"])` → `verdict_from_bundle`
recomputes verdict/CI/guards exactly.

## Why this is stronger evidence than the original CONFIRMED

The 42-51-draw result (+0.0552, lower bound +0.0018) was procedurally
downgraded for its provenance chain and was, numerically, a just-clears
read. This draw is INDEPENDENT (disjoint seeds), executed under the
repaired freeze-binding machinery, and clears with a lower bound 8× the
original's. Two independent seed draws, same direction, comparable
magnitude (+0.055 / +0.069): the objective/harvest-alignment effect is
not a seed artifact.

## Seed-noise disclosure

The fresh draw's BASELINE levels are visibly lower (rank60 +0.187 vs
+0.232 on 42-51) — seed-draw variance in LEVELS is real and material,
which is exactly why the paired within-draw contrast is the registered
statistic and why cross-draw level comparisons are not admissible.

## Frozen consequence

Per prereg v2: **the PARKED shadow design (renquant-pipeline#213) unblocks
at its §5 step-2 gate.** Rollout steps remain separate reviewed PRs
(model artifact → pipeline shadow slot → orchestrator readout job); the
launchd/machine-landing step keeps the standard operator grant; nothing
here changes production. The orchestrator VERDICTS row lands after this
PR is accepted (the recorded ledger convention).

## Boundaries

Survivorship panel (levels inflated; paired contrast robust); fwd_60d
label; one model family; historical corpus — the decisive evidence for
any production decision remains the #213 shadow-forward readout.
