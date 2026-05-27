# Source Map From Monorepo

This repo merges the former `renquant-model-gbdt` and
`renquant-model-patchtst` repos (RFC §"Backfill Plan" P3). Both histories
are preserved via `git filter-repo` subtree merges.

Initial source commit: `8f3e08d8d1ae1e402a78f4815efb59e3c7c66aa8`.

## GBDT family (`src/renquant_model_gbdt/`)

Production GBDT code ported in reviewed slices from:

- `backtesting/renquant_104/training_panel/`
- `scripts/train_104.py`
- `scripts/train_panel*.py`
- `scripts/eval_xgb_*.py`
- GBDT-specific calibrator scripts
- GBDT scorer runtime code currently mixed into
  `backtesting/renquant_104/kernel/panel_pipeline/`

## PatchTST family (`src/renquant_model_patchtst/`)

PatchTST/PatchTXT code ported in reviewed slices from:

- `scripts/patchtst_hf.py`
- `scripts/fit_hf_patchtst_calibrator.py`
- `scripts/eval_hf_*.py`
- `scripts/eval_dlinear_*.py`
- PatchTST-specific scorer/runtime code currently mixed into
  `backtesting/renquant_104/kernel/panel_pipeline/`
- PatchTST diagnostics under `artifacts/patchtst_*` (manifest-only)

## Porting contract (both families)

Do not copy full folders or `_hf_trainer/` checkpoints blindly. Each slice
needs:

1. a named pipeline Task/Job owner,
2. a fixture or synthetic unit test,
3. an import-boundary check,
4. a model-ledger output contract,
5. no dependency on live execution or broker code,
6. (sequence models) declared-label sanity, raw-ER sanity, placebo/shuffle
   checks before reporting IC.
