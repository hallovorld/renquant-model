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
| code | renquant-backtesting `9942bce692f6` (fresh clone, NOT a working tree), executor `wf_gate.modal.executor`; sibling repos symlinked read-only per the #76 assembly convention |
| invocation | `python -u -m renquant_backtesting.wf_gate.modal.executor --staged 43 --gpu T4 --execute --skip-calibrators --timeout-seconds 7200 --repo-root <scratch>/repo-root` |
| recipe | `recipe_id sha256:b4e47e2cd77af660` (the smoke's), dataset `data/transformer_v4_wl200_clean.parquet`, calibrator raw-label panel per recipe; training seed = the recipe's seed44 (single seed, documented — training-seed multiplicity is out of budget and out of scope) |
| expected per-fold | ~2384 s train-only on T4 (smoke-measured); timeout 7200 s |
| expected terminal signature | exit 1 WITH `failed_folds: []` and `quarantine_reasons: ["skip_calibrators_diagnostic"]` — the #76 gate DESIGNEDLY quarantines train-only corpora as non-promotable; exit 1 + empty failed_folds is SUCCESS for this batch |
| budget | HARD cap $20 total (operator grant), $1.45 already spent (probe + smoke) → batch budget $18.55. Projection: 43 × 0.663 h × $0.59 ≈ $16.8 + CPU/mem overhead |
| cost tripwire | after the FIRST 3 pods complete, project total = mean(elapsed) × 43 × $0.59/h + observed overhead; if projection + spent > $20, `modal app stop` immediately → amendment prereg. Any `failed_folds ≠ []` → halt + amendment (no partial salvage) |
| calibrator leg (LOCAL, $0) | after all 43 folds land: `fit_calibrator --method platt --batch-size 512` per fold on THIS machine, ≤8-way parallel, against the recipe's raw-label panel; output = the calibrated manifest via the reviewed `write_manifest` (leakage invariant enforced) |
| outputs | quarantined run namespace `artifacts/walkforward_patchtst_runs/<run_id>/` in the SCRATCH repo-root only — never the umbrella, never a committed corpus; total report with per-pod elapsed/checksums + manifest + provenance sidecar digests |

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
