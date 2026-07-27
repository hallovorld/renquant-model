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
(models>0, score_distribution>0), 4-group environment provisioning
manifest (untracked ohlcv/fund data + UNCOMMITTED live-tree re-stamped
calibrators and fresh models, copy-only with sha256 manifests), measured
wall-clock ~24 min/leg. Seeds/SHA table/cover rule/abort rules unchanged.

## WHY/DIR
Batch 1 froze a never-executed invocation — the process failure. The
amendment adds the rule it violated (no freeze without a completed
end-to-end smoke on the exact environment) and satisfies it: seed-999
smoke ran the full chain (10 bars, 10+10 ledger pairs, exact DB cover,
converter 10/10 admitted, EXPLORATORY_ONLY stamped) before this freeze.

## EVIDENCE
Smoke evidence (2026-07-27 ~09:23Z, quarantined as non-evidence for the
corpus): bars=10, models=121, WF cutoffs 2023-10-02/2023-10-23 with real
content digests + revision pins; score_distribution=1160; cover-rule PASS;
converter 0 provenance rejects, 10/10 admitted post-backfill. Forensic
grounding: the weekly WF gate (2026-07-26 log) is the only continuously
verified sim path and uses the same derive-from-prod mechanism; static
sim profiles are QP-drifted (contract added 2026-05-21) or start-gapped.

## NEXT
Codex review → merge = freeze → provision per §2 → launch 5 seeds
(~2–4 h) → per-seed total report → model#64 re-review with the first
admissible ledger-backed corpus.
