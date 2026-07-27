# AMENDMENT 2 — G4 XGB rerun batch (voids batch 2; re-freezes on the tax-fixed base)

**Amends** amendment 1 (merged model#79) and the base prereg (model#78).
Everything not restated here stands verbatim: seeds {101–105}, the input
bundle + root digest `8072ca77…aea1` + six covered roots + driver-enforced
guard, offline enforcement, §1 invocation and post-steps, tripwires, cover
rule, abort-and-void, PatchTST gating, non-goals.
**Frozen on merge; nothing launches before.**

## 0. Batch-2 VOID declaration (honest record)

Batch 2 launched 2026-07-27 13:18Z under the amendment-1 freeze and was
stopped at bar 2025-06-24 (~370/561) of seed 101 by
`validate_decision_trace_integrity`: `sell_economic_gaps: 1` — a REAL
kernel accounting bug, not an evidence-chain defect. Verified root cause:
`compute_disposed_lot_tax` taxed each positive-gain lot independently and
never netted losing lots of the same sell event; a mixed-sign multi-lot
disposal (top-up lot + original, full exit between the two bases — MA,
lots +126.9676/−193.2083 at rate 0.5) produced "net loss with positive
tax", and the validator fail-closed exactly as designed. The failure is
DETERMINISTIC (no RNG on the decision path) — every seed dies at the same
bar; partial seed-101 output was discarded, nothing salvaged.

Two findings of record: (a) the weekly WF gate always runs `--no-persist`,
so the persistence-side integrity validators are DEAD in the continuously
verified path — this batch was their first full-window execution; (b) the
live daily runner calls the SAME validator over the SAME tax function, so
the latent bug was a LIVE fail-close risk (any full exit of a topped-up
position between lot bases). Fix chain, both merged with codex approval:
renquant-pipeline#217 (mirror) and umbrella#532 (PRIORITY; bucket-netted
`compute_netted_capital_gains_tax` delegation; validator untouched).

## 1. Amended frozen revisions (supersedes the amendment-1/§4 rows shown)

| repo | frozen revision | change |
|---|---|---|
| umbrella worktree base | `15c218e7bd669ab03f883300c883cf4035d7c4d5` | #532 merge (tax fix + committed pipeline pin advance) |
| renquant-pipeline | `dbcab26556a0db474038ea8f9f2a76d85f944c12` | #217 mirror — now COMMITTED in the base lock (no longer a worktree-local advance) |
| renquant-backtesting (worktree-local) | `1bb245595691e3ab3d615d275219c3348427f0f6` | unchanged |
| renquant-common (worktree-local) | `591d8f70758bd64bb0f8024d0d59d7b6a1b5fe25` | unchanged |
| all other rows | unchanged from amendment 1 | model 5ef1c2d, strategy 5c3eae9d, execution c4163984, base-data 021ca647, artifacts c09d66f8, orchestrator ade07dd7; converter 9b4970cb |

Provisioning note of record: after the base advance, the worktree was
re-provisioned FROM THE BUNDLE (its purpose); the guard caught the
intermediate state (337 mismatches from git-restored tracked inputs)
before any run — working as designed. Copies into the worktree are made
writable (`chmod -R u+w` on the copied trees); the bundle itself stays
immutable.

## 2. Smoke C (the §0 process rule for the NEW base, satisfied)

2026-07-27 ~14:49Z, re-assembled worktree at the table above, §1 enforced
invocation verbatim (guard flags + offline proxy), seed 999:
`INPUT BUNDLE PREFLIGHT OK` → 10 bars, models=121, walkforward engaged →
`INPUT BUNDLE POST-RUN OK`, exit 0, final value identical to Smokes A/B
($100,036 — the tax fix is inert on this window, which contains no
mixed-lot sell; the fix's own MA-case regression tests pin the changed
arithmetic in both kernel repos). The §1 post-steps then ran on the
Smoke-C DB/ledger (`sim_runs_smoke999c.db` +
`wf_provenance/wfsim-20260727T144822Z-02cc7fbc.jsonl`, 10 `fold_resolved`
+ 10 `score_committed`) under the NEW base with the frozen converter
`9b4970cb`: backfill 1,170 rows; **0 provenance rejects, exact ledger↔DB
cover, 10/10 admitted** (`DONE: expert=xgb wrote=10 rejected=0
(no_provenance=0) admitted=10`). Quarantined as non-evidence.

## 3. Expectation binding future readers

Bar 2025-06-24 of every seed is where batch 2 died; batch 3 passing that
bar with a zero-tax MA disposal row (validator-clean) is the in-run
confirmation that the fix chain is live in the executing kernel. If any
OTHER integrity counter fires later in the window, that is a NEW defect:
abort-and-void, diagnose, fix, amendment 3.
