"""ADVERSARIAL BUG HUNT — H2 (lag semantics), H3 (survivorship/composition), H5 (join).

READ-ONLY on every input. Writes only under scratchpad/bughunt/.
Reuses stage0.py's exact objects so any difference is attributable to the test,
not to a reimplementation.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

SCRATCH = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-"
               "orchestrator/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad")
sys.path.insert(0, str(SCRATCH / "goal6-stage0"))
import stage0 as S0  # noqa: E402

OUT = SCRATCH / "bughunt"
PICKS = Path("/Users/renhao/git/github/RenQuant/data/exp/oos_pick_table_recipe_v2.parquet")
LAGS = S0.PROFILE_LAGS
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(str(s))


def build_pt():
    sc = pd.read_parquet(S0.SCORES)
    sc["date"] = pd.to_datetime(sc["date"])
    dates = np.array(sorted(sc["date"].unique()))
    fold = sc.drop_duplicates("date").set_index("date")["fold_idx"].to_dict()
    tick = np.array(sorted(sc["ticker"].unique()))
    Smat = sc.pivot(index="date", columns="ticker", values="raw").reindex(
        index=dates, columns=tick)
    return sc, dates, fold, tick, Smat


def build_xgb():
    picks = pd.read_parquet(PICKS).rename(columns={"name": "ticker"})
    picks["date"] = pd.to_datetime(picks["date"])
    dates = np.array(sorted(picks["date"].unique()))
    CUT = Path("/Users/renhao/git/github/RenQuant/backtesting/renquant_104/"
               "artifacts/walkforward_gbdt_prod_recipe_v2")
    cutoffs = sorted(pd.to_datetime([p.name for p in CUT.iterdir() if p.is_dir()]))
    fold = {d: int(np.searchsorted(cutoffs, d, side="right") - 1) for d in dates}
    tick = np.array(sorted(picks["ticker"].unique()))
    Smat = picks.pivot(index="date", columns="ticker", values="score").reindex(
        index=dates, columns=tick)
    return picks, dates, fold, tick, Smat


def ic_series(dates, S, Yl):
    """Per-date spearman(score_t, Yl_t). Returns dict date -> ic."""
    out = {}
    for d in dates:
        s = S.get(d)
        if s is None or d not in Yl.index:
            continue
        y = Yl.loc[d].values.astype(float)
        ok = np.isfinite(s) & np.isfinite(y)
        if ok.sum() < S0.MIN_NAMES:
            continue
        out[d] = float(sstats.spearmanr(s[ok], y[ok]).statistic)
    return out


def fold_t(ics, fold):
    v = pd.Series(ics)
    fm = v.groupby(pd.Series({d: fold[d] for d in v.index})).mean()
    m, se, t, n = S0.tstat(fm.values)
    return m, t, n, len(v)


def main():
    panel = pd.read_parquet(S0.PANEL, columns=["date", "ticker", "fwd_60d_excess",
                                               "fwd_20d_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    pdates = np.array(sorted(panel["date"].unique()))

    # ================================================================ H5 / H2a
    log("=" * 100)
    log("H5 — JOIN + KEY INTEGRITY")
    log("=" * 100)
    dup = panel.duplicated(["date", "ticker"]).sum()
    log(f"  panel duplicate (date,ticker) rows          : {dup}")
    log(f"  panel rows / dates / tickers                : {len(panel):,} / {len(pdates)} / "
        f"{panel['ticker'].nunique()}")
    log(f"  panel date range                            : {pdates.min().date()} .. {pdates.max().date()}")
    nn = panel.dropna(subset=['fwd_60d_excess'])
    log(f"  last date with non-null fwd_60d_excess      : {nn['date'].max().date()}")
    log(f"  non-null fwd_60d_excess rows                : {len(nn):,} ({len(nn)/len(panel):.1%})")

    # panel date axis contiguity vs NYSE trading days (proxy: SPY-bearing dates)
    bd = pd.bdate_range(pdates.min(), pdates.max())
    log(f"  panel dates={len(pdates)}  business days in range={len(bd)}  "
        f"ratio={len(pdates)/len(bd):.4f}  (gaps = market holidays -> axis is trading-day contiguous)")
    gaps = np.diff(pdates).astype('timedelta64[D]').astype(int)
    log(f"  consecutive panel-date gaps: max={gaps.max()}d, "
        f"count>5d={int((gaps > 5).sum())}  (weekend=3d)")

    for tag, builder in (("PatchTST", build_pt), ("prodXGB", build_xgb)):
        sc, dates, fold, tick, Smat = builder()
        d2 = sc.duplicated(["date", "ticker"]).sum()
        log(f"  {tag:9s} score rows={len(sc):,} dates={len(dates)} tickers={len(tick)} "
            f"dup(date,ticker)={d2}")
        log(f"  {tag:9s} score dates {dates.min().date()}..{dates.max().date()}; "
            f"score dates NOT in panel = {len(set(dates) - set(pdates))}; "
            f"tickers NOT in panel = {len(set(tick) - set(panel['ticker'].unique()))}")

    # ================================================================ H2
    log("")
    log("=" * 100)
    log("H2 — WHAT WINDOW DOES 'label lag L' ACTUALLY CORRELATE?")
    log("=" * 100)
    Ym = panel.pivot(index="date", columns="ticker", values="fwd_60d_excess").reindex(index=pdates)
    for L in (0, 60, 100):
        Yl = Ym.shift(-L)
        # pick a probe date well inside the corpus
        t = pdates[300]
        src_pos = 300 + L
        src = pdates[src_pos]
        col = Ym.columns[Ym.loc[src].notna()][0]
        a, b = Yl.loc[t, col], Ym.loc[src, col]
        log(f"  lag={L:>3}: Yl.loc[{t.date()}] == Ym.loc[{src.date()}] ? "
            f"{a} vs {b} -> {'MATCH' if (a == b or (np.isnan(a) and np.isnan(b))) else 'MISMATCH'}"
            f"   (panel rows apart = {src_pos-300})")
    log("  => score_t is correlated with fwd_60d_excess measured at row t+L,")
    log("     i.e. the excess return over the window (t+L, t+L+60] trading days.")
    log("     For L>=60 that window does NOT overlap the trained window (t, t+60].")

    # ================================================================ H3
    log("")
    log("=" * 100)
    log("H3 — SURVIVORSHIP / COMPOSITION IN THE LAG WINDOWS  [DECISIVE]")
    log("=" * 100)
    results = {}
    for tag, builder in (("PatchTST", build_pt), ("prodXGB", build_xgb)):
        sc, dates, fold, tick, Smat = builder()
        S = {d: Smat.loc[d].values.astype(float) for d in dates}
        Ymat = panel.pivot(index="date", columns="ticker",
                           values="fwd_60d_excess").reindex(index=pdates, columns=tick)
        per_lag = {}
        for L in LAGS:
            per_lag[L] = ic_series(dates, S, Ymat.shift(-L))
        common = set.intersection(*[set(v.keys()) for v in per_lag.values()])
        common = sorted(common)
        log("")
        log(f"  --- {tag} --- (label fwd_60d_excess)")
        log(f"  dates surviving ALL lags (== the lag{max(LAGS)} date set): {len(common)} "
            f"[{min(common).date()} .. {max(common).date()}]")
        log(f"  {'lag':>5}{'n_dates':>9}{'lastdate':>13}{'IC_full':>10}{'t_full':>8}"
            f"{'IC_COMMON':>12}{'t_common':>10}")
        rows = {}
        for L in LAGS:
            ics = per_lag[L]
            m, t, nf, nd = fold_t(ics, fold)
            sub = {d: ics[d] for d in common}
            mc, tc, nfc, ndc = fold_t(sub, fold)
            last = max(ics.keys()).date()
            log(f"  {L:>5}{nd:>9}{str(last):>13}{m:>+10.4f}{t:>+8.2f}{mc:>+12.4f}{tc:>+10.2f}")
            rows[L] = {"n_dates_full": nd, "ic_full": m, "t_full": t,
                       "n_dates_common": ndc, "ic_common": mc, "t_common": tc,
                       "last_date": str(last)}
        rise_full = rows[100]["ic_full"] - rows[0]["ic_full"]
        rise_com = rows[100]["ic_common"] - rows[0]["ic_common"]
        log(f"  RISE lag0->lag100 :  full-sample {rise_full:+.4f}   "
            f"COMMON-sample {rise_com:+.4f}   "
            f"({100*(1-rise_com/rise_full):.0f}% of the rise is composition)"
            if abs(rise_full) > 1e-9 else "")
        results[tag] = rows

        # era decomposition of the lag-0 IC (why dropping the tail helps)
        ic0 = pd.Series(per_lag[0])
        yr = pd.Series({d: pd.Timestamp(d).year for d in ic0.index})
        log(f"  lag-0 per-date IC by calendar year of the SCORE date:")
        for y, g in ic0.groupby(yr):
            log(f"      {y}: mean IC={g.mean():+.4f}  n_dates={len(g)}")
        dropped = sorted(set(per_lag[0].keys()) - set(common))
        if dropped:
            keptv = np.array([per_lag[0][d] for d in common])
            dropv = np.array([per_lag[0][d] for d in dropped])
            log(f"  lag-0 IC on dates KEPT by lag{max(LAGS)} : {keptv.mean():+.4f} (n={len(keptv)})")
            log(f"  lag-0 IC on dates DROPPED by lag{max(LAGS)}: {dropv.mean():+.4f} (n={len(dropv)})"
                f"  [{pd.Timestamp(min(dropped)).date()}..{pd.Timestamp(max(dropped)).date()}]")

    (OUT / "h235_results.json").write_text(json.dumps(results, indent=2, default=float))
    (OUT / "h235.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
