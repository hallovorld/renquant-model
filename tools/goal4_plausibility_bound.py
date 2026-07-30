#!/usr/bin/env python3
"""A SECOND, reproducible construction for GOAL-4 Phase-0's plausibility bound `P`.

This does NOT recompute A1.8's registered `P = +0.01897`. That number's construction
was never recorded and is not reconstructed here. This file computes a different,
fully specified bound (`+0.01355`) and proves the GOAL-4 disposition is the same under
either — an invariance result, not a reproduction of the operative threshold.

Why this file exists
--------------------
`P` is the threshold the Phase-0 power condition consumes: A1.8 registers

    MDG > P  ->  UNRESOLVED (underpowered), NO-GAIN unavailable
    MDG <= P ->  NO-GAIN available

and pins `P = +0.01897`. But A1.8 states the *rule* for `P` (a second member exactly
as strong as the incumbent, at the lowest observed pairwise redundancy) without
stating the *construction* that satisfies both constraints at once, and no code was
committed with it. An independent re-derivation returned +0.01355 rather than +0.01897
(renquant-model#119 review thread), so the registered number is not reproducible from
its own text.

This file does NOT close that defect for A1.8's own +0.01897 -- the equations behind
it were never recorded (see `main`'s "Still open" note) and are not reconstructed
here; guessing at them would be worse than leaving the gap open. What it commits
instead is a second, fully specified construction with its own reproducible number,
plus a proof that GOAL-4's decision does not depend on which of the two bounds is used.

What is registered here is A1.9's OWN construction (P = +0.01355), not a
reconstruction of A1.8's +0.01897 and not a new verdict. The disposition is invariant
across both values (see `main`), so nothing about GOAL-4's outcome moves.

The construction
----------------
Gaussian copula on three variates -- the realised forward return `r`, the benchmark
score `b`, and the hypothetical second member `m`:

  * target Spearman(b, r) = Spearman(m, r) = IC_BENCH  (m is "exactly as strong")
  * target Spearman(b, m) = REDUNDANCY                 (lowest observed pair)

Spearman targets are mapped to Pearson by the exact bivariate-normal identity
`rho = 2 * sin(pi * rho_s / 6)`; the resulting 3x3 matrix is verified positive
definite before use, because a plausible-looking triple of Spearman targets need not
be jointly realisable and silently "fixing" that would change the object measured.

The ensemble is the per-date equal-weight average of the members' cross-sectional
RANKS -- the prereg's own combination rule (§3), not an average of raw scores. `P` is
the mean over draws of

    Spearman(ensemble, r) - Spearman(b, r)

i.e. a GAIN in the same units as the decision rule, not an IC.

Everything is seeded; there is no calibration loop and nothing is tuned against the
realised output.
"""
from __future__ import annotations

import argparse
import math

import numpy as np
from scipy.stats import spearmanr

# --- registered inputs, all cited from executed work -------------------------------
IC_BENCH = 0.07312     # benchmark (production XGB) panel IC        [model#118 benchmark arm]
REDUNDANCY = 0.404     # lowest observed pairwise score corr        [model#118 §5.4, PatchTST<->XGB]
N_NAMES = 115          # panel mean admissible names per date       [tr_matrix_metadata.json]
N_DRAWS = 400
SEED = 20260730

# A1.8's published value, produced by an unstated construction. Retained so this file
# reconciles against it rather than quietly replacing it.
A18_PUBLISHED_P = 0.01897
MDG = 0.07180          # T_crit * block-mean s.e. = 2.3646 * 0.03036  [A1.8]


def spearman_to_pearson(rho_s: float) -> float:
    """Exact bivariate-normal identity. Population quantity, not a small-sample one."""
    return 2.0 * math.sin(math.pi * rho_s / 6.0)


def target_matrix(ic: float = IC_BENCH, red: float = REDUNDANCY) -> np.ndarray:
    """Pearson correlation matrix for (r, b, m), verified jointly realisable."""
    a, c = spearman_to_pearson(ic), spearman_to_pearson(red)
    corr = np.array([[1.0, a, a],
                     [a, 1.0, c],
                     [a, c, 1.0]])
    smallest = float(np.linalg.eigvalsh(corr).min())
    if smallest <= 0.0:
        raise SystemExit(
            f"ABORT: the Spearman targets (IC={ic}, redundancy={red}) are not jointly "
            f"realisable — the implied Pearson matrix has minimum eigenvalue "
            f"{smallest:.6g}. Nudging it to be positive definite would silently change "
            f"which quantity P measures."
        )
    return corr


def ranks(x: np.ndarray) -> np.ndarray:
    """Ordinal ranks. No random tie-breaking: Gaussian draws are a.s. distinct."""
    return np.argsort(np.argsort(x)).astype(float)


def plausibility_bound(n_names: int = N_NAMES, n_draws: int = N_DRAWS,
                       seed: int = SEED, ic: float = IC_BENCH,
                       red: float = REDUNDANCY) -> tuple[float, float]:
    """Return (P, standard error of P)."""
    chol = np.linalg.cholesky(target_matrix(ic, red))
    rng = np.random.default_rng(seed)
    gains = np.empty(n_draws)
    for i in range(n_draws):
        r, b, m = chol @ rng.standard_normal((3, n_names))
        ensemble = (ranks(b) + ranks(m)) / 2.0
        gains[i] = spearmanr(ensemble, r).statistic - spearmanr(b, r).statistic
    return float(gains.mean()), float(gains.std(ddof=1) / math.sqrt(n_draws))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=N_DRAWS)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    p, se = plausibility_bound(n_draws=args.draws, seed=args.seed)

    print(f"construction : Gaussian copula, n={N_NAMES}, draws={args.draws}, seed={args.seed}")
    print(f"targets      : Spearman(b,r)=Spearman(m,r)={IC_BENCH}, Spearman(b,m)={REDUNDANCY}")
    print(f"P            : {p:+.5f}  (s.e. {se:.5f})")
    print(f"A1.8 published: {A18_PUBLISHED_P:+.5f}  (construction unstated)")
    print(f"MDG          : {MDG:+.5f}")
    print()

    # The decision rule, evaluated at BOTH candidate bounds. The registered ceiling
    # stays A1.8's larger value -- NOT because it is better attested (it is not; its
    # construction is unrecorded) but because the smaller one is self-serving: a
    # smaller P makes `MDG > P` easier, and UNRESOLVED is the verdict this document
    # already predicts. Per A1.9.1 the re-run may not be ADJUDICATED against +0.01897
    # while its construction is unrecorded; the fallback is the reproducible bound.
    for label, bound in (("this construction", p), ("A1.8 published", A18_PUBLISHED_P)):
        verdict = "UNRESOLVED (underpowered), NO-GAIN unavailable" if MDG > bound \
            else "NO-GAIN available"
        print(f"  MDG/P = {MDG / bound:5.2f}x at {label:18s} -> {verdict}")

    invariant = (MDG > p) == (MDG > A18_PUBLISHED_P)
    print()
    print(f"disposition invariant across both bounds: {invariant}")
    print("NOTE: invariance is NOT reproducibility of the operative threshold.")
    print("      A1.8's +0.01897 remains unrecorded; per A1.9.1 the re-run may not be")
    print(f"      adjudicated against it, and falls back to this bound ({p:+.5f}).")
    if not invariant:
        print("  ^ the two constructions DISAGREE on the outcome; the prereg's threshold")
        print("    must be resolved before any re-run is adjudicated.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
