from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_common.stats import deflated_sharpe, pbo_cscv
from renquant_model_patchtst.research_pipeline import (
    BuildExecutionPlanTask,
    DecideVerdictTask,
    ExperimentContext,
    ExperimentSpec,
    FingerprintTrialsTask,
    MultipleComparisonCorrectionTask,
    RobustnessAndRiskTask,
    TrialResult,
    TrialSpec,
    _assign_split,
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
    p.add_argument("--val-tail-pct", type=float, default=0.10)
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
    baseline_pred = [0.0, 1.0, 2.0, 4.0, 3.0]
    is_baseline = out.name.startswith("B_tuned")
    for d in dates:
        for i in range(5):
            label = float(i)
            if args.shuffle_labels or args.label_shift_days:
                pred = placebo_pred[i]
            elif is_baseline:
                pred = baseline_pred[i]
            else:
                pred = label
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
    assert aggregate["by_config"]["B_tuned"]["mean_pooled_ic"] == pytest.approx(0.9)
    assert ctx.environment["splitter_contract"]["implementation"].endswith("assign_split_column")
    trial_fp = json.loads((ctx.trial_plan[0].out_dir / "trial_fingerprint.json").read_text())
    assert trial_fp["splitter_contract"]["embargo_days"] == 5


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


def test_all_cut_split_uses_canonical_embargo_boundary(tmp_path: Path) -> None:
    panel = pd.read_parquet(_dataset(tmp_path, n_dates=40))

    split = _assign_split(panel, "all", embargo_days=5, val_tail_pct=0.25)

    dates = pd.to_datetime(panel["date"])
    val_dates = dates[split == "val"]
    train_dates = dates[split == "train"]
    embargo_dates = dates[split == "embargo"]
    assert val_dates.nunique() == 10
    assert not train_dates.empty
    assert not embargo_dates.empty
    assert train_dates.max() + pd.offsets.BDay(5) < val_dates.min()
    assert embargo_dates.min() >= val_dates.min() - pd.offsets.BDay(5)
    assert embargo_dates.max() < val_dates.min()


def _trial_spec(tmp_path: Path, config: str, cut: str, seed: int) -> TrialSpec:
    out_dir = tmp_path / f"{config}_{cut}_{seed}"
    return TrialSpec(
        trial_id=f"{config}_{cut}_{seed}",
        config_name=config,
        cut=cut,
        seed=seed,
        trial_kind="real",
        argv=[],
        out_dir=out_dir,
        val_preds_path=out_dir / "preds.parquet",
        summary_path=out_dir / "summary.json",
    )


def _trial_result(
    config: str,
    cut: str,
    seed: int,
    pooled_ic: float,
    *,
    per_regime_ic: dict[str, float] | None = None,
) -> TrialResult:
    per_regime_ic = per_regime_ic or {"BULL_CALM": pooled_ic, "BEAR": pooled_ic}
    return TrialResult(
        trial_id=f"{config}_{cut}_{seed}",
        status="ok",
        trial_kind="real",
        config_name=config,
        cut=cut,
        seed=seed,
        pooled_ic=pooled_ic,
        daily_ic_mean=pooled_ic,
        daily_ic_std=0.01,
        positive_day_ratio=1.0,
        min_regime_ic=min(per_regime_ic.values()),
        per_regime_ic=per_regime_ic,
        n_dates=5,
        n_rows=25,
        elapsed_sec=1.0,
        device="cpu",
        git_head=None,
        fingerprint="",
        error_class=None,
        error=None,
        artifacts={},
    )


def test_multiple_comparison_counts_trial_cells_and_matches_fixture(tmp_path: Path) -> None:
    cuts = ["cut_a", "cut_b"]
    seeds = [1, 2]
    ctx = ExperimentContext(spec=_spec(tmp_path, require_placebos=False))
    ctx.trial_plan = [
        _trial_spec(tmp_path, config, cut, seed)
        for config in ["B_tuned", "C_xstock"]
        for cut in cuts
        for seed in seeds
    ]
    baseline = [0.01, 0.02, 0.015, 0.01]
    candidate = [0.05, 0.04, 0.06, 0.03]
    ctx.trial_results = [
        _trial_result("B_tuned", cut, seed, value)
        for (cut, seed), value in zip([(c, s) for c in cuts for s in seeds], baseline)
    ] + [
        _trial_result("C_xstock", cut, seed, value)
        for (cut, seed), value in zip([(c, s) for c in cuts for s in seeds], candidate)
    ]
    ctx.aggregate_results["by_config"] = {
        "B_tuned": {"mean_pooled_ic": float(np.mean(baseline))},
        "C_xstock": {"mean_pooled_ic": float(np.mean(candidate))},
    }

    MultipleComparisonCorrectionTask().run(ctx)

    mc = ctx.analysis["multiple_comparison"]
    matrix = np.asarray([baseline, candidate], dtype=float)
    assert mc["n_trials"] == 8
    assert mc["dsr"] == pytest.approx(deflated_sharpe(candidate, n_trials=8))
    assert mc["pbo"] == pytest.approx(pbo_cscv(matrix))


def _verdict_context(
    tmp_path: Path,
    *,
    phase: str = "confirm",
    delta: float = 0.06,
    se: float | None = 0.02,
    worst_cut_ic: float = 0.01,
    dsr: float | None = 0.7,
    pbo: float | None = 0.3,
    min_non_defensive: float | None = 0.01,
) -> ExperimentContext:
    ctx = ExperimentContext(spec=_spec(tmp_path, phase=phase, require_placebos=False))
    ctx.aggregate_results["by_config"] = {
        "B_tuned": {
            "n": 4,
            "mean_pooled_ic": 0.01,
            "se_pooled_ic": se,
            "worst_cut_ic": 0.01,
            "mean_delta_vs_baseline": 0.0,
            "positive_count": 4,
        },
        "C_xstock": {
            "n": 4,
            "mean_pooled_ic": 0.01 + delta,
            "se_pooled_ic": se,
            "worst_cut_ic": worst_cut_ic,
            "mean_delta_vs_baseline": delta,
            "positive_count": 4,
        },
    }
    ctx.analysis["multiple_comparison"] = {
        "dsr": dsr,
        "pbo": pbo,
        "dsr_threshold": 0.5,
        "pbo_reject_threshold": 0.5,
    }
    ctx.analysis["robustness"] = {
        "min_non_defensive_regime_ic_by_config": (
            {"C_xstock": min_non_defensive}
            if min_non_defensive is not None
            else {}
        ),
        "negative_non_defensive_regimes_by_config": (
            {"C_xstock": {"BULL_CALM": min_non_defensive}}
            if min_non_defensive is not None and min_non_defensive < 0
            else {}
        ),
    }
    return ctx


@pytest.mark.parametrize(
    ("dsr", "pbo", "expected"),
    [
        (0.7, 0.3, "promote_to_live"),
        (0.1, 0.9, "reject"),
    ],
)
def test_decide_verdict_consumes_dsr_pbo_for_live_gate(
    tmp_path: Path,
    dsr: float,
    pbo: float,
    expected: str,
) -> None:
    ctx = _verdict_context(tmp_path, dsr=dsr, pbo=pbo)

    DecideVerdictTask().run(ctx)

    assert ctx.verdict == expected


def test_decide_verdict_rejects_negative_non_defensive_regime(tmp_path: Path) -> None:
    ctx = _verdict_context(tmp_path, min_non_defensive=-0.01)

    DecideVerdictTask().run(ctx)

    assert ctx.verdict == "reject"


def test_decide_verdict_promotes_confirm_only_after_two_se(tmp_path: Path) -> None:
    strong = _verdict_context(tmp_path, phase="range_find", delta=0.06, se=0.02)
    weak = _verdict_context(tmp_path, phase="range_find", delta=0.03, se=0.02)

    DecideVerdictTask().run(strong)
    DecideVerdictTask().run(weak)

    assert strong.verdict == "promote_to_confirm"
    assert weak.verdict == "needs_more_seeds"


def test_robustness_task_feeds_negative_regime_into_verdict(tmp_path: Path) -> None:
    ctx = _verdict_context(tmp_path)
    ctx.trial_results = [
        _trial_result(
            "C_xstock",
            "all",
            42,
            0.04,
            per_regime_ic={"BULL_CALM": -0.02, "BEAR": -0.10},
        )
    ]

    RobustnessAndRiskTask().run(ctx)
    DecideVerdictTask().run(ctx)

    min_non_defensive = ctx.analysis["robustness"][
        "min_non_defensive_regime_ic_by_config"
    ]["C_xstock"]
    assert min_non_defensive < 0
    assert ctx.verdict == "reject"


# --- PR #8 follow-up findings -----------------------------------------------
#
# Finding 1 (HIGH) — `--no-regime-contract` paired with missing SPY produced
# empty `min_non_defensive_regime_ic_by_config`. Pre-fix, DecideVerdictTask
# would then SKIP the negative-regime check and could promote on DSR/PBO with
# zero per-regime evidence (PRIME DIRECTIVE violation).
#
# Finding 2 (LOW) — `require_regime_contract` was not stamped into
# `environment.json`; downstream audit dashboards couldn't tell which runs
# ran with the bypass.


def test_decide_verdict_needs_more_seeds_when_no_per_regime_evidence(
    tmp_path: Path,
) -> None:
    """PRIME DIRECTIVE safety net: an empty per-regime evidence dict must
    NOT promote even when delta/se/DSR/PBO all look strong. Pre-fix the
    verdict went straight to promote_to_live; post-fix it goes to
    needs_more_seeds with an explicit reason."""
    ctx = _verdict_context(
        tmp_path,
        phase="confirm",
        delta=0.06,
        se=0.02,
        worst_cut_ic=0.01,
        dsr=0.7,        # would normally pass Tier-3 live gate
        pbo=0.3,
        min_non_defensive=None,  # ← empty robustness dict
    )

    DecideVerdictTask().run(ctx)

    assert ctx.verdict == "needs_more_seeds", (
        "no per-regime evidence MUST NOT promote, even with strong DSR/PBO/delta"
    )
    vi = ctx.analysis["verdict_inputs"]
    assert vi["has_non_defensive_evidence"] is False
    assert "needs_more_seeds_reason" in vi
    assert "per-regime evidence" in vi["needs_more_seeds_reason"]


def test_decide_verdict_keeps_strong_promote_when_evidence_present(
    tmp_path: Path,
) -> None:
    """Sanity: the safety net does NOT degrade a run that does have evidence."""
    ctx = _verdict_context(
        tmp_path,
        phase="confirm",
        delta=0.06,
        se=0.02,
        worst_cut_ic=0.01,
        dsr=0.7,
        pbo=0.3,
        min_non_defensive=0.02,  # positive evidence
    )

    DecideVerdictTask().run(ctx)

    assert ctx.verdict == "promote_to_live"
    assert ctx.analysis["verdict_inputs"]["has_non_defensive_evidence"] is True


def test_environment_stamps_require_regime_contract(tmp_path: Path) -> None:
    """The CLI bypass flag MUST appear in environment.json so downstream
    audit dashboards can attribute degraded runs to the operator opt-in.
    Reviewer Finding 2."""
    from renquant_model_patchtst.research_pipeline import StampEnvironmentTask

    # Bypass run
    ctx_bypass = ExperimentContext(spec=_spec(tmp_path, require_regime_contract=False))
    StampEnvironmentTask().run(ctx_bypass)
    assert ctx_bypass.environment["require_regime_contract"] is False

    # Strict run
    ctx_strict = ExperimentContext(spec=_spec(tmp_path, require_regime_contract=True))
    StampEnvironmentTask().run(ctx_strict)
    assert ctx_strict.environment["require_regime_contract"] is True

    # Sibling switches also stamped for full audit
    for ctx in (ctx_bypass, ctx_strict):
        assert "require_placebos" in ctx.environment
        assert "allow_ungated_smoke" in ctx.environment


def test_splitter_contract_is_part_of_trial_fingerprint(tmp_path: Path) -> None:
    spec = _spec(tmp_path, configs=["B_tuned"], require_placebos=False)
    trial_a = _trial_spec(tmp_path, "B_tuned", "all", 42)
    trial_b = _trial_spec(tmp_path, "B_tuned", "all", 42)
    ctx_a = ExperimentContext(spec=spec, trial_plan=[trial_a])
    ctx_b = ExperimentContext(spec=spec, trial_plan=[trial_b])
    ctx_a.environment["splitter_contract"] = {
        "implementation": "renquant_common.walk_forward_splits.assign_split_column",
        "embargo_days": 5,
        "lookahead_days": 5,
    }
    ctx_b.environment["splitter_contract"] = {
        "implementation": "renquant_common.walk_forward_splits.assign_split_column",
        "embargo_days": 10,
        "lookahead_days": 5,
    }

    FingerprintTrialsTask().run(ctx_a)
    FingerprintTrialsTask().run(ctx_b)

    assert trial_a.fingerprint != trial_b.fingerprint


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
