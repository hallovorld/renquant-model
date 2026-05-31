"""Auditable PatchTST research pipeline.

This module replaces the old research loop with Task/Job/Pipeline orchestration.
Heavy model training still goes through ``hf_trainer.train_single_run``; this
file owns experiment planning, resource dispatch, gating, aggregation, and
persistence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from renquant_common import Job, Pipeline, Task, run_parallel
from renquant_common.stats import deflated_sharpe, pbo_cscv

from .splits import (
    DEFAULT_ALL_VAL_TAIL_PCT,
    SPLITTER_IMPLEMENTATION,
    assign_patchtst_split,
)

Phase = Literal["range_find", "doe", "confirm"]
TrialKind = Literal["real", "shuffle_placebo", "timeshift_placebo"]
TrialStatus = Literal["ok", "skipped", "failed"]
Verdict = Literal[
    "promote_to_confirm",
    "promote_to_live",
    "needs_more_seeds",
    "reject",
    "invalid_experiment",
]

DEFAULT_BASELINE_CONFIG = "B_tuned"
DEFAULT_LABEL_SHIFT_DAYS = 10
NON_DEFENSIVE_REGIMES = frozenset({"BULL_CALM", "BULL_VOLATILE", "BULL_STRONG", "CHOPPY"})
DEFAULT_TRIAL_TIMEOUTS_SEC = {
    "real": 4 * 60 * 60,
    "shuffle_placebo": 4 * 60 * 60,
    "timeshift_placebo": 4 * 60 * 60,
}
GATE_THRESHOLDS = {
    "version": 1,
    "shuffle_abs_ic": 0.01,
    "shuffle_real_fraction": 0.25,
    "timeshift_abs_ic": 0.01,
    "timeshift_real_fraction": 0.50,
    "label_shift_days": DEFAULT_LABEL_SHIFT_DAYS,
}
REGIME_GOLDEN_WINDOWS = (
    {
        "name": "covid_crash",
        "start": "2020-02-20",
        "end": "2020-04-30",
        "allowed_majority": ("BEAR", "CHOPPY"),
        "mode": "any_coverage",
    },
    {
        "name": "q2_2022_bear",
        "start": "2022-04-01",
        "end": "2022-06-30",
        "allowed_majority": ("BEAR",),
        "mode": "majority",
    },
    {
        "name": "calm_2017",
        "start": "2017-01-01",
        "end": "2017-12-31",
        "allowed_majority": ("BULL_CALM",),
        "mode": "majority",
    },
)


@dataclass
class ExperimentSpec:
    phase: Phase
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
    config_args: dict[str, list[str]] = field(default_factory=dict)
    max_workers: int | None = None
    resume: bool = True
    fail_fast: bool = False
    require_placebos: bool = True
    allow_ungated_smoke: bool = False
    require_regime_contract: bool = True
    label_col: str = "fwd_60d_excess"
    label_lookahead_days: int = 60
    embargo_days: int = 60
    val_tail_pct: float = DEFAULT_ALL_VAL_TAIL_PCT
    label_shift_days: int = DEFAULT_LABEL_SHIFT_DAYS
    baseline_config: str = DEFAULT_BASELINE_CONFIG
    baseline_pooled_ic: float | None = None
    check_promotion: bool = False
    experiment_id: str | None = None


@dataclass
class TrialSpec:
    trial_id: str
    config_name: str
    cut: str
    seed: int
    trial_kind: TrialKind
    argv: list[str]
    out_dir: Path
    val_preds_path: Path
    summary_path: Path
    fingerprint: str = ""
    timeout_seconds: float | None = None


@dataclass
class TrialResult:
    trial_id: str
    status: TrialStatus
    trial_kind: TrialKind
    config_name: str
    cut: str
    seed: int
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


@dataclass
class ExecutionPlan:
    mode: Literal["linear", "parallel"]
    max_workers: int
    device: str
    per_worker_threads: int
    reason: str


@dataclass
class ExperimentContext:
    spec: ExperimentSpec
    environment: dict[str, Any] = field(default_factory=dict)
    regime_contract: dict[str, Any] = field(default_factory=dict)
    trial_plan: list[TrialSpec] = field(default_factory=list)
    execution_plan: ExecutionPlan | None = None
    trial_contexts: list["TrialContext"] = field(default_factory=list)
    trial_results: list[TrialResult] = field(default_factory=list)
    placebo_gate: dict[str, Any] = field(default_factory=dict)
    aggregate_results: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    verdict: Verdict | None = None
    matrix_hash: str = ""
    experiment_dir: Path | None = None


@dataclass
class TrialContext:
    experiment: ExperimentContext
    spec: TrialSpec
    trainer_runner: Callable[[argparse.Namespace], Any]
    parser_builder: Callable[[], argparse.ArgumentParser]
    regime_labels: pd.DataFrame | None = None
    normalized_preds_path: Path | None = None
    result: TrialResult | None = None
    summary: dict[str, Any] | None = None
    started_at: float | None = None

    @property
    def id(self) -> str:
        return self.spec.trial_id


def build_experiment_pipeline(
    *,
    trainer_runner: Callable[[argparse.Namespace], Any],
    parser_builder: Callable[[], argparse.ArgumentParser],
) -> Pipeline:
    return Pipeline(
        [
            PrepareEnvironmentJob(parser_builder),
            PlanExperimentJob(),
            DispatchTrialsJob(trainer_runner, parser_builder),
            PlaceboGateJob(),
            AggregateResultsJob(),
            AnalyzeResultsJob(),
            PersistResultsJob(),
        ],
        name="patchtst-research-experiment",
    )


def run_experiment(
    spec: ExperimentSpec,
    *,
    trainer_runner: Callable[[argparse.Namespace], Any],
    parser_builder: Callable[[], argparse.ArgumentParser],
) -> ExperimentContext:
    ctx = ExperimentContext(spec=spec)
    build_experiment_pipeline(
        trainer_runner=trainer_runner,
        parser_builder=parser_builder,
    ).run(ctx)
    return ctx


class PrepareEnvironmentJob(Job):
    def __init__(self, parser_builder: Callable[[], argparse.ArgumentParser]) -> None:
        self._tasks = [
            ResolvePathsTask(),
            StampEnvironmentTask(),
            ValidateTrainerSurfaceTask(parser_builder),
            RegimeDetectorContractTask(),
        ]

    @property
    def tasks(self) -> list[Task]:
        return self._tasks


class ResolvePathsTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        spec.dataset = spec.dataset.expanduser()
        spec.spy_path = spec.spy_path.expanduser()
        spec.data_dir = spec.data_dir.expanduser()
        spec.out_dir = spec.out_dir.expanduser()
        if spec.strategy_config is not None:
            spec.strategy_config = spec.strategy_config.expanduser()
        if not spec.dataset.exists():
            raise FileNotFoundError(f"dataset not found: {spec.dataset}")
        if spec.require_regime_contract and not spec.spy_path.exists():
            raise FileNotFoundError(f"spy_path not found: {spec.spy_path}")
        spec.out_dir.mkdir(parents=True, exist_ok=True)
        return True


class StampEnvironmentTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        git_head, git_dirty = _git_state()
        seed_material = {
            "configs": spec.configs,
            "cuts": spec.cuts,
            "seeds": spec.seeds,
            "phase": spec.phase,
            "epochs": spec.epochs,
            "label_col": spec.label_col,
            "label_lookahead_days": spec.label_lookahead_days,
            "embargo_days": spec.embargo_days,
            "val_tail_pct": spec.val_tail_pct,
            "label_shift_days": spec.label_shift_days,
        }
        ctx.matrix_hash = _short_hash(seed_material)
        exp_id = spec.experiment_id or (
            f"{_utc_stamp()}_{spec.phase}_{(git_head or 'nogit')[:8]}_{ctx.matrix_hash}"
        )
        ctx.experiment_dir = spec.out_dir / exp_id
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)
        first_seed = int(spec.seeds[0]) if spec.seeds else 0
        ctx.environment = {
            "experiment_id": exp_id,
            "matrix_hash": ctx.matrix_hash,
            "utc_timestamp": _utc_stamp(),
            "git_head": git_head,
            "git_dirty": git_dirty,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "device_request": spec.device,
            "scheduler": spec.scheduler,
            "max_workers": spec.max_workers,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
            "python_random_seed": first_seed,
            "numpy_seed": first_seed,
            "torch_seed": first_seed,
            "dataloader_worker_seed_policy": "TrialSpec.seed + worker_id",
            "dataset_fingerprint": _file_fingerprint(spec.dataset),
            "spy_fingerprint": _file_fingerprint(spec.spy_path) if spec.spy_path.exists() else None,
            "strategy_config_fingerprint": (
                _file_fingerprint(spec.strategy_config)
                if spec.strategy_config and spec.strategy_config.exists()
                else None
            ),
            # Spec switches that affect the verdict surface — stamped here so
            # downstream audit dashboards reading environment.json see the
            # exact policy the run ran under (PR #8 finding 2).
            "require_regime_contract": bool(spec.require_regime_contract),
            "require_placebos": bool(spec.require_placebos),
            "allow_ungated_smoke": bool(spec.allow_ungated_smoke),
        }
        random.seed(first_seed)
        np.random.seed(first_seed)
        return True


class ValidateTrainerSurfaceTask(Task):
    def __init__(self, parser_builder: Callable[[], argparse.ArgumentParser]) -> None:
        self._parser_builder = parser_builder

    def run(self, ctx: ExperimentContext) -> bool | None:
        actions = self._parser_builder()._actions
        dests = {getattr(action, "dest", None) for action in actions}
        required = {
            "cut",
            "seed",
            "epochs",
            "device",
            "output_dir",
            "dataset",
            "label",
            "embargo_days",
            "val_tail_pct",
        }
        if ctx.spec.require_placebos and not ctx.spec.allow_ungated_smoke:
            required |= {"shuffle_labels", "label_shift_days"}
        for config_name in ctx.spec.configs:
            args = ctx.spec.config_args.get(config_name, [])
            if "--film-regime-cond" in args:
                required |= {"film_regime_cond", "spy_path"}
            if "--exclude-features" in args:
                required.add("exclude_features")
        missing = sorted(required - dests)
        if missing:
            raise ValueError(f"trainer parser missing required flags: {missing}")
        ctx.environment["trainer_surface"] = {"required": sorted(required), "ok": True}
        return True


class RegimeDetectorContractTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        if not spec.require_regime_contract:
            ctx.regime_contract = {"required": False, "passed": True}
            return True
        from renquant_common.hmm_regime_labels import (  # noqa: PLC0415
            BEAR_RET_20D_THR,
            BEAR_RET_5D_THR,
            BEAR_VOL_20D_THR,
            BEAR_VOL_5D_THR,
            CHOPPY_DRIFT_TH,
            CHOPPY_VOL_RATIO,
            HURST_TREND_THR,
            compute_hmm_regime_labels,
        )

        labels = compute_hmm_regime_labels(spec.spy_path)
        labels["date"] = pd.to_datetime(labels["date"])
        counts: dict[str, Any] = {}
        failures: list[str] = []
        for window in REGIME_GOLDEN_WINDOWS:
            start = pd.Timestamp(window["start"])
            end = pd.Timestamp(window["end"])
            sub = labels[(labels["date"] >= start) & (labels["date"] <= end)]
            if sub.empty:
                failures.append(f"{window['name']}: missing SPY coverage")
                counts[window["name"]] = {}
                continue
            vc = {str(k): int(v) for k, v in sub["regime"].value_counts().to_dict().items()}
            counts[window["name"]] = vc
            allowed = set(window["allowed_majority"])
            if window["mode"] == "any_coverage":
                if not (set(vc) & allowed):
                    failures.append(f"{window['name']}: no allowed regimes {sorted(allowed)}")
            else:
                majority = max(vc, key=vc.get)
                if majority not in allowed:
                    failures.append(
                        f"{window['name']}: majority {majority}, expected {sorted(allowed)}"
                    )
        ctx.regime_contract = {
            "required": True,
            "passed": not failures,
            "failures": failures,
            "golden_window_counts": counts,
            "module": "renquant_common.hmm_regime_labels",
            "thresholds": {
                "BEAR_VOL_20D_THR": BEAR_VOL_20D_THR,
                "BEAR_RET_20D_THR": BEAR_RET_20D_THR,
                "BEAR_VOL_5D_THR": BEAR_VOL_5D_THR,
                "BEAR_RET_5D_THR": BEAR_RET_5D_THR,
                "CHOPPY_VOL_RATIO": CHOPPY_VOL_RATIO,
                "CHOPPY_DRIFT_TH": CHOPPY_DRIFT_TH,
                "HURST_TREND_THR": HURST_TREND_THR,
            },
        }
        if failures:
            ctx.verdict = "invalid_experiment"
            return False
        return True


class PlanExperimentJob(Job):
    @property
    def tasks(self) -> list[Task]:
        return [
            ExpandTrialMatrixTask(),
            ValidateSplitterEmbargoTask(),
            FingerprintTrialsTask(),
            ResolveResumeStateTask(),
        ]


class ExpandTrialMatrixTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        kinds: list[TrialKind] = ["real"]
        if spec.require_placebos and not spec.allow_ungated_smoke:
            kinds.extend(["shuffle_placebo", "timeshift_placebo"])
        trials: list[TrialSpec] = []
        for config_name in sorted(spec.configs):
            extra = list(spec.config_args.get(config_name, []))
            for cut in sorted(spec.cuts):
                for seed in sorted(spec.seeds):
                    for kind in kinds:
                        trial_id = _trial_id(config_name, cut, seed, kind)
                        out_dir = ctx.experiment_dir / "trials" / trial_id
                        argv = _trial_argv(spec, extra, cut, seed, out_dir, kind)
                        trials.append(
                            TrialSpec(
                                trial_id=trial_id,
                                config_name=config_name,
                                cut=cut,
                                seed=seed,
                                trial_kind=kind,
                                argv=argv,
                                out_dir=out_dir,
                                val_preds_path=out_dir / f"hf_patchtst_{cut}_seed{seed}_val_preds.parquet",
                                summary_path=out_dir / f"hf_patchtst_{cut}_seed{seed}_summary.json",
                                timeout_seconds=float(DEFAULT_TRIAL_TIMEOUTS_SEC[kind]),
                            )
                        )
        ctx.trial_plan = trials
        return True


class ValidateSplitterEmbargoTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        panel = _read_panel_dates(spec.dataset, spec.label_col)
        failures: list[str] = []
        for cut in sorted(set(t.cut for t in ctx.trial_plan)):
            split = _assign_split(
                panel,
                cut,
                spec.embargo_days,
                val_tail_pct=spec.val_tail_pct,
            )
            dates = pd.to_datetime(panel["date"])
            val_dates = dates[split == "val"]
            if val_dates.empty:
                failures.append(f"{cut}: no val rows")
                continue
            train_dates = dates[split == "train"]
            train_before = train_dates[train_dates < val_dates.min()]
            train_after = train_dates[train_dates > val_dates.max()]
            if len(train_before):
                if train_before.max() + pd.offsets.BDay(spec.label_lookahead_days) >= val_dates.min():
                    failures.append(
                        f"{cut}: train label window overlaps val "
                        f"(lookahead={spec.label_lookahead_days})"
                    )
            if len(train_after):
                if train_after.min() <= val_dates.max() + pd.offsets.BDay(spec.embargo_days):
                    failures.append(f"{cut}: train-after-val violates embargo={spec.embargo_days}")
            if spec.embargo_days < spec.label_lookahead_days:
                failures.append(
                    f"{cut}: embargo_days={spec.embargo_days} < "
                    f"label_lookahead_days={spec.label_lookahead_days}"
                )
        ctx.environment["splitter_contract"] = {
            "implementation": SPLITTER_IMPLEMENTATION,
            "lookahead_days": spec.label_lookahead_days,
            "embargo_days": spec.embargo_days,
            "all_cut_val_tail_pct": spec.val_tail_pct,
            "cuts": sorted(set(t.cut for t in ctx.trial_plan)),
            "passed": not failures,
            "failures": failures,
        }
        if failures:
            ctx.verdict = "invalid_experiment"
            raise ValueError(f"splitter embargo invariant failed: {failures}")
        return True


class FingerprintTrialsTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        for trial in ctx.trial_plan:
            payload = {
                "trial_id": trial.trial_id,
                "config_name": trial.config_name,
                "cut": trial.cut,
                "seed": trial.seed,
                "trial_kind": trial.trial_kind,
                "argv": trial.argv,
                "phase": spec.phase,
                "epochs": spec.epochs,
                "dataset": str(spec.dataset),
                "dataset_fingerprint": ctx.environment.get("dataset_fingerprint"),
                "spy_fingerprint": ctx.environment.get("spy_fingerprint"),
                "strategy_config_fingerprint": ctx.environment.get("strategy_config_fingerprint"),
                "label_col": spec.label_col,
                "label_lookahead_days": spec.label_lookahead_days,
                "embargo_days": spec.embargo_days,
                "val_tail_pct": spec.val_tail_pct,
                "label_shift_days": spec.label_shift_days,
                "git_head": ctx.environment.get("git_head"),
                "git_dirty": ctx.environment.get("git_dirty"),
                "regime_contract": ctx.regime_contract,
                "splitter_contract": ctx.environment.get("splitter_contract"),
                "gate_thresholds": GATE_THRESHOLDS,
            }
            trial.fingerprint = "sha256:" + _hash_json(payload)
        return True


class ResolveResumeStateTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        reusable = 0
        for trial in ctx.trial_plan:
            fp_path = trial.out_dir / "trial_fingerprint.json"
            result_path = trial.out_dir / "trial_result.json"
            if (
                ctx.spec.resume
                and fp_path.exists()
                and result_path.exists()
                and _json_load(fp_path).get("fingerprint") == trial.fingerprint
            ):
                reusable += 1
        ctx.environment["resume"] = {
            "enabled": ctx.spec.resume,
            "reusable_trials": reusable,
            "planned_trials": len(ctx.trial_plan),
        }
        return True


class DispatchTrialsJob(Job):
    def __init__(
        self,
        trainer_runner: Callable[[argparse.Namespace], Any],
        parser_builder: Callable[[], argparse.ArgumentParser],
    ) -> None:
        self._tasks = [
            BuildExecutionPlanTask(),
            RunTrialsTask(trainer_runner, parser_builder),
        ]

    @property
    def tasks(self) -> list[Task]:
        return self._tasks

    def should_skip(self, ctx: ExperimentContext) -> bool:
        return ctx.verdict == "invalid_experiment"


class BuildExecutionPlanTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        spec = ctx.spec
        n_trials = len(ctx.trial_plan)
        cpu_count = os.cpu_count() or 4
        device = _resolve_device(spec.device)
        if spec.scheduler == "linear" or n_trials <= 1:
            mode = "linear"
            workers = 1
            reason = "explicit linear or <=1 trial"
        elif spec.scheduler == "parallel":
            mode = "parallel"
            workers = min(spec.max_workers or max(1, cpu_count - 2), n_trials)
            reason = "explicit parallel"
        elif device == "mps":
            mode = "linear"
            workers = 1
            reason = "MPS uses one shared GPU memory pool"
        elif device == "cuda":
            cuda_count = int(os.environ.get("CUDA_VISIBLE_DEVICE_COUNT", "1"))
            if cuda_count > 1:
                mode = "parallel"
                workers = min(cuda_count, n_trials)
                reason = "multiple CUDA devices"
            else:
                mode = "linear"
                workers = 1
                reason = "single CUDA device"
        else:
            mode = "parallel"
            workers = min(spec.max_workers or max(1, cpu_count - 2), n_trials)
            reason = "CPU auto parallel"
        per_worker_threads = max(1, math.floor(cpu_count / max(1, workers)))
        ctx.execution_plan = ExecutionPlan(
            mode=mode,
            max_workers=workers,
            device=device,
            per_worker_threads=per_worker_threads,
            reason=reason,
        )
        ctx.environment["execution_plan"] = asdict(ctx.execution_plan)
        return True


class RunTrialsTask(Task):
    def __init__(
        self,
        trainer_runner: Callable[[argparse.Namespace], Any],
        parser_builder: Callable[[], argparse.ArgumentParser],
    ) -> None:
        self._trainer_runner = trainer_runner
        self._parser_builder = parser_builder

    def run(self, ctx: ExperimentContext) -> bool | None:
        regime_labels = _load_regime_labels(ctx)
        contexts = [
            TrialContext(
                experiment=ctx,
                spec=trial,
                trainer_runner=self._trainer_runner,
                parser_builder=self._parser_builder,
                regime_labels=regime_labels,
            )
            for trial in ctx.trial_plan
        ]
        ctx.trial_contexts = contexts
        plan = ctx.execution_plan
        if plan is None:
            raise ValueError("execution_plan must be built before RunTrialsTask")
        job = TrialJob()
        if plan.mode == "parallel":
            run_parallel(contexts, job, max_workers=plan.max_workers)
        else:
            for trial_ctx in contexts:
                job.run(trial_ctx)
                if ctx.spec.fail_fast and trial_ctx.result and trial_ctx.result.status == "failed":
                    break
        ctx.trial_results = [tc.result for tc in contexts if tc.result is not None]
        return True


class TrialJob(Job):
    @property
    def tasks(self) -> list[Task]:
        return [
            PrepareTrialTask(),
            RunTrainerTask(),
            LoadValidationPredictionsTask(),
            NormalizePredictionSchemaTask(),
            ComputeTrialMetricsTask(),
            PersistTrialResultTask(),
        ]

    def run(self, ctx: TrialContext) -> None:
        ctx.started_at = time.monotonic()
        try:
            super().run(ctx)
        except Exception as exc:  # noqa: BLE001
            ctx.result = _failed_result(ctx, exc)
            _persist_trial_result(ctx)


class PrepareTrialTask(Task):
    def run(self, ctx: TrialContext) -> bool | None:
        ctx.spec.out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(ctx.spec.out_dir / "trial_spec.json", _trial_spec_payload(ctx.spec))
        _write_json(
            ctx.spec.out_dir / "trial_fingerprint.json",
            {
                "trial_id": ctx.spec.trial_id,
                "fingerprint": ctx.spec.fingerprint,
                "gate_thresholds": GATE_THRESHOLDS,
                "splitter_contract": ctx.experiment.environment.get("splitter_contract"),
            },
        )
        return True


class RunTrainerTask(Task):
    def run(self, ctx: TrialContext) -> bool | None:
        trial = ctx.spec
        result_path = trial.out_dir / "trial_result.json"
        if (
            ctx.experiment.spec.resume
            and result_path.exists()
            and (trial.out_dir / "trial_fingerprint.json").exists()
            and _json_load(trial.out_dir / "trial_fingerprint.json").get("fingerprint")
            == trial.fingerprint
        ):
            ctx.result = _trial_result_from_dict(_json_load(result_path))
            return False
        parser = ctx.parser_builder()
        args = parser.parse_args(trial.argv)
        ctx.summary = ctx.trainer_runner(args)
        if trial.summary_path.exists():
            ctx.summary = _json_load(trial.summary_path)
        return True


class LoadValidationPredictionsTask(Task):
    def run(self, ctx: TrialContext) -> bool | None:
        if not ctx.spec.val_preds_path.exists():
            if isinstance(ctx.summary, dict):
                raw = ctx.summary.get("val_preds_path") or ctx.summary.get("validation_predictions")
                if raw:
                    ctx.spec.val_preds_path = Path(raw)
        if not ctx.spec.val_preds_path.exists():
            raise FileNotFoundError(
                f"validation predictions missing for {ctx.spec.trial_id}: "
                f"{ctx.spec.val_preds_path}"
            )
        return True


class NormalizePredictionSchemaTask(Task):
    def run(self, ctx: TrialContext) -> bool | None:
        df = pd.read_parquet(ctx.spec.val_preds_path)
        missing = {"date", "ticker", "label"} - set(df.columns)
        if missing:
            raise ValueError(f"{ctx.spec.trial_id} val preds missing columns: {sorted(missing)}")
        if "model_score" not in df.columns:
            if "pred" not in df.columns:
                raise ValueError(f"{ctx.spec.trial_id} val preds missing pred/model_score")
            df = df.rename(columns={"pred": "model_score"})
        if "calibrated_score" not in df.columns:
            df["calibrated_score"] = np.nan
        if "split_label" not in df.columns:
            df["split_label"] = "val"
        df["date"] = pd.to_datetime(df["date"])
        if ctx.regime_labels is not None:
            regimes = ctx.regime_labels.copy()
            regimes["date"] = pd.to_datetime(regimes["date"])
            df = df.merge(regimes[["date", "regime"]], on="date", how="left")
        elif "regime" not in df.columns:
            df["regime"] = None
        df["config_name"] = ctx.spec.config_name
        df["cut"] = ctx.spec.cut
        df["seed"] = ctx.spec.seed
        df["trial_kind"] = ctx.spec.trial_kind
        df["trial_id"] = ctx.spec.trial_id
        out_dir = ctx.experiment.experiment_dir / "normalized_predictions"
        out_dir.mkdir(parents=True, exist_ok=True)
        ctx.normalized_preds_path = out_dir / f"{ctx.spec.trial_id}.parquet"
        df.to_parquet(ctx.normalized_preds_path, index=False)
        return True


class ComputeTrialMetricsTask(Task):
    def run(self, ctx: TrialContext) -> bool | None:
        df = pd.read_parquet(ctx.normalized_preds_path)
        daily = _daily_ic(df)
        arr = np.asarray(daily, dtype=float)
        per_regime: dict[str, float] = {}
        for regime, group in df.dropna(subset=["regime"]).groupby("regime"):
            vals = _daily_ic(group)
            if len(vals):
                per_regime[str(regime)] = float(np.mean(vals))
        min_regime = min(per_regime.values()) if per_regime else None
        elapsed = time.monotonic() - ctx.started_at if ctx.started_at is not None else None
        ctx.result = TrialResult(
            trial_id=ctx.spec.trial_id,
            status="ok",
            trial_kind=ctx.spec.trial_kind,
            config_name=ctx.spec.config_name,
            cut=ctx.spec.cut,
            seed=ctx.spec.seed,
            pooled_ic=float(arr.mean()) if len(arr) else None,
            daily_ic_mean=float(arr.mean()) if len(arr) else None,
            daily_ic_std=float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            positive_day_ratio=float((arr > 0).mean()) if len(arr) else None,
            min_regime_ic=float(min_regime) if min_regime is not None else None,
            per_regime_ic=per_regime,
            n_dates=int(df["date"].nunique()),
            n_rows=int(len(df)),
            elapsed_sec=elapsed,
            device=ctx.experiment.execution_plan.device if ctx.experiment.execution_plan else "",
            git_head=ctx.experiment.environment.get("git_head"),
            fingerprint=ctx.spec.fingerprint,
            error_class=None,
            error=None,
            artifacts={
                "val_preds_path": str(ctx.spec.val_preds_path),
                "normalized_preds_path": str(ctx.normalized_preds_path),
                "summary_path": str(ctx.spec.summary_path),
            },
        )
        return True


class PersistTrialResultTask(Task):
    def run(self, ctx: TrialContext) -> bool | None:
        _persist_trial_result(ctx)
        return True


class PlaceboGateJob(Job):
    @property
    def tasks(self) -> list[Task]:
        return [
            ShuffleLabelTrialTask(),
            TimeShiftPlaceboTrialTask(),
            AASplitVerificationTask(),
            PlaceboVerdictTask(),
        ]

    def should_skip(self, ctx: ExperimentContext) -> bool:
        return ctx.spec.allow_ungated_smoke or not ctx.spec.require_placebos


class ShuffleLabelTrialTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        return _placebo_check(ctx, "shuffle_placebo")


class TimeShiftPlaceboTrialTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        return _placebo_check(ctx, "timeshift_placebo")


class AASplitVerificationTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        real = [r for r in ctx.trial_results if r.trial_kind == "real" and r.status == "ok"]
        cuts = {r.cut for r in real}
        seeds = {r.seed for r in real}
        passed = len(cuts) >= 2 or len(seeds) >= 2
        ctx.placebo_gate.setdefault("aa_split", {
            "passed": passed,
            "hard_gate": False,
            "reason": "alternate cut/seed evidence present" if passed else "needs more cuts/seeds",
            "n_cuts": len(cuts),
            "n_seeds": len(seeds),
        })
        if not passed and ctx.verdict is None:
            ctx.verdict = "needs_more_seeds"
        return True


class PlaceboVerdictTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        failed = {
            name: gate for name, gate in ctx.placebo_gate.items()
            if gate.get("hard_gate", True) and not gate.get("passed", False)
        }
        ctx.placebo_gate["thresholds"] = dict(GATE_THRESHOLDS)
        if failed:
            ctx.verdict = "invalid_experiment"
            return False
        return True


class AggregateResultsJob(Job):
    @property
    def tasks(self) -> list[Task]:
        return [
            LoadTrialResultsTask(),
            ValidateResultCompletenessTask(),
            AggregateByConfigTask(),
            AggregateByCutAndSeedTask(),
        ]


class LoadTrialResultsTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        if not ctx.trial_results:
            results = []
            for trial in ctx.trial_plan:
                path = trial.out_dir / "trial_result.json"
                if path.exists():
                    results.append(_trial_result_from_dict(_json_load(path)))
            ctx.trial_results = results
        return True


class ValidateResultCompletenessTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        result_ids = {r.trial_id for r in ctx.trial_results}
        missing = [t.trial_id for t in ctx.trial_plan if t.trial_id not in result_ids]
        failed = [r.trial_id for r in ctx.trial_results if r.status == "failed"]
        total = max(1, len(ctx.trial_plan))
        failure_ratio = (len(missing) + len(failed)) / total
        ctx.aggregate_results["completeness"] = {
            "planned": len(ctx.trial_plan),
            "completed": len(ctx.trial_results),
            "n_failed": len(failed),
            "n_missing": len(missing),
            "failed_trial_ids": failed,
            "missing_trial_ids": missing,
            "failure_ratio": failure_ratio,
        }
        if failure_ratio > 1 / 3:
            ctx.verdict = "invalid_experiment"
        return True


class AggregateByConfigTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        real_ok = [
            r for r in ctx.trial_results
            if r.trial_kind == "real" and r.status == "ok" and r.pooled_ic is not None
        ]
        by_config: dict[str, dict[str, Any]] = {}
        for config in sorted({r.config_name for r in real_ok}):
            vals = np.asarray([r.pooled_ic for r in real_ok if r.config_name == config], dtype=float)
            by_config[config] = {
                "n": int(vals.size),
                "mean_pooled_ic": float(vals.mean()) if vals.size else None,
                "std_pooled_ic": float(vals.std(ddof=1)) if vals.size > 1 else 0.0,
                "se_pooled_ic": float(vals.std(ddof=1) / math.sqrt(vals.size)) if vals.size > 1 else None,
                "positive_count": int((vals > 0).sum()) if vals.size else 0,
                "worst_cut_ic": float(vals.min()) if vals.size else None,
            }
        baseline = by_config.get(ctx.spec.baseline_config, {}).get("mean_pooled_ic")
        for config, stats in by_config.items():
            mean = stats.get("mean_pooled_ic")
            stats["mean_delta_vs_baseline"] = (
                float(mean - baseline) if mean is not None and baseline is not None else None
            )
        ctx.aggregate_results["by_config"] = by_config
        return True


class AggregateByCutAndSeedTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        rows = []
        for r in ctx.trial_results:
            if r.trial_kind == "real" and r.status == "ok":
                rows.append({
                    "config_name": r.config_name,
                    "cut": r.cut,
                    "seed": r.seed,
                    "pooled_ic": r.pooled_ic,
                    "min_regime_ic": r.min_regime_ic,
                })
        ctx.aggregate_results["by_cut_seed"] = rows
        return True


class AnalyzeResultsJob(Job):
    @property
    def tasks(self) -> list[Task]:
        return [
            CompareAgainstBaselineTask(),
            MultipleComparisonCorrectionTask(),
            RobustnessAndRiskTask(),
            DecideVerdictTask(),
        ]

    def should_skip(self, ctx: ExperimentContext) -> bool:
        return ctx.verdict == "invalid_experiment"


class CompareAgainstBaselineTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        by_config = ctx.aggregate_results.get("by_config", {})
        baseline = by_config.get(ctx.spec.baseline_config, {})
        ctx.analysis["baseline_config"] = ctx.spec.baseline_config
        ctx.analysis["baseline"] = baseline
        ctx.analysis["comparisons"] = {
            config: {
                "mean_delta_vs_baseline": stats.get("mean_delta_vs_baseline"),
                "positive_count": stats.get("positive_count"),
            }
            for config, stats in by_config.items()
            if config != ctx.spec.baseline_config
        }
        return True


class MultipleComparisonCorrectionTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        real_ok = [
            r for r in ctx.trial_results
            if r.trial_kind == "real" and r.status == "ok" and r.pooled_ic is not None
        ]
        best = _best_config(ctx)
        best_series = [r.pooled_ic for r in real_ok if r.config_name == best]
        n_trials = sum(1 for t in ctx.trial_plan if t.trial_kind == "real")
        matrix = _returns_matrix(real_ok)
        ctx.analysis["multiple_comparison"] = {
            "n_trials": n_trials,
            "best_config": best,
            "dsr": deflated_sharpe(best_series, n_trials=n_trials) if best_series else None,
            "pbo": pbo_cscv(matrix) if matrix is not None else None,
            "dsr_threshold": 0.5,
            "dsr_threshold_source": "doc/research/promotion-methodology.md Tier 3",
            "pbo_reject_threshold": 0.5,
        }
        return True


class RobustnessAndRiskTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        real_ok = [
            r for r in ctx.trial_results
            if r.trial_kind == "real" and r.status == "ok"
        ]
        non_defensive_by_config: dict[str, list[tuple[str, float]]] = {}
        for result in real_ok:
            for regime, ic in result.per_regime_ic.items():
                if (
                    regime in NON_DEFENSIVE_REGIMES
                    and ic is not None
                    and np.isfinite(float(ic))
                ):
                    non_defensive_by_config.setdefault(result.config_name, []).append(
                        (regime, float(ic))
                    )
        ctx.analysis["robustness"] = {
            "min_regime_ic_by_config": {
                config: min(r.min_regime_ic for r in real_ok if r.config_name == config)
                for config in sorted(
                    {
                        r.config_name
                        for r in real_ok
                        if r.min_regime_ic is not None
                    }
                )
            },
            "non_defensive_regimes": sorted(NON_DEFENSIVE_REGIMES),
            "min_non_defensive_regime_ic_by_config": {
                config: min(ic for _, ic in values)
                for config, values in sorted(non_defensive_by_config.items())
                if values
            },
            "negative_non_defensive_regimes_by_config": {
                config: {
                    regime: ic
                    for regime, ic in values
                    if ic < 0.0
                }
                for config, values in sorted(non_defensive_by_config.items())
                if any(ic < 0.0 for _, ic in values)
            },
        }
        return True


class DecideVerdictTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        if ctx.verdict in {"invalid_experiment", "needs_more_seeds"}:
            return True
        by_config = ctx.aggregate_results.get("by_config", {})
        best = _best_config(ctx)
        if best is None or best == ctx.spec.baseline_config:
            ctx.verdict = "reject"
            return True
        best_stats = by_config.get(best, {})
        delta = best_stats.get("mean_delta_vs_baseline")
        se = best_stats.get("se_pooled_ic")
        worst_cut_ic = best_stats.get("worst_cut_ic")
        multiple = ctx.analysis.get("multiple_comparison", {})
        robustness = ctx.analysis.get("robustness", {})
        min_non_defensive = robustness.get("min_non_defensive_regime_ic_by_config", {}).get(best)
        negative_non_defensive = robustness.get(
            "negative_non_defensive_regimes_by_config", {}
        ).get(best, {})

        # Per-regime evidence presence: empty dict (vs negative value) is
        # qualitatively different — it means no per-regime data was ever
        # available, not that all regimes are non-negative. PRIME DIRECTIVE
        # requires per-regime FIRST, so a "promote" verdict with no per-regime
        # numbers at all is meaningless. This typically happens when
        # `require_regime_contract=False` is paired with a missing/unloadable
        # spy_path — the safety net here catches that combination explicitly.
        non_defensive_map = robustness.get("min_non_defensive_regime_ic_by_config", {})
        has_non_defensive_evidence = best in non_defensive_map

        verdict_inputs = {
            "best_config": best,
            "phase": ctx.spec.phase,
            "delta_vs_baseline": delta,
            "se_pooled_ic": se,
            "required_delta_gt": (2.0 * se if se is not None else None),
            "worst_cut_ic": worst_cut_ic,
            "min_non_defensive_regime_ic": min_non_defensive,
            "has_non_defensive_evidence": has_non_defensive_evidence,
            "regime_contract_required": bool(ctx.spec.require_regime_contract),
            "negative_non_defensive_regimes": negative_non_defensive,
            "dsr": multiple.get("dsr"),
            "dsr_threshold": multiple.get("dsr_threshold", 0.5),
            "pbo": multiple.get("pbo"),
            "pbo_reject_threshold": multiple.get("pbo_reject_threshold", 0.5),
        }
        ctx.analysis["verdict_inputs"] = verdict_inputs

        if delta is None or not _is_finite_number(delta) or delta <= 0.0:
            ctx.verdict = "reject"
        elif (
            min_non_defensive is not None
            and _is_finite_number(min_non_defensive)
            and float(min_non_defensive) < 0.0
        ):
            ctx.verdict = "reject"
        elif not has_non_defensive_evidence:
            # PRIME DIRECTIVE safety net: a "promote" verdict requires at
            # minimum one non-defensive regime IC to gate on. Empty per-regime
            # evidence is a degraded run (typically `--no-regime-contract`
            # bypass + missing SPY path), not a passing one. Surface this as
            # `needs_more_seeds` so the operator knows to re-run with
            # regime labels.
            ctx.verdict = "needs_more_seeds"
            verdict_inputs["needs_more_seeds_reason"] = (
                "no per-regime evidence — verify spy_path is loadable and "
                "PerRegimeICCallback produces per-row regime in val_preds"
            )
        elif (
            worst_cut_ic is None
            or not _is_finite_number(worst_cut_ic)
            or float(worst_cut_ic) <= 0.0
        ):
            ctx.verdict = "reject"
        elif se is None or not _is_finite_number(se):
            ctx.verdict = "needs_more_seeds"
        elif float(delta) <= 2.0 * float(se):
            ctx.verdict = "needs_more_seeds"
        elif ctx.spec.phase != "confirm":
            ctx.verdict = "promote_to_confirm"
        elif _live_gate_passed(multiple):
            ctx.verdict = "promote_to_live"
        else:
            ctx.verdict = "reject"
        verdict_inputs["verdict"] = ctx.verdict
        return True


class PersistResultsJob(Job):
    @property
    def tasks(self) -> list[Task]:
        return [WriteJsonArtifactsTask(), WriteMarkdownReportTask()]


class WriteJsonArtifactsTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        root = ctx.experiment_dir
        if root is None:
            raise ValueError("experiment_dir missing")
        _write_json(root / "experiment_spec.json", _json_safe(asdict(ctx.spec)))
        _write_json(root / "environment.json", _json_safe(ctx.environment))
        _write_json(root / "regime_contract.json", _json_safe(ctx.regime_contract))
        _write_json(root / "trial_plan.json", [_trial_spec_payload(t) for t in ctx.trial_plan])
        with (root / "trial_results.jsonl").open("w", encoding="utf-8") as fh:
            for result in ctx.trial_results:
                fh.write(json.dumps(_json_safe(asdict(result)), sort_keys=True) + "\n")
        _write_json(root / "placebo_gate.json", _json_safe(ctx.placebo_gate))
        _write_json(root / "aggregate_results.json", _json_safe(ctx.aggregate_results))
        if ctx.verdict == "invalid_experiment":
            _write_json(
                root / "invalid_experiment.json",
                {
                    "verdict": ctx.verdict,
                    "placebo_gate": ctx.placebo_gate,
                    "completeness": ctx.aggregate_results.get("completeness", {}),
                    "regime_contract": ctx.regime_contract,
                },
            )
        elif not ctx.spec.allow_ungated_smoke:
            _write_json(root / "analysis.json", _json_safe({**ctx.analysis, "verdict": ctx.verdict}))
        return True


class WriteMarkdownReportTask(Task):
    def run(self, ctx: ExperimentContext) -> bool | None:
        root = ctx.experiment_dir
        if root is None:
            raise ValueError("experiment_dir missing")
        if ctx.spec.allow_ungated_smoke:
            path = root / "smoke_report.md"
            text = (
                "# PatchTST Smoke Run\n\n"
                "WARNING: NO SANITY GATES - DO NOT USE FOR DECISIONS.\n\n"
                f"Planned trials: {len(ctx.trial_plan)}\n"
                f"Completed trials: {len(ctx.trial_results)}\n"
            )
            path.write_text(text, encoding="utf-8")
            return True
        if ctx.verdict == "invalid_experiment":
            return True
        completeness = ctx.aggregate_results.get("completeness", {})
        lines = [
            "# PatchTST Research Report",
            "",
            f"Verdict: `{ctx.verdict}`",
            "",
            "## Completeness",
            "",
            f"- planned: {completeness.get('planned', 0)}",
            f"- completed: {completeness.get('completed', 0)}",
            f"- n_failed: {completeness.get('n_failed', 0)}",
            f"- n_missing: {completeness.get('n_missing', 0)}",
            "",
            "## Config Summary",
            "",
            "| config | n | mean pooled IC | delta vs baseline | positive |",
            "|---|---:|---:|---:|---:|",
        ]
        for config, stats in sorted(ctx.aggregate_results.get("by_config", {}).items()):
            lines.append(
                f"| {config} | {stats.get('n')} | {_fmt(stats.get('mean_pooled_ic'))} | "
                f"{_fmt(stats.get('mean_delta_vs_baseline'))} | {stats.get('positive_count')} |"
            )
        lines.append("")
        lines.append("## Gate Summary")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(_json_safe(ctx.placebo_gate), indent=2, sort_keys=True))
        lines.append("```")
        (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True


def check_promotion(experiment_dir: Path) -> int:
    analysis = experiment_dir / "analysis.json"
    invalid = experiment_dir / "invalid_experiment.json"
    if invalid.exists():
        return 2
    if not analysis.exists():
        return 3
    try:
        verdict = _json_load(analysis).get("verdict")
    except Exception:
        return 3
    if verdict in {"promote_to_confirm", "promote_to_live"}:
        return 0
    if verdict in {"needs_more_seeds", "reject"}:
        return 1
    if verdict == "invalid_experiment":
        return 2
    return 3


def _is_finite_number(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _live_gate_passed(multiple: dict[str, Any]) -> bool:
    dsr = multiple.get("dsr")
    pbo = multiple.get("pbo")
    dsr_threshold = float(multiple.get("dsr_threshold", 0.5))
    pbo_threshold = float(multiple.get("pbo_reject_threshold", 0.5))
    dsr_passed = _is_finite_number(dsr) and float(dsr) > dsr_threshold
    pbo_passed = _is_finite_number(pbo) and float(pbo) < pbo_threshold
    return bool(dsr_passed or pbo_passed)


def _trial_argv(
    spec: ExperimentSpec,
    extra: list[str],
    cut: str,
    seed: int,
    out_dir: Path,
    kind: TrialKind,
) -> list[str]:
    argv = [
        "--cut", cut,
        "--seed", str(seed),
        "--epochs", str(spec.epochs),
        "--device", spec.device if spec.device != "auto" else "cpu",
        "--output-dir", str(out_dir),
        "--dataset", str(spec.dataset),
        "--label", spec.label_col,
        "--embargo-days", str(spec.embargo_days),
        "--val-tail-pct", str(spec.val_tail_pct),
    ] + list(extra)
    if spec.strategy_config is not None:
        argv += ["--strategy-config", str(spec.strategy_config)]
    if kind == "shuffle_placebo":
        argv.append("--shuffle-labels")
    elif kind == "timeshift_placebo":
        argv += ["--label-shift-days", str(spec.label_shift_days)]
    return argv


def _placebo_check(ctx: ExperimentContext, kind: TrialKind) -> bool | None:
    real = [
        r for r in ctx.trial_results
        if r.trial_kind == "real" and r.status == "ok" and r.pooled_ic is not None
    ]
    placebo = [
        r for r in ctx.trial_results
        if r.trial_kind == kind and r.status == "ok" and r.pooled_ic is not None
    ]
    real_mean = float(np.mean([r.pooled_ic for r in real])) if real else float("nan")
    pl_mean = float(np.mean([r.pooled_ic for r in placebo])) if placebo else float("nan")
    if kind == "shuffle_placebo":
        threshold = max(
            GATE_THRESHOLDS["shuffle_abs_ic"],
            GATE_THRESHOLDS["shuffle_real_fraction"] * abs(real_mean),
        )
    else:
        threshold = max(
            GATE_THRESHOLDS["timeshift_abs_ic"],
            GATE_THRESHOLDS["timeshift_real_fraction"] * abs(real_mean),
        )
    passed = bool(np.isfinite(pl_mean) and abs(pl_mean) <= threshold)
    ctx.placebo_gate[kind] = {
        "passed": passed,
        "hard_gate": True,
        "real_ic_mean": real_mean,
        "placebo_ic_mean": pl_mean,
        "threshold": threshold,
        "n_real": len(real),
        "n_placebo": len(placebo),
    }
    return True


def _daily_ic(df: pd.DataFrame) -> list[float]:
    out: list[float] = []
    for _, group in df.groupby("date", sort=True):
        if len(group) < 2:
            continue
        x = group["model_score"].to_numpy(dtype=float)
        y = group["label"].to_numpy(dtype=float)
        if np.nanstd(x) < 1e-12 or np.nanstd(y) < 1e-12:
            continue
        rho, _ = spearmanr(x, y)
        if np.isfinite(rho):
            out.append(float(rho))
    return out


def _load_regime_labels(ctx: ExperimentContext) -> pd.DataFrame | None:
    if not ctx.regime_contract.get("passed"):
        return None
    if not ctx.spec.spy_path.exists():
        return None
    from renquant_common.hmm_regime_labels import compute_hmm_regime_labels  # noqa: PLC0415

    return compute_hmm_regime_labels(ctx.spec.spy_path)


def _assign_split(
    panel: pd.DataFrame,
    cut_name: str,
    embargo_days: int,
    *,
    val_tail_pct: float = DEFAULT_ALL_VAL_TAIL_PCT,
) -> pd.Series:
    return assign_patchtst_split(
        panel,
        cut_name,
        embargo_days=embargo_days,
        val_tail_pct=val_tail_pct,
    )


def _read_panel_dates(dataset: Path, label_col: str) -> pd.DataFrame:
    try:
        panel = pd.read_parquet(dataset, columns=["date", "ticker", label_col])
    except Exception:
        panel = pd.read_parquet(dataset)
    if "date" not in panel.columns:
        raise ValueError("dataset missing date column")
    return panel.dropna(subset=[label_col]).copy() if label_col in panel.columns else panel.copy()


def _failed_result(ctx: TrialContext, exc: Exception) -> TrialResult:
    elapsed = time.monotonic() - ctx.started_at if ctx.started_at is not None else None
    return TrialResult(
        trial_id=ctx.spec.trial_id,
        status="failed",
        trial_kind=ctx.spec.trial_kind,
        config_name=ctx.spec.config_name,
        cut=ctx.spec.cut,
        seed=ctx.spec.seed,
        pooled_ic=None,
        daily_ic_mean=None,
        daily_ic_std=None,
        positive_day_ratio=None,
        min_regime_ic=None,
        per_regime_ic={},
        n_dates=0,
        n_rows=0,
        elapsed_sec=elapsed,
        device=ctx.experiment.execution_plan.device if ctx.experiment.execution_plan else "",
        git_head=ctx.experiment.environment.get("git_head"),
        fingerprint=ctx.spec.fingerprint,
        error_class=type(exc).__name__,
        error=str(exc)[:500],
        artifacts={},
    )


def _persist_trial_result(ctx: TrialContext) -> None:
    if ctx.result is None:
        raise ValueError("trial result missing")
    _write_json(ctx.spec.out_dir / "trial_result.json", _json_safe(asdict(ctx.result)))


def _trial_result_from_dict(payload: dict[str, Any]) -> TrialResult:
    return TrialResult(**payload)


def _trial_spec_payload(trial: TrialSpec) -> dict[str, Any]:
    payload = asdict(trial)
    for key in ("out_dir", "val_preds_path", "summary_path"):
        payload[key] = str(payload[key])
    return payload


def _best_config(ctx: ExperimentContext) -> str | None:
    by_config = ctx.aggregate_results.get("by_config", {})
    if not by_config:
        return None
    ranked = [
        (name, stats.get("mean_pooled_ic"))
        for name, stats in by_config.items()
        if stats.get("mean_pooled_ic") is not None
    ]
    if not ranked:
        return None
    return max(ranked, key=lambda item: item[1])[0]


def _returns_matrix(results: list[TrialResult]) -> np.ndarray | None:
    configs = sorted({r.config_name for r in results})
    observations = sorted({(r.cut, r.seed) for r in results})
    if len(configs) < 2 or len(observations) < 4:
        return None
    lookup = {(r.config_name, r.cut, r.seed): r.pooled_ic for r in results}
    matrix = np.full((len(configs), len(observations)), np.nan)
    for i, config in enumerate(configs):
        for j, (cut, seed) in enumerate(observations):
            value = lookup.get((config, cut, seed))
            if value is not None:
                matrix[i, j] = value
    if np.isnan(matrix).any():
        return None
    return matrix


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    return "cpu"


def _trial_id(config_name: str, cut: str, seed: int, kind: TrialKind) -> str:
    raw = f"{config_name}_{cut}_s{seed}_{kind}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):+.4f}"
    except Exception:
        return str(value)


def _file_fingerprint(path: Path | None) -> str | None:
    if path is None or not path.exists() or path.is_dir():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _git_state() -> tuple[str | None, bool | None]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip())
        return head or None, dirty
    except Exception:
        return None, None


def _short_hash(payload: Any) -> str:
    return _hash_json(payload)[:12]


def _hash_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


__all__ = [
    "ExperimentContext",
    "ExperimentSpec",
    "ExecutionPlan",
    "TrialResult",
    "TrialSpec",
    "build_experiment_pipeline",
    "check_promotion",
    "run_experiment",
]
