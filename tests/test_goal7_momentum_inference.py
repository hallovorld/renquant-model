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
    lo = M.machinery_self_check(
        rng_series, {"bars": {"overlap_ma": 0.0, "ar_resample": 0.0}},
        cfg=M.FROZEN_INFERENCE, reps=100)
    hi = M.machinery_self_check(
        rng_series, {"bars": {"overlap_ma": 99.0, "ar_resample": 99.0}},
        cfg=M.FROZEN_INFERENCE, reps=100)
    for member in ("overlap_ma", "ar_resample"):
        assert lo[member]["rate"] == 1.0 and not lo[member]["ok"]
        assert hi[member]["rate"] == 0.0 and not hi[member]["ok"]
    assert not lo["ok"] and not hi["ok"]


def test_machinery_self_check_covers_both_members_and_ok_is_the_conjunction():
    """One absurd bar + one plausible bar -> the per-member verdicts differ and the
    top-level ok is their AND (a single-member check could not fail this way)."""
    rng_series = M.gen_overlap_ma(np.random.default_rng(17), 300, 20, 1.0)
    mixed = M.machinery_self_check(
        rng_series, {"bars": {"overlap_ma": 0.0, "ar_resample": 99.0}},
        cfg=M.FROZEN_INFERENCE, reps=80)
    assert not mixed["overlap_ma"]["ok"] and not mixed["ar_resample"]["ok"]
    assert mixed["overlap_ma"]["rate"] == 1.0 and mixed["ar_resample"]["rate"] == 0.0
    assert mixed["ok"] is False


def test_calibrate_bar_bootstrap_adequacy_failure_serializes_instead_of_crashing(monkeypatch):
    """The exact path codex flagged: an adequacy FAILURE under the Amendment-2
    bootstrap rule must produce the UNRESOLVED-METHOD report — the earlier message
    interpolated worst_lag/envelope_at_worst, which that rule does not emit, and
    crashed (KeyError) on the very path it had to report."""
    monkeypatch.setattr(M, "adequacy_check", lambda *a, **k: {
        "ok": False, "rule": "bootstrap_max", "max_abs_dev": 0.31,
        "bootstrap_threshold": 0.12, "boot_reps": 500, "alpha": 0.05})
    v = M.gen_ar_resample(np.random.default_rng(9), 400,
                          np.array([0.4]), np.random.default_rng(10).standard_normal(300))
    cfg = dict(M.FROZEN_INFERENCE)
    cfg["reps"] = 60
    cfg["envelope_rule"] = "bootstrap_max"
    cal = M.calibrate_bar(v, cfg)
    assert cal["status"] == "UNRESOLVED-METHOD"
    assert "bootstrap threshold" in cal["why"] and "0.1200" in cal["why"]
    assert "NO collapse" in cal["why"]


def test_calibrate_bar_frozen2se_failure_message_still_carries_worst_lag(monkeypatch):
    monkeypatch.setattr(M, "adequacy_check", lambda *a, **k: {
        "ok": False, "rule": "frozen_2se", "max_abs_dev": 0.2,
        "worst_lag": 7, "envelope_at_worst": 0.05})
    v = M.gen_ar_resample(np.random.default_rng(11), 400,
                          np.array([0.4]), np.random.default_rng(12).standard_normal(300))
    cfg = dict(M.FROZEN_INFERENCE)
    cfg["reps"] = 60
    cal = M.calibrate_bar(v, cfg)
    assert cal["status"] == "UNRESOLVED-METHOD" and "worst lag 7" in cal["why"]


def test_positive_control_is_a_rate_gate_with_pinned_fixture_semantics():
    """Small-rep smoke of the §4.4 gate-1 shape: per-member own-bar rates, a binding
    member, the published iid diagnostic, and ok = the members' conjunction."""
    rng = np.random.default_rng(20260801 + 7)
    noise = rng.standard_normal(300)
    cfg = dict(M.FROZEN_INFERENCE)
    cfg["reps"] = 80
    cfg["envelope_rule"] = "bootstrap_max"
    cfg["adequacy_boot_reps"] = 60
    pc = M.positive_control(noise, cfg)
    if "per_member" not in pc:            # control's own AR fit failed adequacy at
        assert pc["ok"] is False          # this tiny rep count — the honest outcome
        assert "calibration" in pc
        return
    assert set(pc["per_member"]["overlap_ma"]) >= {"rate", "hits", "reps", "bar", "ok"}
    assert pc["binding_member"] in ("overlap_ma", "ar_resample")
    assert pc["rate"] == pc["per_member"][pc["binding_member"]]["rate"]
    assert pc["iid_vs_t_star"]["note"].startswith("diagnostic only")
    assert pc["ok"] == pc["per_member"]["ok"]


def test_positive_control_fixture_is_pinned_and_reads_back_exactly():
    """The committed fixture's content sha equals the FROZEN_INFERENCE pin, and the
    round_trip reader reproduces the generating draw exactly (pandas' default C
    parser is lossy — 230/756 values drift in the last bits without it)."""
    import hashlib
    import pandas as pd
    p = Path(__file__).parent.parent / "tools/data/goal7_positive_control_noise.csv"
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha == M.FROZEN_INFERENCE["positive_control_sha256"]
    got = pd.read_csv(p, float_precision="round_trip")["x"].to_numpy()
    want = np.random.default_rng(20260801 + 7).standard_normal(756)
    assert np.array_equal(got, want)


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
