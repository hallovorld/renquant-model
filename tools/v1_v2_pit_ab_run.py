#!/usr/bin/env python3
"""Run Stage A of doc/research/2026-07-30-v1-v2-pit-ab-prereg.md.

VOID as of `6c992fd`: the STAGE A RESULT section is marked "SUPERSEDED AND
VOID. DO NOT CITE." This script still implements the arms/gate that produced
that voided execution. It ABORTS at startup (NOT_YET_IMPLEMENTED below) until
three amendments are reflected in code, not just in the doc:
  Amendment 2a  restamp_v1() must join v1's values to v2's real `filed` date
                per fact instead of the retired +60d synthetic constant
                (column name TBD against v2's actual schema — not guessed
                here to avoid shipping a second silently-wrong
                implementation)
  Amendment 2b  the §6 READING gate must use E1 as the sole primary estimand,
                require E2 sign-corroboration, and label a resolved-but-
                uncorroborated feature PRIMARY-ONLY, NOT CORROBORATED instead
                of opening the gate; JOINT_BONFERRONI_T is updated 3.24 ->
                3.29 below to match, but the gate LOGIC itself is unchanged
                pending this reimplementation
  Amendment 2c  the placebo VOID rule (max |t| < 2.0 over 5 within-date
                shuffles, already CONTROL_BAR below) is now preregistered —
                no code change needed here, listed for completeness

Three arms on an identical support, per feature (Amendment 1):
  B_v1      v1 values at v1's shipped availability stamps
  B_v1_lag  v1 VALUES re-stamped to v2's real filed date per fact (2a)
  B_v2      v2 as-filed values at real filed availability

B_v1 - B_v1_lag isolates the look-ahead contribution (values held identical);
B_v1_lag - B_v2 isolates the value/source contribution (discipline held identical).

Stage B (retrain A/B) is NOT run here and is not licensed by this script.

    python3 tools/v1_v2_pit_ab_run.py --v1 <...>/sec_fundamentals_daily.parquet \\
        --v2 <...>/pit_fundamentals_830.parquet --ohlcv-dir <...>/data/ohlcv
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402

FEATURES = ("roe", "gross_profitability", "asset_growth")
LAG_DAYS = 60                 # RETIRED (Amendment 2a): p95, not a verified
                               # upper bound. Kept only so restamp_v1's body
                               # still parses; Amendment 2a requires replacing
                               # this constant with a join against v2's real
                               # filed date before use.
HORIZON = 60
BLOCK, N_BOOT_REAL, N_BOOT_CTRL = 60, 2000, 600
TOP_FRACTION, MIN_NAMES, N_CONTROLS, CONTROL_BAR = 0.10, 20, 5, 2.0
JOINT_BONFERRONI_T = 3.29     # 49 joint tests (Amendment 2b)
MIN_NONNULL_DAYS = 250
BENCH = "SPY"
NOT_YET_IMPLEMENTED = (
    "ABORT: this runner still implements the design that produced the VOID "
    "`6c992fd` execution (research doc: 'STAGE A RESULT -- SUPERSEDED AND "
    "VOID. DO NOT CITE.'). restamp_v1() (Amendment 2a: v2 real filed-date "
    "join) and the §6 READING gate (Amendment 2b: E1-primary + "
    "E2-corroboration) must be reimplemented before this script may run "
    "again -- see the module docstring.")


# --------------------------------------------------------------------------
# §4 binding requirement: the shuffle must be a TRUE within-date permutation.
# The immediately preceding study (momentum-horizon) was ABORTED - INVALID
# CONTROL because its frame was ticker-major and lexsort leaked labels across
# dates. This is checked BEFORE any arm runs, and a failure ABORTS.
# --------------------------------------------------------------------------
def shuffle_within_date(frame: pd.DataFrame, seed: int, ycol: str) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return frame[ycol].values[
        np.lexsort((rng.random(len(frame)), frame["_dcode"].values))]


def assert_shuffle_is_a_within_date_permutation() -> None:
    """Self-check on a deliberately INTERLEAVED frame, which is the case that
    broke last time. Sorted-only fixtures would pass on the broken code."""
    inter = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01", "2020-01-02"] * 6),
        "y": [10.0, 20.0, 11.0, 21.0, 12.0, 22.0, 13.0, 23.0, 14.0, 24.0, 15.0, 25.0],
    })
    srt = inter.sort_values("date", kind="stable").reset_index(drop=True)
    srt["_dcode"] = pd.factorize(srt["date"])[0]
    for seed in range(12):
        out = srt.copy(); out["y"] = shuffle_within_date(srt, seed, "y")
        for d, g in out.groupby("date"):
            want = np.sort(srt.loc[srt.date == d, "y"].values)
            got = np.sort(g["y"].values)
            if not np.allclose(want, got):
                raise SystemExit(
                    "ABORT (§4): the shuffle is not a within-date permutation "
                    f"on an interleaved frame (date {d}, seed {seed}): "
                    f"{got.tolist()} != {want.tolist()}")
    # And prove the check has teeth: an UNSORTED frame must be rejected.
    unsorted = inter.copy()
    unsorted["_dcode"] = pd.factorize(unsorted["date"])[0]
    leaked = False
    for seed in range(12):
        out = unsorted.copy(); out["y"] = shuffle_within_date(unsorted, seed, "y")
        for d, g in out.groupby("date"):
            want = np.sort(unsorted.loc[unsorted.date == d, "y"].values)
            if not np.allclose(want, np.sort(g["y"].values)):
                leaked = True
    if not leaked:
        raise SystemExit("ABORT: the self-check cannot detect the known defect, "
                         "so it certifies nothing.")
    print("  §4 shuffle self-check PASSED (sorted frame is a true within-date "
          "permutation; the check demonstrably rejects an unsorted one)")


def per_date_z(v: pd.Series, keys) -> pd.Series:
    g = v.groupby(keys)
    return (v - g.transform("mean")) / g.transform("std").replace(0.0, np.nan)


def build_label(ohlcv: Path, tickers) -> pd.DataFrame:
    def close_of(t):
        p = ohlcv / t / "1d.parquet"
        if not p.exists():
            return None
        df = pd.read_parquet(p)
        idx = (df.index if isinstance(df.index, pd.DatetimeIndex)
               else pd.to_datetime(df.get("date"), errors="coerce"))
        return pd.Series(df["close"].values,
                         index=pd.DatetimeIndex(idx)).sort_index().dropna()
    spy = close_of(BENCH)
    if spy is None:
        raise SystemExit("ABORT: no SPY; the label is excess vs SPY")
    rows = []
    for t in tickers:
        c = close_of(t)
        if c is None or len(c) < HORIZON + 2:
            continue
        sp = spy.reindex(c.index).ffill()
        rows.append(pd.DataFrame({
            "date": c.index, "ticker": t,
            "y": (c.shift(-HORIZON) / c - 1.0).values
                 - (sp.shift(-HORIZON) / sp - 1.0).values}))
    lab = pd.concat(rows, ignore_index=True)
    lab["y"] = per_date_z(lab["y"], lab["date"])
    return lab.dropna(subset=["y"])


def restamp_v1(v1: pd.DataFrame, feature: str, dates_by_ticker) -> pd.DataFrame:
    """B_v1_lag: v1's own (fiscal_period_end -> value) pairs, re-joined with
    availability = fiscal_period_end + LAG_DAYS. Same VALUES, different stamp."""
    fpe = f"{feature}_source_fiscal_period_end"
    src = (v1.dropna(subset=[feature, fpe])[["ticker", fpe, feature]]
             .drop_duplicates(["ticker", fpe]).rename(columns={fpe: "fpe"}))
    src["fpe"] = pd.to_datetime(src["fpe"])
    src["avail"] = src["fpe"] + pd.Timedelta(days=LAG_DAYS)
    out = []
    for t, grp in src.groupby("ticker", sort=False):
        dts = dates_by_ticker.get(t)
        if dts is None or len(dts) == 0:
            continue
        g = grp.sort_values("avail")
        joined = pd.merge_asof(
            pd.DataFrame({"date": pd.DatetimeIndex(sorted(dts))}),
            g[["avail", feature]].rename(columns={"avail": "date"}),
            on="date", direction="backward")
        joined["ticker"] = t
        out.append(joined)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def per_date_stats(f: pd.DataFrame, score: str, ycol: str):
    d = f["date"]
    f = f[d.groupby(d).transform("size") >= MIN_NAMES]
    d = f["date"]
    if f.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    rx = f[score].groupby(d).rank(pct=True); ry = f[ycol].groupby(d).rank(pct=True)
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
    t = f[ycol].groupby([d, rd <= k]).mean().unstack()
    if True not in t.columns or False not in t.columns:
        return e1, pd.Series(dtype=float)
    return e1, (t[True] - t[False]).dropna()


def agg(s: pd.Series, n_boot: int) -> dict:
    if len(s) < 3:
        return {"n": len(s), "mean": float("nan"), "t": float("nan"),
                "resolves": False, "ci_low": float("nan"), "ci_high": float("nan")}
    r = dependence_aware_mean(list(s.values), block_length=BLOCK, n_boot=n_boot)
    return {"n": int(len(s)), "mean": float(r.mean), "t": float(r.block_t),
            "ci_low": float(r.ci_low), "ci_high": float(r.ci_high),
            "resolves": bool(r.resolves)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--v1", required=True, type=Path)
    ap.add_argument("--v2", required=True, type=Path)
    ap.add_argument("--ohlcv-dir", required=True, type=Path)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)

    raise SystemExit(NOT_YET_IMPLEMENTED)

    print("§4 PRE-FLIGHT")
    assert_shuffle_is_a_within_date_permutation()

    keep1 = ["date", "ticker"] + list(FEATURES) + [
        f"{f}_source_fiscal_period_end" for f in FEATURES]
    v1 = pd.read_parquet(a.v1, columns=keep1)
    v1["date"] = pd.to_datetime(v1["date"])
    v2 = pd.read_parquet(a.v2, columns=["date", "ticker"] + list(FEATURES))
    v2["date"] = pd.to_datetime(v2["date"])
    print(f"\nv1 rows={len(v1)} tickers={v1.ticker.nunique()} "
          f"{v1.date.min().date()}->{v1.date.max().date()}")
    print(f"v2 rows={len(v2)} tickers={v2.ticker.nunique()} "
          f"{v2.date.min().date()}->{v2.date.max().date()}")

    # §2 common support
    ok1 = {t for t, g in v1.groupby("ticker")
           if all(g[f].notna().sum() >= MIN_NONNULL_DAYS for f in FEATURES)}
    ok2 = {t for t, g in v2.groupby("ticker")
           if all(g[f].notna().sum() >= MIN_NONNULL_DAYS for f in FEATURES)}
    tickers = sorted(ok1 & ok2)
    dates = pd.DatetimeIndex(sorted(set(v1.date.unique()) & set(v2.date.unique())))
    print(f"\n§2 COMMON SUPPORT: tickers v1={len(ok1)} v2={len(ok2)} "
          f"INTERSECTION={len(tickers)}  common dates={len(dates)}")
    v1 = v1[v1.ticker.isin(tickers) & v1.date.isin(dates)]
    v2 = v2[v2.ticker.isin(tickers) & v2.date.isin(dates)]
    dates_by_ticker = {t: g.date.values for t, g in v1.groupby("ticker")}

    lab = build_label(a.ohlcv_dir, tickers)
    print(f"label rows={len(lab)} (fwd_{HORIZON}d excess vs SPY, per-date z; "
          f"sd={lab.y.std():.4f} => units are SD, not return)")

    arms: dict[str, pd.DataFrame] = {"B_v1": v1[["date", "ticker"] + list(FEATURES)],
                                     "B_v2": v2}
    lagged = None
    for f in FEATURES:
        piece = restamp_v1(v1, f, dates_by_ticker)
        lagged = piece if lagged is None else lagged.merge(
            piece, on=["date", "ticker"], how="outer")
    arms["B_v1_lag"] = lagged
    for k, v in arms.items():
        print(f"  arm {k:<10} rows={len(v)}")

    results, per_date_store = {}, {}
    for arm, frame in arms.items():
        m = frame.merge(lab, on=["date", "ticker"], how="inner")
        for feat in FEATURES:
            sub = m.dropna(subset=[feat, "y"]).sort_values(
                "date", kind="stable").reset_index(drop=True)
            if sub.empty:
                continue
            sub["_dcode"] = pd.factorize(sub["date"])[0]
            e1, e2 = per_date_stats(sub, feat, "y")
            per_date_store[(arm, feat)] = e2
            real = {"E1": agg(e1, N_BOOT_REAL), "E2": agg(e2, N_BOOT_REAL)}
            c1, c2 = [], []
            for seed in range(N_CONTROLS):
                sh = sub.copy(); sh["y"] = shuffle_within_date(sub, seed, "y")
                x1, x2 = per_date_stats(sh, feat, "y")
                c1.append(abs(agg(x1, N_BOOT_CTRL)["t"]))
                c2.append(abs(agg(x2, N_BOOT_CTRL)["t"]))
            real["E1"]["ctl_max"], real["E2"]["ctl_max"] = max(c1), max(c2)
            real["placebos_clean"] = bool(max(c2) < CONTROL_BAR)
            results[f"{arm}|{feat}"] = real
            e = real["E2"]
            print(f"  {arm:<10} {feat:<20} E2={e['mean']:+.4f} t={e['t']:+.2f} "
                  f"ctl={e['ctl_max']:.2f} n={e['n']:<5} E1_t={real['E1']['t']:+.2f} "
                  f"{'clean' if real['placebos_clean'] else 'PLACEBO-DIRTY'}")

    print("\n=== §3 DECOMPOSITION (descriptive, NOT counted as tests) ===")
    contrasts = {}
    for feat in FEATURES:
        for lo, hi, name in (("B_v1", "B_v1_lag", "look-ahead"),
                             ("B_v1_lag", "B_v2", "value/source")):
            A, Bb = per_date_store.get((lo, feat)), per_date_store.get((hi, feat))
            if A is None or Bb is None:
                continue
            common = A.index.intersection(Bb.index)
            d = (A.loc[common] - Bb.loc[common]).dropna()
            r = agg(d, N_BOOT_REAL)
            contrasts[f"{lo}-{hi}|{feat}"] = r
            print(f"  {name:<13} {feat:<20} {lo} - {hi} = {r['mean']:+.4f} "
                  f"t={r['t']:+.2f} n={r['n']}")

    print("\n=== §6 READING (per feature) ===")
    gate_open = False
    for feat in FEATURES:
        c = contrasts.get(f"B_v1_lag-B_v2|{feat}")
        v1r, lagr = results.get(f"B_v1|{feat}"), results.get(f"B_v1_lag|{feat}")
        la = contrasts.get(f"B_v1-B_v1_lag|{feat}")
        if la and v1r and lagr and v1r["E2"]["mean"] > lagr["E2"]["mean"]:
            print(f"  {feat}: B_v1 scores ABOVE B_v1_lag by {la['mean']:+.4f} "
                  f"(t={la['t']:+.2f}) — §3 registered this as the EXPECTED "
                  f"SIGNATURE OF CONTAMINATION, not evidence for v1")
        if c and abs(c["t"]) >= JOINT_BONFERRONI_T and (
                results.get(f'B_v1_lag|{feat}', {}).get('placebos_clean')
                and results.get(f'B_v2|{feat}', {}).get('placebos_clean')):
            gate_open = True
            print(f"  {feat}: SOURCE DIFFERENCE MEASURED (|t|={abs(c['t']):.2f} "
                  f">= {JOINT_BONFERRONI_T}) — Stage B may be registered separately")
        elif c:
            print(f"  {feat}: no measurable source difference "
                  f"(|t|={abs(c['t']):.2f} < {JOINT_BONFERRONI_T})")
    print("\n  STAGE B GATE: " + ("OPEN — register Stage B separately"
          if gate_open else "CLOSED — Stage B is NOT run. v2 is still preferred "
          "on CORRECTNESS grounds; look-ahead is a defect, not a horse race."))
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(
            {"results": results, "contrasts": contrasts,
             "n_tickers": len(tickers), "bar": JOINT_BONFERRONI_T,
             "stage_b_gate": "OPEN" if gate_open else "CLOSED"}, indent=2))
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
