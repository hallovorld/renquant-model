"""Tests for the GOAL-4 dependence-preserving null calibration.

The load-bearing tests are again the CONTROLS:

  * the instrument must RESPOND to serial dependence — a series with none must
    calibrate lower than the real one, or the bootstrap is not carrying dependence
    at all and every number it produces is meaningless;
  * the instrument must REPORT ITS OWN BIAS — i.i.d. Gaussian input does not
    produce a 0.05 size at this geometry, so any row lacking `size_iid_baseline`
    would charge the data for a distortion the bootstrap introduced.
"""

from __future__ import annotations

import numpy as np
import pytest

from tools import goal4_null_calibration as C


def _real():
    return C.load_series(
        "doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/per_date_g_real.csv")


# ------------------------------------------------------------- the geometry --
def test_executed_geometry_matches_the_screens_own_results():
    x = _real()
    assert x.shape[0] == C.N_EVAL == 508
    assert C.n_blocks(C.N_EVAL, C.BLOCK_L, 0) == C.N_BLOCKS == 8
    assert C.N_EVAL - C.N_BLOCKS * C.BLOCK_L == 28   # .main.dropped_remainder_days


def test_executed_geometry_crosses_fully():
    assert C.crossing(C.LABEL_H, C.BLOCK_L, 0) == 1.0


def test_a_gap_of_at_least_h_removes_all_crossing():
    assert C.crossing(C.LABEL_H, 60, 60) == 0.0
    assert C.crossing(C.LABEL_H, 30, 60) == 0.0
    assert C.crossing(C.LABEL_H, 60, 30) == pytest.approx(0.5)


# --------------------------------------------------------------- resampling --
def test_circular_resample_returns_the_requested_shape_and_only_real_values():
    rng = np.random.default_rng(1)
    x0 = np.arange(508, dtype=float)
    r = C.circular_block_resample(rng, x0, 50, 60)
    assert r.shape == (50, 508)
    assert set(np.unique(r)).issubset(set(x0.tolist()))


def test_circular_resample_wraps_rather_than_truncating():
    """A block starting near the end must wrap, not run short."""
    rng = np.random.default_rng(2)
    x0 = np.zeros(508)
    x0[-1] = 1.0
    r = C.circular_block_resample(rng, x0, 400, 60)
    assert r.sum() > 0            # the last element is reachable


def test_block_t_refuses_a_geometry_with_fewer_than_two_blocks():
    with pytest.raises(ValueError):
        C.block_t(np.zeros((2, 508)), 300, 0)


# ----------------------------------------------------------------- CONTROLS --
def test_the_instrument_responds_to_serial_dependence():
    """A dependent series must calibrate to a WIDER null than an independent one.

    Without this the circular block bootstrap could be shuffling i.i.d.-style and
    every size in the sweep would be an artefact.
    """
    rng = np.random.default_rng(3)
    real = _real()
    real = real - real.mean()
    indep = C.load_series(
        "doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/"
        "per_date_synthetic_control_ic.csv")
    indep = indep - indep.mean()
    assert abs(C.autocorr(real, (1,))[1]) > 0.5      # measured 0.7317
    assert abs(C.autocorr(indep, (1,))[1]) < 0.15    # measured -0.0412
    p_real = C.calibrate(rng, real, 3000, 60, 60, 0)["P95_bootstrap"]
    p_ind = C.calibrate(rng, indep, 3000, 60, 60, 0)["P95_bootstrap"]
    assert p_real > p_ind


def test_every_row_carries_its_own_iid_baseline():
    """A size without its instrument baseline is not interpretable."""
    rng = np.random.default_rng(5)
    row = C.calibrate(rng, _real() - _real().mean(), 1500, 60, 60, 0)
    for k in ("size_iid_baseline", "size_excess_over_baseline", "P95_iid_baseline"):
        assert k in row
    assert row["size_excess_over_baseline"] == pytest.approx(   # reported to 4dp
        row["size_at_student_bar"] - row["size_iid_baseline"], abs=5e-5)


def test_the_instrument_is_NOT_exact_on_iid_input():
    """The baseline is not 0.05, which is exactly why it must be reported.

    If this ever starts passing at 0.05 the baseline column becomes redundant —
    but until then, reporting a raw size against a nominal 0.05 overstates the
    damage attributable to the data.
    """
    rng = np.random.default_rng(7)
    iid = rng.standard_normal(508)
    iid -= iid.mean()
    row = C.calibrate(rng, iid, 4000, 60, 60, 0)
    assert row["size_at_student_bar"] > 0.055


# -------------------------------------------------------------------- power --
def test_power_is_monotone_and_reaches_one():
    rng = np.random.default_rng(11)
    x0 = _real() - _real().mean()
    ps = [C.power_at(rng, x0, 1200, 60, 60, 0, 2.3646, g)
          for g in (0.0, 0.02, 0.05, 0.20)]
    assert all(b >= a - 0.03 for a, b in zip(ps, ps[1:])), ps
    assert ps[-1] > 0.95


def test_mde_returns_none_when_the_grid_is_too_short():
    rng = np.random.default_rng(13)
    x0 = _real() - _real().mean()
    assert C.mde(rng, x0, 600, 60, 60, 0, 2.3646, [0.0001, 0.0002]) is None


def test_mde_lower_bound_is_far_above_a_plausible_ensemble_gain():
    """Anti-vacuity for the headline: the gap must be orders of magnitude.

    Measured MDE at the most generous bar in the sweep is ~0.0376 IC; the
    plausible gain on the production recipe is +0.00079.
    """
    rng = np.random.default_rng(17)
    x0 = _real() - _real().mean()
    m = C.mde(rng, x0, 3000, 60, 60, 0, C.T_CRIT_EXECUTED,
              [0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.08, 0.15])
    assert m is not None
    assert m > 0.02
    assert m / 0.00079 > 20
