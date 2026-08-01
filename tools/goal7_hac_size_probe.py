#!/usr/bin/env python3
"""Empirical SIZE of the frozen HAC test under H0, on synthetic dependence. (GOAL-7)

The residual-momentum design (PR #161 §3) requires, BEFORE any verdict is read:

    size probe — seeded synthetic AR(1) series at rho1 in {0.90, 0.95, 0.975} with n
    equal to the observed eligible-date count; empirical size must be <= 1.5x nominal,
    else the study reports UNRESOLVED-METHOD.

This is that probe, runnable ahead of the freeze because it touches NO real data and NO
alternative hypothesis: every series is generated under H0 (zero mean) with a fixed seed.
Validating the instrument's size is method work, not outcome work.

Two generator families, because they answer different questions:

  * ``ma_overlap`` — a rolling h-day mean of iid innovations, i.e. exactly the MA(h-1)
    dependence that h-day label OVERLAP induces by construction. This is the H0 the
    design's L = h-1 Bartlett bandwidth is built for.
  * ``ar1`` — geometric-decay dependence at rho1 in {0.90, 0.95, 0.975}. This is the
    shape the committed per-date IC series actually showed on OTHER arms
    (model#153: rho1 0.82-0.975), where correlation persists far beyond lag h-1. If the
    momentum IC series turns out AR-like rather than overlap-like, L = h-1 truncates
    real dependence and the size below quantifies exactly what that costs.

Estimator under test: ``renquant_common.metrics.hac_se.hac_t_stat`` — measured equal to
the frozen SE_HAC formula to six decimals (model#159). Bandwidths L in {19, 59} so the
report shows whether a wider Bartlett window rescues the AR cases.

Exit codes: 0 ran, 2 usage/import error.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/Users/renhao/git/github/RenQuant/.subrepo_runtime/repos/renquant-common/src")
try:
    from renquant_common.metrics.hac_se import hac_t_stat
except ImportError as exc:  # pragma: no cover
    print(f"size-probe: cannot import the estimator under test: {exc}", file=sys.stderr)
    raise SystemExit(2)


def gen_ar1(rng: np.random.Generator, rho: float, n: int) -> np.ndarray:
    e = rng.standard_normal(n + 300)
    x = np.empty_like(e)
    x[0] = e[0]
    for t in range(1, len(e)):
        x[t] = rho * x[t - 1] + e[t]
    return x[300:]                     # burn-in discarded; mean 0 under H0 by construction


def gen_ma_overlap(rng: np.random.Generator, h: int, n: int) -> np.ndarray:
    e = rng.standard_normal(n + h)
    return np.convolve(e, np.ones(h) / h, mode="valid")[:n]


def size_cell(gen, n_rep: int, lag: int, bar: float, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    ts = np.empty(n_rep)
    for i in range(n_rep):
        ts[i] = hac_t_stat(gen(rng), lag=lag)["t_stat"]
    size = float(np.mean(np.abs(ts) >= bar))
    return {"size": size,
            "mc_se": float(np.sqrt(size * (1 - size) / n_rep)) if 0 < size < 1 else None,
            "t_sd": float(np.std(ts)),      # 1.0 when calibrated
            # The empirically calibrated two-sided 5% critical value: the bar that WOULD
            # give size 0.05 against this generator. Reproducible (fixed seed), so a
            # prereg may freeze it as the decision bar for the matching H0 shape.
            "crit95_abs_t": float(np.quantile(np.abs(ts), 0.95))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=2150, help="eligible-date count (AC4 measurement)")
    ap.add_argument("--reps", type=int, default=2500)
    ap.add_argument("--bar", type=float, default=1.96, help="two-sided nominal 0.05")
    ap.add_argument("--seed", type=int, default=20260801)
    ap.add_argument("--json-out", type=Path, default=None)
    a = ap.parse_args(argv)

    gens = {
        "iid_control":      lambda rng: rng.standard_normal(a.n),
        "ma_overlap_h20":   lambda rng: gen_ma_overlap(rng, 20, a.n),
        "ar1_rho0.90":      lambda rng: gen_ar1(rng, 0.90, a.n),
        "ar1_rho0.95":      lambda rng: gen_ar1(rng, 0.95, a.n),
        "ar1_rho0.975":     lambda rng: gen_ar1(rng, 0.975, a.n),
    }
    out = {"n": a.n, "reps": a.reps, "bar": a.bar, "nominal": 0.05, "seed": a.seed,
           "estimator": "renquant_common.metrics.hac_se.hac_t_stat", "cells": {}}
    print(f"H0 size probe: n={a.n}  reps={a.reps}  bar=|t|>={a.bar}  nominal=0.05")
    print(f"{'generator':<18}  per-L: empirical size at |t|>=1.96 / calibrated 5% bar t*")
    for name, g in gens.items():
        row = {}
        for lag in (19, 39, 59, 119):
            row[f"L{lag}"] = size_cell(g, a.reps, lag, a.bar, a.seed)
        out["cells"][name] = row
        line = f"{name:<18}"
        for lag in (19, 39, 59, 119):
            c = row[f"L{lag}"]
            line += f"  L{lag}: {c['size']:.3f}/t*{c['crit95_abs_t']:.2f}"
        print(line)
    print("\n  PASS rule from the design: size <= 1.5 x nominal = 0.075.")
    print("  t_sd is the H0 sd of the t statistic: 1.00 when calibrated; >1 means the")
    print("  SE understates the dependence and every downstream t is inflated by ~t_sd.")
    if a.json_out:
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print(f"  wrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
