"""Versioned, self-describing signal artifact envelope.

This module lets a producer (the model-scoring pipeline) publish a signal
artifact whose provenance is *embedded in its own bytes*, and lets a consumer
(e.g. the orchestrator's crypto session scheduler) load that artifact in a
single read that both hashes and parses the exact same bytes, returning one
immutable, fully-validated payload.

What this proves
-----------------
Every provenance field on the returned :class:`SignalEnvelope` — schema
version, producer run id, universe hash, model/calibrator content digests,
data watermark, decision timestamp, session date, and the signal payload
itself — was extracted and validated *from the artifact's own JSON bytes* in
``load_and_verify_signal_envelope``. There is no argument surface by which a
caller can supply independent provenance that disagrees with the artifact
content: the function takes a path (and an optional path-policy allowlist),
nothing else. The envelope also carries a ``signal_snapshot_digest`` that the
producer computes over its own canonical fields; the loader recomputes that
digest from the parsed fields and rejects the file if they disagree, so the
envelope cannot describe itself inconsistently.

What this does NOT prove
-------------------------
This module has no way to know *who* was allowed to write a genuine artifact
in the first place. Proving that a file is internally self-consistent is not
the same as proving it was produced by the real, authorized model-scoring
pipeline — that is a process/access-control concern for whatever writes into
the directories a consumer configures via ``allowed_roots``, and it is
outside this module's scope.

Nor does this module know what signal identity a *consumer* currently
expects. A scheduler that loads an envelope must still derive its own
expected identity independently (e.g. compare the envelope's
``session_date`` / ``data_watermark`` against what it independently expects
for the current tick, and compare ``model_content_sha256`` /
``calibrator_content_sha256`` against the model/calibrator it actually has
pinned) rather than treating the envelope's self-reported provenance as
authoritative on its own. That comparison logic belongs to the consumer
(e.g. orchestrator), not to this module.

Typical producer usage::

    envelope_dict = build_signal_envelope(
        producer_run_id="run-20260712-001",
        universe_hash="abc123...",
        model_content_sha256="...",
        calibrator_content_sha256="...",
        data_watermark=data_watermark_dt,
        decision_timestamp=decision_dt,
        session_date=date(2026, 7, 12),
        signals={"scores": {"BTC/USD": 0.42}},
    )
    artifact_path.write_text(json.dumps(envelope_dict, indent=2, sort_keys=True))

Typical consumer usage::

    envelope = load_and_verify_signal_envelope(
        artifact_path, allowed_roots=[trusted_signal_dir]
    )
    # envelope.producer_run_id, envelope.signals, etc. are all validated
    # and came from the same bytes that were hashed as envelope.content_digest.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

__all__ = [
    "SignalEnvelope",
    "SignalEnvelopeError",
    "MalformedSignalEnvelopeError",
    "SignalEnvelopeSchemaVersionError",
    "SignalEnvelopeProvenanceError",
    "SignalEnvelopePathPolicyError",
    "CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION",
    "compute_signal_snapshot_digest",
    "build_signal_envelope",
    "load_and_verify_signal_envelope",
]

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

# Single supported schema version. A hard equality check (reject anything
# else) is sufficient for now; a real migration system (accepting multiple
# versions and translating between them) is a future concern if/when
# producers actually need to evolve the envelope shape.
CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION = 1

# Exact-match (post strip+lowercase) placeholder blocklist for identifier
# fields. Mirrors the convention established in orchestrator's
# crypto_session.py (`_is_valid_fingerprint` / `_PLACEHOLDER_FINGERPRINT_VALUES`)
# for consistency across the producer/consumer boundary.
_PLACEHOLDER_IDENTIFIER_VALUES = frozenset(
    {
        "missing",
        "unknown",
        "todo",
        "tbd",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "fixme",
        "changeme",
        "placeholder",
        "xxx",
        "<unset>",
        "unset",
    }
)

_REQUIRED_FIELDS = (
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
)


class SignalEnvelopeError(ValueError):
    """Base class for all signal envelope validation failures.

    All validation in this module fails closed by raising a subclass of
    this exception (or, for a missing file, the builtin
    ``FileNotFoundError``).
    """


class MalformedSignalEnvelopeError(SignalEnvelopeError):
    """Envelope bytes are not valid JSON, or a required field is missing/mistyped."""


class SignalEnvelopeSchemaVersionError(SignalEnvelopeError):
    """``schema_version`` does not equal the single currently-supported version."""


class SignalEnvelopeProvenanceError(SignalEnvelopeError):
    """A provenance field is a placeholder, malformed, or chronologically inconsistent."""


class SignalEnvelopePathPolicyError(SignalEnvelopeError):
    """Resolved artifact path falls outside the configured ``allowed_roots``."""


def _is_valid_identifier(value: object) -> bool:
    """Reject non-strings, empty/whitespace-only strings, and known placeholders."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return stripped.lower() not in _PLACEHOLDER_IDENTIFIER_VALUES


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64_RE.match(value))


def _isoformat_utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware to serialize into a signal envelope")
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise MalformedSignalEnvelopeError(f"{field_name} must be a string, got {type(value).__name__}")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise MalformedSignalEnvelopeError(f"{field_name} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise SignalEnvelopeProvenanceError(f"{field_name} must be timezone-aware, got {value!r}")
    return parsed


def _parse_iso_date(value: object, field_name: str) -> date:
    if not isinstance(value, str):
        raise MalformedSignalEnvelopeError(f"{field_name} must be a string, got {type(value).__name__}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MalformedSignalEnvelopeError(f"{field_name} is not a valid ISO-8601 date: {value!r}") from exc


def _freeze_json_value(value: Any) -> Any:
    """Recursively convert parsed JSON containers into immutable equivalents."""
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze_json_value(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json_value(v) for v in value)
    return value


def compute_signal_snapshot_digest(
    *,
    schema_version: int,
    producer_run_id: str,
    universe_hash: str,
    model_content_sha256: str,
    calibrator_content_sha256: str,
    data_watermark: datetime,
    decision_timestamp: datetime,
    session_date: date,
    signals: Mapping[str, Any],
) -> str:
    """Compute the canonical signal-snapshot digest over the envelope's fields.

    This is the single source of truth for the digest, used both when a
    producer builds an envelope (:func:`build_signal_envelope`) and when a
    consumer re-derives the expected digest from parsed fields to check
    self-consistency (``load_and_verify_signal_envelope``). ``signals`` must
    be a plain, JSON-serializable mapping (not the frozen view returned on
    :class:`SignalEnvelope`).
    """
    canonical_obj = {
        "schema_version": schema_version,
        "producer_run_id": producer_run_id,
        "universe_hash": universe_hash,
        "model_content_sha256": model_content_sha256,
        "calibrator_content_sha256": calibrator_content_sha256,
        "data_watermark": _isoformat_utc(data_watermark),
        "decision_timestamp": _isoformat_utc(decision_timestamp),
        "session_date": session_date.isoformat(),
        "signals": signals,
    }
    canonical = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_signal_envelope(
    *,
    producer_run_id: str,
    universe_hash: str,
    model_content_sha256: str,
    calibrator_content_sha256: str,
    data_watermark: datetime,
    decision_timestamp: datetime,
    session_date: date,
    signals: Mapping[str, Any],
    schema_version: int = CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Build a JSON-serializable signal envelope dict with a self-consistent digest.

    Producers should serialize the returned dict (e.g. ``json.dumps(...,
    sort_keys=True)``) directly to the artifact file. This is the write-side
    counterpart to ``load_and_verify_signal_envelope`` — using it ensures the
    embedded ``signal_snapshot_digest`` matches what the loader will
    recompute.
    """
    digest = compute_signal_snapshot_digest(
        schema_version=schema_version,
        producer_run_id=producer_run_id,
        universe_hash=universe_hash,
        model_content_sha256=model_content_sha256,
        calibrator_content_sha256=calibrator_content_sha256,
        data_watermark=data_watermark,
        decision_timestamp=decision_timestamp,
        session_date=session_date,
        signals=signals,
    )
    return {
        "schema_version": schema_version,
        "producer_run_id": producer_run_id,
        "universe_hash": universe_hash,
        "model_content_sha256": model_content_sha256,
        "calibrator_content_sha256": calibrator_content_sha256,
        "data_watermark": _isoformat_utc(data_watermark),
        "decision_timestamp": _isoformat_utc(decision_timestamp),
        "session_date": session_date.isoformat(),
        "signals": signals,
        "signal_snapshot_digest": digest,
    }


@dataclass(frozen=True)
class SignalEnvelope:
    """Fully-validated, immutable signal artifact payload.

    Every field was extracted and validated from the artifact's own bytes by
    ``load_and_verify_signal_envelope`` in a single read — construct this
    class only through that function. See the module docstring for exactly
    what this object does and does not prove about the artifact's
    provenance.
    """

    schema_version: int
    producer_run_id: str
    universe_hash: str
    model_content_sha256: str
    calibrator_content_sha256: str
    data_watermark: datetime
    decision_timestamp: datetime
    session_date: date
    signal_snapshot_digest: str
    signals: Mapping[str, Any]
    content_digest: str
    source_path: Path


def load_and_verify_signal_envelope(
    path: str | Path,
    *,
    allowed_roots: Sequence[str | Path] | None = None,
) -> SignalEnvelope:
    """Read, hash, parse, and validate a signal envelope file in one pass.

    Opens *path* once, reads all bytes, computes the whole-file SHA-256
    content digest from those exact bytes, parses the same bytes as JSON,
    and extracts + validates every provenance field from the parsed content
    (never from caller-supplied arguments — there are none). Returns a
    single immutable payload; there is no window between verification and
    consumption where the underlying file could be swapped, because nothing
    is re-read afterward.

    Parameters
    ----------
    path:
        Path to the signal envelope JSON file.
    allowed_roots:
        Optional allowlist of trusted directories. If provided, the
        resolved absolute path must fall under one of these roots (checked
        via ``Path.resolve()`` + parent-chain membership, not string prefix
        matching, to avoid path-traversal bypasses) or loading fails
        closed with :class:`SignalEnvelopePathPolicyError`. If omitted,
        *any* local path is accepted — callers with a real trust boundary
        (e.g. a scheduler that must not be pointed at an arbitrary local
        file) MUST pass this.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist or is not a regular file.
    SignalEnvelopePathPolicyError
        If ``allowed_roots`` is given and the resolved path is outside it.
    MalformedSignalEnvelopeError
        If the file is empty, not valid JSON, not a JSON object, or is
        missing a required field / has a field of the wrong type.
    SignalEnvelopeSchemaVersionError
        If ``schema_version`` does not equal
        ``CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION``.
    SignalEnvelopeProvenanceError
        If an identifier field is empty/placeholder, a digest field is not
        64-char lowercase hex, a timestamp is not timezone-aware,
        ``data_watermark`` is after ``decision_timestamp``, or the embedded
        ``signal_snapshot_digest`` does not match the digest recomputed
        from the envelope's own fields.
    """
    candidate = Path(path)
    resolved = candidate.resolve()

    if allowed_roots is not None:
        resolved_roots = [Path(root).resolve() for root in allowed_roots]
        if not any(resolved == root or root in resolved.parents for root in resolved_roots):
            raise SignalEnvelopePathPolicyError(
                f"artifact path {resolved} is not under any allowed root: "
                f"{[str(r) for r in resolved_roots]}"
            )

    if not resolved.is_file():
        raise FileNotFoundError(f"Signal envelope not found: {path}")

    raw_bytes = resolved.read_bytes()
    if not raw_bytes:
        raise MalformedSignalEnvelopeError(f"Signal envelope is empty: {path}")

    content_digest = hashlib.sha256(raw_bytes).hexdigest()

    try:
        parsed = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise MalformedSignalEnvelopeError(f"Signal envelope is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise MalformedSignalEnvelopeError(
            f"Signal envelope root must be a JSON object, got {type(parsed).__name__}"
        )

    for field_name in _REQUIRED_FIELDS:
        if field_name not in parsed:
            raise MalformedSignalEnvelopeError(f"Signal envelope missing required field: {field_name!r}")

    schema_version = parsed["schema_version"]
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise MalformedSignalEnvelopeError(
            f"schema_version must be an int, got {type(schema_version).__name__}"
        )
    if schema_version != CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION:
        raise SignalEnvelopeSchemaVersionError(
            f"schema_version mismatch: got {schema_version}, "
            f"expected {CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION}"
        )

    producer_run_id = parsed["producer_run_id"]
    if not _is_valid_identifier(producer_run_id):
        raise SignalEnvelopeProvenanceError(
            f"producer_run_id is empty, whitespace, or a placeholder value: {producer_run_id!r}"
        )

    universe_hash = parsed["universe_hash"]
    if not _is_valid_identifier(universe_hash):
        raise SignalEnvelopeProvenanceError(
            f"universe_hash is empty, whitespace, or a placeholder value: {universe_hash!r}"
        )

    model_content_sha256 = parsed["model_content_sha256"]
    if not _is_hex64(model_content_sha256):
        raise SignalEnvelopeProvenanceError(
            f"model_content_sha256 must be a 64-char lowercase hex digest, got {model_content_sha256!r}"
        )

    calibrator_content_sha256 = parsed["calibrator_content_sha256"]
    if not _is_hex64(calibrator_content_sha256):
        raise SignalEnvelopeProvenanceError(
            f"calibrator_content_sha256 must be a 64-char lowercase hex digest, "
            f"got {calibrator_content_sha256!r}"
        )

    data_watermark = _parse_iso_datetime(parsed["data_watermark"], "data_watermark")
    decision_timestamp = _parse_iso_datetime(parsed["decision_timestamp"], "decision_timestamp")
    if data_watermark > decision_timestamp:
        raise SignalEnvelopeProvenanceError(
            f"data_watermark ({data_watermark.isoformat()}) is after "
            f"decision_timestamp ({decision_timestamp.isoformat()}) — chronologically inconsistent"
        )

    session_date = _parse_iso_date(parsed["session_date"], "session_date")

    signals_raw = parsed["signals"]
    if not isinstance(signals_raw, dict) or not signals_raw:
        raise MalformedSignalEnvelopeError("signals must be a non-empty JSON object")

    declared_digest = parsed["signal_snapshot_digest"]
    if not _is_hex64(declared_digest):
        raise SignalEnvelopeProvenanceError(
            f"signal_snapshot_digest must be a 64-char lowercase hex digest, got {declared_digest!r}"
        )
    expected_digest = compute_signal_snapshot_digest(
        schema_version=schema_version,
        producer_run_id=producer_run_id,
        universe_hash=universe_hash,
        model_content_sha256=model_content_sha256,
        calibrator_content_sha256=calibrator_content_sha256,
        data_watermark=data_watermark,
        decision_timestamp=decision_timestamp,
        session_date=session_date,
        signals=signals_raw,
    )
    if declared_digest != expected_digest:
        raise SignalEnvelopeProvenanceError(
            f"signal_snapshot_digest mismatch: declared={declared_digest[:16]}..., "
            f"recomputed={expected_digest[:16]}... — envelope fields are internally inconsistent"
        )

    return SignalEnvelope(
        schema_version=schema_version,
        producer_run_id=producer_run_id,
        universe_hash=universe_hash,
        model_content_sha256=model_content_sha256,
        calibrator_content_sha256=calibrator_content_sha256,
        data_watermark=data_watermark,
        decision_timestamp=decision_timestamp,
        session_date=session_date,
        signal_snapshot_digest=declared_digest,
        signals=_freeze_json_value(signals_raw),
        content_digest=content_digest,
        source_path=resolved,
    )
