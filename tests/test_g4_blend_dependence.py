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


def test_no_gap_honest_geometry_resolves():
    """The one row that DOES resolve is L=20, and it is the least trustworthy:
    crossing = min(1, h/L) = 1.00 at h=60, and it has the most blocks. Independence
    needs a GAP >= h, not a block shorter than h."""
    rows = [r for r in _rows() if r["series"] == "diff"]
    resolving = [r for r in rows if r["resolves"] == "True"]
    assert [r["block_length"] for r in resolving] == ["20"]
    assert resolving[0]["crossing_fraction"] == "1.0000"
    for r in rows:
        if r["block_length"] in ("60", "90", "120", "250"):
            assert r["resolves"] == "False", r
            assert abs(float(r["block_t"])) < 1.6, r


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
