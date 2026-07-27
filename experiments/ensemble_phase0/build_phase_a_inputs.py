"""Convert a walk-forward sim DB + its ``wf_sim_provenance.v1`` ledger into
Phase A ensemble inputs.

The Phase A runner (:mod:`phase_a_runner`) consumes, per expert, a *score
directory* of per-date ``YYYY-MM-DD.json`` files that pass the Stage-0
admissibility ledger (:mod:`admissibility_ledger`), plus one shared
forward-returns CSV. The walk-forward sim persists per-date scores to a sim
DB (``score_distribution``) and — since renquant-pipeline's provenance sink
landed (design ``doc/design/2026-07-27-wf-sim-provenance-contract.md``,
"#215") — appends generation-time provenance records to a
``data/wf_provenance/<sim_run_id>.jsonl`` ledger. This converter bridges the
gap for ANY single scorer's walk-forward-sim run.

Provenance model (design #215 §2.5 — extraction is a READ + VERIFY;
reconstruction is only a CROSS-CHECK):

* The ``wf_sim_provenance.v1`` JSONL ledger (``--provenance-ledger``,
  REQUIRED) is the ONLY source of fold/artifact identity. Per prediction
  date the converter requires the complete ``fold_resolved`` +
  ``score_committed`` pair with matching keys and a matching
  ``artifact_digest`` echo. Orphaned records (either kind alone),
  non-identical duplicates, ``persisted: false``, ``pit_violation: true``,
  and ``is_real_content_digest: false`` are all INADMISSIBLE — each
  rejection is recorded with a machine-readable reason in the build
  manifest.
* The converter reads the score rows AT the recorded
  ``score_observation_key`` (``(run_id, date, run_type)``) from the sim DB,
  recomputes the canonical ``score_payload_digest`` over exactly what it
  read back, and requires equality with the recorded digest plus an
  ``n_rows`` match — proving the observation it consumes IS the one the sim
  committed.
* ``select_pit_fold`` + ``resolve_artifact_digest`` (the previous
  post-hoc reconstruction path, kept in this module) now run ONLY as
  independent cross-checks. ANY disagreement between the ledger's recorded
  identity and the re-derived identity is a HARD error
  (:class:`CrossCheckMismatchError`): the date's evidence is quarantined
  and the build aborts before writing any output. Reconstruction is NEVER
  a fallback for a missing/failed ledger fact.
* Output stamping uses LEDGER facts verbatim: ``training_cutoff`` =
  ``fold_resolved.cutoff_date``; ``model_content_sha256`` =
  ``fold_resolved.artifact_digest``; ``score_timestamp`` =
  ``score_committed.score_timestamp`` (the SIMULATED decision instant, per
  design §2.2); ``as_of_date``/``data_watermark`` =
  ``score_committed.input_watermark``. Nothing time- or identity-shaped is
  recomputed at extraction time. A record with a null ``input_watermark``
  is rejected (the emit-side PIT check could not run; extraction owns that
  judgement and fails closed rather than fabricating a watermark).

Consequence, stated plainly: sim history generated BEFORE the provenance
sink existed has no ledger and is therefore permanently inadmissible
through this converter. That is the point of the redesign (codex review on
model#64/#65/#66), not a regression — admissible Phase-A evidence arrives
only from post-#531 preregistered reruns that emit the ledger at
generation time.

Scorer-agnostic by construction: the sim DB path, the provenance ledger,
the WF manifest (cross-check input), and the score column are all
parameters.

All output goes to an experiment-specific directory, never to production
paths. Source DBs are opened read-only. Records carry an EXPLORATORY_ONLY
classification.

Usage::

    python -m experiments.ensemble_phase0.build_phase_a_inputs \\
        --sim-db /path/to/sim_runs.db \\
        --provenance-ledger /path/to/wf_provenance/<sim_run_id>.jsonl \\
        --manifest-file /path/to/walkforward_manifest_<recipe>.json \\
        --output-dir experiments/ensemble_phase0/output/phase_a \\
        --expert-name xgb \\
        --score-column raw_panel \\
        --start-date 2025-08-25 --end-date 2026-03-27
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.tseries.offsets import BDay

from experiments.ensemble_phase0.admissibility_ledger import (
    US_EQUITY_CLOSE,
    DecisionSchedule,
    ExpertSpec,
    build_calendar_evidence,
    build_exchange_session_calendar,
    build_ledger,
    extract_metadata_from_score,
    load_score_file,
    write_calendar_evidence,
    write_ledger,
)

#: Query/schema-version tag persisted in every provenance record. Bump when
#: the extraction SQL or the admissibility semantics change. ``v2``: the
#: wf_sim_provenance.v1 ledger became the ONLY identity source (design #215
#: §2.5); manifest replay demoted to a cross-check.
QUERY_SCHEMA_VERSION = "build_phase_a_inputs.wf_sim_provenance_ledger.v2"

#: The real numeric per-ticker score columns in ``score_distribution``.
#: ``--score-column`` is validated against this FIXED allowlist BEFORE it ever
#: reaches a SQL string (a SQL-injection guard).
ALLOWED_SCORE_COLUMNS = frozenset({"raw_panel", "mu", "rank_score", "sigma"})


class ScoreColumnNotAllowedError(ValueError):
    """Raised when ``--score-column`` is not on :data:`ALLOWED_SCORE_COLUMNS`."""


def validate_score_column(score_column: str) -> str:
    """Validate ``score_column`` against the fixed allowlist.

    Returns the column name unchanged, or raises
    :class:`ScoreColumnNotAllowedError`. An unrecognised value is rejected
    here and NEVER reaches a query string.
    """
    if score_column not in ALLOWED_SCORE_COLUMNS:
        raise ScoreColumnNotAllowedError(
            f"--score-column={score_column!r} is not an allowed "
            f"score_distribution column. Allowed: {sorted(ALLOWED_SCORE_COLUMNS)}. "
            f"Refusing to build a SQL query from an unvalidated column name."
        )
    return score_column


# =====================================================================
# Canonical score-payload digest (wf_sim_provenance.v1 binding group)
# =====================================================================
#: Fixed per-row field order of the canonical score-payload serialization.
#: Mirrors ``renquant_pipeline.kernel.walk_forward.provenance
#: .SCORE_PAYLOAD_FIELDS`` — do not reorder.
SCORE_PAYLOAD_FIELDS = ("ticker", "raw_panel", "mu", "rank_score", "sigma")

#: The digest implementation identity stamped into the build manifest.
#: This module deliberately does NOT import renquant_pipeline — the model
#: factory never imports the runtime pipeline, not even guarded
#: (architecture boundary; codex round-2 on model#65). The implementation
#: below is a FIXED versioned vendored copy; producer/consumer
#: compatibility is enforced by the fixed test vectors in
#: ``tests/test_build_phase_a_inputs.py`` (computed once from the pinned
#: producer revision), not by an import. Sanctioned follow-up (separate
#: PR, NOT this one): canonicalize this digest into renquant-common (same
#: pattern as ``walk_forward_fold_selection``) so pipeline#216 and this
#: converter both consume ONE implementation.
PAYLOAD_DIGEST_IMPL = (
    "vendored:renquant_pipeline.kernel.walk_forward.provenance@ac98b502"
)


def _canonical_value(value: Any) -> str | None:
    """Float canonicalization: ``repr(float(v))``; ``None`` stays null."""
    if value is None:
        return None
    return repr(float(value))


def canonical_score_payload(rows: Any) -> bytes:
    """Canonical serialization of a persisted score series.

    KEEP IN SYNC — vendored byte-for-byte from
    ``renquant_pipeline/src/renquant_pipeline/kernel/walk_forward/provenance.py``
    (``canonical_score_payload``, renquant-pipeline origin/main
    ``ac98b5027c37052291e1091c368bbbddc8ced766``). A FIXED versioned copy,
    never an import (see :data:`PAYLOAD_DIGEST_IMPL`);
    ``tests/test_build_phase_a_inputs.py`` pins it against known vectors
    computed from that producer revision — those vectors ARE the
    producer/consumer compatibility contract. Rules (all load-bearing —
    extraction requires byte-equality with the emit side):

    * rows sorted by ``str(ticker)``;
    * fixed field order ``(ticker, raw_panel, mu, rank_score, sigma)``;
    * numeric values via ``repr(float(v))`` (``None`` -> JSON null);
    * one compact JSON array per row, newline-joined, UTF-8.
    """
    lines = []
    for row in sorted(rows, key=lambda r: str(r["ticker"])):
        lines.append(json.dumps(
            [str(row["ticker"])]
            + [_canonical_value(row.get(f)) for f in SCORE_PAYLOAD_FIELDS[1:]],
            separators=(",", ":"),
            ensure_ascii=True,
        ))
    return "\n".join(lines).encode("utf-8")


def score_payload_digest(rows: Any) -> str:
    """``sha256:<64 hex>`` over :func:`canonical_score_payload`."""
    return "sha256:" + hashlib.sha256(canonical_score_payload(rows)).hexdigest()


# =====================================================================
# wf_sim_provenance.v1 ledger — read + verify (design #215 §2.5)
# =====================================================================
PROVENANCE_SCHEMA_VERSION = "wf_sim_provenance.v1"
RECORD_KIND_FOLD_RESOLVED = "fold_resolved"
RECORD_KIND_SCORE_COMMITTED = "score_committed"

#: Full digest grammar (admissibility-ledger family) — the producer never
#: abbreviates (design #215 §2.2).
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Keys excluded from the duplicate-identity comparison: the audit-write
#: clock legitimately differs across idempotent re-emits (e.g. a sink
#: restarted for the same ``sim_run_id`` re-appends the same content with a
#: fresh ``emitted_at_utc``). Mirrors the sink's own ``_AUDIT_ONLY_KEYS``.
AUDIT_ONLY_KEYS = frozenset({"emitted_at_utc"})


class ProvenanceLedgerError(ValueError):
    """A structurally invalid ledger file (unparsable/mixed-run/bad schema).

    File-level corruption is a HARD error for the whole build — per-DATE
    problems are per-date rejections instead (see
    :func:`evaluate_provenance_dates`).
    """


class CrossCheckMismatchError(RuntimeError):
    """Generation-time ledger identity disagrees with independent replay.

    Raised when ``select_pit_fold`` / ``resolve_artifact_digest`` re-derive
    a DIFFERENT fold/artifact identity than the ledger recorded (or cannot
    re-derive one at all). This is a HARD error: the affected dates'
    evidence is quarantined and the build aborts before writing output —
    the reconstruction is never used as a fallback, and the ledger is never
    silently trusted over a failed independent check (design #215 §2.5.3).
    """

    def __init__(self, quarantined: dict[str, list[str]]) -> None:
        self.quarantined = dict(quarantined)
        lines = "; ".join(
            f"{d}: {', '.join(reasons)}" for d, reasons in sorted(quarantined.items())
        )
        super().__init__(
            f"cross-check mismatch — evidence quarantined for "
            f"{len(quarantined)} date(s): {lines}"
        )


@dataclass(frozen=True)
class ProvenancePair:
    """One prediction date's validated ``fold_resolved``/``score_committed``."""

    fold: dict
    committed: dict


@dataclass
class ProvenanceLedger:
    """Parsed ``wf_sim_provenance.v1`` JSONL ledger for ONE sim run."""

    path: str
    ledger_digest: str
    sim_run_id: str
    fold_records: dict[str, list[dict]]
    committed_records: dict[str, list[dict]]

    def dates(self) -> set[str]:
        return set(self.fold_records) | set(self.committed_records)


def _record_content_id(record: dict) -> str:
    """Duplicate-identity key: full content minus audit-only keys."""
    return json.dumps(
        {k: v for k, v in record.items() if k not in AUDIT_ONLY_KEYS},
        sort_keys=True, separators=(",", ":"), default=str,
    )


def load_provenance_ledger(path: Path) -> ProvenanceLedger:
    """Parse a ``wf_sim_provenance.v1`` JSONL ledger file.

    Hard errors (:class:`ProvenanceLedgerError`) — these mean the FILE is
    not a well-formed single-run ledger, so no per-date disposition is
    possible: unparsable JSON line, wrong/missing ``schema_version``,
    unknown ``record_kind``, missing ``prediction_date`` or ``sim_run_id``,
    or records from more than one ``sim_run_id`` in one file (the sink
    writes ``<sim_run_id>.jsonl`` and refuses cross-run emits).
    """
    raw = path.read_bytes()
    ledger_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    fold_records: dict[str, list[dict]] = {}
    committed_records: dict[str, list[dict]] = {}
    sim_run_id: str | None = None
    for lineno, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProvenanceLedgerError(
                f"{path}:{lineno}: unparsable JSONL line ({exc})"
            ) from exc
        if not isinstance(record, dict):
            raise ProvenanceLedgerError(
                f"{path}:{lineno}: record is not a JSON object"
            )
        if record.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
            raise ProvenanceLedgerError(
                f"{path}:{lineno}: schema_version "
                f"{record.get('schema_version')!r} != {PROVENANCE_SCHEMA_VERSION!r}"
            )
        kind = record.get("record_kind")
        if kind not in (RECORD_KIND_FOLD_RESOLVED, RECORD_KIND_SCORE_COMMITTED):
            raise ProvenanceLedgerError(
                f"{path}:{lineno}: unknown record_kind {kind!r}"
            )
        run_id = record.get("sim_run_id")
        pred_date = record.get("prediction_date")
        if not run_id or not pred_date:
            raise ProvenanceLedgerError(
                f"{path}:{lineno}: record missing sim_run_id/prediction_date"
            )
        if sim_run_id is None:
            sim_run_id = str(run_id)
        elif str(run_id) != sim_run_id:
            raise ProvenanceLedgerError(
                f"{path}:{lineno}: mixed sim_run_ids in one ledger file "
                f"({sim_run_id!r} vs {run_id!r}) — one file per sim run"
            )
        bucket = (fold_records if kind == RECORD_KIND_FOLD_RESOLVED
                  else committed_records)
        bucket.setdefault(str(pred_date), []).append(record)
    if sim_run_id is None:
        raise ProvenanceLedgerError(f"{path}: ledger contains no records")
    return ProvenanceLedger(
        path=str(path),
        ledger_digest=ledger_digest,
        sim_run_id=sim_run_id,
        fold_records=fold_records,
        committed_records=committed_records,
    )


def _reject(code: str, detail: str) -> dict[str, str]:
    """A machine-readable rejection record."""
    return {"reason_code": code, "detail": detail}


def evaluate_provenance_dates(
    ledger: ProvenanceLedger,
) -> tuple[dict[str, ProvenancePair], dict[str, dict[str, str]]]:
    """Per-date pair validation (design #215 §2.5 step 1).

    Returns ``(pairs, rejections)``: dates with a COMPLETE, self-consistent
    ``fold_resolved`` + ``score_committed`` pair, and every other ledger
    date mapped to a machine-readable rejection reason. Duplicate records
    whose content is identical modulo the audit clock are accepted as
    idempotent re-emits; differing content for the same key is a conflict.
    """
    pairs: dict[str, ProvenancePair] = {}
    rejections: dict[str, dict[str, str]] = {}
    for pred_date in sorted(ledger.dates()):
        folds = ledger.fold_records.get(pred_date, [])
        commits = ledger.committed_records.get(pred_date, [])
        if folds and not commits:
            rejections[pred_date] = _reject(
                "orphaned_fold_resolved",
                "fold_resolved present without its score_committed pair",
            )
            continue
        if commits and not folds:
            rejections[pred_date] = _reject(
                "orphaned_score_committed",
                "score_committed present without its fold_resolved pair",
            )
            continue
        if len({_record_content_id(r) for r in folds}) > 1:
            rejections[pred_date] = _reject(
                "duplicate_fold_resolved_conflict",
                f"{len(folds)} fold_resolved records with differing content "
                f"for one (sim_run_id, prediction_date) key",
            )
            continue
        if len({_record_content_id(r) for r in commits}) > 1:
            rejections[pred_date] = _reject(
                "duplicate_score_committed_conflict",
                f"{len(commits)} score_committed records with differing "
                f"content for one (sim_run_id, prediction_date) key",
            )
            continue
        fold, committed = folds[0], commits[0]

        reason = _validate_pair(fold, committed)
        if reason is not None:
            rejections[pred_date] = reason
            continue
        pairs[pred_date] = ProvenancePair(fold=fold, committed=committed)
    return pairs, rejections


def _validate_pair(fold: dict, committed: dict) -> dict[str, str] | None:
    """Content checks on one deduplicated pair; None = pass."""
    if committed.get("persisted") is not True:
        return _reject(
            "persisted_false",
            "score_committed.persisted is not true — the sim did not persist "
            "this observation to the DB Phase-A reads (design #215 §2.1)",
        )
    if committed.get("pit_violation") is True:
        return _reject(
            "pit_violation",
            "score_committed.pit_violation is true — input_watermark exceeded "
            "the simulated decision instant (design #215 §2.2)",
        )
    for fld in ("cutoff_date", "lookahead_days", "artifact_uri"):
        if fold.get(fld) in (None, ""):
            return _reject(
                "fold_record_incomplete",
                f"fold_resolved.{fld} missing/empty",
            )
    if fold.get("is_real_content_digest") is not True:
        return _reject(
            "artifact_digest_not_real_content",
            "fold_resolved.is_real_content_digest is not true — no genuine "
            "model-content identity; inadmissible for GO/KILL evidence",
        )
    fold_digest = fold.get("artifact_digest")
    if not isinstance(fold_digest, str) or not DIGEST_RE.match(fold_digest):
        return _reject(
            "artifact_digest_missing",
            f"fold_resolved.artifact_digest {fold_digest!r} is not a full "
            f"sha256:<64 hex> digest",
        )
    if committed.get("artifact_digest") != fold_digest:
        return _reject(
            "artifact_digest_echo_mismatch",
            f"score_committed.artifact_digest "
            f"{committed.get('artifact_digest')!r} != fold_resolved."
            f"artifact_digest {fold_digest!r} — pair integrity broken",
        )
    payload_digest = committed.get("score_payload_digest")
    if not isinstance(payload_digest, str) or not DIGEST_RE.match(payload_digest):
        return _reject(
            "malformed_score_payload_digest",
            f"score_committed.score_payload_digest {payload_digest!r} is not "
            f"a full sha256:<64 hex> digest",
        )
    key = committed.get("score_observation_key")
    if not isinstance(key, (list, tuple)) or len(key) != 3:
        return _reject(
            "malformed_score_observation_key",
            f"score_committed.score_observation_key {key!r} is not the "
            f"(run_id, date, run_type) triple",
        )
    n_rows = committed.get("n_rows")
    if not isinstance(n_rows, int) or isinstance(n_rows, bool) or n_rows < 0:
        return _reject(
            "malformed_n_rows",
            f"score_committed.n_rows {n_rows!r} is not a non-negative integer",
        )
    if not committed.get("score_timestamp"):
        return _reject(
            "score_timestamp_missing",
            "score_committed.score_timestamp missing — no simulated decision "
            "instant (design #215 §2.2)",
        )
    if committed.get("input_watermark") in (None, ""):
        return _reject(
            "input_watermark_missing",
            "score_committed.input_watermark is null — the emit-side PIT "
            "check could not run; extraction owns that judgement and fails "
            "closed rather than fabricating a watermark (design #215 §2.2)",
        )
    return None


def read_observation_rows(
    db_path: Path, score_observation_key: Any
) -> list[dict[str, Any]]:
    """Read ALL ``score_distribution`` rows at one observation key.

    The key is the recorded ``(run_id, date, run_type)`` triple; ``IS ?``
    keeps a null ``run_type`` matchable. Every canonical-payload field is
    selected, with NO null filtering — the digest binds the FULL persisted
    series, not the score-column subset.
    """
    run_id, date_str, run_type = score_observation_key
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ticker, raw_panel, mu, rank_score, sigma
            FROM score_distribution
            WHERE run_id = ? AND date = ? AND run_type IS ?
            """,
            (run_id, date_str, run_type),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def verify_committed_observation(
    db_path: Path, pair: ProvenancePair
) -> tuple[list[dict[str, Any]] | None, dict[str, str] | None]:
    """Design #215 §2.5 step 2: read-back + digest/n_rows equality.

    Returns ``(rows, None)`` when the sim DB observation at the recorded
    ``score_observation_key`` matches the committed ``score_payload_digest``
    and ``n_rows``; otherwise ``(None, rejection)``.
    """
    committed = pair.committed
    rows = read_observation_rows(db_path, committed["score_observation_key"])
    if len(rows) != int(committed["n_rows"]):
        return None, _reject(
            "n_rows_mismatch",
            f"score_distribution has {len(rows)} row(s) at "
            f"{committed['score_observation_key']!r}, ledger committed "
            f"n_rows={committed['n_rows']}",
        )
    recomputed = score_payload_digest(rows)
    if recomputed != committed["score_payload_digest"]:
        return None, _reject(
            "score_payload_digest_mismatch",
            f"recomputed {recomputed} != committed "
            f"{committed['score_payload_digest']} — the DB observation is "
            f"not the one the sim committed",
        )
    return rows, None


# =====================================================================
# Walk-forward fold reconstruction — CROSS-CHECK ONLY (design #215 §2.5.3)
# =====================================================================
@dataclass(frozen=True)
class WalkForwardFold:
    """One walk-forward retrain fold's point-in-time provenance."""

    cutoff_date: str
    lookahead_days: int
    artifact_uri: str
    trained_date: str = ""
    calibrator_uri: str = ""

    def effective_train_cutoff_date(self) -> str:
        """The effective train cutoff = ``cutoff_date + BDay(lookahead_days)``.

        BUSINESS days (``pandas.tseries.offsets.BDay``), not calendar days —
        matching the real ``WalkForwardModelLoader.entry_as_of`` /
        ``oos_ic_export`` semantics. A prediction date is only PIT-clean for
        this fold if it is STRICTLY after this effective cutoff.
        """
        eff = pd.Timestamp(self.cutoff_date) + BDay(int(self.lookahead_days))
        return str(eff.date())


def load_folds(manifest_path: Path) -> list[WalkForwardFold]:
    """Load walk-forward folds from a WF manifest, sorted ascending by cutoff.

    Reads the ``retrains[]`` array; each entry must carry ``cutoff_date`` and
    ``lookahead_days``. Missing ``lookahead_days`` is a hard error (it is the
    load-bearing input to the BDay PIT gate; silently defaulting it would
    fabricate provenance).
    """
    manifest = json.loads(manifest_path.read_text())
    retrains = manifest.get("retrains")
    if not isinstance(retrains, list) or not retrains:
        raise ValueError(
            f"manifest {manifest_path} has no non-empty 'retrains' array"
        )
    folds: list[WalkForwardFold] = []
    for i, r in enumerate(retrains):
        cutoff = r.get("cutoff_date")
        lookahead = r.get("lookahead_days")
        if not cutoff:
            raise ValueError(f"retrain fold {i} missing cutoff_date")
        if lookahead is None:
            raise ValueError(
                f"retrain fold {i} (cutoff {cutoff}) missing lookahead_days -- "
                f"cannot compute the BDay PIT cutoff without it"
            )
        folds.append(
            WalkForwardFold(
                cutoff_date=str(cutoff),
                lookahead_days=int(lookahead),
                artifact_uri=str(r.get("artifact_uri", "")),
                trained_date=str(r.get("trained_date", "")),
                calibrator_uri=str(r.get("calibrator_uri", "")),
            )
        )
    folds.sort(key=lambda f: f.cutoff_date)
    return folds


def select_pit_fold(
    folds: list[WalkForwardFold], prediction_date: str
) -> WalkForwardFold | None:
    """Re-derive the PIT-clean walk-forward fold for a prediction date.

    CROSS-CHECK ONLY (design #215 §2.5.3): the ledger's ``fold_resolved``
    record is the identity of record; this replay exists to catch a
    corrupted/mistargeted ledger, and a disagreement is a HARD error —
    never a fallback.

    Returns the LATEST fold whose ``cutoff_date + BDay(lookahead_days)`` is
    STRICTLY before ``prediction_date`` (the entry active as-of that date),
    or ``None`` when no fold is PIT-clean. ``folds`` must be sorted
    ascending by ``cutoff_date`` (as returned by :func:`load_folds`).
    """
    pred = pd.Timestamp(prediction_date)
    chosen: WalkForwardFold | None = None
    for f in folds:
        eff = pd.Timestamp(f.cutoff_date) + BDay(int(f.lookahead_days))
        if eff < pred:
            chosen = f
        else:
            # effective cutoff is monotonic non-decreasing in cutoff_date;
            # once it reaches/passes the prediction date no later fold is
            # eligible either.
            break
    return chosen


def resolve_artifact_digest(
    fold: WalkForwardFold, artifact_base_dir: Path | None
) -> tuple[str, str, bool]:
    """Re-hash a fold's model artifact. CROSS-CHECK ONLY (design #215 §2.5.3).

    Returns ``(fingerprint, locator, is_real_content_digest)``.

    When the fold's ``artifact_uri`` resolves to a readable file under
    ``artifact_base_dir``, the fingerprint is the SHA-256 of that file's
    exact bytes and ``is_real_content_digest`` is True. Otherwise a
    deterministic provenance-bound surrogate is returned with
    ``is_real_content_digest=False`` — the caller treats that as a FAILED
    cross-check (the independent re-hash could not run), never as an
    identity and never as a fallback.
    """
    if artifact_base_dir is not None and fold.artifact_uri:
        candidate = artifact_base_dir / fold.artifact_uri
        if candidate.is_file():
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            return f"sha256:{digest}", str(candidate), True
    # Deterministic provenance-bound fallback (NOT a content digest).
    provenance_key = "|".join(
        [fold.cutoff_date, fold.artifact_uri, fold.trained_date]
    ).encode()
    digest = hashlib.sha256(provenance_key).hexdigest()
    return f"sha256:{digest}", f"provenance_bound:{fold.artifact_uri}", False


def cross_check_date(
    pred_date: str,
    pair: ProvenancePair,
    folds: list[WalkForwardFold],
    artifact_base_dir: Path | None,
) -> list[str]:
    """Independent replay vs the ledger identity; returns mismatch details.

    An empty list = the cross-check PASSED. Any entry = quarantine the
    date (the caller aggregates into :class:`CrossCheckMismatchError`).
    """
    mismatches: list[str] = []
    fold_rec = pair.fold
    derived = select_pit_fold(folds, pred_date)
    if derived is None:
        mismatches.append(
            f"select_pit_fold re-derived NO PIT-clean fold, ledger recorded "
            f"cutoff_date={fold_rec['cutoff_date']!r}"
        )
        return mismatches
    if derived.cutoff_date != str(fold_rec["cutoff_date"]):
        mismatches.append(
            f"cutoff_date: re-derived {derived.cutoff_date!r} != ledger "
            f"{fold_rec['cutoff_date']!r}"
        )
    if int(derived.lookahead_days) != int(fold_rec["lookahead_days"]):
        mismatches.append(
            f"lookahead_days: re-derived {derived.lookahead_days} != ledger "
            f"{fold_rec['lookahead_days']}"
        )
    if derived.artifact_uri != str(fold_rec["artifact_uri"]):
        mismatches.append(
            f"artifact_uri: re-derived {derived.artifact_uri!r} != ledger "
            f"{fold_rec['artifact_uri']!r}"
        )
    if mismatches:
        return mismatches
    fp, locator, is_real = resolve_artifact_digest(derived, artifact_base_dir)
    if not is_real:
        mismatches.append(
            f"resolve_artifact_digest could not re-hash the artifact "
            f"({locator}) — the independent content check cannot run"
        )
    elif fp != fold_rec["artifact_digest"]:
        mismatches.append(
            f"artifact_digest: re-hashed {fp} != ledger "
            f"{fold_rec['artifact_digest']} ({locator})"
        )
    return mismatches


# =====================================================================
# Sim DB extraction
# =====================================================================
def db_digest(db_path: Path) -> str:
    """Content digest of a source DB file (audit provenance)."""
    return f"sha256:{hashlib.sha256(db_path.read_bytes()).hexdigest()}"


def read_db_dates(db_path: Path, *, start_date: str, end_date: str) -> list[str]:
    """Distinct ``score_distribution`` dates in range (honesty reporting)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT date FROM score_distribution
            WHERE date >= ? AND date <= ? ORDER BY date
            """,
            (start_date, end_date),
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def read_forward_returns(
    db_path: Path,
    *,
    label_column: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Read forward-return labels from ``ticker_forward_returns``."""
    if label_column not in {"fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d", "fwd_60d"}:
        raise ValueError(
            f"--label-column={label_column!r} is not an allowed "
            f"ticker_forward_returns column"
        )
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT as_of_date, ticker, {label_column} AS fwd_return
            FROM ticker_forward_returns
            WHERE as_of_date >= ? AND as_of_date <= ?
              AND {label_column} IS NOT NULL
            ORDER BY as_of_date, ticker
            """,
            (start_date, end_date),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def write_returns_csv(returns: list[dict[str, Any]], output_path: Path) -> str:
    """Write the shared forward-returns CSV; return its content digest.

    Columns are ``date,ticker,fwd_return`` -- exactly what
    :func:`phase_a_runner.load_forward_returns` reads.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["date,ticker,fwd_return\n"]
    for r in returns:
        lines.append(f"{r['as_of_date']},{r['ticker']},{r['fwd_return']}\n")
    raw = "".join(lines).encode()
    output_path.write_bytes(raw)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


# =====================================================================
# Score-file payloads (admissibility schema)
# =====================================================================
@dataclass
class LabelContext:
    """Per-date label provenance shared across score payloads."""

    has_realized_labels_by_date: dict[str, bool]
    label_artifact_ref_by_date: dict[str, str]
    label_observation_end_by_date: dict[str, str]


def build_score_payload(
    dt_str: str,
    scores: dict[str, float],
    *,
    expert_name: str,
    pair: ProvenancePair,
    sim_run_id: str,
    labels: LabelContext,
    score_column: str,
    source_db_digest: str,
    source_db_path: str,
    manifest_path: str,
    provenance_ledger_path: str,
    provenance_ledger_digest: str,
) -> dict[str, Any]:
    """Build one date's score payload in the admissibility-ledger schema.

    EVERY identity/time field is copied VERBATIM from the generation-time
    ``wf_sim_provenance.v1`` records — nothing is recomputed here (design
    #215 §2.5):

    * ``training_cutoff`` = ``fold_resolved.cutoff_date``;
    * ``model_content_sha256`` = ``fold_resolved.artifact_digest`` (a real
      content digest — enforced upstream by pair validation);
    * ``score_timestamp`` = ``score_committed.score_timestamp`` (the
      SIMULATED decision instant, design §2.2 — not the audit clock, not a
      recomputed session close);
    * ``as_of_date`` / ``data_watermark`` =
      ``score_committed.input_watermark`` (the max event time of the
      feature store actually served; the emit-side PIT invariant
      ``input_watermark <= score_timestamp`` held, or the date was
      rejected before reaching here).
    """
    fold = pair.fold
    committed = pair.committed
    return {
        "date": dt_str,
        "expert": expert_name,
        "scores": scores,
        # -- fields read by admissibility_ledger.extract_metadata_from_score --
        "as_of_date": committed["input_watermark"],
        "data_watermark": committed["input_watermark"],
        "score_timestamp": committed["score_timestamp"],
        "training_cutoff": fold["cutoff_date"],
        "model_content_sha256": fold["artifact_digest"],
        "has_realized_labels": labels.has_realized_labels_by_date.get(dt_str, False),
        "label_artifact_ref": labels.label_artifact_ref_by_date.get(dt_str, "MISSING"),
        "label_observation_end": labels.label_observation_end_by_date.get(dt_str, "MISSING"),
        # -- audit-trail / extended provenance --
        "metadata": {
            "classification": "EXPLORATORY_ONLY",
            "score_column": score_column,
            "n_tickers": len(scores),
            "query_schema_version": QUERY_SCHEMA_VERSION,
            "provenance": {
                "schema_version": PROVENANCE_SCHEMA_VERSION,
                "sim_run_id": sim_run_id,
                "score_observation_key": list(committed["score_observation_key"]),
                "score_payload_digest": committed["score_payload_digest"],
                "n_observation_rows": int(committed["n_rows"]),
                "ledger_path": provenance_ledger_path,
                "ledger_digest": provenance_ledger_digest,
                "seed": fold.get("seed"),
                "revision_pins": fold.get("revision_pins"),
            },
            "walkforward_fold": {
                "cutoff_date": fold["cutoff_date"],
                "lookahead_days": fold["lookahead_days"],
                "effective_train_cutoff_date": fold.get("effective_train_cutoff_date"),
                "artifact_uri": fold["artifact_uri"],
                "trained_date": fold.get("trained_date"),
                "calibrator_uri": fold.get("calibrator_uri"),
                "calibrator_digest": fold.get("calibrator_digest"),
                "manifest_path": fold.get("manifest_path"),
                "manifest_digest": fold.get("manifest_digest"),
                "family": fold.get("family"),
                "fingerprint_schema": fold.get("fingerprint_schema"),
            },
            "model_fingerprint_is_real_content_digest": True,
            "pit_contract": (
                "all identity/time fields are copied verbatim from "
                "generation-time wf_sim_provenance.v1 records "
                "(fold_resolved + score_committed, pair-validated, "
                "score_payload_digest re-verified against the sim DB); "
                "select_pit_fold/resolve_artifact_digest ran only as "
                "independent cross-checks and agreed (design #215 §2.5)."
            ),
            "source_db_path": source_db_path,
            "source_db_digest": source_db_digest,
            "source_manifest_path": manifest_path,
        },
    }


def write_score_files(
    scores_by_date: dict[str, dict[str, float]],
    pair_by_date: dict[str, ProvenancePair],
    output_dir: Path,
    *,
    expert_name: str,
    sim_run_id: str,
    labels: LabelContext,
    score_column: str,
    source_db_digest: str,
    source_db_path: str,
    manifest_path: str,
    provenance_ledger_path: str,
    provenance_ledger_digest: str,
) -> dict[str, str]:
    """Write per-date score JSON files; return ``{date: file_digest}``."""
    score_dir = output_dir / expert_name
    score_dir.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for dt_str in sorted(scores_by_date):
        payload = build_score_payload(
            dt_str,
            scores_by_date[dt_str],
            expert_name=expert_name,
            pair=pair_by_date[dt_str],
            sim_run_id=sim_run_id,
            labels=labels,
            score_column=score_column,
            source_db_digest=source_db_digest,
            source_db_path=source_db_path,
            manifest_path=manifest_path,
            provenance_ledger_path=provenance_ledger_path,
            provenance_ledger_digest=provenance_ledger_digest,
        )
        raw = json.dumps(payload, indent=2, sort_keys=True).encode()
        out_path = score_dir / f"{dt_str}.json"
        out_path.write_bytes(raw)
        digests[dt_str] = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    return digests


@dataclass
class BuildManifest:
    """Summary manifest for one converter run (audit record)."""

    expert_name: str
    sim_db_path: str
    sim_db_digest: str
    wf_manifest_path: str
    provenance_ledger_path: str
    provenance_ledger_digest: str
    sim_run_id: str
    score_column: str
    label_column: str
    start_date: str
    end_date: str
    payload_digest_impl: str
    n_ledger_dates: int
    n_ledger_dates_in_range: int
    n_dates_admissible: int
    n_dates_rejected: int
    n_db_dates_without_provenance: int
    n_cross_checked: int
    n_dates_written: int
    n_folds: int
    universe_size: int
    universe_source: str
    n_return_records: int
    returns_file_path: str
    returns_file_digest: str
    label_horizon_days: int
    query_schema_version: str
    created_at: str
    output_dir: str
    rejected_dates: dict[str, dict[str, str]] = field(default_factory=dict)
    score_file_digests: dict[str, str] = field(default_factory=dict)
    ledger_admitted: int = 0
    ledger_rejected: int = 0
    ledger_fingerprint: str = ""
    ledger_path: str = ""


# =====================================================================
# Orchestration
# =====================================================================
def run_build(
    *,
    sim_db: Path,
    provenance_ledger: Path,
    manifest_file: Path,
    output_dir: Path,
    expert_name: str,
    score_column: str,
    start_date: str,
    end_date: str,
    label_column: str = "fwd_60d",
    label_horizon_days: int = 60,
    artifact_base_dir: Path | None = None,
    universe_file: Path | None = None,
    decision_schedule: DecisionSchedule = US_EQUITY_CLOSE,
    build_admissibility_ledger: bool = True,
) -> BuildManifest:
    """Build the Phase-A score-dir + returns CSV for one scorer's WF sim.

    Identity source: the ``wf_sim_provenance.v1`` ledger, ONLY. The WF
    manifest + artifact tree serve exclusively as the independent
    cross-check (a disagreement raises :class:`CrossCheckMismatchError`
    BEFORE any output is written).
    """
    validate_score_column(score_column)

    # Default: resolve fold artifact_uris relative to the manifest's
    # renquant_104 root (manifest lives at <root>/artifacts/sim/<manifest>).
    if artifact_base_dir is None:
        artifact_base_dir = manifest_file.parent.parent.parent

    folds = load_folds(manifest_file)
    print(f"Loaded {len(folds)} walk-forward folds "
          f"({folds[0].cutoff_date} .. {folds[-1].cutoff_date}) "
          f"[cross-check input only]")

    # ---- §2.5 step 1: ledger pair validation --------------------------------
    ledger = load_provenance_ledger(provenance_ledger)
    all_pairs, rejections = evaluate_provenance_dates(ledger)
    n_ledger_dates = len(ledger.dates())
    in_range = lambda d: start_date <= d <= end_date  # noqa: E731
    pairs = {d: p for d, p in all_pairs.items() if in_range(d)}
    rejections = {d: r for d, r in rejections.items() if in_range(d)}
    n_ledger_dates_in_range = len(pairs) + len(rejections)
    print(f"Provenance ledger {ledger.path} (sim_run_id={ledger.sim_run_id}): "
          f"{n_ledger_dates} date(s), {n_ledger_dates_in_range} in "
          f"[{start_date}, {end_date}], {len(pairs)} complete pair(s), "
          f"{len(rejections)} rejected "
          f"(payload digest impl: {PAYLOAD_DIGEST_IMPL})")

    # ---- §2.5 step 2: read-back + digest/n_rows verification ----------------
    rows_by_date: dict[str, list[dict[str, Any]]] = {}
    for pred_date in sorted(pairs):
        rows, rejection = verify_committed_observation(sim_db, pairs[pred_date])
        if rejection is not None:
            rejections[pred_date] = rejection
            del pairs[pred_date]
        else:
            rows_by_date[pred_date] = rows

    # Honesty reporting: sim-DB dates in range with NO ledger record are
    # inadmissible by construction (no generation-time provenance exists —
    # e.g. the entire pre-#531 sim history). Recorded, never silently skipped.
    ledger_dates_in_range = {d for d in ledger.dates() if in_range(d)}
    for db_date in read_db_dates(sim_db, start_date=start_date, end_date=end_date):
        if db_date not in ledger_dates_in_range:
            rejections[db_date] = _reject(
                "no_provenance_record",
                "score_distribution rows exist but the wf_sim_provenance.v1 "
                "ledger has no record for this date — pre-provenance history "
                "is permanently inadmissible through this converter",
            )
    n_db_dates_without_provenance = sum(
        1 for r in rejections.values()
        if r["reason_code"] == "no_provenance_record"
    )

    # ---- §2.5 step 3: independent cross-check (HARD; never a fallback) ------
    quarantined: dict[str, list[str]] = {}
    for pred_date in sorted(pairs):
        mismatches = cross_check_date(
            pred_date, pairs[pred_date], folds, artifact_base_dir
        )
        if mismatches:
            quarantined[pred_date] = mismatches
    if quarantined:
        raise CrossCheckMismatchError(quarantined)
    n_cross_checked = len(pairs)
    print(f"Cross-check passed for {n_cross_checked} date(s) "
          f"(select_pit_fold + resolve_artifact_digest agree with the ledger)")

    # ---- score extraction from the VERIFIED observations --------------------
    scores_by_date: dict[str, dict[str, float]] = {}
    for pred_date in sorted(pairs):
        scores = {
            str(r["ticker"]): float(r[score_column])
            for r in rows_by_date[pred_date]
            if r[score_column] is not None
        }
        if not scores:
            rejections[pred_date] = _reject(
                "no_scores_in_column",
                f"the verified observation has no non-null {score_column!r} "
                f"values",
            )
            del pairs[pred_date]
        else:
            scores_by_date[pred_date] = scores

    if rejections:
        counts: dict[str, int] = {}
        for r in rejections.values():
            counts[r["reason_code"]] = counts.get(r["reason_code"], 0) + 1
        print(f"Rejected {len(rejections)} date(s): "
              + ", ".join(f"{c}x {code}" for code, c in sorted(counts.items())))

    if not scores_by_date:
        raise ValueError(
            "no admissible-vintage dates: no date in range has a complete, "
            "verified wf_sim_provenance.v1 pair backed by a matching sim-DB "
            "observation (fail-closed). Pre-provenance sim history is "
            "inadmissible by design — rerun the sim with the provenance sink "
            "enabled (post-#531) to produce admissible evidence."
        )

    # ---- labels / returns ---------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    returns = read_forward_returns(
        sim_db, label_column=label_column,
        start_date=start_date, end_date=end_date,
    )
    returns_path = output_dir / "returns.csv"
    returns_digest = write_returns_csv(returns, returns_path)
    print(f"Wrote {len(returns)} forward-return record(s) to {returns_path}")

    labeled_dates = {r["as_of_date"] for r in returns}
    label_ref = f"{returns_digest}@{returns_path.name}"
    labels = LabelContext(
        has_realized_labels_by_date={
            d: d in labeled_dates for d in scores_by_date
        },
        label_artifact_ref_by_date={
            d: (label_ref if d in labeled_dates else "MISSING")
            for d in scores_by_date
        },
        label_observation_end_by_date={
            d: (
                (date.fromisoformat(d) + timedelta(days=label_horizon_days)).isoformat()
                if d in labeled_dates
                else "MISSING"
            )
            for d in scores_by_date
        },
    )

    src_db_digest = db_digest(sim_db)
    digests = write_score_files(
        scores_by_date, pairs, output_dir,
        expert_name=expert_name,
        sim_run_id=ledger.sim_run_id,
        labels=labels,
        score_column=score_column,
        source_db_digest=src_db_digest,
        source_db_path=str(sim_db),
        manifest_path=str(manifest_file),
        provenance_ledger_path=ledger.path,
        provenance_ledger_digest=ledger.ledger_digest,
    )
    print(f"Wrote {len(digests)} per-date score file(s) to "
          f"{output_dir / expert_name}")

    # Universe: explicit file, else the union of scored tickers (a proxy --
    # missingness/coverage in any ledger built later is relative to it).
    if universe_file is not None:
        universe_tickers = sorted(
            line.strip()
            for line in universe_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )
        universe_source = f"file:{universe_file}"
    else:
        universe_tickers = sorted(
            {t for s in scores_by_date.values() for t in s}
        )
        universe_source = (
            "union_of_scored_tickers (no --universe-file: the union of tickers "
            "this sim scored, NOT the true trading universe; ledger "
            "missingness/coverage is relative to this proxy)"
        )
    universe_path = output_dir / expert_name / "universe.txt"
    universe_path.write_text("\n".join(universe_tickers) + "\n")

    manifest = BuildManifest(
        expert_name=expert_name,
        sim_db_path=str(sim_db),
        sim_db_digest=src_db_digest,
        wf_manifest_path=str(manifest_file),
        provenance_ledger_path=ledger.path,
        provenance_ledger_digest=ledger.ledger_digest,
        sim_run_id=ledger.sim_run_id,
        score_column=score_column,
        label_column=label_column,
        start_date=start_date,
        end_date=end_date,
        payload_digest_impl=PAYLOAD_DIGEST_IMPL,
        n_ledger_dates=n_ledger_dates,
        n_ledger_dates_in_range=n_ledger_dates_in_range,
        n_dates_admissible=len(scores_by_date),
        n_dates_rejected=len(rejections),
        n_db_dates_without_provenance=n_db_dates_without_provenance,
        n_cross_checked=n_cross_checked,
        n_dates_written=len(digests),
        n_folds=len(folds),
        universe_size=len(universe_tickers),
        universe_source=universe_source,
        n_return_records=len(returns),
        returns_file_path=str(returns_path),
        returns_file_digest=returns_digest,
        label_horizon_days=label_horizon_days,
        query_schema_version=QUERY_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        output_dir=str(output_dir),
        rejected_dates=dict(sorted(rejections.items())),
        score_file_digests=digests,
    )

    # Verify the produced score-dir loads through the CANONICAL validator.
    # This converter does not decide admission itself -- it defers to
    # admissibility_ledger.build_ledger (the SAME loader/validator Phase A
    # uses). Reported counts are the validator's verdict.
    if build_admissibility_ledger:
        cal_start = (date.fromisoformat(min(scores_by_date)) - timedelta(days=7)).isoformat()
        cal_end = (date.fromisoformat(max(scores_by_date)) + timedelta(days=7)).isoformat()
        session_calendar = build_exchange_session_calendar(cal_start, cal_end)
        # Per-expert output isolation (folded in from model#66). The
        # admissibility ledger and its calendar evidence are expert-specific
        # evidence (built from THIS expert's per-date score dir). Writing
        # them to the shared output_dir ROOT means a second expert's build
        # into the same output_dir clobbers the first expert's ledger (both
        # -> output_dir/admissibility_ledger.json and
        # output_dir/calendar_evidence.json). Co-locate them under the
        # per-expert score dir so multiple experts can target one output_dir
        # without cross-expert clobber; the ledger's calendar-evidence
        # locator (a bare filename) stays valid because both files sit in
        # the same directory. The shared forward-returns CSV stays at the
        # root -- it is expert-independent label data by design.
        expert_output_dir = output_dir / expert_name
        expert_output_dir.mkdir(parents=True, exist_ok=True)
        expert_spec = ExpertSpec(name=expert_name, score_dir=expert_output_dir)
        cal_evidence = build_calendar_evidence(
            session_calendar, calendar_name="NYSE", query_range=(cal_start, cal_end),
        )
        cal_evidence_path = write_calendar_evidence(cal_evidence, expert_output_dir)

        def _loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            candidate = expert.score_dir / f"{dt}.json"
            if candidate.exists():
                result = load_score_file(candidate)
                if result is not None:
                    data, file_digest = result
                    meta = extract_metadata_from_score(data, expert)
                    meta["score_artifact_digest"] = file_digest
                    return meta
            return {
                "model_fingerprint": "MISSING",
                "training_cutoff": "MISSING",
                "feature_data_cutoff": "MISSING",
                "score_timestamp": "MISSING",
                "score_artifact_digest": "MISSING",
                "scored_count": 0,
            }

        prediction_dates = sorted(digests)
        ledger_verdict = build_ledger(
            [expert_spec], prediction_dates, universe_tickers,
            score_loader=_loader,
            decision_schedule=decision_schedule,
            session_calendar=session_calendar,
            calendar_evidence=cal_evidence,
            calendar_evidence_locator_str=cal_evidence_path.name,
            require_realized_labels=True,
            label_horizon_days=label_horizon_days,
        )
        ledger_path = write_ledger(ledger_verdict, expert_output_dir)
        stats = ledger_verdict.summary.get("per_expert", {}).get(expert_name, {})
        manifest.ledger_admitted = stats.get("admitted", 0)
        manifest.ledger_rejected = stats.get("rejected", 0)
        manifest.ledger_fingerprint = ledger_verdict.ledger_fingerprint
        manifest.ledger_path = str(ledger_path)
        print(f"Canonical admissibility ledger: "
              f"{manifest.ledger_admitted} admitted / "
              f"{manifest.ledger_admitted + manifest.ledger_rejected} evaluated "
              f"(fingerprint {ledger_verdict.ledger_fingerprint})")

    manifest_out = output_dir / f"build_manifest_{expert_name}.json"
    manifest_out.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    print(f"Build manifest written to {manifest_out}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a walk-forward sim DB + its wf_sim_provenance.v1 ledger "
            "into Phase A ensemble inputs (per-date score-dir + shared "
            "returns CSV). The ledger is the ONLY fold/artifact identity "
            "source; the WF manifest + artifact tree are independent "
            "cross-checks (design #215 §2.5)."
        )
    )
    parser.add_argument("--sim-db", required=True, type=Path,
                        help="Path to the walk-forward sim DB (score_distribution)")
    parser.add_argument("--provenance-ledger", required=True, type=Path,
                        help="Path to the wf_sim_provenance.v1 JSONL ledger "
                             "(data/wf_provenance/<sim_run_id>.jsonl) the sim "
                             "emitted at generation time. REQUIRED — sim "
                             "history without a ledger is inadmissible.")
    parser.add_argument("--manifest-file", required=True, type=Path,
                        help="Path to the walk-forward manifest JSON "
                             "(retrains[]) — cross-check input only")
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Output directory (never a production path)")
    parser.add_argument("--expert-name", required=True,
                        help="Expert/scorer name, e.g. xgb or patchtst")
    parser.add_argument("--score-column", default="raw_panel",
                        help=f"score_distribution column. Allowed: "
                             f"{sorted(ALLOWED_SCORE_COLUMNS)} (default: raw_panel)")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--label-column", default="fwd_60d",
                        help="ticker_forward_returns label column (default: fwd_60d)")
    parser.add_argument("--label-horizon-days", type=int, default=60,
                        help="Label horizon in calendar days (default: 60)")
    parser.add_argument("--artifact-base-dir", type=Path, default=None,
                        help="Base dir to resolve fold artifact_uris for the "
                             "cross-check re-hash (default: manifest's "
                             "<root>/artifacts/sim -> <root>)")
    parser.add_argument("--universe-file", type=Path, default=None,
                        help="Optional universe ticker list; default is the "
                             "union of scored tickers (a proxy)")
    parser.add_argument("--no-ledger", action="store_true",
                        help="Skip building the canonical admissibility ledger")
    args = parser.parse_args(argv)

    try:
        validate_score_column(args.score_column)
    except ScoreColumnNotAllowedError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if not args.sim_db.exists():
        print(f"ERROR: sim DB not found: {args.sim_db}", file=sys.stderr)
        return 2
    if not args.provenance_ledger.exists():
        print(f"ERROR: provenance ledger not found: {args.provenance_ledger}. "
              f"A wf_sim_provenance.v1 JSONL ledger is REQUIRED — sim runs "
              f"predating the provenance sink are inadmissible by design.",
              file=sys.stderr)
        return 2
    if not args.manifest_file.exists():
        print(f"ERROR: manifest not found: {args.manifest_file}", file=sys.stderr)
        return 2

    try:
        manifest = run_build(
            sim_db=args.sim_db,
            provenance_ledger=args.provenance_ledger,
            manifest_file=args.manifest_file,
            output_dir=args.output_dir,
            expert_name=args.expert_name,
            score_column=args.score_column,
            start_date=args.start_date,
            end_date=args.end_date,
            label_column=args.label_column,
            label_horizon_days=args.label_horizon_days,
            artifact_base_dir=args.artifact_base_dir,
            universe_file=args.universe_file,
            build_admissibility_ledger=not args.no_ledger,
        )
    except (ProvenanceLedgerError, CrossCheckMismatchError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    print(
        f"\nDONE: expert={manifest.expert_name} "
        f"wrote={manifest.n_dates_written} "
        f"rejected={manifest.n_dates_rejected} "
        f"(no_provenance={manifest.n_db_dates_without_provenance}) "
        f"admitted={manifest.ledger_admitted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
