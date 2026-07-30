#!/usr/bin/env python3
"""Build a dividend-adjusted TOTAL-RETURN close series per ticker, and VALIDATE it.

READ-ONLY on /Users/renhao/git/github/RenQuant. Every output goes to OUT.

================================ THE FORMULA =================================
For each ex-dividend date s (the date the `dividend` column is > 0 -- proven to
be the EX-date in 00_dividend_semantics.py, step [4]) define the per-event
gross-up factor

        g[s] = 1 + D[s] / P[s]                 (P = raw split-adjusted close)

and the BACKWARD-CUMULATIVE adjustment factor, anchored so the most recent bar
is left at its true traded price:

        R[t] = prod_{s > t} g[s]      (empty product = 1 at the last bar)
        TR[t] = P[t] / R[t]

Then for ANY adjacent pair the simple return of TR is the EXACT total return:

        TR[k]/TR[k-1] = (P[k]/P[k-1]) * g[k] = (P[k] + D[k]) / P[k-1]

which is the return to an investor who held from close k-1 through the ex-date.
(Proof, single event at k: R[k-1] = g[k], R[k] = 1, so
 TR[k]/TR[k-1] = P[k] / (P[k-1]/g[k]) = (P[k] + D[k])/P[k-1].)

WHY THIS IS RIGHT FOR RETURNS AND NOT FOR LEVELS. The factor is a *ratio*
correction: over any window containing no event it is a single multiplicative
per-ticker constant, so it cancels out of every return, ratio and rank; over a
window containing events it injects exactly the reinvested cash. Because we
anchor R = 1 at the LAST bar, TR[t] for old t is a rebased index, NOT a price
anybody ever paid -- it is systematically BELOW the historical close. So the
series is valid for momentum / volatility / beta / drawdown (all ratio-based)
and invalid for anything denominated in dollars: share counts, "was it above
$50", round-lot maths, tax lots. That is why this is built as a research series
in scratch and is NOT written back into the corpus.

Note also g uses P[s] (the post-drop close on the ex-date), NOT P[s-1]. The
P[s-1] variant (what Yahoo's adj_close does) is a first-order approximation and
is NOT exact; using P[s] makes the identity above hold to machine precision,
which validation V3 checks on all events.

============================== THE VALIDATIONS ===============================
V1  ex-div-day test re-run on TR. The raw -66.7bp gap must collapse to ~0.
V2  NEGATIVE CONTROL: names that paid nothing must be numerically IDENTICAL.
V3  exactness: TR[k]/TR[k-1] == (P[k]+D[k])/P[k-1] on every event.
V4  yield-slope: regress ex-div-day return on event yield. Raw slope must be
    ~ -1 (bigger dividend, bigger drop); TR slope must be ~ 0. Much sharper
    than V1's mean gap because it is per-event.
V5  INDEPENDENT CROSS-CHECK against the vendor's own `adj close` on the 6
    watchlist files that happen to carry both columns. Not self-referential.
V6  V1 with ticker AND date fixed effects, to separate a real adjustment
    failure from the composition/calendar tilt of who pays dividends when.
V7  economic sanity: TR CAGR - price CAGR must equal the realised average
    dividend yield, per ticker.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import raw_input_manifest  # noqa: E402

LIVE = Path("/Users/renhao/git/github/RenQuant")
OHLCV = LIVE / "data" / "ohlcv"
CFG = (LIVE / ".subrepo_runtime" / "repos" / "renquant-strategy-104"
       / "configs" / "strategy_config.json")
OUT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
           "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/mom-total-return")
BENCH = "SPY"

# Raw-layer reproducibility: aborts if the 145-ticker watchlist corpus this
# script is about to read no longer matches the pinned manifest (see
# raw_input_manifest.py's module docstring for why a pin on the DERIVED
# parquet this script writes is not enough).
raw_input_manifest.verify_or_abort(raw_input_manifest.MOMENTUM_TOTAL_RETURN_PIN)

WATCHLIST = list(json.loads(CFG.read_text())["watchlist"])
UNIVERSE = WATCHLIST + [BENCH]


# ------------------------------------------------------------------ loading --
def _schema(t):
    return set(pq.read_schema(OHLCV / t / "1d.parquet").names)


def load_raw(t: str):
    """close + dividend (+ vendor adj_close when present). NEVER writes."""
    p = OHLCV / t / "1d.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index = df.index.normalize()
    df.index.name = "date"
    out = pd.DataFrame(index=df.index)
    out["close"] = df["close"].astype("float64")
    # `dividend` absent  ==>  no dividend events recorded for this name.
    # Sentinel for "no event" is EXACTLY 0.0 (98.26% of rows), not 1.0 and not
    # NaN -- measured, not assumed. NaN occurs only as a contiguous TAIL on
    # ATI/BA/INTC (253 rows each) and in every case follows >=1yr of explicit
    # zeros, so filling 0.0 is recorded, bounded and safe.
    if "dividend" in df.columns:
        d = df["dividend"].astype("float64")
        n_nan = int(d.isna().sum())
        out["dividend"] = d.fillna(0.0)
        out.attrs["has_div_col"] = True
    else:
        out["dividend"] = 0.0
        n_nan = 0
        out.attrs["has_div_col"] = False
    out.attrs["n_div_nan_filled"] = n_nan
    ac = [c for c in df.columns if c.lower().replace("_", " ") == "adj close"]
    if ac:
        out["vendor_adj_close"] = df[ac[0]].astype("float64")
    return out.dropna(subset=["close"])


# ------------------------------------------------------------ the adjustment --
def total_return_close(close: pd.Series, dividend: pd.Series) -> pd.Series:
    """TR[t] = P[t] / prod_{s>t} (1 + D[s]/P[s]).  See module docstring."""
    p = close.to_numpy(dtype="float64")
    d = dividend.reindex(close.index).fillna(0.0).to_numpy(dtype="float64")

    if np.any(d < 0):
        raise ValueError("negative dividend")
    bad = (d > 0) & ~(np.isfinite(p) & (p > 0))
    if bad.any():
        raise ValueError(f"dividend on a bar with unusable close ({bad.sum()} bars)")

    g = np.ones_like(p)
    ev = d > 0
    g[ev] = 1.0 + d[ev] / p[ev]
    if np.any(g <= 0) or not np.all(np.isfinite(g)):
        raise ValueError("non-positive / non-finite gross-up factor")

    # R[t] = prod of g over s > t ; R[last] = 1 (empty product)
    R = np.ones_like(p)
    if len(p) > 1:
        R[:-1] = np.cumprod(g[::-1])[::-1][1:]
    return pd.Series(p / R, index=close.index, name="tr_close")


# --------------------------------------------------------------------- build --
print("=" * 78)
print("BUILD")
print("=" * 78)
series, meta = {}, {}
for t in UNIVERSE:
    raw = load_raw(t)
    if raw is None:
        print(f"  MISSING {t}")
        continue
    tr = total_return_close(raw["close"], raw["dividend"])
    series[t] = raw.assign(tr_close=tr)
    n_ev = int((raw["dividend"] > 0).sum())
    meta[t] = {
        "bars": int(len(raw)),
        "has_div_col": bool(raw.attrs["has_div_col"]),
        "n_div_nan_filled": int(raw.attrs["n_div_nan_filled"]),
        "n_events": n_ev,
        "total_div_paid": float(raw["dividend"].sum()),
        "caf_first": float(tr.iloc[0] / raw["close"].iloc[0]),
        "caf_last": float(tr.iloc[-1] / raw["close"].iloc[-1]),
    }
payers = [t for t in series if meta[t]["n_events"] > 0]
nonpayers = [t for t in series if meta[t]["n_events"] == 0]
print(f"  built {len(series)} series  ({len(payers)} payers / "
      f"{len(nonpayers)} non-payers)")
print(f"  SPY events={meta[BENCH]['n_events']}  "
      f"SPY caf_first={meta[BENCH]['caf_first']:.6f}   "
      f"<-- the BENCHMARK is adjusted too; the label is excess-vs-SPY, so "
      f"leaving SPY on price would inject its ~1.3%/yr yield into every name")
assert abs(meta[BENCH]["caf_last"] - 1.0) < 1e-15, "anchor broken"

# ============================================================== V3 exactness ==
print("\n" + "=" * 78)
print("V3  EXACTNESS  TR[k]/TR[k-1] == (P[k]+D[k])/P[k-1] on every event")
print("=" * 78)
worst, n_ev_tot = 0.0, 0
for t in payers:
    s = series[t]
    p, d, tr = s["close"], s["dividend"], s["tr_close"]
    ev = (d > 0) & p.shift(1).notna()
    lhs = (tr / tr.shift(1))[ev]
    rhs = ((p + d) / p.shift(1))[ev]
    if len(lhs):
        worst = max(worst, float((lhs - rhs).abs().max()))
        n_ev_tot += int(len(lhs))
print(f"  events checked = {n_ev_tot:,}")
print(f"  max |TR ratio - exact total-return ratio| = {worst:.3e}")
assert worst < 1e-12, "the identity does not hold -- the construction is wrong"
print("  -> holds to machine precision. The construction is EXACT, not approximate.")

# ======================================================== V2 negative control ==
print("\n" + "=" * 78)
print("V2  NEGATIVE CONTROL -- non-payers must be NUMERICALLY IDENTICAL")
print("=" * 78)
print(f"  candidate non-payers in the universe: {len(nonpayers)}")
print("  NOTE, measured in 00/01: every one of the 111 watchlist files that")
print("  CARRIES a `dividend` column has >=1 positive event, so a 'column")
print("  present but all zeros' control does not exist in this universe.")
print("  The non-payers are therefore the 34 names with no `dividend` column.")
ctrl = [t for t in ["TSLA", "AMZN", "NFLX"] if t in nonpayers] or nonpayers[:3]
print(f"\n  the 3 declared control names: {ctrl}")
allmax = 0.0
for t in nonpayers:
    s = series[t]
    m = float((s["tr_close"] - s["close"]).abs().max())
    allmax = max(allmax, m)
    if t in ctrl:
        exact = bool((s["tr_close"].to_numpy() == s["close"].to_numpy()).all())
        print(f"    {t:<6} bars={len(s):>5}  max|new-old| = {m:.1f}   "
              f"bitwise-identical={exact}")
        assert m == 0.0 and exact, f"{t} moved -- adjustment is wrong"
print(f"\n  max|new-old| over ALL {len(nonpayers)} non-payers = {allmax:.1f}")
assert allmax == 0.0, "a non-payer moved"
print("  -> PASS: exactly 0. The adjustment cannot move a name that paid nothing.")
# and the converse: every payer MUST move
moved = [t for t in payers
         if float((series[t]["tr_close"] - series[t]["close"]).abs().max()) > 0]
print(f"  converse check: payers whose series moved = {len(moved)}/{len(payers)} "
      f"(all of them, else the adjustment is inert)")
assert len(moved) == len(payers)

# ================================================== V1 the ex-div-day re-test ==
print("\n" + "=" * 78)
print("V1  THE VALIDATION THAT MATTERS: ex-div-day gap on RAW vs TOTAL-RETURN")
print("=" * 78)


def exdiv_gap(col: str):
    ex, oth, yl = [], [], []
    for t in payers:
        if t == BENCH:
            continue
        s = series[t]
        r = s[col].pct_change()
        isex = s["dividend"] > 0
        m = r.notna()
        ex.append(r[isex & m].to_numpy())
        oth.append(r[~isex & m].to_numpy())
        yl.append((s["dividend"][isex & m] /
                   s["close"].shift(1)[isex & m]).to_numpy())
    ex, oth, yl = np.concatenate(ex), np.concatenate(oth), np.concatenate(yl)
    diff = ex.mean() - oth.mean()
    se = np.sqrt(ex.var(ddof=1) / len(ex) + oth.var(ddof=1) / len(oth))
    return dict(n_ex=len(ex), n_oth=len(oth), ex_bp=ex.mean() * 1e4,
                oth_bp=oth.mean() * 1e4, diff_bp=diff * 1e4, se_bp=se * 1e4,
                t=diff / se, yield_bp=yl.mean() * 1e4)


g_raw = exdiv_gap("close")
g_tr = exdiv_gap("tr_close")
hdr = f"  {'series':<16}{'ex-div bp':>11}{'other bp':>11}{'GAP bp':>10}{'SE':>7}{'t':>8}"
print(hdr)
print(f"  {'raw close':<16}{g_raw['ex_bp']:>+11.1f}{g_raw['oth_bp']:>+11.1f}"
      f"{g_raw['diff_bp']:>+10.1f}{g_raw['se_bp']:>7.1f}{g_raw['t']:>+8.2f}")
print(f"  {'total-return':<16}{g_tr['ex_bp']:>+11.1f}{g_tr['oth_bp']:>+11.1f}"
      f"{g_tr['diff_bp']:>+10.1f}{g_tr['se_bp']:>7.1f}{g_tr['t']:>+8.2f}")
print(f"\n  ex-div days={g_raw['n_ex']:,}  other days={g_raw['n_oth']:,}  "
      f"mean per-event yield={g_raw['yield_bp']:+.1f} bp")
print(f"  GAP: {g_raw['diff_bp']:+.1f} bp (t={g_raw['t']:+.1f})  ->  "
      f"{g_tr['diff_bp']:+.1f} bp (t={g_tr['t']:+.2f})   "
      f"COLLAPSE = {abs(g_raw['diff_bp']) - abs(g_tr['diff_bp']):+.1f} bp "
      f"({1 - abs(g_tr['diff_bp'])/abs(g_raw['diff_bp']):.1%} of the gap removed)")

# ==================================================== V4 the yield-slope test ==
print("\n" + "=" * 78)
print("V4  YIELD-SLOPE (per-event, sharper than V1's mean): regress the")
print("    ex-div-day return on the event yield. raw ~ -1, adjusted ~ 0.")
print("=" * 78)
rows = []
for t in payers:
    if t == BENCH:
        continue
    s = series[t]
    isex = (s["dividend"] > 0) & s["close"].shift(1).notna()
    rows.append(pd.DataFrame({
        "yld": (s["dividend"] / s["close"].shift(1))[isex].to_numpy(),
        "r_raw": s["close"].pct_change()[isex].to_numpy(),
        "r_tr": s["tr_close"].pct_change()[isex].to_numpy()}))
E = pd.concat(rows, ignore_index=True).dropna()
for lbl, col in (("raw close", "r_raw"), ("total-return", "r_tr")):
    x = E["yld"].to_numpy()
    y = E[col].to_numpy()
    b, a = np.polyfit(x, y, 1)
    resid = y - (a + b * x)
    sb = np.sqrt((resid @ resid) / (len(x) - 2) / ((x - x.mean()) @ (x - x.mean())))
    print(f"  {lbl:<14} slope = {b:+.4f}  (SE {sb:.4f}, t={b/sb:+.2f})   "
          f"intercept = {a*1e4:+.1f} bp")
print("  -> raw slope near -1 = the dividend is fully missing from the close.")
print("     TR slope near 0    = it is fully restored, per unit of dividend.")

# ============================================ V6 gap with ticker+date FE ======
print("\n" + "=" * 78)
print("V6  V1 AGAIN with TICKER and DATE fixed effects. Isolates the")
print("    adjustment from the composition tilt of WHO pays and WHEN.")
print("=" * 78)
frs = []
for t in payers:
    if t == BENCH:
        continue
    s = series[t]
    frs.append(pd.DataFrame({"ticker": t, "date": s.index,
                             "r_raw": s["close"].pct_change().to_numpy(),
                             "r_tr": s["tr_close"].pct_change().to_numpy(),
                             "isex": (s["dividend"] > 0).to_numpy()}))
P = pd.concat(frs, ignore_index=True).dropna(subset=["r_raw", "r_tr"])
for lbl, col in (("raw close", "r_raw"), ("total-return", "r_tr")):
    v = P[col] - P.groupby("date")[col].transform("mean")
    v = v - v.groupby(P["ticker"]).transform("mean")
    a, b = v[P.isex], v[~P.isex]
    d = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    print(f"  {lbl:<14} demeaned gap = {d*1e4:+.1f} bp  (SE {se*1e4:.1f}, "
          f"t={d/se:+.2f})   n_ex={len(a):,}")
print("  -> the FE version is the decisive one: it asks whether an ex-div day is")
print("     special for THAT name relative to the SAME day's cross-section.")

# ============================ V5 independent vendor adj_close cross-check =====
print("\n" + "=" * 78)
print("V5  INDEPENDENT CROSS-CHECK vs the vendor's own `adj close`")
print("    (only on files that happen to carry both columns -- not self-made)")
print("=" * 78)
both = [t for t in series if "vendor_adj_close" in series[t].columns
        and meta[t]["n_events"] > 0]
print(f"  files with both `adj close` and `dividend`: {len(both)} -> {both}")
print(f"  {'ticker':<7}{'events':>7}{'corr(dlogTR,dlogVendor)':>26}"
      f"{'mean|ret diff| bp':>19}{'max|ret diff| bp':>18}")
v5 = {}
for t in both:
    s = series[t]
    a = s["tr_close"].pct_change()
    b = s["vendor_adj_close"].pct_change()
    m = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
    c = float(a[m].corr(b[m]))
    dd = (a[m] - b[m]).abs()
    v5[t] = {"corr": c, "mean_abs_bp": float(dd.mean() * 1e4),
             "max_abs_bp": float(dd.max() * 1e4)}
    print(f"  {t:<7}{meta[t]['n_events']:>7}{c:>26.6f}"
          f"{dd.mean()*1e4:>19.3f}{dd.max()*1e4:>18.1f}")
print("  -> a high corr with tiny mean|diff| means an INDEPENDENT writer, using")
print("     its own dividend feed, reproduces this series. Residual diffs are")
print("     expected: the vendor uses the D/P[s-1] approximation, not D/P[s].")

# ================================================= V7 economic sanity, CAGR ===
print("\n" + "=" * 78)
print("V7  ECONOMIC SANITY: TR CAGR - price CAGR must equal the realised yield")
print("=" * 78)
rows = []
for t in payers:
    s = series[t]
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    if yrs < 3:
        continue
    cp = (s["close"].iloc[-1] / s["close"].iloc[0]) ** (1 / yrs) - 1
    ct = (s["tr_close"].iloc[-1] / s["tr_close"].iloc[0]) ** (1 / yrs) - 1
    realised = s["dividend"].sum() / s["close"].mean() / yrs
    rows.append((t, cp, ct, ct - cp, realised))
C = pd.DataFrame(rows, columns=["ticker", "cagr_px", "cagr_tr", "delta",
                                "avg_yield"])
print(f"  n={len(C)}  mean delta(TR-px) = {C.delta.mean():.4%}   "
       f"mean realised yield = {C.avg_yield.mean():.4%}")
print(f"  corr(delta, realised yield) = {C.delta.corr(C.avg_yield):.4f}")
print(f"  names where TR CAGR < price CAGR (must be ZERO): "
      f"{int((C.delta < -1e-12).sum())}")
assert int((C.delta < -1e-12).sum()) == 0
print("\n  largest 8 dividend contributions to CAGR:")
print(C.nlargest(8, "delta").to_string(index=False,
      float_format=lambda v: f"{v:.4%}"))
print(f"\n  SPY: price CAGR {(series[BENCH]['close'].iloc[-1]/series[BENCH]['close'].iloc[0])**(365.25/(series[BENCH].index[-1]-series[BENCH].index[0]).days)-1:.4%}"
      f"  TR CAGR {(series[BENCH]['tr_close'].iloc[-1]/series[BENCH]['tr_close'].iloc[0])**(365.25/(series[BENCH].index[-1]-series[BENCH].index[0]).days)-1:.4%}")

# ------------------------------------------------------------------- persist --
tr_df = pd.concat(
    [series[t][["close", "dividend", "tr_close"]].assign(ticker=t)
     for t in series], axis=0).reset_index()
tr_df = tr_df[["date", "ticker", "close", "dividend", "tr_close"]]
tr_df["ticker"] = tr_df["ticker"].astype("string")
dest = OUT / "total_return_close.parquet"
tr_df.to_parquet(dest, index=False, compression="zstd")
print(f"\n[WROTE] {dest}  shape={tr_df.shape}")

report = {
    "formula": "TR[t] = close[t] / prod_{s>t}(1 + dividend[s]/close[s]); anchor R=1 at last bar",
    "universe": len(series), "payers": len(payers), "nonpayers": len(nonpayers),
    "nonpayer_tickers": sorted(nonpayers),
    "control_names": ctrl,
    "V1_raw": g_raw, "V1_tr": g_tr,
    "V2_max_abs_diff_nonpayers": allmax,
    "V3_events": n_ev_tot, "V3_max_identity_error": worst,
    "V5": v5,
    "V7_mean_delta_cagr": float(C.delta.mean()),
    "V7_mean_realised_yield": float(C.avg_yield.mean()),
    "V7_corr": float(C.delta.corr(C.avg_yield)),
    "per_ticker": meta,
}
(OUT / "02_total_return_report.json").write_text(json.dumps(report, indent=2))
print(f"[WROTE] {OUT/'02_total_return_report.json'}")
