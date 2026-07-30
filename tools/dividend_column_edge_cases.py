#!/usr/bin/env python3
"""Edge cases in `dividend` that would break a naive total-return build.

READ-ONLY on the umbrella.

Q1 What are the 759 NaN rows? Whole-ticker or scattered?
Q2 What is the $15.00 max dividend -- a special dividend, or a split artifact?
Q3 CRITICAL: is `dividend` expressed on the SAME (split-back-adjusted) price
   axis as `close`? If the vendor stores the raw historical cash amount while
   `close` is back-adjusted for a later split, then div/close blows up at old
   dates for names that split, and the adjustment would be badly wrong there.
   Test: per-event yield distribution, worst offenders, and specifically the
   names that DO carry split_ratio with a real split event.
Q4 Are there true measured non-payers (column present, all zeros) anywhere?
Q5 Do the 34 watchlist names with NO dividend column actually pay dividends
   in reality? (If yes, their total-return series is unfixable and that is a
   limitation to register, not to paper over.)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

LIVE = Path("/Users/renhao/git/github/RenQuant")
OHLCV = LIVE / "data" / "ohlcv"
CFG = (LIVE / ".subrepo_runtime" / "repos" / "renquant-strategy-104"
       / "configs" / "strategy_config.json")

watchlist = list(json.loads(CFG.read_text())["watchlist"])


def load(t):
    df = pd.read_parquet(OHLCV / t / "1d.parquet")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index = df.index.normalize()
    return df


def cols(t):
    return set(pq.read_schema(OHLCV / t / "1d.parquet").names)


wl_div = [t for t in watchlist if (OHLCV / t / "1d.parquet").exists()
          and "dividend" in cols(t)]
wl_nodiv = [t for t in watchlist if (OHLCV / t / "1d.parquet").exists()
            and "dividend" not in cols(t)]

print("=" * 78)
print("Q1  the NaN dividend rows")
print("=" * 78)
tot = 0
for t in wl_div:
    d = load(t)["dividend"]
    k = int(d.isna().sum())
    if k:
        idx = d.index[d.isna()]
        print(f"  {t:<6} {k:>4} NaN of {len(d):>5}   "
              f"{idx.min().date()} .. {idx.max().date()}   "
              f"contiguous_tail={bool((d.index[-k:] == idx).all())}")
        tot += k
print(f"  total NaN rows = {tot}")

print("\n" + "=" * 78)
print("Q2/Q3  per-event yield distribution and worst offenders")
print("=" * 78)
rows = []
for t in wl_div:
    df = load(t)
    ev = df[df["dividend"] > 0]
    if ev.empty:
        continue
    prev = df["close"].shift(1)
    for dt, r in ev.iterrows():
        p = prev.get(dt, np.nan)
        if not np.isfinite(p) or p <= 0:
            continue
        rows.append((t, dt, float(r["dividend"]), float(p), float(r["dividend"] / p)))
ev_all = pd.DataFrame(rows, columns=["ticker", "date", "div", "prev_close", "yield"])
print(f"  events with usable prev_close: {len(ev_all):,}")
q = ev_all["yield"].quantile([0, .5, .9, .99, .999, 1.0])
for k, v in q.items():
    print(f"    yield p{k*100:>6.2f} = {v:.5f}  ({v*1e4:.0f} bp)")
print(f"  events with yield > 3%:  {int((ev_all['yield'] > 0.03).sum())}")
print(f"  events with yield > 10%: {int((ev_all['yield'] > 0.10).sum())}")
print("\n  top 15 by yield:")
print(ev_all.nlargest(15, "yield").to_string(index=False))
print("\n  top 8 by raw dividend amount:")
print(ev_all.nlargest(8, "div").to_string(index=False))

print("\n" + "=" * 78)
print("Q3b  split-axis consistency: does the same-day drop track the dividend")
print("     EVENT BY EVENT? (a raw-cash-vs-back-adjusted-close mismatch would")
print("     show as drop >> dividend for pre-split dates on splitters)")
print("=" * 78)
recs = []
for t in wl_div:
    df = load(t)
    r = df["close"].pct_change()
    ev = df["dividend"] > 0
    prev = df["close"].shift(1)
    y = (df["dividend"] / prev)[ev & r.notna()]
    rr = r[ev & r.notna()]
    # residual = same-day return + yield ; should be ~ the day's ordinary move
    recs.append(pd.DataFrame({"ticker": t, "date": rr.index,
                              "ret": rr.values, "yld": y.values}))
ev2 = pd.concat(recs, ignore_index=True)
ev2["resid"] = ev2["ret"] + ev2["yld"]
print(f"  n={len(ev2):,}")
print(f"  mean ret      = {ev2['ret'].mean()*1e4:+.1f} bp")
print(f"  mean yield    = {ev2['yld'].mean()*1e4:+.1f} bp")
print(f"  mean residual = {ev2['resid'].mean()*1e4:+.1f} bp   "
      f"(should be ~ +8.5 bp, the ordinary-day mean)")
# a systematic split mismatch would make yield huge on OLD dates only
ev2["yr"] = pd.DatetimeIndex(ev2["date"]).year
byyr = ev2.groupby("yr").agg(n=("yld", "size"), mean_yld_bp=("yld", lambda s: s.mean()*1e4),
                             max_yld_bp=("yld", lambda s: s.max()*1e4),
                             mean_ret_bp=("ret", lambda s: s.mean()*1e4))
print("\n  by year (a back-adjust mismatch would inflate old-year yields):")
print(byyr.to_string(float_format=lambda v: f"{v:.1f}"))

print("\n" + "=" * 78)
print("Q3c  splitters specifically: names with split_ratio AND a real split")
print("=" * 78)
for t in watchlist:
    if not (OHLCV / t / "1d.parquet").exists() or "split_ratio" not in cols(t):
        continue
    df = load(t)
    sr = df["split_ratio"]
    real = sr[(sr.notna()) & (sr != 0.0) & (sr != 1.0)]
    if real.empty:
        continue
    have_div = "dividend" in df.columns
    print(f"  {t:<6} splits={len(real)} "
          f"{[(str(d.date()), round(float(v),4)) for d, v in real.items()][:4]}"
          f"  dividend_col={have_div}")
    if have_div:
        ev = df[df["dividend"] > 0]
        if not ev.empty:
            y = (ev["dividend"] / df["close"].shift(1).reindex(ev.index))
            for d in real.index:
                pre = y[y.index < d]
                post = y[y.index > d]
                print(f"          split {d.date()}: mean yield pre="
                      f"{pre.mean()*1e4 if len(pre) else float('nan'):.0f}bp "
                      f"(n={len(pre)})  post="
                      f"{post.mean()*1e4 if len(post) else float('nan'):.0f}bp "
                      f"(n={len(post)})")

print("\n" + "=" * 78)
print("Q4  true measured non-payers (dividend column present, ALL zeros)")
print("=" * 78)
all_dirs = sorted(p.name for p in OHLCV.iterdir() if (p / "1d.parquet").exists())
zero_payers = []
for t in all_dirs:
    try:
        c = cols(t)
    except Exception:
        continue
    if "dividend" not in c:
        continue
    d = pd.read_parquet(OHLCV / t / "1d.parquet", columns=["dividend"])["dividend"]
    if len(d) and not (d > 0).any():
        zero_payers.append((t, len(d)))
print(f"  files with dividend column but zero positive events: {len(zero_payers)}")
print(f"  {zero_payers[:30]}")
print(f"  of these, in the watchlist: "
      f"{[t for t, _ in zero_payers if t in set(watchlist)]}")

print("\n" + "=" * 78)
print("Q5  the watchlist names with NO dividend column")
print("=" * 78)
print(f"  n={len(wl_nodiv)}: {sorted(wl_nodiv)}")
