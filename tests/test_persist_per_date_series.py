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


def test_the_runner_actually_PASSES_dpair_to_the_writer():
    """The gap my first load-bearing check exposed.

    Every value test above calls `write_per_date_series` directly, so they all pass
    even if the runner stops handing it `dpair` — I verified that by changing the call
    to `paired=None` and watching 12 tests still pass. The writer being correct is not
    the same as the runner using it correctly, and only the call site can say so.
    """
    src = pathlib.Path(M.__file__).read_text()
    assert "paired=dpair" in src, (
        "the runner no longer passes the paired contrast to the writer — the CSV "
        "would carry only subject/baseline and the reconstruction ambiguity is back")


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


# ===================================================================== SHARED ==
# The writer is now imported by two runners. These tests defend the property that
# made sharing worth doing: ONE definition. `renquant-pipeline` keeps a registry of
# twin implementations precisely because copies agree the day they are written and
# drift silently afterwards -- and a duplicated writer in the lane whose purpose is
# making a dependence assumption CHECKABLE would produce two artifacts that
# disagree about the very series the check reads.

def test_the_writer_is_defined_exactly_once_in_the_repo():
    hits = [p for p in (ROOT / "tools").rglob("*.py")
            if "def write_per_date_series(" in p.read_text(encoding="utf-8")]
    assert [p.name for p in hits] == ["per_date_series_io.py"], hits


def test_both_runners_import_it_rather_than_redefining_it():
    for name in ("momentum_total_return_run.py", "momentum_horizon_run.py"):
        src = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "from per_date_series_io import write_per_date_series" in src, name
        assert "def write_per_date_series(" not in src, name


def test_the_sidecar_does_not_define_a_column_it_did_not_write(tmp_path):
    """A sidecar that documents `paired_contrast` for a file WITHOUT that column
    describes an object that is not there; a reader who trusts it reconstructs a
    contrast the run never made."""
    out = tmp_path / "unpaired.csv"
    rep = M.write_per_date_series({"E1": _s(["2026-01-02"], [0.1])}, out)
    assert "paired_contrast" not in rep["columns"]
    side = json.loads(pathlib.Path(rep["sidecar"]).read_text())
    assert "paired_contrast_definition" not in side
    assert side["n_paired"] == 0
    # ...and the mirror: when the column IS written, the definition must be there.
    out2 = tmp_path / "paired.csv"
    rep2 = M.write_per_date_series({"subject": _s(["2026-01-02"], [0.1])}, out2,
                                   paired=_s(["2026-01-02"], [0.3]))
    side2 = json.loads(pathlib.Path(rep2["sidecar"]).read_text())
    assert "paired_contrast_definition" in side2


# =========================================================== HORIZON RUNNER ====
_hspec = importlib.util.spec_from_file_location(
    "momentum_horizon_run", ROOT / "tools" / "momentum_horizon_run.py")
H = importlib.util.module_from_spec(_hspec)
sys.modules[_hspec.name] = H
_hspec.loader.exec_module(H)


def _panel(n_dates=64, n_names=40, seed=0):
    import numpy as np
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_dates)
    rows = []
    for d in dates:
        x = rng.standard_normal(n_names)
        rows.append(pd.DataFrame({"date": d,
                                  "ticker": [f"T{i}" for i in range(n_names)],
                                  "A1_mom_12_1": x,
                                  "fwd_20": 0.3 * x + rng.standard_normal(n_names)}))
    return pd.concat(rows, ignore_index=True)


def test_keep_series_returns_the_EXACT_series_agg_consumed():
    """Not a recomputation. A second call to per_date_stats would be a twin of the
    one that produced the reported t, and the persisted file could then disagree
    with the number the run published."""
    df = _panel()
    r = H.measure(df, "A1_mom_12_1", 20, controls=False, keep_series=True)
    e1, e2 = H.per_date_stats(df.assign(_dcode=pd.factorize(df["date"])[0]),
                              "A1_mom_12_1", "fwd_20")
    pd.testing.assert_series_equal(r["_series"]["E1_rank_ic"], e1)
    pd.testing.assert_series_equal(r["_series"]["E2_top_decile_spread"], e2)
    assert r["E2"]["n"] == len(e2)          # the reported n IS this series' length


def test_measure_is_unchanged_when_the_series_is_not_kept():
    """Anti-regression on a frozen harness: persistence must not move a number."""
    df = _panel(seed=3)
    a = H.measure(df, "A1_mom_12_1", 20, controls=False, keep_series=False)
    b = H.measure(df, "A1_mom_12_1", 20, controls=False, keep_series=True)
    b.pop("_series")
    assert a == b
    assert "_series" not in a


def test_the_persisted_holdout_file_records_that_crossing_is_full(tmp_path):
    """The runner's block_length IS the label horizon (`agg(e2, h, ...)`), so
    crossing = min(1, h/h) = 1.00 -- the MAXIMUM overlap, not a remedy for it.
    The artifact must say so, or a later reader treats an uncalibrated Student
    bar as calibrated."""
    df = _panel()
    r = H.measure(df, "A1_mom_12_1", 20, controls=False, keep_series=True)
    out = tmp_path / "holdout.csv"
    meta = M.write_per_date_series(
        r["_series"], out,
        provenance={"block_length_used_by_agg": 20, "label_horizon_days": 20,
                    "gap_between_blocks": 0, "crossing_fraction": 1.0})
    assert meta["crossing_fraction"] == 1.0
    assert meta["block_length_used_by_agg"] == meta["label_horizon_days"]
    side = json.loads(pathlib.Path(meta["sidecar"]).read_text())
    assert side["crossing_fraction"] == 1.0


def test_the_horizon_runner_exposes_the_flag_and_records_full_crossing():
    src = (ROOT / "tools" / "momentum_horizon_run.py").read_text(encoding="utf-8")
    assert '"--per-date-out"' in src
    assert '"crossing_fraction": 1.0' in src
    assert 'keep_series=True' in src


def test_a_series_too_short_for_two_blocks_is_UNRESOLVED_not_a_crash():
    """`len(s) < 3` and "enough dates for two blocks" are different quantities.
    Between them the old code raised TypeError -- a short holdout crashed the run
    instead of reporting a statement about POWER."""
    df = _panel(n_dates=8)          # 8 dates, block_length 20 -> not two blocks
    r = H.measure(df, "A1_mom_12_1", 20, controls=False)
    assert r["E2"]["resolves"] is False
    assert r["E2"]["t"] != r["E2"]["t"]        # NaN
    assert r["E2"]["n"] > 0                    # the series existed; the BAR did not
