#!/usr/bin/env python
"""Linear-baseline research CLI — DLinear / NLinear via ExperimentPipeline.

Mirrors the shape of ``renquant_model_patchtst.research`` so the same
research-plan machinery (placebos, regime contract, DSR/PBO, promotion
tiers) applies to the linear baselines. Per the merged research plan
§"P1 Low-Cost Decision Baselines": if a linear model beats PatchTST under
the same splits + placebos + per-regime gates, the PatchTST investment
should pause.

Usage::

    python -m renquant_model_linear.research \
        --phase range_find --model dlinear \
        --cuts cut1_covid --seeds 42,43 --epochs 4 \
        --dataset tests/data/smoke_panel.parquet \
        --spy-path tests/data/smoke_spy.parquet \
        --out-dir artifacts/linear_research \
        --label fwd_5d_excess --val-tail-pct 0.15 --embargo-days 5
"""
from __future__ import annotations

import argparse
from pathlib import Path

from renquant_common.hmm_regime_labels import (
    DETECTOR_VERSION_LEGACY,
    DETECTOR_VERSION_V20260531,
)
from renquant_model_patchtst.research_pipeline import (
    ExperimentSpec,
    check_promotion,
    run_experiment,
)

from . import trainer as linear_trainer

# Cut names are decided by renquant_common's walk-forward split machinery.
# For smoke runs against the synthetic fixture, use `--cuts all`.
DEFAULT_CUTS = ["cut1_covid", "cut2_fed", "cut3_inflpk", "cut4_svb", "cut5_unwind"]

_LINEAR_CONFIG_TUNED: list[str] = [
    "--lr", "1e-3",
    "--weight-decay", "0.0",
    "--seq-len", "24",
    "--early-stopping-patience", "2",
]


def configs() -> dict[str, list[str]]:
    """Linear-baseline configurations, in the same shape as patchtst.research.
    Each maps to a set of CLI args appended to the trainer invocation.

    Naming convention: the canonical ``L_dlinear`` runs the trainer default
    ``--kernel-size 25`` (matches pinned upstream LTSF-Linear) so the
    primary falsification baseline is the same DLinear hypothesis the
    paper measures. Smaller-kernel variants are named ``L_dlinear_k<N>``
    so experiment labels stay scientifically honest — a ``--configs
    L_dlinear`` run is upstream-faithful; ``L_dlinear_k5`` / ``L_dlinear_k3``
    are explicit ablations.
    """
    return {
        # Upstream-faithful DLinear (kernel=25 default from trainer). The
        # primary falsification baseline per the merged plan.
        "L_dlinear":     _LINEAR_CONFIG_TUNED + ["--model", "dlinear"],
        "L_nlinear":     _LINEAR_CONFIG_TUNED + ["--model", "nlinear"],
        # Smaller-kernel ablations — useful when seq_len is short
        # (kernel_size=25 over seq_len=10 over-smooths the trend).
        "L_dlinear_k5":  _LINEAR_CONFIG_TUNED + ["--model", "dlinear", "--kernel-size", "5"],
        "L_dlinear_k3":  _LINEAR_CONFIG_TUNED + ["--model", "dlinear", "--kernel-size", "3"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", default="range_find",
                   help="range_find/doe/confirm or 0/1/2")
    p.add_argument("--configs", default=None,
                   help="comma list of linear configs (default: all)")
    p.add_argument("--cuts", default=None, help="comma list (default: all 5)")
    p.add_argument("--seeds", default="42",
                   help="comma list (confirm phase typically: 42,43,44,45,46)")
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--device", default="cpu",
                   choices=["auto", "cpu", "mps", "cuda"],
                   help="Linear models run fast on CPU; MPS gives no real "
                        "speedup for such small parameter counts.")
    p.add_argument("--scheduler", default="auto",
                   choices=["auto", "linear", "parallel"])
    p.add_argument("--max-workers", type=int, default=None)
    p.add_argument("--data-dir", default="data")
    p.add_argument("--dataset", default="data/transformer_v4_wl200_clean.parquet")
    p.add_argument("--spy-path", default="data/ohlcv/SPY/1d.parquet")
    p.add_argument("--strategy-config", default=None)
    p.add_argument("--out-dir", default="artifacts/linear_research")
    p.add_argument("--out", default=None,
                   help="legacy alias; parent directory is used")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--fail-fast", action="store_true")
    p.add_argument("--no-placebos", action="store_true")
    p.add_argument("--allow-ungated-smoke", action="store_true")
    p.add_argument("--no-regime-contract", action="store_true",
                   help="Bypass RegimeDetectorContractTask (smoke/detector-debug only).")
    p.add_argument("--detector-version",
                   default=DETECTOR_VERSION_V20260531,
                   choices=[DETECTOR_VERSION_LEGACY, DETECTOR_VERSION_V20260531])
    p.add_argument("--label", default="fwd_60d_excess")
    p.add_argument("--label-lookahead-days", type=int, default=60)
    p.add_argument("--embargo-days", type=int, default=60)
    p.add_argument("--val-tail-pct", type=float, default=0.10)
    p.add_argument("--label-shift-days", type=int, default=10)
    p.add_argument("--baseline-pooled-ic", type=float, default=None)
    p.add_argument("--baseline-config", default="L_dlinear",
                   help="Linear baseline to compare candidate configs against. "
                        "Defaults to DLinear since it's the canonical linear "
                        "falsification baseline.")
    p.add_argument("--check-promotion", default=None,
                   help="load experiment dir and return 0/1/2/3")
    args = p.parse_args(argv)

    if args.check_promotion:
        return check_promotion(Path(args.check_promotion))

    phase = _parse_phase(args.phase)
    all_configs = configs()
    selected_configs = (args.configs.split(",") if args.configs
                        else list(all_configs))
    cuts = args.cuts.split(",") if args.cuts else DEFAULT_CUTS
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    out_dir = Path(args.out).parent if args.out else Path(args.out_dir)
    config_args = {name: all_configs[name] for name in selected_configs}

    spec = ExperimentSpec(
        phase=phase,
        configs=selected_configs,
        cuts=cuts,
        seeds=seeds,
        epochs=args.epochs,
        dataset=Path(args.dataset),
        spy_path=Path(args.spy_path),
        data_dir=Path(args.data_dir),
        strategy_config=Path(args.strategy_config) if args.strategy_config else None,
        out_dir=out_dir,
        device=args.device,
        scheduler=args.scheduler,
        config_args=config_args,
        max_workers=args.max_workers,
        resume=not args.no_resume,
        fail_fast=args.fail_fast,
        require_placebos=not args.no_placebos,
        allow_ungated_smoke=args.allow_ungated_smoke,
        require_regime_contract=not args.no_regime_contract,
        detector_version=args.detector_version,
        label_col=args.label,
        label_lookahead_days=args.label_lookahead_days,
        embargo_days=args.embargo_days,
        val_tail_pct=args.val_tail_pct,
        label_shift_days=args.label_shift_days,
        baseline_pooled_ic=args.baseline_pooled_ic,
        baseline_config=args.baseline_config,
    )
    ctx = run_experiment(
        spec,
        trainer_runner=linear_trainer.train_single_run,
        parser_builder=linear_trainer.build_parser,
    )
    print(
        f"Linear research done: verdict={ctx.verdict} "
        f"experiment_dir={ctx.experiment_dir}",
        flush=True,
    )
    return 2 if ctx.verdict == "invalid_experiment" else 0


def _parse_phase(raw: str) -> str:
    aliases = {
        "0": "range_find",
        "1": "doe",
        "2": "confirm",
        "range-find": "range_find",
    }
    phase = aliases.get(str(raw), str(raw))
    if phase not in {"range_find", "doe", "confirm"}:
        raise SystemExit(f"unknown phase {raw!r}; "
                          f"expected range_find/doe/confirm or 0/1/2")
    return phase


if __name__ == "__main__":
    raise SystemExit(main())
