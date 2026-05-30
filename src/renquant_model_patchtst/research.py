#!/usr/bin/env python
"""PatchTST improvement research harness (designed 2026-05-28; run by other agents).

Lives WITH the model (renquant_model_patchtst) because improving the PatchTST model
is model-development work, not daily orchestration. Drives this package's own
`hf_trainer` across the walk-forward cuts and scores configs on the fair POOLED
per-date IC (not the trainer's pessimistic min-regime selection metric).

=============================== THE PLAN ===============================

GOAL: raise PatchTST's walk-forward POOLED cross-sectional IC above the XGB baseline
(placebo-clean pooled IC +0.017 ± 0.056, 3/5 cuts) so the sequence learner becomes a
viable single-model alternative (NO ensemble — user mandate 2026-05-28).

WHAT WE ALREADY KNOW (don't re-discover):
  * Default/untuned config is unstable: min-regime IC +0.021 ± 0.124 (2/5 cuts).
  * The DOE-tuned point (lr 1e-4, wd 0.3, seq 24, 8 epochs) FIXES most of the
    variance — partial run gave cut1 +0.106 / cut2 -0.032 / cut3 +0.038
    (vs default +0.091 / -0.128 / -0.046). wd=0.3 is the key regularizer.
  * The trainer's selection metric `eval_min_regime_ic` = MIN across regimes is
    pessimistic + noisy (sparse BEAR/CHOPPY val days). The RIGHT comparison metric
    is the POOLED per-date Spearman IC on the val predictions (this harness computes
    it from each run's *_val_preds.parquet) — directly comparable to XGB's +0.017.
  * Runtime is ~40 min/cut (8 epochs on full panel). Cuts are independent →
    parallelize. Runs are RESUMABLE (existing val_preds.parquet ⇒ skipped).

LEVERS TO TEST (each grounded in code/literature):
  B_tuned         lr1e-4 wd0.3 seq24 8ep            regularization — the baseline to beat
  C_xstock        B + --cross-stock-attn            iTransformer cross-stock attention
                                                    (Liu 2024 arXiv 2310.06625) — the fix
                                                    for PatchTST channel-independence on
                                                    cross-sectional finance
  D_film          B + --film-regime-cond --spy-path FiLM regime conditioning (Perez 2017)
  E_drop_senti    B + drop 3 sentiment features     XGB lesson: sentiment DILUTES; needs a
                                                    trainer --exclude-features flag (see NOTE)
  F_fwd20d        B + --label fwd_20d_excess        shorter horizon (XGB: 20d >= 60d)

STAGED PROTOCOL (CLAUDE.md §5.11 range-find, §5.14 DOE, §5.13.4a confirm):
  Phase 0  RANGE-FIND : B_tuned + each single lever, 5 cuts x 1 seed, POOLED IC,
                        --epochs 4. A lever "helps" if its pooled IC mean exceeds
                        B_tuned by >= 1 SE AND positive-cut-count >= B.
  Phase 1  DOE        : if a lever helps, Box-Behnken (pyDOE2.bbdesign) on
                        {lr, wd, seq_len, nll_loss_weight}; fit quadratic surface; optimum.
  Phase 2  CONFIRM    : best config x 5 seeds (§5.13.4) + PLACEBO battery (label-shuffle +
                        time-shift, §5.2) + DSR/PBO (§5.14.4). PROMOTE to PatchTST-primary
                        ONLY if pooled IC > XGB +0.017 placebo-clean AND DSR>0.5.

NOTE — prerequisites (small renquant_model_patchtst additions, not yet done):
  * E_drop_senti needs hf_trainer to accept a feature-exclusion list (mirror the GBDT
    `GbdtTrainingContext.exclude_features`); until then E is skipped with a warning.
  * Phase-2 label-shuffle placebo needs a trainer `--shuffle-labels` flag (permute the
    label within each date in TRAIN only). Time-shift placebo = train on label shifted
    +horizon (pre-shifted dataset or a flag). Both flagged TODO.

USAGE (agents) — needs the sibling pins on path + the umbrella data dir:
  python -m renquant_model_patchtst.research --phase 0 --epochs 4 --device mps
  python -m renquant_model_patchtst.research --configs B_tuned,C_xstock --seeds 42,43
  # data location overridable: --strategy-dir, --dataset, --spy-path
Results stream to stdout AND a JSON at --out (default <umbrella>/artifacts/
patchtst_research/results.json) so a run can be killed/resumed and the partial table
is always readable.
========================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

GITHUB = Path(__file__).resolve().parents[3]
DEFAULT_UMBRELLA = GITHUB / "RenQuant"
_PIN_SRCS = ["renquant-common", "renquant-base-data", "renquant-artifacts", "renquant-model"]
CUTS = ["cut1_covid", "cut2_fed", "cut3_inflpk", "cut4_svb", "cut5_unwind"]
XGB_BASELINE = "+0.017 ± 0.056 pooled, 3/5 (placebo-clean); ALL-minus-sentiment +0.0115"

_TUNED = ["--lr", "1e-4", "--weight-decay", "0.3", "--seq-len", "24",
          "--early-stopping-patience", "2"]


def _configs(spy_path: str) -> dict[str, list[str]]:
    return {
        "B_tuned":      _TUNED,
        "C_xstock":     _TUNED + ["--cross-stock-attn"],
        "D_film":       _TUNED + ["--film-regime-cond", "--spy-path", spy_path],
        "E_drop_senti": _TUNED + ["--exclude-features",
                                  "mean_sentiment,n_articles_log,sentiment_pos_share"],
        "F_fwd20d":     _TUNED + ["--label", "fwd_20d_excess"],
        # §5.2 placebos — must score pooled IC ≈ 0; quantify val-selection
        # optimism in the real configs above (val IC is the selection metric).
        "B_placebo":    _TUNED + ["--shuffle-labels"],
        "C_placebo":    _TUNED + ["--cross-stock-attn", "--shuffle-labels"],
    }


def _bootstrap(strategy_dir: Path) -> None:
    for n in _PIN_SRCS:
        s = GITHUB / n / "src"
        if s.is_dir() and str(s) not in sys.path:
            sys.path.insert(0, str(s))
    os.environ.setdefault("RENQUANT_STRATEGY_DIR", str(strategy_dir))
    umbrella = strategy_dir.parent.parent
    for p in (str(strategy_dir), str(umbrella)):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(umbrella)  # trainer reads relative data/ paths


def _pooled_ic(val_preds_path: Path) -> float:
    """Pooled per-date Spearman IC — the fair, XGB-comparable metric."""
    import pandas as pd
    from scipy.stats import spearmanr
    df = pd.read_parquet(val_preds_path)
    xs = [spearmanr(g["pred"], g["label"])[0] for _, g in df.groupby("date") if len(g) >= 8]
    xs = [x for x in xs if np.isfinite(x)]
    return float(np.mean(xs)) if xs else float("nan")


def _trainer_supports(hf, dest: str) -> bool:
    return any(getattr(act, "dest", None) == dest for act in hf.build_parser()._actions)


def run_one(hf, configs, name, cut, seed, epochs, device, out_root) -> dict:
    """Run one (config,cut,seed); resumable (skips if val_preds already present)."""
    out = out_root / f"{name}_{cut}_s{seed}"
    vp = list(out.glob(f"hf_patchtst_{cut}_seed{seed}_val_preds.parquet"))
    if not vp:
        extra = configs[name]
        if "--exclude-features" in extra and not _trainer_supports(hf, "exclude_features"):
            return {"skipped": "trainer lacks --exclude-features (add it to hf_trainer)"}
        argv = (["--cut", cut, "--seed", str(seed), "--epochs", str(epochs),
                 "--device", device, "--output-dir", str(out)] + extra)
        try:
            summary = hf.train_single_run(hf.build_parser().parse_args(argv))
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:300]}
        vp = list(out.glob(f"hf_patchtst_{cut}_seed{seed}_val_preds.parquet"))
        min_regime = summary.get("best_val_ic")
    else:
        min_regime = None  # resumed
    return {"pooled_ic": _pooled_ic(vp[0]) if vp else float("nan"), "min_regime_ic": min_regime}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("===")[0])
    p.add_argument("--phase", type=int, default=0, help="0=range-find, 2=confirm")
    p.add_argument("--configs", default=None, help="comma list (default: all)")
    p.add_argument("--cuts", default=None, help="comma list (default: all 5)")
    p.add_argument("--seeds", default="42", help="comma list (Phase 2: 42,43,44,45,46)")
    p.add_argument("--epochs", type=int, default=4, help="4 range-find, 8 confirm")
    p.add_argument("--device", default="mps")
    p.add_argument("--strategy-dir", default=str(DEFAULT_UMBRELLA / "backtesting" / "renquant_104"),
                   help="umbrella strategy dir (hosts the data-side kernel.* deps + data/)")
    p.add_argument("--spy-path", default=None, help="SPY OHLCV for FiLM (default: <umbrella>/data/...)")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)

    strat = Path(a.strategy_dir)
    _bootstrap(strat)
    umbrella = strat.parent.parent
    spy_path = a.spy_path or str(umbrella / "data" / "ohlcv" / "SPY" / "1d.parquet")
    import renquant_model_patchtst.hf_trainer as hf

    configs = _configs(spy_path)
    cfgs = a.configs.split(",") if a.configs else list(configs)
    cuts = a.cuts.split(",") if a.cuts else CUTS
    seeds = [int(s) for s in a.seeds.split(",")]
    out_root = Path(a.out).parent if a.out else umbrella / "artifacts" / "patchtst_research"
    out_root.mkdir(parents=True, exist_ok=True)
    results_path = Path(a.out) if a.out else out_root / "results.json"

    print(f"=== PatchTST research phase {a.phase} | configs={cfgs} cuts={len(cuts)} "
          f"seeds={seeds} epochs={a.epochs} ===\nXGB baseline: {XGB_BASELINE}", flush=True)
    results: dict = json.loads(results_path.read_text()) if results_path.exists() else {}
    for name in cfgs:
        results.setdefault(name, {})
        for cut in cuts:
            for seed in seeds:
                key = f"{cut}_s{seed}"
                if key in results[name] and "pooled_ic" in results[name][key]:
                    continue
                r = run_one(hf, configs, name, cut, seed, a.epochs, a.device, out_root)
                results[name][key] = r
                results_path.write_text(json.dumps(results, indent=2))
                print(f"  {name} {key}: {r}", flush=True)

    print("\n=== POOLED IC SUMMARY (fair vs XGB +0.017) ===")
    for name in cfgs:
        ics = [v["pooled_ic"] for v in results[name].values()
               if isinstance(v, dict) and v.get("pooled_ic") == v.get("pooled_ic")]
        if ics:
            arr = np.array(ics)
            print(f"  {name:14} pooled {arr.mean():+.4f} ± "
                  f"{arr.std(ddof=1) if len(arr) > 1 else 0:.4f}  ({int((arr > 0).sum())}/{len(arr)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
