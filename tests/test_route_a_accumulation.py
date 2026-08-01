"""GOAL-7 §7.1 route (a): the accumulation rate and the staleness rate, pinned.

The finding is arithmetic on two measured rates, so the rates are what must not drift
silently. These read a committed SNAPSHOT, not the live log — the log is append-only and
re-reading it would let the numbers move under the conclusion.
"""

from __future__ import annotations

import json
import pathlib

SNAP = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "doc/research/evidence/2026-07-31-route-a/shadow_scorer_health_snapshot.json"
     ).read_text(encoding="utf-8"))
ADMITTED = "sha256:07046963994dbb8d"


def _scored_admitted():
    return [r for r in SNAP["rows"]
            if r.get("content_sha256") == ADMITTED and (r.get("n_scored") or 0) > 0]


def test_the_admitted_digest_scored_on_four_consecutive_dates():
    """v2 measured 2; today it is 4. Route (a) IS running."""
    rows = _scored_admitted()
    dates = sorted({r["run_date"] for r in rows})
    assert dates == ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30"], dates


def test_staleness_grows_exactly_one_day_per_scored_DATE():
    """The second rate, and the one that makes route (a) self-defeating.

    Deduped BY DATE: 2026-07-28 carries two scored rows (the job ran twice that day), so
    counting rows would report a step of 0 between them and hide the real 1-per-day
    slope. Five scored rows, four distinct dates.
    """
    by_date = {}
    for r in _scored_admitted():
        by_date.setdefault(r["run_date"], r["staleness_days"])
    stale = [by_date[d] for d in sorted(by_date)]
    assert len(_scored_admitted()) == 5, "row count changed"
    assert stale == [621, 622, 623, 624], stale
    assert all(b - a == 1 for a, b in zip(stale, stale[1:]))


def test_every_admitted_scored_row_is_DEGRADED_not_healthy():
    """The evidence is produced under a breach, not alongside one."""
    for r in _scored_admitted():
        assert r["state"] == "degraded", r
        assert any("stale_" in s for s in (r.get("reasons") or [])), r


def test_the_snapshot_pins_the_bytes_it_was_computed_from():
    """A live append-only surface needs a digest, or the finding is unre-checkable."""
    assert len(SNAP["source_sha256"]) == 64
    assert SNAP["n_rows"] == len(SNAP["rows"]) == 13
    assert SNAP["source_path"].endswith("shadow_scorer_health.jsonl")


def test_the_document_does_not_compute_a_closure_verdict():
    """§7.1 asked what would raise n_blocks — not for a verdict. Four dates is still
    n_blocks = 0, and inventing one here would be the fourth non-resolution dressed up."""
    doc = (pathlib.Path(__file__).resolve().parent.parent
           / "doc/progress/2026-07-31-route-a-measured.md").read_text(encoding="utf-8")
    d = " ".join(doc.split())
    assert "no verdict is computed here" in d
    assert "remains **UNRESOLVED (underpowered)**" in d


def test_the_document_names_the_checkpoint_as_the_SERVED_PRIMARY():
    """CORRECTED 2026-07-31: the first version framed a choice between "frozen research
    instrument" and "live shadow". Neither is true — the live config makes this
    checkpoint the PRIMARY scorer, and that is what removes route (a).

    Pinned because the correction is the finding: an arithmetic argument about a
    research artifact reads very differently once its subject is the model making live
    decisions.
    """
    doc = (pathlib.Path(__file__).resolve().parent.parent
           / "doc/progress/2026-07-31-route-a-measured.md").read_text(encoding="utf-8")
    d = " ".join(doc.split())
    assert "the SERVED PRIMARY" in d
    assert "route (a) is withdrawn on that ground" in d
    assert "deciding that the production primary is never retrained" in d
    # and the withdrawn either/or must not still read as a live choice
    assert "The arithmetic in this document stands unchanged" in d


def test_the_two_measured_rates_survive_the_correction():
    """The subject changed; the measurements did not. Both must still be asserted."""
    rows = _scored_admitted()
    assert len({r["run_date"] for r in rows}) == 4
    by_date = {}
    for r in rows:
        by_date.setdefault(r["run_date"], r["staleness_days"])
    assert [by_date[d] for d in sorted(by_date)] == [621, 622, 623, 624]
