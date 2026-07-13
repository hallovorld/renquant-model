"""Tests for renquant_model_common.signal_contract."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from renquant_model_common.signal_contract import (
    SUPPORTED_SCHEMA_VERSIONS,
    V1_OPTIONAL_KEYS,
    V1_REQUIRED_KEYS,
    V1_SUPPORTED_ASSET_CLASSES,
    SignalArtifactContract,
    _validate_crypto_pair_key,
    compute_signal_snapshot_digest,
    load_and_verify_signal_artifact,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_DIGEST = "a" * 64
_ALT_DIGEST = "b" * 64
_NOW = datetime.now(timezone.utc)


def _make_manifest(**overrides) -> dict:
    """Return a minimal valid artifact manifest dict.

    ``signal_snapshot_digest`` is computed from the *other* fields (after
    overrides are applied) via ``compute_signal_snapshot_digest``, so the
    default manifest is self-consistent under the loader's digest-recompute
    check. Pass ``signal_snapshot_digest=...`` explicitly to override it
    verbatim (e.g. to test mismatch/tamper scenarios) — in that case it is
    NOT recomputed.
    """
    content = {
        "schema_version": 1,
        "asset_class": "crypto",
        "producer_run_id": "run-20260712-001",
        "universe_hash": "univ-abc123",
        "model_content_digest": _VALID_DIGEST,
        "calibrator_content_digest": _VALID_DIGEST,
        "data_watermark": "2026-07-12T00:00:00+00:00",
        "decision_timestamp": "2026-07-12T01:00:00+00:00",
        "session_date": "2026-07-12",
        "session_calendar": "UTC",
        "signals": {"BTC/USD": 0.42, "ETH/USD": -0.13},
    }
    explicit_digest = overrides.pop("signal_snapshot_digest", None)
    content.update(overrides)
    if explicit_digest is not None:
        content["signal_snapshot_digest"] = explicit_digest
    else:
        try:
            # Validate crypto pair keys to ensure they are already
            # canonical (uppercase).  The loader no longer normalizes
            # keys, so the digest is computed over the keys as-is.
            digest_signals = content["signals"]
            if (
                content.get("asset_class") == "crypto"
                and isinstance(digest_signals, dict)
            ):
                for k in digest_signals:
                    _validate_crypto_pair_key(k)
            content["signal_snapshot_digest"] = compute_signal_snapshot_digest(
                schema_version=content["schema_version"],
                asset_class=content["asset_class"],
                producer_run_id=content["producer_run_id"],
                universe_hash=content["universe_hash"],
                model_content_digest=content["model_content_digest"],
                calibrator_content_digest=content["calibrator_content_digest"],
                data_watermark=datetime.fromisoformat(content["data_watermark"]),
                decision_timestamp=datetime.fromisoformat(content["decision_timestamp"]),
                session_date=date.fromisoformat(content["session_date"]),
                session_calendar=content["session_calendar"],
                signals=digest_signals,
            )
        except (TypeError, ValueError):
            # A negative-path test intentionally corrupted a content field
            # (e.g. an unparsable timestamp or non-canonical key) to
            # something that can't feed the digest formula; that test
            # fails earlier in the loader (before the digest check), so a
            # placeholder here is harmless.
            content["signal_snapshot_digest"] = _VALID_DIGEST
    return content


def _write_artifact(tmp_path: Path, manifest: dict | None = None) -> Path:
    """Write a JSON artifact file and return its path."""
    if manifest is None:
        manifest = _make_manifest()
    p = tmp_path / "signals.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def _make_contract(**overrides) -> SignalArtifactContract:
    """Construct a SignalArtifactContract with valid defaults.

    ``session_date`` defaults to ``_NOW``'s own UTC calendar date (not a
    hardcoded date) so it stays consistent with ``decision_timestamp=_NOW``
    under the v1 session-date-binding invariant, regardless of which real
    calendar day the test suite happens to run on.
    """
    defaults = dict(
        artifact_path="/some/path.json",
        content_digest=_VALID_DIGEST,
        schema_version=1,
        asset_class="crypto",
        producer_run_id="run-001",
        universe_hash="u1",
        model_content_digest=_VALID_DIGEST,
        calibrator_content_digest=_VALID_DIGEST,
        data_watermark=_NOW,
        decision_timestamp=_NOW,
        session_date=_NOW.astimezone(timezone.utc).date(),
        session_calendar="UTC",
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
        assert contract.signal_snapshot_digest == manifest["signal_snapshot_digest"]
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
        manifest = _make_manifest(schema_version=1)
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 1

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
        """A signal_snapshot_digest that is genuinely consistent with the
        rest of the manifest (here, a manifest with different signals) is
        extracted correctly. (An arbitrary/unrelated digest value is no
        longer accepted verbatim — see TestSignalSnapshotDigestSelfConsistency.)"""
        manifest = _make_manifest(signals={"BTC/USD": 0.9})
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.signal_snapshot_digest == manifest["signal_snapshot_digest"]


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
    def test_different_self_consistent_snapshots_have_different_digests(self, tmp_path):
        """Two genuinely different (each self-consistent) manifests produce
        different signal_snapshot_digest and content_digest values."""
        m1 = _make_manifest(universe_hash="universe-a")
        p = _write_artifact(tmp_path, m1)
        c1, _ = load_and_verify_signal_artifact(str(p))

        m2 = _make_manifest(universe_hash="universe-b")
        p.write_text(json.dumps(m2), encoding="utf-8")
        c2, _ = load_and_verify_signal_artifact(str(p))

        assert c1.signal_snapshot_digest != c2.signal_snapshot_digest
        assert c1.content_digest != c2.content_digest

    def test_stale_digest_after_field_tamper_is_rejected(self, tmp_path):
        """A field changed without recomputing signal_snapshot_digest must
        be caught — a raw file digest alone cannot detect this, since the
        whole point is that *some* field disagrees with the declared
        snapshot identity."""
        manifest = _make_manifest()
        stale_digest = manifest["signal_snapshot_digest"]
        # Tamper universe_hash but keep the (now stale) digest from before.
        manifest["universe_hash"] = "attacker-supplied-universe-hash"
        manifest["signal_snapshot_digest"] = stale_digest
        p = _write_artifact(tmp_path, manifest)

        with pytest.raises(ValueError, match="signal_snapshot_digest mismatch"):
            load_and_verify_signal_artifact(str(p))

    def test_tampered_signals_with_stale_digest_is_rejected(self, tmp_path):
        manifest = _make_manifest()
        stale_digest = manifest["signal_snapshot_digest"]
        manifest["signals"] = {"BTC/USD": 999.0}
        manifest["signal_snapshot_digest"] = stale_digest
        p = _write_artifact(tmp_path, manifest)

        with pytest.raises(ValueError, match="signal_snapshot_digest mismatch"):
            load_and_verify_signal_artifact(str(p))

    def test_valid_self_consistent_digest_round_trips(self, tmp_path):
        manifest = _make_manifest()
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.signal_snapshot_digest == manifest["signal_snapshot_digest"]


class TestSignalsPayloadValidation:
    def test_signals_not_object_rejected(self, tmp_path):
        manifest = _make_manifest(signals="not-a-mapping")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_signals_null_rejected(self, tmp_path):
        manifest = _make_manifest(signals=None)
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_signals_list_rejected(self, tmp_path):
        manifest = _make_manifest(signals=[1, 2, 3])
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_signals_empty_object_rejected(self, tmp_path):
        manifest = _make_manifest(signals={})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))


class TestAllowedRootsPolicy:
    """``allowed_roots`` — the path-policy allowlist requested alongside the
    other fixes, previously entirely absent (only the unrelated ``..``
    traversal guard existed, which does not stop an absolute path outside
    any trust boundary)."""

    def test_no_allowed_roots_is_unrestricted(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p), allowed_roots=None)
        assert contract.producer_run_id == "run-20260712-001"

    def test_path_under_allowed_root_accepted(self, tmp_path):
        root = tmp_path / "trusted"
        root.mkdir()
        p = _write_artifact(root)
        contract, _ = load_and_verify_signal_artifact(str(p), allowed_roots=[root])
        assert contract.producer_run_id == "run-20260712-001"

    def test_path_outside_allowed_root_rejected(self, tmp_path):
        trusted = tmp_path / "trusted"
        trusted.mkdir()
        untrusted = tmp_path / "untrusted"
        untrusted.mkdir()
        p = _write_artifact(untrusted)
        with pytest.raises(ValueError, match="not under any allowed root"):
            load_and_verify_signal_artifact(str(p), allowed_roots=[trusted])

    def test_traversal_lookalike_sibling_prefix_rejected(self, tmp_path):
        """A sibling directory whose name string-prefixes the allowed root
        (e.g. ``trusted-evil/`` vs ``trusted/``) must still be rejected —
        this requires real path/parent-chain checks, not string-prefix
        matching."""
        root = tmp_path / "trusted"
        root.mkdir()
        lookalike = tmp_path / "trusted-evil"
        lookalike.mkdir()
        p = _write_artifact(lookalike)
        with pytest.raises(ValueError, match="not under any allowed root"):
            load_and_verify_signal_artifact(str(p), allowed_roots=[root])

    def test_multiple_allowed_roots_any_match_accepted(self, tmp_path):
        root_a = tmp_path / "root_a"
        root_b = tmp_path / "root_b"
        root_a.mkdir()
        root_b.mkdir()
        p = _write_artifact(root_b)
        contract, _ = load_and_verify_signal_artifact(
            str(p), allowed_roots=[root_a, root_b]
        )
        assert contract.producer_run_id == "run-20260712-001"


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

    def test_unknown_future_schema_version_rejected(self, tmp_path):
        """A future schema_version (e.g. 99) is a valid integer >= 1 but
        not in SUPPORTED_SCHEMA_VERSIONS, so it must be rejected."""
        manifest = _make_manifest(schema_version=99)
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="Unsupported schema_version"):
            load_and_verify_signal_artifact(str(p))

    def test_supported_versions_is_explicit_set(self):
        assert isinstance(SUPPORTED_SCHEMA_VERSIONS, frozenset)
        assert 1 in SUPPORTED_SCHEMA_VERSIONS


class TestMissingRequiredFields:
    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "asset_class",
            "producer_run_id",
            "universe_hash",
            "model_content_digest",
            "calibrator_content_digest",
            "data_watermark",
            "decision_timestamp",
            "session_date",
            "session_calendar",
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


# ====================================================================
# Causal timing invariant (review item 2)
# ====================================================================


class TestCausalTimingInvariant:
    """data_watermark <= decision_timestamp and session_date ==
    decision_timestamp.date()."""

    def test_data_watermark_after_decision_rejected(self, tmp_path):
        """data_watermark > decision_timestamp violates causality."""
        manifest = _make_manifest(
            data_watermark="2026-07-12T05:00:00+00:00",
            decision_timestamp="2026-07-12T01:00:00+00:00",
        )
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="[Cc]ausal timing"):
            load_and_verify_signal_artifact(str(p))

    def test_session_date_mismatch_rejected(self, tmp_path):
        """session_date != decision_timestamp.date() is rejected."""
        manifest = _make_manifest(
            session_date="2026-07-11",
            decision_timestamp="2026-07-12T01:00:00+00:00",
        )
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="[Ss]ession date"):
            load_and_verify_signal_artifact(str(p))

    def test_valid_causal_chain_passes(self, tmp_path):
        """data_watermark <= decision_timestamp, session_date matches."""
        manifest = _make_manifest(
            data_watermark="2026-07-12T00:30:00+00:00",
            decision_timestamp="2026-07-12T01:00:00+00:00",
            session_date="2026-07-12",
        )
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.data_watermark <= contract.decision_timestamp
        assert contract.session_date == contract.decision_timestamp.date()

    def test_watermark_equals_decision_passes(self, tmp_path):
        """Exact equality (watermark == decision_timestamp) is valid."""
        ts = "2026-07-12T01:00:00+00:00"
        manifest = _make_manifest(
            data_watermark=ts,
            decision_timestamp=ts,
            session_date="2026-07-12",
        )
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.data_watermark == contract.decision_timestamp


# ====================================================================
# Non-finite JSON values (review item 3)
# ====================================================================


class TestNonFiniteJsonValues:
    """Reject NaN, Infinity, and -Infinity in signal artifacts."""

    def test_nan_in_signals_rejected(self, tmp_path):
        """A signal value of NaN is non-standard JSON and must be rejected."""
        manifest = _make_manifest()
        p = tmp_path / "signals.json"
        text = json.dumps(manifest)
        # Replace a numeric value with NaN (non-standard JSON)
        text = text.replace("-0.13", "NaN")
        p.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="[Nn]on-finite"):
            load_and_verify_signal_artifact(str(p))

    def test_infinity_in_signals_rejected(self, tmp_path):
        manifest = _make_manifest()
        p = tmp_path / "signals.json"
        text = json.dumps(manifest)
        text = text.replace("-0.13", "Infinity")
        p.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="[Nn]on-finite"):
            load_and_verify_signal_artifact(str(p))

    def test_negative_infinity_in_signals_rejected(self, tmp_path):
        manifest = _make_manifest()
        p = tmp_path / "signals.json"
        text = json.dumps(manifest)
        text = text.replace("-0.13", "-Infinity")
        p.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="[Nn]on-finite"):
            load_and_verify_signal_artifact(str(p))

    def test_finite_signals_pass(self, tmp_path):
        """Normal finite signal values are accepted."""
        manifest = _make_manifest(
            signals={"BTC/USD": 0.42, "ETH/USD": -0.13, "DOGE/USD": 0.0}
        )
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 1


# ====================================================================
# Independent verification follow-up: 3 gaps found in a concurrent
# session's fix for these same 3 Codex findings (5dc9bb6)
# ====================================================================


class TestSessionDateUsesUtcNotNaiveDate:
    """5dc9bb6 compared session_date against decision_timestamp.date()
    directly -- .date() on a timezone-aware datetime returns the date in
    WHATEVER offset it carries, not necessarily UTC. A producer using a
    non-UTC offset near a UTC-day boundary would be compared against the
    wrong day under the crypto RFC's UTC-calendar-day session convention.
    """

    def test_non_utc_offset_near_day_boundary_compared_against_utc_day(
        self, tmp_path
    ):
        # 2026-07-12T23:30:00-05:00 is 2026-07-13T04:30:00+00:00 in UTC --
        # local date is 07-12, UTC date is 07-13. session_date must match
        # the UTC date, not the local one.
        manifest = _make_manifest(
            data_watermark="2026-07-12T23:30:00-05:00",
            decision_timestamp="2026-07-12T23:30:00-05:00",
            session_date="2026-07-12",  # local date -- wrong under UTC rule
        )
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="session_date"):
            load_and_verify_signal_artifact(str(p))

    def test_non_utc_offset_with_correct_utc_session_date_accepted(
        self, tmp_path
    ):
        manifest = _make_manifest(
            data_watermark="2026-07-12T23:30:00-05:00",
            decision_timestamp="2026-07-12T23:30:00-05:00",
            session_date="2026-07-13",  # correct UTC date
        )
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.session_date == date(2026, 7, 13)

    def test_post_init_uses_utc_not_naive_date_too(self):
        from datetime import timedelta

        local_dt = datetime(
            2026, 7, 12, 23, 30, 0, tzinfo=timezone(timedelta(hours=-5))
        )
        with pytest.raises(ValueError, match="session_date"):
            _make_contract(
                data_watermark=local_dt,
                decision_timestamp=local_dt,
                session_date=date(2026, 7, 12),  # local date, not UTC (07-13)
            )


class TestSignalValueTypeValidation:
    """5dc9bb6's finiteness check only fired for `isinstance(value, float)`
    -- a string, None, or bool value never matches that check and would
    pass straight through untouched, since bool is an int subclass (not a
    float subclass) and doesn't trigger it either."""

    def test_rejects_string_signal_value(self, tmp_path):
        manifest = _make_manifest(signals={"BTC/USD": "not-a-number"})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_none_signal_value(self, tmp_path):
        manifest = _make_manifest(signals={"BTC/USD": None})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_bool_signal_value(self, tmp_path):
        manifest = _make_manifest(signals={"BTC/USD": True})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_empty_string_signal_key(self, tmp_path):
        manifest = _make_manifest(signals={"": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_accepts_int_signal_value(self, tmp_path):
        """An integer score (e.g. a discretized signal) is a valid finite
        real number -- only non-numeric/non-finite/bool values are rejected.
        """
        manifest = _make_manifest(signals={"BTC/USD": 1})
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 1


class TestSchemaVersionRejectedAtDirectConstruction:
    """5dc9bb6 added the SUPPORTED_SCHEMA_VERSIONS check to
    load_and_verify_signal_artifact but not to
    SignalArtifactContract.__post_init__ -- a direct construction
    bypassing the loader could still smuggle an unsupported version
    through via the old `>= 1` check alone."""

    def test_unsupported_version_rejected_at_direct_construction(self):
        with pytest.raises(ValueError, match="schema_version"):
            _make_contract(schema_version=2)

    def test_bool_rejected_as_schema_version_at_direct_construction(self):
        with pytest.raises(ValueError, match="schema_version"):
            _make_contract(schema_version=True)


# ====================================================================
# v1 signal key/value negative cases (Codex review items)
# ====================================================================


class TestSignalKeyWhitespaceValidation:
    """Whitespace-only signal keys must be rejected."""

    def test_rejects_whitespace_only_signal_key(self, tmp_path):
        manifest = _make_manifest(signals={"  ": 1.0})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))


class TestSignalValueTypeNegativeCases:
    """Additional negative tests for signal value types."""

    def test_rejects_nested_dict_signal_value(self, tmp_path):
        manifest = _make_manifest(signals={"BTC/USD": {"score": 1}})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_list_signal_value(self, tmp_path):
        manifest = _make_manifest(signals={"BTC/USD": [1, 2]})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="signals"):
            load_and_verify_signal_artifact(str(p))


# ====================================================================
# Unknown envelope keys
# ====================================================================


class TestUnknownEnvelopeKeys:
    """Unknown top-level envelope keys must be rejected."""

    def test_unknown_envelope_key_rejected(self, tmp_path):
        manifest = _make_manifest()
        manifest["extra_unknown_field"] = "surprise"
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="unknown envelope keys"):
            load_and_verify_signal_artifact(str(p))

    def test_future_field_rejected(self, tmp_path):
        """A forward-looking field not in the v1 schema must be rejected,
        ensuring the v1 envelope is schema-closed."""
        manifest = _make_manifest()
        manifest["future_field"] = "value"
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="unknown envelope keys"):
            load_and_verify_signal_artifact(str(p))

    def test_all_required_keys_defined(self):
        """V1_REQUIRED_KEYS includes session_calendar and asset_class."""
        assert "session_calendar" in V1_REQUIRED_KEYS
        assert "asset_class" in V1_REQUIRED_KEYS

    def test_optional_keys_is_frozen(self):
        assert isinstance(V1_OPTIONAL_KEYS, frozenset)


# ====================================================================
# Session calendar
# ====================================================================


class TestSessionCalendar:
    """session_calendar field validation."""

    def test_session_calendar_present_in_contract(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.session_calendar == "UTC"

    def test_non_utc_session_calendar_rejected_for_v1(self, tmp_path):
        manifest = _make_manifest(session_calendar="America/New_York")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="session_calendar"):
            load_and_verify_signal_artifact(str(p))

    def test_empty_session_calendar_rejected(self, tmp_path):
        manifest = _make_manifest(session_calendar="")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="session_calendar"):
            load_and_verify_signal_artifact(str(p))

    def test_session_calendar_direct_construction(self):
        c = _make_contract()
        assert c.session_calendar == "UTC"

    def test_non_utc_direct_construction_rejected(self):
        with pytest.raises(ValueError, match="session_calendar"):
            _make_contract(session_calendar="America/New_York")


# ====================================================================
# Asset class
# ====================================================================


class TestAssetClass:
    """asset_class field validation."""

    def test_asset_class_present_in_contract(self, tmp_path):
        p = _write_artifact(tmp_path)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.asset_class == "crypto"

    def test_crypto_is_supported_v1(self):
        assert "crypto" in V1_SUPPORTED_ASSET_CLASSES

    def test_unknown_asset_class_rejected_via_loader(self, tmp_path):
        manifest = _make_manifest(asset_class="equity")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="asset_class"):
            load_and_verify_signal_artifact(str(p))

    def test_unknown_asset_class_rejected_at_direct_construction(self):
        with pytest.raises(ValueError, match="asset_class"):
            _make_contract(asset_class="equity")

    def test_empty_asset_class_rejected(self, tmp_path):
        manifest = _make_manifest(asset_class="")
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="asset_class"):
            load_and_verify_signal_artifact(str(p))

    def test_empty_asset_class_rejected_at_direct_construction(self):
        with pytest.raises(ValueError, match="asset_class"):
            _make_contract(asset_class="")

    def test_asset_class_in_required_keys(self):
        assert "asset_class" in V1_REQUIRED_KEYS

    def test_asset_class_in_digest_preimage(self):
        """Changing only asset_class must produce a different digest."""
        common = dict(
            schema_version=1,
            producer_run_id="run-001",
            universe_hash="u1",
            model_content_digest=_VALID_DIGEST,
            calibrator_content_digest=_VALID_DIGEST,
            data_watermark=_NOW,
            decision_timestamp=_NOW,
            session_date=_NOW.astimezone(timezone.utc).date(),
            session_calendar="UTC",
            signals={"BTC/USD": 0.5},
        )
        d1 = compute_signal_snapshot_digest(asset_class="crypto", **common)
        # Use a hypothetical second class to prove the digest changes --
        # compute_signal_snapshot_digest itself doesn't validate the value,
        # only load/contract construction do.
        d2 = compute_signal_snapshot_digest(asset_class="equity", **common)
        assert d1 != d2


# ====================================================================
# Crypto pair key validation
# ====================================================================


class TestCryptoPairKeyValidation:
    """When asset_class is "crypto", signal keys must be canonical
    BASE/QUOTE pairs (alpha-only, uppercase, exactly one slash)."""

    # -- rejection cases --

    def test_rejects_no_slash_equity_ticker(self, tmp_path):
        """A plain equity ticker like 'AAPL' has no slash -- rejected."""
        manifest = _make_manifest(signals={"AAPL": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="crypto pair key"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_concatenated_pair_no_slash(self, tmp_path):
        """'BTCUSD' without a slash is not a valid pair."""
        manifest = _make_manifest(signals={"BTCUSD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="crypto pair key"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_whitespace_in_quote(self, tmp_path):
        """'BTC/ USD' has whitespace inside the pair -- rejected."""
        manifest = _make_manifest(signals={"BTC/ USD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="whitespace"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_leading_whitespace(self, tmp_path):
        """' BTC/USD' has leading whitespace -- rejected."""
        manifest = _make_manifest(signals={" BTC/USD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="whitespace"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_multiple_slashes(self, tmp_path):
        """'BTC/USD/ETH' has multiple slashes -- rejected."""
        manifest = _make_manifest(signals={"BTC/USD/ETH": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="crypto pair key"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_numeric_base(self, tmp_path):
        """'123/USD' has a numeric base component -- rejected."""
        manifest = _make_manifest(signals={"123/USD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="alpha-only"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_empty_base(self, tmp_path):
        """'/USD' has an empty base -- rejected."""
        manifest = _make_manifest(signals={"/USD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="empty base"):
            load_and_verify_signal_artifact(str(p))

    def test_rejects_empty_quote(self, tmp_path):
        """'BTC/' has an empty quote -- rejected."""
        manifest = _make_manifest(signals={"BTC/": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="empty quote"):
            load_and_verify_signal_artifact(str(p))

    # -- valid cases --

    def test_accepts_btc_usd(self, tmp_path):
        manifest = _make_manifest(signals={"BTC/USD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 1

    def test_accepts_eth_usd(self, tmp_path):
        manifest = _make_manifest(signals={"ETH/USD": -0.3})
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 1

    def test_accepts_doge_usd(self, tmp_path):
        manifest = _make_manifest(signals={"DOGE/USD": 0.1})
        p = _write_artifact(tmp_path, manifest)
        contract, _ = load_and_verify_signal_artifact(str(p))
        assert contract.schema_version == 1

    # -- rejection of non-canonical (non-uppercase) keys --

    def test_lowercase_pair_rejected(self, tmp_path):
        """'btc/usd' is rejected -- producers must supply canonical
        (uppercase) keys so payload bytes and digest always agree."""
        manifest = _make_manifest(signals={"btc/usd": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="uppercase"):
            load_and_verify_signal_artifact(str(p))

    def test_mixed_case_pair_rejected(self, tmp_path):
        """'Btc/Usd' is rejected -- must be fully uppercase."""
        manifest = _make_manifest(signals={"Btc/Usd": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="uppercase"):
            load_and_verify_signal_artifact(str(p))

    def test_lowercase_base_uppercase_quote_rejected(self, tmp_path):
        """'btc/USD' is rejected -- base must also be uppercase."""
        manifest = _make_manifest(signals={"btc/USD": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="uppercase"):
            load_and_verify_signal_artifact(str(p))

    def test_uppercase_base_lowercase_quote_rejected(self, tmp_path):
        """'BTC/usd' is rejected -- quote must also be uppercase."""
        manifest = _make_manifest(signals={"BTC/usd": 0.5})
        p = _write_artifact(tmp_path, manifest)
        with pytest.raises(ValueError, match="uppercase"):
            load_and_verify_signal_artifact(str(p))

    # -- regression: payload keys match digest keys --

    def test_payload_keys_equal_digest_canonical_keys(self, tmp_path):
        """Regression: the keys in the returned payload must exactly equal
        the canonical keys used in the digest, so that two byte-distinct
        representations cannot share a snapshot identity."""
        signals = {"BTC/USD": 0.42, "ETH/USD": -0.13}
        manifest = _make_manifest(signals=signals)
        p = _write_artifact(tmp_path, manifest)
        contract, payload = load_and_verify_signal_artifact(str(p))

        # Parse the payload and verify keys are exactly the canonical ones
        loaded = json.loads(payload)
        assert set(loaded["signals"].keys()) == set(signals.keys())
        for key in signals:
            assert key in loaded["signals"], (
                f"canonical key {key!r} missing from payload"
            )

        # Recompute digest from the payload's own signal keys/values and
        # verify it matches the contract's declared digest
        recomputed = compute_signal_snapshot_digest(
            schema_version=loaded["schema_version"],
            asset_class=loaded["asset_class"],
            producer_run_id=loaded["producer_run_id"],
            universe_hash=loaded["universe_hash"],
            model_content_digest=loaded["model_content_digest"],
            calibrator_content_digest=loaded["calibrator_content_digest"],
            data_watermark=datetime.fromisoformat(loaded["data_watermark"]),
            decision_timestamp=datetime.fromisoformat(
                loaded["decision_timestamp"]
            ),
            session_date=date.fromisoformat(loaded["session_date"]),
            session_calendar=loaded["session_calendar"],
            signals=loaded["signals"],
        )
        assert recomputed == contract.signal_snapshot_digest
