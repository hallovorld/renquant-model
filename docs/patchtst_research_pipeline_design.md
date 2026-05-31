# PatchTST Research Pipeline Design

## Purpose

Replace `renquant_model_patchtst.research` with a strict, auditable
`ExperimentPipeline`. A user defines the scientific test matrix once; the
pipeline then schedules linear or concurrent execution from live resource
constraints, records every condition and result, blocks invalid experiments, and
emits analysis strong enough to decide whether a PatchTST variant deserves
confirmation.

This is a design proposal only. Implementation must keep the existing CLI
behavior until the new pipeline is covered by tests and parity checks.

## Research Basis

- PatchTST itself uses patch tokens and channel independence; the research
  harness should therefore track sequence length, patch length, channel-mixing
  variants, and resource usage as first-class experimental conditions. See Nie
  et al., 2023, "A Time Series is Worth 64 Words."
- Purged and embargoed validation is mandatory for overlapping financial labels.
  Use the shared `renquant_common.PurgedKFold` / `CombinatorialPurgedCV` and
  `renquant_common.walk_forward_splits`, not a model-local splitter.
- Multiple testing must be corrected. Use `renquant_common.stats.deflated_sharpe`
  and `renquant_common.stats.pbo_cscv` for DSR/PBO rather than reporting raw
  Sharpe or IC winners.
- Regime-conditioned metrics depend on detector quality. Regime labels must come
  from a versioned common contract and pass golden-window checks before any
  `per_regime_ic` or `min_regime_ic` is reported.

References:

- Nie et al. 2023, PatchTST, ICLR: https://openreview.net/forum?id=Jbdc0vTOcol
- Bailey and Lopez de Prado 2014, Deflated Sharpe Ratio:
  https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Bailey, Borwein, Lopez de Prado, Zhu 2016, Probability of Backtest
  Overfitting: https://doi.org/10.21314/JCF.2016.322
- Lopez de Prado 2018, Advances in Financial Machine Learning, ch. 7:
  https://www.oreilly.com/library/view/advances-in-financial/9781119482086/

## Goals

- Express research orchestration as `Task / Job / Pipeline` using
  `renquant_common`.
- Treat each `(config, cut, seed)` as an independent trial with explicit
  provenance.
- Use `renquant_common.run_parallel` only for independent trial jobs and only
  when the resource plan says concurrency is safe.
- Gate every reported IC behind the mandatory sanity triad: shuffled-label,
  time-shift placebo, and A/A split verification.
- Validate the splitter embargo invariant before dispatching compute.
- Validate regime detector quality before producing regime-conditioned metrics.
- Support deterministic linear runs and resource-aware parallel runs.
- Make experiments resumable without silently changing the trial matrix.
- Persist enough metadata to reproduce, compare, audit, and reject every result.

## Non-Goals

- Do not change `hf_trainer.train_single_run` semantics in this refactor.
- Do not import downstream repos such as `renquant_pipeline`,
  `renquant_backtesting`, `renquant_execution`, `kernel.*`, broker, or live code.
- Do not use the umbrella repo as a runtime dependency or path source.
- Do not promote a model automatically. The pipeline may emit a machine-readable
  verdict, but production promotion remains a separate manual/downstream action.

## Cross-Repo Boundaries

The pipeline lives in `renquant-model` because PatchTST research is
model-development work. It may depend on these upstream contracts:

- `renquant-common`: `Task`, `Job`, `Pipeline`, `run_parallel`,
  `PurgedKFold`, `CombinatorialPurgedCV`, `walk_forward_splits`,
  `hmm_regime_labels`, scorer contracts, training ledger helpers, and statistical
  gates.
- `renquant-base-data`: dataset/data-manifest validation.
- `renquant-artifacts`: artifact and model-evidence contract validation.

Cross-repo collaboration happens through explicit contracts:

- Data paths are explicit: `--data-dir`, `--dataset`, `--spy-path`, and optional
  dataset manifests. No inference from another checkout.
- Strategy/config provenance comes from `--strategy-config` or an experiment
  config snapshot. Do not `chdir` into another repo or import strategy modules.
- Model artifacts are exposed through `renquant_common.scorers` entry points and
  `ArtifactManifest` fields.
- Training runs are recorded through the shared ledger with `repo_dir`,
  `git_head`, dataset fingerprint, config fingerprint, matrix hash, and scheduler
  plan.
- Downstream backtesting/execution consumes persisted JSON/Parquet outputs. This
  pipeline must not call those repos in-process.

Dependency direction:

```text
renquant-common / base-data / artifacts
        -> renquant-model
        -> persisted experiment artifacts, manifests, reports
        -> downstream pipeline / backtesting / execution consumers
```

If a needed detector, splitter, or statistic exists only in a downstream or
umbrella module, lift it into `renquant-common` first and add common-side tests.
Do not import `kernel.*`.

## Top-Level Pipeline

```text
ExperimentPipeline
  PrepareEnvironmentJob
    ResolvePathsTask
    StampEnvironmentTask
    ValidateTrainerSurfaceTask
    RegimeDetectorContractTask
  PlanExperimentJob
    ExpandTrialMatrixTask
    ValidateSplitterEmbargoTask
    FingerprintTrialsTask
    ResolveResumeStateTask
  DispatchTrialsJob
    BuildExecutionPlanTask
    RunTrialsTask
  PlaceboGateJob
    ShuffleLabelTrialTask
    TimeShiftPlaceboTrialTask
    AASplitVerificationTask
    PlaceboVerdictTask
  AggregateResultsJob
    LoadTrialResultsTask
    ValidateResultCompletenessTask
    AggregateByConfigTask
    AggregateByCutAndSeedTask
  AnalyzeResultsJob
    CompareAgainstBaselineTask
    MultipleComparisonCorrectionTask
    RobustnessAndRiskTask
    DecideVerdictTask
  PersistResultsJob
    WriteJsonArtifactsTask
    WriteMarkdownReportTask
```

`ExperimentPipeline` owns orchestration only. Single-run training remains
delegated to `hf_trainer.train_single_run`, which already routes through
`sequence_training.run_sequence_training()`.

## Core Context Objects

`ExperimentSpec` captures requested work:

```python
@dataclass
class ExperimentSpec:
    phase: Literal["range_find", "doe", "confirm"]
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
    label_col: str = "fwd_60d_excess"
    label_lookahead_days: int = 60
    embargo_days: int = 60
    check_promotion: bool = False
```

`TrialSpec` is one atomic real or gate trial:

```python
@dataclass
class TrialSpec:
    trial_id: str
    config_name: str
    cut: str
    seed: int
    trial_kind: Literal["real", "shuffle_placebo", "timeshift_placebo", "aa_split"]
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
    trial_kind: Literal["real", "shuffle_placebo", "timeshift_placebo", "aa_split"]
    pooled_ic: float | None
    daily_ic_mean: float | None
    daily_ic_std: float | None
    positive_day_ratio: float | None
    min_regime_ic: float | None
    per_regime_ic: dict[str, float]
    n_dates: int
    n_rows: int
    elapsed_sec: float | None
    device: str
    git_head: str | None
    fingerprint: str
    error_class: str | None
    error: str | None
    artifacts: dict[str, str]
```

`ExperimentContext` carries mutable pipeline state:

```python
@dataclass
class ExperimentContext:
    spec: ExperimentSpec
    environment: dict[str, Any] = field(default_factory=dict)
    regime_contract: dict[str, Any] = field(default_factory=dict)
    trial_plan: list[TrialSpec] = field(default_factory=list)
    execution_plan: ExecutionPlan | None = None
    trial_results: list[TrialResult] = field(default_factory=list)
    placebo_gate: dict[str, Any] = field(default_factory=dict)
    aggregate_results: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    verdict: Literal[
        "promote_to_confirm",
        "needs_more_seeds",
        "reject",
        "invalid_experiment",
    ] | None = None
```

## PrepareEnvironmentJob

`ResolvePathsTask` resolves every path from explicit CLI arguments. It must fail
if `dataset` or `spy_path` is missing. It may resolve sibling repos only through
normal editable installs / `PYTHONPATH`, never by assuming an umbrella layout.

`StampEnvironmentTask` writes `environment.json` before dispatch:

- `git_head`, branch, dirty flag, and remote URL for `renquant-model`
- package versions for `torch`, `transformers`, `numpy`, `pandas`, `scipy`, and
  sibling `renquant-*` packages when importable
- CPU count, RAM summary if available, device, scheduler mode, max workers
- `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`
- Python random seed, NumPy seed, Torch seed, and DataLoader worker seed policy
- `matrix_hash`, `experiment_id`, UTC timestamp

For CPU parallel runs, `BuildExecutionPlanTask` must set per-worker thread caps
so workers do not each consume all cores. Example:
`per_worker_threads = max(1, floor(cpu_count / max_workers))`.

`ValidateTrainerSurfaceTask` checks the trainer supports required flags:

- always required: `--cut`, `--seed`, `--epochs`, `--device`, `--output-dir`,
  `--dataset`, `--label`, `--embargo-days`
- gate-required: `--shuffle-labels`
- if absent for time-shift, implementation must create a temporary shifted
  dataset snapshot and fingerprint it; do not fake the gate
- if `D_film` is in the matrix: `--film-regime-cond` and `--spy-path`
- if feature-drop configs are in the matrix: `--exclude-features`

## RegimeDetectorContractTask

Regime-conditioned IC is invalid unless the detector passes a contract check.
Use common-side labels, currently
`renquant_common.hmm_regime_labels.compute_hmm_regime_labels(spy_path)`.

The task must:

- compute labels from `--spy-path`
- assert label values are in `renquant_common.RegimeLabel`
- assert golden windows:
  - 2020-02-20 to 2020-04-30 has BEAR or CHOPPY coverage
  - 2022-04-01 to 2022-06-30 is majority BEAR
  - 2017-01-01 to 2017-12-31 is majority BULL_CALM
- stamp threshold constants, implementation module, source hash if available,
  input SPY fingerprint, and golden-window counts in `environment.json`

If the detector fails or the SPY file does not cover these windows, set
`verdict=invalid_experiment` and do not report `per_regime_ic` / `min_regime_ic`.
If a future dataset cannot include 2017, it must pass an explicit replacement
calm-window contract supplied in the experiment spec; silent omission is not
allowed.
If production parity requires a richer detector than `hmm_regime_labels`, lift it
to `renquant-common` first with tests; do not import umbrella `kernel.regime`.

## PlanExperimentJob

`ExpandTrialMatrixTask` builds real trials from `configs x cuts x seeds`. It also
builds gate trials for configs that would be eligible for reporting:

- `shuffle_placebo`: same config/cut/seed, training labels shuffled, validation
  labels left aligned
- `timeshift_placebo`: same config/cut/seed, training target shifted by
  `label_shift_days` or equivalent shifted dataset, validation labels left
  aligned
- `aa_split`: baseline and candidate repeated on an alternate purged split or
  CPCV partition to verify the candidate-baseline lift is not a split artifact

`ValidateSplitterEmbargoTask` is P0. For every cut used by a trial, load only
metadata and dates when possible, assign splits through the shared common
splitter, then assert:

```text
max(train_date) + label_lookahead_days < min(val_date)
min(train_date_after_val) > max(val_date) + embargo_days   # when train-after-val exists
```

The task must reject:

- missing `lookahead_days`
- `embargo_days < label_lookahead_days`
- model-local splitters that do not resolve to `renquant_common`
- named cuts that cannot expose `train`, `embargo`, `val`, and `test` counts

`FingerprintTrialsTask` includes all scientific conditions:

- config name and full trainer argv
- cut name, cut date ranges, split policy, `label_col`
- `label_lookahead_days`, `embargo_days`, and any `label_shift_days`
- seed, phase, epoch count, device request
- dataset path, dataset fingerprint/schema, SPY fingerprint
- strategy config fingerprint
- regime detector contract hash
- code git SHA and dirty flag

Resume is allowed only when the stored fingerprint exactly matches.

## Resource-Aware Execution

`BuildExecutionPlanTask` produces:

```python
@dataclass
class ExecutionPlan:
    mode: Literal["linear", "parallel"]
    max_workers: int
    device: str
    per_worker_threads: int
    reason: str
```

Default rules:

- `scheduler=linear`: stable sorted trial order, one trial at a time.
- `scheduler=parallel`: use `max_workers`, capped by trial count and resource
  safety checks.
- `scheduler=auto`:
  - `device=mps`: linear by default because Apple MPS jobs share one GPU memory
    pool.
  - `device=cuda`: parallel only when multiple CUDA devices are visible; map
    one worker to one device.
  - `device=cpu`: parallel with capped per-worker BLAS/OpenMP threads.
  - Phase `range_find`: may parallelize aggressively on CPU.
  - Phase `confirm`: prefer linear or low concurrency for reproducibility.

`RunTrialsTask` calls:

```python
run_parallel(trial_contexts, TrialJob(), max_workers=plan.max_workers)
```

only when `plan.mode == "parallel"`. In linear mode it calls
`TrialJob().run(ctx)` for each trial in stable sorted order.

Important `run_parallel` constraint: worker exceptions are logged by
`renquant_common.run_parallel` but do not automatically create a failed result
row. Therefore `TrialJob` must catch expected trial failures internally and
persist `TrialResult(status="failed")`. A timeout from `run_parallel` remains a
hard pipeline failure.

## Trial Job

Each trial is a small job:

```text
TrialJob
  PrepareTrialTask
  RunTrainerTask
  LoadValidationPredictionsTask
  NormalizePredictionSchemaTask
  ComputeTrialMetricsTask
  PersistTrialResultTask
```

`RunTrainerTask` builds CLI args from `TrialSpec.argv` and calls
`hf_trainer.train_single_run`. If `resume=True` and both `summary_path` and
`val_preds_path` exist with matching fingerprint, it skips training and loads
existing evidence.

Failures write a `TrialResult(status="failed")` row with exception class,
message, elapsed time, and artifact paths. A failed trial must not erase prior
results.

## Prediction Schema

`LoadValidationPredictionsTask` accepts the current trainer schema:

```text
date, ticker, pred, label, mu?, sigma?
```

`NormalizePredictionSchemaTask` writes a normalized Parquet under the experiment
directory:

```text
date, ticker, model_score, calibrated_score, label, split_label, regime,
config_name, cut, seed, trial_kind, trial_id
```

Rules:

- `model_score` comes from `pred`.
- `calibrated_score` is nullable. Initial implementation may leave it null.
- If calibrated scores are emitted later, the pipeline must prove the calibrator
  was fit on `split_label == "train"` only. `!= "val"` is forbidden because it
  includes test rows.
- `regime` comes from the validated common detector labels, not trainer-local
  fallback labels.

## Metrics

Per-trial metrics:

- pooled per-date Spearman IC: compute Spearman across tickers for each
  validation date, then average dates. Never use one row-pooled correlation.
- daily IC mean, standard deviation, standard error, and HAC/Newey-West mean
  where enough dates exist
- positive daily IC ratio
- per-regime IC and `min_regime_ic`, after `RegimeDetectorContractTask` passes
- number of validation dates and rows
- label distribution summary
- elapsed seconds, device, and worker/thread counts

Aggregate metrics per config:

- mean pooled IC across cuts/seeds
- standard error across cuts/seeds
- positive cut count and positive seed count
- worst-cut IC
- mean delta vs `B_tuned`
- placebo-adjusted IC
- failed/skipped trial count, shown prominently

Partial failure policy:

- `failed_trial_count / total_trial_count > 1/3` sets
  `verdict=invalid_experiment`.
- Otherwise aggregate succeeded trials only, but every table and verdict must
  stamp `n_failed`, `n_skipped`, and missing trial IDs.

## PlaceboGateJob

The sanity triad is a pipeline gate, not a phase-2-only analysis note. Raw
`trial_results.jsonl` can be written for audit, but `analysis.json` and
`report.md` must not contain headline IC or promotion recommendations until this
gate passes.

Gate tasks:

- `ShuffleLabelTrialTask`: retrain with training labels shuffled; validation
  labels remain aligned. Pass if `abs(shuffle_ic_mean) <= max(0.01,
  0.25 * abs(real_ic_mean))`.
- `TimeShiftPlaceboTrialTask`: retrain on shifted labels or a shifted dataset.
  Pass if `abs(timeshift_ic_mean) <= max(0.01, 0.5 * abs(real_ic_mean))`.
- `AASplitVerificationTask`: rerun candidate-vs-baseline on an alternate purged
  split/CPCV partition. Pass if the lift does not reverse sign; if sample count
  is insufficient, verdict becomes `needs_more_seeds`, not `promote_to_confirm`.
- `PlaceboVerdictTask`: if any gate fails, set `verdict=invalid_experiment`,
  write `invalid_experiment.json`, and stop before scientific report generation.

The gate applies before every IC-bearing report, including phase `range_find`.
Small smoke runs may use `--allow-ungated-smoke`, but outputs must be named
`smoke_*` and cannot write `analysis.json` or `report.md`.

## AnalyzeResultsJob

`MultipleComparisonCorrectionTask` calls:

- `renquant_common.stats.deflated_sharpe(returns, n_trials=design_matrix_size)`
- `renquant_common.stats.pbo_cscv(returns_matrix)`

`n_trials` is the full design matrix size considered for selection, not only the
surviving or successful rows. PBO uses a config-by-observation matrix where
observations are cut/seed/date-level IC or return deltas.

Verdict rules:

```text
invalid_experiment:
  any P0 gate fails, detector contract fails, splitter embargo fails,
  failed_trial_count / total_trial_count > 1/3, or required artifacts missing

promote_to_confirm:
  range_find/doe only; mean_delta_vs_B_tuned > 1 SE,
  positive_cut_count >= baseline_positive_cut_count,
  no regime-conditioned gate failure

needs_more_seeds:
  positive effect but fewer than required seeds/cuts for DSR/PBO or A/A split
  verification

reject:
  gate-clean but effect is non-positive, unstable, or worse than baseline
```

For phase `confirm`, the report may recommend downstream promotion review only
when:

- all real and placebo gates pass
- all planned cuts and seeds completed or failure ratio is zero for promotion
  candidate rows
- mean pooled IC exceeds the declared XGB baseline
- `min_regime_ic` is not negative for eligible regimes with enough samples
- DSR exceeds the repo promotion threshold (`> 0.5` by current RenQuant
  promotion policy; a stricter config may require `> 0.95`)
- PBO is below the repo rejection threshold (`< 0.5`)

`--check-promotion <experiment_dir>` loads persisted analysis and exits:

- `0`: verdict is `promote_to_confirm`
- `1`: verdict is `needs_more_seeds` or `reject`
- `2`: verdict is `invalid_experiment` or artifacts are corrupt/missing

## Persistence Layout

Every experiment writes a self-contained directory:

```text
artifacts/patchtst_research/<experiment_id>/
  experiment_spec.json
  environment.json
  regime_contract.json
  trial_plan.json
  trial_results.jsonl
  normalized_predictions/
    <trial_id>.parquet
  placebo_gate.json
  aggregate_results.json
  analysis.json
  report.md
  invalid_experiment.json        # only when a P0 gate blocks reporting
```

`experiment_id` includes UTC timestamp, phase, git short SHA, and matrix hash.

## Resume Rules

Resume is conservative:

- Existing trial outputs are reused only when stored fingerprint matches the
  planned `TrialSpec`.
- Partial files do not count as completed trials.
- Changed config, seed, cut, dataset/schema/fingerprint, SPY fingerprint,
  regime detector hash, label horizon, embargo, git head, or trainer argv creates
  a new fingerprint.
- `--no-resume` forces recomputation.
- Resumed results still re-run `PlaceboGateJob` and aggregation from stored
  trial rows.

## CLI Shape

Preserve existing flags and add explicit execution/gating controls:

```bash
python -m renquant_model_patchtst.research \
  --phase range_find \
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

Promotion check mode:

```bash
python -m renquant_model_patchtst.research \
  --check-promotion artifacts/patchtst_research/<experiment_id>
```

## Test Plan

Add focused tests for:

- trial matrix expansion and stable trial IDs
- fingerprint changes when config/data/git/splitter/regime inputs change
- resume accepts matching fingerprints and rejects mismatches
- scheduler decisions for `cpu`, `mps`, `cuda`, `linear`, and `parallel`
- `RunTrialsTask` dispatches to `run_parallel` only when plan mode is `parallel`
- `TrialJob` persists `failed` rows even when trainer raises
- splitter embargo rejects any `max(train_date) + lookahead >= min(val_date)`
- regime detector contract validates 2022-Q2 BEAR and 2017 BULL_CALM when data
  covers those windows
- shuffled-label gate blocks report generation when placebo IC exceeds threshold
- time-shift gate blocks report generation when IC remains too high
- A/A split verification returns `needs_more_seeds` when evidence is insufficient
- aggregate verdict becomes `invalid_experiment` when failed trials exceed 1/3
- `MultipleComparisonCorrectionTask` passes `n_trials=design_matrix_size`
- normalized prediction schema accepts current trainer output and stamps
  `regime`, `trial_kind`, and `trial_id`
- `--check-promotion` exit codes are 0/1/2 for promote/reject/invalid cases

## Implementation Sequence

1. Add dataclasses and planning tasks with splitter/regime/fingerprint tests.
2. Add normalized prediction schema and metric computation tests using synthetic
   Parquet predictions.
3. Add `TrialJob` with mocked trainer tests, including persisted failures.
4. Add scheduler and `run_parallel` dispatch tests.
5. Add `PlaceboGateJob` with shuffled/time-shift/A-A synthetic failures.
6. Add aggregation, DSR/PBO, verdict, and report-generation tests.
7. Keep current `run_one` behavior as a compatibility adapter.
8. Switch CLI `main()` to build and run `ExperimentPipeline`.
9. Remove obsolete ad hoc loop code after parity tests pass.
