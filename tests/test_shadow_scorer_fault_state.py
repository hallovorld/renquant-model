"""GOAL-4/GOAL-1 — the shadow scorer marks `fault` and scores every candidate anyway."""

from __future__ import annotations

import json
import pathlib

BUNDLE = (pathlib.Path(__file__).resolve().parent.parent
          / "doc/research/data/2026-07-30-patchtst-closure-v2")
HEALTH = BUNDLE / "shadow_scorer_health_hf_patchtst.jsonl"


def _rows():
    return [json.loads(l) for l in HEALTH.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_every_live_health_record_is_a_fault():
    rows = _rows()
    assert len(rows) == 4
    assert all(r["status"] == "fault" for r in rows)
    assert all(r["reasons"] == [f"stale_{r['staleness_days']}d_limit_28d"] for r in rows)


def test_it_scored_every_candidate_despite_the_fault():
    """THE finding. The fault is advisory: nothing was skipped."""
    for r in _rows():
        assert r["n_scored"] == r["n_candidates"], r["run_date"]
        assert r["skip_reason"] is None, r["run_date"]


def test_the_staleness_is_22x_the_stated_limit():
    last = _rows()[-1]
    assert last["staleness_days"] == 623
    assert last["staleness_days"] / 28 > 22


def test_the_train_cutoff_predates_the_training_date_by_over_a_year():
    """Flagged, not explained: a 60-day embargo does not produce a gap this size."""
    import datetime as dt

    ev = json.loads((BUNDLE / "identity_evidence.json").read_text(encoding="utf-8"))
    cutoff = dt.date.fromisoformat(ev["effective_train_cutoff_date"])
    trained = dt.date.fromisoformat(ev["trained_date"])
    assert (trained - cutoff).days > 500
