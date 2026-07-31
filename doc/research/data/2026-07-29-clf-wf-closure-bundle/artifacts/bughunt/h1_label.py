"""H1 — reconstruct fwd_60d_excess from raw OHLCV closes + SPY and compare to stored.

READ-ONLY. Tests: (a) is the label forward-looking over (d, d+60 trading days]?
(b) does the CLEAN panel preserve the same date alignment as the RAW sidecar?
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

OHLCV = Path("/Users/renhao/git/github/RenQuant/data/ohlcv")
CLEAN = Path("/Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet")
RAW = Path("/Users/renhao/git/github/RenQuant/data/"
           "alpha158_291_fundamental_dataset_rawlabel.parquet")
OUT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator/"
           "428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/bughunt")
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(str(s))


def closes(t):
    d = pd.read_parquet(OHLCV / t / "1d.parquet")["close"]
    d.index = pd.to_datetime(d.index)
    return d


def main():
    clean = pd.read_parquet(CLEAN, columns=["date", "ticker", "fwd_60d_excess"])
    clean["date"] = pd.to_datetime(clean["date"])
    raw = pd.read_parquet(RAW, columns=["date", "ticker", "fwd_60d_excess",
                                        "fwd_60d_excess_raw"])
    raw["date"] = pd.to_datetime(raw["date"])
    spy = closes("SPY")

    log("=" * 100)
    log("H1 — FIRST-PRINCIPLES LABEL RECONSTRUCTION FROM OHLCV")
    log("=" * 100)
    log(f"  clean panel rows={len(clean):,}  raw sidecar rows={len(raw):,}")
    log(f"  clean fwd_60d_excess: mean={clean['fwd_60d_excess'].mean():+.5f} "
        f"std={clean['fwd_60d_excess'].std():.5f} "
        f"min={clean['fwd_60d_excess'].min():+.4f} max={clean['fwd_60d_excess'].max():+.4f}")
    log(f"  raw   fwd_60d_excess_raw: mean={raw['fwd_60d_excess_raw'].mean():+.5f} "
        f"std={raw['fwd_60d_excess_raw'].std():.5f} "
        f"min={raw['fwd_60d_excess_raw'].min():+.4f} max={raw['fwd_60d_excess_raw'].max():+.4f}")

    tickers = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "KO"]
    probe_dates = [pd.Timestamp(x) for x in
                   ["2019-03-15", "2021-06-10", "2023-11-02", "2024-07-01", "2025-02-14"]]

    log("")
    log("  RECONSTRUCTION: excess_fwd60(d) = (P[t+60]/P[t]-1) - (SPY[t+60]/SPY[t]-1)")
    log("  on the ticker's own trading-day index (offset = +60 rows, forward).")
    log("")
    log(f"  {'ticker':>7}{'date':>13}{'recon_+60':>12}{'raw_stored':>12}{'clean_stored':>14}"
        f"{'recon_-60':>12}{'recon_+59':>12}{'recon_+61':>12}")
    hits = {"p60": 0, "m60": 0, "p59": 0, "p61": 0, "n": 0}
    for t in tickers:
        try:
            c = closes(t)
        except Exception as e:
            log(f"  {t}: no OHLCV ({e})")
            continue
        cs = c.reindex(spy.index).dropna()
        s = spy.reindex(cs.index)
        for d in probe_dates:
            if d not in cs.index:
                continue
            i = cs.index.get_loc(d)

            def rec(off):
                j = i + off
                if j < 0 or j >= len(cs):
                    return np.nan
                return (cs.iloc[j] / cs.iloc[i] - 1) - (s.iloc[j] / s.iloc[i] - 1)

            rv = raw[(raw.ticker == t) & (raw.date == d)]["fwd_60d_excess_raw"]
            cv = clean[(clean.ticker == t) & (clean.date == d)]["fwd_60d_excess"]
            rv = float(rv.iloc[0]) if len(rv) else np.nan
            cv = float(cv.iloc[0]) if len(cv) else np.nan
            r60, rm60, r59, r61 = rec(60), rec(-60), rec(59), rec(61)
            log(f"  {t:>7}{str(d.date()):>13}{r60:>+12.5f}{rv:>+12.5f}{cv:>+14.5f}"
                f"{rm60:>+12.5f}{r59:>+12.5f}{r61:>+12.5f}")
            if np.isfinite(rv):
                hits["n"] += 1
                for k, val in (("p60", r60), ("m60", rm60), ("p59", r59), ("p61", r61)):
                    if np.isfinite(val) and abs(val - rv) < 1e-6:
                        hits[k] += 1
    log("")
    log(f"  EXACT (<1e-6) matches to the stored RAW label out of n={hits['n']} probes:")
    log(f"    forward +60 rows : {hits['p60']}      backward -60 rows: {hits['m60']}")
    log(f"    forward +59 rows : {hits['p59']}      forward  +61 rows: {hits['p61']}")

    # ---- alignment of CLEAN vs RAW on the shared keys
    log("")
    log("=" * 100)
    log("H1b — CLEAN (standardised) vs RAW sidecar: same date alignment?")
    log("=" * 100)
    cl = clean.rename(columns={"fwd_60d_excess": "L_clean"})
    rw = raw.rename(columns={"fwd_60d_excess": "L_rawstd",
                             "fwd_60d_excess_raw": "L_rawraw"})
    m = cl.merge(rw, on=["date", "ticker"], how="inner")
    log(f"  inner-join rows={len(m):,}  (clean={len(clean):,}, raw={len(raw):,})")
    log(f"  clean tickers={clean['ticker'].nunique()} raw tickers={raw['ticker'].nunique()} "
        f"joined tickers={m['ticker'].nunique()}")
    log(f"  clean dates {clean['date'].min().date()}..{clean['date'].max().date()}; "
        f"raw dates {raw['date'].min().date()}..{raw['date'].max().date()}; "
        f"joined {m['date'].min().date()}..{m['date'].max().date()}")
    for pair in (("L_clean", "L_rawraw"), ("L_clean", "L_rawstd")):
        a = m[pair[0]].values.astype(float); b = m[pair[1]].values.astype(float)
        ok = np.isfinite(a) & np.isfinite(b)
        log(f"  corr({pair[0]},{pair[1]}) same (date,ticker): pearson="
            f"{np.corrcoef(a[ok], b[ok])[0,1]:.6f} spearman="
            f"{sstats.spearmanr(a[ok], b[ok]).statistic:.6f} n={ok.sum():,}")
    log("  per-ticker shifted spearman (L_clean_t vs L_rawraw_{t+k}) - peak MUST be at k=0:")
    sub = m.sort_values(["ticker", "date"])
    for k in (-2, -1, 0, 1, 2):
        vals = []
        for tk, g in sub.groupby("ticker"):
            x = g["L_clean"].values.astype(float)
            y = g["L_rawraw"].values.astype(float)
            if k >= 0:
                xs, ys = x[:len(x)-k], y[k:]
            else:
                xs, ys = x[-k:], y[:len(y)+k]
            o = np.isfinite(xs) & np.isfinite(ys)
            if o.sum() > 50:
                vals.append(sstats.spearmanr(xs[o], ys[o]).statistic)
        log(f"    k={k:+d}: mean spearman={np.mean(vals):.6f} over {len(vals)} tickers")

    (OUT / "h1_label.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
