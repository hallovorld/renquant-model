"""The within-date shuffle, and the PROOF THAT ITS SELF-CHECK CAN FAIL.

Defect 1 of the aborted 2026-07-30 momentum run was a placebo that leaked
labels across dates: the shuffle sorted the frame into (_dcode, random) order
and then wrote that sorted sequence back into ORIGINAL row positions
positionally, which is a within-date permutation only if rows already arrive
grouped by date. The frame was ticker-major, so they did not.

The lesson that matters is not "fix the shuffle" -- it is that a self-check
which only ever exercises the CORRECT implementation passes on the broken one
too. So this module tests three separate things:

  1. the shipped shuffle is a true within-date permutation on INTERLEAVED input;
  2. the known-broken implementation LEAKS on that same input;
  3. `selfcheck_shuffle()` -- the guard the runner executes before it will touch
     any data -- REJECTS the broken implementation. That is the test of the
     test, and it is the one the previous run did not have.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import momentum_total_return_run as T  # noqa: E402


def _frame(dates, labels):
    f = pd.DataFrame({"date": list(dates), "y": [float(x) for x in labels]})
    f["_dcode"] = pd.factorize(f["date"])[0]
    return f


# ----------------------------------------------------- 1. the shipped shuffle --
def test_interleaved_frame_does_not_leak_across_dates():
    f = _frame(["d1", "d2", "d1", "d2"], [10, 20, 11, 21])
    for seed in range(8):
        out = T.shuffle_within_date(f, seed, "y")
        assert set(out[f.date.values == "d1"]) <= {10.0, 11.0}
        assert set(out[f.date.values == "d2"]) <= {20.0, 21.0}


def test_is_a_permutation_within_every_date_group():
    rng = np.random.default_rng(3)
    d = np.repeat([f"d{i}" for i in range(6)], 9)
    rng.shuffle(d)
    f = _frame(d, np.arange(len(d)))
    out = T.shuffle_within_date(f, 7, "y")
    for u in np.unique(d):
        m = f.date.values == u
        assert sorted(out[m]) == sorted(f.y.values[m])


def test_seed_changes_the_permutation():
    rng = np.random.default_rng(4)
    d = np.repeat([f"d{i}" for i in range(5)], 12)
    rng.shuffle(d)
    f = _frame(d, np.arange(len(d)))
    assert not np.array_equal(T.shuffle_within_date(f, 0, "y"),
                              T.shuffle_within_date(f, 1, "y"))


def test_single_date_frame_is_still_a_permutation():
    f = _frame(["d1"] * 6, [1, 2, 3, 4, 5, 6])
    out = T.shuffle_within_date(f, 0, "y")
    assert sorted(out) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


# --------------------------------------------- 2. the broken one really leaks --
def test_broken_lexsort_leaks_on_the_pr105_reproducer():
    f = _frame(["d1", "d2", "d1", "d2"], [10, 20, 11, 21])
    leaked = False
    for seed in range(8):
        out = T._shuffle_BROKEN_lexsort(f, seed, "y")
        if (not set(out[f.date.values == "d1"]) <= {10.0, 11.0}
                or not set(out[f.date.values == "d2"]) <= {20.0, 21.0}):
            leaked = True
    assert leaked, "the broken implementation must leak, else it is not the bug"


def test_broken_lexsort_is_harmless_on_a_DATE_SORTED_frame():
    """Why the defect survived review: on sorted input the broken code is FINE.

    This is the whole trap. Any self-check built on a date-sorted fixture --
    the natural way to write a fixture -- passes on the broken code.
    """
    f = _frame(["d1", "d1", "d2", "d2"], [10, 11, 20, 21])
    for seed in range(8):
        out = T._shuffle_BROKEN_lexsort(f, seed, "y")
        assert set(out[f.date.values == "d1"]) <= {10.0, 11.0}
        assert set(out[f.date.values == "d2"]) <= {20.0, 21.0}


# ------------------------------------------- 3. THE TEST OF THE SELF-CHECK -----
def test_selfcheck_passes_on_the_shipped_implementation():
    rep = T.selfcheck_shuffle()
    assert rep["fixed_passes_interleaved"] is True
    assert rep["broken_rejected_seeds_small"], "no seed rejected the broken impl"
    assert rep["broken_rejected_seeds_big"], "no seed rejected the broken impl"


def test_selfcheck_ABORTS_when_the_shuffle_is_the_broken_one(monkeypatch):
    """The load-bearing test: point the guard at the broken shuffle and it must
    refuse to run. If this test fails, the guard is decoration."""
    monkeypatch.setattr(T, "shuffle_within_date", T._shuffle_BROKEN_lexsort)
    with pytest.raises(SystemExit) as e:
        T.selfcheck_shuffle()
    assert "leaked" in str(e.value).lower() or "abort" in str(e.value).lower()


def test_selfcheck_ABORTS_when_the_shuffle_ignores_its_seed(monkeypatch):
    monkeypatch.setattr(T, "shuffle_within_date",
                        lambda f, seed, ycol: f[ycol].to_numpy(copy=True))
    with pytest.raises(SystemExit):
        T.selfcheck_shuffle()


def test_selfcheck_ABORTS_when_the_rejection_probe_is_defeated(monkeypatch):
    """If the 'broken' reference stops leaking, the guard can no longer prove it
    discriminates, and must refuse rather than silently pass."""
    monkeypatch.setattr(T, "_shuffle_BROKEN_lexsort", T.shuffle_within_date)
    with pytest.raises(SystemExit) as e:
        T.selfcheck_shuffle()
    assert "FAILED TO REJECT" in str(e.value)


# ------------------------------------------ the frame really is interleaved ----
def test_the_fixture_is_actually_interleaved():
    """A fixture that happens to be date-sorted would make every test above
    vacuous, so assert non-contiguity explicitly."""
    for f in (T._interleaved_frame(), T._big_interleaved_frame()):
        d = f["_dcode"].to_numpy()
        n_runs = 1 + int((d[1:] != d[:-1]).sum())
        assert n_runs > len(np.unique(d)), "fixture is date-contiguous, not interleaved"
