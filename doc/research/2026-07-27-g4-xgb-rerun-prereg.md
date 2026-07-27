# PREREGISTRATION — G4 XGB walk-forward rerun batch (evidence generation only)

**Frozen on merge of this PR; no rerun launches before the freeze.**
**Refs:** pipeline#215 §3 step 5 (the freeze requirement) + §4 (non-goals),
pipeline#216, umbrella#531, backtesting#78, model#65 (the consuming
converter), DESIGN_AMENDMENT_v4 (§4 registration, §5 ownership),
`experiment_manifest.py` (v2-block-rebalance, frozen constants),
`phase_a_runner.py` (verdict ladder + EXPLORATORY_ONLY hard cap),
2026-07-16 Phase-A data audit (evidence-volume BLOCK).

## 1. What this preregisters — and what it cannot decide

This batch generates the FIRST `wf_sim_provenance.v1`-backed, ledger-admissible
XGB expert corpus, and provides the end-to-end evidence run that model#64's
remaining blocker requires. It is NOT a G4 disposition instrument:

- Phase-A verdicts remain UNCONDITIONALLY capped at `EXPLORATORY_ONLY`
  (`phase_a_runner.py` hard cap; no verified nested-WF harness exists).
- Phase 0 remains BLOCKED per the v4 header and the 2026-07-16 audit; this
  batch produces the XGB HALF of the dual-expert corpus only. The PatchTST
  half is compute-gated (§6) — Phase 0's dual-expert evidence-volume
  prerequisite is explicitly NOT satisfied by this batch.
- GO/KILL of G4 arises only from the standing registered machinery
  (v4 two-stage registration; pipeline `decision_schedule` contract v1).
  Nothing here amends any frozen constant, arm ladder, threshold, schema
  version, or ownership boundary; where this document and those sources
  conflict, those sources win and the run halts.

## 2. Frozen run matrix

| item | frozen value |
|---|---|
| seeds | **{101, 102, 103, 104, 105}** — 5 seeds, chosen before any run; no additions, no drops; ALL seeds reported regardless of outcome |
| driver | `renquant_backtesting.wf_gate.sim_driver` (run_sim_104 body), window fixed 2024-01-02 → 2026-03-28 (~27 months, driver constant) |
| per-seed invocation | `--seed <S> --compare-to strategy_config.json --sim-db-path data/sim_runs_seed<S>.db --equity-json out/equity_seed<S>.json --trade-log-csv out/trades_seed<S>.csv` |
| single authority leg | `--compare-to strategy_config.json` equals the candidate config name, which the driver deterministically treats as "no golden comparison leg" (`sim_driver.py` gates the golden run on `compare_to != strategy_config_name`). Frozen rationale: each `run_backtest` TRUNCATEs the sim tables, so a second leg sharing one `--sim-db-path` would overwrite the candidate observation while its provenance carries a different `sim_run_id` — the converter could not prove which leg the retained DB belongs to. One leg ⇒ 1:1 pairing: one `run_backtest`, one `sim_run_id`, one DB, one ledger |
| ledger↔DB pairing rule | a seed's corpus = the (`data/wf_provenance/<sim_run_id>.jsonl`, `data/sim_runs_seed<S>.db`) pair whose `sim_run_id` appears in that DB's `score_committed` observations; a DB containing observations from any OTHER `sim_run_id` voids the seed (§5) |
| execution | sequential or ≤2-way parallel on this machine (local CPU only; ~3 h/run per the 2026-06-03 feasibility study → ~15 h sequential); no Modal, no cloud spend |
| environment | one ISOLATED umbrella worktree assembled for this batch (see §4); NEVER the live tree, NEVER the live `.subrepo_runtime` |

## 3. Frozen admissibility requirements (references, not redefinitions)

Every date must satisfy the merged contract end-to-end, evaluated by the
model#65 converter with `--provenance-ledger` per sim run:

- complete `fold_resolved` + `score_committed` pair, matching keys and
  `artifact_digest` echo; `score_payload_digest` + `n_rows` equality on
  read-back; `input_watermark ≤ score_timestamp`; `persisted: true`;
  `is_real_content_digest: true` (pipeline#215 §2.1–§2.5, verbatim);
- admissibility-ledger gates as coded (missingness ≤20%, digest grammar,
  label horizon ≥60d, look-ahead check) — `admissibility_ledger.py` is the
  authority; this document adds NO new gate and relaxes none.

Reporting is fail-closed and total: per seed, the count of admitted dates and
EVERY rejection with its machine-readable reason code, published as-is. No
seed, date, or leg is dropped for looking bad; a seed whose corpus is fully
rejected is a reported result, not a discarded one.

## 4. Environment pinning (worktree-local; no live-surface mutation)

- Fresh `git worktree` of the umbrella at current `origin/main`, with its
  OWN lock edited (uncommitted, worktree-local) to advance exactly TWO pins:
  `renquant-pipeline` to current main (past #216 — the #531 PIN CAVEAT:
  without this the sink is `None`, zero provenance is emitted, and the
  batch is VOID, not silently passed) and `renquant-backtesting` to current
  main (past its #78 — the pinned revision otherwise lacks the
  `sim_driver --seed` surface this prereg's commands require). All other
  pins as on umbrella main. The batch report MUST list the exact resolved
  revision of EVERY runtime repo in the assembled worktree (and each
  provenance record's `revision_pins` independently attests them); all
  provenance/DB/output artifacts are collected from that assembled
  runtime's tree, nowhere else.
- `subrepo_assemble --sync` into that worktree's own runtime; the live
  tree, live lock, and live `.subrepo_runtime` are not touched. The lock
  pin advance for the LIVE surface ships later with its own reviewed PR and
  is not part of this batch.
- `revision_pins` captured per provenance record (adapter behavior) are the
  audit trail that the batch actually ran on the stated revisions.

## 5. Validity conditions and abort rule

The batch is VALID iff every launched seed completes and its ledger + sim DB
+ provenance JSONL are archived (per-seed: `data/wf_provenance/*.jsonl`,
`data/sim_runs_seed<S>.db`, equity/trade outputs, converter build manifest).
ABORT-AND-VOID (the whole batch, not the offending seed): any
`pit_violation: true` row, any read-back digest mismatch, or any converter
cross-check disagreement — these indicate implementation defects, and the
remedy is fix → NEW prereg (amendment PR) → rerun ALL seeds fresh. Partial
salvage of a defective batch is forbidden. (Context: the 2026-05-09 audit
recorded a non-reproducible 27-month replay under identical config; frozen
seeds make residual nondeterminism DETECTABLE via the provenance records —
cross-seed variance is a reported statistic, not a defect.)

## 6. PatchTST plan (NOT executed under this prereg)

The Modal 43-fold rescore path exists (backtesting#76) but the no-Modal rule
stands. Local MPS is the only permitted engine today (per-fold smoke: 38 s
MPS for 2 epochs; a full 43-fold multi-seed batch is materially heavier and
unscheduled). The operator decision point is explicit: EITHER lift the
no-Modal rule for a costed, capped rescore batch, OR authorize a multi-day
local MPS schedule. Until one is granted, the dual-expert corpus — and with
it Phase 0's evidence-volume prerequisite — remains BLOCKED, and saying
otherwise would be false.

## 7. Non-goals

No G4 disposition, no schedule change, no capital action, no live pin
advance, no edits to any frozen constant or schema. Outputs are
`EXPLORATORY_ONLY` by construction and are consumed only by the standing
Phase-A machinery.
