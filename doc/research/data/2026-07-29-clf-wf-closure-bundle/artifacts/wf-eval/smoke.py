"""Smoke test: load one fold scorer, score one date via the repo's own
score_with_history, exactly as job_panel_scoring.py does. Measure timing."""
import sys, time, json
from pathlib import Path
import pandas as pd
import numpy as np

CORPUS = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/modal-probe/repo-root/backtesting/renquant_104/artifacts/walkforward_patchtst_runs/wf-pt-b4e47e2c-batch1")
PANEL = Path("/Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet")

from kernel.panel_pipeline.hf_patchtst_scorer import HFPatchTSTPanelScorer
from training_panel.global_calibrator import GlobalPanelCalibration

t0 = time.time()
sc = HFPatchTSTPanelScorer.load(CORPUS / "2023-10-02" / "hf_patchtst_all_seed44_model.pt")
print(f"[load] {time.time()-t0:.1f}s seq_len={sc.seq_len} n_feat={len(sc.feature_cols)}")
print("uses_csranknorm =", sc.metadata.get("uses_csranknorm"))
print("label_col =", sc.metadata.get("label_col"))

t0 = time.time()
panel = pd.read_parquet(PANEL)
print(f"[panel] {time.time()-t0:.1f}s shape={panel.shape}")
panel["date"] = pd.to_datetime(panel["date"])
missing = [c for c in sc.feature_cols if c not in panel.columns]
print("missing feature cols:", missing)
dates = np.sort(panel["date"].unique())
print("date range", dates[0], dates[-1], "n_dates", len(dates))

# live path replication
cut = pd.Timestamp("2023-10-02")
future = [d for d in dates if d > cut]
d0 = future[0]
past = panel[panel["date"] <= d0]
recent = sorted(past["date"].unique())[-sc.seq_len:]
hist = past[past["date"].isin(recent)]
tgt = sorted(panel.loc[panel["date"] == d0, "ticker"].unique())
print(f"date={pd.Timestamp(d0).date()} hist_rows={len(hist)} n_tickers={len(tgt)}")
t0 = time.time()
s = sc.score_with_history(hist, tgt)
dt = time.time() - t0
print(f"[score] {dt:.2f}s n={len(s)} mean={s.mean():+.4f} std={s.std():.4f}")
print(f"projected 43 folds x 21 dates = {903*dt/60:.1f} min")

cal = GlobalPanelCalibration.load(CORPUS / "2023-10-02" / "hf_patchtst-calibration.json")
p = cal.calibrate_probability_vec(s.values)
print("calibrated: mean=%.4f min=%.4f max=%.4f n_unique=%d" % (
    p.mean(), p.min(), p.max(), len(np.unique(p))))
lab = panel.loc[panel["date"] == d0, ["ticker", "fwd_60d_excess"]].set_index("ticker")["fwd_60d_excess"]
j = pd.DataFrame({"s": s, "p": p, "y": lab.reindex(s.index)}).dropna()
print("n_joined=", len(j), "IC_raw=%.4f IC_cal=%.4f" % (
    j["s"].corr(j["y"], method="spearman"), j["p"].corr(j["y"], method="spearman")))
