# Repository Guidelines

## Project Structure & Module Organization

This is a Python `src/` layout with three top-level packages:

- `src/renquant_model_gbdt/`: production GBDT panel-LTR model family.
- `src/renquant_model_patchtst/`: PatchTST / sequence model family.
- `src/renquant_model_common/`: shared model-family utilities only.

Tests mirror the families under `tests/gbdt/`, `tests/patchtst/`, plus root-level shared tests. `docs/` holds design and training notes, `scripts/` holds maintenance utilities, and `data` is a gitignored symlink to `../RenQuant/data`.

## Build, Test, and Development Commands

- `pip install -e .[gbdt]`: install the package with XGBoost and parquet support.
- `pip install -e .[patchtst]`: install with torch and transformers support.
- `make test`: run the full pytest suite with sibling RenQuant repos on `PYTHONPATH`.
- `make doctor`: smoke-test imports for both model families and `renquant_common`.
- `python -m pytest tests/gbdt -q`: run one family’s tests.
- `python -m pytest tests/gbdt/test_pipeline.py::test_job_respects_skip_cv -q`: run one focused test.

CI uses Python 3.10 and runs `make test`.

## Coding Style & Naming Conventions

Use Python 3.10+ with type hints for public interfaces and keep `py.typed` packages typed. Follow the existing Task / Job / Pipeline style: explicit dataclass contexts, named task outputs, and small family-specific modules. Keep package names as `renquant_model_gbdt` and `renquant_model_patchtst`; do not deep-rename to a nested namespace.

No formatter or type checker is enforced. Ruff has been used ad hoc with defaults, so preserve existing `# noqa` annotations and run `../RenQuant/.venv/bin/ruff check src tests` when available.

## Testing Guidelines

Tests use `pytest` with `--import-mode=importlib`. Add focused synthetic or fixture-based tests next to the relevant family. Preserve import-boundary tests: GBDT and PatchTST must not import each other, and this repo must not import downstream execution, pipeline, broker, or backtesting packages.

## Commit & Pull Request Guidelines

Recent history uses short imperative subjects, sometimes with Conventional Commit-style prefixes such as `feat(patchtst):`, `refactor(D6):`, and `doc:`. Keep commits scoped and mention the family or milestone when useful.

PRs should include a concise behavior summary, tests run, linked issue or milestone when applicable, and model/training metric notes for training changes. Include screenshots only for documentation or report rendering changes.

## Security & Configuration Tips

Keep large datasets, model artifacts, credentials, and local database files out of git. Use the `data` symlink or explicit CLI paths for local training data.
