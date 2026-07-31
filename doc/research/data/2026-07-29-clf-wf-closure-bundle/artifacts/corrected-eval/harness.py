#!/usr/bin/env python3
"""Corrected signal evaluation — executes the FROZEN prereg
doc/research/2026-07-29-corrected-signal-evaluation-prereg.md (model#90).

EVERY cross-lag and cross-arm comparison is pinned to the common sample
produced by `renquant_model_common.lag_alignment.align_lags` (model#89).
The alignment is NOT reimplemented here.

Read-only over the corpora and the panel. Writes only under this directory.

Usage:  python3 harness.py --smoke      (fast: 3 perm seeds, 2 subjects)
        python3 harness.py              (full)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

sys.path.insert(0, "/private/tmp/renquant-model-pr89-review/src")
from renquant_model_common.lag_alignment import align_lags, lag_evaluable_dates  # noqa: E402

SCRATCH = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
               "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad")
OUT = SCRATCH / "corrected-eval"
PANEL = "/Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet"
XGB_P = "/Users/renhao/git/github/RenQuant/data/exp/oos_pick_table_recipe_v2.parquet"
CLF_P = SCRATCH / "clf-wf/clf_wf_scores.parquet"
PT_P = SCRATCH / "wf-eval/scores.parquet"

# ---- frozen prereg constants (§2/§3) --------------------------------------
LABEL_COL = "fwd_60d_excess"       # §2 horizon: 60d, the traded horizon
BLOCK_LEN = 60                     # §2 block length = the arm's own label horizon
PROFILE_LAGS = [0, 20, 40, 60, 80, 100, 120, 160]   # §2, exactly as frozen
PERM_SEEDS = 20                    # §2 within-date permutation, 20 seeds
DECILE = 0.10
# ---- INHERITED / DISCLOSED (not restated by the frozen prereg) ------------
PERSIST_LAG = 60      # "the persistence-matched control" = same corpus's score
                      # 60 trading days earlier. Inherited verbatim from the
                      # Stage-0 registration (model#86 §3.2, PERSIST_LAG = 60).
MIN_NAMES = 20        # inherited from the Stage-0 harness (goal6-stage0/stage0.py)
RNG_BASE = 20260729


# ---------------------------------------------------------------- inference
def block_t(per_date: pd.Series, block_len: int = BLOCK_LEN):
    """Block-level t of a per-date series. Blocks = consecutive chunks of
    `block_len` DATES of the (already common) sample. The trailing partial
    block is KEPT (block means are unbiased at any chunk size; dropping it
    would be an unregistered threshold). n_eff = number of blocks."""
    s = per_date.dropna().sort_index()
    if len(s) == 0:
        return dict(mean=np.nan, se=np.nan, t=np.nan, n_eff=0, n_dates=0)
    grp = np.arange(len(s)) // block_len
    bm = pd.Series(s.values, index=grp).groupby(level=0).mean().values
    n = len(bm)
    m = float(np.mean(bm))
    if n < 2:
        return dict(mean=m, se=np.nan, t=np.nan, n_eff=n, n_dates=int(len(s)))
    se = float(np.std(bm, ddof=1) / np.sqrt(n))
    return dict(mean=m, se=se, t=(m / se if se > 0 else np.nan),
                n_eff=n, n_dates=int(len(s)))


# ---------------------------------------------------------------- statistics
def date_stats(sv: np.ndarray, yv: np.ndarray):
    """rank IC and top-minus-bottom decile spread for one date."""
    ok = np.isfinite(sv) & np.isfinite(yv)
    n = int(ok.sum())
    if n < MIN_NAMES:
        return np.nan, np.nan, n
    s, y = sv[ok], yv[ok]
    rs = sstats.rankdata(s)
    ic = float(np.corrcoef(rs, sstats.rankdata(y))[0, 1])
    pct = rs / n
    top, bot = y[pct > 1 - DECILE], y[pct <= DECILE]
    spread = float(top.mean() - bot.mean()) if (len(top) >= 3 and len(bot) >= 3) else np.nan
    return ic, spread, n


def arm_per_date(dates, Smat, Lmat, label_pos, perm_seeds=0):
    """Per-date REAL stats (and, if perm_seeds>0, the within-date permutation
    null averaged over seeds) for one arm.

    Smat: (ndate_score, nname) score matrix rows indexed by `dates` order.
    Lmat: (ndate_label, nname) label matrix.
    label_pos: for each date in `dates`, the row of Lmat to pair with.
    """
    ic_r, sp_r, ic_p, sp_p, nn = [], [], [], [], []
    for i, d in enumerate(dates):
        sv = Smat[i]
        yv = Lmat[label_pos[i]]
        ic, sp, n = date_stats(sv, yv)
        ic_r.append(ic); sp_r.append(sp); nn.append(n)
        if perm_seeds:
            ok = np.isfinite(sv) & np.isfinite(yv)
            if ok.sum() < MIN_NAMES:
                ic_p.append(np.nan); sp_p.append(np.nan); continue
            s, y = sv[ok], yv[ok]
            ai, asp = [], []
            for k in range(perm_seeds):
                rng = np.random.default_rng(RNG_BASE + 1000 * k + i)
                yp = rng.permutation(y)          # within-date permutation
                a, b, _ = date_stats(s, yp)
                ai.append(a); asp.append(b)
            ic_p.append(float(np.nanmean(ai))); sp_p.append(float(np.nanmean(asp)))
    out = pd.DataFrame({"date": pd.DatetimeIndex(dates), "n_names": nn,
                        "ic": ic_r, "spread": sp_r})
    if perm_seeds:
        out["ic_perm"] = ic_p
        out["spread_perm"] = sp_p
    return out.set_index("date")


# ---------------------------------------------------------------- loading
def load_panel():
    p = pd.read_parquet(PANEL, columns=["ticker", "date", LABEL_COL])
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    return p


def to_matrix(df, date_col, key_col, val_col, names, date_index):
    piv = df.pivot_table(index=date_col, columns=key_col, values=val_col, aggfunc="first")
    piv = piv.reindex(index=date_index, columns=names)
    return piv.values.astype(float)


def load_subject(name, universe):
    """Returns (score_long_df with columns date/key/score, key_col)."""
    if name == "prod_XGB":
        d = pd.read_parquet(XGB_P)[["date", "name", "score", LABEL_COL]]
        d = d.rename(columns={"name": "key"})
    elif name == "certified_clf":
        d = pd.read_parquet(CLF_P)[["date", "ticker", "raw", "fold_idx", LABEL_COL]]
        d = d.rename(columns={"ticker": "key", "raw": "score"})
    elif name == "PatchTST":
        d = pd.read_parquet(PT_P)[["date", "ticker", "raw", "fold_idx"]]
        d = d.rename(columns={"ticker": "key", "raw": "score"})
    else:
        raise ValueError(name)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    if universe is not None:
        d = d[d["key"].isin(universe)]
    return d


# ---------------------------------------------------------------- per subject
def run_subject(sname, sdf, panel, names, perm_seeds, log, tag="inter142"):
    """All frozen measurements for one subject on one universe."""
    res = {"subject": sname, "n_names_universe": len(names)}

    label_axis = pd.DatetimeIndex(sorted(panel["date"].unique()))
    Lmat = to_matrix(panel, "date", "ticker", LABEL_COL, names, label_axis)

    # score axis: dates with >= MIN_NAMES scored names in this universe
    cnt = sdf.groupby("date")["score"].apply(lambda s: s.notna().sum())
    score_axis = pd.DatetimeIndex(sorted(cnt[cnt >= MIN_NAMES].index))
    Smat_full = to_matrix(sdf, "date", "key", "score", names, score_axis)
    res["score_axis"] = dict(n=len(score_axis), first=str(score_axis[0].date()),
                             last=str(score_axis[-1].date()))
    res["label_axis_n"] = len(label_axis)
    # contiguity of the score axis inside the label axis (positional lag == trading-day lag)
    spos = label_axis.get_indexer(score_axis)
    res["score_axis_contiguous_in_label_axis"] = bool(
        (spos >= 0).all() and np.all(np.diff(spos) == 1))

    # ============================ LAG PROFILE (T11) =========================
    al = align_lags(score_axis, label_axis, PROFILE_LAGS, min_dates=BLOCK_LEN)
    log(f"  [{sname}] {al.describe()}")
    res["lag_alignment"] = dict(
        n_common_dates=al.n_dates,
        dropped_per_lag={int(k): int(v) for k, v in al.dropped_per_lag.items()},
        first=str(al.dates[0].date()), last=str(al.dates[-1].date()),
        describe=al.describe())

    cpos_s = pd.Index(score_axis).get_indexer(al.dates)        # rows of Smat
    cpos_l = label_axis.get_indexer(al.dates)                  # rows of Lmat
    Sc = Smat_full[cpos_s]
    prof, prof_per_date = {}, {}
    for L in PROFILE_LAGS:
        pd_tab = arm_per_date(al.dates, Sc, Lmat, cpos_l + L, perm_seeds=0)
        prof_per_date[L] = pd_tab
        prof[L] = {"ic": block_t(pd_tab["ic"]), "spread": block_t(pd_tab["spread"])}
    # paired lag-vs-lag0 on the SAME common sample (T11)
    base = prof_per_date[0]["ic"]
    lag_vs0 = {}
    for L in PROFILE_LAGS:
        if L == 0:
            continue
        lag_vs0[L] = block_t(prof_per_date[L]["ic"] - base)
    res["lag_profile"] = {str(L): prof[L] for L in PROFILE_LAGS}
    res["lag_vs_lag0_paired_ic"] = {str(L): v for L, v in lag_vs0.items()}

    # DIAGNOSTIC (descriptive, not a decision statistic): the same profile on
    # each lag's OWN maximal sample — i.e. what the defective `Y.shift(-lag)`
    # harness would have reported. Quantifies how much of any apparent lag
    # effect was sample drift (T11).
    maximal = {}
    for L in PROFILE_LAGS:
        dts = lag_evaluable_dates(score_axis, label_axis, L)
        t_ = arm_per_date(dts, Smat_full[pd.Index(score_axis).get_indexer(dts)],
                          Lmat, label_axis.get_indexer(dts) + L, perm_seeds=0)
        maximal[str(L)] = {"n_dates": len(dts), "ic": block_t(t_["ic"]),
                           "spread": block_t(t_["spread"])}
    res["lag_profile_maximal_sample_DIAGNOSTIC"] = maximal

    # ======================= ARM SAMPLE (Q1/Q3, T12) ========================
    # both arms of every paired comparison restricted to the SAME score dates
    # BEFORE any statistic: lag-0 evaluable AND persist-eligible.
    a0 = align_lags(score_axis, label_axis, [0], min_dates=1)
    src = lag_evaluable_dates(score_axis, score_axis, PERSIST_LAG)  # dates having a +LAG row
    src_pos = pd.Index(score_axis).get_indexer(src)
    tgt = score_axis[src_pos + PERSIST_LAG]                        # persist-eligible targets
    src_of_tgt = dict(zip(tgt, src))
    arm_dates = a0.dates.intersection(pd.DatetimeIndex(tgt)).sort_values()
    res["arm_sample"] = dict(
        n=len(arm_dates), first=str(arm_dates[0].date()), last=str(arm_dates[-1].date()),
        lag0_evaluable=len(a0.dates), persist_eligible=len(tgt),
        dropped_vs_lag0=len(a0.dates) - len(arm_dates), persist_lag=PERSIST_LAG)

    ai_s = pd.Index(score_axis).get_indexer(arm_dates)
    ai_l = label_axis.get_indexer(arm_dates)
    src_idx = pd.Index(score_axis).get_indexer(
        pd.DatetimeIndex([src_of_tgt[d] for d in arm_dates]))

    real = arm_per_date(arm_dates, Smat_full[ai_s], Lmat, ai_l, perm_seeds=perm_seeds)
    pers = arm_per_date(arm_dates, Smat_full[src_idx], Lmat, ai_l, perm_seeds=0)
    real.to_csv(OUT / f"per_date_{tag}_{sname}_real.csv")
    pers.to_csv(OUT / f"per_date_{tag}_{sname}_persist.csv")

    tab = {}
    for stat in ("ic", "spread"):
        tab[stat] = {
            "real": block_t(real[stat]),
            "perm": block_t(real[stat + "_perm"]),
            "persist": block_t(pers[stat]),
            "d_vs_perm": block_t(real[stat] - real[stat + "_perm"]),
            "d_vs_persist": block_t(real[stat] - pers[stat]),
        }
    res["q1_table"] = tab

    # fold-level t (descriptive secondary; §3 says "block-level t over folds")
    if "fold_idx" in sdf.columns:
        fmap = sdf.groupby("date")["fold_idx"].first()
        for stat in ("ic", "spread"):
            dser = (real[stat] - pers[stat]).dropna()
            f = fmap.reindex(dser.index)
            bm = dser.groupby(f).mean().dropna().values
            if len(bm) >= 2:
                m = float(bm.mean()); se = float(bm.std(ddof=1) / np.sqrt(len(bm)))
                tab[stat]["d_vs_persist_foldlevel"] = dict(
                    mean=m, se=se, t=m / se if se > 0 else np.nan, n_eff=len(bm))

    # robustness: permutation arms on the full lag-0 sample (no persist restriction)
    r0 = arm_per_date(a0.dates,
                      Smat_full[pd.Index(score_axis).get_indexer(a0.dates)],
                      Lmat, label_axis.get_indexer(a0.dates), perm_seeds=perm_seeds)
    res["q3_full_lag0_sample"] = {
        "n_dates": len(a0.dates),
        "ic_d_vs_perm": block_t(r0["ic"] - r0["ic_perm"]),
        "spread_d_vs_perm": block_t(r0["spread"] - r0["spread_perm"]),
    }
    return res


# ---------------------------------------------------------------- self-test
def self_test(panel, names, log):
    """Harness positive/negative control (NOT a decision statistic).
    A score built as (label + noise) must land strongly FRESH-INFORMATIVE;
    a pure-noise score must land near zero."""
    label_axis = pd.DatetimeIndex(sorted(panel["date"].unique()))[-700:]
    sub = panel[panel["date"].isin(label_axis)]
    rng = np.random.default_rng(7)
    out = {}
    for kind in ("oracle_plus_noise", "pure_noise"):
        d = sub.copy()
        if kind == "oracle_plus_noise":
            d["score"] = d[LABEL_COL] + rng.normal(0, 2.0, len(d))
        else:
            d["score"] = rng.normal(0, 1.0, len(d))
        d = d.rename(columns={"ticker": "key"})[["date", "key", "score"]]
        r = run_subject(f"selftest_{kind}", d, panel, names, perm_seeds=5, log=log, tag="selftest")
        out[kind] = {
            "ic_real_t": r["q1_table"]["ic"]["real"]["t"],
            "ic_d_vs_perm_t": r["q1_table"]["ic"]["d_vs_perm"]["t"],
            "ic_d_vs_persist_t": r["q1_table"]["ic"]["d_vs_persist"]["t"],
            "ic_real_mean": r["q1_table"]["ic"]["real"]["mean"],
        }
        log(f"  SELF-TEST {kind}: {out[kind]}")
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--skip-selftest", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    logf = open(OUT / ("run_smoke.log" if a.smoke else "run.log"), "w")

    def log(m):
        print(m); logf.write(m + "\n"); logf.flush()

    perm_seeds = 3 if a.smoke else PERM_SEEDS
    log(f"corrected-eval start  smoke={a.smoke}  perm_seeds={perm_seeds}")

    panel = load_panel()
    names142 = sorted(set(panel["ticker"]))
    subs = ["prod_XGB", "certified_clf", "PatchTST"]
    universes = {s: sorted(set(load_subject(s, None)["key"])) for s in subs}
    inter = sorted(set(universes["prod_XGB"]) & set(universes["certified_clf"])
                   & set(universes["PatchTST"]))
    log(f"142-name intersection check: |inter|={len(inter)}  |panel|={len(names142)}  "
        f"identical={inter == names142}")

    results = {"meta": {
        "prereg": "doc/research/2026-07-29-corrected-signal-evaluation-prereg.md (model#90)",
        "alignment_primitive": "renquant_model_common.lag_alignment (model#89, "
                               "/private/tmp/renquant-model-pr89-review)",
        "label_source": PANEL, "label_col": LABEL_COL,
        "profile_lags": PROFILE_LAGS, "persist_lag": PERSIST_LAG,
        "perm_seeds": perm_seeds, "block_len": BLOCK_LEN, "min_names": MIN_NAMES,
        "universe_intersection_n": len(inter),
        "own_universe_n": {s: len(u) for s, u in universes.items()},
    }}

    if not a.skip_selftest:
        log("== harness self-test (control, not a decision statistic) ==")
        results["self_test"] = self_test(panel, names142, log)

    log("== comparative: 142-name intersection, panel labels ==")
    results["comparative"] = {}
    for s in subs:
        log(f"-- {s}")
        sdf = load_subject(s, set(inter))
        results["comparative"][s] = run_subject(s, sdf, panel, inter, perm_seeds, log)

    log("== descriptive: own universe, subject's own carried label ==")
    results["own_universe"] = {}
    for s in subs:
        if s == "PatchTST":
            results["own_universe"][s] = {"note": "own universe == the 142-name "
                                          "intersection; see comparative"}
            continue
        sdf = load_subject(s, None)
        own_names = sorted(set(sdf["key"]))
        own_lab = sdf[["date", "key", LABEL_COL]].rename(columns={"key": "ticker"})
        own_lab = own_lab.dropna(subset=[LABEL_COL])
        results["own_universe"][s] = run_subject(s, sdf[["date", "key", "score"]],
                                                 own_lab, own_names, perm_seeds, log,
                                                 tag="ownuniv")

    results["meta"]["wall_seconds"] = round(time.time() - t0, 1)
    p = OUT / ("results_smoke.json" if a.smoke else "results.json")
    p.write_text(json.dumps(results, indent=2, default=str))
    log(f"wrote {p}  wall={results['meta']['wall_seconds']}s")
    logf.close()


if __name__ == "__main__":
    main()
