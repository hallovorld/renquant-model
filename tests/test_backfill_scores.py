"""Tests for the G4 forward series consumer (v4 §5 step 3).

The score "backfill" is RETIRED: there is no runs.alpaca.db scan and no
private as-of helper. These tests are the v4 §6 adversarial acceptance
set for the forward consumer:

* a pre-freeze / pre-activation session is REFUSED from the inferential
  series (data hygiene, v4 §4);
* a non-canonical-store record is REFUSED (integrity);
* a forward canonical, registration-bound, post-activation session is
  enrolled with series_eligible;
* job-identity determinism;
* no leakage — a record whose inputs postdate the session close (a future
  model/input for a past date) is REFUSED.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from renquant_pipeline.decision_schedule import (
    ARM_CHAMPION,
    ARM_L1,
    EXPECTED_ARMS,
    SessionWindow,
    job_identity,
)
from renquant_orchestrator.g4_shadow_job import (
    G4ArmSpec,
    G4EvidenceStore,
    build_arm_record,
    input_snapshot_bytes,
    max_event_time_from_bytes,
    run_g4_shadow_session,
)

from experiments.ensemble_phase0 import backfill_scores as bf
from experiments.ensemble_phase0.backfill_scores import (
    DIAGNOSTIC_ONLY,
    INFERENTIAL_SERIES_CANDIDATE,
    REASON_PRE_ACTIVATION,
    REASON_REGISTRATION_UNBOUND,
    REFUSED,
    SeriesIntegrityError,
    assemble_inferential_series,
    evaluate_forward_session,
    main,
)

CAL_ID = "XNYS/v1"
PS_ID = "alpaca_sip/v1"


def _aware(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


class _FakeBounds:
    def __init__(self, open_: dt.datetime, close: dt.datetime) -> None:
        self.open = open_
        self.close = close


class _FakeCalendar:
    """Deterministic session calendar — the same fake-calendar approach the
    orchestrator's own step-2 tests use, so parity/consumer tests need no
    pandas_market_calendars."""

    name = "FAKE"

    #: consecutive sessions, close 20:00Z, next open 13:30Z.
    SESSIONS = [f"2026-08-{d:02d}" for d in range(3, 11)]

    def session_bounds(self, day: dt.date):
        iso = day.isoformat()
        if iso not in self.SESSIONS:
            return None
        return _FakeBounds(
            open_=_aware(f"{iso}T13:30:00+00:00"),
            close=_aware(f"{iso}T20:00:00+00:00"),
        )


def _window(session: str, next_session: str) -> SessionWindow:
    return SessionWindow.from_iso(
        close=f"{session}T20:00:00+00:00",
        next_open=f"{next_session}T13:30:00+00:00",
        next_open_session=next_session,
    )


def _canonical_store(tmp_path, session: str, next_session: str) -> tuple[G4EvidenceStore, SessionWindow]:
    """Build a genuine canonical store for one session via the canonical
    job (both frozen arms, one shared manifested input set)."""
    store = G4EvidenceStore(tmp_path / "g4store")
    window = _window(session, next_session)
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
    run_g4_shadow_session(
        store, decision_session=session, session_window=window, inputs=inputs,
        arms=arms, calendar_id=CAL_ID, price_source_id=PS_ID,
        produced_at=_aware(f"{session}T21:00:00+00:00"),
    )
    return store, window


# ─────────────────────────────────────────────────────────────────────────
# Retirement of the backfill/inferential role
# ─────────────────────────────────────────────────────────────────────────


class TestRetirement:
    def test_private_asof_helper_and_db_scan_are_gone(self):
        # v4 §5: no private cross-repo as-of helper survives anywhere.
        assert not hasattr(bf, "select_asof_runs")
        assert not hasattr(bf, "RunSelection")
        assert not hasattr(bf, "AsOfExclusion")
        assert not hasattr(bf, "extract_daily_scores")
        assert not hasattr(bf, "run_backfill")

    def test_module_never_imports_a_database(self):
        # Structurally incapable of a runs.alpaca.db enrollment path: the
        # module imports no sqlite driver at all (a module-level ``import
        # sqlite3`` would surface as an attribute).
        assert not hasattr(bf, "sqlite3")
        assert "sqlite3" not in getattr(bf, "__dict__", {})


# ─────────────────────────────────────────────────────────────────────────
# Forward canonical session → series_eligible (v4 §6)
# ─────────────────────────────────────────────────────────────────────────


class TestForwardCanonicalSeriesEligible:
    def test_registration_bound_post_activation_is_enrolled(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05",
            activation_session="2026-08-04",  # strictly before the session
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        assert outcome.admissible is True
        assert outcome.admission_series_eligible is True
        assert outcome.post_activation is True
        assert outcome.inferential_role is True
        assert outcome.classification == INFERENTIAL_SERIES_CANDIDATE
        assert outcome.model_refusals == []

    def test_calendar_resolves_window_when_not_supplied(self, tmp_path):
        store, _ = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05", activation_session="2026-08-04",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            calendar=_FakeCalendar(),  # window resolved from the calendar
        )
        assert outcome.classification == INFERENTIAL_SERIES_CANDIDATE


# ─────────────────────────────────────────────────────────────────────────
# Pre-freeze / pre-activation refusal (v4 §4 data hygiene)
# ─────────────────────────────────────────────────────────────────────────


class TestPreActivationRefused:
    def test_pre_activation_session_is_diagnostic_only_not_enrolled(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-03", "2026-08-04")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-03",
            activation_session="2026-08-04",  # session is BEFORE activation
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        # A perfectly clean canonical observation, yet structurally barred.
        assert outcome.admissible is True
        assert outcome.admission_series_eligible is True  # admission alone would allow it
        assert outcome.post_activation is False
        assert outcome.inferential_role is False  # the model-side gate excludes it
        assert outcome.classification == DIAGNOSTIC_ONLY
        assert REASON_PRE_ACTIVATION in outcome.model_refusals

    def test_equal_to_activation_is_not_post_activation(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05",
            activation_session="2026-08-05",  # STRICTLY after is required
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        assert outcome.inferential_role is False
        assert outcome.classification == DIAGNOSTIC_ONLY

    def test_no_activation_registered_nothing_enrollable(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05",
            activation_session=None,  # current reality: nothing registered
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        assert outcome.inferential_role is False
        assert outcome.classification == DIAGNOSTIC_ONLY
        assert bf.REASON_NO_ACTIVATION_REGISTERED in outcome.model_refusals


# ─────────────────────────────────────────────────────────────────────────
# Unregistered (no frozen ids) → not series_eligible
# ─────────────────────────────────────────────────────────────────────────


class TestRegistrationUnbound:
    def test_missing_frozen_ids_is_not_series_eligible(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05", activation_session="2026-08-04",
            frozen_calendar_id=None, frozen_price_source_id=None,  # unbound
            session_window=window,
        )
        assert outcome.admissible is True
        assert outcome.registration_bound is False
        assert outcome.admission_series_eligible is False
        assert outcome.inferential_role is False
        assert outcome.classification == DIAGNOSTIC_ONLY
        assert REASON_REGISTRATION_UNBOUND in outcome.model_refusals


# ─────────────────────────────────────────────────────────────────────────
# Non-canonical / missing records → REFUSED (integrity)
# ─────────────────────────────────────────────────────────────────────────


class TestNonCanonicalRefused:
    def test_forged_record_is_refused(self, tmp_path):
        store = G4EvidenceStore(tmp_path / "g4store")
        session, nxt = "2026-08-05", "2026-08-06"
        window = _window(session, nxt)
        # A record that never went through the canonical write path: a
        # forged job_id + a manifest digest the store cannot resolve.
        forged = {
            "schema_version": 1, "execution_mode": "shadow", "arm": ARM_L1,
            "decision_session": session,
            "declared_input_watermark": f"{session}T19:00:00+00:00",
            "input_manifest": {"universe": {"digest": "sha256:" + "0" * 64,
                                            "max_event_time": f"{session}T19:00:00+00:00"}},
            "artifact_digests": {"x": "sha256:" + "1" * 64},
            "config_digest": "sha256:" + "2" * 64,
            "calendar_id": CAL_ID, "price_source_id": PS_ID,
            "scores": {"AAPL": 0.1}, "orders": [], "orders_scheduled_for": nxt,
            "run_bundle_timestamp": f"{session}T21:00:00+00:00",
            "job_id": "sha256:" + "9" * 64,          # forged
            "decision_digest": "sha256:" + "8" * 64,  # forged
        }
        records_dir = store.records_dir(session)
        records_dir.mkdir(parents=True, exist_ok=True)
        (records_dir / "forged.json").write_text(json.dumps(forged), encoding="utf-8")

        outcome = evaluate_forward_session(
            store, decision_session=session, activation_session="2026-08-04",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        assert outcome.admissible is False
        assert outcome.inferential_role is False
        assert outcome.classification == REFUSED

    def test_missing_session_is_refused(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-06",  # no records for this session
            activation_session="2026-08-04",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=_window("2026-08-06", "2026-08-07"),
        )
        assert outcome.admissible is False
        assert outcome.classification == REFUSED
        assert "missing_session" in outcome.admission_reason_codes


# ─────────────────────────────────────────────────────────────────────────
# Job-identity determinism (v4 §6)
# ─────────────────────────────────────────────────────────────────────────


class TestJobIdentityDeterminism:
    def test_record_job_id_matches_deterministic_identity(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        loaded = dict(
            (rec["arm"], rec) for _p, rec in store.load_session_records("2026-08-05")
        )
        for arm in EXPECTED_ARMS:
            rec = loaded[arm]
            assert rec["job_id"] == job_identity(
                arm=arm, decision_session="2026-08-05",
                artifact_digests=rec["artifact_digests"],
                config_digest=rec["config_digest"],
            )

    def test_re_evaluation_is_stable(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        kw = dict(decision_session="2026-08-05", activation_session="2026-08-04",
                  frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
                  session_window=window)
        a = evaluate_forward_session(store, **kw)
        b = evaluate_forward_session(store, **kw)
        assert a.classification == b.classification == INFERENTIAL_SERIES_CANDIDATE
        assert a.admission["arm_verdicts"] == b.admission["arm_verdicts"]


# ─────────────────────────────────────────────────────────────────────────
# No leakage — future inputs for a past date are REFUSED (v4 §6)
# ─────────────────────────────────────────────────────────────────────────


class TestNoLeakage:
    def _leaky_store(self, tmp_path, session, nxt, event_iso):
        """Both arms built from an input whose event-time is ``event_iso``;
        pass an after-close ``event_iso`` to forge look-ahead."""
        store = G4EvidenceStore(tmp_path / "g4store")
        window = _window(session, nxt)
        data = input_snapshot_bytes("universe", event_times=[_aware(event_iso)],
                                    payload=["AAPL"])
        digest = store.store_input(data)
        mx = max_event_time_from_bytes(data)
        manifest = {"universe": {"digest": digest, "max_event_time": mx.isoformat()}}
        for arm, art in ((ARM_L1, "a"), (ARM_CHAMPION, "b")):
            rec = build_arm_record(
                G4ArmSpec(arm=arm, artifact_digests={arm: "sha256:" + art * 64},
                          config_digest="sha256:" + "c" * 64,
                          scores={"AAPL": 0.1}, orders=[]),
                decision_session=session, session_window=window,
                input_manifest=manifest, calendar_id=CAL_ID, price_source_id=PS_ID,
                produced_at=_aware(f"{session}T21:00:00+00:00"),
            )
            store.write_record(rec)
        return store, window

    def test_input_after_close_is_refused(self, tmp_path):
        # event-time 22:00Z is AFTER the 20:00Z close -> a future input for
        # this decision session -> watermark_after_close -> REFUSED.
        store, window = self._leaky_store(
            tmp_path, "2026-08-05", "2026-08-06", "2026-08-05T22:00:00+00:00")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05", activation_session="2026-08-04",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        assert outcome.admissible is False
        assert outcome.inferential_role is False
        assert outcome.classification == REFUSED
        assert "watermark_after_close" in outcome.admission_reason_codes

    def test_input_before_close_is_clean(self, tmp_path):
        # same construction, but a 19:00Z (pre-close) event-time is clean.
        store, window = self._leaky_store(
            tmp_path, "2026-08-05", "2026-08-06", "2026-08-05T19:00:00+00:00")
        outcome = evaluate_forward_session(
            store, decision_session="2026-08-05", activation_session="2026-08-04",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_window=window,
        )
        assert outcome.admissible is True
        assert outcome.classification == INFERENTIAL_SERIES_CANDIDATE


# ─────────────────────────────────────────────────────────────────────────
# Series assembly — only candidates enrolled; structural invariant
# ─────────────────────────────────────────────────────────────────────────


class TestAssembleSeries:
    def test_only_candidates_enrolled(self, tmp_path):
        # One store, three sessions: pre-activation (diagnostic), post
        # (enrolled), and a missing one (refused).
        store = G4EvidenceStore(tmp_path / "g4store")
        windows = {}
        for s, nxt in (("2026-08-04", "2026-08-05"), ("2026-08-06", "2026-08-07")):
            w = _window(s, nxt)
            windows[s] = w
            inputs = {
                "universe": {"event_times": [_aware(f"{s}T19:00:00+00:00")],
                             "payload": ["AAPL", "MSFT"]},
            }
            arms = [
                G4ArmSpec(arm=ARM_L1, artifact_digests={"l1": "sha256:" + "a" * 64},
                          config_digest="sha256:" + "c" * 64,
                          scores={"AAPL": 0.1, "MSFT": 0.2}, orders=[]),
                G4ArmSpec(arm=ARM_CHAMPION, artifact_digests={"champ": "sha256:" + "b" * 64},
                          config_digest="sha256:" + "c" * 64,
                          scores={"AAPL": 0.05, "MSFT": 0.15}, orders=[]),
            ]
            run_g4_shadow_session(
                store, decision_session=s, session_window=w, inputs=inputs,
                arms=arms, calendar_id=CAL_ID, price_source_id=PS_ID,
                produced_at=_aware(f"{s}T21:00:00+00:00"))
        windows["2026-08-09"] = _window("2026-08-09", "2026-08-10")  # no records

        report = assemble_inferential_series(
            store, sessions=["2026-08-04", "2026-08-06", "2026-08-09"],
            activation_session="2026-08-05",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_windows=windows,
        )
        assert report.enrolled_sessions == ["2026-08-06"]
        assert report.diagnostic_only_sessions == ["2026-08-04"]
        assert report.refused_sessions == ["2026-08-09"]
        assert report.n_enrolled == 1

    def test_structural_invariant_guards_enrollment(self, tmp_path, monkeypatch):
        """If a hygiene regression let a non-candidate into the enrolled
        set, assembly must fail-closed rather than silently enroll it."""
        store, window = _canonical_store(tmp_path, "2026-08-03", "2026-08-04")

        real = bf.evaluate_forward_session

        def _leaky(*a, **k):
            out = real(*a, **k)
            # Simulate a bug: mislabel a pre-activation diagnostic session
            # as an enrolled candidate without clearing its failed gates.
            out.classification = INFERENTIAL_SERIES_CANDIDATE
            return out

        monkeypatch.setattr(bf, "evaluate_forward_session", _leaky)
        with pytest.raises(SeriesIntegrityError):
            assemble_inferential_series(
                store, sessions=["2026-08-03"], activation_session="2026-08-04",
                frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
                session_windows={"2026-08-03": window})


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


class TestCLI:
    def test_cli_missing_store_root(self, tmp_path):
        rc = main(["--store-root", str(tmp_path / "nope"),
                   "--output-dir", str(tmp_path / "o"),
                   "--session", "2026-08-05"])
        assert rc == 1

    def test_cli_requires_sessions(self, tmp_path):
        store, _ = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        rc = main(["--store-root", str(store.root),
                   "--output-dir", str(tmp_path / "o")])
        assert rc == 1

    def test_cli_end_to_end_real_calendar(self, tmp_path):
        # Full CLI path incl. real-NYSE window resolution (needs pandas).
        pytest.importorskip("pandas_market_calendars")
        pytest.importorskip("renquant_common.market_calendar")
        store, _ = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        out = tmp_path / "output"
        rc = main(["--store-root", str(store.root), "--output-dir", str(out),
                   "--activation-session", "2026-08-04",
                   "--frozen-calendar-id", CAL_ID,
                   "--frozen-price-source-id", PS_ID,
                   "--session", "2026-08-05"])
        assert rc == 0
        report = json.loads((out / "forward_series_report.json").read_text())
        assert report["n_evaluated"] == 1
        assert report["classification"] == bf.CLASSIFICATION

    def test_report_written_and_classified(self, tmp_path):
        store, window = _canonical_store(tmp_path, "2026-08-05", "2026-08-06")
        report = assemble_inferential_series(
            store, sessions=["2026-08-05"], activation_session="2026-08-04",
            frozen_calendar_id=CAL_ID, frozen_price_source_id=PS_ID,
            session_windows={"2026-08-05": window})
        out = tmp_path / "output"
        path = bf.write_report(report, out)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["classification"] == bf.CLASSIFICATION
        assert data["enrolled_sessions"] == ["2026-08-05"]
        cls = json.loads((out / "_experiment_classification.json").read_text())
        assert cls["tool_role"] == bf.TOOL_ROLE
