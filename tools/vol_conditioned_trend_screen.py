#!/usr/bin/env python3
"""Run the FROZEN screen in doc/research/2026-07-29-vol-conditioned-momentum-reversion-screen.md.

Tests ONE hypothesis: that the sign of the price-trend effect depends on the
volatility state, which would explain why unconditional momentum and reversal
both average to nothing on this universe.

    python3 tools/vol_conditioned_trend_screen.py \\
        --panel /Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet

The panel is pinned by sha256 and the run ABORTS on a mismatch: a different
panel must not be able to reproduce different numbers under the frozen
document's name. The panel is a production file, opened READ-ONLY.

Every arm, estimand, control protocol and threshold here is fixed by that
document. This script contains no free choices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402

PANEL_SHA256 = "7defdacf97f8eb057a9a56a2eb7bc6eb48bc33adb9fd00a2a6c36943be87daa5"
LABEL = "fwd_60d_excess"
BLOCK = 60
N_BOOT = 2000
TOP_FRACTION = 0.10
MIN_NAMES = 20
N_CONTROLS = 5
N_FALSE_FLAG = 30
CONTROL_BAR = 2.0
# 5 arms x 2 estimands = 10 tests; Bonferroni alpha=0.05 two-sided.
BONFERRONI_T = 2.81
NEEDED = ["date", "ticker", "STD60", "ROC5", "ROC20", "ROC60", LABEL]


def check_pin(path: Path, allow_mismatch: bool) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest == PANEL_SHA256:
        print(f"  panel sha256={digest[:16]}… PIN OK")
        return
    msg = f"panel sha256={digest} != pinned {PANEL_SHA256}"
    if not allow_mismatch:
        raise SystemExit(f"ABORT: {msg}\n  The frozen design registered the "
                         f"pinned panel. Re-freezing is a new registration.")
    print(f"  WARNING: {msg}")


def ret(roc: pd.Series) -> pd.Series:
    """n-day return from Alpha158 ROC{n} = close[t-n]/close[t] (INVERSE momentum)."""
    return 1.0 / roc.where(roc > 0) - 1.0


def per_date_z(values: pd.Series, dates: pd.Series) -> pd.Series:
    grp = values.groupby(dates)
    return (values - grp.transform("mean")) / grp.transform("std").replace(0.0, np.nan)


def per_date_rank_pct(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates).rank(pct=True)


def build_arms(panel: pd.DataFrame) -> pd.DataFrame:
    """§3 factor definitions and §4 arms. Formulaic; nothing fitted."""
    d = panel["date"]
    out = pd.DataFrame({"date": d, "ticker": panel["ticker"], "y": panel[LABEL]})
    mom60 = ret(panel["ROC60"])
    rev20 = -ret(panel["ROC20"])
    rev5 = -ret(panel["ROC5"])
    vol_pct = per_date_rank_pct(panel["STD60"], d)
    volq = pd.Series(1, index=panel.index, dtype="float64")
    volq[vol_pct <= 1.0 / 3.0] = 0.0
    volq[vol_pct > 2.0 / 3.0] = 2.0
    volq[panel["STD60"].isna()] = np.nan

    zm, zr = per_date_z(mom60, d), per_date_z(rev20, d)
    n1 = pd.Series(np.nan, index=panel.index, dtype="float64")
    n1[volq == 2.0] = zm[volq == 2.0]
    n1[volq == 0.0] = zr[volq == 0.0]
    n1[volq == 1.0] = 0.0

    out["R1"], out["R2"], out["R3"] = mom60, rev5, rev20
    out["N1"] = n1
    out["N2"] = 0.5 * zm + 0.5 * zr
    return out


def per_date_stats(frame: pd.DataFrame, score: str, ycol: str) -> tuple[pd.Series, pd.Series]:
    """Return (E1 spearman IC, E2 top-decile spread) per date, vectorised.

    Both use the SAME row set, so a divergence between them is about the cut,
    not about the sample.
    """
    d = frame["date"]
    n = d.groupby(d).transform("size")
    keep = n >= MIN_NAMES
    frame, d = frame[keep], d[keep]
    if frame.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    # E1: Spearman == Pearson on per-date ranks. Closed-form groupwise sums so
    # this stays vectorised across the ~30 real+placebo passes.
    rx = frame[score].groupby(d).rank(pct=True)
    ry = frame[ycol].groupby(d).rank(pct=True)
    g = pd.DataFrame({"d": d.values, "x": rx.values, "y": ry.values})
    g["xy"], g["xx"], g["yy"] = g.x * g.y, g.x ** 2, g.y ** 2
    s = g.groupby("d").agg(n=("x", "size"), sx=("x", "sum"), sy=("y", "sum"),
                           sxy=("xy", "sum"), sxx=("xx", "sum"), syy=("yy", "sum"))
    cov = s.sxy / s.n - (s.sx / s.n) * (s.sy / s.n)
    vx = s.sxx / s.n - (s.sx / s.n) ** 2
    vy = s.syy / s.n - (s.sy / s.n) ** 2
    e1 = (cov / np.sqrt(vx * vy)).replace([np.inf, -np.inf], np.nan).dropna()

    # E2: k = round(0.10 * n), k >= 1 -- the frozen definition, not a rank-pct
    # approximation, so it matches renquant-model#101 §2 exactly.
    rank_desc = frame[score].groupby(d).rank(ascending=False, method="first")
    size = frame[score].groupby(d).transform("size")
    k = np.maximum(1, np.round(size * TOP_FRACTION))
    top = rank_desc <= k
    t = frame[ycol].groupby([d, top]).mean().unstack()
    if True not in t.columns or False not in t.columns:
        return e1, pd.Series(dtype=float)
    e2 = (t[True] - t[False]).dropna()
    return e1, e2


def shuffle_within_date(frame: pd.DataFrame, seed: int) -> np.ndarray:
    """Permute the label within each date. The frame MUST already be date-sorted:
    then a lexsort by (date, random key) yields, block by block, the same dates
    in the same group sizes with the labels reordered inside each block."""
    rng = np.random.default_rng(seed)
    order = np.lexsort((rng.random(len(frame)), frame["_dcode"].values))
    return frame["y"].values[order]


def aggregate(series: pd.Series, n_boot: int = N_BOOT) -> dict:
    if len(series) < 3:
        return {"n": len(series), "mean": float("nan"), "t": float("nan"),
                "ci_low": float("nan"), "ci_high": float("nan"), "resolves": False}
    r = dependence_aware_mean(list(series.values), block_length=BLOCK, n_boot=n_boot)
    return {"n": int(len(series)), "mean": float(r.mean), "t": float(r.block_t),
            "ci_low": float(r.ci_low), "ci_high": float(r.ci_high),
            "resolves": bool(r.resolves)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", required=True, type=Path)
    ap.add_argument("--allow-input-mismatch", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    print("INPUT")
    check_pin(args.panel, args.allow_input_mismatch)
    panel = pd.read_parquet(args.panel, columns=NEEDED)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.dropna(subset=[LABEL]).sort_values("date", kind="stable")
    panel = panel.reset_index(drop=True)

    print(f"\n0. LABEL UNITS ({LABEL}) — measured, not assumed")
    y = panel[LABEL]
    print(f"   rows={len(panel)}  dates={panel.date.nunique()}  "
          f"tickers={panel.ticker.nunique()}")
    print(f"   mean={y.mean():+.4f}  sd={y.std():.4f}  "
          f"-> the statistic is in SD, not return")

    arms = build_arms(panel)
    arms["_dcode"] = pd.factorize(arms["date"])[0]
    arm_ids = ["R1", "R2", "R3", "N1", "N2"]
    labels = {"R1": "mom60 (replication)", "R2": "rev5 (replication)",
              "R3": "rev20 (replication)", "N1": "vol-conditional (HYPOTHESIS)",
              "N2": "unconditional blend (must be beaten)"}
    results: dict[str, dict] = {}

    for arm in arm_ids:
        sub = arms.dropna(subset=[arm, "y"]).copy()
        print(f"\n=== ARM {arm}: {labels[arm]}  (rows={len(sub)}) ===")
        e1, e2 = per_date_stats(sub, arm, "y")
        real = {"E1": aggregate(e1), "E2": aggregate(e2)}
        ctrl: dict[str, list[dict]] = {"E1": [], "E2": []}
        for seed in range(N_CONTROLS):
            shuffled = sub.copy()
            shuffled["y"] = shuffle_within_date(sub, seed)
            c1, c2 = per_date_stats(shuffled, arm, "y")
            ctrl["E1"].append(aggregate(c1, n_boot=600))
            ctrl["E2"].append(aggregate(c2, n_boot=600))
        for est in ("E1", "E2"):
            r = real[est]
            cmax = max(abs(c["t"]) for c in ctrl[est])
            void = cmax > abs(r["t"]) or cmax > CONTROL_BAR
            verdict = ("VOID (control not null)" if void else
                       "resolves" if r["resolves"] and abs(r["t"]) >= BONFERRONI_T
                       else "not screen-interesting")
            print(f"   {est}: {r['mean']:+.4f}  t={r['t']:+.2f}  "
                  f"CI=[{r['ci_low']:+.4f},{r['ci_high']:+.4f}]  "
                  f"n={r['n']}  resolves={r['resolves']}")
            print(f"       controls max|t|={cmax:.2f} (bar {CONTROL_BAR})  "
                  f"-> {verdict}")
            r["control_max_abs_t"] = cmax
            r["void"] = bool(void)
            r["verdict"] = verdict
        results[arm] = real

    print(f"\n=== CORPUS FALSE-FLAG RATE — {N_FALSE_FLAG} clean shuffles, "
          f"arm N1 under E2 (#101 §5 Amendment 1) ===")
    sub = arms.dropna(subset=["N1", "y"]).copy()
    flagged, ts = 0, []
    for seed in range(5000, 5000 + N_FALSE_FLAG):
        shuffled = sub.copy()
        shuffled["y"] = shuffle_within_date(sub, seed)
        _, c2 = per_date_stats(shuffled, "N1", "y")
        stat = aggregate(c2, n_boot=400)
        ts.append(abs(stat["t"]))
        flagged += abs(stat["t"]) > CONTROL_BAR
    rate = flagged / N_FALSE_FLAG
    print(f"   {flagged}/{N_FALSE_FLAG} = {rate:.0%} per arm  "
          f"-> ALL-clean over {N_CONTROLS} controls voids "
          f"{1 - (1 - rate) ** N_CONTROLS:.0%} of valid work")
    print(f"   null |t|: median={np.median(ts):.2f}  p90={np.percentile(ts, 90):.2f}  "
          f"max={max(ts):.2f}")
    print("   LIMIT: one arm's score geometry, not a per-arm rate (registered).")

    print("\n=== §7 DECISION ===")
    n1, n2 = results["N1"]["E2"], results["N2"]["E2"]
    reps = [results[a]["E2"]["mean"] for a in ("R1", "R2", "R3")]
    beats = (not n1["void"] and abs(n1["t"]) >= BONFERRONI_T
             and n1["mean"] > n2["mean"] and n1["mean"] > max(reps))
    print(f"   N1 E2 spread {n1['mean']:+.4f} (t={n1['t']:+.2f})  vs  "
          f"N2 {n2['mean']:+.4f}  vs  best replication {max(reps):+.4f}")
    print("   OUTCOME 1 — register a confirmatory prereg on an UNSEEN corpus"
          if beats else
          "   OUTCOME 2 — hypothesis NOT supported on this corpus; "
          "no factor change proposed")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"results": results, "false_flag_rate": rate,
             "label": {"mean": float(y.mean()), "sd": float(y.std())},
             "outcome": 1 if beats else 2}, indent=2))
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
