# PREREGISTRATION — G4 PatchTST 43-fold Modal rescore (corpus generation only)

**Frozen on merge; nothing dispatches before.** Scope: generate the
PatchTST fold-artifact corpus (training + local calibrators). The
subsequent WF sims + converter runs (the PatchTST analog of the XGB
batch-3) are a SEPARATE prereg once these artifacts exist. No G4
disposition; every downstream output remains `EXPLORATORY_ONLY`.

**Refs:** operator grant 2026-07-27 ("modal 预计开销低于20可以开工" — a
$20 HARD cap), backtesting#76 (Modal driver + promotion quarantine),
backtesting#80 (timeout 7200 default, probe-measured), the staged-1
probe + the pre-freeze smoke below, model#78/#79/#80 house rules
(smoke-before-freeze, total reporting, abort-and-void).

## 1. Frozen run matrix

| item | frozen value |
|---|---|
| code | renquant-backtesting `0e140c5825b90a162c242ee07337371104847a98` (fresh clone, NOT a working tree — includes #81's bounded pilot/resume dispatch, codex-approved), executor `wf_gate.modal.executor`; sibling repos symlinked read-only per the #76 assembly convention |
| invocation (TWO-PHASE, #81 bounded dispatch — the P0-mandated enforceable cap) | PHASE 1 (pilot, exactly 3 folds — the 3 newest grid cutoffs): `python -u -m renquant_backtesting.wf_gate.modal.executor --select-cutoffs 2026-03-02,2026-02-09,2026-01-19 --gpu T4 --execute --skip-calibrators --timeout-seconds 7200 --repo-root <scratch>/repo-root`. THEN the frozen projection gate: `--print-cost-projection --run-id <pilot run> --project-folds 40 --rate-usd-per-hour 0.59` — dispatch PHASE 2 ONLY IF projected + spent-to-date ≤ \. PHASE 2 (exactly the remaining 40, resume, zero retrain): `--select-cutoffs <all 43> --run-id <pilot run> --gpu T4 --execute --skip-calibrators --timeout-seconds 7200 --dispatch-note "cost GO: <projection figures>" --repo-root <scratch>/repo-root` — #81's resume dispatches only absent folds, refuses retrains/overwrites, fail-closes on missing/mismatched provenance, and keeps ONE auditable manifest with per-dispatch history |
| recipe | `recipe_id sha256:b4e47e2cd77af660` (the smoke's), dataset `data/transformer_v4_wl200_clean.parquet`, calibrator raw-label panel per recipe; training seed = the recipe's seed44 (single seed, documented — training-seed multiplicity is out of budget and out of scope) |
| expected per-fold | ~2384 s train-only on T4 (smoke-measured); timeout 7200 s |
| expected terminal signature | exit 1 WITH `failed_folds: []` and `quarantine_reasons: ["skip_calibrators_diagnostic"]` — the #76 gate DESIGNEDLY quarantines train-only corpora as non-promotable; exit 1 + empty failed_folds is SUCCESS for this batch |
| budget | HARD cap $20 total (operator grant), $1.45 already spent (probe + smoke) → batch budget $18.55. Projection: 43 × 0.663 h × $0.59 ≈ $16.8 + CPU/mem overhead |
| cost gate (mechanized, supersedes the prose tripwire) | the two-phase structure above IS the cap enforcement: phase 1 risks exactly 3 pods (~\.20); phase 2 cannot dispatch without the recorded projection GO (stamped via `--dispatch-note` into the audit record). Any `failed_folds ≠ []` in either phase → halt + amendment (no partial salvage) |
| calibrator leg (LOCAL, $0) | after all 43 folds land: `fit_calibrator --method platt --batch-size 512` per fold on THIS machine, ≤8-way parallel, against the recipe's raw-label panel; output = the calibrated manifest via the reviewed `write_manifest` (leakage invariant enforced) |
| outputs | quarantined run namespace `artifacts/walkforward_patchtst_runs/<run_id>/` in the SCRATCH repo-root only — never the umbrella, never a committed corpus; total report with per-pod elapsed/checksums + manifest + provenance sidecar digests |

## 1b. Smoke artifact index (round-1 P1)

- Smoke log: `<scratchpad>/modal-probe/logs/smoke-trainonly-t4.log`
- Pod log: `<scratchpad>/modal-probe/logs/pod-run2-full.log` (probe) — smoke pod facts in the sidecar below
- Manifest + provenance sidecar: `<scratchpad>/modal-probe/repo-root/backtesting/renquant_104/artifacts/walkforward_patchtst_runs/wf-pt-b4e47e2c-20260727T195313Z/walkforward_patchtst_manifest.json{,.provenance.json}` — carries `pod_facts` (worker ta-01KYJJ79V42GFH5K8PB40P2TMR, image im-7gxA3w8FvDM67fSDfov31i, elapsed 2384.4075977802277, device cuda, result_checksum sha256:8a926df3bb9e4a66), `failed_folds: []`, and the diagnostic-quarantine record `quarantine_reasons: ["skip_calibrators_diagnostic"], promotion_ready: false`
- Fold artifact: `.../wf-pt-b4e47e2c-20260727T195313Z/2026-03-02/hf_patchtst_all_seed44_model.pt` + `.metadata.json` (effective_train_cutoff 2025-12-05)

## 2. Pre-freeze smoke (house §0 rule, satisfied)

2026-07-27 19:53Z, the frozen invocation with `--staged 1`, code at
`9942bce6`: fold 2026-03-02 completed 1/1, `failed_folds: []`, pod
`elapsed_seconds 2384.41` (cuda), result_checksum `sha256:8a926df3bb9e4a66`,
run `wf-pt-b4e47e2c-20260727T195313Z`, volume content-commit
`sha256:8e6af69a32a65093`, AC7 freshness PASS (panel max 2026-04-28 ≥
required 2025-12-08), exit 1 with the exact quarantine signature above.

## 3. Non-goals / honesty

Corpus generation only: no sims, no converter, no Phase-A evaluation, no
disposition. The dual-expert evidence-volume prerequisite of Phase 0 is
NOT satisfied by this batch alone (it produces artifacts, not admissible
per-date evidence — that requires the follow-up sim prereg). Total
reporting: every pod's outcome published; a fully-failed batch is a
reported result.
