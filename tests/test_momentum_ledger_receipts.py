"""Ledger-append receipts (orch#909 contract): the WRITER emits the evidence.

The scorer-identity monitor keys a ledger lane by the LEDGER FILE's byte
digest, so receipts carry the file digest straddling the append — not the
artifact's content sha. All tests run in tmp dirs; nothing touches RenQuant.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import momentum_train_run as run  # noqa: E402

from renquant_model_momentum.ledger import (  # noqa: E402
    LedgerIntegrityError, append_to_artifact_ledger)
from renquant_model_momentum.train import content_sha256_of  # noqa: E402


def _artifact(cutoff: str) -> dict:
    art = {
        "kind": "momentum_residual_v1_fast",
        "cutoff_date": cutoff,
        "params": {"params_version": "v1_fast"},
        "scores": {"AAPL": 0.5},
    }
    art["content_sha256"] = content_sha256_of(art)
    return art


def _append_with_receipt(receipts: Path, ledger: Path, art: dict) -> Path:
    before = run._sha256_of_file(ledger)
    row = append_to_artifact_ledger(art, ledger)
    return run.emit_ledger_append_receipt(receipts, ledger, before, art, row)


def test_genesis_receipt_omits_identity_before(tmp_path):
    ledger = tmp_path / "momentum_fast" / "ledger.jsonl"
    ledger.parent.mkdir()
    receipts = tmp_path / "receipts"
    out = _append_with_receipt(receipts, ledger, _artifact("2026-08-06"))

    payload = json.loads(out.read_text())
    assert "identity_before" not in payload  # absent, not null — genesis
    after = payload["identity_after"]["expected_content_sha256"]
    assert after == f"sha256:{hashlib.sha256(ledger.read_bytes()).hexdigest()}"
    assert payload["kind"] == "ledger_append"
    assert payload["append"]["row_index"] == 0
    # filename: date prefix + the ledger dir stem (collision-free across lanes)
    assert out.name.endswith("__momentum_fast.json")


def test_second_append_carries_the_prior_file_digest(tmp_path):
    ledger = tmp_path / "momentum" / "ledger.jsonl"
    ledger.parent.mkdir()
    receipts = tmp_path / "receipts"
    _append_with_receipt(receipts, ledger, _artifact("2026-08-06"))
    digest_between = hashlib.sha256(ledger.read_bytes()).hexdigest()
    out2 = _append_with_receipt(receipts, ledger, _artifact("2026-08-07"))

    p2 = json.loads(out2.read_text())
    assert p2["identity_before"]["expected_content_sha256"] == f"sha256:{digest_between}"
    assert p2["identity_after"]["expected_content_sha256"] != p2["identity_before"]["expected_content_sha256"]
    assert p2["append"]["row_index"] == 1


def test_failed_append_emits_no_receipt(tmp_path):
    ledger = tmp_path / "momentum" / "ledger.jsonl"
    ledger.parent.mkdir()
    receipts = tmp_path / "receipts"
    art = _artifact("2026-08-06")
    _append_with_receipt(receipts, ledger, art)
    n_before = len(list(receipts.iterdir()))
    with pytest.raises(LedgerIntegrityError):
        # duplicate cutoff+version refuses BEFORE any receipt logic runs
        _append_with_receipt(receipts, ledger, art)
    assert len(list(receipts.iterdir())) == n_before


def test_monitor_explains_the_boundary_from_this_receipt(tmp_path):
    """END-TO-END against the REAL consumer: the orchestrator monitor must mark
    a ledger-lane change explained by exactly this receipt, and must keep an
    unrelated lane CRITICAL. Skipped when the sibling checkout is absent."""
    sim = pytest.importorskip(
        "renquant_orchestrator.scorer_identity_monitor",
        reason="orchestrator sibling checkout not on path")
    from datetime import datetime

    ledger = tmp_path / "momentum_fast" / "ledger.jsonl"
    ledger.parent.mkdir()
    receipts = tmp_path / "receipts"
    _append_with_receipt(receipts, ledger, _artifact("2026-08-06"))
    d_genesis = hashlib.sha256(ledger.read_bytes()).hexdigest()
    _append_with_receipt(receipts, ledger, _artifact("2026-08-07"))
    d_after = hashlib.sha256(ledger.read_bytes()).hexdigest()

    lane = f"shadow:{ledger}"
    other = "shadow:other_model.pt"

    def _run(rid, day, led_sha, other_sha):
        return sim.RunIdentity(
            run_id=rid, run_date=day,
            created_at=datetime.fromisoformat(f"{day}T12:00:00"),
            lanes={lane: sim.LaneIdentity(lane=lane, artifact_sha=f"sha256:{led_sha}"),
                   other: sim.LaneIdentity(lane=other, artifact_sha=other_sha)},
            usable=True)

    prev = _run("r1", "2026-08-06", d_genesis, "sha256:" + "a" * 64)
    curr = _run("r2", "2026-08-09", d_after, "sha256:" + "b" * 64)  # other SWAPPED
    boundary = sim.Boundary(prev_run=prev, curr_run=curr,
                            changes=sim.diff_runs(prev, curr))
    events = sim.collect_promote_events(
        prod_artifacts_dir=tmp_path / "noprod",
        promote_log_dir=tmp_path / "nolog",
        shadow_receipt_dir=receipts)
    sim.explain_boundary(boundary, events)

    verdict = {c.lane: c.explained for c in boundary.changes}
    assert verdict[lane] is True      # the append is explained by our receipt
    assert verdict[other] is False    # the genuine swap STAYS unexplained
