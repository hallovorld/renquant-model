"""The registered run's verdict, pinned — including that it FAILED for Phase-0.

model#144 froze `b = 35` and the pass band `[0.04, 0.06]` before this number existed.
These tests hold the outcome so it cannot be softened later, and hold the harness control
so a "not calibrated" reading stays distinguishable from a broken tool.
"""

from __future__ import annotations

import json
import math
import pathlib

RES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "doc/research/evidence/2026-07-31-g4-null-calibration/size_study_b35.json"
     ).read_text(encoding="utf-8"))
S = RES["size_by_geometry_and_boot_block"]
BAND = (0.04, 0.06)


def _size(geo: str, b: int = 35) -> float:
    return S[f"boot{b}_{geo}"]["size"]


def test_the_registered_block_length_was_actually_run():
    assert any(k.startswith("boot35_") for k in S), "b=35 missing from the sweep"
    assert RES["draws"] == 4000 and RES["seed"] == 20260731


def test_phase0s_own_geometry_FAILS_the_registered_band():
    """The load-bearing negative. L = h = 60, gap = 0, crossing 1.00."""
    p = _size("L60_gap0")
    assert p > BAND[1], p
    se = math.sqrt(p * (1 - p) / RES["draws"])
    assert (p - BAND[1]) / se > 3, "should be decisive, not marginal"
    assert S["boot35_L60_gap0"]["crossing"] == 1.0


def test_exactly_one_geometry_is_inside_the_band():
    inside = [g for g in ("L60_gap0", "L60_gap60", "L30_gap60", "L20_gap60")
              if BAND[0] <= _size(g) <= BAND[1]]
    assert inside == ["L20_gap60"], inside


def test_the_harness_control_still_hits_nominal():
    """Without it, "not calibrated" is indistinguishable from a broken tool."""
    for k, v in RES["harness_control_iid"].items():
        assert 0.04 <= v["size"] <= 0.065, (k, v)


def test_the_band_is_still_reported_beside_the_registered_value():
    """§4 of the prereg: the registered cell never replaces the sensitivity band."""
    for b in (20, 40, 60, 90, 120):
        assert f"boot{b}_L60_gap0" in S, b
    vals = [_size("L60_gap0", b) for b in (20, 35, 40, 60, 90, 120)]
    assert max(vals) - min(vals) > 0.02, vals


def test_the_document_states_the_verdict_and_its_limits():
    d = " ".join((pathlib.Path(__file__).resolve().parent.parent
                  / "doc/progress/2026-07-31-g4-registered-block-length-executed.md"
                  ).read_text(encoding="utf-8").split())
    assert "NOT CALIBRATED" in d
    assert "no GOAL-4 member verdict may cite a block-`t` computed on it" in d
    assert "Does NOT settle" in d
