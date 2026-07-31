"""GOAL-7 Stage 1 redesign — measure the MDE of each candidate design.

WHAT THIS IS
------------
The redesign document (`doc/design/2026-07-30-goal7-stage1-redesign.md`) lists four
candidate designs and, in the "MDE" column of every one of them, the words
"must be measured".  Review (2026-07-30) made the same demand explicitly:

    "Revise the table and decision question so each candidate includes a
     dependence-valid inferential method and honest MDE and power calculation.
     Do that before B-versus-C is settled or frozen."

This module measures it.  It is a **design calibration**, not a run of the
hypothesis: it never touches the momentum score, the label, or the panel.  It
simulates a per-date statistic series whose *dependence structure* is the one the
real labels impose, and asks each candidate design a single question:

    how large must a constant per-date effect `g` be before this design
    rejects at 5% with 80% probability?

WHAT IS MEASURED VS WHAT IS ASSUMED
-----------------------------------
Measured inputs, from the real programme:

  * `N = 1082` trading days — the uncontaminated window 2016-12-29 -> 2021-04-19
    [VERIFIED — redesign doc §2, itself from the Stage-1 run's date index].
  * `rho1 = 0.94` — the Stage-1 run's own realised lag-1 autocorrelation of the
    per-date statistic at `h = 120`
    [VERIFIED — redesign doc §1, "The run's own lag-1 autocorrelation of 0.94"].

Assumed, and the assumption is load-bearing so it is reported with a sensitivity
band rather than buried:

  * that the per-date statistic decomposes into an overlap-driven common
    component plus i.i.d. cross-sectional noise.  Overlapping `h`-day forward
    labels give the common component the exact autocorrelation `1 - k/h`, so the
    single number `rho1` pins the mix at `h = 120`.
  * for the `h = 20` candidates (C', C") there is **no measured rho1** — the run
    was at `h = 120`.  The overlap/idiosyncratic variance ratio is carried over
    from `h = 120`, which implies `rho1(h=20) = c2 * (1 - 1/20)`.  `--sensitivity`
    re-runs every candidate across a band of `c2` so the reader can see how much
    of each MDE is riding on that carry-over.

UNITS
-----
`g` is in units of `sigma_x`, the per-date statistic's own standard deviation.
That is deliberate.  Converting an MDE to an economically meaningful number needs
`sigma_x` from a *clean* run, and no clean run exists — the only one that produced
it is void.  In `sigma_x` units the comparison the review asked for (B vs C, and
both against A) is exact and needs nothing that has been retracted.

THE ANTI-VACUITY CONTROL
------------------------
A calibrated bar that never rejects would report a wonderful (infinite) MDE and be
useless.  `size` is therefore reported alongside every MDE: the calibrated bar's
realised false-positive rate must land at the nominal 5%, and the *uncalibrated*
Student/normal bar's realised rate is reported next to it to show what the
calibration is buying.  If the uncalibrated rate is not materially above 5%, the
dependence problem this whole redesign exists for would not be visible in the
simulation, and the numbers below would be measuring nothing.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy import stats

# --- realised geometry -------------------------------------------------------
N_DATES = 1082           # 2016-12-29 -> 2021-04-19  [VERIFIED — redesign doc §2]
RHO1_H120 = 0.94         # realised lag-1 autocorr    [VERIFIED — redesign doc §1]
H_PRIMARY = 120
ALPHA = 0.05
POWER_TARGET = 0.80


@dataclass(frozen=True)
class Candidate:
    key: str
    kind: str            # "block" | "hac"
    h: int               # label horizon (days)
    L: int | None        # block length, block designs only
    gap: int | None      # gap between blocks, block designs only
    bandwidth: int | None  # HAC bandwidth, hac only


CANDIDATES = (
    Candidate("A",  "block", 120, 120, 120, None),
    Candidate("B",  "hac",   120, None, None, H_PRIMARY),
    Candidate("C'", "block",  20,  60,  20, None),
    Candidate("C\"", "block", 20,  40,  20, None),
)


def overlap_mix(rho1: float, h: int) -> float:
    """Common-component variance share `c2` implied by a realised lag-1 autocorr.

    With unit total variance, x_t = sqrt(c2)*z_t + sqrt(1-c2)*e_t where z is the
    standardised mean of h consecutive daily shocks (corr(z_t, z_{t+k}) = 1 - k/h
    for k < h) and e is i.i.d.  Then rho1 = c2 * (1 - 1/h).
    """
    denom = 1.0 - 1.0 / h
    if denom <= 0:
        raise ValueError(f"h={h} too small")
    c2 = rho1 / denom
    if not (0.0 <= c2 <= 1.0):
        raise ValueError(
            f"rho1={rho1} at h={h} implies c2={c2:.4f} outside [0,1] — the "
            "overlap alone cannot produce that autocorrelation"
        )
    return c2


def simulate_series(rng: np.random.Generator, reps: int, n: int, h: int,
                    c2: float, g: float) -> np.ndarray:
    """(reps, n) per-date statistic with overlap-induced dependence and mean g."""
    u = rng.standard_normal((reps, n + h - 1))
    cs = np.cumsum(u, axis=1)
    cs = np.concatenate([np.zeros((reps, 1)), cs], axis=1)
    # z_t = mean(u[t : t+h]) * sqrt(h)  -> unit variance
    z = (cs[:, h:h + n] - cs[:, 0:n]) / math.sqrt(h)
    e = rng.standard_normal((reps, n))
    return g + math.sqrt(c2) * z + math.sqrt(1.0 - c2) * e


def crossing_fraction(h: int, L: int, gap: int) -> float:
    """Share of a block's dates whose label window reaches into the NEXT block.

    The published form `min(1, h/L)` is the special case `gap = 0`.  A gap
    absorbs the first `gap` days of reach, so what crosses is `max(0, h - gap)`.
    With `gap >= h` nothing crosses and the blocks are independent — which is the
    whole point of the gap-separated candidates, and why quoting `min(1, h/L)`
    for them would understate them.
    """
    return min(1.0, max(0, h - gap) / L)


# The designs that were actually executed on this programme, with the bar each
# one compared itself to.  `--executed` measures what those bars really cost.
EXECUTED = (
    ("GOAL-7 Stage 1 as executed", 120, 60, 0),
    ("momentum total-return as executed", 120, 120, 0),
    ("GOAL-4 Phase-0 ensemble screen", 60, 60, 0),
    ("C row rejected at review (h=20 in L=60)", 20, 60, 0),
)


def block_starts(n: int, L: int, gap: int) -> list[int]:
    """Block i occupies [i*(L+gap), i*(L+gap)+L).  Count is n // (L+gap).

    This matches the arithmetic already published in the redesign table so the
    block counts here and there cannot drift apart.
    """
    period = L + gap
    nb = n // period
    return [i * period for i in range(nb)]


def block_t(x: np.ndarray, L: int, gap: int) -> np.ndarray:
    starts = block_starts(x.shape[1], L, gap)
    if len(starts) < 2:
        raise ValueError(f"L={L} gap={gap} leaves {len(starts)} block(s) — no t")
    means = np.stack([x[:, s:s + L].mean(axis=1) for s in starts], axis=1)
    nb = means.shape[1]
    sd = means.std(axis=1, ddof=1)
    sd = np.where(sd == 0.0, np.nan, sd)
    return means.mean(axis=1) / (sd / math.sqrt(nb))


def hac_t(x: np.ndarray, bandwidth: int) -> np.ndarray:
    """Newey-West with the Bartlett kernel, bandwidth fixed by registration."""
    n = x.shape[1]
    d = x - x.mean(axis=1, keepdims=True)
    var = (d * d).sum(axis=1) / n
    for k in range(1, bandwidth + 1):
        if k >= n:
            break
        w = 1.0 - k / (bandwidth + 1.0)
        gamma_k = (d[:, k:] * d[:, :-k]).sum(axis=1) / n
        var += 2.0 * w * gamma_k
    # A Bartlett-kernel NW estimate is guaranteed non-negative in exact
    # arithmetic; clamp only against floating-point underruns and record it.
    var = np.maximum(var, 1e-300)
    se = np.sqrt(var / n)
    return x.mean(axis=1) / se


def stat_for(cand: Candidate, x: np.ndarray) -> np.ndarray:
    if cand.kind == "block":
        return block_t(x, cand.L, cand.gap)
    return hac_t(x, cand.bandwidth)


def student_bar(cand: Candidate, n: int) -> float | None:
    """The bar a design would use if it (wrongly) trusted an asymptotic df."""
    if cand.kind == "block":
        nb = len(block_starts(n, cand.L, cand.gap))
        return float(stats.t.ppf(1 - ALPHA / 2, nb - 1))
    return 1.959963985  # what a naive HAC t would be compared against


def calibrate(rng, cand, c2, n, reps):
    x = simulate_series(rng, reps, n, cand.h, c2, 0.0)
    t = np.abs(stat_for(cand, x))
    t = t[np.isfinite(t)]
    crit_perm = float(np.percentile(t, 100 * (1 - ALPHA)))
    naive = student_bar(cand, n)
    size_naive = float((t > naive).mean())
    # The registered rule: the permutation bar, and for block designs the
    # Student leg as a floor so a lucky-small null draw cannot lower the bar.
    crit = crit_perm if cand.kind == "hac" else max(crit_perm, naive)
    size_cal = float((t > crit).mean())
    return crit, crit_perm, naive, size_cal, size_naive


def power_at(rng, cand, c2, n, reps, crit, g):
    x = simulate_series(rng, reps, n, cand.h, c2, g)
    t = np.abs(stat_for(cand, x))
    t = t[np.isfinite(t)]
    return float((t > crit).mean())


def mde(rng, cand, c2, n, reps, crit, grid):
    """Smallest g on the grid reaching POWER_TARGET, linearly interpolated."""
    prev_g, prev_p = 0.0, ALPHA
    for g in grid:
        p = power_at(rng, cand, c2, n, reps, crit, g)
        if p >= POWER_TARGET:
            if p == prev_p:
                return g, p
            frac = (POWER_TARGET - prev_p) / (p - prev_p)
            return prev_g + frac * (g - prev_g), p
        prev_g, prev_p = g, p
    return None, prev_p


def run(n=N_DATES, rho1=RHO1_H120, reps_null=4000, reps_power=2000, seed=20260730,
        c2_override=None):
    rng = np.random.default_rng(seed)
    c2_base = overlap_mix(rho1, H_PRIMARY) if c2_override is None else c2_override
    grid = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
            0.55, 0.60, 0.70, 0.80, 0.90, 1.00, 1.15, 1.30, 1.50, 1.75,
            2.00, 2.50, 3.00]
    out = {"n_dates": n, "rho1_h120": rho1, "c2": c2_base,
           "reps_null": reps_null, "reps_power": reps_power, "seed": seed,
           "candidates": []}
    for cand in CANDIDATES:
        crit, crit_perm, naive, size_cal, size_naive = calibrate(
            rng, cand, c2_base, n, reps_null)
        m, p = mde(rng, cand, c2_base, n, reps_power, crit, grid)
        row = asdict(cand)
        row.update({
            "blocks": (len(block_starts(n, cand.L, cand.gap))
                       if cand.kind == "block" else None),
            "crossing": (round(crossing_fraction(cand.h, cand.L, cand.gap), 4)
                         if cand.kind == "block" else None),
            "rho1_implied": round(c2_base * (1 - 1 / cand.h), 4),
            "crit": round(crit, 4),
            "crit_permutation": round(crit_perm, 4),
            "bar_uncalibrated": round(naive, 4),
            "size_calibrated": size_cal,
            "size_uncalibrated": size_naive,
            "mde_sigma_x": (None if m is None else round(m, 4)),
            "power_at_grid_end": p,
        })
        out["candidates"].append(row)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps-null", type=int, default=4000)
    ap.add_argument("--reps-power", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260730)
    ap.add_argument("--executed", action="store_true",
                    help="measure the realised false-positive rate of the "
                         "designs this programme actually ran, at their own bars")
    ap.add_argument("--sensitivity", action="store_true",
                    help="re-run across a band of c2 to expose how much of the "
                         "h=20 MDEs rides on the carry-over assumption")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)

    R = run(reps_null=a.reps_null, reps_power=a.reps_power, seed=a.seed)
    print(f"\nGOAL-7 design MDE — N={R['n_dates']} rho1(h=120)={R['rho1_h120']} "
          f"c2={R['c2']:.4f} reps_null={R['reps_null']} reps_power={R['reps_power']}")
    print(f"{'cand':>4} {'h':>4} {'blocks':>7} {'rho1':>6} {'bar_naive':>10} "
          f"{'bar_cal':>8} {'size_naive':>11} {'size_cal':>9} {'MDE(sig_x)':>11}")
    for c in R["candidates"]:
        m = c["mde_sigma_x"]
        m_txt = ">3.000" if m is None else f"{m:.3f}"
        print(f"{c['key']:>4} {c['h']:>4} {str(c['blocks'] or '-'):>7} "
              f"{c['rho1_implied']:>6.3f} {c['bar_uncalibrated']:>10.4f} "
              f"{c['crit']:>8.4f} {c['size_uncalibrated']:>11.3f} "
              f"{c['size_calibrated']:>9.3f} {m_txt:>11}")

    if a.executed:
        rng = np.random.default_rng(a.seed + 11)
        c2 = overlap_mix(RHO1_H120, H_PRIMARY)
        R["executed"] = []
        print("\nrealised size of the designs this programme ACTUALLY ran "
              f"(nominal {ALPHA:.2f})")
        print(f"{'study':<40}{'h':>4}{'L':>5}{'gap':>5}{'cross':>7}"
              f"{'blk':>5}{'bar':>8}{'SIZE':>8}")
        for name, h, L, gap in EXECUTED + tuple(
                (f"repaired: {c.key} (gap-separated)", c.h, c.L, c.gap)
                for c in CANDIDATES if c.kind == "block"):
            x = simulate_series(rng, a.reps_null, N_DATES, h, c2, 0.0)
            t = np.abs(block_t(x, L, gap))
            nb = len(block_starts(N_DATES, L, gap))
            bar = float(stats.t.ppf(1 - ALPHA / 2, nb - 1))
            size = float((t > bar).mean())
            R["executed"].append({"study": name, "h": h, "L": L, "gap": gap,
                                  "crossing": crossing_fraction(h, L, gap),
                                  "blocks": nb, "bar": round(bar, 4),
                                  "size": size})
            print(f"{name:<40}{h:>4}{L:>5}{gap:>5}"
                  f"{crossing_fraction(h, L, gap):>7.3f}{nb:>5}"
                  f"{bar:>8.4f}{size:>8.4f}")

    if a.sensitivity:
        R["sensitivity"] = []
        for c2 in (0.80, 0.9479, 0.99):
            s = run(reps_null=max(1500, a.reps_null // 2),
                    reps_power=max(1000, a.reps_power // 2),
                    seed=a.seed + 1, c2_override=c2)
            R["sensitivity"].append(
                {"c2": c2, "mde": {r["key"]: r["mde_sigma_x"]
                                   for r in s["candidates"]}})
        print("\nsensitivity — MDE(sigma_x) across the overlap-share band")
        for s in R["sensitivity"]:
            print(f"  c2={s['c2']:.4f}  " +
                  "  ".join(f"{k}={v}" for k, v in s["mde"].items()))

    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(R, fh, indent=2)
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
