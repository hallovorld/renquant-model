"""GOAL-4 — the registered members' measured status, pinned.

The decision doc's table is the load-bearing content. If any of these numbers moves,
the premise changes and the doc must be rewritten rather than quietly kept.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREREG = (ROOT / "doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md"
          ).read_text(encoding="utf-8")
DOC = (ROOT / "doc/design/2026-07-31-goal4-ensemble-premise-decision.md"
       ).read_text(encoding="utf-8")


def test_the_prereg_already_carries_the_small_n_caveat_on_patchtst():
    """Checked BEFORE claiming an inconsistency. The sibling closure prereg states
    |-2.31| < 2.3646; this one states it too, so there is nothing to propagate."""
    assert "−0.0556 (t = −2.31)" in PREREG
    assert "2.3646" in PREREG
    assert "n_eff = 8" in PREREG
    i = PREREG.index("−0.0556")
    assert "does **not** clear" in PREREG[i:i + 400]


def test_every_registered_member_is_recorded_as_not_clearing():
    for member in ("production XGB", "PatchTST", "certified clf"):
        assert member in DOC, member
    assert DOC.count("| **no**") == 3


def test_the_decision_rule_puts_member_viability_before_any_blend():
    assert "at least two" in DOC
    assert "No blend is fitted, screened or scored while zero members" in DOC


def test_the_redundancy_ceiling_is_stated_as_CONDITIONAL():
    """Anti-overreach: 1.045x was derived between two CONFIGURATIONS, not members."""
    assert "1.045" in DOC
    assert "conditional and must not be quoted flatly" in DOC
    assert "not between two ensemble *members*" in DOC


def test_it_does_not_claim_a_kill():
    assert "Not a KILL" in DOC
    assert "un-resolved**, not negative results" in DOC
