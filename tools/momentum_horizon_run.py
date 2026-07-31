#!/usr/bin/env python3
"""Run the FROZEN prereg doc/research/2026-07-30-momentum-horizon-prereg.md.

Phase S selects ONE (arm, horizon) pair by a mechanical rule and MAY NOT make a
claim. Phase H measures that pair EXACTLY ONCE on dates it has never touched.

    python3 tools/momentum_horizon_run.py --matrix <mom-lib>/momentum_factor_matrix.parquet \\
        --ohlcv-dir <umbrella>/data/ohlcv

Matrix pinned by sha256, ABORTS on mismatch. OHLCV READ-ONLY, used only to build
the label. Nothing is written outside --json-out.
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
sys.path.append(str(Path(__file__).resolve().parent))   # tools/ — shared writers
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402
from per_date_series_io import write_per_date_series  # noqa: E402

MATRIX_SHA256 = "544701bacb552f0fc0e4ea5e5099d2ece28b32cfa6f4dbd57df2757f92ff200e"
HORIZONS = (20, 60, 120, 250)
TOP_FRACTION, MIN_NAMES, N_CONTROLS, CONTROL_BAR = 0.10, 20, 5, 2.0
N_BOOT_REAL, N_BOOT_CTRL = 2000, 600
SHADOW_T, PROGRAMME_T = 1.96, 3.08      # §8 two tiers
SCREEN_END = pd.Timestamp("2021-07-14")
HOLDOUT_START = pd.Timestamp("2021-10-08")
BENCH = "SPY"


def check_pin(p: Path, allow: bool) -> None:
    d = hashlib.sha256(p.read_bytes()).hexdigest()
    if d == MATRIX_SHA256:
        print(f"  matrix sha256={d[:16]}… PIN OK"); return
    if not allow:
        raise SystemExit(f"ABORT: matrix sha256={d} != pinned {MATRIX_SHA256}")
    print(f"  WARNING: sha mismatch {d}")


def per_date_z(v: pd.Series, keys) -> pd.Series:
    g = v.groupby(keys)
    return (v - g.transform("mean")) / g.transform("std").replace(0.0, np.nan)


def build_labels(ohlcv: Path, tickers, dates_needed) -> pd.DataFrame:
    """§4: fwd_h_excess vs SPY, then per-date cross-sectional z-score.

    Built here rather than reused from any existing panel so the horizon set is
    the registered one and the construction is auditable in one place.
    """
    def close_of(t):
        p = ohlcv / t / "1d.parquet"
        if not p.exists():
            return None
        df = pd.read_parquet(p)
        idx = (df.index if isinstance(df.index, pd.DatetimeIndex)
               else pd.to_datetime(df.get("date"), errors="coerce"))
        return pd.Series(df["close"].values, index=pd.DatetimeIndex(idx)).sort_index().dropna()

    spy = close_of(BENCH)
    if spy is None:
        raise SystemExit("ABORT: no SPY series; the label is defined as excess vs SPY")
    rows = []
    for t in tickers:
        c = close_of(t)
        if c is None or len(c) < max(HORIZONS) + 2:
            continue
        sp = spy.reindex(c.index).ffill()
        rec = {"date": c.index, "ticker": t}
        for h in HORIZONS:
            rec[f"fwd_{h}"] = (c.shift(-h) / c - 1.0).values - (sp.shift(-h) / sp - 1.0).values
        rows.append(pd.DataFrame(rec))
    lab = pd.concat(rows, ignore_index=True)
    for h in HORIZONS:
        lab[f"fwd_{h}"] = per_date_z(lab[f"fwd_{h}"], lab["date"])
    return lab


def build_arms(m: pd.DataFrame) -> dict[str, pd.Series]:
    """§5. Seven arms over seven factor inputs."""
    d = m["date"]
    zm = per_date_z(m["mom_12_1"], d)
    gate = m["vol_60"] > m["vol_60"].groupby(d).transform("median")
    a6 = pd.Series(np.nan, index=m.index, dtype=float)
    a6[gate] = zm[gate]
    a6[~gate & m["vol_60"].notna() & m["mom_12_1"].notna()] = 0.0
    return {
        "A1_mom_12_1": m["mom_12_1"],
        "A2_mom_6_1": m["mom_6_1"],
        "A3_hi52_prox": m["hi52_prox"],
        "A4_ma200_ratio": m["ma200_ratio"],
        "A5_vol_scaled": m["mom_12_1"] / m["vol_250"].where(m["vol_250"] > 0),
        "A6_vol_gated": a6,
        "A7_sector_neutral": per_date_z(m["mom_12_1"], [d, m["sector"]]),
    }


def per_date_stats(f: pd.DataFrame, score: str, y: str):
    d = f["date"]
    f = f[d.groupby(d).transform("size") >= MIN_NAMES]
    d = f["date"]
    if f.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    rx = f[score].groupby(d).rank(pct=True); ry = f[y].groupby(d).rank(pct=True)
    g = pd.DataFrame({"d": d.values, "x": rx.values, "y": ry.values})
    g["xy"], g["xx"], g["yy"] = g.x * g.y, g.x ** 2, g.y ** 2
    s = g.groupby("d").agg(n=("x", "size"), sx=("x", "sum"), sy=("y", "sum"),
                           sxy=("xy", "sum"), sxx=("xx", "sum"), syy=("yy", "sum"))
    cov = s.sxy / s.n - (s.sx / s.n) * (s.sy / s.n)
    e1 = (cov / np.sqrt((s.sxx / s.n - (s.sx / s.n) ** 2) *
                        (s.syy / s.n - (s.sy / s.n) ** 2))
          ).replace([np.inf, -np.inf], np.nan).dropna()
    rd = f[score].groupby(d).rank(ascending=False, method="first")
    k = np.maximum(1, np.round(f[score].groupby(d).transform("size") * TOP_FRACTION))
    t = f[y].groupby([d, rd <= k]).mean().unstack()
    if True not in t.columns or False not in t.columns:
        return e1, pd.Series(dtype=float)
    return e1, (t[True] - t[False]).dropna()


def shuffle_within_date(f: pd.DataFrame, seed: int, ycol: str) -> np.ndarray:
    """Permute `ycol` within each `_dcode` group, independent of row order.

    Must hold for an INTERLEAVED frame, not just one pre-sorted by date: each
    output row keeps its own date's label pool. A lexsort-and-reindex form
    only shuffles correctly when rows already arrive grouped by date, because
    it reassigns the (dcode, random)-sorted values back into original row
    order positionally rather than per-group.
    """
    rng = np.random.default_rng(seed)
    y = f[ycol].to_numpy(copy=True)
    for idx in f.groupby("_dcode").indices.values():
        y[idx] = y[rng.permutation(idx)]
    return y


def _unresolved(n: int) -> dict:
    return {"n": int(n), "mean": float("nan"), "t": float("nan"),
            "ci_low": float("nan"), "ci_high": float("nan"), "resolves": False}


def agg(s: pd.Series, block: int, n_boot: int) -> dict:
    """Aggregate a per-date series to a dependence-aware mean and block t.

    THE GUARD BELOW CHECKS TWO DIFFERENT THINGS AND BOTH ARE NEEDED. `len(s) < 3`
    is about having any series at all; it is NOT the condition the block bootstrap
    actually requires, which is **at least two blocks of length `block`**. Between
    the two -- a series with 3+ dates but fewer than two whole blocks -- the old
    code sailed past the guard and `float(r.block_t)` raised `TypeError: float()
    argument must be ... not 'NoneType'`. A short holdout therefore CRASHED the run
    instead of reporting UNRESOLVED, which is the strictly worse failure: a
    statement about power was turned into a stack trace.

    The second check asks the estimator whether it resolved rather than
    re-deriving its block-count rule here -- a re-derivation would be a twin of
    that rule and could drift from it. Behaviour is unchanged on every path that
    previously returned: this can only convert a crash into an honest `resolves:
    False`.
    """
    if len(s) < 3:
        return _unresolved(len(s))
    r = dependence_aware_mean(list(s.values), block_length=block, n_boot=n_boot)
    if r.block_t is None:                      # too few blocks at this geometry
        return _unresolved(len(s))
    return {"n": int(len(s)), "mean": float(r.mean), "t": float(r.block_t),
            "ci_low": float(r.ci_low), "ci_high": float(r.ci_high),
            "resolves": bool(r.resolves)}


def measure(sub: pd.DataFrame, arm: str, h: int, *, controls: bool,
            keep_series: bool = False) -> dict:
    sub = sub.dropna(subset=[arm, f"fwd_{h}"]).copy()
    if sub.empty:
        return {}
    sub["_dcode"] = pd.factorize(sub["date"])[0]
    ycol = f"fwd_{h}"
    e1, e2 = per_date_stats(sub, arm, ycol)
    out = {"rows": len(sub), "E1": agg(e1, h, N_BOOT_REAL), "E2": agg(e2, h, N_BOOT_REAL)}
    if keep_series:
        # The EXACT series handed to `agg` above, not a recomputation. A second
        # call to per_date_stats would be a twin of this one and could drift.
        out["_series"] = {"E1_rank_ic": e1, "E2_top_decile_spread": e2}
    if controls:
        c1, c2 = [], []
        for seed in range(N_CONTROLS):
            sh = sub.copy(); sh[ycol] = shuffle_within_date(sub, seed, ycol)
            x1, x2 = per_date_stats(sh, arm, ycol)
            c1.append(abs(agg(x1, h, N_BOOT_CTRL)["t"]))
            c2.append(abs(agg(x2, h, N_BOOT_CTRL)["t"]))
        out["E1"]["ctl_max"] = max(c1); out["E2"]["ctl_max"] = max(c2)
        out["placebos_clean"] = bool(max(c2) < CONTROL_BAR)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", required=True, type=Path)
    ap.add_argument("--ohlcv-dir", required=True, type=Path)
    ap.add_argument("--allow-input-mismatch", action="store_true")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--per-date-out", default=None,
                    help="CSV path for the HOLDOUT per-date series (the exact "
                         "input to the block bootstrap). Without it the only "
                         "surviving handle on dependence is a handful of block "
                         "means, which cannot separate rho1=0 from rho1=+0.5.")
    a = ap.parse_args(argv)

    print("INPUTS"); check_pin(a.matrix, a.allow_input_mismatch)
    m = pd.read_parquet(a.matrix)
    m["date"] = pd.to_datetime(m["date"])
    print(f"  matrix rows={len(m)} tickers={m.ticker.nunique()} "
          f"{m.date.min().date()}->{m.date.max().date()}")

    print("\n0. §4 LABEL (built here, not reused)")
    lab = build_labels(a.ohlcv_dir, sorted(m.ticker.unique()), None)
    for h in HORIZONS:
        s = lab[f"fwd_{h}"]
        print(f"   fwd_{h:<3} non-null={s.notna().mean():.3f} mean={s.mean():+.4f} sd={s.std():.4f}")
    print("   -> per-date z-scored: units are SD of the cross-section, NOT return")

    df = m.merge(lab, on=["date", "ticker"], how="inner")
    arms = build_arms(df)
    for k, v in arms.items():
        df[k] = v
    screen = df[df.date <= SCREEN_END]
    hold = df[df.date >= HOLDOUT_START]
    print(f"\n   screen rows={len(screen)} dates={screen.date.nunique()} | "
          f"holdout rows={len(hold)} dates={hold.date.nunique()} | "
          f"embargo discarded={len(df) - len(screen) - len(hold)}")

    print("\n=== PHASE S — SELECTION ONLY. NO CLAIM MAY BE MADE FROM THIS TABLE ===")
    sres, eligible = {}, []
    for arm in arms:
        for h in HORIZONS:
            r = measure(screen, arm, h, controls=True)
            if not r:
                continue
            sres[f"{arm}|{h}"] = r
            e2 = r["E2"]
            flag = "clean" if r["placebos_clean"] else "PLACEBO-DIRTY"
            print(f"   {arm:<20} h={h:<4} E2={e2['mean']:+.4f} t={e2['t']:+.2f} "
                  f"ctl={e2['ctl_max']:.2f} n={e2['n']:<5} E1_t={r['E1']['t']:+.2f}  {flag}")
            if r["placebos_clean"]:
                eligible.append((arm, h, e2["t"]))

    if not eligible:
        print("\n=== §6: no (arm, horizon) pair has clean placebos -> UNRESOLVED. "
              "THE HOLDOUT IS NOT TOUCHED. ===")
        return 0
    # §6 selection rule: largest E2 block t; ties within 0.05 -> longer formation.
    best_t = max(t for _, _, t in eligible)
    tied = [(arm, h) for arm, h, t in eligible if best_t - t <= 0.05]
    order = {"A1_mom_12_1": 0, "A5_vol_scaled": 1, "A6_vol_gated": 2,
             "A7_sector_neutral": 3, "A4_ma200_ratio": 4, "A3_hi52_prox": 5,
             "A2_mom_6_1": 6}
    sel_arm, sel_h = sorted(tied, key=lambda x: (order.get(x[0], 9), -x[1]))[0]
    print(f"\n   SELECTED by the frozen rule: {sel_arm} @ h={sel_h} "
          f"(screen E2 t={best_t:+.2f}; {len(tied)} tied within 0.05)")

    print("\n=== PHASE H — the holdout, used ONCE ===")
    hr = measure(hold, sel_arm, sel_h, controls=True, keep_series=True)
    series = hr.pop("_series")
    e2 = hr["E2"]
    print(f"   {sel_arm} h={sel_h}: E2={e2['mean']:+.4f} t={e2['t']:+.2f} "
          f"CI=[{e2['ci_low']:+.4f},{e2['ci_high']:+.4f}] n={e2['n']} "
          f"resolves={e2['resolves']}")
    print(f"   own|t|={abs(e2['t']):.2f} vs placebos max|t|={e2['ctl_max']:.2f} "
          f"(bar {CONTROL_BAR}) | E1 t={hr['E1']['t']:+.2f}")

    print("\n=== §8 VERDICT ===")
    if not hr["placebos_clean"]:
        v = "VOID — placebos not clean. Nothing licensed."
    elif abs(e2["t"]) < SHADOW_T:
        v = (f"UNRESOLVED — |t|={abs(e2['t']):.2f} < {SHADOW_T}. A statement about "
             f"POWER, never about momentum. Nothing licensed.")
    elif abs(e2["t"]) >= PROGRAMME_T and e2["resolves"]:
        v = (f"RESOLVED (programme bar {PROGRAMME_T}) — still SHADOW-FIRST; "
             f"promotion out of shadow needs its own registration on forward dates.")
    elif e2["resolves"]:
        v = (f"SHADOW-ELIGIBLE — |t|={abs(e2['t']):.2f} >= {SHADOW_T}, placebos clean, "
             f"three views agree. Licensed: build the model, deploy to SHADOW ONLY. "
             f"No capital, no sizing, no live path.")
    else:
        v = "UNRESOLVED — the three views do not agree in sign."
    print("   " + v)
    print("   §3 REMINDER: prices are NOT dividend-adjusted and the bias is "
          "sector-correlated, so a positive cannot be attributed to momentum "
          "rather than to a dividend-yield tilt.")
    if a.per_date_out:
        # block_length is `sel_h` (see `agg(e2, h, ...)`), so crossing fraction is
        # min(1, max(0, h - gap)/L) = min(1, h/h) = 1.00 -- FULL label overlap
        # between adjacent blocks. That is recorded, not hidden: it is precisely
        # why the series must survive the run, so the bar can be calibrated on
        # this data instead of assumed from another programme's rho1.
        meta = write_per_date_series(
            series, a.per_date_out,
            provenance={
                "run": "GOAL-7 momentum horizon sweep, PHASE H holdout",
                "arm": sel_arm, "horizon_days": sel_h,
                "statistic_E1": "per-date Spearman rank IC",
                "statistic_E2": "per-date top-decile spread (top 10% - rest)",
                "block_length_used_by_agg": sel_h,
                "label_horizon_days": sel_h,
                "gap_between_blocks": 0,
                "crossing_fraction": 1.0,
                "crossing_note": (
                    "L = h with gap 0 gives crossing 1.00, the MAXIMUM overlap, not "
                    "a remedy for it. The Student bar over these blocks is therefore "
                    "NOT calibrated; treat |t| here as uncalibrated until a "
                    "dependence-preserving null is run ON THIS FILE."),
                "units": "E2 in SD of the cross-section (labels are per-date z-scores)",
            })
        print(f"\n   per-date series written: {meta['n_rows']} rows "
              f"{meta['first_date']} -> {meta['last_date']} -> {meta['path']}")

    if a.json_out:
        Path(a.json_out).write_text(json.dumps(
            {"screen": sres, "selected": [sel_arm, sel_h], "holdout": hr,
             "verdict": v}, indent=2, default=str))
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
