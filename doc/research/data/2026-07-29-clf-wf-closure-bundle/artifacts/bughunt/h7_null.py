"""H7 — is the CLOSE decision statistic CALIBRATED under a PERSISTENCE-PRESERVING null?

closure.py's negative control permutes scores WITHIN EACH DATE INDEPENDENTLY
(closure.py L164-173: a fresh rng per row i). That destroys the score's
time-series persistence entirely -- so under that control the "persistence"
arm (score_{t-L}) is unrelated to the real arm (score_t). A design whose whole
statistic is "score vs a lagged copy of ITSELF" cannot be validated by a control
that removes the lag relationship.

Correct persistence-preserving null: one GLOBAL ticker-identity permutation.
Each name keeps its entire score path (persistence identical by construction);
only the score<->label pairing is destroyed. E[IC]=0 in both arms, so E[diff]=0.
We use it to measure the NULL DISTRIBUTION OF closure's block-level t.

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
LAGS = [20, 40, 60, 80]
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


def closure_stat(Sarr, Ylab):
    """Ylab[i] = label vector for corpus date i (the (t,t+60] window).
    Returns {L: (diff_mean_block, t_block, n_blocks)} exactly as closure.py aggregates."""
    N = Sarr.shape[0]
    prof0 = np.array([ic(Sarr[i], Ylab[i]) for i in range(N)])
    out = {}
    for L in LAGS:
        idx, dif = [], []
        for t in range(L, N):
            a = prof0[t]
            b = ic(Sarr[t - L], Ylab[t])          # stale score, SAME label window
            if np.isfinite(a) and np.isfinite(b):
                idx.append(t)
                dif.append(a - b)
        if not dif:
            out[L] = (np.nan, np.nan, 0)
            continue
        s = pd.Series(dif, index=idx)
        bm = s.groupby(np.array(idx) // BLOCK).mean()
        m, se, t, n = S0.tstat(bm.values)
        out[L] = (m, t, n)
    return out


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
    Y = panel.pivot(index="date", columns="ticker",
                    values="fwd_60d_excess").reindex(index=pdates, columns=tick)
    Ylab = [Y.loc[d].values.astype(float) if d in Y.index else np.full(len(tick), np.nan)
            for d in dates]
    return S, Ylab, tick


def main():
    log("=" * 104)
    log("H7 — NULL CALIBRATION OF THE CLOSE DECISION STATISTIC")
    log("=" * 104)
    log("  null = ONE global ticker-identity permutation of the score matrix")
    log("         (persistence preserved EXACTLY; score<->label signal destroyed)")
    log(f"  {NSEED} seeds; statistic + block aggregation identical to closure.py")

    summary = {}
    for tag in ("PatchTST", "prodXGB"):
        S, Ylab, tick = load(tag)
        obs = closure_stat(S, Ylab)
        rows = {L: {"diff": [], "t": []} for L in LAGS}
        for seed in range(NSEED):
            rng = np.random.default_rng(770000 + seed)
            Sp = S[:, rng.permutation(len(tick))]
            r = closure_stat(Sp, Ylab)
            for L in LAGS:
                rows[L]["diff"].append(r[L][0])
                rows[L]["t"].append(r[L][1])
            if (seed + 1) % 150 == 0:
                log(f"    {tag}: {seed+1}/{NSEED}")
        log("")
        log(f"  --- {tag} ---")
        log(f"  {'L':>4}{'obs diff':>11}{'obs t_blk':>11} | {'null diff SD':>14}"
            f"{'null t MEAN':>13}{'null t SD':>11}{'null |t|>1 %':>14}"
            f"{'P(null<=obs)':>14}")
        summary[tag] = {}
        for L in LAGS:
            d = np.array(rows[L]["diff"], dtype=float)
            t = np.array(rows[L]["t"], dtype=float)
            od, ot, _ = obs[L]
            p = float((d <= od).mean()) if tag == "PatchTST" else float((d >= od).mean())
            log(f"  {L:>4}{od:>+11.5f}{ot:>+11.2f} | {d.std(ddof=1):>14.5f}"
                f"{np.nanmean(t):>+13.2f}{np.nanstd(t, ddof=1):>11.2f}"
                f"{100*np.mean(np.abs(t) > 1.0):>13.1f}%{p:>14.4f}")
            summary[tag][L] = {"obs_diff": od, "obs_t": ot,
                               "null_diff_sd": float(d.std(ddof=1)),
                               "null_t_mean": float(np.nanmean(t)),
                               "null_t_sd": float(np.nanstd(t, ddof=1)),
                               "null_frac_absT_gt1": float(np.mean(np.abs(t) > 1.0)),
                               "p_one_sided": p}
        log("   P(null<=obs) for PatchTST (one-sided, the CLOSE direction);"
            " P(null>=obs) for prodXGB (control direction).")

    log("")
    log("=" * 104)
    log("CALIBRATION READ-OUT")
    log("=" * 104)
    for tag in summary:
        sds = [summary[tag][L]["null_t_sd"] for L in LAGS]
        fr = [summary[tag][L]["null_frac_absT_gt1"] for L in LAGS]
        log(f"  {tag:9s}: null SD of block-t = {min(sds):.2f}..{max(sds):.2f} "
            f"(a calibrated t has SD~1.0); P(|t|>1.0) under the null = "
            f"{100*min(fr):.0f}%..{100*max(fr):.0f}% (calibrated ~32%)")
    json.dump(summary, open(OUT / "h7_results.json", "w"), indent=2, default=float)
    (OUT / "h7_null.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
