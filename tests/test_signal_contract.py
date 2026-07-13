"""Tests for renquant_model_common.signal_contract."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from renquant_model_common.signal_contract import (
    SignalArtifactContract,
    load_signal_contract,
    verify_signal_contract,
)


@pytest.fixture()
def artifact_file(tmp_path):
    """Create a small artifact file for testing."""
    p = tmp_path / "scores.parquet"
    p.write_bytes(b"fake-parquet-content-for-testing")
    return p


@pytest.fixture()
def known_digest(artifact_file):
    """Pre-compute the SHA-256 of the test artifact."""
    return hashlib.sha256(artifact_file.read_bytes()).hexdigest()


# ── Happy path ──────────────────────────────────────────────────────


def test_load_and_verify_roundtrip(artifact_file, known_digest):
    contract = load_signal_contract(
        artifact_path=str(artifact_file),
        producer_run_id="run-001",
        schema_version=1,
        universe_hash="abc123",
    )
    assert contract.content_digest == known_digest
    assert contract.schema_version == 1
    assert contract.producer_run_id == "run-001"
    assert contract.universe_hash == "abc123"
    assert isinstance(contract.created_utc, datetime)
    assert verify_signal_contract(contract)


# ── Tamper detection ────────────────────────────────────────────────


def test_verify_detects_modification(artifact_file):
    contract = load_signal_contract(
        artifact_path=str(artifact_file),
        producer_run_id="run-001",
        schema_version=1,
        universe_hash="u1",
    )
    # Mutate the file after contract creation.
    artifact_file.write_bytes(b"modified-content")
    assert not verify_signal_contract(contract)


def test_verify_returns_false_for_deleted_file(artifact_file):
    contract = load_signal_contract(
        artifact_path=str(artifact_file),
        producer_run_id="run-001",
        schema_version=1,
        universe_hash="u1",
    )
    artifact_file.unlink()
    assert not verify_signal_contract(contract)


# ── Error paths ─────────────────────────────────────────────────────


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_signal_contract(
            artifact_path=str(tmp_path / "nonexistent.parquet"),
            producer_run_id="run-001",
            schema_version=1,
            universe_hash="u1",
        )


def test_load_empty_file_raises(tmp_path):
    empty = tmp_path / "empty.parquet"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        load_signal_contract(
            artifact_path=str(empty),
            producer_run_id="run-001",
            schema_version=1,
            universe_hash="u1",
        )


# ── __post_init__ validation ───────────────────────────────────────

_VALID_DIGEST = "a" * 64
_NOW = datetime.now(timezone.utc)


def _make_contract(**overrides):
    defaults = dict(
        artifact_path="/some/path",
        content_digest=_VALID_DIGEST,
        schema_version=1,
        producer_run_id="run-001",
        created_utc=_NOW,
        universe_hash="u1",
    )
    defaults.update(overrides)
    return SignalArtifactContract(**defaults)


def test_valid_contract_creates():
    c = _make_contract()
    assert c.artifact_path == "/some/path"


@pytest.mark.parametrize("field", ["artifact_path", "producer_run_id", "universe_hash"])
def test_empty_string_field_rejected(field):
    with pytest.raises(ValueError, match=field):
        _make_contract(**{field: ""})


def test_empty_content_digest_rejected():
    with pytest.raises(ValueError, match="content_digest"):
        _make_contract(content_digest="")


def test_invalid_hex_digest_rejected():
    with pytest.raises(ValueError, match="content_digest"):
        _make_contract(content_digest="not-valid-hex")


def test_short_digest_rejected():
    with pytest.raises(ValueError, match="content_digest"):
        _make_contract(content_digest="abcd1234")


def test_uppercase_digest_rejected():
    with pytest.raises(ValueError, match="content_digest"):
        _make_contract(content_digest="A" * 64)


def test_schema_version_zero_rejected():
    with pytest.raises(ValueError, match="schema_version"):
        _make_contract(schema_version=0)


def test_schema_version_negative_rejected():
    with pytest.raises(ValueError, match="schema_version"):
        _make_contract(schema_version=-1)


# ── Frozen immutability ─────────────────────────────────────────────


def test_contract_is_frozen():
    c = _make_contract()
    with pytest.raises(AttributeError):
        c.content_digest = "b" * 64  # type: ignore[misc]
