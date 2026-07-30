#!/usr/bin/env python3
"""Run FROZEN screen 2: doc/research/2026-07-29-momentum-family-screen.md.

The momentum family, re-measured on the TRADED estimand (top-decile spread) as
well as on full cross-section IC. Registered because the operator leans towards
a momentum model; the bar is RAISED, not lowered, to pay for asking a second
question of the same corpus (18 joint tests => |t| >= 2.99).

    python3 tools/momentum_family_screen.py \\
        --panel /Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet

Estimand, estimator, control protocol and shuffle are IMPORTED from screen 1's
runner rather than reimplemented, so the two screens are comparable by
construction and a fix to one cannot silently diverge from the other.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "vol_conditioned_trend_screen",
    Path(__file__).resolve().parent / "vol_conditioned_trend_screen.py")
s1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(s1)

# Joint family with screen 1: 18 tests. Supersedes screen 1's 2.81 UPWARD.
JOINT_BONFERRONI_T = 2.99


def build_arms(panel: pd.DataFrame) -> pd.DataFrame:
    """§3. ret(60) alone is NOT here: it is screen 1's R1 on this same corpus."""
    d = panel["date"]
    out = pd.DataFrame({"date": d, "ticker": panel["ticker"], "y": panel[s1.LABEL]})
    mom60 = s1.ret(panel["ROC60"])
    mom20 = s1.ret(panel["ROC20"])
    mom5 = s1.ret(panel["ROC5"])
    std60 = panel["STD60"]

    out["M1"] = mom20                                   # near-replication
    out["M2"] = mom60 - mom5                            # 12-1 style
    out["M3"] = mom60 / std60.where(std60 > 0)          # vol-scaled
    med = std60.groupby(d).transform("median")
    gated = pd.Series(0.0, index=panel.index, dtype="float64")
    hi = std60 > med
    gated[hi] = mom60[hi]
    gated[std60.isna() | mom60.isna()] = np.nan
    out["M4"] = gated                                   # vol-gated
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", required=True, type=Path)
    ap.add_argument("--allow-input-mismatch", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    print("INPUT")
    s1.check_pin(args.panel, args.allow_input_mismatch)
    panel = pd.read_parquet(args.panel, columns=s1.NEEDED)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = (panel.dropna(subset=[s1.LABEL])
                  .sort_values("date", kind="stable").reset_index(drop=True))

    y = panel[s1.LABEL]
    print(f"\n0. LABEL UNITS ({s1.LABEL}) — measured, not assumed")
    print(f"   rows={len(panel)}  dates={panel.date.nunique()}  "
          f"tickers={panel.ticker.nunique()}")
    print(f"   mean={y.mean():+.4f}  sd={y.std():.4f}  -> statistic is in SD")

    arms = build_arms(panel)
    arms["_dcode"] = pd.factorize(arms["date"])[0]
    labels = {"M1": "ret(20) — NEAR-REPLICATION, a positive here is a PLUMBING red flag",
              "M2": "ret(60) - ret(5) — 12-1 style",
              "M3": "ret(60) / STD60 — vol-scaled",
              "M4": "ret(60) gated to above-median STD60 — vol-gated"}
    results: dict[str, dict] = {}

    for arm in ("M1", "M2", "M3", "M4"):
        sub = arms.dropna(subset=[arm, "y"]).copy()
        print(f"\n=== ARM {arm}: {labels[arm]}  (rows={len(sub)}) ===")
        e1, e2 = s1.per_date_stats(sub, arm, "y")
        real = {"E1": s1.aggregate(e1), "E2": s1.aggregate(e2)}
        ctrl: dict[str, list[float]] = {"E1": [], "E2": []}
        for seed in range(s1.N_CONTROLS):
            shuffled = sub.copy()
            shuffled["y"] = s1.shuffle_within_date(sub, seed)
            c1, c2 = s1.per_date_stats(shuffled, arm, "y")
            ctrl["E1"].append(abs(s1.aggregate(c1, n_boot=600)["t"]))
            ctrl["E2"].append(abs(s1.aggregate(c2, n_boot=600)["t"]))
        for est in ("E1", "E2"):
            r, cmax = real[est], max(ctrl[est])
            void = cmax > abs(r["t"]) or cmax > s1.CONTROL_BAR
            verdict = ("VOID (control not null)" if void else
                       "resolves" if r["resolves"] and abs(r["t"]) >= JOINT_BONFERRONI_T
                       else "not screen-interesting")
            print(f"   {est}: {r['mean']:+.4f}  t={r['t']:+.2f}  "
                  f"CI=[{r['ci_low']:+.4f},{r['ci_high']:+.4f}]  n={r['n']}  "
                  f"resolves={r['resolves']}")
            print(f"       controls max|t|={cmax:.2f}  -> {verdict}  "
                  f"(joint bar |t|>={JOINT_BONFERRONI_T})")
            r.update(control_max_abs_t=cmax, void=bool(void), verdict=verdict)
        results[arm] = real

    print("\n=== §6 DECISION ===")
    m1 = results["M1"]["E2"]["mean"]
    if not results["M1"]["E2"]["void"] and abs(results["M1"]["E2"]["t"]) >= JOINT_BONFERRONI_T:
        print("   !! M1 (near-replication of a KILLED factor) cleared the bar. "
              "Per §6 this is a PLUMBING red flag, NOT a rehabilitation of "
              "20-day momentum. Do not read the other arms until it is explained.")
    cands = [(a, results[a]["E2"]) for a in ("M2", "M3", "M4")]
    winners = [(a, r) for a, r in cands
               if not r["void"] and abs(r["t"]) >= JOINT_BONFERRONI_T
               and r["mean"] > m1]
    for arm, r in cands:
        print(f"   {arm}: E2 {r['mean']:+.4f} t={r['t']:+.2f} "
              f"{'VOID' if r['void'] else r['verdict']}")
    print(f"   replication reference M1 E2 = {m1:+.4f}")
    if winners:
        print("   OUTCOME 1 — " + ", ".join(a for a, _ in winners)
              + " clear the joint bar; the ONLY licensed action is a "
                "confirmatory prereg on an UNSEEN corpus. No factor added, no "
                "config change, no capital action.")
    else:
        print("   OUTCOME 2 — momentum NOT supported on this corpus on either "
              "estimand. The operator's stated preference does not survive "
              "measurement here.")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"results": results, "joint_bar": JOINT_BONFERRONI_T,
             "label": {"mean": float(y.mean()), "sd": float(y.std())},
             "outcome": 1 if winners else 2}, indent=2))
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
