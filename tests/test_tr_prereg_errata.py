"""The frozen TR prereg's "statement about the DATA" clause is narrowed by errata.

A frozen document is not edited: the registered text stays byte-identical and the
narrowing is appended, with pointers at the affected sites. These tests hold both
halves — that the errata exists, and that the registered claim was NOT rewritten.
"""

from __future__ import annotations

import pathlib

DOC = (pathlib.Path(__file__).resolve().parent.parent
       / "doc/research/2026-07-30-momentum-total-return-prereg.md").read_text(encoding="utf-8")
BODY, _, ERRATA = DOC.partition("# ERRATA 2026-07-31")


def test_the_registered_claim_is_still_there_unedited():
    """The point of an errata is that it does NOT rewrite history. If the original
    clause disappears, the frozen record has been altered."""
    assert "D1 is a statement about the DATA, not about momentum." in BODY
    assert "the dividend confound is REFUTED" in BODY


def test_the_affected_sites_carry_a_pointer():
    assert BODY.count("ERRATA-2026-07-31") >= 2


def test_the_errata_states_the_code_level_reason():
    assert ERRATA, "no errata block"
    assert 's["dividend"] > 0' in ERRATA
    assert "build_total_return_series.py:250" in ERRATA
    assert "cannot fail on a bad feed" in ERRATA


def test_the_errata_separates_what_stands_from_what_does_not():
    assert "**supported**" in ERRATA
    assert ERRATA.count("NOT established") >= 2


def test_the_verdict_is_explicitly_UNAFFECTED():
    """§6 never rested on the data claim; an errata that quietly widened its reach
    would be a second over-reach."""
    assert "Unaffected:" in ERRATA
    assert "UNRESOLVED / TILT-NOT-EXCLUDED" in ERRATA
