"""Pin the provenance of `genuine_ic = +0.00079` so the correction cannot rot.

The 2026-07-30 prereg cited `renquant-backtesting#83` for this number. The number is
real; that citation is not, and the SUBJECT was wrong too — it belongs to a retrain
CANDIDATE that fails the enforced leakage criterion, not to the deployed recipe.

These tests read the frozen evidence CSV rather than the live artifacts: the live tree
is a production surface and a test that reaches into it would both couple this suite to
an operator's disk and re-measure a moving target.
"""
from __future__ import annotations

import csv
import pathlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / ("doc/research/evidence/2026-07-31-genuine-ic-provenance/"
              "sanity_placebo_by_vintage.csv")


def _rows():
    with CSV.open() as fh:
        return list(csv.DictReader(fh))


def _f(r, k):
    return float(r[k])


def test_the_00079_row_is_a_CANDIDATE_and_it_FAILS():
    hit = [r for r in _rows() if abs(_f(r, "genuine_ic") - 0.00079) < 5e-6]
    assert len(hit) == 1, hit
    r = hit[0]
    assert r["deployed"] == "False"                    # NOT the production recipe
    assert r["enforced_placebo_pass"] == "False"       # and it fails the criterion
    assert "20260726T170001Z" in r["source_artifacts"]


def test_exactly_one_vintage_is_deployed_and_it_is_the_ONLY_one_that_passes():
    rows = _rows()
    deployed = [r for r in rows if r["deployed"] == "True"]
    passing = [r for r in rows if r["enforced_placebo_pass"] == "True"]
    assert len(deployed) == 1
    assert [r["train_end"] for r in passing] == [deployed[0]["train_end"]]
    assert abs(_f(deployed[0], "genuine_ic") - 0.04153) < 5e-6


def test_the_mde_vs_genuine_ic_comparison_is_NON_DECISIONAL():
    """Both 47x and 0.91x are withdrawn, and this test says why rather than pinning a
    replacement ratio.

    The first version asserted `0.0376 / 0.04153 == 0.91` and read it as "marginally
    powered". Neither side supports that:

      * the NUMERATOR is not a valid detection floor -- 0.0376 comes from model#129's
        calibration, which is itself unresolved (its null is a dependence-sensitivity
        diagnostic and its MDE is explicitly non-decisional). A ratio inherits the
        standing of its inputs.
      * the DENOMINATOR is the wrong estimand -- a deployed SINGLE-RECIPE genuine_ic
        is not an ENSEMBLE INCREMENT. The screen asks what combining members ADDS over
        the incumbent; one recipe's own IC is not that quantity, so the two are not
        commensurable whatever their ratio.

    Pinning 0.91 would have re-committed the original error -- pairing the MDE with
    whichever genuine_ic was to hand -- one number later. So this asserts the
    provenance fact the evidence DOES support, and that no power conclusion is drawn.
    """
    dep = next(r for r in _rows() if r["deployed"] == "True")
    assert abs(_f(dep, "genuine_ic") - 0.04153) < 5e-6, (
        "the provenance correction itself: the deployed recipe reads +0.04153, not "
        "the +0.00079 the prereg cited")

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "doc" / "research"
           / "2026-07-30-goal4-phase0-ensemble-gain-prereg.md").read_text()
    assert "Both 47× and 0.91× are withdrawn" in src
    assert "remains UNRESOLVED" in src or "remain UNRESOLVED" in src, (
        "the prereg must not carry a power conclusion from this comparison")


def test_the_collapse_is_placebo_RISING_not_real_ic_falling():
    """The candidates get better at ranking a SHUFFLED label. That is the signature
    the criterion exists to catch, and it is the opposite of 'alpha decayed'."""
    rows = sorted(_rows(), key=lambda r: r["train_end"])
    first, last = rows[0], rows[-1]
    assert _f(last, "placebo_ic") / _f(first, "placebo_ic") > 1.6      # +69%
    assert _f(last, "aligned_real_ic") / _f(first, "aligned_real_ic") > 0.7  # -22%
    # Two artifacts share train_end 2018-04-30, so a flat sort has an arbitrary
    # order inside that tie. Group by distinct train_end and require each group to
    # sit entirely below the previous one -- a STRONGER statement than a sorted
    # list, and one that does not quietly assume the ordering it is testing.
    groups: dict[str, list[float]] = {}
    for r in rows:
        groups.setdefault(r["train_end"], []).append(_f(r, "genuine_ic"))
    keys = sorted(groups)
    for a, b in zip(keys, keys[1:]):
        assert min(groups[a]) > max(groups[b]), (a, groups[a], b, groups[b])


def test_the_prereg_no_longer_sources_this_number_from_issue_83():
    src = (ROOT / "doc/research/"
           "2026-07-30-goal4-phase0-ensemble-gain-prereg.md").read_text(encoding="utf-8")
    assert "+0.04153" in src
    assert "WITHDRAWN 2026-07-31" in src
    # the old claim may be quoted, but never again as a live citation
    for line in src.splitlines():
        if "renquant-backtesting#83" in line:
            assert "was wrong in" in line or "previously written" in line, line
