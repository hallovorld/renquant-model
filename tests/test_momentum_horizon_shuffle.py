"""`shuffle_within_date` must not leak labels across dates on an interleaved frame.

Codex review on renquant-model#105: `np.lexsort((rng.random(len(f)),
f["_dcode"].values))` sorts the frame INTO date-grouped order, then the
resulting values are reassigned back to ORIGINAL row positions positionally.
That only shuffles correctly when the input already arrives pre-sorted by
date; on an interleaved frame a row can receive another date's label.
Reproducer from the review: dates `[d1,d2,d1,d2]`, labels `[10,20,11,21]` ->
old code returned `[11,10,21,20]`, so `d1` (row 1) received `21` from `d2`.

Because Phase S selection and the holdout placebo cleanliness both depend on
this control being a true within-date permutation, a leak here silently
biases which (arm, horizon) pair gets selected and whether the holdout
result is reported as placebo-clean.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import momentum_horizon_run as T  # noqa: E402


def _frame(dates, labels):
    f = pd.DataFrame({"date": dates, "y": labels})
    f["_dcode"] = pd.factorize(f["date"])[0]
    return f


def test_interleaved_frame_does_not_leak_across_dates():
    f = _frame(["d1", "d2", "d1", "d2"], [10, 20, 11, 21])
    out = T.shuffle_within_date(f, seed=0, ycol="y")
    d1_pool, d2_pool = {10, 11}, {20, 21}
    assert set(out[f["date"].values == "d1"]) <= d1_pool
    assert set(out[f["date"].values == "d2"]) <= d2_pool


def test_shuffle_is_a_permutation_within_each_date_group():
    rng = np.random.default_rng(1)
    n_dates, per_date = 6, 9
    dates = np.repeat([f"d{i}" for i in range(n_dates)], per_date)
    rng.shuffle(dates)  # interleave
    labels = np.arange(len(dates))
    f = _frame(dates, labels)

    out = T.shuffle_within_date(f, seed=7, ycol="y")

    for d in np.unique(dates):
        mask = f["date"].values == d
        assert sorted(out[mask]) == sorted(labels[mask])


def test_different_seeds_produce_different_permutations():
    rng = np.random.default_rng(2)
    n_dates, per_date = 5, 12
    dates = np.repeat([f"d{i}" for i in range(n_dates)], per_date)
    rng.shuffle(dates)
    labels = np.arange(len(dates))
    f = _frame(dates, labels)

    out_a = T.shuffle_within_date(f, seed=0, ycol="y")
    out_b = T.shuffle_within_date(f, seed=1, ycol="y")
    assert not np.array_equal(out_a, out_b)
