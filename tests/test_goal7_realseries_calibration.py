"""The per-date series is the frozen run's, and the calibration refuses to overclaim.

Two things are pinned here. First, the series may only be treated as GOAL-7 Stage 1's if
every published arm statistic reproduces bit-identically — a "close enough" reconstruction
would calibrate a bar nobody registered. Second, a bootstrap cell built from a handful of
draws must not be usable as evidence in EITHER direction: the low tail cell (0.034) is as
unquotable as the high one (0.111), and a checker that only guards against optimism would
let the conservative-looking cell through.
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import goal7_realseries_calibration as C  # noqa: E402

DATA = ROOT / "doc" / "research" / "data" / "2026-08-01-goal7-realseries-calibration"
FROZEN = (ROOT / "doc" / "research" / "data"
          / "2026-07-30-goal7-stage1-two-sided-tail" / "results.json")


@pytest.fixture(scope="module")
def cal():
    return json.loads((DATA / "calibration.json").read_text())


# ------------------------------------------------ the warrant for the series --
def test_every_arm_statistic_reproduced_BIT_IDENTICALLY(cal):
    """The whole warrant. Without this the series is an unrelated computation."""
    r = cal["reproduction"]
    assert r["all_identical"] is True
    assert r["n_compared"] == 6
    for name, row in r["arms"].items():
        assert row["identical"] is True, (name, row["divergent_fields"])


def test_the_reproduction_compares_the_LOAD_BEARING_fields():
    """A repro check over only `n_blocks` would pass on any series of the right length."""
    for f in ("block_mean", "block_sd", "t", "abs_t"):
        assert f in C.REPRO_FIELDS


def test_a_DIVERGENT_reconstruction_is_reported_and_calibrates_nothing():
    frozen = {"arms": {"z": {"treatment_u": {"mean_per_date": 1.0, "block_mean": 1.0,
                                             "block_sd": 1.0, "t": 1.0, "abs_t": 1.0,
                                             "n_blocks": 18}}}}
    g = np.arange(18 * 60, dtype=float)
    out = C.check_repro({("z", "treatment_u"): g}, 18, frozen)
    assert out["all_identical"] is False
    assert out["arms"]["z/treatment_u"]["divergent_fields"]


def test_the_persisted_series_covers_exactly_the_BLOCK_COVERED_dates(cal):
    s = cal["per_date_series"]
    assert s["dates_per_series"] == 18 * 60 == 1080
    assert s["rows"] == 6 * 1080
    rows = (DATA / "per_date_g_real.csv").read_text().strip().split("\n")
    assert rows[0] == "date,label,arm,g"
    assert len(rows) - 1 == 6 * 1080


def test_the_series_carries_DATES_not_just_values():
    """A bare column of numbers cannot be checked against the partition, and the
    partition is the thing under dispute."""
    row = (DATA / "per_date_g_real.csv").read_text().split("\n")[1].split(",")
    assert len(row) == 4 and row[0].count("-") == 2


def test_the_dropped_remainder_is_NOT_in_the_series():
    """§3 drops 2021-04-16 and 2021-04-19; a calibration of that estimator may not use
    dates the estimator itself never scored."""
    text = (DATA / "per_date_g_real.csv").read_text()
    frozen = json.loads(FROZEN.read_text())
    for d in frozen["partition"]["dropped_dates"]:
        assert f"\n{d}," not in text, d


# ----------------------------------------- the calibration refuses to overclaim --
def test_NOT_IDENTIFIED_on_every_series(cal):
    """The measured outcome. If this ever flips, the verdict below must be re-derived,
    not inherited."""
    assert cal["verdict"]["any_series_identified"] is False
    for k, c in cal["calibration"].items():
        assert c["identified"] is False, k


def test_preserving_the_label_horizon_leaves_TOO_FEW_DRAWS(cal):
    """The finding in one line: the two requirements do not overlap."""
    for k, c in cal["calibration"].items():
        assert c["min_Lb_preserving_the_label_horizon"] == 120, k
        assert c["draws_at_that_Lb"] == 9, k
        assert c["dependence_and_bootstrap_requirements_overlap"] is False, k


def test_the_LOW_tail_cell_is_excluded_too_not_just_the_high_one(cal):
    """0.034 at Lb=240 comes from FIVE draws. A checker that only rejected the inflated
    cells would let a flattering one through, and that asymmetry is how a design gets
    talked into looking correctly sized."""
    for k, c in cal["calibration"].items():
        for lb in (120, 180, 240):
            cell = c["by_block_length"][str(lb)]
            assert cell["usable_for_a_size_claim"] is False, (k, lb)
        assert 240 not in c["usable_Lb"] and 120 not in c["usable_Lb"], k


def test_usable_cells_are_exactly_those_with_enough_draws(cal):
    for k, c in cal["calibration"].items():
        for lb_s, cell in c["by_block_length"].items():
            expect = math.ceil(1080 / int(lb_s)) >= C.MIN_DRAWS
            assert cell["usable_for_a_size_claim"] is expect, (k, lb_s)
        assert c["usable_Lb"] == [1, 5, 10, 20, 30], k


def test_the_required_span_is_ARITHMETIC_on_the_two_stated_requirements(cal):
    """Derived, not measured — and the document must not read it as evidence that a
    2400-date design would pass."""
    for c in cal["calibration"].values():
        assert c["dates_required_for_an_identifiable_bar"] == C.MIN_DRAWS * 120 == 2400
        assert c["dates_available"] == 1080


def test_the_measured_rho1_confirms_the_reviewer_not_the_registration(cal):
    """codex's 0.94 was the objection; it is a property of the real series."""
    for k, c in cal["calibration"].items():
        assert 0.90 <= c["lag1_autocorr"] <= 0.99, (k, c["lag1_autocorr"])


# ------------------------------------------------------- the bootstrap itself --
def test_the_bootstrap_is_CIRCULAR_so_the_ends_are_not_undersampled():
    """A truncated block bootstrap under-samples the first and last Lb-1 points, which
    biases the resampled variance DOWN — i.e. it errs toward flattering the design."""
    rng = np.random.default_rng(0)
    e = np.arange(100, dtype=float)
    boot = C.circular_block_bootstrap(e, 10, 4000, rng)
    counts = np.bincount(boot.astype(int).ravel(), minlength=100)
    assert counts.min() > 0
    assert counts.max() / counts.min() < 1.25, (counts.min(), counts.max())


def test_the_bootstrap_imposes_the_NULL_by_demeaning_not_by_assumption():
    rng = np.random.default_rng(1)
    g = np.random.default_rng(2).normal(5.0, 1.0, 1080)      # a big nonzero mean
    out = C.calibrate(g, 18, 2.1098, rng)
    # If the mean were not removed, the "null" would reject essentially always.
    assert out["by_block_length"][1]["realised_size"] < 0.20


def test_n_blk_drawn_is_a_CEILING_not_a_floor():
    assert C.n_blk_drawn(1080, 240) == 5
    assert C.n_blk_drawn(1080, 7) == 155        # 154.28… must round UP


def test_a_degenerate_resample_is_dropped_not_counted_as_a_pass():
    """sd == 0 makes t undefined; counting it as "did not reject" would silently lower
    every realised size."""
    rng = np.random.default_rng(3)
    out = C.calibrate(np.zeros(1080), 18, 2.1098, rng)
    for cell in out["by_block_length"].values():
        assert cell["n_usable"] == 0 and cell["n_degenerate"] == C.N_BOOT
        # None, NOT 0.0: a size of zero reads as "the bar never fires", which is the
        # opposite of "unknown". And it must not raise -- a scheduled caller cannot tell
        # a thrown exception from a deliberate alarm.
        assert cell["realised_size"] is None and cell["p95_abs_t"] is None
        assert cell["usable_for_a_size_claim"] is False
    assert out["identified"] is False
