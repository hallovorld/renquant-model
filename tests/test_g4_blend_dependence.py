"""GOAL-4 — why the blend construction screen is INCONCLUSIVE, measured.

The published bundle reports `diff_mean = +0.0627` on 2161 dates. A naive t on that
series is **+6.19**. Under any block bar with a gap-honest geometry it is **~1.5**,
and after winsorization **~0.95**. The published verdict was right; this pins WHY.

Read from a frozen summary, never recomputed from the bundle at test time: the point
is to hold the numbers that were reviewed.
"""

from __future__ import annotations

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = ROOT / "doc/research/evidence/2026-07-31-g4-blend-dependence"
SUM = json.loads((DIR / "summary.json").read_text(encoding="utf-8"))


def _rows():
    return list(csv.DictReader((DIR / "block_t_by_geometry.csv").open()))


def test_the_naive_t_is_inflated_by_serial_dependence():
    assert SUM["n_dates"] == 2161
    assert SUM["rho1_diff"] > 0.55                 # measured 0.5799
    assert SUM["naive_t_diff"] > 6.0               # measured 6.192


def test_NOT_ONE_geometry_here_is_gap_honest():
    """CORRECTED 2026-08-01, codex on #134. I described L=60..250 as "gap-honest".
    The frozen CSV records gap=0 on EVERY row and a NON-ZERO crossing on every row.
    Block length is not an embargo: adjacent blocks still share labels, so every
    Student bar in this table is uncalibrated and no row adjudicates anything."""
    for r in _rows():
        assert int(r["gap"]) == 0, r
        assert float(r["crossing_fraction"]) > 0.0, r


def test_the_block_t_values_are_recorded_as_a_DIAGNOSTIC_not_a_verdict():
    """What survives calibration-independently: the naive-to-block RATIO. It says the
    naive t counts overlapping-label dates as independent, not that the effect is
    absent."""
    rows = [r for r in _rows() if r["series"] == "diff"]
    at60 = next(r for r in rows if r["block_length"] == "60")
    assert abs(SUM["naive_t_diff"] / float(at60["block_t"]) - 4.2) < 0.2


def test_the_winsorized_arm_resolves_nowhere():
    rows = [r for r in _rows() if r["series"] == "winsorized_diff"]
    assert all(r["resolves"] == "False" for r in rows)
    assert max(abs(float(r["block_t"])) for r in rows) < 1.4


def test_the_advantage_is_overwhelmingly_TAIL_driven():
    """diff 0.06265 -> winsorized 0.00957. Winsorizing removes 84.7% of it."""
    assert SUM["tail_share_of_diff"] > 0.84
    # measured ratio is 0.1528, not "<0.15" -- the bound is set from the measurement,
    # not from a round number that happens to look tidier than the data.
    ratio = SUM["winsorized_diff_mean"] / SUM["diff_mean"]
    assert abs(ratio - 0.1528) < 5e-4, ratio


def test_the_two_arms_are_highly_correlated():
    """rho = 0.831 day to day. They are not independent views of the panel."""
    assert 0.82 < SUM["arm_correlation_blend_vs_rank60"] < 0.84


def test_the_published_verdict_is_upheld_not_overturned():
    """Honest direction: this CONFIRMS the bundle's own INCONCLUSIVE."""
    assert SUM["published_verdict"] == "INCONCLUSIVE"
