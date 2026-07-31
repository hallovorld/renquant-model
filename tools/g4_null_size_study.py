#!/usr/bin/env python3
"""Realised size of the Phase-0 block-t procedure, on GOAL-4's own per-date series.

WHY. model#136 lists four requirements for a validated dependence-preserving null.
Requirement (3) is an EMPIRICAL CALIBRATION TARGET: the procedure must be shown to hit
its nominal size at the realised geometry. This measures it.

THE ANSWER IS THAT IT IS NOT IDENTIFIED YET, and that is the finding. A block bootstrap
needs its own block length, and the realised size moves from 0.0508 to 0.0803 across
defensible choices of it -- on the same data, same statistic, same geometry. So
requirement (3) cannot be met before requirement (1) fixes the mechanism.

CONSTRUCTION. No-effect condition: the real series minus its mean, so the true mean is
exactly 0 while the empirical dependence is retained. Draws: circular block bootstrap.
Statistic: block means with `gap` dropped between blocks, one-sample t, compared to
t(0.975, n_blocks-1) -- exactly what the Phase-0 prereg specifies.

HARNESS CONTROL. The same procedure run on an i.i.d. Normal series must hit ~0.05, or a
"miscalibrated" reading would be the harness, not the data.
"""

from __future__ import annotations

import argparse
import csv
import json

import numpy as np
from scipy import stats

H = 60  #: label horizon of the Phase-0 screen (fwd_60d)


def circular_block_bootstrap(x: np.ndarray, block: int, rng) -> np.ndarray:
    n = len(x)
    k = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=k)
    return np.concatenate(
        [np.take(x, (s + np.arange(block)) % n) for s in starts])[:n]


def block_t(x: np.ndarray, length: int, gap: int):
    """Block means with `gap` observations DROPPED between blocks, then a t.

    `gap = 0` is the Phase-0 geometry (`n_blocks = floor(N/60)`, `L = h = 60`), whose
    crossing fraction is `min(1, h/L) = 1.00` -- the maximum label overlap.
    """
    means, i = [], 0
    while i + length <= len(x):
        means.append(x[i:i + length].mean())
        i += length + gap
    m = np.array(means)
    if len(m) < 2:
        return None, len(m)
    return float(m.mean() / (m.std(ddof=1) / np.sqrt(len(m)))), len(m)


def size(series: np.ndarray, length: int, gap: int, boot_block: int, draws: int,
         rng, iid_sd: float | None = None) -> tuple[float, int]:
    rej = n_blocks = 0
    crit_cache: dict[int, float] = {}
    for _ in range(draws):
        x = (rng.normal(0.0, iid_sd, len(series)) if iid_sd is not None
             else circular_block_bootstrap(series, boot_block, rng))
        t, nb = block_t(x, length, gap)
        if t is None:
            continue
        n_blocks = nb
        crit = crit_cache.setdefault(nb, float(stats.t.ppf(0.975, nb - 1)))
        rej += abs(t) > crit
    return rej / draws, n_blocks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", required=True)
    ap.add_argument("--column", default="g")
    ap.add_argument("--draws", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260731)
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    rng = np.random.default_rng(a.seed)
    g = np.array([float(r[a.column]) for r in csv.DictReader(open(a.series))])
    centred = g - g.mean()

    geometries = [(60, 0), (60, H), (30, H), (20, H)]
    # 35 is the REGISTERED value (model#144: first zero crossing of the sample ACF).
    # The other five are model#143's sensitivity band, reported beside it as the prereg
    # requires -- the registered value never replaces the band.
    boot_blocks = [20, 35, 40, 60, 90, 120]

    out = {
        "n": len(g),
        "mean": float(g.mean()),
        "sd": float(g.std(ddof=1)),
        "acf": {f"rho_{k}": float(np.corrcoef(g[:-k], g[k:])[0, 1])
                for k in (1, 2, 5, 10, 20, 60)},
        "h": H, "draws": a.draws, "seed": a.seed,
        "harness_control_iid": {}, "size_by_geometry_and_boot_block": {},
    }
    for length, gap in geometries[:1] + geometries[-1:]:
        s, nb = size(centred, length, gap, 0, a.draws, rng, iid_sd=float(g.std(ddof=1)))
        out["harness_control_iid"][f"L{length}_gap{gap}"] = {"size": s, "n_blocks": nb}
    for bb in boot_blocks:
        for length, gap in geometries:
            s, nb = size(centred, length, gap, bb, a.draws, rng)
            out["size_by_geometry_and_boot_block"][f"boot{bb}_L{length}_gap{gap}"] = {
                "size": s, "n_blocks": nb,
                "crossing": min(1.0, max(0.0, (H - gap)) / length)}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
    print(json.dumps({k: v for k, v in out.items()
                      if k != "size_by_geometry_and_boot_block"},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
