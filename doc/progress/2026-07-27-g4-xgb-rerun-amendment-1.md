# G4 XGB rerun — amendment 1 (batch-1 void + proven matrix)

## STATUS
delivered

## WHAT
Preregistration AMENDMENT only — no code, and NOTHING RUNS BEFORE THIS PR
MERGES. Voids batch 1 (leakage-guard stop at bar 1; zero evidence; the
frozen profile never engaged walkforward) and freezes the PROVEN matrix:
gate-builder-derived prod-semantic config (43-fold calibrated manifest, QP
strict inherited), `--no-compare` single leg, two post-steps per seed
(forward-returns backfill → model#65 converter), per-seed tripwires
(models>0, score_distribution>0), the IMMUTABLE frozen input bundle
(/Users/renhao/renquant_bundles/g4-rerun-inputs-20260727, 4,429 files,
root 8072ca77…aea1, MANIFEST committed in this PR) consumed by the
worktree — live-tree copies were smoke-era staging ONLY and are no longer
a provisioning path; guard enforced THROUGH the driver
(renquant_backtesting.wf_gate.input_bundle_guard @ 1bb24559,
--input-bundle flags + six explicit covered roots, exit 4 pre / exit 6
post); offline proxy enforcement (no refresh hatch); measured wall-clock
~24 min/leg. Seeds/SHA table/cover rule/abort rules unchanged.

## WHY/DIR
Batch 1 froze a never-executed invocation — the process failure. The
amendment adds the rule it violated (no freeze without a completed
end-to-end smoke on the exact environment) and satisfies it: seed-999
smoke ran the full chain (10 bars, 10+10 ledger pairs, exact DB cover,
converter 10/10 admitted, EXPLORATORY_ONLY stamped) before this freeze.

## EVIDENCE
Smoke B (the ENFORCED command, 2026-07-27 ~11:52Z, backtesting @
1bb24559): INPUT BUNDLE PREFLIGHT OK → 10 bars/121 models → POST-RUN OK,
exit 0; post-steps on the Smoke-B DB/ledger: backfill 1,170 rows;
converter @ frozen 9b4970cb: 0 provenance rejects, exact ledger↔DB cover,
10/10 admitted (ledger fingerprint sha256:7eff7427…bc69). Smoke A
(~09:23Z, pre-enforcement) retained as the original chain proof. Both
quarantined as non-evidence. Forensic
grounding: the weekly WF gate (2026-07-26 log) is the only continuously
verified sim path and uses the same derive-from-prod mechanism; static
sim profiles are QP-drifted (contract added 2026-05-21) or start-gapped.

## NEXT
Codex review → merge = freeze → provision per §2 → launch 5 seeds
(~2–4 h) → per-seed total report → model#64 re-review with the first
admissible ledger-backed corpus.
