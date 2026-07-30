#!/usr/bin/env python3
"""POST-VERDICT diagnostics commissioned by the §8 adversarial review.

**These are NOT part of the registered design and CANNOT change the verdict.**
The verdict (VOLATILITY-TILT) was computed and committed at 97245c2 before this
file existed; everything here is a check the reviewer asked for, re-measured by
the author rather than taken on the reviewer's word.

Three things, in the order the review raised them:

1. **The asymmetry test** (review finding 4). §4's kill condition is only
   meaningful if the explanation runs one way. Running `vol_60_tr` through the
   IDENTICAL harness, and orthogonalising it to `u`, tells you which of the two
   is the mediator. This is a diagnostic OF THE CONTROL, not a new candidate
   arm — nothing here is a two-sided transform and nothing here could have
   produced a pass.
2. **Minimum detectable effect and power** for the §4 residual arm (finding 7),
   so "did not clear" is separable from "could not have cleared".
3. **The §5.1 positive control's finite-width bias** re-measured at four widths
   with tighter Monte-Carlo error (finding 9), plus the prior probability that
   the registered construction would have VOIDed this run on its own artifact.

    python3 tools/goal7_stage1_postreview_diagnostics.py \
        --matrix <sp>/momentum_factor_matrix_tr.parquet \
        --tr     <sp>/total_return_close.parquet \
        --out-dir doc/research/data/2026-07-30-goal7-stage1-two-sided-tail
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, nct, spearmanr, t as student_t

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import goal7_stage1_two_sided_run as G  # noqa: E402


def build_panel(matrix: Path, tr_path: Path) -> tuple[G.Panel, dict]:
    """Rebuild EXACTLY the registered evaluation panel (same pins, same
    eligibility, same window). Aborts on any digest or partition divergence."""
    G.check_pin(matrix, G.PIN_MATRIX)
    G.check_pin(tr_path, G.PIN_TR)
    m = pd.read_parquet(matrix)
    m["date"] = pd.to_datetime(m["date"])
    tr = pd.read_parquet(tr_path)
    tr["date"] = pd.to_datetime(tr["date"])
    w = {t_: g.set_index("date").sort_index()
         for t_, g in tr.groupby("ticker", observed=True)}
    spy = w["SPY"]
    rows = []
    for t_, d in w.items():
        c = d["tr_close"]
        b = spy["tr_close"].reindex(c.index).ffill()
        rows.append(pd.DataFrame({
            "date": d.index, "ticker": t_,
            "fwd_raw": ((c.shift(-G.H) / c - 1.0).to_numpy()
                        - (b.shift(-G.H) / b - 1.0).to_numpy())}))
    lab = pd.concat(rows, ignore_index=True)
    lab["fwd_z"] = G.per_date_z(lab["fwd_raw"], lab["date"])
    df = m[["date", "ticker", G.MOM_COL, G.VOL_COL]].merge(
        lab, on=["date", "ticker"], how="inner")
    elig = df.dropna(subset=[G.MOM_COL, G.VOL_COL, "fwd_raw", "fwd_z"])
    cnt = elig.groupby("date").size()
    elig = elig[elig["date"].isin(cnt[cnt >= G.MIN_NAMES].index)]
    ev = elig[(elig["date"] >= G.EVAL_START) & (elig["date"] <= G.EVAL_END)]
    p = G.Panel(ev)
    if p.n_dates != G.PIN_N_EVAL:
        raise SystemExit(f"ABORT: N_eval={p.n_dates} != {G.PIN_N_EVAL}")
    return p, {"n_eval": p.n_dates, "n_blocks": p.n_dates // G.BLOCK}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", required=True, type=Path)
    ap.add_argument("--tr", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    p, meta = build_panel(a.matrix, a.tr)
    nb = meta["n_blocks"]
    tcrit = float(student_t.ppf(0.975, nb - 1))
    lab = p.df["fwd_z"].to_numpy(float)
    mom = p.df[G.MOM_COL].to_numpy(float)
    vol = p.df[G.VOL_COL].to_numpy(float)
    z_mom, z_vol = p.gz(mom), p.gz(vol)
    u, av = np.abs(z_mom), np.abs(z_vol)
    out: dict = {"note": "POST-VERDICT diagnostics; not registered; cannot "
                         "change the verdict computed at 97245c2",
                 "n_eval": meta["n_eval"], "n_blocks": nb, "t_crit_leg": tcrit}

    # ---- 1. asymmetry: which of u and volatility is the mediator? -----------
    scores = {
        "u = |z(mom_12_1_tr)|                     [registered treatment]": u,
        "u  ⟂ |z(vol_60_tr)|                      [registered §4 kill]": p.residualise(u, av),
        "z(vol_60_tr)": z_vol,
        "|z(vol_60_tr)|": av,
        "z(vol_60_tr)  ⟂ u": p.residualise(z_vol, u),
        "|z(vol_60_tr)| ⟂ u": p.residualise(av, u)}
    print(f"\n{'score':<52}{'spread':>10}{'t':>9}{'clears':>8}")
    asym = {}
    for nm, s in scores.items():
        st = G.block_t(p.top_spread(s, lab), nb)
        asym[nm] = {"spread": st["block_mean"], "t": st["t"],
                    "clears_t_leg": bool(abs(st["t"]) >= tcrit)}
        print(f"  {nm:<50}{st['block_mean']:>+10.4f}{st['t']:>+9.3f}"
              f"{str(abs(st['t']) >= tcrit):>8}")
    out["asymmetry"] = asym
    r2 = []
    for gi in range(p.n_dates):
        s0, n0 = p.starts[gi], p.counts[gi]
        r2.append(np.corrcoef(u[s0:s0 + n0], av[s0:s0 + n0])[0, 1] ** 2)
    out["mean_per_date_r2_u_on_absz_vol"] = float(np.mean(r2))
    out["pooled_corr_u_absz_vol"] = float(np.corrcoef(u, av)[0, 1])
    print(f"\n  mean per-date R² of u on |z(vol_60_tr)| = "
          f"{np.mean(r2):.4f}  (pooled corr {out['pooled_corr_u_absz_vol']:+.5f})")

    # ---- 2. MDE and power for the §4 residual arm --------------------------
    resid = G.block_t(p.top_spread(p.residualise(u, av), lab), nb)
    raw = G.block_t(p.top_spread(u, lab), nb)
    mde = tcrit * resid["block_sd"] / math.sqrt(nb)
    power = float(nct.sf(tcrit, nb - 1, abs(resid["t"]))
                  + nct.cdf(-tcrit, nb - 1, abs(resid["t"])))
    out["power"] = {
        "residual_block_sd": resid["block_sd"], "MDE_spread": mde,
        "observed_spread": resid["block_mean"],
        "observed_over_MDE": resid["block_mean"] / mde,
        "power_at_observed_effect": power,
        "retention_required_of_raw_spread": mde / raw["block_mean"],
        "retention_achieved": resid["block_mean"] / raw["block_mean"]}
    print(f"\n  MDE = {tcrit:.4f}×{resid['block_sd']:.5f}/√{nb} = {mde:.4f} SD; "
          f"observed {resid['block_mean']:.4f} = {resid['block_mean'] / mde:.1%} of MDE; "
          f"power at that effect = {power:.1%}")
    print(f"  the kill condition demanded the residual retain "
          f"{mde / raw['block_mean']:.1%} of the raw spread; it retained "
          f"{resid['block_mean'] / raw['block_mean']:.1%}")

    # ---- 3. §5.1 positive-control finite-width bias -------------------------
    print("\n  §5.1 construction, Monte-Carlo by cross-section width:")
    rng = np.random.default_rng(20260730)
    bias = {}
    for n, D in ((31, 20000), (128, 20000), (512, 20000), (4096, 3000)):
        ns = norm.ppf((np.arange(n) + 0.5) / n)
        ic = np.empty(D)
        for i in range(D):
            r = rng.normal(size=n)
            wv = ns[np.argsort(np.argsort(r))]
            e = ns[np.argsort(np.argsort(rng.random(n)))]
            ic[i] = spearmanr(G.ALPHA_PC * wv + math.sqrt(1 - G.ALPHA_PC ** 2) * e,
                              r).statistic
        se = float(ic.std(ddof=1) / math.sqrt(D))
        bias[n] = {"mean_ic": float(ic.mean()), "mc_se": se, "draws": D,
                   "per_date_sd": float(ic.std(ddof=1))}
        print(f"    n={n:<6} mean IC = {ic.mean():+.5f} ± {se:.5f} (MC s.e., "
              f"{D} draws)")
    n_w = int(np.median(p.counts))
    exp_ic, sd_ic = bias[128]["mean_ic"], bias[128]["per_date_sd"]
    se_run = sd_ic / math.sqrt(nb * G.BLOCK)
    p_void = float(norm.cdf((0.04 - exp_ic) / se_run)
                   + norm.sf((0.06 - exp_ic) / se_run))
    bias["prior_void_probability_at_this_width"] = p_void
    bias["run_se_of_mean_ic"] = se_run
    bias["corpus_median_width"] = n_w
    print(f"    at this corpus's median width {n_w}, expected mean IC "
          f"{exp_ic:.5f}, s.e. over {nb * G.BLOCK} dates {se_run:.5f} → prior "
          f"P(|mean − 0.05| > 0.01, i.e. VOID) = {p_void:.1%}")
    out["positive_control_finite_width_bias"] = bias

    dest = a.out_dir / "postreview_diagnostics.json"
    dest.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
