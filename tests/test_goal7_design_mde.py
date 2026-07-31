"""Tests for the GOAL-7 design MDE calibration.

The load-bearing tests here are the two CONTROLS, not the arithmetic ones:

  * `test_harness_reproduces_the_defect_it_was_built_to_measure` — if the
    simulated dependence did not actually inflate the false-positive rate of the
    executed designs, then every MDE this tool reports would be measuring a
    harness with no overlap in it, and would be vacuous.
  * `test_gap_separated_designs_are_correctly_sized` — the mirror image: the
    repair must land at nominal.  A harness that inflates everything equally
    would pass the first test and still be useless.

Together they establish that the tool can tell a broken design from a repaired
one, which is the only property that makes its MDE column worth reading.
"""

from __future__ import annotations

import math
import numpy as np
import pytest
from scipy import stats

from tools import goal7_design_mde as M


# --------------------------------------------------------------- arithmetic --
def test_block_counts_match_the_published_design_table():
    """The redesign doc publishes 4 / 13 / 18 blocks.  Drift is a defect."""
    assert len(M.block_starts(1082, 120, 120)) == 4
    assert len(M.block_starts(1082, 60, 20)) == 13
    assert len(M.block_starts(1082, 40, 20)) == 18


def test_dropped_remainders_match_the_published_design_table():
    for L, gap, blocks, dropped in ((120, 120, 4, 122), (60, 20, 13, 42),
                                    (40, 20, 18, 2)):
        assert 1082 - blocks * (L + gap) == dropped


def test_blocks_never_overlap_and_respect_the_gap():
    for L, gap in ((120, 120), (60, 20), (40, 20)):
        starts = M.block_starts(1082, L, gap)
        for a, b in zip(starts, starts[1:]):
            assert b - (a + L) == gap
        assert starts[-1] + L <= 1082


def test_every_candidate_block_design_has_gap_at_least_h():
    """Dependence validity is a property of the geometry, so assert it."""
    for c in M.CANDIDATES:
        if c.kind == "block":
            assert c.gap >= c.h, f"{c.key} gap={c.gap} < h={c.h}"
            assert M.crossing_fraction(c.h, c.L, c.gap) == 0.0


def test_crossing_fraction_reduces_to_the_published_form_without_a_gap():
    assert M.crossing_fraction(120, 60, 0) == 1.0
    assert M.crossing_fraction(120, 120, 0) == 1.0
    assert M.crossing_fraction(60, 60, 0) == 1.0
    assert M.crossing_fraction(20, 60, 0) == pytest.approx(1 / 3)


def test_gap_absorbs_reach_but_only_up_to_h():
    assert M.crossing_fraction(20, 60, 10) == pytest.approx(10 / 60)
    assert M.crossing_fraction(20, 60, 20) == 0.0
    assert M.crossing_fraction(20, 60, 999) == 0.0


# ------------------------------------------------------------- overlap mix --
def test_overlap_mix_inverts_the_autocorrelation_identity():
    c2 = M.overlap_mix(0.94, 120)
    assert c2 * (1 - 1 / 120) == pytest.approx(0.94)


def test_overlap_mix_refuses_an_autocorrelation_the_overlap_cannot_produce():
    with pytest.raises(ValueError):
        M.overlap_mix(0.999, 120)   # implies c2 > 1


def test_simulated_series_has_the_requested_lag1_autocorrelation():
    rng = np.random.default_rng(3)
    c2 = M.overlap_mix(0.94, 120)
    x = M.simulate_series(rng, 400, 1082, 120, c2, 0.0)
    d = x - x.mean(axis=1, keepdims=True)
    r1 = ((d[:, 1:] * d[:, :-1]).sum(axis=1)
          / (d * d).sum(axis=1)).mean()
    assert r1 == pytest.approx(0.94, abs=0.03)


# ----------------------------------------------------------------- CONTROLS --
@pytest.mark.parametrize("h,L,floor", [(120, 60, 0.15), (120, 120, 0.08),
                                       (60, 60, 0.08)])
def test_harness_reproduces_the_defect_it_was_built_to_measure(h, L, floor):
    """Contiguous blocks at crossing 1.00 must OVER-reject at their own bar.

    Without this the MDE numbers would be produced by a harness in which the
    overlap does nothing, i.e. they would be vacuous.
    """
    rng = np.random.default_rng(11)
    c2 = M.overlap_mix(0.94, 120)
    x = M.simulate_series(rng, 3000, 1082, h, c2, 0.0)
    t = np.abs(M.block_t(x, L, 0))
    nb = len(M.block_starts(1082, L, 0))
    bar = float(stats.t.ppf(0.975, nb - 1))
    assert float((t > bar).mean()) > floor


@pytest.mark.parametrize("h,L,gap", [(120, 120, 120), (20, 60, 20), (20, 40, 20)])
def test_gap_separated_designs_are_correctly_sized(h, L, gap):
    """The repair must land at nominal — otherwise it is not a repair."""
    rng = np.random.default_rng(13)
    c2 = M.overlap_mix(0.94, 120)
    x = M.simulate_series(rng, 3000, 1082, h, c2, 0.0)
    t = np.abs(M.block_t(x, L, gap))
    nb = len(M.block_starts(1082, L, gap))
    bar = float(stats.t.ppf(0.975, nb - 1))
    assert float((t > bar).mean()) == pytest.approx(0.05, abs=0.02)


def test_naive_hac_bar_over_rejects_badly():
    """Option B without its permutation calibration is not a 5% test."""
    rng = np.random.default_rng(17)
    c2 = M.overlap_mix(0.94, 120)
    x = M.simulate_series(rng, 1500, 1082, 120, c2, 0.0)
    t = np.abs(M.hac_t(x, 120))
    assert float((t > 1.959963985).mean()) > 0.12


def test_permutation_calibration_restores_size_for_hac():
    rng = np.random.default_rng(19)
    c2 = M.overlap_mix(0.94, 120)
    crit, _, _, size_cal, size_naive = M.calibrate(
        rng, M.CANDIDATES[1], c2, 1082, 3000)
    assert size_naive > 0.12
    assert size_cal == pytest.approx(0.05, abs=0.012)
    assert crit > 2.5


# -------------------------------------------------------------------- power --
def test_power_is_monotone_in_the_effect_size():
    rng = np.random.default_rng(23)
    c2 = M.overlap_mix(0.94, 120)
    cand = M.CANDIDATES[3]        # C"
    crit = M.calibrate(rng, cand, c2, 1082, 1500)[0]
    ps = [M.power_at(rng, cand, c2, 1082, 800, crit, g)
          for g in (0.0, 0.2, 0.4, 0.8)]
    assert all(b >= a - 0.03 for a, b in zip(ps, ps[1:])), ps
    assert ps[-1] > 0.9


def test_power_at_zero_effect_equals_the_calibrated_size():
    rng = np.random.default_rng(29)
    c2 = M.overlap_mix(0.94, 120)
    cand = M.CANDIDATES[2]        # C'
    crit = M.calibrate(rng, cand, c2, 1082, 2000)[0]
    assert M.power_at(rng, cand, c2, 1082, 2000, crit, 0.0) == pytest.approx(
        0.05, abs=0.02)


def test_mde_returns_none_rather_than_a_number_off_the_grid():
    rng = np.random.default_rng(31)
    c2 = M.overlap_mix(0.94, 120)
    cand = M.CANDIDATES[0]        # A — the coarse one
    crit = M.calibrate(rng, cand, c2, 1082, 800)[0]
    m, _ = M.mde(rng, cand, c2, 1082, 400, crit, [0.01, 0.02])
    assert m is None


def test_block_t_refuses_a_geometry_with_fewer_than_two_blocks():
    with pytest.raises(ValueError):
        M.block_t(np.zeros((2, 100)), 90, 90)
