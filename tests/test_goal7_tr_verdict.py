"""GOAL-7 — the frozen total-return study does NOT license a standalone momentum model.

Pins the published bundle so the conclusion cannot drift, and pins the caveat on the
half of it that looks strong.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "doc/research/data/2026-07-30-momentum-total-return"
                / "results.json").read_text(encoding="utf-8"))


def test_the_arm_does_not_beat_its_own_dividend_yield_baseline():
    """THE verdict. Three gates pass and the fourth is the one that matters."""
    g = R["gates"]
    assert g["placebos_clean"] is True
    assert g["false_flag_rate_ok"] is True
    assert g["three_views_agree"] is True
    assert g["beats_baseline_holm"] is False        # <- nothing licensed
    assert R["verdict"].startswith("UNRESOLVED / TILT-NOT-EXCLUDED")


def test_the_two_views_disagree_about_whether_anything_resolved():
    """E2 (top-decile spread) resolves; E1 (rank IC) does not. A spread that moves
    while the rank correlation does not is a tail statement, not a panel statement."""
    assert R["primary"]["E2"]["resolves"] is True
    assert abs(R["primary"]["E2"]["t"] - 3.767) < 0.01
    assert R["primary"]["E1"]["resolves"] is False
    assert abs(R["primary"]["E1"]["t"] - 0.589) < 0.01


def test_the_deltas_are_negative_AND_none_of_them_resolves():
    """NARROWED after codex on #135. Every TR-minus-price delta is negative — and not
    one clears any bar (|t| <= 1.74), on gap=0 geometry. So "removing the tilt made
    momentum worse" is a CAUSAL reading these numbers do not support; what they show
    is that the TR series does not score higher than the price series here."""
    for h in ("20", "60", "120", "250"):
        d = R["D1"][h]
        assert d["tr"] < d["px"], h
        assert d["delta"]["mean"] < 0, h
    assert abs(R["D1"]["120"]["delta"]["mean"] + 0.01068) < 1e-4
    for h in ("20", "60", "120", "250"):
        assert abs(R["D1"][h]["delta"]["t"]) < 1.96, h        # none resolves


def test_the_strong_looking_t_sits_on_a_crossing_1_geometry():
    """`n_blocks = 10` at L = h = 120 means crossing = min(1, h/L) = 1.00 — the
    MAXIMUM label overlap. The realised size at that geometry was measured at 0.1034
    against a nominal 0.05, so 'clears the bar' is weaker than it reads. The per-date
    series was NOT persisted for this run, so it cannot be recalibrated from the
    bundle — which is precisely what model#131 exists to fix."""
    assert R["n_blocks_primary"] == 10
    assert min(1.0, 120 / 120) == 1.0
    # and with 10 blocks the Student bar is t(9) ~ 2.262, not 1.96
    assert R["primary"]["E2"]["t"] > 2.262          # it clears even the correct bar


def test_the_document_separates_the_RULE_OUTPUT_from_the_evidence():
    """codex #135: the deterministic gate field may be reported; the causal and
    evidential claims must be deferred."""
    doc = (ROOT / "doc/progress/2026-07-31-goal7-tr-study-licenses-nothing.md"
           ).read_text(encoding="utf-8")
    assert "rule output, not a verdict" in doc
    assert "NOT claimed: that the tilt was contributing" in doc
    assert "Deferred pending" in doc
