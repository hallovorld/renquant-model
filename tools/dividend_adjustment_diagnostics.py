#!/usr/bin/env python3
"""Two loose ends from 02, neither of which gets papered over.

A. V4's residual yield-slope is -0.409 (t=-5.4) on the TR series, not ~0.
   FIRST: note the +1.000 shift from raw (-1.409) to TR (-0.409) is an
   ALGEBRAIC IDENTITY, not evidence -- r_tr = r_raw + D/P[s-1] exactly, so
   slope(r_tr|yld) == slope(r_raw|yld) + 1 by construction. V4 as written
   therefore validates NOTHING. The real question is why the RAW slope is
   -1.409 rather than -1.0, i.e. what the extra -0.409*yield is.
   Hypotheses: (H1) composition -- high-yield events sit in names/dates that
   fell anyway; (H2) a few huge special dividends dominate an OLS slope;
   (H3) genuinely mis-dated events. Test with FE, with trimming, and by
   splitting out specials.

B. V5's independent cross-check silently produced NaN: the `adj close` column
   in those 6 files is 100% NaN. Search the WHOLE corpus for any file with a
   USABLE adj_close plus a dividend column, so the cross-check can be done
   somewhere, or reported as unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

LIVE = Path("/Users/renhao/git/github/RenQuant")
OHLCV = LIVE / "data" / "ohlcv"
OUT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
           "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/mom-total-return")
TR = pd.read_parquet(OUT / "total_return_close.parquet")
TR["date"] = pd.to_datetime(TR["date"])

print("=" * 78)
print("A. WHY IS THE RAW YIELD-SLOPE -1.41 AND NOT -1.0 ?")
print("=" * 78)
E = TR.sort_values(["ticker", "date"]).copy()
g = E.groupby("ticker", observed=True)
E["prev_close"] = g["close"].shift(1)
E["r_raw"] = g["close"].pct_change()
E["r_tr"] = g["tr_close"].pct_change()
E["yld"] = E["dividend"] / E["prev_close"]
ev = E[(E.dividend > 0) & E.r_raw.notna() & E.prev_close.notna()].copy()
print(f"  events = {len(ev):,}")


def slope(x, y, lbl):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    b, a = np.polyfit(x, y, 1)
    r = y - (a + b * x)
    sx = ((x - x.mean()) ** 2).sum()
    sb = np.sqrt((r @ r) / (len(x) - 2) / sx)
    print(f"    {lbl:<46} slope={b:+.4f} (SE {sb:.4f}, t={b/sb:+6.2f})  n={len(x):,}")
    return b


print("\n  [baseline, as in 02]")
slope(ev.yld, ev.r_raw, "raw  ~ yld")
slope(ev.yld, ev.r_tr, "TR   ~ yld   (== raw + 1 by identity)")

print("\n  H2: is an OLS slope dominated by a few huge specials?")
for cut in (0.03, 0.02, 0.015, 0.01):
    s = ev[ev.yld <= cut]
    slope(s.yld, s.r_tr, f"TR ~ yld, events with yld <= {cut:.1%}")
print("    (Costco's $7/$10/$15 specials and TSM's annual are the >3% tail)")

print("\n  H1: composition. Remove the same-DATE cross-sectional mean return")
print("      (a market/sector-day effect) and the per-TICKER mean, then re-fit.")
allr = E[E.r_raw.notna()].copy()
for col in ("r_raw", "r_tr"):
    dm = allr[col] - allr.groupby("date")[col].transform("mean")
    allr[col + "_fe"] = dm - dm.groupby(allr["ticker"]).transform("mean")
evfe = allr[(allr.dividend > 0) & allr.prev_close.notna()]
slope(evfe.yld, evfe.r_raw_fe, "raw, date+ticker demeaned ~ yld")
slope(evfe.yld, evfe.r_tr_fe, "TR,  date+ticker demeaned ~ yld")

print("\n  H1b: WITHIN-TICKER only (each name against its own mean event)")
w = ev.copy()
w["yld_c"] = w.yld - w.groupby("ticker", observed=True)["yld"].transform("mean")
w["r_c"] = w.r_tr - w.groupby("ticker", observed=True)["r_tr"].transform("mean")
slope(w.yld_c, w.r_c, "TR, within-ticker demeaned ~ within-ticker yld")

print("\n  H1c: BETWEEN-ticker (per-name means only) -- is the slope purely")
print("       a high-yield-names-did-worse effect?")
byt = ev.groupby("ticker", observed=True).agg(yld=("yld", "mean"),
                                             r_tr=("r_tr", "mean"))
slope(byt.yld, byt.r_tr, "TR per-ticker mean ~ per-ticker mean yld")

print("\n  robust view: median same-day TR return by yield quintile")
ev["q"] = pd.qcut(ev.yld, 5, labels=False)
print(ev.groupby("q").agg(n=("r_tr", "size"),
                          mean_yld_bp=("yld", lambda s: s.mean() * 1e4),
                          mean_r_tr_bp=("r_tr", lambda s: s.mean() * 1e4),
                          median_r_tr_bp=("r_tr", lambda s: s.median() * 1e4)
                          ).to_string(float_format=lambda v: f"{v:.1f}"))
print("\n  -> if the MEDIAN is flat across quintiles while the MEAN slopes, the")
print("     OLS slope is an outlier/heteroskedasticity artifact, not a")
print("     mis-specified adjustment.")

print("\n" + "=" * 78)
print("B. IS AN INDEPENDENT vendor adj_close CROSS-CHECK AVAILABLE ANYWHERE?")
print("=" * 78)
usable = []
n_ac, n_ac_allnan = 0, 0
for p in sorted(OHLCV.iterdir()):
    f = p / "1d.parquet"
    if not f.exists():
        continue
    try:
        names = pq.read_schema(f).names
    except Exception:
        continue
    ac = [c for c in names if c.lower().replace("_", " ") == "adj close"]
    if not ac or "dividend" not in names:
        continue
    n_ac += 1
    d = pd.read_parquet(f, columns=[ac[0], "close", "dividend"])
    if d[ac[0]].isna().all():
        n_ac_allnan += 1
        continue
    if (d["dividend"] > 0).any():
        usable.append((p.name, ac[0], int(d[ac[0]].notna().sum()),
                       int((d["dividend"] > 0).sum())))
print(f"  files with adj_close AND dividend      : {n_ac}")
print(f"  ... of which adj_close is 100% NaN     : {n_ac_allnan}")
print(f"  ... USABLE (adj_close has data + events): {len(usable)}")
print(f"  {usable[:20]}")

if usable:
    print("\n  cross-check on the usable files:")
    print(f"  {'ticker':<8}{'events':>7}{'corr':>12}{'mean|diff| bp':>15}"
          f"{'max|diff| bp':>14}")
    for t, ac, _, nev in usable[:12]:
        d = pd.read_parquet(OHLCV / t / "1d.parquet")
        d.index = pd.to_datetime(d.index)
        d = d[~d.index.duplicated(keep="last")].sort_index()
        div = d["dividend"].fillna(0.0)
        p_ = d["close"].astype(float)
        gg = np.ones(len(p_))
        m = (div > 0).to_numpy()
        gg[m] = 1 + div.to_numpy()[m] / p_.to_numpy()[m]
        R = np.ones(len(p_))
        R[:-1] = np.cumprod(gg[::-1])[::-1][1:]
        mine = pd.Series(p_.to_numpy() / R, index=p_.index)
        a = mine.pct_change()
        b = d[ac].astype(float).pct_change(fill_method=None)
        k = a.notna() & b.notna()
        dd = (a[k] - b[k]).abs()
        print(f"  {t:<8}{nev:>7}{a[k].corr(b[k]):>12.6f}"
              f"{dd.mean()*1e4:>15.4f}{dd.max()*1e4:>14.2f}")
else:
    print("\n  -> NO independent vendor-adjusted series exists in this corpus.")
    print("     The `adj close` column is present in 2,548 files but is 100%")
    print("     NaN wherever a `dividend` column also exists, so it cannot")
    print("     corroborate the construction. REPORTED AS UNAVAILABLE.")
