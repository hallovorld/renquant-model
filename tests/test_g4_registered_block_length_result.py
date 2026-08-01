"""The registered run's verdict, pinned — including that it FAILED for Phase-0.

model#144 froze `b = 35` and the pass band `[0.04, 0.06]` before this number existed.
These tests hold the outcome so it cannot be softened later, and hold the harness control
so a "not calibrated" reading stays distinguishable from a broken tool.
"""

from __future__ import annotations

import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

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


def test_NO_geometry_is_licensed_once_MC_uncertainty_is_carried():
    """codex on model#145: a point estimate inside the band is not calibration.

    `L=20, gap=60` reads 0.0568 with SE ~0.0037 -- LESS THAN ONE standard error inside
    the bar, and its one-sided 95% upper bound (0.0628) exceeds 0.06. The prereg
    registered what to report when an estimate falls OUTSIDE the band; it registered no
    precision rule, so it cannot license a marginally-inside estimate.

    The same standard applies in the negative direction: `L=60, gap=60` (0.0635) is
    INCONCLUSIVE, not "not calibrated".
    """
    def bound(g):
        p = _size(g); se = math.sqrt(p * (1 - p) / RES["draws"])
        return p - 1.645 * se, p + 1.645 * se

    decisive_fail, inconclusive = [], []
    for g in ("L60_gap0", "L60_gap60", "L30_gap60", "L20_gap60"):
        lo, hi = bound(g)
        (decisive_fail if lo > BAND[1] else inconclusive).append(g)
    assert set(decisive_fail) == {"L60_gap0", "L30_gap60"}, decisive_fail
    assert set(inconclusive) == {"L60_gap60", "L20_gap60"}, inconclusive
    # and NOTHING is licensed: no geometry's upper bound sits inside the band
    licensed = [g for g in inconclusive if bound(g)[1] <= BAND[1]]
    assert licensed == [], licensed


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


def test_the_recorded_provenance_HASHES_MATCH_the_files_they_name():
    """codex on model#145 round 2: presence and length are not verification.

    The first version asserted `len(sha) == 64`, so an arbitrary 64-character string
    would have passed — an unverified annotation dressed as provenance, in the test
    written to make provenance evidence. This RECOMPUTES both digests from the files
    the artifact names and requires equality.

    It is deliberately brittle in one direction: editing the study tool without
    re-emitting the artifact fails here, because the recorded sizes would then have been
    produced by code that is no longer in the tree.
    """
    import hashlib

    pv = RES["provenance"]
    series = ROOT / pv["series_path"]
    assert series.is_file(), f"recorded series_path does not resolve: {pv['series_path']}"
    raw = series.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pv["series_sha256"], "series digest mismatch"
    assert len(raw) == pv["series_bytes"], "series byte count mismatch"

    tool = ROOT / "tools" / "g4_null_size_study.py"
    assert hashlib.sha256(tool.read_bytes()).hexdigest() == pv["tool_sha256"], (
        "the artifact was produced by a different revision of the study tool than the "
        "one in this tree — re-emit it")
    assert "code_revision" in pv and "code_revision_dirty" in pv


def test_the_document_states_the_verdict_and_its_limits():
    d = " ".join((pathlib.Path(__file__).resolve().parent.parent
                  / "doc/progress/2026-07-31-g4-registered-block-length-executed.md"
                  ).read_text(encoding="utf-8").split())
    assert "NOT CALIBRATED" in d
    assert "NO GEOMETRY IS LICENSED" in d
    assert "INCONCLUSIVE" in d
    assert "Does NOT settle" in d
