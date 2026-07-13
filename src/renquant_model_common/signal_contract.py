"""Versioned immutable signal artifact contract.

Provides a content-addressable, frozen contract for signal artifacts.
Consumers (e.g. the orchestrator session scheduler) load a contract once
and later verify that the artifact has not been mutated.

Typical usage::

    contract = load_signal_contract(
        artifact_path="signals/panel_scores.parquet",
        producer_run_id="run-20260712-001",
        schema_version=1,
        universe_hash="abc123...",
    )
    # ... later, before consuming the artifact ...
    if not verify_signal_contract(contract):
        raise RuntimeError("signal artifact was tampered with")
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "SignalArtifactContract",
    "load_signal_contract",
    "verify_signal_contract",
]

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class SignalArtifactContract:
    """Frozen, content-addressable contract for a signal artifact.

    All string fields must be non-empty; ``schema_version`` >= 1;
    ``content_digest`` must be a valid 64-char lowercase hex string.
    """

    artifact_path: str
    content_digest: str
    schema_version: int
    producer_run_id: str
    created_utc: datetime
    universe_hash: str

    def __post_init__(self) -> None:
        for field_name in ("artifact_path", "content_digest", "producer_run_id", "universe_hash"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a non-empty string")

        if self.schema_version < 1:
            raise ValueError(f"schema_version must be >= 1, got {self.schema_version}")

        if not _HEX64_RE.match(self.content_digest):
            raise ValueError(
                f"content_digest must be a 64-char lowercase hex string, "
                f"got {self.content_digest!r}"
            )


def load_signal_contract(
    artifact_path: str,
    producer_run_id: str,
    schema_version: int,
    universe_hash: str,
) -> SignalArtifactContract:
    """Load a signal artifact and return a frozen contract.

    Parameters
    ----------
    artifact_path:
        Path to the signal artifact file.
    producer_run_id:
        Identifier of the run that produced the artifact.
    schema_version:
        Version of the artifact schema (>= 1).
    universe_hash:
        Hash of the universe/watchlist used to produce the artifact.

    Returns
    -------
    SignalArtifactContract
        A frozen contract with a content-addressable digest.

    Raises
    ------
    FileNotFoundError
        If *artifact_path* does not exist.
    ValueError
        If the artifact file is empty.
    """
    p = Path(artifact_path)
    if not p.is_file():
        raise FileNotFoundError(f"Signal artifact not found: {artifact_path}")
    if p.stat().st_size == 0:
        raise ValueError(f"Signal artifact is empty: {artifact_path}")

    digest = _sha256_file(p)
    return SignalArtifactContract(
        artifact_path=artifact_path,
        content_digest=digest,
        schema_version=schema_version,
        producer_run_id=producer_run_id,
        created_utc=datetime.now(timezone.utc),
        universe_hash=universe_hash,
    )


def verify_signal_contract(contract: SignalArtifactContract) -> bool:
    """Verify that the artifact still matches the contract digest.

    Returns ``True`` if the file exists and its SHA-256 matches
    ``contract.content_digest``; ``False`` otherwise (including if the
    file is missing or unreadable).
    """
    try:
        p = Path(contract.artifact_path)
        if not p.is_file():
            return False
        return _sha256_file(p) == contract.content_digest
    except OSError:
        return False
