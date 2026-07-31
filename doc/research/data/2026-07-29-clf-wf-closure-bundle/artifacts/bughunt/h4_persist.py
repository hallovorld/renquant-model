"""H4 — signal-free but EQUALLY PERSISTENT score null.

Null construction: apply a single global TICKER-IDENTITY permutation to the score
matrix. This preserves, EXACTLY and non-parametrically:
  * each name's full score time-series (so cross-sectional rank autocorrelation
    at every lag is identical to the real corpus, by construction),
  * the per-date cross-sectional score distribution,
  * the per-date name coverage pattern (up to relabelling),
while destroying the score<->label association. Expected IC is 0 at every lag.

We then run the IDENTICAL lag profile and ask: how often does a signal-free but
equally persistent score produce a rise of the observed size?

READ-ONLY on all inputs. Writes only under scratchpad/bughunt/.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRATCH = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-"
               "orchestrator/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad")
sys.path.insert(0, str(SCRATCH / "goal6-stage0"))
import stage0 as S0  # noqa: E402

OUT = SCRATCH / "bughunt"
LAGS = S0.PROFILE_LAGS
NSEED = 400
MIN_NAMES = S0.MIN_NAMES
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(str(s))


def fastrank(x):
    """Average-tie-free rank (data are continuous floats)."""
    o = np.argsort(x, kind="stable")
    r = np.empty(len(x), dtype=float)
    r[o] = np.arange(len(x), dtype=float)
    return r


def profile_ics(Sarr, Yarrs, date_ok):
    """Sarr: (ndates, ntick) scores. Yarrs: list per lag of (ndates, ntick) labels.
    Returns list per lag of dict {date_index: ic}."""
    out = []
    for Y in Yarrs:
        d = {}
        for i in np.where(date_ok)[0]:
            s, y = Sarr[i], Y[i]
            ok = np.isfinite(s) & np.isfinite(y)
            n = ok.sum()
            if n < MIN_NAMES:
                continue
            rs, ry = fastrank(s[ok]), fastrank(y[ok])
            rs -= rs.mean()
            ry -= ry.mean()
            den = np.sqrt((rs * rs).sum() * (ry * ry).sum())
            if den > 0:
                d[i] = float((rs * ry).sum() / den)
        out.append(d)
    return out


def foldmean_t(ics, fold_of_i, restrict=None):
    it = ics if restrict is None else {k: v for k, v in ics.items() if k in restrict}
    if not it:
        return np.nan, np.nan
    s = pd.Series(it)
    fm = s.groupby(pd.Series({k: fold_of_i[k] for k in s.index})).mean()
    m, se, t, n = S0.tstat(fm.values)
    return m, t


def main():
    sc = pd.read_parquet(S0.SCORES)
    sc["date"] = pd.to_datetime(sc["date"])
    dates = np.array(sorted(sc["date"].unique()))
    tick = np.array(sorted(sc["ticker"].unique()))
    fold_of_date = sc.drop_duplicates("date").set_index("date")["fold_idx"].to_dict()
    Smat = sc.pivot(index="date", columns="ticker", values="raw").reindex(
        index=dates, columns=tick)

    panel = pd.read_parquet(S0.PANEL, columns=["date", "ticker", "fwd_60d_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    pdates = np.array(sorted(panel["date"].unique()))
    Ym = panel.pivot(index="date", columns="ticker",
                     values="fwd_60d_excess").reindex(index=pdates, columns=tick)

    # label matrices restricted to the corpus date rows, per lag
    Yarrs = []
    for L in LAGS:
        Yl = Ym.shift(-L).reindex(index=dates)
        Yarrs.append(Yl.values.astype(float))
    Sarr = Smat.values.astype(float)
    date_ok = np.ones(len(dates), dtype=bool)
    fold_of_i = {i: fold_of_date[dates[i]] for i in range(len(dates))}

    log("=" * 100)
    log("H4 — SIGNAL-FREE, PERSISTENCE-MATCHED NULL (global ticker-identity permutation)")
    log("=" * 100)
    log(f"  corpus: {len(dates)} dates, {len(tick)} tickers, {NSEED} permutation seeds")
    log(f"  score NaN fraction in corpus matrix: {np.isnan(Sarr).mean():.4f}")

    # ---- REAL profile (reference) + the common date set
    real = profile_ics(Sarr, Yarrs, date_ok)
    common = set.intersection(*[set(d.keys()) for d in real])
    log(f"  dates surviving ALL lags: {len(common)}")
    real_full = [foldmean_t(real[k], fold_of_i)[0] for k in range(len(LAGS))]
    real_com = [foldmean_t(real[k], fold_of_i, common)[0] for k in range(len(LAGS))]
    i0, i100 = LAGS.index(0), LAGS.index(100)
    obs_full = real_full[i100] - real_full[i0]
    obs_com = real_com[i100] - real_com[i0]
    log("")
    log(f"  {'lag':>5}{'REAL full':>12}{'REAL common':>14}")
    for k, L in enumerate(LAGS):
        log(f"  {L:>5}{real_full[k]:>+12.4f}{real_com[k]:>+14.4f}")
    log(f"  observed rise lag0->lag100: full={obs_full:+.4f}  common={obs_com:+.4f}")

    # ---- permutation null
    rows_full, rows_com = [], []
    for seed in range(NSEED):
        rng = np.random.default_rng(900000 + seed)
        perm = rng.permutation(len(tick))
        Sp = Sarr[:, perm]
        p = profile_ics(Sp, Yarrs, date_ok)
        rows_full.append([foldmean_t(p[k], fold_of_i)[0] for k in range(len(LAGS))])
        rows_com.append([foldmean_t(p[k], fold_of_i, common)[0] for k in range(len(LAGS))])
        if (seed + 1) % 100 == 0:
            log(f"    ...{seed+1}/{NSEED} seeds")
    F = np.array(rows_full)
    C = np.array(rows_com)

    log("")
    log("  NULL profile (mean over seeds; must be ~0 at every lag) and its SD:")
    log(f"  {'lag':>5}{'null mean':>12}{'null SD':>10}{'REAL full':>12}"
        f"{'null mean(c)':>14}{'null SD(c)':>12}{'REAL com':>11}")
    for k, L in enumerate(LAGS):
        log(f"  {L:>5}{F[:,k].mean():>+12.4f}{F[:,k].std(ddof=1):>10.4f}{real_full[k]:>+12.4f}"
            f"{C[:,k].mean():>+14.4f}{C[:,k].std(ddof=1):>12.4f}{real_com[k]:>+11.4f}")

    dF = F[:, i100] - F[:, i0]
    dC = C[:, i100] - C[:, i0]
    log("")
    log("  DISTRIBUTION OF THE RISE (lag100 - lag0) UNDER THE SIGNAL-FREE PERSISTENT NULL")
    log(f"    full-sample : null mean={dF.mean():+.4f} SD={dF.std(ddof=1):.4f}   "
        f"observed={obs_full:+.4f}  ->  P(null >= observed) = {(dF >= obs_full).mean():.4f}")
    log(f"    COMMON set  : null mean={dC.mean():+.4f} SD={dC.std(ddof=1):.4f}   "
        f"observed={obs_com:+.4f}  ->  P(null >= observed) = {(dC >= obs_com).mean():.4f}")
    # shape test: max over lags minus lag0
    mF = F.max(axis=1) - F[:, i0]
    mC = C.max(axis=1) - C[:, i0]
    obs_mF = max(real_full) - real_full[i0]
    obs_mC = max(real_com) - real_com[i0]
    log(f"    max_lag - lag0, full : null mean={mF.mean():+.4f} SD={mF.std(ddof=1):.4f}  "
        f"observed={obs_mF:+.4f}  P(null>=obs)={(mF >= obs_mF).mean():.4f}")
    log(f"    max_lag - lag0, com  : null mean={mC.mean():+.4f} SD={mC.std(ddof=1):.4f}  "
        f"observed={obs_mC:+.4f}  P(null>=obs)={(mC >= obs_mC).mean():.4f}")
    # how often does a signal-free persistent score produce a MONOTONE-ish rise?
    up = ((F[:, i100] > F[:, i0])).mean()
    log(f"    fraction of signal-free seeds with IC(lag100) > IC(lag0), full = {up:.3f}")

    json.dump({"lags": LAGS, "real_full": real_full, "real_common": real_com,
               "null_full_mean": F.mean(axis=0).tolist(),
               "null_full_sd": F.std(axis=0, ddof=1).tolist(),
               "null_common_mean": C.mean(axis=0).tolist(),
               "null_common_sd": C.std(axis=0, ddof=1).tolist(),
               "obs_rise_full": obs_full, "obs_rise_common": obs_com,
               "p_rise_full": float((dF >= obs_full).mean()),
               "p_rise_common": float((dC >= obs_com).mean()),
               "p_maxminus_full": float((mF >= obs_mF).mean()),
               "p_maxminus_common": float((mC >= obs_mC).mean()),
               "n_seeds": NSEED},
              open(OUT / "h4_results.json", "w"), indent=2, default=float)
    (OUT / "h4_persist.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
