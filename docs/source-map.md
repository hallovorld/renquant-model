# Source Map From Monorepo

Initial source commit:
`8f3e08d8d1ae1e402a78f4815efb59e3c7c66aa8`.

PatchTST/PatchTXT code should be ported in reviewed slices from:

- `scripts/patchtst_hf.py`
- `scripts/fit_hf_patchtst_calibrator.py`
- `scripts/eval_hf_*.py`
- `scripts/eval_dlinear_*.py`
- PatchTST-specific scorer/runtime code currently mixed into
  `backtesting/renquant_104/kernel/panel_pipeline/`
- PatchTST diagnostics currently under `artifacts/patchtst_*` after they are
  classified and represented by manifests

Do not copy `_hf_trainer/` checkpoint directories or ad hoc artifact dumps into
normal Git. Each ported slice needs declared-label sanity, raw-ER sanity, and
placebo/shuffle checks before reporting IC.
