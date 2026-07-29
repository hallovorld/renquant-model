"""H9 — corrected paired lag test (consistent estimator) + score-window sensitivity.

Fixes an estimator inconsistency in h8_final.py: the observed statistic was a
BLOCK mean while the null distribution was a SIMPLE date mean. Here both are
simple date means; block-level t is reported alongside for dispersion.

Adds the sensitivity that matters: how the paired lag contrast moves as the
score-date window END is varied. A robust effect should be flat; a composition
artifact should swing with the window.
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
sys.path.insert(0, str(SCRATCH / "bughunt"))
from h8_final import load, profiles, blk_t, fastrank, ic  # noqa: E402

OUT = SCRATCH / "bughunt"
LAGS = S0.PROFILE_LAGS
NSEED = 300
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(str(s))


def main():
    out = {}
    for tag in ("PatchTST", "prodXGB"):
        S, Yv, rows, dates, tick = load(tag)
        P = profiles(S, Yv, rows, LAGS)
        fixed = np.all([np.isfinite(P[L]) for L in LAGS], axis=0)
        idx = np.where(fixed)[0]

        log("=" * 108)
        log(f"{tag} — PAIRED LAG CONTRAST ON THE FIXED SCORE-DATE SET (consistent estimator)")
        log("=" * 108)
        log(f"  fixed set n={len(idx)} score dates "
            f"[{pd.Timestamp(dates[idx[0]]).date()}..{pd.Timestamp(dates[idx[-1]]).date()}]")

        nullD = {L: [] for L in LAGS}
        for seed in range(NSEED):
            rng = np.random.default_rng(550000 + seed)
            Sp = S[:, rng.permutation(len(tick))]
            Pp = profiles(Sp, Yv, rows, LAGS)
            for L in LAGS:
                nullD[L].append(float(np.nanmean(Pp[L][idx] - Pp[0][idx])))
        log(f"  {'lag':>5}{'IC(fixed)':>12}{'RISE = ICL-IC0':>17}{'t_block':>10}"
            f"{'null SD':>10}{'z':>8}{'P(null>=obs)':>14}")
        r = {}
        for L in LAGS:
            icl = float(np.nanmean(P[L][idx]))
            rise = float(np.nanmean(P[L][idx] - P[0][idx]))
            m_b, t_b, nb = blk_t(P[L][idx] - P[0][idx], idx)
            nd = np.array(nullD[L], dtype=float)
            sd = nd.std(ddof=1)
            z = (rise - nd.mean()) / sd if sd > 0 else np.nan
            pv = float((nd >= rise).mean())
            log(f"  {L:>5}{icl:>+12.4f}{rise:>+17.5f}{t_b:>+10.2f}{sd:>10.5f}"
                f"{z:>+8.2f}{pv:>14.4f}")
            r[L] = {"ic_fixed": icl, "rise_vs_lag0": rise, "t_block": t_b,
                    "null_sd": float(sd), "z": float(z), "p_one_sided": pv}
        out[tag] = {"fixed_set": r, "n_fixed": int(len(idx))}

        # ---------------- sensitivity to the score-window END
        log("")
        log(f"  SENSITIVITY — paired contrast ICL-IC0 vs the END of the score-date window")
        log(f"  (window = corpus[0:end]; a robust effect is flat across `end`)")
        N = S.shape[0]
        ends = [e for e in range(300, N + 1, 40)]
        log(f"  {'end':>6}{'last score date':>18}" + "".join(f"{'L='+str(L):>10}"
                                                             for L in (40, 60, 80, 100)))
        sens = {}
        for e in ends:
            sl = slice(0, e)
            vals = []
            for L in (40, 60, 80, 100):
                v = np.nanmean(P[L][sl] - P[0][sl])
                vals.append(v)
            sens[e] = vals
            log(f"  {e:>6}{str(pd.Timestamp(dates[e-1]).date()):>18}"
                + "".join(f"{v:>+10.4f}" for v in vals))
        out[tag]["sensitivity_by_window_end"] = {
            str(k): dict(zip(["L40", "L60", "L80", "L100"], v)) for k, v in sens.items()}
        for L, j in zip((40, 60, 80, 100), range(4)):
            col = [sens[e][j] for e in ends]
            log(f"    L={L:>3}: range over windows = [{min(col):+.4f}, {max(col):+.4f}]  "
                f"sign flips = {sum(1 for a, b in zip(col, col[1:]) if a*b < 0)}")
        log("")

    json.dump(out, open(OUT / "h9_results.json", "w"), indent=2, default=float)
    (OUT / "h9_fix.log").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
