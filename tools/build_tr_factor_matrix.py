#!/usr/bin/env python3
"""Rebuild the momentum factor library on the TOTAL-RETURN series.

Window conventions are byte-for-byte the ones in
  <scratchpad>/mom-lib/build_factor_matrix.py
so the only thing that changes is WHICH price series feeds them. Every factor
is built TWICE -- once on tr_close (suffix `_tr`, the real thing) and once on
raw close (suffix `_px`, the control) -- in ONE frame, so the price-vs-TR
comparison is exactly paired on (date, ticker) with no merge and no
sample-composition difference.

READ-ONLY on the umbrella: this reads only the already-built
total_return_close.parquet plus the strategy config for the sector map.

  mom_n         = c[t]/c[t-n] - 1                     needs pos >= n
  mom_12_1      = c[t-20]/c[t-250] - 1                needs pos >= 250
  mom_6_1       = c[t-20]/c[t-120] - 1                needs pos >= 120
  mom_12_2      = c[t-40]/c[t-250] - 1                needs pos >= 250
  hi52_prox     = c[t]/max(c[t-250..t])               251 bars inclusive
  ma200_ratio   = c[t]/mean(c[t-200..t])              201 bars inclusive
  vol_60/250    = std(simple ret, last n, ddof=1)*sqrt(252)
  beta_n_spy    = cov(r,r_spy,last n)/var(r_spy,last n), all n pairs present
  mdd_250       = min over c[t-250..t] of (c/running_max - 1)

NaN when the window is not fully available. No zero-fill, no ffill.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parent))
import raw_input_manifest  # noqa: E402

LIVE = Path("/Users/renhao/git/github/RenQuant")
CFG = (LIVE / ".subrepo_runtime" / "repos" / "renquant-strategy-104"
       / "configs" / "strategy_config.json")
OUT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
           "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/mom-total-return")
ANN = np.sqrt(252.0)
EMBARGO_DAYS, SCREEN_FRAC = 60, 0.60
BENCH = "SPY"

# Same raw-layer pin build_total_return_series.py checks. This script reads
# the same watchlist config for the universe/sector map, so it verifies the
# same manifest before constructing the factor matrix.
raw_input_manifest.verify_or_abort(raw_input_manifest.MOMENTUM_TOTAL_RETURN_PIN)

BASE = ["mom_20", "mom_60", "mom_120", "mom_250", "mom_12_1", "mom_6_1",
        "mom_12_2", "hi52_prox", "ma200_ratio", "vol_60", "vol_250",
        "beta_60_spy", "beta_250_spy", "mdd_250"]


def rolling_mdd(c: np.ndarray, win: int) -> np.ndarray:
    out = np.full(c.shape[0], np.nan)
    if c.shape[0] >= win:
        W = sliding_window_view(c, win)
        rmax = np.maximum.accumulate(W, axis=1)
        out[win - 1:] = (W / rmax - 1.0).min(axis=1)
    return out


def factors(c: pd.Series, spy_ret: pd.Series | None, sfx: str) -> pd.DataFrame:
    o = pd.DataFrame(index=c.index)
    lag = c.shift
    for w in (20, 60, 120, 250):
        o[f"mom_{w}{sfx}"] = c / lag(w) - 1.0
    o[f"mom_12_1{sfx}"] = lag(20) / lag(250) - 1.0
    o[f"mom_6_1{sfx}"] = lag(20) / lag(120) - 1.0
    o[f"mom_12_2{sfx}"] = lag(40) / lag(250) - 1.0
    o[f"hi52_prox{sfx}"] = c / c.rolling(251, min_periods=251).max()
    o[f"ma200_ratio{sfx}"] = c / c.rolling(201, min_periods=201).mean()
    r = c.pct_change()
    o[f"vol_60{sfx}"] = r.rolling(60, min_periods=60).std(ddof=1) * ANN
    o[f"vol_250{sfx}"] = r.rolling(250, min_periods=250).std(ddof=1) * ANN
    if spy_ret is not None:
        rs = spy_ret.reindex(c.index)
        both = r.notna() & rs.notna()
        for w in (60, 250):
            beta = (r.rolling(w, min_periods=w).cov(rs)
                    / rs.rolling(w, min_periods=w).var(ddof=1))
            o[f"beta_{w}_spy{sfx}"] = beta.where(
                both.rolling(w, min_periods=w).sum() == w)
    else:
        o[f"beta_60_spy{sfx}"] = np.nan
        o[f"beta_250_spy{sfx}"] = np.nan
    o[f"mdd_250{sfx}"] = rolling_mdd(c.to_numpy(), 251)
    return o


tr = pd.read_parquet(OUT / "total_return_close.parquet")
tr["date"] = pd.to_datetime(tr["date"])
cfg = json.loads(CFG.read_text())
sector_map = cfg.get("sector_map") or {}
wl = [t for t in cfg["watchlist"] if t in set(tr.ticker)]

wide = {t: g.set_index("date")[["close", "tr_close"]].sort_index()
        for t, g in tr.groupby("ticker", observed=True)}
spy_tr = wide[BENCH]["tr_close"].pct_change()
spy_px = wide[BENCH]["close"].pct_change()
print(f"universe={len(wl)}  bench={BENCH}")

div_wide = {t: g.set_index("date")["dividend"].sort_index()
            for t, g in tr.groupby("ticker", observed=True)}

frames = []
for t in wl:
    w = wide[t]
    f_tr = factors(w["tr_close"], spy_tr, "_tr")
    f_px = factors(w["close"], spy_px, "_px")
    f = pd.concat([f_tr, f_px], axis=1)
    # §5b NAIVE BASELINE COLUMN: trailing 12-month cash dividend yield.
    # sum(dividend[t-251..t]) / close[t]; 252 bars inclusive, NaN before that.
    # Strictly backward-looking, same source column the adjustment uses.
    f["div_yield_252"] = (div_wide[t].rolling(252, min_periods=252).sum()
                          / w["close"])
    f["ticker"] = t
    f["sector"] = sector_map.get(t)
    f["n_bars_available"] = np.arange(1, len(w) + 1, dtype="int32")
    frames.append(f)

panel = pd.concat(frames).rename_axis("date").reset_index()

dates = np.sort(panel["date"].unique())
n_screen = int(np.floor(SCREEN_FRAC * len(dates)))
lut = {}
for d in dates[:n_screen]:
    lut[d] = "screen"
for d in dates[n_screen:n_screen + EMBARGO_DAYS]:
    lut[d] = "embargo"
for d in dates[n_screen + EMBARGO_DAYS:]:
    lut[d] = "holdout"
panel["split"] = panel["date"].map(lut)

cols = (["date", "ticker", "sector", "n_bars_available", "split",
         "div_yield_252"]
        + [f"{b}_tr" for b in BASE] + [f"{b}_px" for b in BASE])
panel = panel[cols].sort_values(["date", "ticker"]).reset_index(drop=True)
for c in ("ticker", "sector", "split"):
    panel[c] = panel[c].astype("string")
assert panel["split"].notna().all()

dest = OUT / "momentum_factor_matrix_tr.parquet"
panel.to_parquet(dest, index=False, compression="zstd")
sha = hashlib.sha256(dest.read_bytes()).hexdigest()
print(f"[WROTE] {dest}\n  shape={panel.shape}  sha256={sha}")

# ============================ VALIDATION ====================================
print("\n" + "=" * 78)
print("W1  HAND AUDIT of mom_12_1_tr against the TR series (3 dates, AAPL)")
print("=" * 78)
c = wide["AAPL"]["tr_close"]
sub = panel[panel.ticker == "AAPL"].set_index("date")
worst = 0.0
for i in (300, 1500, len(c) - 1):
    d = c.index[i]
    hand = c.iloc[i - 20] / c.iloc[i - 250] - 1.0
    got = float(sub.loc[d, "mom_12_1_tr"])
    worst = max(worst, abs(hand - got))
    print(f"  {d.date()}  tr[t-20]={c.iloc[i-20]:>10.4f} "
          f"tr[t-250]={c.iloc[i-250]:>10.4f}  hand={hand:+.10f} "
          f"matrix={got:+.10f}  d={abs(hand-got):.2e}")
assert worst < 1e-12
print(f"  -> max error {worst:.2e} < 1e-12")

print("\n" + "=" * 78)
print("W2  the _px twin must REPRODUCE the pinned price-only library exactly")
print("    (proves the only change is the input series, not the code)")
print("=" * 78)
old_p = (OUT.parent / "mom-lib" / "momentum_factor_matrix.parquet")
old = pd.read_parquet(old_p)
old["date"] = pd.to_datetime(old["date"])
print(f"  old library sha256="
      f"{hashlib.sha256(old_p.read_bytes()).hexdigest()[:16]}...  rows={len(old)}")
j = panel.merge(old, on=["date", "ticker"], how="inner", suffixes=("", "_old"))
print(f"  paired rows={len(j):,}")
print(f"  {'factor':<16}{'n both':>10}{'max|px - old|':>16}{'identical':>11}")
ok = True
for b in BASE:
    a, o = j[f"{b}_px"], j[b]
    m = a.notna() & o.notna()
    mx = float((a[m] - o[m]).abs().max()) if m.any() else float("nan")
    same = bool(m.any() and mx == 0.0)
    ok &= same
    print(f"  {b:<16}{int(m.sum()):>10,}{mx:>16.3e}{str(same):>11}")
print(f"  -> all identical: {ok}")

print("\n" + "=" * 78)
print("W3  DID THE ADJUSTMENT ACTUALLY MOVE THE FACTORS? (else it is inert)")
print("=" * 78)
print(f"  {'factor':<16}{'n':>9}{'mean(tr-px)':>14}{'p50':>11}{'p99':>11}"
      f"{'spearman':>11}{'moved%':>9}")
for b in BASE:
    a, o = panel[f"{b}_tr"], panel[f"{b}_px"]
    m = a.notna() & o.notna()
    d = (a[m] - o[m])
    print(f"  {b:<16}{int(m.sum()):>9,}{d.mean():>+14.5f}{d.median():>+11.5f}"
          f"{d.quantile(.99):>+11.5f}"
          f"{a[m].corr(o[m], method='spearman'):>11.5f}"
          f"{(d.abs() > 1e-12).mean():>9.1%}")
print("\n  the momentum factors MUST shift up by the window's accumulated yield;")
print("  vol/beta/mdd should barely move; hi52_prox/ma200_ratio shift up a little")
print("  because a TR series trends up more steeply than its price series.")

print("\n" + "=" * 78)
print("W4  NON-PAYER NEGATIVE CONTROL, at the FACTOR level")
print("=" * 78)
# An earlier version of this check asserted ALL factors identical for a
# non-payer and FAILED on beta_*_spy (max 5.686e-01). That failure was in the
# CHECK, not the data: beta is a two-legged statistic and the BENCHMARK leg is
# SPY, which is itself a dividend payer (42 events). So beta_tr != beta_px for a
# non-payer is REQUIRED, not a defect. Split the factors accordingly.
OWN = [b for b in BASE if not b.startswith("beta_")]
BENCH_DEP = [b for b in BASE if b.startswith("beta_")]
nonpayers = sorted(set(tr.loc[tr.groupby('ticker', observed=True)['dividend']
                              .transform('max') == 0, 'ticker']))
np_panel = panel[panel.ticker.isin(nonpayers)]
print(f"  non-payers={len(nonpayers)}  rows={len(np_panel):,}")
worst_np, worst_f = 0.0, None
for b in OWN:
    a, o = np_panel[f"{b}_tr"], np_panel[f"{b}_px"]
    m = a.notna() & o.notna()
    mx = float((a[m] - o[m]).abs().max()) if m.any() else 0.0
    if mx > worst_np:
        worst_np, worst_f = mx, b
print(f"  (a) OWN-SERIES factors ({len(OWN)}: {', '.join(OWN)})")
print(f"      max|tr - px| = {worst_np:.3e}  (worst: {worst_f})   MUST be 0")
assert worst_np == 0.0, "a non-payer's own-series factor moved"
print("      -> PASS: exactly 0.")
print(f"  (b) BENCHMARK-DEPENDENT factors ({', '.join(BENCH_DEP)})")
for b in BENCH_DEP:
    a, o = np_panel[f"{b}_tr"], np_panel[f"{b}_px"]
    m = a.notna() & o.notna()
    print(f"      {b:<14} max|tr - px| = {float((a[m]-o[m]).abs().max()):.4f}  "
          f"EXPECTED non-zero: the SPY leg is dividend-adjusted")
print("  -> the adjustment cannot move a non-payer through its OWN series; it")
print("     moves its beta only via the benchmark, which is correct.")

print("\n" + "=" * 78)
print("W5  NON-NULL RATES / SPLITS")
print("=" * 78)
print(f"  rows={len(panel):,} tickers={panel.ticker.nunique()} "
      f"dates={len(dates)} {panel.date.min().date()}..{panel.date.max().date()}")
for b in ("mom_12_1", "mom_6_1", "hi52_prox", "ma200_ratio", "vol_250"):
    print(f"  {b:<14} non-null _tr={panel[f'{b}_tr'].notna().mean():.4f} "
          f"_px={panel[f'{b}_px'].notna().mean():.4f}")
print(f"  sector non-null={panel.sector.notna().mean():.4f}")
print(f"  div_yield_252 non-null={panel.div_yield_252.notna().mean():.4f}  "
      f"mean={panel.div_yield_252.mean():.5f}  p50={panel.div_yield_252.median():.5f}  "
      f"p99={panel.div_yield_252.quantile(.99):.5f}  max={panel.div_yield_252.max():.5f}")
print(f"  div_yield_252 == 0 (non-payers) rate={(panel.div_yield_252==0).mean():.4f}")
for nm in ("screen", "embargo", "holdout"):
    s = panel[panel.split == nm]
    print(f"  {nm:<9} dates={s.date.nunique():>5} rows={len(s):>7,} "
          f"{s.date.min().date()}..{s.date.max().date()}")

(OUT / "04_tr_matrix_metadata.json").write_text(json.dumps({
    "built_utc": pd.Timestamp.utcnow().isoformat(),
    "sha256": sha,
    "source": str(OUT / "total_return_close.parquet"),
    "tr_formula": "TR[t] = close[t]/prod_{s>t}(1+dividend[s]/close[s])",
    "n_rows": int(len(panel)), "n_tickers": int(panel.ticker.nunique()),
    "n_dates": int(len(dates)),
    "px_twin_reproduces_pinned_library": bool(ok),
    "nonpayer_factor_max_abs_diff": worst_np,
    "factors_tr": [f"{b}_tr" for b in BASE],
    "factors_px": [f"{b}_px" for b in BASE],
    "baseline_column": "div_yield_252 = sum(dividend[t-251..t]) / close[t], 252 bars inclusive",
    "split": {k: [str(pd.Timestamp(v[0]).date()), str(pd.Timestamp(v[-1]).date())]
              for k, v in (("screen", dates[:n_screen]),
                           ("embargo", dates[n_screen:n_screen + EMBARGO_DAYS]),
                           ("holdout", dates[n_screen + EMBARGO_DAYS:]))},
}, indent=2))
print(f"\n[WROTE] {OUT/'04_tr_matrix_metadata.json'}")
