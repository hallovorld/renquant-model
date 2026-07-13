"""Tests for renquant_model_common.signal_contract."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from renquant_model_common.signal_contract import (
    SignalArtifactContract,
    load_and_verify_signal_artifact,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_DIGEST = "a" * 64
_ALT_DIGEST = "b" * 64
_NOW = datetime.now(timezone.utc)


def _make_manifest(**overrides) -> dict:
    """Return a minimal valid artifact manifest dict."""
    base = {
        "schema_version": 1,
        "producer_run_id": "run-20260712-001",
        "universe_hash": "univ-abc123",
        "model_content_digest": _VALID_DIGEST,
        "calibrator_content_digest": _VALID_DIGEST,
        "data_watermark": "2026-07-12T00:00:00+00:00",
        "decision_timestamp": "2026-07-12T01:00:00+00:00",
        "session_date": "2026-07-12",
        "signal_snapshot_digest": _VALID_DIGEST,
        "signals": {"AAPL": 0.42, "MSFT": -0.13},
    }
    base.update(overrides)
    return base


def _write_artifact(tmp_path: Path, manifest: dict | None = None) -> Path:
    """Write a JSON artifact file and return its path."""
    if manifest is None:
        manifest = _make_manifest()
    p = tmp_path / "signals.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def _make_contract(**overrides) -> SignalArtifactContract:
    """Construct a SignalArtifactContract with valid defaults."""
    defaults = dict(
        artifact_path="/some/path.json",
        content_digest=_VALID_DIGEST,
        schema_version=1,
        producer_run_id="run-001",
        universe_hash="u1",
        model_content_digest=_VALID_DIGEST,
        calibrator_content_digest=_VALID_DIGEST,
        data_watermark=_NOW,
        decision_timestamp=_NOW,
        session_date=date(2026, 7, 12),
        signal_snapshot_digest=_VALID_DIGEST,
        created_utc=_NOW,
    )
    defaults.update(overrides)
    return SignalArtifactContract(**defaults)


# ====================================================================
# Happy path
# ====================================================================


class TestHappyPath:
    def test_load_roundtrip(self, tmp_path):
        manifest = _make_manifest()
        p = _write_artifact(tmp_path, manifest)
        raw_bytes = p.read_bytes()
        expected_digest = hashlib.sha256(raw_bytes).hexdigest()

        contract, payload = load_and_verify_signal_artifact(str(p))

        assert payload == raw_bytes
        assert contract.content_digest == expected_digest
        assert contract.schema_version == 1
        assert contract.producer_run_id == "run-20260712-001"
        assert contract.universe_hash == "univ-abc123"
        assert contract.model_content_digest == _VALID_DIGEST
        assert contract.calibrator_content_digest == _VALID_DIGEST
        assert contract.signal_snapshot_digest == _VALID_DIGEST
        assert contract.data_watermark.tzinfo is not None
        assert contract.decision_timestamp.tzinfo is not None
        assert contract.session_date == date(2026, 7, 12)
        assert isinstance(contract.created_utc, datetime)
        assert contract.created_utc.tzinfo is not None

    def test_payload_matches_file_bytes(self, tmp_path):
        """Returned payload is the exact file bytes — no re-read needed."""
        p = _write_artifact(tmp_path)
        _, payload = load_and_verify_signal_artifact(str(p))
        assert payload == p.read_bytes()

    def test_content_digest_is_sha256_of_file(self, tmp_path):
        p = _write_artifact(tmp_path)
        raw = p.read_bytes()
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.content_digest == hashlib.sha256(raw).hexdigest()

    def test_contract_is_frozen(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p))
        with pytest.raises(AttributeError):
            contract.content_digest = "b" * 64  # type: ignore[misc]


# ====================================================================
# Item 1: Provenance from artifact, not caller args
# ====================================================================


class TestProvenanceExtraction:
    """Metadata is extracted from the artifact envelope, not caller-supplied."""

    def test_producer_run_id_from_manifest(self, tmp_path):
        manifest = _make_manifest(producer_run_id="run-from-producer")
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.producer_run_id == "run-from-producer"

    def test_schema_version_from_manifest(self, tmp_path):
        manifest = _make_manifest(schema_version=2)
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 2

    def test_universe_hash_from_manifest(self, tmp_path):
        manifest = _make_manifest(universe_hash="universe-xyz")
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.universe_hash == "universe-xyz"


# ====================================================================
# Item 2: New fields present and correct
# ====================================================================


class TestNewFields:
    def test_model_content_digest(self, tmp_path):
        digest = "c" * 64
        p = _write_artifact(tmp_path, _make_manifest(model_content_digest=digest))
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.model_content_digest == digest

    def test_calibrator_content_digest(self, tmp_path):
        digest = "d" * 64
        p = _write_artifact(
            tmp_path, _make_manifest(calibrator_content_digest=digest)
        )
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.calibrator_content_digest == digest

    def test_data_watermark_is_tz_aware(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.data_watermark.tzinfo is not None
        assert contract.data_watermark.year == 2026

    def test_decision_timestamp_is_tz_aware(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.decision_timestamp.tzinfo is not None

    def test_session_date_is_date(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert isinstance(contract.session_date, date)
        assert contract.session_date == date(2026, 7, 12)

    def test_signal_snapshot_digest(self, tmp_path):
        digest = "e" * 64
        p = _write_artifact(
            tmp_path, _make_manifest(signal_snapshot_digest=digest)
        )
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.signal_snapshot_digest == digest


# ====================================================================
# Item 3: Single-read prevents verify-then-read race
# ====================================================================


class TestSingleRead:
    """load_and_verify_signal_artifact reads once; returned bytes are the
    source of truth — replacement after load is impossible."""

    def test_mutation_after_load_does_not_affect_payload(self, tmp_path):
        """Even if the file is mutated after load, the returned payload
        and digest reflect the original content."""
        p = _write_artifact(tmp_path)
        original_bytes = p.read_bytes()
        original_digest = hashlib.sha256(original_bytes).hexdigest()

        contract, payload = load_and_verify_signal_artifact(str(p))

        # Mutate the file on disk after loading
        p.write_text('{"replaced": true}', encoding="utf-8")

        # Contract and payload reflect the original, pre-mutation content
        assert payload == original_bytes
        assert contract.content_digest == original_digest

    def test_replacement_after_verify_uses_stale_payload(self, tmp_path):
        """Demonstrates that the single-read API prevents TOCTOU:
        consumers use ``payload`` not ``open(path).read()``."""
        p = _write_artifact(tmp_path)
        contract, payload = load_and_verify_signal_artifact(str(p))

        # An attacker replaces the file
        p.write_bytes(b"malicious-replacement")

        # The payload we already have is still the verified original
        assert (
            hashlib.sha256(payload).hexdigest() == contract.content_digest
        )
        # Re-reading the file would give different content — that is
        # exactly the race the single-read API eliminates.
        assert p.read_bytes() != payload


# ====================================================================
# Item 4: Validation — timezone, digest format, path policy
# ====================================================================


class TestTimezoneValidation:
    def test_naive_data_watermark_rejected(self, tmp_path):
        manifest = _make_manifest(data_watermark="2026-07-12T00:00:00")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="timezone-aware"):
            load_and_verify_signal_artifact(str(p))

    def test_naive_decision_timestamp_rejected(self, tmp_path):
        manifest = _make_manifest(decision_timestamp="2026-07-12T01:00:00")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="timezone-aware"):
            load_and_verify_signal_artifact(str(p))

    def test_created_utc_must_be_tz_aware(self):
        """Direct construction with naive created_utc raises."""
        naive = datetime(2026, 7, 12, 0, 0, 0)
        with pytest.raises(ValueError, match="created_utc.*timezone-aware"):
            _make_contract(created_utc=naive)

    def test_data_watermark_direct_naive_rejected(self):
        naive = datetime(2026, 7, 12, 0, 0, 0)
        with pytest.raises(ValueError, match="data_watermark.*timezone-aware"):
            _make_contract(data_watermark=naive)

    def test_decision_timestamp_direct_naive_rejected(self):
        naive = datetime(2026, 7, 12, 0, 0, 0)
        with pytest.raises(
            ValueError, match="decision_timestamp.*timezone-aware"
        ):
            _make_contract(decision_timestamp=naive)

    def test_invalid_datetime_string_rejected(self, tmp_path):
        manifest = _make_manifest(data_watermark="not-a-date")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="invalid ISO-8601"):
            load_and_verify_signal_artifact(str(p))


class TestDigestFormatValidation:
    @pytest.mark.parametrize(
        "field",
        [
            "content_digest",
            "model_content_digest",
            "calibrator_content_digest",
            "signal_snapshot_digest",
        ],
    )
    def test_uppercase_hex_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _make_contract(**{field: "A" * 64})

    @pytest.mark.parametrize(
        "field",
        [
            "content_digest",
            "model_content_digest",
            "calibrator_content_digest",
            "signal_snapshot_digest",
        ],
    )
    def test_short_hex_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _make_contract(**{field: "abcd1234"})

    @pytest.mark.parametrize(
        "field",
        [
            "model_content_digest",
            "calibrator_content_digest",
            "signal_snapshot_digest",
        ],
    )
    def test_bad_digest_in_manifest_rejected(self, field, tmp_path):
        manifest = _make_manifest(**{field: "INVALID"})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match=field):
            load_and_verify_signal_artifact(str(p))


class TestPathValidation:
    def test_path_traversal_rejected_at_load(self, tmp_path):
        p = _write_artifact(tmp_path)
        traversal = str(tmp_path / ".." / tmp_path.name / "signals.json")
        with pytest.raises(ValueError, match="[Pp]ath traversal"):
            load_and_verify_signal_artifact(traversal)

    def test_path_traversal_rejected_at_construction(self):
        with pytest.raises(ValueError, match="[Pp]ath traversal"):
            _make_contract(artifact_path="/foo/../bar/signal.json")


# ====================================================================
# Item 5: Integration tests
# ====================================================================


class TestCallerProvenanceMismatch:
    """Artifact says one run_id; consumer expects another.
    With the new API, provenance comes FROM the artifact — a consumer
    who expects a different run_id compares against the contract field.
    """

    def test_run_id_mismatch_detectable(self, tmp_path):
        manifest = _make_manifest(producer_run_id="run-actual-001")
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        expected_run_id = "run-expected-999"
        assert contract.producer_run_id != expected_run_id

    def test_universe_hash_mismatch_detectable(self, tmp_path):
        manifest = _make_manifest(universe_hash="actual-universe")
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.universe_hash != "expected-universe"


class TestMismatchedSnapshotMetadata:
    def test_snapshot_digest_mismatch(self, tmp_path):
        """If a consumer has a prior snapshot digest, it can detect change."""
        m1 = _make_manifest(signal_snapshot_digest="a" * 64)
        p = _write_artifact(tmp_path, m1)
        c1, _ = load_and_verify_signal_artifact(str(p))

        m2 = _make_manifest(signal_snapshot_digest="b" * 64)
        p.write_text(json.dumps(m2), encoding="utf-8")
        c2, _ = load_and_verify_signal_artifact(str(p))

        assert c1.signal_snapshot_digest != c2.signal_snapshot_digest
        assert c1.content_digest != c2.content_digest


class TestSchemaVersionIncompatibility:
    def test_schema_version_zero_rejected(self, tmp_path):
        manifest = _make_manifest(schema_version=0)
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="schema_version"):
            load_and_verify_signal_artifact(str(p))

    def test_schema_version_negative_rejected(self, tmp_path):
        manifest = _make_manifest(schema_version=-1)
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="schema_version"):
            load_and_verify_signal_artifact(str(p))

    def test_schema_version_string_rejected(self, tmp_path):
        manifest = _make_manifest(schema_version="1")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="schema_version"):
            load_and_verify_signal_artifact(str(p))

    def test_schema_version_directly_rejected(self):
        with pytest.raises(ValueError, match="schema_version"):
            _make_contract(schema_version=0)


class TestMissingRequiredFields:
    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "producer_run_id",
            "universe_hash",
            "model_content_digest",
            "calibrator_content_digest",
            "data_watermark",
            "decision_timestamp",
            "session_date",
            "signal_snapshot_digest",
            "signals",
        ],
    )
    def test_missing_field_rejected(self, field, tmp_path):
        manifest = _make_manifest()
        del manifest[field]
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="missing required fields"):
            load_and_verify_signal_artifact(str(p))


class TestInvalidTimestamps:
    def test_naive_watermark_via_file(self, tmp_path):
        manifest = _make_manifest(data_watermark="2026-07-12T00:00:00")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="timezone-aware"):
            load_and_verify_signal_artifact(str(p))

    def test_naive_decision_via_file(self, tmp_path):
        manifest = _make_manifest(decision_timestamp="2026-07-12T00:00:00")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="timezone-aware"):
            load_and_verify_signal_artifact(str(p))

    def test_garbage_timestamp_rejected(self, tmp_path):
        manifest = _make_manifest(decision_timestamp="last-tuesday")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="invalid ISO-8601"):
            load_and_verify_signal_artifact(str(p))

    def test_invalid_session_date_rejected(self, tmp_path):
        manifest = _make_manifest(session_date="not-a-date")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="session_date"):
            load_and_verify_signal_artifact(str(p))


# ====================================================================
# Error paths — file-level
# ====================================================================


class TestFileErrors:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_and_verify_signal_artifact(
                str(tmp_path / "nonexistent.json")
            )

    def test_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.json"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="empty"):
            load_and_verify_signal_artifact(str(empty))

    def test_non_json_file_raises(self, tmp_path):
        p = tmp_path / "binary.bin"
        p.write_bytes(b"\x00\x01\x02\x03")
        with pytest.raises(ValueError, match="not valid JSON"):
            load_and_verify_signal_artifact(str(p))

    def test_json_array_rejected(self, tmp_path):
        p = tmp_path / "array.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            load_and_verify_signal_artifact(str(p))

    def test_empty_producer_run_id_in_manifest(self, tmp_path):
        manifest = _make_manifest(producer_run_id="")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="producer_run_id"):
            load_and_verify_signal_artifact(str(p))

    def test_empty_universe_hash_in_manifest(self, tmp_path):
        manifest = _make_manifest(universe_hash="")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="universe_hash"):
            load_and_verify_signal_artifact(str(p))


# ====================================================================
# __post_init__ direct construction
# ====================================================================


class TestPostInitValidation:
    def test_valid_contract_creates(self):
        c = _make_contract()
        assert c.artifact_path == "/some/path.json"

    @pytest.mark.parametrize(
        "field", ["artifact_path", "producer_run_id", "universe_hash"]
    )
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            _make_contract(**{field: ""})

    def test_empty_content_digest_rejected(self):
        with pytest.raises(ValueError, match="content_digest"):
            _make_contract(content_digest="")

    def test_invalid_hex_digest_rejected(self):
        with pytest.raises(ValueError, match="content_digest"):
            _make_contract(content_digest="not-valid-hex")

    def test_contract_frozen(self):
        c = _make_contract()
        with pytest.raises(AttributeError):
            c.content_digest = "b" * 64  # type: ignore[misc]
