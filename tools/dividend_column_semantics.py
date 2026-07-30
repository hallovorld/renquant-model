#!/usr/bin/env python3
"""Establish the EMPIRICAL semantics of the `dividend` column before using it.

READ-ONLY on /Users/renhao/git/github/RenQuant. No writes there, ever.

The sibling trap being guarded against: in `split_ratio` the "no event" sentinel
is 0.0, not 1.0, and only 63/830 tickers even carry the column. So we do not
assume anything about `dividend` -- we measure:
  1. how many ticker files carry the column at all
  2. the value distribution (what is the no-event sentinel? 0.0 or NaN?)
  3. what a real dividend looks like (magnitude, cadence, as % of close)
  4. whether the value is per-share cash in price units (yield ~ plausible)
  5. whether the flag date is the EX-date (price drops that day) or pay date
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LIVE = Path("/Users/renhao/git/github/RenQuant")
OHLCV = LIVE / "data" / "ohlcv"
CFG = (LIVE / ".subrepo_runtime" / "repos" / "renquant-strategy-104"
       / "configs" / "strategy_config.json")
OUT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
           "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/mom-total-return")

watchlist = list(json.loads(CFG.read_text())["watchlist"])
all_dirs = sorted(p.name for p in OHLCV.iterdir() if (p / "1d.parquet").exists())
print(f"ticker dirs with 1d.parquet: {len(all_dirs)}   watchlist: {len(watchlist)}")

# ---- 1. column presence across ALL ticker files (not just watchlist) --------
import pyarrow.parquet as pq

has_div, has_split, cols_seen = [], [], {}
for t in all_dirs:
    try:
        sch = pq.read_schema(OHLCV / t / "1d.parquet")
    except Exception:
        continue
    names = tuple(n for n in sch.names if n != "__index_level_0__")
    cols_seen[names] = cols_seen.get(names, 0) + 1
    if "dividend" in names:
        has_div.append(t)
    if "split_ratio" in names:
        has_split.append(t)

print(f"\n[1] column presence over {len(all_dirs)} files")
print(f"    have 'dividend'   : {len(has_div)}")
print(f"    have 'split_ratio': {len(has_split)}")
print("    distinct column tuples:")
for k, v in sorted(cols_seen.items(), key=lambda kv: -kv[1]):
    print(f"      {v:>5}x  {k}")
wl_div = [t for t in watchlist if t in set(has_div)]
wl_split = [t for t in watchlist if t in set(has_split)]
print(f"    watchlist with 'dividend'   : {len(wl_div)}/{len(watchlist)}")
print(f"    watchlist with 'split_ratio': {len(wl_split)}/{len(watchlist)}")


def load(t, cols=None):
    df = pd.read_parquet(OHLCV / t / "1d.parquet", columns=cols)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index = df.index.normalize()
    return df


# ---- 2. value distribution over the watchlist -------------------------------
print(f"\n[2] `dividend` value distribution across {len(wl_div)} watchlist files")
n_nan = n_zero = n_neg = n_pos = n_tot = 0
pos_vals = []
for t in wl_div:
    d = load(t, ["dividend"])["dividend"]
    n_tot += len(d)
    n_nan += int(d.isna().sum())
    n_zero += int((d == 0.0).sum())
    n_neg += int((d < 0).sum())
    pv = d[d > 0]
    n_pos += len(pv)
    pos_vals.append(pv)
pos = pd.concat(pos_vals) if pos_vals else pd.Series(dtype=float)
print(f"    rows total  : {n_tot:,}")
print(f"    NaN         : {n_nan:,}   ({n_nan/n_tot:.4%})")
print(f"    exactly 0.0 : {n_zero:,}   ({n_zero/n_tot:.4%})   <-- no-event sentinel?")
print(f"    negative    : {n_neg:,}")
print(f"    positive    : {n_pos:,}   ({n_pos/n_tot:.4%})")
if len(pos):
    q = pos.quantile([0, .01, .05, .25, .5, .75, .95, .99, 1.0])
    print("    positive-value quantiles (raw units):")
    for k, v in q.items():
        print(f"      p{k*100:>5.1f} = {v:.6f}")

# ---- 3. per-ticker event counts and cadence ---------------------------------
print("\n[3] per-ticker event count / cadence / magnitude as % of close")
recs = []
for t in wl_div:
    df = load(t, ["close", "dividend"])
    ev = df[df["dividend"] > 0]
    if ev.empty:
        recs.append((t, 0, np.nan, np.nan, np.nan, np.nan))
        continue
    gaps = np.diff(np.asarray(ev.index.view("int64"))) / 86_400_000_000_000
    yld = (ev["dividend"] / ev["close"]).astype(float)
    recs.append((t, len(ev), float(np.median(gaps)) if len(gaps) else np.nan,
                 float(ev["dividend"].median()), float(yld.median()),
                 float(yld.max())))
ev_df = pd.DataFrame(recs, columns=["ticker", "n_events", "median_gap_days",
                                    "median_div", "median_yield", "max_yield"])
payers = ev_df[ev_df.n_events > 0]
nonpayers = ev_df[ev_df.n_events == 0]
print(f"    payers (>=1 positive dividend): {len(payers)}")
print(f"    non-payers (all zero/NaN)     : {len(nonpayers)}")
print(f"    non-payer tickers: {sorted(nonpayers.ticker)}")
print(f"    median gap between events, pooled median = "
      f"{payers.median_gap_days.median():.1f} calendar days "
      f"(91 => quarterly, 30 => monthly)")
print("    gap-day histogram over payers (median gap):")
print(payers.median_gap_days.value_counts().sort_index().to_string())
print(f"    per-event yield (div/close): pooled median "
      f"{payers.median_yield.median():.6f}  max over tickers "
      f"{payers.max_yield.max():.6f}")
print("\n    sample of 12 payers:")
print(payers.sort_values("n_events", ascending=False).head(12).to_string(index=False))

# ---- 4. is the flagged date the EX-date? ------------------------------------
# On an ex-div date the price drops by ~the dividend in a NON-adjusted series.
# Measure same-day return on flagged dates vs all other dates.
print("\n[4] is the flagged date the EX-date? same-day return test on RAW close")
ex_rets, other_rets, yields = [], [], []
n_ev = 0
for t in payers.ticker:
    df = load(t, ["close", "dividend"])
    r = df["close"].pct_change()
    isex = df["dividend"] > 0
    m = r.notna()
    ex_rets.append(r[isex & m].to_numpy())
    other_rets.append(r[~isex & m].to_numpy())
    yields.append((df["dividend"][isex & m] / df["close"].shift(1)[isex & m]).to_numpy())
    n_ev += int((isex & m).sum())
ex = np.concatenate(ex_rets)
oth = np.concatenate(other_rets)
yl = np.concatenate(yields)
diff = ex.mean() - oth.mean()
se = np.sqrt(ex.var(ddof=1) / len(ex) + oth.var(ddof=1) / len(oth))
print(f"    payers={len(payers)}  ex-div days={n_ev:,}")
print(f"    mean same-day return, EX-DIV days : {ex.mean()*1e4:+.1f} bp  (n={len(ex):,})")
print(f"    mean same-day return, OTHER days  : {oth.mean()*1e4:+.1f} bp  (n={len(oth):,})")
print(f"    difference                        : {diff*1e4:+.1f} bp  (SE {se*1e4:.1f} bp)")
print(f"    mean per-event yield div/close[t-1]: {yl.mean()*1e4:+.1f} bp")
print("    -> if difference ~= -yield, the flagged date IS the ex-date and the")
print("       close series does NOT include the dividend.")

json.dump({
    "n_ticker_files": len(all_dirs),
    "files_with_dividend": len(has_div),
    "files_with_split_ratio": len(has_split),
    "watchlist_n": len(watchlist),
    "watchlist_with_dividend": len(wl_div),
    "watchlist_with_split_ratio": len(wl_split),
    "rows_total": n_tot, "n_nan": n_nan, "n_zero": n_zero,
    "n_negative": n_neg, "n_positive": n_pos,
    "n_payers": int(len(payers)), "n_nonpayers": int(len(nonpayers)),
    "nonpayer_tickers": sorted(nonpayers.ticker),
    "median_gap_days_pooled": float(payers.median_gap_days.median()),
    "exdiv_days": int(n_ev),
    "mean_ret_exdiv_bp": float(ex.mean() * 1e4),
    "mean_ret_other_bp": float(oth.mean() * 1e4),
    "diff_bp": float(diff * 1e4), "diff_se_bp": float(se * 1e4),
    "mean_event_yield_bp": float(yl.mean() * 1e4),
}, open(OUT / "00_dividend_semantics.json", "w"), indent=2)
print(f"\nwrote {OUT/'00_dividend_semantics.json'}")
