"""GOAL-7 §7 — the runner must persist the per-date series it already computes.

The load-bearing test is the LAST one: writing must not change any number the run
would otherwise report. A persistence feature that perturbs a frozen harness would
be worse than the omission it fixes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "momentum_total_return_run", ROOT / "tools" / "momentum_total_return_run.py")
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)


def _s(dates, vals):
    return pd.Series(vals, index=pd.to_datetime(dates))


def test_writes_the_series_it_is_given(tmp_path):
    out = tmp_path / "per_date.csv"
    rep = M.write_per_date_series(
        {"subject": _s(["2026-01-02", "2026-01-05"], [0.1, -0.2])}, out)
    assert out.exists()
    df = pd.read_csv(out, index_col=0)
    assert list(df.columns) == ["subject"]
    assert df["subject"].tolist() == [0.1, -0.2]
    assert rep["n_rows"] == 2 and rep["columns"] == ["subject"]


def test_multiple_series_align_on_date_not_position(tmp_path):
    """Subject and baseline have DIFFERENT date sets in the real run."""
    out = tmp_path / "p.csv"
    M.write_per_date_series({
        "subject": _s(["2026-01-02", "2026-01-05", "2026-01-06"], [1.0, 2.0, 3.0]),
        "baseline": _s(["2026-01-05", "2026-01-06"], [9.0, 8.0]),
    }, out)
    df = pd.read_csv(out, index_col=0)
    assert len(df) == 3
    assert pd.isna(df.loc["2026-01-02", "baseline"])
    assert df.loc["2026-01-05", "baseline"] == 9.0


def test_output_is_sorted_by_date(tmp_path):
    out = tmp_path / "p.csv"
    M.write_per_date_series(
        {"subject": _s(["2026-03-01", "2026-01-01", "2026-02-01"], [3, 1, 2])}, out)
    df = pd.read_csv(out, index_col=0)
    assert df.index.tolist() == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert df["subject"].tolist() == [1, 2, 3]


def test_none_series_are_dropped_not_written_as_a_column(tmp_path):
    out = tmp_path / "p.csv"
    rep = M.write_per_date_series(
        {"subject": _s(["2026-01-02"], [0.5]), "absent": None}, out)
    assert rep["columns"] == ["subject"]


def test_parent_directory_is_created(tmp_path):
    out = tmp_path / "deep" / "nested" / "p.csv"
    M.write_per_date_series({"subject": _s(["2026-01-02"], [0.5])}, out)
    assert out.exists()


def test_an_empty_series_still_writes_a_readable_file(tmp_path):
    """A run with no admissible dates must leave evidence of that, not nothing."""
    out = tmp_path / "p.csv"
    rep = M.write_per_date_series({"subject": pd.Series(dtype=float)}, out)
    assert out.exists()
    assert rep["n_rows"] == 0
    assert rep["first_date"] is None


def test_writing_CANNOT_alter_the_series(tmp_path):
    """ANTI-REGRESSION, and the reason this is safe to add to a frozen harness:
    persistence must be a pure read. If this ever fails, the feature is changing
    the run it was added to observe."""
    subj = _s(["2026-01-02", "2026-01-05"], [0.1, -0.2])
    base = _s(["2026-01-05"], [9.0])
    before = (subj.copy(), base.copy())
    M.write_per_date_series({"subject": subj, "baseline": base}, tmp_path / "p.csv")
    pd.testing.assert_series_equal(subj, before[0])
    pd.testing.assert_series_equal(base, before[1])


def test_the_flag_exists_and_defaults_to_not_writing(tmp_path):
    """Default OFF: a frozen prereg run without the flag is byte-identical."""
    import argparse
    src = (ROOT / "tools" / "momentum_total_return_run.py").read_text()
    assert '"--per-date-out"' in src
    assert 'ap.add_argument("--per-date-out", default=None' in src
    assert "if a.per_date_out:" in src
