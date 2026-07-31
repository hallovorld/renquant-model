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


def _prose(text: str) -> str:
    """Markdown prose, flattened for phrase matching.

    Two things break a naive `in` test on markdown. Prose WRAPS, so a phrase can
    straddle a newline; and a wrapped BLOCKQUOTE continues each line with `> `, which
    lands mid-phrase once the newlines collapse. Both bit me on the first run here --
    `dependence-preserving > null` -- and the wrap alone bit me twice more tonight.
    Strip the quote markers first, then collapse whitespace.
    """
    stripped = re.sub(r"(?m)^\s*>\s?", "", text)
    return " ".join(stripped.split())


def test_no_member_is_recorded_as_HAVING_BEEN_ADJUDICATED():
    """Codex on model#136: the table declared all three non-clearing on an UNCALIBRATED
    bar.

    `t(n-1)` is a reference, valid only under i.i.d. Normal block means. No null was
    ever calibrated for the block statistic here, and the supporting #134 geometry has
    `gap = 0` on every row. An instrument that cannot license "clears" cannot license
    "does not clear" either -- so the two threshold-based rows must read as
    un-adjudicated, not as negative findings.
    """
    for member in ("production XGB", "PatchTST", "certified clf"):
        assert member in DOC, member
    d = _prose(DOC)
    assert d.count("un-adjudicated") >= 2
    assert "gap = 0" in d
    # "correctly calibrated" may appear ONLY inside the caveat that withdraws it --
    # never in the table above. Bounding the region beats blacklisting the phrase:
    # the document has to be able to quote what it is retracting.
    caveat = d.index('WHY "un-adjudicated"')
    table = d[:caveat]
    assert "correctly calibrated" not in table, "the withdrawn claim is back in the table"
    assert "clears its bar?" not in table


def test_the_freeze_cannot_cite_an_uncalibrated_bar_AS_EVIDENCE():
    """The freeze must be a prior-discipline default, with a reachable release.

    A freeze justified by members "not clearing" an uncalibrated bar is unliftable by
    construction: no procedure exists to produce the "clears" that would release it.
    The document must therefore (a) rest the freeze on the unmeasured premise rather
    than on any t-statistic, and (b) name the condition that makes it evidential.
    """
    d = _prose(DOC)
    assert "prior-discipline" in d
    assert "unblocking condition" in d
    assert "dependence-preserving null" in d
    # codex #136 round 2: "bootstrap the series" is a PRECONDITION, not the procedure.
    # The four requirements must be named, or the release condition is another
    # unvalidated instrument standing in for a calibrated one.
    assert "overclaimed" in d
    assert "null-generating mechanism, stated in advance" in d
    assert "Paired dependence preserved" in d
    assert "empirical calibration target" in d
    assert "None of (1)–(4) has been done" in d
    assert "inputs awaiting an instrument, not findings" in d


def test_the_withdrawn_power_ratios_are_never_a_decision_basis():
    """Regression codex asked for: 47x and 0.91x must appear ONLY as withdrawn.

    Both were used as headlines before being withdrawn -- and the 0.91x was used as one
    in a document that had already named the category error. Naming a defect does not
    license using the thing that has it, so this pins the withdrawal rather than
    trusting the prose around it.
    """
    d = _prose(DOC)
    start = d.index("BOTH power ratios are WITHDRAWN")
    end = d.index("The one screen that showed a blend advantage")
    withdrawal = d[start:end]
    # EVERY occurrence of either ratio must fall inside the withdrawal paragraph.
    # Stronger than blacklisting phrases, and it survives rewording: if a ratio ever
    # reappears in a bottom line, a table or a decision rule, this fails.
    for ratio in ("47\u00d7", "0.91\u00d7"):
        assert ratio in withdrawal, ratio
        assert d.count(ratio) == withdrawal.count(ratio), (
            f"{ratio} appears outside the withdrawal paragraph")
    assert "GOAL-4's power is unmeasured" in d
    assert "it is not 47\u00d7-short and it is not marginal" in d


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
