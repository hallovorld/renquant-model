"""Every block count and critical value in the GOAL-7 redesign must re-derive.

The first version of that document carried two `t` bars taken from `N / h` used as a
degrees-of-freedom count, and review rejected both. The repair is only durable if the
replacement numbers are *computed* rather than transcribed — the recurring failure on
this programme is a load-bearing constant that was asserted in prose and never
re-derived at the realised geometry.

So this test recomputes the §3.1 table from `N = 1082` and asserts the document says
what the arithmetic says. It reads the markdown deliberately: a helper that agreed
with itself but not with the published table would validate the wrong object.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from scipy import stats

DOC = (Path(__file__).resolve().parent.parent / "doc" / "design"
       / "2026-07-30-goal7-stage1-redesign.md")

#: The uncontaminated window, in trading days. Stated in §2 of the document.
N_DATES = 1082
LABEL_H_LONG = 120
LABEL_H_SHORT = 20


def _text() -> str:
    # Thousands separators are typeset with spaces in the prose ("1 082"); strip
    # them so a digit match is about the number, not its formatting.
    return re.sub(r"(?<=\d)[\s  ](?=\d)", "", DOC.read_text())


def _blocks(L: int, gap: int) -> tuple[int, int]:
    unit = L + gap
    n = N_DATES // unit
    return n, N_DATES - n * unit


@pytest.mark.parametrize("L,gap,h,blocks,dropped", [
    (120, 120, LABEL_H_LONG, 4, 122),    # A
    (60, 20, LABEL_H_SHORT, 13, 42),     # C-prime
    (40, 20, LABEL_H_SHORT, 18, 2),      # C-double-prime
])
def test_each_gapped_design_is_dependence_valid_and_counts_as_published(
        L, gap, h, blocks, dropped):
    assert gap >= h, "a gap below the label horizon leaves blocks overlapping"
    assert _blocks(L, gap) == (blocks, dropped)
    assert str(blocks) in _text()
    assert f"{dropped}d" in _text()


@pytest.mark.parametrize("blocks,bar", [(4, "3.1824"), (13, "2.1788"), (18, "2.1098")])
def test_the_published_student_bars_are_the_realised_df(blocks, bar):
    assert f"{stats.t.ppf(0.975, blocks - 1):.4f}" == bar
    assert bar in _text()


def test_the_rejected_contiguous_design_is_recorded_as_invalid():
    """`h=20` in contiguous 60-day blocks crosses by one third. The document must
    keep saying so — deleting the rejected row would lose the reason."""
    assert f"{LABEL_H_SHORT / 60:.4f}" == "0.3333"
    t = _text()
    assert "0.3333" in t
    assert "2.3060" in t, "row B's rejected bar must stay on the record"


def test_the_power_heuristic_is_not_presented_as_degrees_of_freedom():
    """`N/h` may appear — it is a legitimate power heuristic — but the document must
    say in the same breath that it is not a df, or the original error is still live."""
    t = _text()
    assert f"{N_DATES / LABEL_H_LONG:.2f}" == "9.02"
    assert "9.02" in t
    assert "not a degrees-of-freedom count" in t or "not a `df`" in t


def test_option_B_carries_no_student_bar_at_all():
    """HAC's reference distribution comes from permutation. If a Student bar ever
    reappears on the B row, the rejected inference is back."""
    row = next(l for l in DOC.read_text().splitlines()
               if l.startswith("| **B**"))
    assert "No Student bar" in row
    assert not re.search(r"t\(\.975", row), row
