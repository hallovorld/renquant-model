# PatchTST Improvement — Research Plan & Runbook

**Designed 2026-05-28. Execution assigned to other agents.**
Driver: `renquant_model_patchtst.research` (full spec in its module docstring).
Lives with the model because improving PatchTST is model-development, not orchestration.

## Goal
Raise PatchTST's walk-forward **pooled** cross-sectional IC above the XGB baseline
(**+0.017 ± 0.056**, 3/5 cuts, placebo-clean) so it becomes a viable *single-model*
alternative. **No ensemble** (user mandate 2026-05-28).

## Established facts — do NOT re-discover
- Untuned default config is unstable: min-regime IC **+0.021 ± 0.124** (2/5 cuts).
- DOE-tuned (**lr 1e-4, wd 0.3, seq 24**) fixes most of the variance: partial run
  cut1 +0.106 / cut2 −0.032 / cut3 +0.038 vs default +0.091 / −0.128 / −0.046.
  `wd=0.3` (300× the default) is the key regularizer.
- **Metric**: trainer selects on `eval_min_regime_ic` = *min* across regimes
  (pessimistic, noisy on sparse BEAR/CHOPPY days). Judge on the **pooled per-date
  Spearman IC** from each run's `*_val_preds.parquet` — the only metric comparable to
  XGB's +0.017. (Candidate fix: switch `metric_for_best_model` to a pooled IC.)
- **Runtime ≈ 40 min/cut** (8 epochs, full panel). Cuts independent → parallelize.
  Runs **resumable** (existing `val_preds.parquet` ⇒ skipped).

## Levers (each grounded in code/literature)
| id | change | rationale |
|---|---|---|
| `B_tuned` | lr1e-4 wd0.3 seq24 | regularization — the baseline to beat |
| `C_xstock` | `--cross-stock-attn` | iTransformer cross-stock attention (Liu 2024, arXiv 2310.06625) — fixes PatchTST channel-independence, the #1 cross-sectional failure mode |
| `D_film` | `--film-regime-cond` | FiLM regime conditioning (Perez 2017) — PRIME DIRECTIVE |
| `E_drop_senti` | drop 3 sentiment feats | XGB: sentiment DILUTES (clean IC −0.005→+0.011). **Prereq: add `--exclude-features` to hf_trainer**; harness skips until then |
| `F_fwd20d` | `--label fwd_20d_excess` | XGB: 20d ≥ 60d horizon |

## Staged protocol (CLAUDE.md §5.11 / §5.14 / §5.13.4a)
1. **Phase 0 — range-find**: `B_tuned` + each single lever, 5 cuts × 1 seed, `--epochs 4`.
   Lever *helps* if pooled-IC mean exceeds `B_tuned` by ≥ 1 SE **and** positive-cut ≥ B.
   `python -m renquant_model_patchtst.research --phase 0 --epochs 4`
2. **Phase 1 — DOE** (if a lever helps): Box-Behnken (`pyDOE2.bbdesign`) over
   {lr, wd, seq_len, nll_loss_weight}; fit quadratic surface; pick optimum.
3. **Phase 2 — confirm**: best config × 5 seeds (§5.13.4) + **placebo battery**
   (label-shuffle + time-shift, §5.2) + DSR/PBO (§5.14.4). `--phase 2 --epochs 8 --seeds 42,43,44,45,46`

## Promotion gate (PatchTST → primary scorer)
Pooled IC > XGB **+0.017** placebo-clean **AND** survives both placebos (≈0) **AND**
DSR > 0.5. Anything less = research note only.

## Prerequisites the runner must add first (small renquant_model_patchtst changes)
- `--exclude-features` on `hf_trainer` (for `E_drop_senti`) — mirror GBDT `exclude_features`.
- `--shuffle-labels` (Phase-2 placebo): permute label within each date in TRAIN only.
- Time-shift placebo: train on label shifted +horizon.

## Cost / parallelization
Full Phase 0 (5 levers × 5 cuts × 1 seed × ~20 min @4ep) ≈ 8 GPU-hours; parallelize
across cuts/configs. Phase 2 (5 seeds × 8ep) is the expensive part — only on the winner.

## Env to run
Sibling pins on path (renquant-common/base-data/artifacts/model) — the `Makefile`
PYTHONPATH covers them — plus the umbrella data dir (`--strategy-dir`, default
`../RenQuant/backtesting/renquant_104`) which hosts the transformer dataset + SPY +
the data-side `kernel.*` deps resolved via `RENQUANT_STRATEGY_DIR`.
