"""`fwd_60d_excess` is a per-date z-score, not an excess return.

Written because I was about to preregister a consensus study whose estimand was a
"top-decile spread in excess return", and the column that name points at is standardised
per date: measured 2026-08-01, **2 599 of 2 599 dates** have mean 0 and std 1 (worst
deviations 7.7e-17 and 1.2e-11).

Reading a spread off it gives standard deviations of that date's cross-section — not basis
points. It cannot be summed, annualised, or compared to a cost.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import pytest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import panel_label_contract as C  # noqa: E402


def _panel(tmp_path, frame):
    p = tmp_path / "panel.parquet"
    frame.to_parquet(p)
    return p


def _zscored(dates, n=50):
    rows = []
    rng = __import__("numpy").random.default_rng(0)
    for d in dates:
        v = rng.normal(size=n)
        v = (v - v.mean()) / v.std(ddof=1)
        rows.append(pd.DataFrame({"date": pd.Timestamp(d), "ticker": range(n),
                                  C.LABEL: v}))
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------ the contract --
def test_a_zscored_column_is_recognised(tmp_path):
    p = _panel(tmp_path, _zscored(["2026-01-02", "2026-01-05"]))
    rep = C.survey(p, C.LABEL, None)
    assert rep["is_per_date_zscore"] is True
    assert rep["dates_with_zero_mean"] == rep["n_dates"] == 2


def test_a_RAW_RETURN_column_is_NOT_recognised_as_zscored(tmp_path):
    """The discriminating case: real excess returns have a non-zero cross-sectional mean
    on almost every date."""
    df = pd.DataFrame({"date": [pd.Timestamp("2026-01-02")] * 50,
                       "ticker": range(50),
                       C.LABEL: [0.01 + i * 0.001 for i in range(50)]})
    rep = C.survey(_panel(tmp_path, df), C.LABEL, None)
    assert rep["is_per_date_zscore"] is False
    assert C.main(["--panel", str(_panel(tmp_path, df))]) == 1


def test_ONE_non_conforming_date_breaks_the_contract(tmp_path):
    """The check must be per-date and total — 'mostly z-scored' is not the contract, and a
    single unstandardised date would change what a pooled statistic means."""
    good = _zscored(["2026-01-02"])
    bad = pd.DataFrame({"date": [pd.Timestamp("2026-01-05")] * 50, "ticker": range(50),
                        C.LABEL: [0.05] * 50})
    rep = C.survey(_panel(tmp_path, pd.concat([good, bad])), C.LABEL, None)
    assert rep["is_per_date_zscore"] is False


# ------------------------------------------------------- the past-frontier report --
def test_rows_past_the_frontier_are_counted_not_judged(tmp_path):
    p = _panel(tmp_path, _zscored(["2026-04-28", "2026-04-29", "2026-04-30"]))
    rep = C.survey(p, C.LABEL, "2026-04-28")
    assert rep["dates_past_frontier"] == ["2026-04-29", "2026-04-30"]
    assert rep["rows_past_frontier"] == 100
    # and the verdict is NOT affected by them
    assert rep["is_per_date_zscore"] is True


def test_the_report_states_what_it_does_NOT_establish(tmp_path):
    """A z-score is computable from any values, so its presence says nothing either way
    about whether the 60-day window elapsed. Saying so travels with the number."""
    rep = C.survey(_panel(tmp_path, _zscored(["2026-01-02"])), C.LABEL, None)
    assert "does not show the row is unrealised" in rep["not_established"] or \
           "neither does it show the row is unrealised" in rep["not_established"]
    assert "WRONG" in rep["not_established"]


def test_no_frontier_argument_means_no_frontier_claim(tmp_path):
    rep = C.survey(_panel(tmp_path, _zscored(["2026-01-02"])), C.LABEL, None)
    assert "dates_past_frontier" not in rep


def test_an_unreadable_panel_is_a_usage_error(tmp_path):
    bad = tmp_path / "nope.parquet"
    bad.write_text("not parquet")
    assert C.main(["--panel", str(bad)]) == 2
