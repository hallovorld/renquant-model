# PatchTST Research Pipeline Design

## Purpose

Replace the current `renquant_model_patchtst.research` loop script with a strict, auditable experiment pipeline. The new design must let us define a scientific test matrix once, then execute it linearly or concurrently based on available resources, persist every condition/result, and produce analysis that is strong enough to decide whether a PatchTST variant deserves deeper confirmation.

This document is a design proposal only. Implementation should preserve the existing CLI behavior until the new pipeline is fully covered by tests.

## Goals

- Express research orchestration as `Task / Job / Pipeline` using `renquant_common`.
- Treat each `(config, cut, seed)` as an independent trial with explicit provenance.
- Use `renquant_common.run_parallel` for safe concurrent trial execution.
- Support deterministic linear runs and resource-aware parallel runs.
- Make experiments resumable without silently changing the trial matrix.
- Persist enough metadata to reproduce, compare, and audit every result.
- Generate statistical analysis, not just a sorted table of IC values.

## Non-Goals

- Do not change `hf_trainer.train_single_run` semantics in this refactor.
- Do not import downstream repos such as `renquant_pipeline`, `renquant_backtesting`, or execution code.
- Do not promote a model automatically. The pipeline may emit a recommendation, but promotion stays manual.

## Cross-Repo Boundaries

The research pipeline lives in `renquant-model` because it is model-development
orchestration. It may use these upstream repos directly:

- `renquant-common`: `Task`, `Job`, `Pipeline`, `run_parallel`, scorer contracts,
  training-ledger helpers, walk-forward split helpers, and shared validation logic.
- `renquant-base-data`: dataset/data-manifest validation when available.
- `renquant-artifacts`: artifact and model-evidence contract validation.

It must not import downstream runtime repos:

- `renquant-pipeline`
- `renquant-backtesting`
- `renquant-execution`
- `kernel.*`, broker, or live modules

Cross-repo collaboration should happen through explicit contracts instead:

- Data comes from filesystem paths or manifests owned by this model workflow:
  `--data-dir`, `--dataset`, `--spy-path`, and optional dataset manifests.
  The pipeline must not infer paths from another monorepo checkout.
- Strategy/config provenance comes from an explicit `--strategy-config` file or
  a config snapshot supplied in the experiment spec. Do not `chdir` into another
  repo or import strategy modules to discover config.
- Model artifacts are exposed through `renquant_common.scorers` entry points and
  `ArtifactManifest` fields, not direct downstream imports.
- Training runs are recorded through the shared training ledger API in
  `renquant-common`, with `repo_dir`, `git_head`, dataset fingerprint, and config
  fingerprint stamped.
- Backtesting or execution follow-up should consume persisted JSON/Parquet outputs
  from the experiment directory; this pipeline should not call those repos in-process.

This keeps the dependency direction:

```text
renquant-common / base-data / artifacts
        -> renquant-model
        -> persisted artifacts, manifests, reports
        -> downstream pipeline / backtesting / execution consumers
```

If an implementation needs a downstream-only metric, write the trial outputs first
and let a downstream repo run a separate analysis job against those files.

## Top-Level Pipeline

```text
ExperimentPipeline
  BootstrapJob
    ResolvePathsTask
    StampEnvironmentTask
    ValidateTrainerSurfaceTask
  PlanExperimentJob
    ExpandTrialMatrixTask
    FingerprintTrialsTask
    ResolveResumeStateTask
  DispatchTrialsJob
    BuildExecutionPlanTask
    RunTrialsTask
  AggregateResultsJob
    LoadTrialResultsTask
    AggregateByConfigTask
    AggregateByCutAndSeedTask
  AnalyzeResultsJob
    CompareAgainstBaselineTask
    PlaceboCleanlinessTask
    RobustnessAndRiskTask
  PersistResultsJob
    WriteJsonArtifactsTask
    WriteMarkdownReportTask
```

`ExperimentPipeline` owns orchestration only. Single-run model training remains delegated to `hf_trainer.train_single_run`, which already routes through `sequence_training.build_sequence_training_pipeline()`.

## Core Context Objects

`ExperimentSpec` captures requested work:

```python
@dataclass
class ExperimentSpec:
    phase: int
    configs: list[str]
    cuts: list[str]
    seeds: list[int]
    epochs: int
    dataset: Path
    spy_path: Path
    data_dir: Path
    strategy_config: Path | None
    out_dir: Path
    device: Literal["auto", "cpu", "mps", "cuda"]
    scheduler: Literal["auto", "linear", "parallel"]
    max_workers: int | None = None
    resume: bool = True
    fail_fast: bool = False
    require_placebos: bool = True
```

`TrialSpec` is one atomic experiment:

```python
@dataclass
class TrialSpec:
    trial_id: str
    config_name: str
    cut: str
    seed: int
    argv: list[str]
    out_dir: Path
    val_preds_path: Path
    summary_path: Path
    fingerprint: str
```

`TrialResult` is append-only evidence:

```python
@dataclass
class TrialResult:
    trial_id: str
    status: Literal["ok", "skipped", "failed"]
    pooled_ic: float | None
    daily_ic_std: float | None
    positive_day_ratio: float | None
    min_regime_ic: float | None
    per_regime_ic: dict[str, float]
    elapsed_sec: float | None
    device: str
    git_head: str | None
    error: str | None
    artifacts: dict[str, str]
```

## Resource-Aware Execution

`BuildExecutionPlanTask` should produce an `ExecutionPlan`:

```python
@dataclass
class ExecutionPlan:
    mode: Literal["linear", "parallel"]
    max_workers: int
    device: str
    reason: str
```

Default rules:

- `scheduler=linear`: always run trials sequentially.
- `scheduler=parallel`: use `max_workers`, capped by trial count.
- `scheduler=auto`:
  - `device=mps`: default linear. Apple MPS jobs compete for one GPU memory pool.
  - `device=cuda`: parallel only when multiple CUDA devices are visible; otherwise linear.
  - `device=cpu`: parallel with `min(cpu_count - 2, n_trials)`.
  - Phase 0 range-finding may parallelize aggressively.
  - Phase 2 confirmation should prefer linear or low concurrency for reproducibility.

`RunTrialsTask` should call:

```python
run_parallel(trial_contexts, TrialJob(), max_workers=plan.max_workers)
```

when `plan.mode == "parallel"`. In linear mode it should call `TrialJob().run(ctx)` for each trial in stable sorted order.

## Trial Job

Each trial has a small pipeline:

```text
TrialJob
  PrepareTrialTask
  RunTrainerTask
  LoadValidationPredictionsTask
  ComputeTrialMetricsTask
  PersistTrialResultTask
```

`RunTrainerTask` builds CLI args from `TrialSpec.argv` and calls `hf_trainer.train_single_run`. If `resume=True` and both `summary_path` and `val_preds_path` exist with matching trial fingerprint, it should skip training and load existing evidence.

Failures must write a `TrialResult(status="failed")` row with the exception class, short message, and elapsed time. A failed trial should not erase prior results.

## Metrics

Minimum metrics per trial:

- pooled per-date Spearman IC
- daily IC mean, standard deviation, and standard error
- positive daily IC ratio
- per-regime IC and `min_regime_ic`
- number of validation dates and rows
- label distribution summary
- elapsed seconds and device

Aggregate metrics per config:

- mean pooled IC across cuts/seeds
- standard error across cuts/seeds
- positive cut count
- worst-cut IC
- mean delta vs `B_tuned`
- placebo-adjusted IC when placebo trials exist
- failed/skipped trial count

## Scientific Gates

The report should separate exploration from confirmation:

- Phase 0 range-find: a lever advances only if mean pooled IC beats `B_tuned` by at least one standard error and positive-cut count is not worse.
- Phase 1 DOE: keep all tested points, fit/report sensitivity, and never hide failed or losing configs.
- Phase 2 confirm: require multiple seeds, all walk-forward cuts, placebo runs, and DSR/PBO-ready vectors before any promotion recommendation.

Recommended verdict values:

```text
promote_to_confirm
needs_more_seeds
reject
invalid_experiment
```

## Persistence Layout

Every experiment writes a self-contained directory:

```text
artifacts/patchtst_research/<experiment_id>/
  experiment_spec.json
  environment.json
  trial_plan.json
  trial_results.jsonl
  aggregate_results.json
  analysis.json
  report.md
```

`experiment_id` should include UTC timestamp, phase, git short SHA, and a short hash of the trial matrix.

## Resume Rules

Resume must be conservative:

- Existing trial outputs are reused only when the stored fingerprint matches the planned `TrialSpec`.
- Partial files do not count as completed trials.
- A changed config, seed, cut, dataset path/schema, or git head creates a new fingerprint.
- `--no-resume` forces recomputation.

## CLI Shape

Preserve existing flags and add explicit execution controls:

```bash
python -m renquant_model_patchtst.research \
  --phase 0 \
  --configs B_tuned,C_xstock \
  --cuts cut1_covid,cut2_fed \
  --seeds 42 \
  --epochs 4 \
  --data-dir data \
  --dataset data/transformer_v4_wl200_clean.parquet \
  --spy-path data/ohlcv/SPY/1d.parquet \
  --strategy-config config/model_research.json \
  --device mps \
  --scheduler auto \
  --max-workers 1 \
  --out-dir artifacts/patchtst_research
```

## Test Plan

Add focused unit tests for:

- trial matrix expansion and stable trial IDs
- fingerprint changes when config/data/git inputs change
- resume accepts matching fingerprints and rejects mismatches
- scheduler decisions for `cpu`, `mps`, `cuda`, `linear`, and `parallel`
- aggregate math on synthetic trial results
- report generation with failed, skipped, placebo, and successful trials
- `RunTrialsTask` dispatches to `run_parallel` only when plan mode is `parallel`

## Implementation Sequence

1. Add dataclasses, planning tasks, and aggregate/report tasks behind tests.
2. Keep current `run_one` behavior as a compatibility adapter.
3. Introduce `TrialJob` with mocked trainer tests.
4. Wire `run_parallel` dispatch.
5. Switch CLI `main()` to build and run `ExperimentPipeline`.
6. Remove obsolete ad hoc loop code after parity tests pass.
