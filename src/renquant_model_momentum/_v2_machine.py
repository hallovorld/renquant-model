"""The sealed v2 gap-block machine's pure pieces, as a PACKAGED MIRROR. (GOAL-7 slice 3)

Every function body and the ``FROZEN_V2`` dict below are BYTE-VERBATIM copies
from the sealed v2 runner ``tools/goal7_momentum_v2_run.py`` (model#192;
``sample_acf`` from ``tools/goal7_momentum_inference.py``, the same estimator
the v2 runner reuses for its §2.5 rho_1 valve). Nothing is modified here — not
a docstring, not a comment, not a constant.

WHY A MIRROR RATHER THAN AN IMPORT OR AN INVERSION (the same split as
``_frozen_params_v0``, review round 1 on model#196):

* The recurring evaluator (design §2, doc/design/2026-08-02-momentum-pipeline-
  architecture.md) must ship in the wheel; ``tools/`` never enters the built
  distribution (``[tool.setuptools.packages.find] where = ["src"]``), so an
  import from ``tools/`` would reproduce the exact reviewed defect that made
  ``params_v0()`` raise ``FileNotFoundError`` at first installed use.
* Inverting the dependency (editing the sealed v2 runner to import from here)
  would change the bytes a published, sealed result was produced by — the v2
  study is SPENT and its runner is its provenance. The precedent is the
  ``total_return_close`` move for a LIVE build script versus the
  ``_frozen_params_v0`` mirror for a SEALED runner; the v2 runner is sealed.

The cost of a mirror is that two copies can diverge. That cost is paid by
``tests/test_momentum_evaluator.py``: the mirror-fidelity tests hold every
function here equal to the sealed runner's own source (``inspect.getsource``
byte equality) and the parity golden holds the OUTPUTS equal on the same
input. If either ever fails, this mirror is what changed and the sealed
runner is right.

``FROZEN_V2`` is carried WHOLE for mirror fidelity, including the decision-map
and placebo constants (``mde_ceiling``, ``h1_mean_min``, ``placebo_*``) that
the recurring evaluator deliberately does NOT use — design §2: no gate, no
verdict wording; the evaluator publishes raw gate outputs only.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import t as _student_t

__all__ = ["FROZEN_V2", "block_stats", "one_sample_t", "partition_blocks",
           "run_controls", "sample_acf", "t_bar"]

# ---- frozen by the v2 prereg; restated verbatim, never re-chosen ----------------
FROZEN_V2 = {
    "h": 20,                     # block width = label horizon (prereg §2.1)
    "gap": 20,                   # discarded gap between blocks = h (prereg §2.1)
    "min_usable_per_block": 10,  # §2.2: thinner blocks dropped and counted
    "min_surviving_blocks": 40,  # §2.2: below -> UNRESOLVED-POWER, controls NOT run
    "rho1_ceiling": 0.25,        # §2.5: |rho_1(block means)| at/above -> METHOD
    "quantile": 0.975,           # §2.4: two-sided Student-t bar, df-aware
    "n_reps": 1000,              # §3.2: control replications
    "base_seed": 20260801,       # §3: placebo seed AND control base seed
    "placebo_perms": 5,          # §3: per-date within-date label permutations
    "placebo_ceiling": 0.01,     # §3: H1 requires placebo mean |IC| below this
    "positive_mu": 0.04,         # §3.3: = the §4 H1 threshold
    "positive_rate_min": 0.80,   # §3.3: positive-control clear-rate floor
    "negative_mu": 0.0,          # §3.4
    "negative_rate_max": 0.10,   # §3.4: negative-control clear-rate ceiling
    "mde_ceiling": 0.06,         # §4
    "h1_mean_min": 0.04,         # §4
}


# ---- §2 gap-block machine (pure functions, no I/O) — verbatim from the v2 runner -
def partition_blocks(T: int, h: int, gap: int) -> list[tuple[int, int]]:
    """§2.1: block k covers positions [k*(h+gap), k*(h+gap)+h) of the realized
    scored-date sequence; n_blocks = floor((T-h)/(h+gap)) + 1 for T >= h, else 0.
    At v1's realized T=2378 this is 59. Thin dates never enter the scored
    sequence, so they change T only — the partition never shifts within it."""
    if T < h:
        return []
    n = (T - h) // (h + gap) + 1
    return [(k * (h + gap), k * (h + gap) + h) for k in range(n)]


def block_stats(values: np.ndarray, h: int, gap: int, min_usable: int) -> dict:
    """§2.2: per-block mean over the block's usable (finite) dates; blocks with
    fewer than ``min_usable`` usable dates are dropped AND counted."""
    v = np.asarray(values, float)
    blocks = partition_blocks(len(v), h, gap)
    means: list[float] = []
    usable_counts: list[int] = []
    dropped = 0
    for lo, hi in blocks:
        w = v[lo:hi]
        finite = w[np.isfinite(w)]
        usable_counts.append(int(len(finite)))
        if len(finite) < min_usable:
            dropped += 1
            continue
        means.append(float(finite.mean()))
    return {"n_blocks_formed": len(blocks), "n_dropped": dropped,
            "n_surviving": len(means), "usable_counts": usable_counts,
            "means": np.asarray(means, float)}


def _block_summary(st: dict) -> dict:
    return {"n_blocks_formed": st["n_blocks_formed"], "n_dropped": st["n_dropped"],
            "n_surviving": st["n_surviving"], "usable_counts": st["usable_counts"],
            "block_means": [float(x) for x in st["means"]]}


def one_sample_t(x: np.ndarray) -> float:
    """§2.3 / §3.2: mean / (sd_ddof1 / sqrt(n)) — the ONE t formula, shared by the
    real series and the controls. Degenerate spreads are refused UPSTREAM by the
    §3.1(c') valve before this is ever evaluated on the real series."""
    x = np.asarray(x, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def t_bar(df: int) -> float:
    """§2.4: two-sided t_{0.975, df} read from Student-t (df-aware; no borrowed
    1.96). At df=58 this is 2.0017, the prereg's derived value."""
    return float(_student_t.ppf(FROZEN_V2["quantile"], df))


def run_controls(mu: float, sd: float, n: int, bar: float, *,
                 base_seed: int, n_reps: int) -> dict:
    """§3.2 FROZEN generator, exactly: rep r uses numpy.random.default_rng(
    base_seed + r) (PCG64), draws exactly n iid Normal(mu, sd) via
    rng.normal(mu, sd, n), computes the §2.3 one-sample t and applies the SAME
    comparison H1 uses (t >= bar). Rates AND per-rep clear/fail are published."""
    clears: list[bool] = []
    for r in range(n_reps):
        rng = np.random.default_rng(base_seed + r)
        draws = rng.normal(mu, sd, n)
        clears.append(bool(one_sample_t(draws) >= bar))
    n_clear = sum(clears)
    return {"mu": float(mu), "sd": float(sd), "n": int(n), "bar": float(bar),
            "base_seed": int(base_seed), "n_reps": int(n_reps),
            "n_clear": int(n_clear), "n_fail": int(n_reps - n_clear),
            "rate": n_clear / n_reps,
            "per_rep_clear": "".join("1" if c else "0" for c in clears)}


# ---- the §2.5 rho_1 estimator — verbatim from tools/goal7_momentum_inference.py --
def sample_acf(v: np.ndarray, max_lag: int) -> np.ndarray:
    v = np.asarray(v, float)
    if not np.all(np.isfinite(v)):
        return np.full(max_lag, np.nan)
    d = v - v.mean()
    g0 = float(d @ d)
    if g0 <= 0:
        return np.full(max_lag, np.nan)
    return np.array([float(d[:-k] @ d[k:]) / g0 for k in range(1, max_lag + 1)])
