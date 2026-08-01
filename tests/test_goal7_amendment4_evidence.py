"""Amendment 4 evidence bindings (model#172 review round 1): the committed validation
JSON must be traceable to the vendored source and internally consistent — fast checks
only; the full re-derivation is `validate_gate_replacement.py --check` (minutes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "doc/research/data/2026-08-01-goal7-a4-validation"


def _out() -> dict:
    return json.loads((D / "validation_output.json").read_text())


def test_json_binds_to_the_vendored_inference_module():
    out = _out()
    ref_sha = hashlib.sha256((D / "goal7_momentum_inference_ref.py").read_bytes()).hexdigest()
    assert out["inference_ref_sha256"] == ref_sha


def test_fixture_recipe_reproduces_the_pinned_sha():
    import io
    import numpy as np
    rng = np.random.default_rng(20260801 + 7)
    buf = io.StringIO()
    buf.write("x\n")
    for v in rng.standard_normal(756):
        buf.write(f"{float(v)!r}\n")
    assert hashlib.sha256(buf.getvalue().encode()).hexdigest() == _out()["fixture_sha256"]


def test_verdict_rows_are_consistent_with_the_recorded_rates():
    out = _out()
    lo, hi = out["band"]
    c = out["correct_machine"]
    in_band = lambda r: lo <= r <= hi  # noqa: E731
    assert out["verdict"]["replacement_gate_passes_on_correct_machine"] == (
        in_band(c["overlap_ma"]["rate"]) and in_band(c["ar_resample"]["rate"]))
    neg = out["corrupted_machines"]
    assert out["verdict"]["replacement_gate_fails_on_A"] == (
        not (in_band(neg["A_wrong_quantile_0.90"]["overlap_ma"]["rate"])
             and in_band(neg["A_wrong_quantile_0.90"]["ar_resample"]["rate"])))
    assert out["verdict"]["replacement_gate_fails_on_C"] == (
        not in_band(neg["C_mirror_drift_L10_test_vs_L59_bar"]["ma_draws_tested_at_L10"]["rate"]))
    # the disclosed limitation: B is genuinely NOT caught, and the verdict says so
    assert out["verdict"]["replacement_gate_fails_on_B"] is False
    assert "NO TEETH" in out["verdict"]["limitation_B"]


def test_iid_reading_is_below_the_band_floor_as_the_amendment_claims():
    out = _out()
    assert out["correct_machine"]["iid_vs_t_star_diagnostic"]["rate"] < out["band"][0]
