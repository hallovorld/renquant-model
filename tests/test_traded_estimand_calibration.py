"""The two arms of the registered estimand must be exact complements.

The registered statistic is mean(top-k) - mean(the REMAINING n-k). An earlier
revision of the verifier took those as `nlargest(k)` and `nsmallest(n-k)`,
which select independently: when `raw` ties across the k boundary the same row
can land in BOTH arms, so the bottom arm is not the complement of the top and
the number computed is not the registered estimand.

These pin the complement property directly, including the degenerate all-ties
case where the old form provably double-counted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import traded_estimand_calibration as T  # noqa: E402


def _frame(raw, y, date="2026-01-02", tickers=None):
    n = len(raw)
    return pd.DataFrame({
        "date": [date] * n,
        "ticker": tickers if tickers is not None else [f"T{i:03d}" for i in range(n)],
        "raw": raw,
        T.LABEL: y,
    })


def test_all_ties_does_not_double_count_a_row():
    """The case the old nlargest/nsmallest form got wrong.

    With every `raw` identical, `nlargest(1)` and `nsmallest(n-1)` both include
    row 0, so it was counted in both arms. Position splitting cannot do that.
    """
    n = 40
    y = list(np.arange(float(n)))
    out = T.spread_per_date(_frame([1.0] * n, y), T.LABEL)
    assert len(out) == 1
    k = max(1, int(round(n * T.TOP_FRACTION)))
    # top = first k by (raw desc, ticker asc) = T000..T00{k-1}; rest = remainder
    expected = np.mean(y[:k]) - np.mean(y[k:])
    assert out.iloc[0] == pytest.approx(expected)


def test_arms_are_complements_under_boundary_ties():
    """Ties spanning exactly the k boundary must still partition cleanly."""
    n = 30
    k = max(1, int(round(n * T.TOP_FRACTION)))
    # a block of identical scores straddling the boundary
    raw = [9.0] * (k + 4) + [1.0] * (n - k - 4)
    y = list(np.arange(float(n)))
    out = T.spread_per_date(_frame(raw, y), T.LABEL)
    expected = np.mean(y[:k]) - np.mean(y[k:])
    assert out.iloc[0] == pytest.approx(expected)


def test_tie_policy_is_row_order_independent():
    """Same rows, shuffled input order -> identical statistic.

    A merely-stable sort would give order-dependent answers here; the
    registered policy breaks ties on `ticker`, so it does not.
    """
    n = 40
    raw = [1.0] * n                      # fully degenerate: policy decides everything
    y = list(np.arange(float(n)))
    tick = [f"T{i:03d}" for i in range(n)]
    a = T.spread_per_date(_frame(raw, y, tickers=tick), T.LABEL)

    idx = np.random.default_rng(0).permutation(n)
    b = T.spread_per_date(
        _frame([raw[i] for i in idx], [y[i] for i in idx],
               tickers=[tick[i] for i in idx]), T.LABEL)
    assert a.iloc[0] == pytest.approx(b.iloc[0])


def test_a_clean_signal_gives_a_positive_spread():
    """Sanity: monotone score/label agreement is a positive top-minus-rest."""
    n = 50
    y = list(np.arange(float(n)))        # highest raw <-> highest y
    out = T.spread_per_date(_frame(list(np.arange(float(n))), y), T.LABEL)
    assert out.iloc[0] > 0


def test_dates_below_the_minimum_are_dropped_not_guessed():
    out = T.spread_per_date(_frame([1.0] * (T.MIN_NAMES - 1),
                                   list(range(T.MIN_NAMES - 1))), T.LABEL)
    assert out.empty
