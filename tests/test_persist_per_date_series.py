"""GOAL-7 §7 — the runner must persist the per-date series it already computes.

The load-bearing test is the LAST one: writing must not change any number the run
would otherwise report. A persistence feature that perturbs a frozen harness would
be worse than the omission it fixes.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
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


# --- the paired contrast is the artifact (codex #131) -------------------------
#
# The first version wrote `subject` and `baseline` BEFORE the runner formed
# `common = subj.index.intersection(base.index)` and `dpair = (subj - base).dropna()`.
# A later reader had to guess that alignment, and a different guess yields a different
# calibration -- which is exactly what this file exists to prevent. These tests pin the
# persisted contrast against the one the runner actually hands to `agg`.

def _mismatched_pair():
    """Deliberately misaligned indexes: overlap, subject-only, baseline-only, and a
    NaN inside the overlap. A naive `subj - base` differs from the runner's dpair on
    every one of those."""
    subj = pd.Series({"2026-01-02": 1.0, "2026-01-03": 2.0, "2026-01-05": 4.0,
                      "2026-01-06": float("nan")})
    base = pd.Series({"2026-01-02": 0.5, "2026-01-03": 0.25, "2026-01-04": 9.0,
                      "2026-01-06": 1.0})
    common = subj.index.intersection(base.index)
    dpair = (subj.reindex(common) - base.reindex(common)).dropna()
    return subj, base, dpair


def test_the_persisted_contrast_is_byte_for_byte_the_series_agg_receives(tmp_path):
    subj, base, dpair = _mismatched_pair()
    out = tmp_path / "s.csv"
    M.write_per_date_series({"subject": subj, "baseline": base}, out, paired=dpair)

    got = pd.read_csv(out, index_col="date")["paired_contrast"].dropna()
    assert list(got.index) == list(dpair.index)
    assert [float(x) for x in got] == [float(x) for x in dpair]


def test_a_DIFFERENT_reconstruction_really_does_diverge(tmp_path):
    """Anti-vacuity, and a correction to my first version of this test.

    I first asserted that a naive `subject - baseline` could not recover `dpair`.
    That is FALSE: pandas aligns on subtraction, so `(subj - base).dropna()` equals
    the runner's intersection-then-dropna exactly. My own test caught it.

    The real gap codex identified is narrower and still real: the reader must GUESS
    which operation was performed. Reconstructions that are entirely reasonable a
    priori — fill the gaps instead of dropping them, or keep the union — give a
    different series and therefore a different calibration. That is what the
    persisted column and the sidecar definition remove.
    """
    subj, base, dpair = _mismatched_pair()
    equivalent = (subj - base).dropna()
    assert [float(x) for x in equivalent] == [float(x) for x in dpair], (
        "pandas alignment makes these identical; if that ever changes, say so here")

    filled = (subj - base).fillna(0.0)          # a plausible alternative choice
    union = subj.reindex(subj.index.union(base.index)) -         base.reindex(subj.index.union(base.index))
    assert len(filled) != len(dpair) or list(filled) != list(dpair)
    assert len(union) != len(dpair)


def test_the_sidecar_carries_enough_to_read_the_csv_alone(tmp_path):
    subj, base, dpair = _mismatched_pair()
    out = tmp_path / "s.csv"
    meta = M.write_per_date_series(
        {"subject": subj, "baseline": base}, out, paired=dpair,
        provenance={"subject_arm": "A1", "baseline_arm": "B1",
                    "label_column": "fwd_120_tr", "label_horizon_trading_days": 120,
                    "matrix_sha256": "aa", "tr_sha256": "bb"})
    side = json.loads((tmp_path / "s.meta.json").read_text())
    for k in ("subject_arm", "baseline_arm", "label_column",
              "label_horizon_trading_days", "matrix_sha256", "tr_sha256",
              "paired_contrast_definition"):
        assert k in side, f"sidecar cannot be interpreted without {k}"
    assert side["n_paired"] == len(dpair)
    assert meta["sidecar"].endswith("s.meta.json")


def test_the_runner_writes_AFTER_forming_dpair():
    """Ordering is the defect, so it is pinned in the source rather than only in
    behaviour: a future edit that hoists the write back above the intersection
    re-creates the ambiguity without failing any value assertion."""
    src = pathlib.Path(M.__file__).read_text()
    i_dpair = src.index("dpair = (subj.reindex(common)")
    i_write = src.index("R[\"per_date_series\"] = write_per_date_series(")
    assert i_dpair < i_write, (
        "the per-date write happens before dpair is formed — it can only persist "
        "ingredients, not the series actually tested")
