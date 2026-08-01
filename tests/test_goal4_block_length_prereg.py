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
import pytest

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


def test_the_prereg_COMMIT_PRECEDES_the_result_commit():
    """Freeze-before-run, proved from the commit graph rather than from an absence.

    The first version of this test asserted that no size at b = 35 existed anywhere in
    the branch. That was the right guard WHILE the prereg was unmerged: it is what made
    "registered before the answer" checkable. Once the prereg merged and the run
    executed, the guard fired -- correctly, and it had done its job.

    Replacing it with an absence check that permits the result would have been a
    weakening. Asserting the ORDER IN GIT is strictly stronger: it holds forever, it
    survives both files existing, and it cannot be satisfied by deleting evidence.
    """
    import subprocess

    def added_in(path: str) -> str | None:
        r = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--format=%H", "--diff-filter=A", "--", path],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return r.stdout.split()[-1]          # oldest = the adding commit

    prereg = added_in("doc/research/2026-07-31-goal4-bootstrap-block-length-prereg.md")
    result = added_in(
        "doc/research/evidence/2026-07-31-g4-null-calibration/size_study_b35.json")
    if prereg is None:
        pytest.skip("prereg commit not resolvable (shallow clone or git unavailable)")
    exec_doc = ROOT / "doc/progress/2026-07-31-g4-registered-block-length-executed.md"
    if result is None:
        # CORRECTED (codex on model#145): I claimed this guard "cannot be satisfied by
        # deleting evidence". FALSE — deleting the result made `added_in` return None
        # and the test returned successfully. Once the execution document exists, a
        # missing result artifact is a FAILURE, not a pass; only a genuinely unrun
        # prereg (no execution doc) may return clean.
        assert not exec_doc.exists(), (
            "the execution document exists but the result artifact it reports has no "
            "adding commit — evidence was deleted or never committed")
        return
    anc = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", prereg, result],
        capture_output=True, text=True, timeout=30)
    assert anc.returncode == 0, (
        f"the prereg commit {prereg[:9]} is NOT an ancestor of the result commit "
        f"{result[:9]} — the registration would be retrospective")


def test_the_reporting_obligations_and_the_registered_threshold_are_stated():
    d = " ".join(DOC.split())
    assert "full sensitivity band" in d
    assert "[0.04, 0.06]" in d
    assert "NOT calibrated at this geometry" in d
