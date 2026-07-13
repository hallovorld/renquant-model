"""Versioned immutable signal artifact contract.

The signal artifact file is a JSON envelope containing producer-authored
metadata and signal data.  ``load_and_verify_signal_artifact`` reads the
file exactly once, validates the embedded manifest, and returns both a
frozen contract and the raw bytes — eliminating the verify-then-read
race condition.

Typical usage::

    contract, payload = load_and_verify_signal_artifact(
        "signals/panel_scores.json",
    )
    # contract.producer_run_id, .model_content_digest, etc. are
    # extracted from the artifact envelope — never caller-supplied.
    # Use ``payload`` directly; do not re-read the file.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

__all__ = [
    "SignalArtifactContract",
    "load_and_verify_signal_artifact",
]

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ARTIFACT_BYTES = 50 * 1024 * 1024  # 50 MB

_REQUIRED_MANIFEST_KEYS = frozenset(
    {
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
    }
)


def _validate_hex64(value: str, field_name: str) -> None:
    """Raise ``ValueError`` unless *value* is a 64-char lowercase hex string."""
    if not isinstance(value, str) or not _HEX64_RE.match(value):
        raise ValueError(
            f"{field_name} must be a 64-char lowercase hex string, "
            f"got {value!r}"
        )


def _parse_tz_aware_datetime(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware ``datetime``."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name}: invalid ISO-8601 datetime: {value!r}"
        ) from exc
    if dt.tzinfo is None:
        raise ValueError(
            f"{field_name} must be timezone-aware, got naive datetime: {value!r}"
        )
    return dt


@dataclass(frozen=True)
class SignalArtifactContract:
    """Frozen, content-addressable contract for a signal artifact.

    All metadata fields are extracted from the artifact's JSON envelope —
    never caller-supplied.  ``content_digest`` is the SHA-256 of the
    entire file bytes (envelope + signals).
    """

    artifact_path: str
    content_digest: str  # SHA-256 of the entire file bytes
    schema_version: int
    producer_run_id: str
    universe_hash: str
    model_content_digest: str
    calibrator_content_digest: str
    data_watermark: datetime  # timezone-aware
    decision_timestamp: datetime  # timezone-aware
    session_date: date
    signal_snapshot_digest: str
    created_utc: datetime  # when the contract was loaded; timezone-aware

    def __post_init__(self) -> None:
        # Non-empty string fields
        for field_name in (
            "artifact_path",
            "content_digest",
            "producer_run_id",
            "universe_hash",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a non-empty string")

        # Schema version
        if not isinstance(self.schema_version, int) or self.schema_version < 1:
            raise ValueError(
                f"schema_version must be >= 1, got {self.schema_version}"
            )

        # Digest format: 64-char lowercase hex
        for field_name in (
            "content_digest",
            "model_content_digest",
            "calibrator_content_digest",
            "signal_snapshot_digest",
        ):
            _validate_hex64(getattr(self, field_name), field_name)

        # Timezone-aware datetime checks
        for field_name in ("created_utc", "data_watermark", "decision_timestamp"):
            dt = getattr(self, field_name)
            if not isinstance(dt, datetime):
                raise ValueError(
                    f"{field_name} must be a datetime, "
                    f"got {type(dt).__name__}"
                )
            if dt.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")

        # session_date
        if not isinstance(self.session_date, date):
            raise ValueError(
                f"session_date must be a date, "
                f"got {type(self.session_date).__name__}"
            )

        # Path traversal
        if ".." in Path(self.artifact_path).parts:
            raise ValueError(
                f"Path traversal detected in artifact_path: "
                f"{self.artifact_path}"
            )


def load_and_verify_signal_artifact(
    artifact_path: str,
) -> Tuple[SignalArtifactContract, bytes]:
    """Read, hash, parse, and validate a signal artifact in one pass.

    The artifact file must be a JSON envelope with the required metadata
    fields (``schema_version``, ``producer_run_id``, ``universe_hash``,
    ``model_content_digest``, ``calibrator_content_digest``,
    ``data_watermark``, ``decision_timestamp``, ``session_date``,
    ``signal_snapshot_digest``, ``signals``).

    Returns both the frozen contract *and* the raw bytes so that
    consumers never need to re-read the file — closing the
    verify-then-read race window.

    Parameters
    ----------
    artifact_path:
        Path to the signal artifact JSON file.

    Returns
    -------
    tuple[SignalArtifactContract, bytes]
        A frozen contract and the raw file bytes.

    Raises
    ------
    FileNotFoundError
        If *artifact_path* does not exist.
    ValueError
        If the file is empty, too large, not valid JSON, or has
        missing / malformed manifest fields.
    """
    # Path traversal guard (before touching the filesystem)
    if ".." in Path(artifact_path).parts:
        raise ValueError(
            f"Path traversal detected in artifact path: {artifact_path}"
        )

    p = Path(artifact_path)
    if not p.is_file():
        raise FileNotFoundError(f"Signal artifact not found: {artifact_path}")

    size = p.stat().st_size
    if size == 0:
        raise ValueError(f"Signal artifact is empty: {artifact_path}")
    if size > _MAX_ARTIFACT_BYTES:
        raise ValueError(
            f"Signal artifact exceeds {_MAX_ARTIFACT_BYTES} byte limit: "
            f"{size} bytes"
        )

    # ── single read: all downstream operations use these bytes ──
    raw = p.read_bytes()
    content_digest = hashlib.sha256(raw).hexdigest()

    # ── parse JSON envelope ──
    try:
        manifest: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Signal artifact is not valid JSON: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ValueError(
            "Signal artifact must be a JSON object at the top level"
        )

    # ── required keys ──
    missing = _REQUIRED_MANIFEST_KEYS - manifest.keys()
    if missing:
        raise ValueError(
            f"Signal artifact missing required fields: {sorted(missing)}"
        )

    # ── extract and validate individual fields ──
    schema_version = manifest["schema_version"]
    if not isinstance(schema_version, int) or schema_version < 1:
        raise ValueError(
            f"schema_version must be an integer >= 1, got {schema_version!r}"
        )

    producer_run_id = manifest["producer_run_id"]
    if not isinstance(producer_run_id, str) or not producer_run_id:
        raise ValueError("producer_run_id must be a non-empty string")

    universe_hash = manifest["universe_hash"]
    if not isinstance(universe_hash, str) or not universe_hash:
        raise ValueError("universe_hash must be a non-empty string")

    for digest_field in (
        "model_content_digest",
        "calibrator_content_digest",
        "signal_snapshot_digest",
    ):
        _validate_hex64(manifest[digest_field], digest_field)

    data_watermark = _parse_tz_aware_datetime(
        manifest["data_watermark"], "data_watermark"
    )
    decision_timestamp = _parse_tz_aware_datetime(
        manifest["decision_timestamp"], "decision_timestamp"
    )

    raw_session_date = manifest["session_date"]
    try:
        session_date = date.fromisoformat(raw_session_date)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"session_date: invalid ISO-8601 date: {raw_session_date!r}"
        ) from exc

    contract = SignalArtifactContract(
        artifact_path=artifact_path,
        content_digest=content_digest,
        schema_version=schema_version,
        producer_run_id=producer_run_id,
        universe_hash=universe_hash,
        model_content_digest=manifest["model_content_digest"],
        calibrator_content_digest=manifest["calibrator_content_digest"],
        data_watermark=data_watermark,
        decision_timestamp=decision_timestamp,
        session_date=session_date,
        signal_snapshot_digest=manifest["signal_snapshot_digest"],
        created_utc=datetime.now(timezone.utc),
    )

    return contract, raw
