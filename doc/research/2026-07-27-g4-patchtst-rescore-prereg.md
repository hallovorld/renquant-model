# PREREGISTRATION — G4 PatchTST 43-fold Modal rescore (corpus generation only)

**Frozen on merge; nothing dispatches before.** Scope: generate the
PatchTST fold-artifact corpus (Modal train-only + local calibrators). The
subsequent WF sims + converter runs are a SEPARATE prereg once artifacts
exist. No G4 disposition; downstream outputs remain EXPLORATORY_ONLY.

**Refs:** operator grants 2026-07-27 ("低于20可以开工") and 2026-07-27
option B ("上限提到 $25，含探针花费" — a $25 HARD cap INCLUSIVE of the
$1.45 probe/smoke pre-spend), backtesting#76 (driver + diagnostic
quarantine), #80 (timeout default), #81 (bounded pilot/resume dispatch),
#82 (execute-time hard cost cap + immutable budget_contract), the
pre-freeze smoke (§3).

## 1. Frozen run matrix

| item | frozen value |
|---|---|
| code | renquant-backtesting `2fcec872d623` (fresh clone, NOT a working tree; contains #80+#81+#82), executor `wf_gate.modal.executor`; sibling repos symlinked read-only per the #76 assembly convention |
| recipe | `recipe_id sha256:b4e47e2cd77af660`; dataset `data/transformer_v4_wl200_clean.parquet`; training seed = the recipe's seed44 (single seed, documented) |
| grid (all 43 cutoffs, 21-day cadence) | 2023-10-02,2023-10-23,2023-11-13,2023-12-04,2023-12-25,2024-01-15,2024-02-05,2024-02-26,2024-03-18,2024-04-08,2024-04-29,2024-05-20,2024-06-10,2024-07-01,2024-07-22,2024-08-12,2024-09-02,2024-09-23,2024-10-14,2024-11-04,2024-11-25,2024-12-16,2025-01-06,2025-01-27,2025-02-17,2025-03-10,2025-03-31,2025-04-21,2025-05-12,2025-06-02,2025-06-23,2025-07-14,2025-08-04,2025-08-25,2025-09-15,2025-10-06,2025-10-27,2025-11-17,2025-12-08,2025-12-29,2026-01-19,2026-02-09,2026-03-02 |
| run namespace | `--run-id wf-pt-b4e47e2c-batch1` — ONE namespace for both phases (the #81 resume + #82 budget_contract bind to it) |
| PHASE 1 (exactly the 3 newest folds) | `python -u -m renquant_backtesting.wf_gate.modal.executor --select-cutoffs 2026-03-02,2026-02-09,2026-01-19 --run-id wf-pt-b4e47e2c-batch1 --gpu T4 --execute --skip-calibrators --timeout-seconds 2900 --max-total-usd 25 --rate-usd-per-hour 0.59 --pre-spend-usd 1.45 --overhead-frac 0.15 --repo-root <scratch-assembly>/repo-root` |
| PHASE 2 (the remaining 40, resume) | same command with `--select-cutoffs 2023-10-02,2023-10-23,2023-11-13,2023-12-04,2023-12-25,2024-01-15,2024-02-05,2024-02-26,2024-03-18,2024-04-08,2024-04-29,2024-05-20,2024-06-10,2024-07-01,2024-07-22,2024-08-12,2024-09-02,2024-09-23,2024-10-14,2024-11-04,2024-11-25,2024-12-16,2025-01-06,2025-01-27,2025-02-17,2025-03-10,2025-03-31,2025-04-21,2025-05-12,2025-06-02,2025-06-23,2025-07-14,2025-08-04,2025-08-25,2025-09-15,2025-10-06,2025-10-27,2025-11-17,2025-12-08,2025-12-29,2026-01-19,2026-02-09,2026-03-02` — #81's resume partitions to the 40 absent folds (zero retrain/overwrite, fail-closed on missing/mismatched provenance, one auditable manifest with per-dispatch history) |
| THE control (supersedes every earlier tripwire/projection description) | bt#82's EXECUTE-TIME gate is the sole budget control: before any Modal import it computes the HARD worst-case projection and refuses (exit 4) over-cap; the five-field `budget_contract` {25, 0.59, 1.45, 0.15, 2900} freezes at the first capped dispatch/refusal and any drift on this run-id refuses pre-import. `--print-cost-projection` and `--dispatch-note` are OPTIONAL diagnostics only — they control nothing |
| frozen worst-case arithmetic (hard timeout bound, 2900 s provider ceiling per fold) | usd/s = 0.59/3600 × 1.15. PHASE 1: 1.45 + 3 × 2900 × usd/s ≈ **$3.09 ≤ $25 → GO**. PHASE 2 (3 measured pods ≈ 2384 s each): 1.45 + 3×2384×usd/s (≈$1.35 measured) + 40×2900×usd/s (≈$21.85 bound) ≈ **$24.65 ≤ $25 → GO**. A fold reaching 2900 s is provider-killed → `failed_folds ≠ []` → halt + amendment (no partial salvage) |
| expected terminal signature | exit 1 WITH `failed_folds: []` and `quarantine_reasons: ["skip_calibrators_diagnostic"]` — the #76 gate quarantines train-only corpora as non-promotable; that exit-1 signature IS success for this batch |
| calibrator leg (LOCAL, $0) | after all 43 folds land: `fit_calibrator --method platt --batch-size 512` per fold on THIS machine, ≤8-way parallel, recipe raw-label panel; manifest via the reviewed `write_manifest` (leakage invariant enforced) |
| outputs | quarantined run namespace `artifacts/walkforward_patchtst_runs/wf-pt-b4e47e2c-batch1/` in the SCRATCH assembly only — never the umbrella, never a committed corpus; TOTAL report (every pod's outcome; per-pod elapsed/checksums; manifest + provenance digests) |

## 2. Durable smoke artifact index

Retained at `/Users/renhao/renquant_bundles/g4-modal-smoke-20260727/`:
- `logs/staged1-t4-run2.log`, `logs/pod-run2-full.log`, `logs/smoke-trainonly-t4.log`
- `walkforward_patchtst_runs/wf-pt-b4e47e2c-20260727T195313Z/` — manifest + provenance sidecar (`pod_facts`: worker ta-01KYJJ79V42GFH5K8PB40P2TMR, image im-7gxA3w8FvDM67fSDfov31i, `elapsed_seconds 2384.4075977802277`, device cuda, result_checksum sha256:8a926df3bb9e4a66; `failed_folds: []`; `quarantine_reasons: ["skip_calibrators_diagnostic"]`, `promotion_ready: false`) + fold artifact `2026-03-02/hf_patchtst_all_seed44_model.pt` + `.metadata.json` (effective_train_cutoff 2025-12-05)

## 3. Pre-freeze smoke (house §0 rule, satisfied)

2026-07-27 19:53Z, the frozen train-only invocation with `--staged 1`,
code at `9942bce6` (a strict ancestor of the frozen `2fcec872`; the
delta is #81+#82 — the dispatch/budget machinery itself, smoke-covered by
their own merged test suites): fold 2026-03-02 completed 1/1,
2384.41 s on cuda, AC7 freshness PASS (panel max 2026-04-28 ≥ required
2025-12-08), exact diagnostic-quarantine terminal signature. Cost history:
probe ≈ $1.00 + smoke ≈ $0.45 = the frozen `--pre-spend-usd 1.45`.

## 4. Non-goals / honesty

Corpus generation only: no sims, no converter, no Phase-A evaluation, no
disposition. This batch alone does NOT satisfy Phase 0's dual-expert
evidence-volume prerequisite. Total reporting: a fully-failed batch is a
reported result. Any `failed_folds ≠ []`, cover failure, or budget-gate
refusal ⇒ halt + amendment prereg (no partial salvage, no cap weakening).
