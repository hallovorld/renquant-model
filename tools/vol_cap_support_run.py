#!/usr/bin/env python3
"""Run the FROZEN prereg doc/research/2026-07-30-vol-cap-support-mismatch-prereg.md.

Is the deployed model's edge CONCENTRATED in the names the pre-scoring 60% vol
gate removes? A one-way test: it can CLOSE the lane cheaply, or justify an
out-of-sample escalation. It can never license touching the live path (§3
confound, §8).

    python3 tools/vol_cap_support_run.py \\
        --panel <umbrella>/data/alpha158_291_fundamental_dataset.parquet \\
        --artifact <umbrella>/backtesting/renquant_104/artifacts/prod/panel-ltr.alpha158_fund.json \\
        --ohlcv-dir <umbrella>/data/ohlcv

Panel pinned by sha256, ABORTS on mismatch. All inputs READ-ONLY.

The per-date statistics, the shuffle and the aggregator are byte-identical to the
two factor screens' implementations, as §6 requires, so nothing in the answer can
be attributed to an estimator choice.
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402

PANEL_SHA256 = "7defdacf97f8eb057a9a56a2eb7bc6eb48bc33adb9fd00a2a6c36943be87daa5"
LABEL = "fwd_60d_excess"
BLOCK, N_BOOT, TOP_FRACTION, MIN_NAMES, N_CONTROLS = 60, 2000, 0.10, 20, 5
CONTROL_BAR = 2.0
JOINT_BONFERRONI_T = 3.06          # 24 joint tests; supersedes 2.99 UPWARD
VOL_CAP_PCT = 60.0
# §4 reconstruction gate, registered before the run
GATE_MEAN_TOL, GATE_SD_LO, GATE_SD_HI, GATE_MIN_FRAC = 0.15, 0.8, 1.25, 0.90


def check_pin(path: Path, allow: bool) -> None:
    d = hashlib.sha256(path.read_bytes()).hexdigest()
    if d == PANEL_SHA256:
        print(f"  panel sha256={d[:16]}… PIN OK"); return
    msg = f"panel sha256={d} != pinned {PANEL_SHA256}"
    if not allow:
        raise SystemExit(f"ABORT: {msg}\n  The frozen design registered the pinned panel.")
    print(f"  WARNING: {msg}")


def per_date_stats(frame: pd.DataFrame, score: str, ycol: str):
    """(E1 spearman IC, E2 top-decile spread) per date. Identical to the screens."""
    d = frame["date"]
    n = d.groupby(d).transform("size")
    keep = n >= MIN_NAMES
    frame, d = frame[keep], d[keep]
    if frame.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
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
    rank_desc = frame[score].groupby(d).rank(ascending=False, method="first")
    size = frame[score].groupby(d).transform("size")
    k = np.maximum(1, np.round(size * TOP_FRACTION))
    top = rank_desc <= k
    t = frame[ycol].groupby([d, top]).mean().unstack()
    if True not in t.columns or False not in t.columns:
        return e1, pd.Series(dtype=float)
    return e1, (t[True] - t[False]).dropna()


def shuffle_within_date(frame: pd.DataFrame, seed: int) -> np.ndarray:
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


def annualised_vol(ohlcv_dir: Path, tickers) -> pd.DataFrame:
    """Exactly the live gate's quantity: annualised stdev of daily close-to-close
    returns over 60 trading days, in percent."""
    frames, missing = [], []
    for t in tickers:
        p = ohlcv_dir / t / "1d.parquet"
        if not p.exists():
            missing.append(t); continue
        try:
            df = pd.read_parquet(p)
        except Exception:  # noqa: BLE001
            missing.append(t); continue
        idx = (df.index if isinstance(df.index, pd.DatetimeIndex)
               else pd.to_datetime(df.get("date"), errors="coerce"))
        s = pd.Series(df["close"].values, index=pd.DatetimeIndex(idx)).sort_index().dropna()
        v = s.pct_change().rolling(60, min_periods=60).std(ddof=1) * np.sqrt(252) * 100.0
        frames.append(pd.DataFrame({"date": v.index, "ticker": t, "ann_vol": v.values}))
    print(f"  ann_vol built for {len(frames)} tickers; {len(missing)} without OHLCV"
          + (f" (e.g. {missing[:6]})" if missing else ""))
    return pd.concat(frames, ignore_index=True).dropna() if frames else pd.DataFrame()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", required=True, type=Path)
    ap.add_argument("--artifact", required=True, type=Path)
    ap.add_argument("--ohlcv-dir", required=True, type=Path)
    ap.add_argument("--allow-input-mismatch", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    print("INPUTS"); check_pin(args.panel, args.allow_input_mismatch)
    art = json.loads(args.artifact.read_text())
    print(f"  artifact sha256={hashlib.sha256(args.artifact.read_bytes()).hexdigest()[:16]}… "
          f"trained_date={art.get('trained_date')} label={art.get('label_col')}")
    fc = art["feature_cols"]
    mu = np.asarray(art["feature_means"], dtype=float)
    sd = np.asarray(art["feature_stds"], dtype=float)

    panel = pd.read_parquet(args.panel, columns=["date", "ticker", LABEL] + fc)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.dropna(subset=[LABEL]).sort_values("date", kind="stable").reset_index(drop=True)
    print(f"\n0. PANEL  rows={len(panel)} dates={panel.date.nunique()} "
          f"tickers={panel.ticker.nunique()}  label mean={panel[LABEL].mean():+.4f} "
          f"sd={panel[LABEL].std():.4f}")

    X = panel[fc].to_numpy(dtype=np.float32)
    Z = (X - mu) / np.where(sd == 0, 1.0, sd)

    print("\n1. §4 RECONSTRUCTION GATE (runs BEFORE any arm)")
    cm, cs = np.nanmean(Z, axis=0), np.nanstd(Z, axis=0, ddof=1)
    ok = (np.abs(cm) <= GATE_MEAN_TOL) & (cs >= GATE_SD_LO) & (cs <= GATE_SD_HI)
    frac = float(ok.mean())
    print(f"   columns within |mean|<={GATE_MEAN_TOL}, sd in [{GATE_SD_LO},{GATE_SD_HI}]: "
          f"{ok.sum()}/{len(fc)} = {frac:.1%}  (registered floor {GATE_MIN_FRAC:.0%})")
    worst = np.argsort(-np.abs(cm))[:5]
    print("   worst-mean columns: " + ", ".join(
        f"{fc[i]}(mean={cm[i]:+.2f},sd={cs[i]:.2f})" for i in worst))
    if frac < GATE_MIN_FRAC:
        print("\nABORT per §7.1: the stored moments do not standardise this panel, so "
              "every downstream number would be computed on a mis-standardised input. "
              "No arm is reported.")
        return 2
    print("   GATE PASSED")

    import xgboost as xgb
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        raw = art["booster_raw_json"]
        fh.write(raw if isinstance(raw, str) else json.dumps(raw)); tmp = fh.name
    b = xgb.Booster(); b.load_model(tmp); os.unlink(tmp)
    b.feature_names = [f"f{i}" for i in range(len(fc))]
    panel["score"] = b.predict(xgb.DMatrix(Z, feature_names=b.feature_names))
    print(f"\n2. SCORES  mean={panel.score.mean():+.4f} sd={panel.score.std():.4f} "
          f"min={panel.score.min():+.4f} max={panel.score.max():+.4f}")

    print("\n3. ANNUALISED VOL (the live gate's own quantity)")
    vol = annualised_vol(args.ohlcv_dir, sorted(panel.ticker.unique()))
    merged = panel.merge(vol, on=["date", "ticker"], how="inner")
    print(f"   rows with vol: {len(merged)}/{len(panel)} = {len(merged)/len(panel):.1%}; "
          f"tickers={merged.ticker.nunique()}  "
          f"SAMPLE RESTRICTION: arms are computed on these rows only")
    merged = merged.rename(columns={LABEL: "y"}).sort_values("date", kind="stable").reset_index(drop=True)
    merged["_dcode"] = pd.factorize(merged["date"])[0]
    drop_frac = float((merged.ann_vol > VOL_CAP_PCT).mean())
    print(f"   rows the {VOL_CAP_PCT:.0f}% gate would DROP: {drop_frac:.1%}")

    arms = {"V_full": merged,
            "V_kept": merged[merged.ann_vol <= VOL_CAP_PCT],
            "V_drop": merged[merged.ann_vol > VOL_CAP_PCT]}
    results = {}
    for name, sub in arms.items():
        sub = sub.copy(); sub["_dcode"] = pd.factorize(sub["date"])[0]
        print(f"\n=== ARM {name}  rows={len(sub)}  tickers={sub.ticker.nunique()} ===")
        e1, e2 = per_date_stats(sub, "score", "y")
        real = {"E1": aggregate(e1), "E2": aggregate(e2)}
        ctrl = {"E1": [], "E2": []}
        for seed in range(N_CONTROLS):
            sh = sub.copy(); sh["y"] = shuffle_within_date(sub, seed)
            c1, c2 = per_date_stats(sh, "score", "y")
            ctrl["E1"].append(abs(aggregate(c1, n_boot=600)["t"]))
            ctrl["E2"].append(abs(aggregate(c2, n_boot=600)["t"]))
        for est in ("E1", "E2"):
            r, cmax = real[est], max(ctrl[est])
            void = cmax > abs(r["t"]) or cmax > CONTROL_BAR
            why = ("VOID-because-null" if void and abs(r["t"]) < CONTROL_BAR
                   else "VOID-because-dirty" if void else
                   "resolves" if r["resolves"] and abs(r["t"]) >= JOINT_BONFERRONI_T
                   else "not screen-interesting")
            print(f"   {est}: {r['mean']:+.4f} t={r['t']:+.2f} "
                  f"CI=[{r['ci_low']:+.4f},{r['ci_high']:+.4f}] n={r['n']} "
                  f"resolves={r['resolves']}")
            print(f"       own|t|={abs(r['t']):.2f} vs controls max|t|={cmax:.2f} -> {why} "
                  f"(joint bar {JOINT_BONFERRONI_T})")
            r.update(control_max_abs_t=cmax, void=bool(void), verdict=why)
        results[name] = real

    print("\n=== §7 DECISION ===")
    kd, kk = results["V_drop"]["E2"], results["V_kept"]["E2"]
    print(f"   V_drop E2 {kd['mean']:+.4f} (t={kd['t']:+.2f})  vs  "
          f"V_kept E2 {kk['mean']:+.4f} (t={kk['t']:+.2f})  |  "
          f"V_full {results['V_full']['E2']['mean']:+.4f}")
    escalate = (kd["mean"] > kk["mean"] and not kd["void"]
                and abs(kd["t"]) >= JOINT_BONFERRONI_T)
    if escalate:
        print("   ESCALATE — the gate removes names where the model's in-sample edge is "
              "concentrated. ONLY licensed next step: an out-of-sample design for the "
              "dropped names. NOT a config change, NOT moving the vol cap, NOT a retrain.")
    else:
        print("   CLOSE THE LANE — the pre-scoring vol cap is NOT removing the model's "
              "edge. The support mismatch is cosmetic; no retrain, no gate move, no "
              "further work on this lane is justified.")
    print("   REMINDER §3: in-sample. Only the kept-vs-dropped CONTRAST is readable, "
          "and even it cannot separate real edge concentration from differential overfit.")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"results": results, "gate_frac": frac, "drop_frac": drop_frac,
             "joint_bar": JOINT_BONFERRONI_T,
             "outcome": "ESCALATE" if escalate else "CLOSE"}, indent=2))
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
