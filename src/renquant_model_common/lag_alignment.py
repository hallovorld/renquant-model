"""Sample-stable lag alignment for score-vs-label evaluation.

WHY THIS EXISTS — the defect it makes unrepresentable
-----------------------------------------------------
2026-07-28/29, a walk-forward study concluded that per-date cross-sectional
IC "rises with label lag" across two independent models, and a follow-up
frozen test returned CLOSE on that basis. An adversarial audit found the
conclusion was mostly a changing SAMPLE, not a changing signal.

The mechanism is a one-liner that reads as obviously correct:

    Y_lagged = Y.shift(-lag)          # WRONG for cross-lag comparison

`shift(-lag)` nulls the newest `lag` rows. Every longer lag therefore drops
the most RECENT dates — and in that study those were precisely the dates
carrying ~0 or negative IC. Recomputed on a date set common to all lags:
the first model's rise lost 60% of its size and the second model's profile
REVERSED (z = -2.09), destroying the "two models agree" corroboration.

A second form of the same defect: comparing an arm built from `scores[L:N]`
against an arm built from `scores[0:N-L)`. The two arms are paired on the
label date but drawn from different score windows, so any time-variation in
skill leaks in as an "effect" — measured at 19-28% of the statistic.

THE RULE this module enforces, at two levels: when statistics are compared
ACROSS lags (or across arms with different lags), (1) every lag must be
evaluated on the SAME set of score DATES — `align_lags` — and (2), because a
cross-sectional panel is rarely balanced (tickers get delisted, IPO, or have
data gaps), the SAME date can still have a different constituent set at
different lags' target dates. `common_panel_members` narrows further, to
the same (date, ticker) PAIRS at every lag. A per-lag maximal sample, at
either level, answers a different question for each lag, and the
differences between those answers are not comparable.

Using a smaller sample is the price of comparability. This module makes that
price explicit and refuses to hide it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import pandas as pd


class LagAlignmentError(ValueError):
    """Raised when a requested comparison cannot be made on a common sample."""


@dataclass(frozen=True)
class LagAlignment:
    """The common evaluation sample for a set of lags.

    Attributes
    ----------
    lags:
        The lags this alignment covers, ascending.
    dates:
        Score dates evaluable at EVERY lag in ``lags`` — the comparison
        sample. Sorted, unique.
    dropped_per_lag:
        Per lag, how many otherwise-evaluable dates were given up to reach
        the common sample. A large asymmetry here is the signature of the
        defect this module exists for, so it is reported rather than hidden.
    """
    lags: tuple[int, ...]
    dates: pd.DatetimeIndex
    dropped_per_lag: dict[int, int]

    @property
    def n_dates(self) -> int:
        return len(self.dates)

    def describe(self) -> str:
        worst = max(self.dropped_per_lag.values()) if self.dropped_per_lag else 0
        return (
            f"common sample: {self.n_dates} score dates evaluable at all "
            f"{len(self.lags)} lags {self.lags}; dropped per lag "
            f"{self.dropped_per_lag} (worst {worst})"
        )


def _as_date_index(values: Iterable) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(list(values))).normalize()
    return idx.drop_duplicates().sort_values()


def lag_evaluable_dates(score_dates: Iterable, label_dates: Iterable,
                        lag: int) -> pd.DatetimeIndex:
    """Score dates whose lag-`lag` label position exists in `label_dates`.

    Positional, not calendar: `lag` counts ROWS of the label date axis (i.e.
    trading days), matching how the labels themselves are built. A score date
    is evaluable at `lag` when the label axis has a row `lag` positions after
    that date.
    """
    if lag < 0:
        raise LagAlignmentError(f"lag must be >= 0, got {lag}")
    sd, ld = _as_date_index(score_dates), _as_date_index(label_dates)
    if len(ld) == 0:
        return pd.DatetimeIndex([])
    pos = ld.get_indexer(sd)                      # -1 where a score date is
    ok = pos >= 0                                 # absent from the label axis
    target = pos + lag
    ok &= target < len(ld)
    return sd[ok]


def align_lags(score_dates: Iterable, label_dates: Iterable,
               lags: Sequence[int], *, min_dates: int = 1) -> LagAlignment:
    """Intersect the evaluable dates of every lag into one comparison sample.

    Raises
    ------
    LagAlignmentError
        If ``lags`` is empty, or the intersection has fewer than
        ``min_dates`` dates. Failing loudly is deliberate: silently
        comparing lag profiles on a near-empty or wildly uneven sample is
        exactly the failure this module exists to prevent.
    """
    lags = tuple(sorted({int(x) for x in lags}))
    if not lags:
        raise LagAlignmentError("at least one lag is required")

    per_lag = {lag: lag_evaluable_dates(score_dates, label_dates, lag)
               for lag in lags}
    common = per_lag[lags[0]]
    for lag in lags[1:]:
        common = common.intersection(per_lag[lag])
    common = common.sort_values()

    if len(common) < min_dates:
        raise LagAlignmentError(
            f"lags {lags} share only {len(common)} evaluable score date(s), "
            f"below min_dates={min_dates}. Per-lag availability: "
            f"{ {lag: len(idx) for lag, idx in per_lag.items()} }. Comparing "
            f"lag statistics across different samples is not meaningful."
        )
    dropped = {lag: len(per_lag[lag]) - len(common) for lag in lags}
    return LagAlignment(lags=lags, dates=common, dropped_per_lag=dropped)


def lagged_label_frame(labels: pd.DataFrame, *, date_col: str, key_col: str,
                       value_col: str, lag: int,
                       restrict_to: pd.DatetimeIndex | None = None
                       ) -> pd.DataFrame:
    """Labels re-indexed so row `date` carries the value observed `lag` rows later.

    The returned frame is the honest counterpart of ``Y.shift(-lag)``: rows
    whose lagged position does not exist are DROPPED rather than filled with
    NaN, and ``restrict_to`` (normally ``align_lags(...).dates``) pins the
    sample so the caller cannot accidentally compare across lags on different
    date sets.
    """
    if lag < 0:
        raise LagAlignmentError(f"lag must be >= 0, got {lag}")
    axis = _as_date_index(labels[date_col])
    src = lag_evaluable_dates(axis, axis, lag)
    if restrict_to is not None:
        src = src.intersection(_as_date_index(restrict_to))
    if len(src) == 0:
        return labels.iloc[0:0][[date_col, key_col, value_col]].copy()

    pos = axis.get_indexer(src)
    target_dates = axis[pos + lag]
    mapping = pd.DataFrame({date_col: src, "_target": target_dates})

    lab = labels[[date_col, key_col, value_col]].copy()
    lab[date_col] = _as_date_index_col(lab[date_col])
    merged = mapping.merge(lab.rename(columns={date_col: "_target"}),
                           on="_target", how="inner")
    return merged[[date_col, key_col, value_col]].reset_index(drop=True)


def _as_date_index_col(col: pd.Series) -> pd.Series:
    return pd.to_datetime(col).dt.normalize()


def common_panel_members(frames: dict[int, pd.DataFrame], *, date_col: str,
                         key_col: str, min_rows: int = 1
                         ) -> dict[int, pd.DataFrame]:
    """Restrict per-lag label frames to (date, key) pairs present at EVERY lag.

    `align_lags` / `lagged_label_frame` guarantee a common set of SCORE
    DATES across lags. They do not guarantee a common set of (date, key)
    PAIRS in an unbalanced panel: a ticker with a valid label at one lag's
    target date can be missing (delisted, not yet listed, a data gap) at
    another lag's target date, for the SAME source date. Comparing a
    per-date cross-sectional statistic computed over different constituent
    sets at "the same" date reintroduces a milder form of the composition
    defect this module exists to prevent — the two dates are the same, but
    the two cross-sections are not.

    Parameters
    ----------
    frames:
        One `lagged_label_frame(...)` output per lag, all built from the
        SAME `align_lags(...).dates` via `restrict_to` (so their date
        columns already agree — this function narrows further, to the
        member level).

    Returns
    -------
    Each input frame filtered to the (date, key) pairs that appear in
    every lag's frame, same columns, reset index.

    Raises
    ------
    LagAlignmentError
        If ``frames`` is empty, or the intersection has fewer than
        ``min_rows`` (date, key) pairs.
    """
    if not frames:
        raise LagAlignmentError("at least one lag's frame is required")

    keysets = {
        lag: set(zip(df[date_col], df[key_col]))
        for lag, df in frames.items()
    }
    common = set.intersection(*keysets.values()) if keysets else set()

    if len(common) < min_rows:
        raise LagAlignmentError(
            f"lags {sorted(frames)} share only {len(common)} common "
            f"(date, {key_col}) pair(s), below min_rows={min_rows}. Per-lag "
            f"pair counts: { {lag: len(ks) for lag, ks in keysets.items()} }. "
            f"An unbalanced panel can leave almost no members common to "
            f"every lag even when the DATES themselves align."
        )

    out: dict[int, pd.DataFrame] = {}
    for lag, df in frames.items():
        mask = [(d, k) in common for d, k in zip(df[date_col], df[key_col])]
        out[lag] = df[mask].reset_index(drop=True)
    return out
