"""Tests for the PIT input-parity ledger (v4 §2/§5 step 3, canonical store).

The prod-vs-shadow runs.alpaca.db bundle scan and the private
``select_asof_runs`` import are RETIRED; parity is now defined between the
two frozen arms (l1 / champion) of ONE canonical G4 evidence store,
consuming the step-1 contract + the step-2 byte-level watermark hook.
"""
from __future__ import annotations

import datetime as dt

from renquant_pipeline.decision_schedule import ARM_CHAMPION, ARM_L1, SessionWindow
from renquant_orchestrator.g4_shadow_job import (
    G4ArmSpec,
    G4EvidenceStore,
    build_arm_record,
    input_snapshot_bytes,
    max_event_time_from_bytes,
    run_g4_shadow_session,
)

from experiments.ensemble_phase0 import pit_parity_ledger as pit
from experiments.ensemble_phase0.pit_parity_ledger import (
    build_parity_ledger,
    compare_session_parity,
    write_parity_ledger,
)

CAL_ID = "XNYS/v1"
PS_ID = "alpaca_sip/v1"
SESSION = "2026-08-05"
NXT = "2026-08-06"


def _aware(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


def _window(session: str = SESSION, nxt: str = NXT) -> SessionWindow:
    return SessionWindow.from_iso(
        close=f"{session}T20:00:00+00:00",
        next_open=f"{nxt}T13:30:00+00:00",
        next_open_session=nxt,
    )


def _canonical_store(tmp_path, session=SESSION, nxt=NXT) -> G4EvidenceStore:
    store = G4EvidenceStore(tmp_path / "g4store")
    window = _window(session, nxt)
    inputs = {
        "universe": {"event_times": [_aware(f"{session}T19:00:00+00:00")],
                     "payload": ["AAPL", "MSFT"]},
        "prices": {"event_times": [_aware(f"{session}T19:30:00+00:00")],
                   "payload": {"AAPL": 1, "MSFT": 2}},
    }
    arms = [
        G4ArmSpec(arm=ARM_L1, artifact_digests={"l1": "sha256:" + "a" * 64},
                  config_digest="sha256:" + "c" * 64,
                  scores={"AAPL": 0.10, "MSFT": 0.20}, orders=[]),
        G4ArmSpec(arm=ARM_CHAMPION, artifact_digests={"champ": "sha256:" + "b" * 64},
                  config_digest="sha256:" + "c" * 64,
                  scores={"AAPL": 0.05, "MSFT": 0.15}, orders=[]),
    ]
    run_g4_shadow_session(store, decision_session=session, session_window=window,
                          inputs=inputs, arms=arms, calendar_id=CAL_ID,
                          price_source_id=PS_ID,
                          produced_at=_aware(f"{session}T21:00:00+00:00"))
    return store


def _manifest(store, event_iso, payload):
    data = input_snapshot_bytes("universe", event_times=[_aware(event_iso)], payload=payload)
    digest = store.store_input(data)
    return {"universe": {"digest": digest,
                         "max_event_time": max_event_time_from_bytes(data).isoformat()}}


def _write_arm(store, arm, manifest, *, session=SESSION, art="a",
               calendar_id=CAL_ID, price_source_id=PS_ID):
    rec = build_arm_record(
        G4ArmSpec(arm=arm, artifact_digests={arm: "sha256:" + art * 64},
                  config_digest="sha256:" + "c" * 64,
                  scores={"AAPL": 0.1}, orders=[]),
        decision_session=session, session_window=_window(session),
        input_manifest=manifest, calendar_id=calendar_id,
        price_source_id=price_source_id,
        produced_at=_aware(f"{session}T21:00:00+00:00"))
    store.write_record(rec)


class TestRetirement:
    def test_no_private_asof_or_db_scan(self):
        # The retired symbols/imports are not defined on the module (a
        # module-level import/binding would surface as an attribute).
        for name in ("select_asof_runs", "RunSelection", "AsOfExclusion",
                     "sqlite3", "compare_session"):
            assert not hasattr(pit, name), name
        assert "sqlite3" not in getattr(pit, "__dict__", {})


class TestParityVerdicts:
    def test_canonical_pair_is_parity(self, tmp_path):
        store = _canonical_store(tmp_path)
        v = compare_session_parity(store, SESSION, session_window=_window(),
                                   expected_calendar_id=CAL_ID,
                                   expected_price_source_id=PS_ID)
        assert v.verdict == "parity"
        assert not v.reasons

    def test_scorer_artifact_difference_stays_parity(self, tmp_path):
        # l1 and champion carry DIFFERENT artifact digests by design; the
        # shared input manifest still makes them parity.
        store = _canonical_store(tmp_path)
        v = compare_session_parity(store, SESSION, session_window=_window(),
                                   expected_calendar_id=CAL_ID,
                                   expected_price_source_id=PS_ID)
        assert v.verdict == "parity"
        assert v.informational["artifact_digests_equal"] is False

    def test_input_manifest_divergence_is_not_parity(self, tmp_path):
        store = G4EvidenceStore(tmp_path / "g4store")
        _write_arm(store, ARM_L1, _manifest(store, f"{SESSION}T19:00:00+00:00",
                                            ["AAPL", "MSFT"]), art="a")
        _write_arm(store, ARM_CHAMPION, _manifest(store, f"{SESSION}T19:00:00+00:00",
                                                 ["AAPL"]), art="b")  # different digest
        v = compare_session_parity(store, SESSION, session_window=_window(),
                                   expected_calendar_id=CAL_ID,
                                   expected_price_source_id=PS_ID)
        assert v.verdict == "not_parity"
        assert "input_manifest_divergence" in v.reasons

    def test_missing_arm_is_not_parity(self, tmp_path):
        store = G4EvidenceStore(tmp_path / "g4store")
        _write_arm(store, ARM_L1, _manifest(store, f"{SESSION}T19:00:00+00:00", ["AAPL"]))
        v = compare_session_parity(store, SESSION, session_window=_window(),
                                   expected_calendar_id=CAL_ID,
                                   expected_price_source_id=PS_ID)
        assert v.verdict == "not_parity"
        assert any("missing_qualifying_arm" in r for r in v.reasons)

    def test_missing_session_is_not_parity(self, tmp_path):
        store = G4EvidenceStore(tmp_path / "g4store")
        v = compare_session_parity(store, SESSION, session_window=_window())
        assert v.verdict == "not_parity"
        assert any("missing_session" in r for r in v.reasons)

    def test_frozen_id_mismatch_fails_contract(self, tmp_path):
        # Binding against a calendar id that differs from the records is a
        # contract-level frozen_identifier_mismatch -> not parity.
        store = _canonical_store(tmp_path)
        v = compare_session_parity(store, SESSION, session_window=_window(),
                                   expected_calendar_id="OTHER/v1",
                                   expected_price_source_id=PS_ID)
        assert v.verdict == "not_parity"
        assert any("frozen_identifier_mismatch" in r for r in v.reasons)

    def test_watermark_after_close_fails_contract(self, tmp_path):
        # A future input for this session breaks contract integrity.
        store = G4EvidenceStore(tmp_path / "g4store")
        m = _manifest(store, f"{SESSION}T22:00:00+00:00", ["AAPL"])  # after 20:00Z close
        _write_arm(store, ARM_L1, m, art="a")
        _write_arm(store, ARM_CHAMPION, m, art="b")
        v = compare_session_parity(store, SESSION, session_window=_window(),
                                   expected_calendar_id=CAL_ID,
                                   expected_price_source_id=PS_ID)
        assert v.verdict == "not_parity"
        assert any("watermark_after_close" in r for r in v.reasons)


class TestLedger:
    def test_build_and_write_ledger(self, tmp_path):
        store = _canonical_store(tmp_path)
        verdicts = build_parity_ledger(
            store, sessions=[SESSION], session_windows={SESSION: _window()},
            expected_calendar_id=CAL_ID, expected_price_source_id=PS_ID)
        assert len(verdicts) == 1 and verdicts[0].verdict == "parity"
        out = tmp_path / "out"
        path = write_parity_ledger(verdicts, out)
        assert path.exists()
        lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1
