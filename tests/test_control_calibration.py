"""Pins the 2026-07-29 defect: a placebo arm that was significantly positive.

The PatchTST walk-forward evaluation read its real arm against a `shift120`
label-displacement placebo. On a common 524-score-date sample (37 folds) the
placebo scored +0.0715 at t=+2.90 while the real arm scored +0.0343 at t=+1.38.
The control outperformed the treatment and was the only arm to clear
significance — which makes every verdict built on it void, in either direction.
"""
from __future__ import annotations

import math

import pytest

from renquant_model_common.control_calibration import (
    ControlCalibrationError,
    assess_control,
    gate_comparison,
)


def _arm(mean: float, sd: float, n: int, seed: int = 0) -> list[float]:
    """A fold-level arm with a target mean and dispersion (deterministic)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    v = rng.normal(size=n)
    v = (v - v.mean()) / v.std(ddof=1)          # exact standardisation
    return list(mean + sd * v)


# The measured 2026-07-29 numbers: 37 folds, control mean +0.0715 at t=+2.90.
# sd implied by t = mean / (sd/sqrt(n))  ->  sd = mean*sqrt(n)/t
N_FOLDS = 37
CONTROL_MEAN = 0.0715
CONTROL_SD = CONTROL_MEAN * math.sqrt(N_FOLDS) / 2.90


def test_the_real_placebo_is_rejected():
    v = assess_control(_arm(CONTROL_MEAN, CONTROL_SD, N_FOLDS),
                       name="shift120")
    assert v.status == "NOT_NULL"
    assert not v.usable
    assert v.t_stat == pytest.approx(2.90, abs=0.02)
    assert "VOID" in v.reason


def test_the_real_shuffle_arm_is_accepted():
    # measured the same day on the same corpus: +0.0013 at t=+0.90
    sd = 0.0013 * math.sqrt(43) / 0.90
    v = assess_control(_arm(0.0013, sd, 43), name="shuffle")
    assert v.status == "CLEAN"
    assert v.usable


def test_a_broken_control_voids_the_whole_comparison():
    """One bad arm is enough: the reader cannot tell which null was used."""
    ok, verdicts = gate_comparison({
        "shuffle": _arm(0.0013, 0.0095, 43, seed=1),
        "shift120": _arm(CONTROL_MEAN, CONTROL_SD, N_FOLDS, seed=2),
    })
    assert ok is False
    by_name = {v.name: v for v in verdicts}
    assert by_name["shuffle"].usable
    assert not by_name["shift120"].usable


def test_all_clean_controls_permit_the_comparison():
    ok, verdicts = gate_comparison({
        "shuffle": _arm(0.0013, 0.0095, 43, seed=3),
        "negctl": _arm(-0.0020, 0.0110, 43, seed=4),
    })
    assert ok is True
    assert all(v.usable for v in verdicts)


def test_a_negative_control_is_rejected_too():
    """Direction is irrelevant — a control with signal is not a null."""
    v = assess_control(_arm(-CONTROL_MEAN, CONTROL_SD, N_FOLDS), name="neg")
    assert v.status == "NOT_NULL"
    assert v.t_stat < -2.0


def test_too_few_observations_is_unproven_not_clean():
    v = assess_control([0.001, -0.002, 0.000, 0.001], name="thin")
    assert v.status == "UNPROVEN"
    assert not v.usable, "an untestable control must not be treated as clean"
    assert "not failed the null check" in v.reason


def test_no_controls_raises_rather_than_passing():
    with pytest.raises(ControlCalibrationError, match="no control arms"):
        gate_comparison({})


def test_empty_control_raises():
    with pytest.raises(ControlCalibrationError, match="no observations"):
        assess_control([], name="empty")


def test_single_observation_raises():
    with pytest.raises(ControlCalibrationError, match="at least 2"):
        assess_control([0.01], name="one")


def test_unanimous_zero_is_no_evidence_not_infinite_evidence():
    v = assess_control([0.0] * 40, name="flat")
    assert v.t_stat == 0.0
    assert v.status == "CLEAN"


def test_unanimous_nonzero_is_rejected():
    v = assess_control([0.05] * 40, name="constant")
    assert math.isinf(v.t_stat)
    assert v.status == "NOT_NULL"


def test_threshold_is_stricter_than_a_discovery_bar():
    """Rejecting a usable control is cheaper than trusting a broken one."""
    from renquant_model_common.control_calibration import DEFAULT_MAX_ABS_T
    assert DEFAULT_MAX_ABS_T < 1.96 + 0.5


def test_describe_names_the_status_and_the_numbers():
    d = assess_control(_arm(CONTROL_MEAN, CONTROL_SD, N_FOLDS),
                       name="shift120").describe()
    assert "shift120" in d and "NOT_NULL" in d and "t=" in d


def test_a_nan_observation_raises_rather_than_certifying_clean():
    """NaN made the old mean/var/t_stat chain NaN, and NaN fails every
    magnitude comparison — so |t| > max_abs_t was False and a broken control
    silently reached CLEAN. It must be rejected before the statistic exists."""
    vals = [0.001, -0.002, 0.0015, float("nan")] + [0.001] * 6
    with pytest.raises(ControlCalibrationError, match="non-finite"):
        assess_control(vals, name="nan-poisoned")


def test_a_positive_infinity_observation_raises():
    vals = [0.001] * 9 + [float("inf")]
    with pytest.raises(ControlCalibrationError, match="non-finite"):
        assess_control(vals, name="inf-poisoned")


def test_a_negative_infinity_observation_raises():
    vals = [0.001] * 9 + [float("-inf")]
    with pytest.raises(ControlCalibrationError, match="non-finite"):
        assess_control(vals, name="neg-inf-poisoned")


def test_gate_comparison_propagates_the_non_finite_rejection():
    with pytest.raises(ControlCalibrationError, match="non-finite"):
        gate_comparison({
            "shuffle": _arm(0.0013, 0.0095, 43, seed=5),
            "poisoned": [0.001] * 9 + [float("nan")],
        })
