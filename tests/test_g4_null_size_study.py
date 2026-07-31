"""The size study's harness control and its non-identification, pinned.

The finding is that the realised size is NOT identified without a registered bootstrap
block-length rule. Two things must not drift silently: the harness must stay correct
(or a "miscalibration" reading is just a broken tool), and the spread must stay wide
enough that quoting a single cell remains wrong.
"""

from __future__ import annotations

import json
import pathlib

RES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "doc/research/evidence/2026-07-31-g4-null-calibration/size_study.json"
     ).read_text(encoding="utf-8"))


def test_the_harness_hits_nominal_on_an_iid_series():
    """Without this control, a high size reading would be indistinguishable from a bug."""
    for key, v in RES["harness_control_iid"].items():
        assert 0.04 <= v["size"] <= 0.065, (key, v)


def test_the_series_is_the_508_row_phase0_one():
    assert RES["n"] == 508
    assert abs(RES["mean"] + 0.008550) < 1e-5
    assert RES["acf"]["rho_1"] > 0.7, RES["acf"]


def test_phase0_geometry_has_crossing_one():
    """`L = h = 60`, `gap = 0` -> maximum label overlap; the defect, not the remedy."""
    cell = RES["size_by_geometry_and_boot_block"]["boot60_L60_gap0"]
    assert cell["crossing"] == 1.0
    assert cell["n_blocks"] == 8


def test_the_realised_size_is_NOT_identified_by_the_data_alone():
    """The load-bearing negative: the answer moves with an unregistered nuisance choice.

    If this ever becomes narrow, the finding is over and the document must be rewritten
    -- so it is asserted, not assumed.
    """
    S = RES["size_by_geometry_and_boot_block"]
    for geo in ("L60_gap0", "L20_gap60"):
        vals = [S[f"boot{b}_{geo}"]["size"] for b in (20, 40, 60, 90, 120)]
        assert max(vals) - min(vals) > 0.02, (geo, vals)


def test_gap_alone_does_not_uniformly_fix_the_size():
    """`gap >= h` is necessary, not sufficient — measured once more here."""
    S = RES["size_by_geometry_and_boot_block"]
    closer = sum(abs(S[f"boot{b}_L20_gap60"]["size"] - 0.05)
                 < abs(S[f"boot{b}_L60_gap0"]["size"] - 0.05) for b in (20, 40, 60, 90, 120))
    assert closer < 5, "gap-honest was uniformly closer — the claim would need rewriting"


def test_the_document_quotes_a_RANGE_not_a_single_size():
    doc = (pathlib.Path(__file__).resolve().parent.parent
           / "doc/progress/2026-07-31-g4-null-calibration-not-identified.md"
           ).read_text(encoding="utf-8")
    d = " ".join(doc.split())
    assert "0.049–0.078 at nominal 0.05" in d
    assert "cannot be met by" in d
    assert "No GOAL-4 verdict changes" in d
