"""H6 — does the SAME composition confound contaminate the CLOSE decision statistic?

closure.py's paired arms at persistence-lag L, on the common LABEL-date set t in [L, N):
    REAL   arm = IC(score_t      , ret(t, t+60])   -> uses SCORE dates [L, N)
    PERSIST arm = IC(score_{t-L} , ret(t, t+60])   -> uses SCORE dates [0, N-L)
The label date is matched, but the SCORE-date window is NOT: the persist arm is fed
systematically EARLIER score dates. With strong era-heterogeneity in per-date IC this
biases REAL-persist by construction.

Test: recompute both arms on a COMMON SCORE-date set and see whether the sign survives.
READ-ONLY on all inputs.
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
CUT = Path("/Users/renhao/git/github/RenQuant/backtesting/renquant_104/"
           "artifacts/walkforward_gbdt_prod_recipe_v2")
LAGS = [20, 40, 60, 80]
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(str(s))


def ic_at(s, y):
    ok = np.isfinite(s) & np.isfinite(y)
    if ok.sum() < S0.MIN_NAMES:
        return np.nan
    return float(sstats.spearmanr(s[ok], y[ok]).statistic)


def block_t(vals_by_pos, block_len=60):
    """vals_by_pos: dict corpus_position -> value. Block t on corpus position."""
    s = pd.Series(vals_by_pos).dropna()
    if len(s) == 0:
        return np.nan, np.nan, 0
    bm = s.groupby((pd.Series(s.index, index=s.index) // block_len).values).mean()
    m, se, t, n = S0.tstat(bm.values)
    return m, t, n


def run(tag, dates, Smat, Ymat, pdates):
    """Return dict of diagnostics per lag."""
    N = len(dates)
    Sarr = Smat.values.astype(float)
    pos_of_pdate = {d: i for i, d in enumerate(pdates)}
    # label at corpus date index i = fwd_60d_excess at that panel row
    Yrow = {}
    for i, d in enumerate(dates):
        if d in pos_of_pdate:
            Yrow[i] = Ymat.loc[d].values.astype(float)

    # lagL_profile[i] = IC(score at corpus pos i, label at panel row pos(date_i)+L)
    def profile(L):
        out = {}
        for i, d in enumerate(dates):
            j = pos_of_pdate.get(d)
            if j is None or j + L >= len(pdates):
                continue
            y = Ymat.iloc[j + L].values.astype(float)
            v = ic_at(Sarr[i], y)
            if np.isfinite(v):
                out[i] = v
        return out

    prof = {L: profile(L) for L in [0] + LAGS}
    res = {}
    log("")
    log(f"  --- {tag} ---")
    log(f"  {'L':>4}{'REALarm(as closure)':>21}{'PERSarm(as closure)':>21}"
        f"{'diff':>10}{'t_blk':>8} | {'REAL common-SD':>16}{'PERS common-SD':>16}"
        f"{'diff_fixed':>12}{'t_blk':>8}")
    for L in LAGS:
        # ---- closure-equivalent arms (common LABEL date t in [L,N))
        real_c = {i: prof[0][i] for i in prof[0] if i >= L}
        pers_c = {i: prof[L][i - L] for i in range(L, N) if (i - L) in prof[L]}
        both = sorted(set(real_c) & set(pers_c))
        dif = {i: real_c[i] - pers_c[i] for i in both}
        m, t, nb = block_t(dif)
        mr = np.mean([real_c[i] for i in both])
        mp = np.mean([pers_c[i] for i in both])

        # ---- FIXED SCORE-DATE set: both arms evaluated on the SAME score dates
        sd = sorted(set(prof[0]) & set(prof[L]))     # score positions valid at both lags
        mr2 = np.mean([prof[0][i] for i in sd])
        mp2 = np.mean([prof[L][i] for i in sd])
        dif2 = {i: prof[0][i] - prof[L][i] for i in sd}
        m2, t2, nb2 = block_t(dif2)
        log(f"  {L:>4}{mr:>+21.5f}{mp:>+21.5f}{m:>+10.5f}{t:>+8.2f} | "
            f"{mr2:>+16.5f}{mp2:>+16.5f}{m2:>+12.5f}{t2:>+8.2f}")
        res[L] = {"closure_real": mr, "closure_pers": mp, "closure_diff": m,
                  "closure_t": t, "closure_nblocks": nb, "n_dates": len(both),
                  "fixed_real": mr2, "fixed_pers": mp2, "fixed_diff": m2,
                  "fixed_t": t2, "fixed_nblocks": nb2, "n_score_dates": len(sd)}
    # era diagnostic: score-date windows actually used
    log(f"  score-date windows used by the two closure arms:")
    for L in LAGS:
        log(f"    L={L:>3}: REAL arm score dates = corpus[{L}:{N}] "
            f"({dates[L].date()}..{dates[N-1].date()});  "
            f"PERSIST arm score dates = corpus[0:{N-L}] "
            f"({dates[0].date()}..{dates[N-L-1].date()})")
    return res


def main():
    panel = pd.read_parquet(S0.PANEL, columns=["date", "ticker", "fwd_60d_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    pdates = np.array(sorted(panel["date"].unique()))

    log("=" * 118)
    log("H6 — CLOSE-VERDICT DECISION STATISTIC: closure arms vs FIXED-SCORE-DATE arms")
    log("=" * 118)
    log("  'as closure' = paired on the common LABEL date (what closure.py/verdict.py did).")
    log("  'common-SD'  = both arms recomputed on the SAME SCORE-date set (confound removed).")
    log("  diff = REAL - PERSIST. CLOSE verdict required diff<0 with t_block<=-1.0 at >=3 lags.")

    sc = pd.read_parquet(S0.SCORES)
    sc["date"] = pd.to_datetime(sc["date"])
    ptd = np.array(sorted(sc["date"].unique()))
    ptt = np.array(sorted(sc["ticker"].unique()))
    ptS = sc.pivot(index="date", columns="ticker", values="raw").reindex(index=ptd, columns=ptt)
    ptY = panel.pivot(index="date", columns="ticker",
                      values="fwd_60d_excess").reindex(index=pdates, columns=ptt)
    r_pt = run("PatchTST", ptd, ptS, ptY, pdates)

    picks = pd.read_parquet(PICKS).rename(columns={"name": "ticker"})
    picks["date"] = pd.to_datetime(picks["date"])
    xgd = np.array(sorted(picks["date"].unique()))
    xgt = np.array(sorted(picks["ticker"].unique()))
    xgS = picks.pivot(index="date", columns="ticker", values="score").reindex(
        index=xgd, columns=xgt)
    xgY = panel.pivot(index="date", columns="ticker",
                      values="fwd_60d_excess").reindex(index=pdates, columns=xgt)
    r_xg = run("prodXGB", xgd, xgS, xgY, pdates)

    log("")
    log("=" * 118)
    log("RE-APPLYING THE FROZEN §3 RULE TO THE CONFOUND-REMOVED STATISTIC")
    log("=" * 118)
    p_cl = sum(1 for L in LAGS if r_pt[L]["closure_diff"] < 0 and r_pt[L]["closure_t"] <= -1.0)
    p_fx = sum(1 for L in LAGS if r_pt[L]["fixed_diff"] < 0 and r_pt[L]["fixed_t"] <= -1.0)
    c_cl = sum(1 for L in LAGS if r_xg[L]["closure_diff"] > 0)
    c_fx = sum(1 for L in LAGS if r_xg[L]["fixed_diff"] > 0)
    log(f"  PatchTST p (diff<0 AND t_block<=-1.0):  as-closure = {p_cl}/4   "
        f"FIXED-score-date = {p_fx}/4      (CLOSE needs p>=3)")
    log(f"  prodXGB control positive lags:          as-closure = {c_cl}/4   "
        f"FIXED-score-date = {c_fx}/4      (validity needs >=3)")

    json.dump({"patchtst": r_pt, "xgb": r_xg,
               "p_as_closure": p_cl, "p_fixed": p_fx,
               "ctrl_as_closure": c_cl, "ctrl_fixed": c_fx},
              open(OUT / "h6_results.json", "w"), indent=2, default=float)
    (OUT / "h6_closure.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
