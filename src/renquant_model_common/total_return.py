"""Total-return close construction — the ONE importable home.

MOVED VERBATIM (byte-identical function body) from
``tools/build_total_return_series.py`` on 2026-08-02. WHY THE MOVE: that file
is a build SCRIPT whose top level runs the entire July total-return study —
raw-corpus pin guard (``verify_or_abort``), live watchlist read, per-ticker
build loop. Importing it to reach this one pure function therefore EXECUTED
the study's guards against the LIVE corpus; the GOAL-7 momentum runner's
single --execute crashed exactly there on 2026-08-02 (the July pin no longer
matches the refreshed raw layer — correct for THAT study's rebuilds,
irrelevant to a runner whose inputs are the frozen, digest-verified durable
store). A pure function must be importable without side effects; the script
keeps its guards for its own builds and now imports the function from here.

The construction itself was validated in the total-return study (V1-V5
checks; ex-div gap collapse −66.58bp → −4.84bp) and is NOT modified by a
character here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def total_return_close(close: pd.Series, dividend: pd.Series) -> pd.Series:
    """TR[t] = P[t] / prod_{s>t} (1 + D[s]/P[s]).  See module docstring."""
    p = close.to_numpy(dtype="float64")
    d = dividend.reindex(close.index).fillna(0.0).to_numpy(dtype="float64")

    if np.any(d < 0):
        raise ValueError("negative dividend")
    bad = (d > 0) & ~(np.isfinite(p) & (p > 0))
    if bad.any():
        raise ValueError(f"dividend on a bar with unusable close ({bad.sum()} bars)")

    g = np.ones_like(p)
    ev = d > 0
    g[ev] = 1.0 + d[ev] / p[ev]
    if np.any(g <= 0) or not np.all(np.isfinite(g)):
        raise ValueError("non-positive / non-finite gross-up factor")

    # R[t] = prod of g over s > t ; R[last] = 1 (empty product)
    R = np.ones_like(p)
    if len(p) > 1:
        R[:-1] = np.cumprod(g[::-1])[::-1][1:]
    return pd.Series(p / R, index=close.index, name="tr_close")
