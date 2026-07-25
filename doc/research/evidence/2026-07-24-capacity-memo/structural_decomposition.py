"""STRUCTURAL DECOMPOSITION of the book's P&L generation chain.

Theory frame (Grinold 1989; Daniel-Grinblatt-Titman-Wermers 1997):

    realized alpha = [ skill + characteristic premia ] x dispersion x capture
                      ------ TEST 1 (DGTW) ------        TEST 2

TEST 1 — DGTW characteristic-matched benchmark. Each stock's benchmark is
  the mean fwd60 of its (vol x momentum x beta) cell that date, self-excluded.
  Pick-minus-cell = SKILL. Raw-minus-DGTW = the characteristic tilt.
  If DGTW-adjusted spread ~ 0, the model selects CHARACTERISTICS, not stocks.

TEST 2 — dispersion conditioning. Grinold: expected spread = IC x sigma_CS.
  Regress per-date clean IC and per-date top-10 spread on cross-sectional
  dispersion of fwd60. If the 'episodes' are just high-dispersion states,
  the model's usefulness is PREDICTABLE from a live observable.

A former TEST 3 (exit-stack counterfactual: production stop params applied
to real price paths) has been REMOVED from this repo (model#69 review,
BLOCKER 2): it read `RenQuant/backtesting/renquant_104/strategy_config.json`
and production OHLCV paths directly, which is backtesting/execution-policy
analysis, outside this repo's GBDT-score/model-analysis boundary. If
pursued, it belongs in the repo/harness that owns backtesting execution
policy, consuming a versioned contract-level input rather than reaching
into that repo's tree.

Inputs: cached real/placebo scores (this session), the panel's own STD60 /
ROC60 / BETA60 columns.

REPRODUCIBILITY GAP: scores_real.parquet / scores_placebo.parquet are the
per-row real vs matched-placebo model scores from the same production-recipe
run that depth_probe.py (this bundle) reads directly from panel/model
training — that ad hoc scoring pass was not itself committed as a script, so
these two inputs are not regenerable from this bundle alone. Recreate them by
scoring `all_172 / fwd_60d_excess / rank:pairwise / 5 purged folds / 60d
embargo / seeds 42-43-44` twice (real labels, then label-shuffled placebo)
via `renquant_model_gbdt.panel_trainer.train_xgb`, then write each run's
per-(ticker, date) predicted score to a parquet with those columns before
running this script.
"""
import warnings, json, sys, os
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(line_buffering=True)
from pathlib import Path
import numpy as np
import pandas as pd

# RQ_DATA_DIR has no default: this repo does not contain the umbrella's
# data/ dir, so a hardcoded path would only work on one operator's machine.
# S (CAPACITY_MEMO_OUT) defaults to this file's own directory (repo-local)
# — see the REPRODUCIBILITY GAP note above for what must be placed in S.
if "RQ_DATA_DIR" not in os.environ:
    raise SystemExit("RQ_DATA_DIR must be set to the RenQuant umbrella repo's data/ dir")
DD = Path(os.environ["RQ_DATA_DIR"])
S = Path(os.environ.get("CAPACITY_MEMO_OUT", str(Path(__file__).resolve().parent)))
TOP_N = 10

R = pd.read_parquet(S / "scores_real.parquet")
P = pd.read_parquet(S / "scores_placebo.parquet")
pan = pd.read_parquet(DD / "alpha158_291_fundamental_dataset.parquet",
                      columns=["ticker", "date", "STD60", "ROC60", "BETA60"])
pan["date"] = pd.to_datetime(pan["date"])
R = R.merge(pan, on=["ticker", "date"], how="left")
print(f"scored rows {len(R):,} · char coverage {R['STD60'].notna().mean():.1%}", flush=True)

# ════════════════════════ TEST 1 — DGTW ════════════════════════════
print("\n" + "=" * 76, flush=True)
print("TEST 1 — DGTW (1997): skill vs characteristic tilt", flush=True)
print("=" * 76, flush=True)

def dgtw_cells(df):
    d = df.dropna(subset=["STD60", "ROC60", "BETA60", "f60"]).copy()
    for c, q in (("STD60", 3), ("ROC60", 3), ("BETA60", 3)):
        d[c + "_t"] = d.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), q, labels=False))
    d["cell"] = (d["STD60_t"].astype(int) * 9 + d["ROC60_t"].astype(int) * 3
                 + d["BETA60_t"].astype(int))
    g = d.groupby(["date", "cell"])["f60"]
    d["cell_sum"] = g.transform("sum")
    d["cell_n"] = g.transform("count")
    # self-excluded cell mean
    d["bench"] = (d["cell_sum"] - d["f60"]) / (d["cell_n"] - 1).replace(0, np.nan)
    d["dgtw"] = d["f60"] - d["bench"]
    return d

D = dgtw_cells(R)
def daily_top_spread(df, col, wins=None):
    def one(g):
        if len(g) < 30:
            return np.nan
        v = g[col] if wins is None else g[col].clip(-wins, wins)
        return v.loc[g.nlargest(TOP_N, "score").index].mean() - v.mean()
    return df.groupby("date").apply(one).dropna()

raw_sp = daily_top_spread(D, "f60")
dgtw_sp = daily_top_spread(D, "dgtw")
raw_w = daily_top_spread(D, "f60", wins=0.5)
dgtw_w = daily_top_spread(D, "dgtw", wins=0.5)

def block_t(x):
    x = x.sort_index()
    b = np.array([x.iloc[i:i + 60].mean() for i in range(0, len(x) - 59, 60)])
    return b.mean(), b.mean() / (b.std(ddof=1) / np.sqrt(len(b))), len(b)

for name, sp in (("RAW top-10 spread", raw_sp), ("DGTW-ADJUSTED (skill)", dgtw_sp),
                 ("RAW winsorized ±50%", raw_w), ("DGTW winsorized ±50%", dgtw_w)):
    m, t, n = block_t(sp)
    print(f"  {name:24} {m:+.4f}/60d   block-t={t:+.2f} (n={n})", flush=True)
tilt = raw_sp.mean() - dgtw_sp.mean()
print(f"\n  characteristic tilt = raw − DGTW = {tilt:+.4f}/60d "
      f"({100 * tilt / raw_sp.mean():.0f}% of the raw spread)", flush=True)
# what characteristics do the picks tilt to?
picks = D.loc[D.groupby("date")["score"].rank(ascending=False) <= TOP_N]
print("  top-10 mean percentile of: vol {:.0f} · momentum {:.0f} · beta {:.0f}".format(
    *[100 * picks.groupby("date")[c].rank(pct=True).groupby(picks["date"]).mean().mean()
      if False else 100 * D.groupby("date")[c].rank(pct=True).loc[picks.index].mean()
      for c in ("STD60", "ROC60", "BETA60")]), flush=True)

# ════════════════════════ TEST 2 — dispersion ═══════════════════════
print("\n" + "=" * 76, flush=True)
print("TEST 2 — Grinold: are the 'episodes' just cross-sectional dispersion?", flush=True)
print("=" * 76, flush=True)
disp = R.groupby("date")["f60"].std().rename("disp")
icR = R.groupby("date").apply(lambda g: g["score"].corr(g["f60"], method="spearman")
                              if len(g) >= 5 else np.nan).dropna()
icP = P.groupby("date").apply(lambda g: g["score"].corr(g["f60"], method="spearman")
                              if len(g) >= 5 else np.nan).dropna()
common = icR.index.intersection(icP.index)
clean_ic = (icR[common] - icP[common]).rename("clean_ic")
J = pd.concat([clean_ic, disp, raw_sp.rename("spread")], axis=1).dropna()
J["dt"] = pd.qcut(J["disp"], 3, labels=["LOW", "MID", "HIGH"])
print(f"  corr(clean IC, dispersion)        : {J['clean_ic'].corr(J['disp']):+.2f}", flush=True)
print(f"  corr(top-10 spread, dispersion)   : {J['spread'].corr(J['disp']):+.2f}", flush=True)
print("\n  by dispersion tercile:", flush=True)
for t_, g in J.groupby("dt"):
    print(f"    {t_:5}  clean IC {g['clean_ic'].mean():+.4f}   "
          f"spread {g['spread'].mean():+.4f}/60d   n={len(g)}", flush=True)
yr = J.groupby(J.index.year)[["clean_ic", "disp"]].mean()
print(f"\n  corr(YEARLY clean IC, YEARLY dispersion): "
      f"{yr['clean_ic'].corr(yr['disp']):+.2f}", flush=True)
cur = J["disp"].iloc[-250:].mean()
pct = 100 * (J["disp"] < cur).mean()
print(f"  trailing-250d dispersion now at the {pct:.0f}th percentile of history", flush=True)

# TEST 3 (exit-stack counterfactual) removed — see module docstring.

json.dump({"dgtw": {"raw": float(raw_sp.mean()), "dgtw": float(dgtw_sp.mean()),
                    "raw_w50": float(raw_w.mean()), "dgtw_w50": float(dgtw_w.mean())},
           "dispersion_corr": float(J["clean_ic"].corr(J["disp"]))},
          open(S / "structural_decomposition_result.json", "w"), indent=2)
print("\nSaved structural_decomposition_result.json", flush=True)
