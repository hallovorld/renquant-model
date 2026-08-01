"""Inference-machinery tests: recovery, boundaries, gate logic — tiny reps, no real data."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "goal7_momentum_inference", REPO / "tools" / "goal7_momentum_inference.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def test_frozen_constants_match_the_prereg():
    c = M.FROZEN_INFERENCE
    assert (c["h"], c["L"], c["alpha_per_test"], c["quantile"]) == (20, 59, 0.025, 0.975)
    assert (c["reps"], c["seed"], c["ar_p_max"]) == (5000, 20260801, 20)
    lo, hi = c["gate_band"]
    se = np.sqrt(0.025 * 0.975 / 5000)
    assert lo == pytest.approx(0.025 - 3 * se, abs=2e-4)
    assert hi == pytest.approx(0.025 + 3 * se, abs=2e-4)


def test_ma_generator_variance_matches_target():
    rng = np.random.default_rng(2)
    v = M.gen_overlap_ma(rng, 2000, 20, 0.04)
    assert v.std() == pytest.approx(0.2, rel=1e-9)   # exact rescale by construction


def test_ar1_recovery_and_the_slice_boundary():
    """Regression pin for the negative-slice bug: p=1's first step must read exactly
    one lag, and phi=0.7 must be recovered on resampled innovations."""
    rng = np.random.default_rng(1)
    series = M.gen_ar_resample(rng, 800, np.array([0.7]), rng.standard_normal(500))
    fit = M.fit_ar(series, 5)
    assert fit["p"] == 1
    assert fit["phi"][0] == pytest.approx(0.7, abs=0.08)


def test_frozen_envelope_is_DEGENERATE_and_the_max_test_is_not():
    """Measured 2026-08-01: the frozen 2·(1/√n) max-over-40-lags envelope rejects
    15–19 of 20 PERFECT-SPECIFICATION true-AR series (the max of K noisy deviations
    almost surely exceeds a per-lag 2·SE band). The principled max-test envelope
    (z₁₋α/2K · Bartlett SE) passes the same fixtures. Both behaviors pinned; prereg
    Amendment 2 proposes switching the frozen rule."""
    rng = np.random.default_rng(3)
    series = M.gen_ar_resample(rng, 1500, np.array([0.6]), rng.standard_normal(800))
    fit = M.fit_ar(series, 5)
    frozen = M.adequacy_check(series, fit, dict(M.FROZEN_INFERENCE,
                                                envelope_rule="frozen_2se"),
                              np.random.default_rng(4))
    boot = M.adequacy_check(series, fit, dict(M.FROZEN_INFERENCE,
                                              envelope_rule="bootstrap_max",
                                              adequacy_boot_reps=120),
                            np.random.default_rng(4))
    assert not frozen["ok"], "the degenerate frozen rule unexpectedly passed"
    assert boot["ok"], boot
    assert boot["bootstrap_threshold"] > boot["max_abs_dev"]


def test_calibrate_returns_UNRESOLVED_METHOD_when_ar_cannot_express_the_series():
    """An MA(19) series fit by a small-p AR fails the envelope — and per the reviewed
    rule that is UNRESOLVED-METHOD with NO collapse to the MA member."""
    rng = np.random.default_rng(5)
    v = M.gen_overlap_ma(rng, 400, 20, 1.0)
    cfg = dict(M.FROZEN_INFERENCE); cfg["reps"] = 200; cfg["ar_p_max"] = 3
    cal = M.calibrate_bar(v, cfg)
    assert cal["status"] == "UNRESOLVED-METHOD"
    assert "collapse" in cal["why"]
    assert "overlap_ma" in cal["bars"] and "ar_resample" not in cal["bars"]


def test_calibrate_succeeds_on_an_ar_series_and_takes_the_max_bar():
    rng = np.random.default_rng(6)
    v = M.gen_ar_resample(rng, 600, np.array([0.5]), rng.standard_normal(400))
    cfg = dict(M.FROZEN_INFERENCE); cfg["reps"] = 200
    cfg["envelope_rule"] = "bootstrap_max"          # the Amendment-2 rule
    cfg["adequacy_boot_reps"] = 120
    cal = M.calibrate_bar(v, cfg)
    assert cal["status"] == "calibrated", cal
    assert cal["t_star"] == pytest.approx(max(cal["bars"].values()))


def test_machinery_self_check_logic_rejects_absurd_bars():
    rng_series = M.gen_overlap_ma(np.random.default_rng(7), 300, 20, 1.0)
    lo_bar = M.machinery_self_check(rng_series, t_star=0.0,
                                    cfg=M.FROZEN_INFERENCE, reps=100)
    hi_bar = M.machinery_self_check(rng_series, t_star=99.0,
                                    cfg=M.FROZEN_INFERENCE, reps=100)
    assert lo_bar["rate"] == 1.0 and not lo_bar["ok"]
    assert hi_bar["rate"] == 0.0 and not hi_bar["ok"]


def test_hac_t_matches_the_pinned_implementation_formula():
    """Cross-check against renquant_common's hac_se on one series (the runner does
    this on every execution; here it pins the mirror at test time). Skips loudly if
    the pinned runtime copy is absent (CI)."""
    hac_path = Path("/Users/renhao/git/github/RenQuant/.subrepo_runtime/repos/"
                    "renquant-common/src/renquant_common/metrics/hac_se.py")
    if not hac_path.exists():
        pytest.skip("pinned renquant-common absent — mirror check not verifiable here")
    import sys
    sys.path.insert(0, str(hac_path.parent.parent.parent))
    from renquant_common.metrics.hac_se import newey_west_se
    rng = np.random.default_rng(8)
    v = M.gen_overlap_ma(rng, 500, 20, 1.0)
    mine = M.bartlett_hac_t(v, 59)
    theirs = float(v.mean()) / newey_west_se(v, lag=59)
    assert mine == pytest.approx(theirs, rel=1e-9)
