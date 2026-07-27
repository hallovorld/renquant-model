# G4 XGB rerun batch — preregistration PR

## STATUS
PREREG only; nothing runs before this PR merges (the freeze). No code.

## WHAT
`doc/research/2026-07-27-g4-xgb-rerun-prereg.md`: frozen 5-seed
{101–105} run matrix for the 27-month run_sim_104 replay in an isolated
umbrella worktree with a worktree-local pipeline-pin advance past #216;
admissibility judged solely by the merged #215/#216/#531/#78/#65 contract;
fail-closed total reporting; batch-level abort-and-void on any
pit_violation/digest-mismatch/cross-check failure; PatchTST explicitly NOT
executed (no-Modal stands) with the operator decision point named.

## WHY/DIR
pipeline#215 §3 step 5 requires seeds + rules frozen in a prereg BEFORE
launch; single-seed results stay exploratory. The batch generates the first
admissible ledger-backed XGB corpus and the end-to-end run model#64 needs.
It cannot and does not dispose G4 (EXPLORATORY_ONLY hard cap; v4 machinery
owns disposition) — the doc states this in §1 and defers to every frozen
constant/schema on conflict.

## EVIDENCE
Grounding audit against the standing machinery (v4 §4/§5, decision_schedule
contract v1, experiment_manifest v2-block-rebalance, phase_a_runner verdict
ladder + cap, 07-16 data audit, #531 PIN CAVEAT, #78 seed surface,
2026-06-03 ~3 h/run feasibility, 2026-05-09 reproducibility caveat). No
behavior claims — design/prereg only.

## NEXT
Codex review → merge = freeze → assemble isolated worktree → launch 5 seeds
(local CPU, ~15 h) → converter + ledger per seed → total report →
model#64 re-review with end-to-end evidence.
