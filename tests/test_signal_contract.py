"""Tests for renquant_model_common.signal_contract (envelope-based)."""
from __future__ import annotations

import hashlib
import inspect
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from renquant_model_common.signal_contract import (
    CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION,
    MalformedSignalEnvelopeError,
    SignalEnvelope,
    SignalEnvelopeError,
    SignalEnvelopePathPolicyError,
    SignalEnvelopeProvenanceError,
    SignalEnvelopeSchemaVersionError,
    build_signal_envelope,
    compute_signal_snapshot_digest,
    load_and_verify_signal_envelope,
)

_VALID_HEX = "a" * 64
_OTHER_HEX = "b" * 64
_DATA_WATERMARK = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
_DECISION_TS = datetime(2026, 7, 12, 0, 5, tzinfo=timezone.utc)
_SESSION_DATE = date(2026, 7, 12)
_SIGNALS = {"scores": {"BTC/USD": 0.42, "ETH/USD": -0.1}}


def _valid_fields(**overrides):
    defaults = dict(
        producer_run_id="run-20260712-001",
        universe_hash="universe-hash-abc123",
        model_content_sha256=_VALID_HEX,
        calibrator_content_sha256=_OTHER_HEX,
        data_watermark=_DATA_WATERMARK,
        decision_timestamp=_DECISION_TS,
        session_date=_SESSION_DATE,
        signals=_SIGNALS,
    )
    defaults.update(overrides)
    return defaults


def _write_envelope(tmp_path, name="signal.json", *, envelope_dict=None, **field_overrides):
    """Build a valid envelope dict (unless one is supplied) and write it as JSON."""
    if envelope_dict is None:
        envelope_dict = build_signal_envelope(**_valid_fields(**field_overrides))
    path = tmp_path / name
    path.write_text(json.dumps(envelope_dict, sort_keys=True, indent=2))
    return path


# ── Happy path / round-trip ─────────────────────────────────────────


def test_load_and_verify_roundtrip(tmp_path):
    path = _write_envelope(tmp_path)
    envelope = load_and_verify_signal_envelope(path)

    assert isinstance(envelope, SignalEnvelope)
    assert envelope.schema_version == CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION
    assert envelope.producer_run_id == "run-20260712-001"
    assert envelope.universe_hash == "universe-hash-abc123"
    assert envelope.model_content_sha256 == _VALID_HEX
    assert envelope.calibrator_content_sha256 == _OTHER_HEX
    assert envelope.data_watermark == _DATA_WATERMARK
    assert envelope.decision_timestamp == _DECISION_TS
    assert envelope.session_date == _SESSION_DATE
    assert dict(envelope.signals) == {"scores": {"BTC/USD": 0.42, "ETH/USD": -0.1}}
    assert envelope.content_digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert envelope.source_path == path.resolve()


def test_signal_snapshot_digest_matches_helper(tmp_path):
    path = _write_envelope(tmp_path)
    envelope = load_and_verify_signal_envelope(path)
    expected = compute_signal_snapshot_digest(
        schema_version=envelope.schema_version,
        producer_run_id=envelope.producer_run_id,
        universe_hash=envelope.universe_hash,
        model_content_sha256=envelope.model_content_sha256,
        calibrator_content_sha256=envelope.calibrator_content_sha256,
        data_watermark=envelope.data_watermark,
        decision_timestamp=envelope.decision_timestamp,
        session_date=envelope.session_date,
        signals=_SIGNALS,
    )
    assert envelope.signal_snapshot_digest == expected


def test_accepts_str_path(tmp_path):
    path = _write_envelope(tmp_path)
    envelope = load_and_verify_signal_envelope(str(path))
    assert envelope.producer_run_id == "run-20260712-001"


# ── No caller-provenance argument surface ───────────────────────────


def test_loader_signature_has_no_provenance_args():
    """The loader must not accept provenance as separate caller arguments.

    This is the structural guarantee behind "caller-provenance mismatch is
    impossible by construction": every provenance field must come from the
    artifact's own bytes, so the only parameters are the path and the
    (optional) path-policy allowlist.
    """
    params = set(inspect.signature(load_and_verify_signal_envelope).parameters)
    assert params == {"path", "allowed_roots"}
    forbidden = {
        "producer_run_id",
        "schema_version",
        "universe_hash",
        "model_content_sha256",
        "calibrator_content_sha256",
        "data_watermark",
        "decision_timestamp",
        "session_date",
    }
    assert params.isdisjoint(forbidden)


# ── No verify-then-read race: re-load reflects mutation, no caching ──


def test_reload_after_mutation_returns_different_result(tmp_path):
    path = _write_envelope(tmp_path, producer_run_id="run-original")
    first = load_and_verify_signal_envelope(path)
    assert first.producer_run_id == "run-original"

    # Overwrite with a different, still internally-consistent envelope.
    _write_envelope(tmp_path, envelope_dict=None, producer_run_id="run-replaced")
    second = load_and_verify_signal_envelope(path)

    assert second.producer_run_id == "run-replaced"
    assert first.producer_run_id != second.producer_run_id
    assert first.content_digest != second.content_digest


def test_tamper_after_load_is_not_silently_trusted(tmp_path):
    """Mutating the file after an initial load must not affect that
    already-returned, immutable payload, and a fresh load must reflect the
    new (or now-invalid) content rather than reusing a cached result."""
    path = _write_envelope(tmp_path, producer_run_id="run-a")
    envelope = load_and_verify_signal_envelope(path)

    # Corrupt the file in place after the first load.
    path.write_text("not json at all")

    # The already-returned payload is unaffected (held in memory).
    assert envelope.producer_run_id == "run-a"
    # A fresh load re-reads from disk and fails closed.
    with pytest.raises(MalformedSignalEnvelopeError):
        load_and_verify_signal_envelope(path)


# ── Path / root policy ───────────────────────────────────────────────


def test_allowed_roots_accepts_path_under_root(tmp_path):
    root = tmp_path / "trusted"
    root.mkdir()
    path = _write_envelope(root)
    envelope = load_and_verify_signal_envelope(path, allowed_roots=[root])
    assert envelope.producer_run_id == "run-20260712-001"


def test_allowed_roots_rejects_path_outside_root(tmp_path):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    untrusted = tmp_path / "untrusted"
    untrusted.mkdir()
    path = _write_envelope(untrusted)

    with pytest.raises(SignalEnvelopePathPolicyError):
        load_and_verify_signal_envelope(path, allowed_roots=[trusted])


def test_allowed_roots_rejects_traversal_lookalike_prefix(tmp_path):
    """A sibling directory whose name string-prefixes the allowed root must
    still be rejected — this must use real path/parent checks, not naive
    string prefix matching."""
    root = tmp_path / "trusted"
    root.mkdir()
    lookalike = tmp_path / "trusted-evil"
    lookalike.mkdir()
    path = _write_envelope(lookalike)

    with pytest.raises(SignalEnvelopePathPolicyError):
        load_and_verify_signal_envelope(path, allowed_roots=[root])


def test_no_allowed_roots_keeps_unrestricted_behavior(tmp_path):
    path = _write_envelope(tmp_path)
    envelope = load_and_verify_signal_envelope(path, allowed_roots=None)
    assert envelope.producer_run_id == "run-20260712-001"


# ── Missing file / empty file / malformed JSON ──────────────────────


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_and_verify_signal_envelope(tmp_path / "nonexistent.json")


def test_empty_file_raises(tmp_path):
    path = tmp_path / "empty.json"
    path.write_bytes(b"")
    with pytest.raises(MalformedSignalEnvelopeError, match="empty"):
        load_and_verify_signal_envelope(path)


def test_malformed_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    with pytest.raises(MalformedSignalEnvelopeError):
        load_and_verify_signal_envelope(path)


def test_non_object_json_root_raises(tmp_path):
    path = tmp_path / "array.json"
    path.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(MalformedSignalEnvelopeError):
        load_and_verify_signal_envelope(path)


# ── Missing required fields (each individually) ─────────────────────


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "producer_run_id",
        "universe_hash",
        "model_content_sha256",
        "calibrator_content_sha256",
        "data_watermark",
        "decision_timestamp",
        "session_date",
        "signals",
        "signal_snapshot_digest",
    ],
)
def test_missing_required_field_rejected(tmp_path, field):
    envelope_dict = build_signal_envelope(**_valid_fields())
    del envelope_dict[field]
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(MalformedSignalEnvelopeError, match=field):
        load_and_verify_signal_envelope(path)


# ── schema_version ───────────────────────────────────────────────────


def test_schema_version_mismatch_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["schema_version"] = CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION + 1
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(SignalEnvelopeSchemaVersionError):
        load_and_verify_signal_envelope(path)


def test_schema_version_wrong_type_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["schema_version"] = "1"
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(MalformedSignalEnvelopeError):
        load_and_verify_signal_envelope(path)


# ── Placeholder identifiers ──────────────────────────────────────────


@pytest.mark.parametrize("placeholder", ["", "   ", "UNKNOWN", "unknown", "TODO", "placeholder", "N/A"])
def test_placeholder_producer_run_id_rejected(tmp_path, placeholder):
    path = _write_envelope(tmp_path, producer_run_id=placeholder)
    with pytest.raises(SignalEnvelopeProvenanceError, match="producer_run_id"):
        load_and_verify_signal_envelope(path)


@pytest.mark.parametrize("placeholder", ["", "   ", "UNKNOWN", "MISSING", "changeme"])
def test_placeholder_universe_hash_rejected(tmp_path, placeholder):
    path = _write_envelope(tmp_path, universe_hash=placeholder)
    with pytest.raises(SignalEnvelopeProvenanceError, match="universe_hash"):
        load_and_verify_signal_envelope(path)


# ── Digest field format ──────────────────────────────────────────────


@pytest.mark.parametrize("bad_digest", ["", "not-hex", "abcd1234", "A" * 64, "g" * 64])
def test_invalid_model_content_sha256_rejected(tmp_path, bad_digest):
    path = _write_envelope(tmp_path, model_content_sha256=bad_digest)
    with pytest.raises(SignalEnvelopeProvenanceError, match="model_content_sha256"):
        load_and_verify_signal_envelope(path)


@pytest.mark.parametrize("bad_digest", ["", "not-hex", "abcd1234", "A" * 64])
def test_invalid_calibrator_content_sha256_rejected(tmp_path, bad_digest):
    path = _write_envelope(tmp_path, calibrator_content_sha256=bad_digest)
    with pytest.raises(SignalEnvelopeProvenanceError, match="calibrator_content_sha256"):
        load_and_verify_signal_envelope(path)


# ── Timestamps ───────────────────────────────────────────────────────


def test_naive_data_watermark_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["data_watermark"] = "2026-07-11T00:00:00"  # no tz offset
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(SignalEnvelopeProvenanceError, match="data_watermark"):
        load_and_verify_signal_envelope(path)


def test_naive_decision_timestamp_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["decision_timestamp"] = "2026-07-12T00:05:00"  # no tz offset
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(SignalEnvelopeProvenanceError, match="decision_timestamp"):
        load_and_verify_signal_envelope(path)


def test_malformed_data_watermark_string_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["data_watermark"] = "not-a-timestamp"
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(MalformedSignalEnvelopeError, match="data_watermark"):
        load_and_verify_signal_envelope(path)


def test_malformed_session_date_string_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["session_date"] = "not-a-date"
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(MalformedSignalEnvelopeError, match="session_date"):
        load_and_verify_signal_envelope(path)


def test_data_watermark_after_decision_timestamp_rejected(tmp_path):
    """Causal violation: data cannot be watermarked later than the decision
    that (allegedly) used it."""
    path = _write_envelope(
        tmp_path,
        data_watermark=_DECISION_TS + timedelta(hours=1),
        decision_timestamp=_DECISION_TS,
    )
    with pytest.raises(SignalEnvelopeProvenanceError, match="chronologically inconsistent"):
        load_and_verify_signal_envelope(path)


def test_data_watermark_equal_decision_timestamp_allowed(tmp_path):
    path = _write_envelope(tmp_path, data_watermark=_DECISION_TS, decision_timestamp=_DECISION_TS)
    envelope = load_and_verify_signal_envelope(path)
    assert envelope.data_watermark == envelope.decision_timestamp


def test_accepts_z_suffix_timestamp(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    # Re-embed watermark with a literal "Z" suffix (still the same instant);
    # the digest was computed from the isoformat "+00:00" representation, so
    # we only swap the *reader-facing* string, not what the digest covers.
    assert envelope_dict["data_watermark"].endswith("+00:00")
    envelope_dict["data_watermark"] = envelope_dict["data_watermark"].replace("+00:00", "Z")
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    envelope = load_and_verify_signal_envelope(path)
    assert envelope.data_watermark == _DATA_WATERMARK


# ── signals payload ──────────────────────────────────────────────────


def test_signals_not_object_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["signals"] = [1, 2, 3]
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(MalformedSignalEnvelopeError, match="signals"):
        load_and_verify_signal_envelope(path)


def test_signals_empty_object_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields(signals={}))
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(MalformedSignalEnvelopeError, match="signals"):
        load_and_verify_signal_envelope(path)


# ── signal_snapshot_digest self-consistency ──────────────────────────


def test_tampered_signals_after_digest_computed_rejected(tmp_path):
    """Mutating the payload without recomputing the digest must be caught —
    this is the internal self-consistency check that a raw file-hash-only
    scheme cannot provide."""
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["signals"] = {"scores": {"BTC/USD": 999.0}}
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(SignalEnvelopeProvenanceError, match="signal_snapshot_digest"):
        load_and_verify_signal_envelope(path)


def test_tampered_universe_hash_after_digest_computed_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["universe_hash"] = "a-different-universe-hash"
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(SignalEnvelopeProvenanceError, match="signal_snapshot_digest"):
        load_and_verify_signal_envelope(path)


def test_invalid_signal_snapshot_digest_format_rejected(tmp_path):
    envelope_dict = build_signal_envelope(**_valid_fields())
    envelope_dict["signal_snapshot_digest"] = "not-hex"
    path = _write_envelope(tmp_path, envelope_dict=envelope_dict)
    with pytest.raises(SignalEnvelopeProvenanceError, match="signal_snapshot_digest"):
        load_and_verify_signal_envelope(path)


# ── Immutability ──────────────────────────────────────────────────────


def test_envelope_is_frozen(tmp_path):
    path = _write_envelope(tmp_path)
    envelope = load_and_verify_signal_envelope(path)
    with pytest.raises(AttributeError):
        envelope.producer_run_id = "different-run"  # type: ignore[misc]


def test_envelope_signals_is_immutable_mapping(tmp_path):
    path = _write_envelope(tmp_path)
    envelope = load_and_verify_signal_envelope(path)
    with pytest.raises(TypeError):
        envelope.signals["scores"] = {}  # type: ignore[index]


# ── Exception hierarchy ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "exc_cls",
    [
        MalformedSignalEnvelopeError,
        SignalEnvelopeSchemaVersionError,
        SignalEnvelopeProvenanceError,
        SignalEnvelopePathPolicyError,
    ],
)
def test_all_domain_exceptions_are_signal_envelope_errors(exc_cls):
    assert issubclass(exc_cls, SignalEnvelopeError)
    assert issubclass(exc_cls, ValueError)
