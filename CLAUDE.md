# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

One repo for all RenQuant model families, merging the former `renquant-model-gbdt`
and `renquant-model-patchtst` repos (RFC §"Backfill Plan" P3). Three packages under `src/`:

- `renquant_model_gbdt/` — GBDT panel-LTR family (**production**).
- `renquant_model_patchtst/` — PatchTST / sequence family (**candidate**, in research).
- `renquant_model_common/` — cross-family scaffolding (lifted utilities; currently
  `calibrator_quality`, `triple_barrier`, `acceptance_entry_ic`, `challenger`).

These are three **top-level** packages, not a nested `renquant_model.{gbdt,patchtst}`
namespace. That was deliberate (preserves working Scorer entry points / consumer
wiring from earlier phases) — do not deep-rename without reading the README note.

## Commands

The Makefile sets `PYTHONPATH` to the three sibling dependency repos and selects the
RenQuant conda venv (`../RenQuant/.venv/bin/python`) when present — that env has
`xgboost` and `torch` installed. Prefer the Makefile targets so the environment is right.

```bash
make test        # python -m pytest -q  (with sibling pins on PYTHONPATH)
make doctor      # import smoke: imports PanelGbdtTrainingPipeline + renquant_common
```

Running pytest directly also works because `pyproject.toml`'s `[tool.pytest.ini_options]`
pins `pythonpath` to `src` + the three sibling `../*/src` dirs — but you must use a
Python that has the model backends installed:

```bash
python -m pytest tests/gbdt -q                                      # one family
python -m pytest tests/gbdt/test_pipeline.py::test_job_respects_skip_cv -q   # one test
```

Install (per-family extras keep installs slim):

```bash
pip install -e .[gbdt]       # XGBoost backend
pip install -e .[patchtst]   # torch + transformers backend
```

PatchTST CLIs (need the sibling pins on `PYTHONPATH` — run via the Makefile env or set
it manually; they also need `data/` present):

```bash
python -m renquant_model_patchtst.hf_trainer --cut cut1_covid --epochs 8 --device mps   # the real trainer
python -m renquant_model_patchtst.research --phase 0 --epochs 4 --device mps            # research harness
```

## Architecture

Everything is built on `renquant_common`'s **Task / Job / Pipeline** primitives:
a `Task.run(ctx)` mutates a shared dataclass *context*; a `Job` is an ordered list of
Tasks (`tasks` property); a `Pipeline` runs Jobs and returns a `PipelineResult`. Training
is modeled as explicit Tasks with declared outputs on the context, not scattered side effects.

### Two pipeline flavors per family (important, and confusingly named)

Each family has a `pipeline.py` *and* a `pipelines.py` — they differ by one letter and
do very different things:

- **`pipelines.py` (plural) = generic DI shell.** `PanelGbdtTrainingPipeline` /
  `PatchTstTrainingPipeline` take injected `loader` / `trainer` / `validator` callables.
  This is the surface **renquant-orchestrator's DailyRunPipeline** consumes — it injects
  its own implementations. These files validate data + artifact manifests via
  `renquant_base_data` / `renquant_artifacts` contracts.
- **GBDT `pipeline.py` (singular) = the byte-identical production engine.**
  `ModelTrainingJob` (`WalkForwardCVTask` → `TrainBoosterTask` → `BuildArtifactTask`)
  threaded through `GbdtTrainingContext`. This reproduces the umbrella's
  `scripts/train_production_model.py` model-side math.
- **GBDT `panel_data.py` = self-contained data-side + end-to-end assembly.**
  `build_training_pipeline()` stitches `DataPrepJob` → `ModelTrainingJob` →
  `ArtifactContractJob` so the repo can train the panel-LTR model on its own from a
  `data_dir`, with no umbrella / `kernel.*` code.

PatchTST equivalents: `hf_trainer.py` is the **real trainer** (`train_one`,
`build_parser`); `training.py` is the **adapter** that wires `hf_trainer` into the DI
shell (`build_training_pipeline()`); `research.py` is the **research harness** (see below).

### Byte-identity contract (GBDT)

`panel_trainer.py` must reproduce the umbrella production booster **byte-for-byte**
(only `train_run_id` and `trained_date` are allowed to differ). The contract: `float64`
features, label `clip(-5, 5)`, the caller's params dict used **verbatim** (no implicit
default merge), `np.argsort` date ordering, per-date `np.unique` group sizes for
`rank:pairwise`. `tests/gbdt/test_panel_trainer_parity.py` guards this against an inline
golden — do **not** reintroduce a float32 cast or a `DEFAULT_PARAMS` merge.

## Boundaries (the rules to not break)

1. **Dependency direction.** This repo depends only on `renquant-common`,
   `renquant-base-data`, `renquant-artifacts`. It must **not** import `renquant-pipeline`,
   `renquant-execution`, or `renquant-backtesting` (nor `kernel.*`, `alpaca`, `ib_insync`,
   `live`).
2. **Families must not import each other.** `renquant_model_gbdt` and
   `renquant_model_patchtst` share code only through `renquant_model_common` /
   `renquant_common`. Enforced by `tests/*/test_import_boundaries.py` (an AST source scan
   **and** a fresh-subprocess runtime import check — the subprocess avoids pollution from
   other tests in the session).
3. **Consumers never import this package directly** — they resolve models through
   `renquant_common.load_scorer` against the `renquant_common.scorers` entry-point group
   declared in `pyproject.toml`.

> **Known gap:** `pyproject.toml` declares the entry point
> `panel_ltr_xgboost = "renquant_model_gbdt.scorer:load"`, but `scorer.py` does **not
> exist yet** (the runtime scorer code is still being ported in slices). The PatchTST
> scorer is likewise unregistered. `make doctor` only checks the training-pipeline import,
> so it passes despite this. Don't assume the scorer module is present.

## Porting work (lifting from the umbrella)

Code arrives in reviewed slices from the `RenQuant` umbrella (see `docs/source-map.md`).
Each slice must carry: a named Task/Job owner, a fixture or synthetic unit test, an
import-boundary check, a model-ledger output contract, no dependency on live/broker code,
and — for sequence models — declared-label/raw-ER/placebo-shuffle sanity before any IC is
reported. Don't copy whole folders or `_hf_trainer/` checkpoints blindly.

## Data

`data/` is a **gitignored symlink** to `../RenQuant/data` (the umbrella's canonical data
store — too large for git). GBDT reads `alpha158_291_fundamental_dataset.parquet`,
`alpha158_qlib_dataset.stats.json`, `sec_fundamentals_daily.parquet`; PatchTST reads
`transformer_v4_wl200_clean.parquet` + `ohlcv/SPY/`. On a fresh machine, repoint the
symlink (or pass `--strategy-dir` / `--dataset` to the CLIs).

## PatchTST research harness

`renquant_model_patchtst.research` drives `hf_trainer` across walk-forward cuts to raise
PatchTST's **pooled per-date Spearman IC** above the XGB baseline (+0.017). Full spec lives
in the module docstring and `docs/patchtst_research_plan.md`. Two things to respect:
the trainer's own selection metric (`eval_min_regime_ic`, a pessimistic min across regimes)
is **not** the judging metric — score on pooled IC from each run's `*_val_preds.parquet`;
and some levers need small trainer additions first (e.g. `E_drop_senti` needs
`--exclude-features`, the Phase-2 placebo needs `--shuffle-labels`) that are not yet built.
