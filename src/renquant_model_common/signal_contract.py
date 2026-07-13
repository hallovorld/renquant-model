"""Versioned immutable signal artifact contract.

The signal artifact file is a JSON envelope containing producer-authored
metadata and signal data.  ``load_and_verify_signal_artifact`` reads the
file exactly once, validates the embedded manifest, and returns both a
frozen contract and the raw bytes — eliminating the verify-then-read
race condition.

Two additional guarantees beyond byte-identity:

* ``signal_snapshot_digest`` is not merely format-checked — it is
  *recomputed* from the manifest's own other fields (via
  ``compute_signal_snapshot_digest``) and the load fails closed if the
  declared value disagrees. A raw whole-file digest alone cannot catch a
  hand-edited single field (e.g. a bumped ``universe_hash``) left next to a
  stale digest; this check can.
* ``allowed_roots`` lets a caller with a real trust boundary (e.g. a
  scheduler) restrict loading to a configured set of trusted directories,
  so it cannot be pointed at an arbitrary local file. This is a positive
  allowlist, checked via ``Path.resolve()`` + parent-chain membership (not
  string-prefix matching); it is distinct from — and in addition to — the
  existing ``..`` path-traversal rejection, which alone does not stop an
  absolute path outside any trust boundary.

Neither of these — nor anything else in this module — proves *who* was
authorized to write a genuine artifact in the first place; that is a
process/access-control concern for whatever writes into the configured
``allowed_roots``, outside this module's scope. Nor does loading an
envelope tell a consumer whether its contents are what *it* currently
expects (e.g. the right session/day) — a scheduler must still derive its
own expected identity independently and compare it against the loaded
contract, rather than treating the envelope's self-reported provenance as
authoritative on its own.

Asset class and session calendar convention (v1):

``asset_class`` identifies the market segment the signals target.  v1
supports only ``"crypto"``; future versions may add ``"equity"`` etc.

``session_calendar`` identifies which calendar defines a "session day."
Crypto (``asset_class="crypto"``, v1) uses ``"UTC"`` — the session day
equals ``decision_timestamp.astimezone(UTC).date()``.  Equity markets
would use e.g. ``"America/New_York"`` (session day = the exchange's
trading day), but non-UTC calendars are not implemented in v1.

Typical usage::

    contract, payload = load_and_verify_signal_artifact(
        "signals/panel_scores.json",
        allowed_roots=[trusted_signal_dir],
    )
    # contract.producer_run_id, .model_content_digest, etc. are
    # extracted from the artifact envelope — never caller-supplied.
    # Use ``payload`` directly; do not re-read the file.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "V1_OPTIONAL_KEYS",
    "V1_REQUIRED_KEYS",
    "V1_SUPPORTED_ASSET_CLASSES",
    "SignalArtifactContract",
    "compute_signal_snapshot_digest",
    "load_and_verify_signal_artifact",
]

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})
V1_SUPPORTED_ASSET_CLASSES: frozenset[str] = frozenset({"crypto"})

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ARTIFACT_BYTES = 50 * 1024 * 1024  # 50 MB

V1_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
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
    }
)

V1_OPTIONAL_KEYS: frozenset[str] = frozenset()

_V1_ALLOWED_KEYS = V1_REQUIRED_KEYS | V1_OPTIONAL_KEYS


def _reject_non_finite(constant: str) -> None:
    """Raise on non-standard JSON constants (NaN, Infinity, -Infinity).

    Passed as ``parse_constant`` to ``json.loads`` so that Python's
    permissive parser does not silently accept values that are illegal
    in RFC 8259 JSON.
    """
    raise ValueError(
        f"Non-finite JSON value rejected: {constant!r} — "
        f"signal artifacts must contain only finite numbers"
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


def _validate_crypto_pair_key(key: str) -> str:
    """Validate a crypto trading pair key (must already be canonical).

    Must be ``BASE/QUOTE`` format: exactly one ``/``, both parts non-empty,
    uppercase alpha-only (A-Z).  Returns the key unchanged -- the key must
    already be in canonical (uppercase) form.  Non-uppercase input is
    rejected outright rather than silently normalized, so the payload bytes
    and the digest always agree on the same canonical representation.

    Raises ``ValueError`` for invalid pairs (whitespace, missing slash,
    numeric components, empty base/quote, multiple slashes, non-uppercase).
    """
    if not isinstance(key, str):
        raise ValueError(
            f"crypto pair key must be a string, got {type(key).__name__}"
        )
    if any(c.isspace() for c in key):
        raise ValueError(
            f"crypto pair key must not contain whitespace, got {key!r}"
        )
    parts = key.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"crypto pair key must be BASE/QUOTE with exactly one '/', "
            f"got {key!r}"
        )
    base, quote = parts
    if not base:
        raise ValueError(f"crypto pair key has empty base: {key!r}")
    if not quote:
        raise ValueError(f"crypto pair key has empty quote: {key!r}")
    if not base.isalpha() or not base.isupper():
        raise ValueError(
            f"crypto pair base must be uppercase alpha-only (A-Z), got {key!r}"
        )
    if not quote.isalpha() or not quote.isupper():
        raise ValueError(
            f"crypto pair quote must be uppercase alpha-only (A-Z), got {key!r}"
        )
    return key


def _validate_v1_signals(signals: dict, *, asset_class: str) -> dict:
    """Validate v1 signal payload schema and return validated signals.

    Enforces:
    - ``signals`` must be a non-empty dict.
    - Each key must be a non-empty string with no whitespace-only keys.
    - Each value must be a scalar finite numeric (``int`` or ``float``),
      **not** ``bool`` (``isinstance(True, int)`` is ``True`` in Python,
      so ``bool`` is explicitly excluded).
    - Rejects: nested dicts/lists, strings, ``None``, bools, empty keys,
      whitespace-only keys.
    - When ``asset_class == "crypto"``, each key is additionally validated
      as a canonical ``BASE/QUOTE`` pair (uppercase alpha-only, exactly one
      slash) via ``_validate_crypto_pair_key``.  Non-uppercase keys are
      **rejected**, not normalized -- producers must supply canonical keys.

    Returns the validated signals dict unchanged for use in downstream
    digest computation.
    """
    if not isinstance(signals, dict) or not signals:
        raise ValueError(
            f"signals must be a non-empty JSON object, got {type(signals).__name__}"
        )
    normalized: dict = {}
    for ticker, value in signals.items():
        if not isinstance(ticker, str) or not ticker or not ticker.strip():
            raise ValueError(
                f"signals key must be a non-empty, non-whitespace string, "
                f"got {ticker!r}"
            )
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(
                f"signals[{ticker!r}] must be a finite real number, got {value!r}"
            )
        if asset_class == "crypto":
            canonical_key = _validate_crypto_pair_key(ticker)
        else:
            canonical_key = ticker
        if canonical_key in normalized:
            raise ValueError(
                f"duplicate signal key after normalization: {canonical_key!r} "
                f"(from {ticker!r})"
            )
        normalized[canonical_key] = value
    return normalized


def compute_signal_snapshot_digest(
    *,
    schema_version: int,
    asset_class: str,
    producer_run_id: str,
    universe_hash: str,
    model_content_digest: str,
    calibrator_content_digest: str,
    data_watermark: datetime,
    decision_timestamp: datetime,
    session_date: date,
    session_calendar: str,
    signals: Any,
) -> str:
    """Compute the canonical digest over every provenance field + the signals payload.

    This is the single source of truth for the digest formula — used both to
    verify an artifact's embedded ``signal_snapshot_digest`` for internal
    self-consistency at load time, and importable by producers when
    constructing a compliant envelope, so the formula is not hand-copied
    (and does not drift) across the write and read sides.
    """
    canonical = json.dumps(
        {
            "asset_class": asset_class,
            "schema_version": schema_version,
            "producer_run_id": producer_run_id,
            "universe_hash": universe_hash,
            "model_content_digest": model_content_digest,
            "calibrator_content_digest": calibrator_content_digest,
            "data_watermark": data_watermark.astimezone(timezone.utc).isoformat(),
            "decision_timestamp": decision_timestamp.astimezone(timezone.utc).isoformat(),
            "session_date": session_date.isoformat(),
            "session_calendar": session_calendar,
            "signals": signals,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    asset_class: str  # "crypto" for v1; future versions may add "equity" etc.
    producer_run_id: str
    universe_hash: str
    model_content_digest: str
    calibrator_content_digest: str
    data_watermark: datetime  # timezone-aware
    decision_timestamp: datetime  # timezone-aware
    session_date: date
    session_calendar: str  # "UTC" for v1 (crypto); equity would use e.g. "America/New_York"
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

        # Schema version -- must be one this module actually implements
        # (SUPPORTED_SCHEMA_VERSIONS), not merely a positive integer. This
        # check exists in load_and_verify_signal_artifact too, but a direct
        # SignalArtifactContract(...) construction (bypassing the loader)
        # must not be able to skip it. bool is excluded explicitly: it's an
        # int subclass in Python, so `True in {1}` is True.
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version not in SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ValueError(
                f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}, "
                f"got {self.schema_version!r}"
            )

        # asset_class -- must be a non-empty string and, for v1, one of the
        # supported asset classes.
        if not isinstance(self.asset_class, str) or not self.asset_class:
            raise ValueError("asset_class must be a non-empty string")
        if (
            self.schema_version == 1
            and self.asset_class not in V1_SUPPORTED_ASSET_CLASSES
        ):
            raise ValueError(
                f"asset_class must be one of {sorted(V1_SUPPORTED_ASSET_CLASSES)} "
                f"for schema_version 1, got {self.asset_class!r}"
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

        # v1 causal timing invariant: data_watermark must not be after
        # decision_timestamp (a decision cannot precede the data it was
        # based on). Also present in load_and_verify_signal_artifact, but a
        # direct SignalArtifactContract(...) construction must not be able
        # to bypass it.
        if self.data_watermark > self.decision_timestamp:
            raise ValueError(
                f"data_watermark ({self.data_watermark.isoformat()}) must be "
                f"<= decision_timestamp ({self.decision_timestamp.isoformat()}) "
                "-- a decision cannot precede the data it was based on"
            )

        # session_calendar: identifies which calendar defines a "session day."
        # Crypto (v1) uses "UTC" -- session_date equals
        # decision_timestamp.astimezone(UTC).date().  Equity would use
        # e.g. "America/New_York" (exchange trading day); those calendars
        # are not implemented in v1.
        if not isinstance(self.session_calendar, str) or not self.session_calendar:
            raise ValueError("session_calendar must be a non-empty string")
        if self.schema_version == 1 and self.session_calendar != "UTC":
            raise ValueError(
                f"session_calendar must be 'UTC' for schema_version 1, "
                f"got {self.session_calendar!r}"
            )

        # v1 session-date binding (UTC calendar): session_date must equal
        # decision_timestamp's UTC calendar date (matching the crypto
        # RFC's UTC-calendar-day session convention,
        # renquant_orchestrator.crypto_session.SessionWindow), not an
        # independently self-reported field. astimezone(UTC) first --
        # .date() alone would use whatever offset decision_timestamp
        # happens to carry, not necessarily UTC.
        if self.session_calendar == "UTC":
            expected_session_date = self.decision_timestamp.astimezone(
                timezone.utc
            ).date()
            if self.session_date != expected_session_date:
                raise ValueError(
                    f"session_date ({self.session_date.isoformat()}) does not match "
                    f"decision_timestamp's UTC calendar date "
                    f"({expected_session_date.isoformat()})"
                )

        # Path traversal
        if ".." in Path(self.artifact_path).parts:
            raise ValueError(
                f"Path traversal detected in artifact_path: "
                f"{self.artifact_path}"
            )


def load_and_verify_signal_artifact(
    artifact_path: str,
    *,
    allowed_roots: Sequence[str | Path] | None = None,
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
    allowed_roots:
        Optional allowlist of trusted directories. If provided, the
        resolved absolute path must fall under one of these roots (checked
        via ``Path.resolve()`` + parent-chain membership, not string-prefix
        matching, to avoid a sibling directory whose name happens to
        string-prefix an allowed root) or loading fails closed. If
        omitted, any local path is accepted (subject only to the ``..``
        traversal guard below) — callers with a real trust boundary (e.g.
        a scheduler that must not be pointed at an arbitrary local file)
        MUST pass this.

    Returns
    -------
    tuple[SignalArtifactContract, bytes]
        A frozen contract and the raw file bytes.

    Raises
    ------
    FileNotFoundError
        If *artifact_path* does not exist.
    ValueError
        If the file is empty, too large, not valid JSON, has missing /
        malformed manifest fields, the resolved path falls outside
        ``allowed_roots`` (when given), ``signals`` is not a non-empty
        JSON object, or the embedded ``signal_snapshot_digest`` does not
        match the digest recomputed from the manifest's own other fields.
    """
    # Path traversal guard (before touching the filesystem)
    if ".." in Path(artifact_path).parts:
        raise ValueError(
            f"Path traversal detected in artifact path: {artifact_path}"
        )

    p = Path(artifact_path)

    if allowed_roots is not None:
        resolved_candidate = p.resolve()
        resolved_roots = [Path(root).resolve() for root in allowed_roots]
        if not any(
            resolved_candidate == root or root in resolved_candidate.parents
            for root in resolved_roots
        ):
            raise ValueError(
                f"artifact path {resolved_candidate} is not under any allowed root: "
                f"{[str(r) for r in resolved_roots]}"
            )

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
        manifest: Dict[str, Any] = json.loads(
            raw, parse_constant=_reject_non_finite
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Signal artifact is not valid JSON: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ValueError(
            "Signal artifact must be a JSON object at the top level"
        )

    # ── required keys ──
    missing = V1_REQUIRED_KEYS - manifest.keys()
    if missing:
        raise ValueError(
            f"Signal artifact missing required fields: {sorted(missing)}"
        )

    # ── reject unknown envelope keys ──
    unknown = manifest.keys() - _V1_ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f"Signal artifact contains unknown envelope keys: {sorted(unknown)}"
        )

    # ── extract and validate individual fields ──
    schema_version = manifest["schema_version"]
    if not isinstance(schema_version, int) or schema_version < 1:
        raise ValueError(
            f"schema_version must be an integer >= 1, got {schema_version!r}"
        )
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported schema_version {schema_version}; "
            f"supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )

    asset_class = manifest["asset_class"]
    if not isinstance(asset_class, str) or not asset_class:
        raise ValueError("asset_class must be a non-empty string")
    if schema_version == 1 and asset_class not in V1_SUPPORTED_ASSET_CLASSES:
        raise ValueError(
            f"asset_class must be one of {sorted(V1_SUPPORTED_ASSET_CLASSES)} "
            f"for schema_version 1, got {asset_class!r}"
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

    session_calendar = manifest["session_calendar"]
    if not isinstance(session_calendar, str) or not session_calendar:
        raise ValueError("session_calendar must be a non-empty string")
    if schema_version == 1 and session_calendar != "UTC":
        raise ValueError(
            f"session_calendar must be 'UTC' for schema_version 1, "
            f"got {session_calendar!r}"
        )

    # ── causal timing invariant ──
    if data_watermark > decision_timestamp:
        raise ValueError(
            f"Causal timing violation: data_watermark ({data_watermark.isoformat()}) "
            f"must not be after decision_timestamp ({decision_timestamp.isoformat()})"
        )
    # Compare against decision_timestamp's UTC calendar date, not its
    # naive .date() -- .date() on a timezone-aware datetime returns the
    # date in WHATEVER offset the datetime happens to carry (e.g. a
    # producer using local time), not necessarily UTC. The crypto session
    # convention (matching renquant_orchestrator.crypto_session.SessionWindow)
    # is UTC-calendar-day based, so an artifact timestamped near a
    # non-UTC-midnight boundary (e.g. 23:30 US Eastern) would otherwise be
    # compared against the wrong day.
    if session_calendar == "UTC":
        expected_session_date = decision_timestamp.astimezone(timezone.utc).date()
        if session_date != expected_session_date:
            raise ValueError(
                f"Session date mismatch: session_date ({session_date.isoformat()}) "
                f"does not match decision_timestamp's UTC calendar date "
                f"({expected_session_date.isoformat()})"
            )

    signals = manifest["signals"]
    signals = _validate_v1_signals(signals, asset_class=asset_class)

    # Self-consistency: the declared signal_snapshot_digest must actually be
    # the digest of the manifest's own other fields, not merely a
    # well-formatted string. Without this, a single hand-edited field (e.g.
    # universe_hash bumped without recomputing the digest) would pass
    # through with a stale-but-valid-format digest undetected.
    expected_snapshot_digest = compute_signal_snapshot_digest(
        schema_version=schema_version,
        asset_class=asset_class,
        producer_run_id=producer_run_id,
        universe_hash=universe_hash,
        model_content_digest=manifest["model_content_digest"],
        calibrator_content_digest=manifest["calibrator_content_digest"],
        data_watermark=data_watermark,
        decision_timestamp=decision_timestamp,
        session_date=session_date,
        session_calendar=session_calendar,
        signals=signals,
    )
    declared_snapshot_digest = manifest["signal_snapshot_digest"]
    if declared_snapshot_digest != expected_snapshot_digest:
        raise ValueError(
            f"signal_snapshot_digest mismatch: declared={declared_snapshot_digest[:16]}..., "
            f"recomputed={expected_snapshot_digest[:16]}... — envelope fields are "
            f"internally inconsistent (tampered, hand-edited, or stale digest)"
        )

    contract = SignalArtifactContract(
        artifact_path=artifact_path,
        content_digest=content_digest,
        schema_version=schema_version,
        asset_class=asset_class,
        producer_run_id=producer_run_id,
        universe_hash=universe_hash,
        model_content_digest=manifest["model_content_digest"],
        calibrator_content_digest=manifest["calibrator_content_digest"],
        data_watermark=data_watermark,
        decision_timestamp=decision_timestamp,
        session_date=session_date,
        session_calendar=session_calendar,
        signal_snapshot_digest=manifest["signal_snapshot_digest"],
        created_utc=datetime.now(timezone.utc),
    )

    return contract, raw
