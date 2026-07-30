#!/usr/bin/env python3
"""Pure computational core for the FROZEN prereg
doc/research/2026-07-30-patchtst-closure-prereg-v2.md ("model#113").

This module implements ONLY what §1/§3/§3.5/§4/§6 specify. It does not choose
any threshold or estimator beyond what is written there. Every function that
touches the block/lag/permutation mechanics is unit-tested in
tests/test_patchtst_closure_v2_selfchecks.py per the §0.3 self-checks.

No file I/O happens in this module (data loading + orchestration live in
patchtst_closure_v2_run.py); this keeps the estimator testable in isolation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as sstats

MIN_NAMES = 20  # [ASSUMED — not specified by the frozen text; inherited from
                 # model#90's harness convention ("Stage-0 harness"), used only
                 # as a per-date cross-sectional-IC validity floor. Neither
                 # corpus used by this study ever drops below it (PT: constant
                 # 142 names/date; XGB: min 109/date) so this floor never
                 # actually removes an admissible date — see the run log.


class UnsortedDateFrameError(ValueError):
    """Raised by admissible_dates when the score-date axis is not sorted
    ascending. §0.3 self-check #1: the within-date pairing must be proven to
    REJECT an unsorted frame, not merely to work correctly on a sorted one."""


# --------------------------------------------------------------- §1 admissible
def admissible_dates(score_dates: pd.DatetimeIndex, label_axis: pd.DatetimeIndex,
                      L: int, h: int = 60) -> np.ndarray:
    """§1 admissible dates: score_t exists, score_{t-L} exists, r_{t->t+h} is
    COMPLETE (forward window ends on or before label_axis's last date).

    `score_dates` and `label_axis` must both be sorted ascending; `score_dates`
    must be a subset of `label_axis` at identical positions offset (i.e. the
    positional lag on the score axis is the same trading-day lag as on the
    label axis) — this is asserted, not assumed; see
    `assert_score_axis_positionally_contiguous`.

    Returns the admissible dates as a sorted, deduplicated DatetimeIndex-like
    ndarray of datetime64.
    """
    if not pd.DatetimeIndex(score_dates).is_monotonic_increasing:
        raise UnsortedDateFrameError(
            "admissible_dates requires score_dates sorted ascending; got an "
            "unsorted frame. This assertion exists per §0.3 self-check #1.")
    if not pd.DatetimeIndex(label_axis).is_monotonic_increasing:
        raise UnsortedDateFrameError(
            "admissible_dates requires label_axis sorted ascending; got an "
            "unsorted frame. This assertion exists per §0.3 self-check #1.")
    sd = pd.DatetimeIndex(score_dates)
    la = pd.DatetimeIndex(label_axis)
    n = len(sd)
    lab_pos = la.get_indexer(sd)
    if (lab_pos < 0).any():
        raise ValueError("score_dates contains a date absent from label_axis")
    idx = np.arange(n)
    ok = (idx - L) >= 0                    # (b) score_{t-L} exists on score axis
    ok &= (lab_pos + h) < len(la)          # (c) forward window complete
    return sd.values[ok]


def assert_score_axis_positionally_contiguous(score_dates: pd.DatetimeIndex,
                                                label_axis: pd.DatetimeIndex) -> None:
    """Assert that positions on `score_dates` line up 1:1 with consecutive
    positions on `label_axis` (no internal gaps). This is what makes "L
    positions back on the score axis" equal "L trading days back" — required
    for §1's L to mean what it says. Raises AssertionError if violated."""
    sd, la = pd.DatetimeIndex(score_dates), pd.DatetimeIndex(label_axis)
    pos = la.get_indexer(sd)
    assert (pos >= 0).all(), "a score date is absent from the label axis"
    assert np.all(np.diff(pos) == 1), (
        "score axis is not positionally contiguous in the label axis; L would "
        "not mean 'L trading days' under this data")


# --------------------------------------------------------------- per-date IC
def spearman_ic(x: np.ndarray, y: np.ndarray, min_names: int = MIN_NAMES):
    """Cross-sectional Spearman IC for one date. NaNs pairwise-dropped.
    Returns (ic, n) with ic=NaN if n < min_names."""
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < min_names:
        return float("nan"), n
    xr = sstats.rankdata(x[ok])
    yr = sstats.rankdata(y[ok])
    if np.std(xr) == 0 or np.std(yr) == 0:
        return float("nan"), n
    ic = float(np.corrcoef(xr, yr)[0, 1])
    return ic, n


# --------------------------------------------------------------- §3 estimator
@dataclass(frozen=True)
class BlockStat:
    mean: float
    se: float
    t: float
    n_blocks: int
    block_len: int
    n_eval: int
    dropped_remainder: int


def block_partition_indices(n_eval: int, block_len: int) -> list[tuple[int, int]]:
    """§3 step 3: non-overlapping contiguous blocks of `block_len`.
    n_blocks = floor(n_eval / block_len); remainder DROPPED (not kept).
    Returns a list of (start, end) index pairs into a 0-indexed, date-sorted
    admissible-date array, each of exactly `block_len` positions."""
    n_blocks = n_eval // block_len
    return [(i * block_len, (i + 1) * block_len) for i in range(n_blocks)]


def assert_no_undersized_block(blocks: list[tuple[int, int]], block_len: int) -> None:
    """§0.3 self-check #2. Raises if any block is not exactly `block_len`
    wide — the remainder must have been dropped before this point, never
    included as a short trailing block."""
    for (s, e) in blocks:
        assert (e - s) == block_len, (
            f"undersized block ({s},{e}) width={e - s} != block_len={block_len}; "
            f"§3 requires the remainder to be DROPPED, never equal-weighted")


def block_t(d_series: np.ndarray, block_len: int = 60,
            agg: str = "mean") -> BlockStat:
    """§3: one-sample two-sided t over block means (or, for §6.2, block
    medians) of `d_series`, which MUST already be in ascending date order.
    Remainder dropped, never kept (§3, and the model#110 ERRATUM it cites)."""
    d = np.asarray(d_series, dtype=float)
    n_eval = len(d)
    blocks = block_partition_indices(n_eval, block_len)
    assert_no_undersized_block(blocks, block_len)
    dropped = n_eval - len(blocks) * block_len
    if agg == "mean":
        bstat = np.array([np.mean(d[s:e]) for (s, e) in blocks])
    elif agg == "median":
        bstat = np.array([np.median(d[s:e]) for (s, e) in blocks])
    else:
        raise ValueError(agg)
    n_blocks = len(bstat)
    m = float(np.mean(bstat)) if n_blocks else float("nan")
    if n_blocks < 2:
        return BlockStat(mean=m, se=float("nan"), t=float("nan"),
                          n_blocks=n_blocks, block_len=block_len,
                          n_eval=n_eval, dropped_remainder=dropped)
    se = float(np.std(bstat, ddof=1) / math.sqrt(n_blocks))
    t = (m / se) if se > 0 else float("nan")
    return BlockStat(mean=m, se=se, t=t, n_blocks=n_blocks, block_len=block_len,
                      n_eval=n_eval, dropped_remainder=dropped)


# --------------------------------------------------------------- §3.5 T_crit
@dataclass(frozen=True)
class CritValue:
    t_crit: float
    student_t_leg: float
    p95_null_leg: float
    bound_by: str
    n_blocks: int
    n_perm: int
    null_abs_t: list  # the |t| draws, for reporting mean/p95/max


def critical_value(n_blocks: int, null_abs_t_draws: list[float]) -> CritValue:
    student_leg = float(sstats.t.ppf(0.975, n_blocks - 1)) if n_blocks >= 2 else float("nan")
    p95_leg = float(np.percentile(null_abs_t_draws, 95)) if null_abs_t_draws else float("nan")
    t_crit = max(student_leg, p95_leg)
    bound_by = "student_t" if student_leg >= p95_leg else "p95_null"
    return CritValue(t_crit=t_crit, student_t_leg=student_leg, p95_null_leg=p95_leg,
                      bound_by=bound_by, n_blocks=n_blocks,
                      n_perm=len(null_abs_t_draws), null_abs_t=list(null_abs_t_draws))


def null_quantile_of(value: float, null_abs_t_draws: list[float]) -> float:
    """What fraction of the null |t| draws are <= |value|? (i.e. the
    treatment's |t| expressed as a quantile of the null distribution.)"""
    if not null_abs_t_draws:
        return float("nan")
    arr = np.asarray(null_abs_t_draws, dtype=float)
    return float(np.mean(arr <= abs(value)))
