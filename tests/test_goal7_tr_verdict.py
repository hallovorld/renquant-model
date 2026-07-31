"""GOAL-7 — the frozen rule returned "nothing licensed"; the evidence adjudicates nothing.

Two different things live in the published bundle and this module keeps them apart,
because codex on model#135 found the document reinstating one as the other:

  * **Rule outputs** -- deterministic gate booleans and the verdict string, produced by
    applying a decision rule that was frozen before the run. These are valid regardless
    of whether the statistics feeding them support inference. Pinning them is the point.
  * **Descriptive statistics** -- the block `t` values and the four TR-minus-price
    deltas. Every one of them sits on a `gap = 0` geometry with no calibrated null, so
    none is cleared and none is rejected.

The module title previously read "does NOT license a standalone momentum model", and a
test asserted `E2["t"] > 2.262` with the comment "it clears even the correct bar". The
first is fine as a rule outcome and misleading as a verdict; the second is withdrawn
outright -- `t(n-1)` is the correct bar only under i.i.d. Normal block means, and at
crossing 1.00 they are not.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "doc/research/data/2026-07-30-momentum-total-return"
                / "results.json").read_text(encoding="utf-8"))
DOC = (ROOT / "doc/progress/2026-07-31-goal7-tr-study-licenses-nothing.md"
       ).read_text(encoding="utf-8")


def _prose(text: str) -> str:
    """Markdown flattened for phrase matching: quote markers stripped, then whitespace.

    Prose wraps, and a wrapped blockquote continues each line with `> `, which lands
    mid-phrase once newlines collapse. Both have broken assertions in this batch.
    """
    return " ".join(re.sub(r"(?m)^\s*>\s?", "", text).split())


# --------------------------------------------------------------- rule outputs --
def test_the_frozen_rule_returned_nothing_licensed():
    """A RULE OUTCOME, not an evidential verdict.

    The rule was frozen before the run, the run produced its inputs, the rule was
    applied. That is a procedure, and it is valid whether or not the statistics it
    consumed can support inference -- which is what preregistration buys.
    """
    g = R["gates"]
    assert g["placebos_clean"] is True
    assert g["false_flag_rate_ok"] is True
    assert g["three_views_agree"] is True
    assert g["beats_baseline_holm"] is False
    assert R["verdict"].startswith("UNRESOLVED / TILT-NOT-EXCLUDED")


def test_resolves_is_recorded_as_SIGN_AGREEMENT_not_significance():
    """`resolves` never compares the block-t to a critical value (model#137).

    It requires the bootstrap CI, the LOBO bounds and the block-t to agree in SIGN. So
    "E2 resolves at t = 3.767" states sign agreement, not that 3.767 cleared anything --
    and the document must say so where it reports the pair.
    """
    assert R["primary"]["E2"]["resolves"] is True
    assert R["primary"]["E1"]["resolves"] is False
    d = _prose(DOC)
    assert "`resolves` is not significance" in d
    assert "agree in sign" in d


# ------------------------------------------------------ descriptive statistics --
def test_the_two_t_values_are_pinned_as_DESCRIPTIVE():
    """Pinned so the numbers cannot drift; labelled so they cannot be promoted."""
    assert abs(R["primary"]["E2"]["t"] - 3.767) < 0.01
    assert abs(R["primary"]["E1"]["t"] - 0.589) < 0.01
    d = _prose(DOC)
    assert "descriptive statistic on a geometry with no valid null" in d
    assert "neither cleared nor rejected" in d


def test_every_delta_is_negative_and_none_is_adjudicated():
    """The arithmetic is claimable; the causal reading is not.

    Every TR-minus-price delta is negative -- that is a fact about two runs. Whether
    removing the tilt CAUSED it is not established: nothing was randomised, and the
    four |t| sit at 1.74 / 1.35 / 0.97 / 0.79 on `gap = 0` geometry where no null is
    calibrated. No magnitude is compared to a threshold here, deliberately.
    """
    for h in ("20", "60", "120", "250"):
        d = R["D1"][h]
        assert d["tr"] < d["px"], h
        assert d["delta"]["mean"] < 0, h
    assert abs(R["D1"]["120"]["delta"]["mean"] + 0.01068) < 1e-4
    assert max(abs(R["D1"][h]["delta"]["t"]) for h in ("20", "60", "120", "250")) < 1.75


def test_the_strong_looking_t_sits_on_a_crossing_1_geometry():
    """`n_blocks = 10` at L = h = 120 ⇒ crossing = min(1, h/L) = 1.00, the MAXIMUM
    label overlap, with realised size measured at 0.1034 against a nominal 0.05.

    This test previously ended `assert E2["t"] > 2.262  # clears even the correct bar`.
    WITHDRAWN: `t(n-1)` is correct only under i.i.d. Normal block means, and 0.1034 at
    nominal 0.05 is the direct evidence they are not. The geometry is what gets pinned;
    no comparison to any bar is made.
    """
    assert R["n_blocks_primary"] == 10
    assert min(1.0, 120 / 120) == 1.0
    d = _prose(DOC)
    assert "0.1034" in d
    assert "maximum** label overlap" in d or "MAXIMUM label overlap" in d


# ------------------------------------------------------------------ regressions --
def test_the_withdrawn_CAUSAL_phrasings_do_not_come_back():
    """codex #135: the document reinstated these below the section that defers them.

    A later correction does not make an earlier contradictory claim safe -- a reader who
    stops at the first occurrence carries away the opposite. Each phrase may appear ONLY
    inside a sentence that marks it withdrawn.
    """
    d = _prose(DOC)
    for phrase in ("take the tilt away and the number goes",
                   "cannot outrun a dividend-yield sort"):
        for m in re.finditer(re.escape(phrase), d):
            window = d[max(0, m.start() - 260):m.start()]
            assert "withdrawn" in window.lower() or "earlier version" in window.lower(), phrase


def test_the_document_does_not_claim_the_model_is_UNSUPPORTED_BY_EVIDENCE():
    """"The rule declined to license" is not "the evidence is against it"."""
    d = _prose(DOC)
    assert "an inferential claim against the model" in d
    assert "The rule declined to license; that is not the same as evidence against" in d
    # Phrased to avoid inline emphasis: the source reads "status is *unmeasured*, which
    # is a different lane state from *negative*". Asserting across a `*` is the same
    # class of brittleness as asserting across a line wrap.
    assert "which is a different lane state from" in d
