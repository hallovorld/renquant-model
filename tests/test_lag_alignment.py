"""Pins the 2026-07-28/29 defect: cross-lag comparison on a drifting sample.

The study these tests exist for concluded "IC rises with label lag" across
two models and a follow-up frozen test returned CLOSE on that basis. Both
were artifacts of `Y.shift(-lag)` nulling the newest rows, so each longer lag
silently evaluated a different — older — set of dates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from renquant_model_common.lag_alignment import (
    LagAlignmentError,
    align_lags,
    lag_evaluable_dates,
    lagged_label_frame,
)

AXIS = pd.bdate_range("2024-01-01", periods=200)


def test_shift_drops_the_newest_dates_and_align_makes_it_visible():
    # The defect in one assertion: at lag 60 the last 60 dates become
    # unevaluable, and they are the NEWEST ones — not a random subset.
    ev0 = lag_evaluable_dates(AXIS, AXIS, 0)
    ev60 = lag_evaluable_dates(AXIS, AXIS, 60)
    assert len(ev0) == 200 and len(ev60) == 140
    lost = ev0.difference(ev60)
    assert lost.min() > ev60.max()          # everything lost is more recent
    assert lost.max() == AXIS.max()


def test_align_lags_yields_one_sample_for_every_lag():
    al = align_lags(AXIS, AXIS, [0, 60, 100, 160])
    assert al.n_dates == 40                 # 200 - 160, the binding lag
    # every lag gives up whatever it must to reach the common sample
    assert al.dropped_per_lag == {0: 160, 60: 100, 100: 60, 160: 0}
    assert "common sample: 40 score dates" in al.describe()


def test_common_sample_is_identical_across_lags():
    al = align_lags(AXIS, AXIS, [0, 60, 100])
    for lag in al.lags:
        ev = lag_evaluable_dates(AXIS, AXIS, lag)
        assert al.dates.difference(ev).empty, (
            f"lag {lag} cannot evaluate the whole common sample"
        )


def test_the_lag0_statistic_itself_moves_between_full_and_common_samples():
    """The precise mechanism that inflated the real finding.

    Longer lags never see the newest dates. If those dates carry weaker
    skill, the SHORT-lag statistic is dragged down by dates the LONG-lag
    statistic was never charged for — so the two are not comparable and the
    difference reads as a rising profile. Measured in the real study: lag-0
    IC rose from +0.028 to +0.043 (PatchTST) and +0.069 to +0.100 (prod XGB)
    once the sample was held common, which is where 60% of the apparent rise
    went, and where the second model's profile reversed outright.
    """
    rng = np.random.default_rng(0)
    tickers = [f"T{i:02d}" for i in range(30)]
    rows = []
    for i, d in enumerate(AXIS):
        strength = 0.9 if i < 120 else 0.0      # the RECENT era carries nothing
        s = rng.normal(size=len(tickers))
        y = strength * s + rng.normal(size=len(tickers))
        rows.extend((d, t, sv, yv) for t, sv, yv in zip(tickers, s, y))
    df = pd.DataFrame(rows, columns=["date", "ticker", "score", "label"])

    def ic_lag0(dates=None):
        d = df if dates is None else df[df["date"].isin(dates)]
        per = d.groupby("date").apply(
            lambda g: g["score"].corr(g["label"], method="spearman"),
            include_groups=False)
        return per.mean()

    al = align_lags(AXIS, AXIS, [0, 100])
    assert al.n_dates == 100                    # the newest 100 dates are gone
    assert al.dates.max() < AXIS.max()          # ...and they are the NEWEST

    full, common = ic_lag0(), ic_lag0(al.dates)
    # The same statistic, on the same data, differs by more than most of the
    # effects this project chases — purely from which dates are in scope.
    assert common - full > 0.15, (full, common)

def test_lagged_label_frame_carries_the_later_value_to_the_earlier_row():
    df = pd.DataFrame({
        "date": list(AXIS[:5]) * 2,
        "ticker": ["A"] * 5 + ["B"] * 5,
        "label": [1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0],
    })
    out = lagged_label_frame(df, date_col="date", key_col="ticker",
                            value_col="label", lag=2)
    a = out[out.ticker == "A"].sort_values("date")
    # row for date[0] must carry the value observed at date[2]
    assert a.iloc[0]["label"] == 3.0
    assert len(a) == 3                       # last two rows have no lag-2 target


def test_rows_without_a_lagged_target_are_dropped_not_nan_filled():
    df = pd.DataFrame({"date": list(AXIS[:4]), "ticker": ["A"] * 4,
                       "label": [1.0, 2.0, 3.0, 4.0]})
    out = lagged_label_frame(df, date_col="date", key_col="ticker",
                            value_col="label", lag=3)
    assert len(out) == 1 and not out["label"].isna().any()


def test_empty_intersection_raises_rather_than_returning_garbage():
    with pytest.raises(LagAlignmentError, match="share only"):
        align_lags(AXIS[:50], AXIS[:50], [0, 60])


def test_min_dates_guard_is_enforced():
    with pytest.raises(LagAlignmentError, match="min_dates=100"):
        align_lags(AXIS, AXIS, [0, 160], min_dates=100)


def test_negative_lag_is_rejected():
    with pytest.raises(LagAlignmentError, match="lag must be >= 0"):
        lag_evaluable_dates(AXIS, AXIS, -1)


def test_score_dates_absent_from_the_label_axis_are_excluded():
    scores = AXIS.append(pd.DatetimeIndex(["2030-01-01"]))
    ev = lag_evaluable_dates(scores, AXIS, 0)
    assert pd.Timestamp("2030-01-01") not in ev and len(ev) == 200


# ---------------------------------------------------------------------------
# (date, key) alignment — the unbalanced-panel gap. Date-only alignment lets
# per-date MEMBERSHIP drift with the lag, which is the same defect one level
# down and bites hardest in exactly the survivorship-correct panels we want.
# ---------------------------------------------------------------------------

from renquant_model_common.lag_alignment import (  # noqa: E402
    align_lag_pairs,
    lag_evaluable_pairs,
)


def _unbalanced(n_dates=10, exit_at=6):
    rows = []
    for i, d in enumerate(AXIS[:n_dates]):
        keys = ["A", "B"] if i < exit_at else ["A"]      # B delists at exit_at
        rows.extend((d, k) for k in keys)
    return pd.DataFrame(rows, columns=["date", "ticker"])


def test_a_delisted_key_is_dropped_where_its_lagged_row_is_missing():
    df = _unbalanced()
    ev = lag_evaluable_pairs(df, date_col="date", key_col="ticker", lag=4)
    b = ev[ev.ticker == "B"]
    # B trades on dates 0..5; at lag 4 only dates 0..1 have a B row at t+4
    assert len(b) == 2 and b["date"].max() == AXIS[1]
    assert (ev[ev.ticker == "A"]).shape[0] == 6           # A survives throughout


def test_date_only_alignment_would_keep_pairs_the_pair_alignment_drops():
    df = _unbalanced()
    date_only = align_lags(df["date"].unique(), df["date"].unique(), [0, 4])
    pairs = align_lag_pairs(df, date_col="date", key_col="ticker", lags=[0, 4])
    # the date axis says dates 0..5 are fine for both lags...
    assert len(date_only.dates) == 6
    # ...but B is only evaluable on 2 of them, so 4 (date, ticker) pairs that a
    # date-only rule would have compared across lags are correctly excluded
    kept_b = (pairs.pairs.ticker == "B").sum()
    assert kept_b == 2
    assert pairs.n_pairs == 8                              # 6 A + 2 B


def test_pair_alignment_is_identical_across_lags():
    df = _unbalanced()
    al = align_lag_pairs(df, date_col="date", key_col="ticker", lags=[0, 2, 4])
    for lag in al.lags:
        ev = lag_evaluable_pairs(df, date_col="date", key_col="ticker", lag=lag)
        merged = al.pairs.merge(ev, on=["date", "ticker"], how="left",
                                indicator=True)
        assert (merged["_merge"] == "both").all(), (
            f"lag {lag} cannot evaluate the whole common pair sample"
        )


def test_restrict_joins_a_frame_down_to_the_common_sample():
    df = _unbalanced()
    al = align_lag_pairs(df, date_col="date", key_col="ticker", lags=[0, 4])
    scored = df.assign(score=1.0)
    out = al.restrict(scored)
    assert len(out) == al.n_pairs and set(out.columns) >= {"date", "ticker", "score"}


def test_balanced_panel_agrees_with_the_date_only_special_case():
    rows = [(d, k) for d in AXIS[:10] for k in ("A", "B")]
    df = pd.DataFrame(rows, columns=["date", "ticker"])
    pairs = align_lag_pairs(df, date_col="date", key_col="ticker", lags=[0, 4])
    dates = align_lags(df["date"].unique(), df["date"].unique(), [0, 4])
    assert list(pairs.dates) == list(dates.dates)
    assert pairs.n_pairs == len(dates.dates) * 2


def test_empty_pair_intersection_raises():
    df = _unbalanced(n_dates=6, exit_at=3)
    with pytest.raises(LagAlignmentError, match="min_pairs=99"):
        align_lag_pairs(df, date_col="date", key_col="ticker", lags=[0, 2],
                        min_pairs=99)
