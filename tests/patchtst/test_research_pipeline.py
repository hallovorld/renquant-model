from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pytest

from renquant_model_patchtst.research_pipeline import (
    BuildExecutionPlanTask,
    ExperimentContext,
    ExperimentSpec,
    check_promotion,
    run_experiment,
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--cut")
    p.add_argument("--seed", type=int)
    p.add_argument("--epochs", type=int)
    p.add_argument("--device")
    p.add_argument("--output-dir")
    p.add_argument("--dataset")
    p.add_argument("--label", default="fwd_60d_excess")
    p.add_argument("--embargo-days", type=int, default=5)
    p.add_argument("--strategy-config")
    p.add_argument("--shuffle-labels", action="store_true")
    p.add_argument("--label-shift-days", type=int, default=0)
    p.add_argument("--film-regime-cond", action="store_true")
    p.add_argument("--spy-path")
    p.add_argument("--exclude-features")
    return p


def _dataset(path: Path, n_dates: int = 80) -> Path:
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    rows = []
    for d in dates:
        for i in range(5):
            rows.append({
                "date": d,
                "ticker": f"T{i}",
                "feature": float(i),
                "fwd_60d_excess": float(i),
            })
    out = path / "panel.parquet"
    pd.DataFrame(rows).to_parquet(out, index=False)
    return out


def _spec(tmp_path: Path, **overrides) -> ExperimentSpec:
    dataset = overrides.pop("dataset", _dataset(tmp_path))
    params = {
        "phase": "range_find",
        "configs": ["B_tuned", "C_xstock"],
        "cuts": ["all"],
        "seeds": [42],
        "epochs": 1,
        "dataset": dataset,
        "spy_path": tmp_path / "spy.parquet",
        "data_dir": tmp_path,
        "strategy_config": None,
        "out_dir": tmp_path / "out",
        "device": "cpu",
        "scheduler": "linear",
        "config_args": {"B_tuned": [], "C_xstock": []},
        "require_regime_contract": False,
        "label_lookahead_days": 5,
        "embargo_days": 5,
    }
    params.update(overrides)
    return ExperimentSpec(**params)


def _trainer(args: argparse.Namespace) -> dict:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    placebo_pred = [1.0, 4.0, 2.0, 0.0, 3.0]
    for d in dates:
        for i in range(5):
            label = float(i)
            pred = placebo_pred[i] if args.shuffle_labels or args.label_shift_days else label
            rows.append({"date": d, "ticker": f"T{i}", "pred": pred, "label": label})
    pred_path = out / f"hf_patchtst_{args.cut}_seed{args.seed}_val_preds.parquet"
    summary_path = out / f"hf_patchtst_{args.cut}_seed{args.seed}_summary.json"
    pd.DataFrame(rows).to_parquet(pred_path, index=False)
    summary = {"val_preds_path": str(pred_path), "best_val_ic": 1.0}
    summary_path.write_text(json.dumps(summary))
    return summary


def test_pipeline_runs_gated_experiment_and_persists_report(tmp_path: Path) -> None:
    ctx = run_experiment(_spec(tmp_path), trainer_runner=_trainer, parser_builder=_parser)

    assert ctx.verdict == "needs_more_seeds"
    assert len(ctx.trial_plan) == 6
    assert ctx.placebo_gate["shuffle_placebo"]["passed"] is True
    assert ctx.placebo_gate["timeshift_placebo"]["passed"] is True
    assert (ctx.experiment_dir / "analysis.json").exists()
    assert (ctx.experiment_dir / "report.md").exists()
    aggregate = json.loads((ctx.experiment_dir / "aggregate_results.json").read_text())
    assert aggregate["completeness"]["n_failed"] == 0
    assert aggregate["by_config"]["B_tuned"]["mean_pooled_ic"] == pytest.approx(1.0)


def test_splitter_embargo_failure_blocks_planning(tmp_path: Path) -> None:
    spec = _spec(tmp_path, configs=["B_tuned"], require_placebos=False, embargo_days=1)

    with pytest.raises(ValueError, match="splitter embargo invariant failed"):
        run_experiment(spec, trainer_runner=_trainer, parser_builder=_parser)


def test_scheduler_mps_stays_linear(tmp_path: Path) -> None:
    ctx = ExperimentContext(
        spec=_spec(tmp_path, configs=["B_tuned"], require_placebos=False, device="mps")
    )
    ctx.trial_plan = [object(), object()]  # only count matters for this task

    BuildExecutionPlanTask().run(ctx)

    assert ctx.execution_plan.mode == "linear"
    assert ctx.execution_plan.max_workers == 1


def test_trial_failure_is_persisted_and_check_promotion_returns_invalid(tmp_path: Path) -> None:
    def failing_trainer(args: argparse.Namespace) -> dict:
        raise RuntimeError("boom")

    ctx = run_experiment(
        _spec(tmp_path, configs=["B_tuned"], require_placebos=False, allow_ungated_smoke=True),
        trainer_runner=failing_trainer,
        parser_builder=_parser,
    )

    result_path = ctx.trial_plan[0].out_dir / "trial_result.json"
    result = json.loads(result_path.read_text())
    assert result["status"] == "failed"
    assert result["error_class"] == "RuntimeError"
    assert check_promotion(ctx.experiment_dir) == 2
