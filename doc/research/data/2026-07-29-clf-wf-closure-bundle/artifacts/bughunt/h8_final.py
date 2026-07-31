"""H8 — decisive test of the HEADLINE finding, and decomposition of the CLOSE statistic.

(A) Exact algebraic decomposition of closure.py's statistic:
      closure_diff(L) = mean_{[L,N)} prof0  -  mean_{[0,N-L)} profL
                      = [mean_{[L,N)} prof0 - mean_{[0,N-L)} prof0]   <- ERA term (score-window mismatch)
                      + [mean_{[0,N-L)} prof0 - mean_{[0,N-L)} profL] <- LAG term (the headline finding)
(B) PAIRED test of the LAG term on a FIXED score-date set:
      D(L)_i = IC(score_i, ret(i,i+60]) - IC(score_i, ret(i+L,i+L+60])
    Same score date in both terms -> variance-reduced. Block-level t + the
    persistence-preserving global-ticker-permutation null.

READ-ONLY. Writes only under scratchpad/bughunt/.
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
PICKS = Path("/Users/renhao/git/github/RenQuant/data/exp/oos_pick_table_recipe_v2.parquet")
NSEED = 300
BLOCK = 60
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(str(s))


def fastrank(x):
    o = np.argsort(x, kind="stable")
    r = np.empty(len(x), dtype=float)
    r[o] = np.arange(len(x), dtype=float)
    return r


def ic(s, y):
    ok = np.isfinite(s) & np.isfinite(y)
    if ok.sum() < S0.MIN_NAMES:
        return np.nan
    a, b = fastrank(s[ok]), fastrank(y[ok])
    a -= a.mean()
    b -= b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else np.nan


def load(tag):
    panel = pd.read_parquet(S0.PANEL, columns=["date", "ticker", "fwd_60d_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    pdates = np.array(sorted(panel["date"].unique()))
    if tag == "PatchTST":
        sc = pd.read_parquet(S0.SCORES)
        sc["date"] = pd.to_datetime(sc["date"])
        val = "raw"
    else:
        sc = pd.read_parquet(PICKS).rename(columns={"name": "ticker"})
        sc["date"] = pd.to_datetime(sc["date"])
        val = "score"
    dates = np.array(sorted(sc["date"].unique()))
    tick = np.array(sorted(sc["ticker"].unique()))
    S = sc.pivot(index="date", columns="ticker", values=val).reindex(
        index=dates, columns=tick).values.astype(float)
    Yp = panel.pivot(index="date", columns="ticker",
                     values="fwd_60d_excess").reindex(index=pdates, columns=tick)
    prow = {d: i for i, d in enumerate(pdates)}
    Yv = Yp.values.astype(float)
    rows = np.array([prow[d] for d in dates])
    return S, Yv, rows, dates, tick


def profiles(S, Yv, rows, lags):
    """prof[L][i] = IC(score at corpus date i, label at panel row rows[i]+L)."""
    P = {}
    for L in lags:
        v = np.full(S.shape[0], np.nan)
        for i in range(S.shape[0]):
            j = rows[i] + L
            if j < Yv.shape[0]:
                v[i] = ic(S[i], Yv[j])
        P[L] = v
    return P


def blk_t(vals, idx):
    s = pd.Series(vals, index=idx).dropna()
    if len(s) == 0:
        return np.nan, np.nan, 0
    bm = s.groupby(np.asarray(s.index) // BLOCK).mean()
    m, se, t, n = S0.tstat(bm.values)
    return m, t, n


def main():
    LAGS_C = [20, 40, 60, 80]
    LAGS_P = S0.PROFILE_LAGS

    for tag in ("PatchTST", "prodXGB"):
        S, Yv, rows, dates, tick = load(tag)
        N = S.shape[0]
        P = profiles(S, Yv, rows, sorted(set(LAGS_C) | set(LAGS_P)))
        p0 = P[0]

        log("=" * 112)
        log(f"(A) {tag} — EXACT DECOMPOSITION OF closure.py's 'REAL - persistence' STATISTIC")
        log("=" * 112)
        log(f"  {'L':>4}{'closure diff':>14}{'= ERA term':>13}{'+ LAG term':>13}"
            f"{'ERA share':>11}{'  score dates: REAL arm / PERSIST arm'}")
        dec = {}
        for L in LAGS_C:
            late = p0[L:N]
            early0 = p0[0:N - L]
            earlyL = P[L][0:N - L]
            m_late = np.nanmean(late)
            m_e0 = np.nanmean(early0)
            m_eL = np.nanmean(earlyL)
            era = m_late - m_e0
            lag = m_e0 - m_eL
            tot = m_late - m_eL
            log(f"  {L:>4}{tot:>+14.5f}{era:>+13.5f}{lag:>+13.5f}"
                f"{100*era/tot:>10.0f}%   [{L}:{N}] / [0:{N-L}]")
            dec[L] = {"total": tot, "era": era, "lag": lag,
                      "era_share": float(era / tot) if tot else np.nan}

        # -------- (B) paired LAG test on a FIXED score-date set
        log("")
        log("=" * 112)
        log(f"(B) {tag} — PAIRED LAG TEST ON A FIXED SCORE-DATE SET "
            f"(same score date in both terms)")
        log("=" * 112)
        valid = {L: np.isfinite(P[L]) for L in LAGS_P}
        fixed = np.all([valid[L] for L in LAGS_P], axis=0)
        idx = np.where(fixed)[0]
        log(f"  fixed score-date set = dates valid at ALL lags {LAGS_P}: n={len(idx)} "
            f"[{pd.Timestamp(dates[idx[0]]).date()}..{pd.Timestamp(dates[idx[-1]]).date()}]")
        log(f"  {'lag':>5}{'IC (fixed set)':>16}{'paired D=IC0-ICL':>19}{'t_block':>10}"
            f"{'n_blk':>7}{'null D SD':>12}{'P(null<=D)':>12}")

        # null: global ticker permutation, persistence preserved
        nullD = {L: [] for L in LAGS_P}
        nullIC = {L: [] for L in LAGS_P}
        for seed in range(NSEED):
            rng = np.random.default_rng(550000 + seed)
            Sp = S[:, rng.permutation(len(tick))]
            Pp = profiles(Sp, Yv, rows, LAGS_P)
            for L in LAGS_P:
                nullD[L].append(np.nanmean(Pp[0][idx] - Pp[L][idx]))
                nullIC[L].append(np.nanmean(Pp[L][idx]))
            if (seed + 1) % 150 == 0:
                log(f"    ...null {seed+1}/{NSEED}")
        res = {}
        for L in LAGS_P:
            d = p0[idx] - P[L][idx]
            m, t, nb = blk_t(d, idx)
            nd = np.array(nullD[L], dtype=float)
            pv = float((nd <= m).mean())
            log(f"  {L:>5}{np.nanmean(P[L][idx]):>+16.4f}{m:>+19.5f}{t:>+10.2f}{nb:>7}"
                f"{nd.std(ddof=1):>12.5f}{pv:>12.4f}")
            res[L] = {"ic_fixed": float(np.nanmean(P[L][idx])), "paired_D": m,
                      "t_block": t, "n_blocks": nb,
                      "null_D_sd": float(nd.std(ddof=1)), "p_one_sided": pv}
        log("  D<0 means the FAR window is predicted BETTER than the near window.")
        log("  P is one-sided P(null D <= observed D) under the persistence-preserving null.")
        log("")
        json.dump({"decomposition": dec, "paired_lag_test": res,
                   "n_fixed_dates": int(len(idx)), "n_seeds": NSEED},
                  open(OUT / f"h8_{tag}.json", "w"), indent=2, default=float)

    (OUT / "h8_final.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
