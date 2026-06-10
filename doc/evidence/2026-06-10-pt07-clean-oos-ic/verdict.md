# P0 verdict — pt07 placebo-clean OOS IC artifact (IC→Sharpe RFC §7.1)

**Date:** 2026-06-10 · **Author:** Claude · **Status:** §5.2 eval battery **PASS**
**Candidate:** `pt07 strict_trainfit_embargo60 seed_44` — the live production
primary (`hf_patchtst`, promoted 2026-06-05, per `strategy_config.json`).
**Consumer:** E1 transfer-coefficient decomposition (renquant-pipeline), per
`renquant-orchestrator/doc/research/2026-06-10-ic-to-pnl-architecture.md` §5.5 / §7.1.

## Headline

| Metric | Value |
|---|---|
| **Mean placebo-clean OOS cross-sectional IC** | **+0.0724** |
| Median daily IC | +0.0940 |
| Daily IC std | 0.1556 |
| % dates positive | 68.7% |
| Eval window (split-pure OOS) | 2025-03-13 → 2026-02-10, 230 dates, 32,660 (date,ticker) rows |
| Shuffled-label IC | +0.0014 (pass: \|·\| < 0.005) |
| Timeshift placebo @ 2×horizon = 120d | −0.0192 (pass: \|·\| < 0.0927 = 0.5×\|aligned_real +0.1854\|) |

**The operator premise "PatchTST IC ≈ 0.1" is NOT confirmed at face value; the
honest clean number is ≈ 0.07** (median 0.09). Per RFC §7.1, the A0 ceiling and
all E1 math must be computed on **+0.0724**, not 0.10 and not the in-sample
calibrator `pool_ic=0.13`.

## Artifact (what E1 consumes)

- Per-date IC series (committed): `doc/evidence/2026-06-10-pt07-clean-oos-ic/oos_ic_daily.csv`
  — columns `date, ic, n_names`; sha256 `1f0f522d36dd96ca0bc4b2136a1b2aae3849aa323daad21525fc08d0b29d23a7`.
- Run manifest (committed): `doc/evidence/2026-06-10-pt07-clean-oos-ic/manifest.json`
  — checkpoint sha256 `0704696…`, panel sha256 `7ae2a8b…`, full battery results, command.
- Raw audit trail (workstation-local, gitignored):
  `artifacts/diagnostics/oos_ic/hf_patchtst_all_seed44_model_20260610T165959Z/`
  incl. `predictions.parquet` (per-(date,ticker) scores;
  sha256 `d74fc52d1bf91101edcfd09ecc362300b31448c43bd9045366e0145024813109`).

Reproduce (repo root, umbrella venv):

```bash
PYTHONPATH=../renquant-common/src:../renquant-base-data/src:../renquant-artifacts/src:src \
../RenQuant/.venv/bin/python -m renquant_model_patchtst.oos_ic_export \
  --checkpoint ../RenQuant/artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt
```

Wall time ≈ 1.5 min (CPU). Exit code 0 = battery PASS, 1 = FAIL, 2 = contract error.

## Why this number is trustworthy (and the 2026-06-02 audit numbers were not)

1. **Right dataset, native scorer.** Scores the checkpoint on its OWN training
   panel (`data/transformer_v4_wl200_clean.parquet`, from
   `training_contract.dataset`) through the native `load_panel_with_split` +
   `PerDayDataset` forward pass — the path that reproduces training-time
   held-out predictions. Cross-check vs `hf_patchtst_all_seed44_val_preds.parquet`:
   per-date IC correlation **0.99999997** on all 230 common dates (means
   +0.072415 vs +0.072413). This avoids both root causes of the 2026-06-09
   WF-gate false negative (`doc/2026-06-09-patchtst-wf-gate-eval-bug.md`).
2. **Split-pure windows.** Uses the post-`c5d15dc` `PerDayDataset`: 3,408 val
   lookback windows crossing the embargo boundary are skipped (closes the
   2026-06-02 sequence-boundary purity follow-up). That is why the export
   starts 2025-03-13, not 2025-02-06, and why mean IC (+0.0724) differs
   slightly from the raw full-val figure (+0.0706).
3. **OOS contract, fail closed.** `val_start 2025-02-06 > effective_train_cutoff
   2024-11-13 + 60 business days (2025-02-05)`; split counts reproduce the
   training contract exactly (train 302,144 / val 36,068 / embargo 7,810).
4. **Placebo decay shape is the leak-free signature.** Shifted-label IC decays
   monotonically with shift: +0.072 @5d → +0.034 @40d → +0.015 @60d →
   +0.008 @80d → **−0.019 @120d** → −0.023 @180d. Overlapping-60d-label
   persistence dies by ≈ the horizon; there is no future-information bump.
   Contrast B_tuned (2026-06-02 audit): timeshift placebo **+0.067 > real
   +0.044** — the textbook leak fingerprint. pt07 is a different artifact
   (strict trainfit, embargo 60, different recipe) and shows the opposite,
   healthy profile.

## Caveats (honest limits of this artifact)

- **This is one fixed holdout window (2025-03→2026-02), one regime mix.** It is
  not a walk-forward point-in-time IC; the WF-gate manifest evaluation for
  PatchTST is still broken (doc 2026-06-09 Fix A/B pending in
  renquant-backtesting). E1 may proceed on this artifact per RFC §5.5, but
  promotion decisions still require the WF gate once fixed.
- **IC is non-stationary within the window:** aligned-real IC on the early
  placebo-alignable subset (110 dates ending ~2025-08) is +0.185 vs +0.072
  full-window — the signal weakened in late 2025/early 2026. E1 should use the
  per-date series, not the scalar mean.
- The §5.2 *regime-level* sanity layer (per-regime min-IC + per-regime placebo,
  as enforced by the WF gate) is out of scope here; the battery implemented is
  the pooled shuffled-label + timeshift placebo pair named by RFC §5.2/§7.1.
- The shuffled-label check here is the **eval-time** form (placebo on a fixed
  model). The *retrain*-grade placebos (train on shuffled/shifted labels) live
  in `research_pipeline` Tier-3 and were not re-run for this export.

Agent-Origin: Claude
