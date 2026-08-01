"""Which horizons could EVER have an identifiable bar here — and which verdicts are mine.

Measured 2026-08-01 on the pinned momentum matrix: h=120 pre-burn is SHORT at every draws
floor tested (10/20/30), so that verdict does not rest on my convention. h=60 pre-burn
flips — OK at 10, SHORT at 20 and 30 — and is therefore reported FLOOR_DEPENDENT rather
than as either answer. That third value is the point of the module.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import goal7_corpus_capacity as C  # noqa: E402

DATA = ROOT / "doc" / "research" / "data" / "2026-08-01-goal7-corpus-capacity"


@pytest.fixture(scope="module")
def rep():
    return json.loads((DATA / "capacity.json").read_text())


# --------------------------------------------------------------- the robust verdicts --
def test_h120_PRE_BURN_is_infeasible_at_EVERY_floor(rep):
    """The load-bearing result: it does not depend on my draws floor."""
    assert rep["robust_verdict"]["h120/pre_burn"] == "INFEASIBLE"
    rows = [r for r in rep["rows"] if r["horizon"] == 120 and r["scope"] == "pre_burn"]
    assert len(rows) == 3 and not any(r["feasible"] for r in rows)


def test_h120_is_not_rescued_by_discarding_the_burn_boundary(rep):
    """Even every admissible date to 2026-07-29 is short at the floor model#147 used."""
    r = next(r for r in rep["rows"]
             if r["horizon"] == 120 and r["scope"] == "whole_corpus"
             and r["draws_floor"] == 20)
    assert r["available"] == 2287 and r["needed"] == 2400 and r["feasible"] is False


def test_h60_pre_burn_is_reported_FLOOR_DEPENDENT_not_as_an_answer(rep):
    """A verdict that flips with my convention rests on me, not on the corpus. Reporting
    it as either 'feasible' or 'infeasible' would launder a choice into a finding."""
    assert rep["robust_verdict"]["h60/pre_burn"] == "FLOOR_DEPENDENT"
    v = [r["feasible"] for r in rep["rows"]
         if r["horizon"] == 60 and r["scope"] == "pre_burn"]
    assert any(v) and not all(v)


def test_h20_pre_burn_is_feasible_at_every_floor(rep):
    assert rep["robust_verdict"]["h20/pre_burn"] == "FEASIBLE"


def test_the_registered_1082_is_reproduced(rep):
    """The pre-burn h=120 count must equal the frozen run's N_eval, or the admissible
    rule here is not the one the study used."""
    r = next(r for r in rep["rows"]
             if r["horizon"] == 120 and r["scope"] == "pre_burn"
             and r["draws_floor"] == 20)
    assert r["available"] == 1082
    assert r["last_usable_t"] == "2021-04-19"


def test_the_corpus_and_admissible_spans_are_recorded(rep):
    assert rep["corpus_calendar_dates"] == 3161
    assert rep["admissible_dates"] == 2407
    assert rep["admissible_first"] == "2016-12-29"
    assert rep["min_names"] == 20 and rep["burn_boundary"] == "2021-10-08"


def test_the_matrix_is_bound_by_DIGEST(rep):
    assert rep["matrix_sha256"] == (
        "85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a")


# --------------------------------------------------- the distinction that must survive --
def test_the_report_says_CAPACITY_IS_NOT_POWER(rep):
    """h=20 clearing this is a statement about calibration only. GOAL-6 Stage 0 already
    measured that the shorter horizon buys no power; using this as an argument for a
    20-day design would substitute one instrument for another."""
    assert "CAPACITY IS NOT POWER" in rep["scope_note"]
    assert "no power" in rep["scope_note"] and "H2 NOT SUPPORTED" in rep["scope_note"]


def test_the_report_says_the_burn_boundary_is_NOT_LICENSED_to_be_lifted(rep):
    assert "BOUND the question" in rep["scope_note"]
    assert "do not" in rep["scope_note"] and "license" in rep["scope_note"]


# ----------------------------------------------------------------------- the calendar --
def test_last_usable_t_uses_the_CORPUS_trading_day_index_not_calendar_days():
    """A4.3 makes the corpus's own index the calendar of record; a calendar-day
    approximation would silently move the cutoff."""
    cal = pd.DatetimeIndex(pd.bdate_range("2020-01-01", periods=400))
    got = C.last_usable_t(cal, 10, pre_burn=False)
    assert got == cal[len(cal) - 11]


def test_a_horizon_longer_than_the_corpus_yields_NO_USABLE_DATE():
    cal = pd.DatetimeIndex(pd.bdate_range("2020-01-01", periods=5))
    assert C.last_usable_t(cal, 10, pre_burn=False) is None


def test_pre_burn_excludes_any_t_whose_window_CROSSES_the_boundary():
    cal = pd.DatetimeIndex(pd.bdate_range("2021-09-01", periods=60))
    last = C.last_usable_t(cal, 5, pre_burn=True)
    assert last is not None
    i = list(cal).index(last)
    assert cal[i + 5] < C.BURN
    assert i + 6 >= len(cal) or cal[i + 6] >= C.BURN


# ---------------------------------------------------------------------------
# Is the shortfall the CORPUS or my admissibility rule? 2026-08-01
# ---------------------------------------------------------------------------
def test_the_754_lost_dates_split_504_empty_and_250_warmup(rep):
    """#148's verdict only means anything if the shortfall is the data. Measured: it is."""
    L = rep["admissibility_loss"]
    assert L["n_inadmissible"] == 754
    assert L["corpus_has_under_min_names"]["n"] == 504
    assert L["feature_warmup"]["n"] == 250
    assert 504 + 250 == 754


def test_the_empty_stretch_is_2014_2015_and_recovers_NOTHING(rep):
    e = rep["admissibility_loss"]["corpus_has_under_min_names"]
    assert e["first"] == "2014-01-02" and e["last"] == "2015-12-31"


def test_the_warmup_gap_is_exactly_the_features_own_lookback(rep):
    """250 sessions between 'names exist' and 'the feature is computable' is one year,
    which is what mom_12_1 means. Tuning it away would be computing the feature from
    history it does not have."""
    w = rep["admissibility_loss"]["feature_warmup"]
    assert w["first"] == "2016-01-04" and w["last"] == "2016-12-28"
    assert w["sessions_between_first_20_names_and_first_admissible"] == 250
    assert "not a defect to be tuned away" in w["note"]


def test_the_NAME_FLOOR_is_falsified_as_a_suspect(rep):
    """The obvious third remedy — relax MIN_NAMES — recovers ZERO dates. Reported as a
    measurement rather than argued away."""
    by = rep["admissibility_loss"]["admissible_dates_by_name_floor"]
    assert set(by.values()) == {2407}
    assert rep["admissibility_loss"]["name_floor_is_not_binding"] is True


def test_the_conclusion_names_all_three_foreclosed_remedies(rep):
    c = rep["admissibility_loss"]["conclusion"]
    assert "Extending the window backwards recovers nothing" in c
    assert "the feature's own lookback" in c
    assert "ZERO dates" in c


# ---------------------------------------------------------------------------
# The draws-floor rationale, withdrawn 2026-08-01
# ---------------------------------------------------------------------------
def test_the_document_WITHDRAWS_the_estimator_stability_rationale():
    """`draws_floor = 20` was justified by "too few draws to estimate a tail". Measured:
    replication SD is 0.002-0.006 at EVERY draw count 5..90 and does not fall with more
    draws. The rationale is withdrawn; the h=120 verdict survives on floor-invariance
    instead, and this pins that the document says so."""
    import pathlib
    doc = (pathlib.Path(__file__).resolve().parent.parent / "doc" / "progress"
           / "2026-08-01-goal7-corpus-capacity.md").read_text()
    assert "is wrong**, and it is withdrawn" in doc
    assert "not independent knobs" in doc
    assert "INFEASIBLE at floors 10, 20 **and**\n30" in doc or "floors 10, 20" in doc


def test_the_h120_verdict_does_not_rest_on_the_floor(rep):
    """The load-bearing consequence: it is INFEASIBLE at every floor swept, so removing
    the floor's rationale does not touch it."""
    assert rep["robust_verdict"]["h120/pre_burn"] == "INFEASIBLE"
    assert set(rep["draws_floors_swept"]) == {10, 20, 30}


def test_the_TOOL_DOCSTRING_carries_the_qualified_claim_too():
    """`[codex on model#148]`: the progress doc was corrected while the tool docstring
    still said "cannot be rescued by data" — and that string is `--help` output, so a
    caller could still consume the withdrawn absolute as a design conclusion. One
    surface being right is not the claim being withdrawn."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent / "tools"
           / "goal7_corpus_capacity.py").read_text()
    assert "cannot be rescued by data" not in src
    assert "FLOOR_DEPENDENT" in src and "must not drive a design decision" in src
    assert "INFEASIBLE across all swept floors" in src
    # and the table cells must carry their floor rather than reading as absolutes
    assert "@floor 20" in src and "OK @floor 10" in src


def test_the_qualified_claim_SURVIVES_argparse_reflow():
    """codex asked for the PRINTED explanatory text, not just the source. argparse's
    default formatter collapses the docstring, so a phrase can be present in the file and
    broken across lines in `--help`. Checked on whitespace-normalised output."""
    import re
    import subprocess
    import sys
    tool = (pathlib.Path(__file__).resolve().parent.parent / "tools"
            / "goal7_corpus_capacity.py")
    out = subprocess.run([sys.executable, str(tool), "--help"],
                         capture_output=True, text=True).stdout
    flat = re.sub(r"\s+", " ", out)
    assert "cannot be rescued" not in flat
    for phrase in ("INFEASIBLE across all swept floors",
                   "must not drive a design decision",
                   "FLOOR_DEPENDENT"):
        assert phrase in flat, phrase


def test_the_document_does_NOT_claim_h120_is_unrescuable_by_data(rep):
    """`[codex on model#148]`: the sensitivity table says whole-corpus h=120 is
    FLOOR_DEPENDENT (clears at 10, short at 20/30), which contradicts an unconditional
    "cannot be rescued by data". The robust claim is the PRE-BURN one; the whole-corpus
    one is qualified. Pinned so the absolute wording cannot come back."""
    import pathlib
    doc = (pathlib.Path(__file__).resolve().parent.parent / "doc" / "progress"
           / "2026-08-01-goal7-corpus-capacity.md").read_text()
    assert "cannot be rescued by data.**" not in doc
    assert "The absolute wording is withdrawn" in doc
    assert "No design decision may consume the whole-corpus row" in doc
    # and the verdict the prose must match
    assert rep["robust_verdict"]["h120/pre_burn"] == "INFEASIBLE"
    assert rep["robust_verdict"]["h120/whole_corpus"] == "FLOOR_DEPENDENT"
