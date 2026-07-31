"""FROZEN PREREG EXECUTION — step 1: score the 43 WF folds over their
out-of-sample windows using the repo's own HFPatchTSTPanelScorer.

Replicates the live serving call exactly (job_panel_scoring.py L489-497):
    past   = panel[panel.date <= d]
    recent = sorted(past.date.unique())[-scorer.seq_len:]
    hist   = past[past.date.isin(recent)]
    scores = scorer.score_with_history(hist, target_tickers)

Writes scores.parquet (fold_idx, cutoff, date, ticker, raw, cal).
READ-ONLY over the corpus and the panel. No production surface touched.
"""
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

logging.getLogger("kernel.panel_pipeline.hf_patchtst_scorer").setLevel(
    logging.ERROR)

CORPUS = Path(
    "/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator/"
    "428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/modal-probe/repo-root/"
    "backtesting/renquant_104/artifacts/walkforward_patchtst_runs/"
    "wf-pt-b4e47e2c-batch1")
PANEL = Path("/Users/renhao/git/github/RenQuant/data/"
             "transformer_v4_wl200_clean.parquet")
OUT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-"
           "orchestrator/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/"
           "wf-eval")
LAST_FOLD_TRADING_DAYS = 21

from kernel.panel_pipeline.hf_patchtst_scorer import HFPatchTSTPanelScorer
from training_panel.global_calibrator import GlobalPanelCalibration


def main() -> int:
    t_start = time.time()
    manifest = json.loads(
        (CORPUS / "walkforward_patchtst_manifest.json").read_text())
    retrains = manifest["retrains"]
    cutoffs = [pd.Timestamp(r["cutoff_date"]) for r in retrains]
    assert len(cutoffs) == 43, f"expected 43 folds, got {len(cutoffs)}"

    panel = pd.read_parquet(PANEL)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)
    all_dates = np.sort(panel["date"].unique())
    print(f"[panel] {panel.shape} dates {pd.Timestamp(all_dates[0]).date()}"
          f" .. {pd.Timestamp(all_dates[-1]).date()}", flush=True)

    rows = []
    for i, cut in enumerate(cutoffs):
        fold_dir = CORPUS / cut.strftime("%Y-%m-%d")
        model_p = fold_dir / "hf_patchtst_all_seed44_model.pt"
        cal_p = fold_dir / "hf_patchtst-calibration.json"
        if not model_p.exists() or not cal_p.exists():
            raise FileNotFoundError(f"fold {i} {cut.date()}: missing artifact")

        if i + 1 < len(cutoffs):
            window = [d for d in all_dates if cut < d <= cutoffs[i + 1]]
        else:
            window = [d for d in all_dates if d > cut][:LAST_FOLD_TRADING_DAYS]

        scorer = HFPatchTSTPanelScorer.load(model_p)
        cal = GlobalPanelCalibration.load(cal_p)
        t0 = time.time()
        n_scored = 0
        for d in window:
            past = panel[panel["date"] <= d]
            recent = sorted(past["date"].unique())[-scorer.seq_len:]
            hist = past[past["date"].isin(recent)]
            tgt = sorted(panel.loc[panel["date"] == d, "ticker"].unique())
            s = scorer.score_with_history(hist, list(tgt))
            if s.empty:
                print(f"  !! fold {i} {pd.Timestamp(d).date()}: empty score",
                      flush=True)
                continue
            p = cal.calibrate_probability_vec(s.values)
            rows.append(pd.DataFrame({
                "fold_idx": i,
                "cutoff": cut,
                "date": pd.Timestamp(d),
                "ticker": s.index.values,
                "raw": s.values.astype(float),
                "cal": np.asarray(p, dtype=float),
            }))
            n_scored += len(s)
        print(f"[fold {i:02d}] {cut.date()} n_dates={len(window)} "
              f"n_scores={n_scored} {time.time() - t0:.1f}s "
              f"(elapsed {time.time() - t_start:.0f}s)", flush=True)

    out = pd.concat(rows, ignore_index=True)
    out.to_parquet(OUT / "scores.parquet", index=False)
    meta = {
        "n_folds": len(cutoffs),
        "n_rows": int(len(out)),
        "n_dates": int(out["date"].nunique()),
        "wall_seconds": round(time.time() - t_start, 1),
        "corpus": str(CORPUS),
        "panel": str(PANEL),
        "last_fold_trading_days": LAST_FOLD_TRADING_DAYS,
    }
    (OUT / "scores_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2), flush=True)
    # disjointness assertion
    per_date_folds = out.groupby("date")["fold_idx"].nunique()
    assert per_date_folds.max() == 1, "OOS windows are NOT disjoint"
    print("[OK] windows disjoint; wrote scores.parquet", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
