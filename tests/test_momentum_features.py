"""Analytic fixtures for the momentum feature engine — every expectation derivable by
hand, no market data anywhere."""
from __future__ import annotations

import numpy as np
import pytest

from renquant_model_common.momentum_features import (
    composite_scores, f1_residual_momentum, f2_information_discreteness,
    f3_industry_momentum, f4_signed_volume_agreement, f5_downside_beta_penalty)


RNG = np.random.default_rng(20260801)


def test_f1_pure_beta_exposure_has_small_alpha_t():
    r_m = RNG.normal(0, 0.01, 300)
    r_i = 1.7 * r_m + RNG.normal(0, 0.002, 300)   # beta + noise, zero alpha
    v = f1_residual_momentum(r_i, r_m, min_obs=200)
    assert abs(v) < 3.0                            # an alpha t-stat near zero, seeded


def test_f1_positive_idio_drift_scores_as_a_large_alpha_t():
    """THE DEGENERACY PIN. The naive same-window-with-intercept reading makes
    sum(eps) identically zero — this fixture returned ~0 under that reading and >5
    under the alpha-t semantics the module (and the prereg, post-fix) specify."""
    r_m = RNG.normal(0, 0.01, 400)
    r_i = 0.5 * r_m + 0.001 + RNG.normal(0, 0.002, 400)   # idio drift + noise
    v = f1_residual_momentum(r_i, r_m, min_obs=200)
    assert v > 5


def test_f2_smooth_up_trend_beats_jump():
    smooth = np.full(252, 0.002)
    v_smooth = f2_information_discreteness(smooth, min_obs=200)
    jump = np.zeros(252); jump[100] = 0.6
    v_jump = f2_information_discreteness(jump, min_obs=200)
    assert v_smooth == pytest.approx(1.0)
    assert v_jump < 0.01


def test_f3_sector_mean_and_etf_nan():
    forms = {"A": 0.10, "B": 0.20, "C": -0.10, "GLD": 0.05}
    sect = {"A": "tech", "B": "tech", "C": "fin"}      # GLD unmapped
    out = f3_industry_momentum(forms, sect)
    assert out["A"] == pytest.approx(0.15) and out["B"] == pytest.approx(0.15)
    assert out["C"] == pytest.approx(-0.10)
    assert np.isnan(out["GLD"])


def test_f4_all_volume_on_up_days_is_plus_one():
    r = np.array([0.01, -0.01] * 126)
    vol = np.array([100.0, 0.0] * 126)
    assert f4_signed_volume_agreement(r, vol, min_obs=200) == pytest.approx(1.0)


def test_f5_asymmetric_beta_is_penalized():
    # per-side VARIANCE is required (constant sides made beta undefined — first
    # fixture was degenerate); exact per-side linearity keeps the expectation exact
    down = np.tile([-0.013, -0.007], 75)
    up = np.tile([0.007, 0.013], 75)
    r_m = np.concatenate([down, up])
    r_i = np.where(r_m < 0, 2.0 * r_m, 0.5 * r_m)
    v = f5_downside_beta_penalty(r_i, r_m, min_obs=200, min_side_obs=50)
    assert v == pytest.approx(-(2.0 - 0.5), abs=1e-9)


def test_f5_refuses_without_a_declared_side_floor_being_met():
    r_m = np.concatenate([np.full(5, -0.01), np.full(295, 0.01)])
    r_i = r_m.copy()
    assert np.isnan(f5_downside_beta_penalty(r_i, r_m, min_obs=200, min_side_obs=20))


def test_composite_needs_min_features_and_keeps_the_name_visible():
    feats = {
        "f1": {"A": 1.0, "B": -1.0, "C": 0.0},
        "f2": {"A": 2.0, "B": 0.0, "C": -2.0},
        "f4": {"A": 0.5, "B": float("nan"), "C": -0.5},
    }
    scores, n_used = composite_scores(feats, min_features=3)
    assert n_used == {"A": 3, "B": 2, "C": 3}
    assert np.isfinite(scores["A"]) and np.isfinite(scores["C"])
    assert np.isnan(scores["B"]) and "B" in scores


def test_composite_zero_variance_feature_is_dropped_not_divided_by_zero():
    feats = {"f1": {"A": 1.0, "B": 1.0}, "f2": {"A": 1.0, "B": -1.0}}
    scores, n_used = composite_scores(feats, min_features=1)
    assert n_used == {"A": 1, "B": 1}
