#!/usr/bin/env python
"""PatchTST research CLI backed by ExperimentPipeline."""
from __future__ import annotations

import argparse
from pathlib import Path

from .research_pipeline import ExperimentSpec, check_promotion, run_experiment

CUTS = ["cut1_covid", "cut2_fed", "cut3_inflpk", "cut4_svb", "cut5_unwind"]
XGB_BASELINE = "+0.017 +/- 0.056 pooled, 3/5 (placebo-clean); ALL-minus-sentiment +0.0115"

_TUNED = [
    "--lr", "1e-4",
    "--weight-decay", "0.3",
    "--seq-len", "24",
    "--early-stopping-patience", "2",
]


def configs(spy_path: str) -> dict[str, list[str]]:
    return {
        "B_tuned": list(_TUNED),
        "C_xstock": _TUNED + ["--cross-stock-attn"],
        "D_film": _TUNED + ["--film-regime-cond", "--spy-path", spy_path],
        "E_drop_senti": _TUNED + [
            "--exclude-features",
            "mean_sentiment,n_articles_log,sentiment_pos_share",
        ],
        "F_fwd20d": _TUNED + ["--label", "fwd_20d_excess"],
    }


_configs = configs


def run_one(hf, config_args, name, cut, seed, epochs, device, out_root) -> dict:
    """Compatibility adapter for older callers of the research harness."""
    out = Path(out_root) / f"{name}_{cut}_s{seed}"
    argv = [
        "--cut", cut,
        "--seed", str(seed),
        "--epochs", str(epochs),
        "--device", device,
        "--output-dir", str(out),
    ] + list(config_args[name])
    summary = hf.train_single_run(hf.build_parser().parse_args(argv))
    pred_paths = list(out.glob(f"hf_patchtst_{cut}_seed{seed}_val_preds.parquet"))
    pooled_ic = None
    if pred_paths:
        pooled_ic = _pooled_ic(pred_paths[0])
    return {"pooled_ic": pooled_ic, "min_regime_ic": summary.get("best_val_ic")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", default="range_find", help="range_find/doe/confirm or 0/1/2")
    p.add_argument("--configs", default=None, help="comma list (default: all)")
    p.add_argument("--cuts", default=None, help="comma list (default: all 5)")
    p.add_argument("--seeds", default="42", help="comma list (confirm: 42,43,44,45,46)")
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--device", default="mps", choices=["auto", "cpu", "mps", "cuda"])
    p.add_argument("--scheduler", default="auto", choices=["auto", "linear", "parallel"])
    p.add_argument("--max-workers", type=int, default=None)
    p.add_argument("--data-dir", default="data")
    p.add_argument("--dataset", default="data/transformer_v4_wl200_clean.parquet")
    p.add_argument("--spy-path", default="data/ohlcv/SPY/1d.parquet")
    p.add_argument("--strategy-config", default=None)
    p.add_argument("--out-dir", default="artifacts/patchtst_research")
    p.add_argument("--out", default=None, help="legacy alias; parent directory is used")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--fail-fast", action="store_true")
    p.add_argument("--no-placebos", action="store_true")
    p.add_argument("--allow-ungated-smoke", action="store_true")
    p.add_argument(
        "--no-regime-contract", action="store_true",
        help="Bypass RegimeDetectorContractTask. Use ONLY when a detector "
             "mislabel is being tracked separately (e.g. calm_2017 → "
             "BULL_VOLATILE) and Tier-3 evaluation can't wait for the "
             "detector fix. Per umbrella CLAUDE.md §1.4 PRIME DIRECTIVE: "
             "detector quality is P0 and bypass is temporary scaffolding, "
             "not a default.",
    )
    p.add_argument("--label", default="fwd_60d_excess")
    p.add_argument("--label-lookahead-days", type=int, default=60)
    p.add_argument("--embargo-days", type=int, default=60)
    p.add_argument("--val-tail-pct", type=float, default=0.10)
    p.add_argument("--label-shift-days", type=int, default=10)
    p.add_argument("--baseline-pooled-ic", type=float, default=None)
    p.add_argument("--check-promotion", default=None, help="load experiment dir and return 0/1/2/3")
    args = p.parse_args(argv)

    if args.check_promotion:
        return check_promotion(Path(args.check_promotion))

    import renquant_model_patchtst.hf_trainer as hf

    phase = _parse_phase(args.phase)
    spy_path = str(Path(args.spy_path))
    all_configs = configs(spy_path)
    selected_configs = args.configs.split(",") if args.configs else list(all_configs)
    cuts = args.cuts.split(",") if args.cuts else CUTS
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
        label_col=args.label,
        label_lookahead_days=args.label_lookahead_days,
        embargo_days=args.embargo_days,
        val_tail_pct=args.val_tail_pct,
        label_shift_days=args.label_shift_days,
        baseline_pooled_ic=args.baseline_pooled_ic,
    )
    ctx = run_experiment(spec, trainer_runner=hf.train_single_run, parser_builder=hf.build_parser)
    print(
        f"PatchTST research done: verdict={ctx.verdict} "
        f"experiment_dir={ctx.experiment_dir} baseline={XGB_BASELINE}",
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
        raise SystemExit(f"unknown phase {raw!r}; expected range_find/doe/confirm or 0/1/2")
    return phase


def _pooled_ic(val_preds_path: Path) -> float:
    import numpy as np
    import pandas as pd
    from scipy.stats import spearmanr

    df = pd.read_parquet(val_preds_path)
    score_col = "pred" if "pred" in df.columns else "model_score"
    xs = [
        spearmanr(g[score_col], g["label"])[0]
        for _, g in df.groupby("date")
        if len(g) >= 2
    ]
    xs = [x for x in xs if np.isfinite(x)]
    return float(np.mean(xs)) if xs else float("nan")


if __name__ == "__main__":
    raise SystemExit(main())
