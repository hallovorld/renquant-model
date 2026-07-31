"""The registered block-length rule is reproducible from the series, and unrun.

A prereg is only worth the paper if (a) the registered value can be recomputed from the
data by the stated rule, and (b) it was committed BEFORE the answer it gates was known.
(a) is testable here; (b) is testable as an absence — this branch must contain no size
result at b = 35.
"""

from __future__ import annotations

import csv
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = (ROOT / "doc/research/2026-07-31-goal4-bootstrap-block-length-prereg.md"
       ).read_text(encoding="utf-8")
SERIES = ROOT / "doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/per_date_g_real.csv"


def _acf(x: np.ndarray, max_lag: int) -> list[float]:
    c = x - x.mean()
    v = float((c * c).mean())
    return [float((c[:len(c) - k] * c[k:]).mean() / v) for k in range(max_lag + 1)]


def test_the_registered_block_length_is_recomputable_by_the_stated_rule():
    """b = first lag where the sample ACF crosses zero. One integer, no window."""
    g = np.array([float(r["g"]) for r in csv.DictReader(SERIES.open())])
    assert len(g) == 508
    rho = _acf(g, 120)
    first_zero = next(k for k in range(1, 121) if rho[k] <= 0)
    assert first_zero == 35, first_zero
    assert "`b = 35`" in DOC


def test_tau_int_really_is_window_dependent_which_is_why_it_was_rejected():
    """The rejection must rest on a measurement, not on a preference.

    If tau_int were stable across windows, the textbook rule would be the right choice
    and this prereg would need rewriting — so the instability is asserted, not assumed.
    """
    g = np.array([float(r["g"]) for r in csv.DictReader(SERIES.open())])
    rho = _acf(g, 120)
    taus = [1 + 2 * sum(rho[1:M + 1]) for M in (10, 20, 30, 40, 60)]
    assert max(taus) - min(taus) > 5, taus          # measured spread ~8.5
    assert "not identified on" in DOC


def test_the_prereg_discloses_that_the_sensitivity_table_was_already_seen():
    """The main threat to this document, on the record rather than omitted."""
    d = " ".join(DOC.split())
    assert "I have already seen the sensitivity table" in d
    assert "can be steered" in d


def test_the_answer_this_prereg_gates_is_NOT_in_this_branch():
    """Freeze-before-run, made mechanical.

    If a size at b = 35 appears here, the registration is retrospective and worthless.
    35 is deliberately not one of the five lengths model#143 measured.
    """
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix not in (".md", ".json", ".csv", ".py"):
            continue
        if path.name == "test_goal4_block_length_prereg.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "boot35" in text or "b = 35, size" in text or "size at b = 35 =" in text:
            raise AssertionError(f"a size at b=35 already exists in {path}")


def test_the_reporting_obligations_and_the_registered_threshold_are_stated():
    d = " ".join(DOC.split())
    assert "full sensitivity band" in d
    assert "[0.04, 0.06]" in d
    assert "NOT calibrated at this geometry" in d
