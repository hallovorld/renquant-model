"""Extract historical panel scores from runs.alpaca.db for Phase A ensemble experiments.

The daily pipeline persists candidate scores to runs.alpaca.db but never
exports them as per-date JSON files. The Phase A runner
(:mod:`phase_a_runner`) consumes per-date ``{scores: {ticker: mu}}`` JSON
files verified against an admissibility ledger. This script bridges the gap.

For each historical trading day, it:
  1. Resolves the AS-OF ELIGIBLE 'live' pipeline run for that date -- the
     one committed at-or-before that date's own NYSE session-close cutoff
     (see :func:`select_asof_runs`). A date with no such run (either no
     live run exists, or every live run for it was committed AFTER its own
     session closed -- e.g. a later reprocessing/backfill insert) is
     EXCLUDED with a documented reason, never silently substituted.
  2. Reads the candidate-role score column (validated against a fixed
     allowlist) for that ONE eligible run.
  3. Writes a per-date CANDIDATE EVIDENCE JSON file carrying full
     point-in-time provenance (source run id/timestamp, code revision,
     model/scorer identity, calendar/query-schema version, source DB
     digest) -- never a self-attested ``admitted: true``.
  4. Exports forward returns as a CSV for the runner.
  5. Defers the actual admission decision to the CANONICAL validator
     (:func:`admissibility_ledger.build_ledger` /
     :func:`admissibility_ledger.validate_expert_date`) by building a real
     ledger from the just-written candidate evidence -- this script does
     not decide admissibility itself.

All output goes to an experiment-specific directory, never to production
paths. The output carries EXPLORATORY_ONLY classification.

Security / provenance notes (Codex review 2026-07-14 on model#54):

* ``--score-column`` is validated against :data:`ALLOWED_SCORE_COLUMNS`
  (the real numeric candidate-scoring columns in ``candidate_scores`` --
  see ``renquant-pipeline/src/renquant_pipeline/kernel/persistence.py``'s
  ``candidate_scores`` schema) BEFORE it ever reaches a SQL string. An
  unrecognized value is rejected with a clear error, not interpolated.
* The as-of contract: for prediction date ``D``, only a ``run_type='live'``
  ``pipeline_runs`` row whose ``created_at`` (the run's committed/available
  timestamp -- SQLite's ``CURRENT_TIMESTAMP``, UTC) is ``<=`` ``D``'s real
  NYSE session-close cutoff (holiday/early-close aware, via
  ``pandas_market_calendars`` -- the SAME primitive
  ``admissibility_ledger.py`` uses) is eligible. ``ORDER BY created_at DESC
  LIMIT 1`` alone is NOT sufficient proof of point-in-time availability: it
  can select a rerun committed after the target date's own decision time,
  which is exactly look-ahead. See :func:`select_asof_runs`.
* Because ``runs.alpaca.db`` does not persist ``training_cutoff`` or a
  model-content fingerprint anywhere in ``pipeline_runs``/
  ``candidate_scores``, every backfilled record honestly carries
  ``training_cutoff="MISSING"`` and ``model_content_sha256="MISSING"``.
  The canonical validator therefore rejects these records today -- this is
  INTENDED fail-closed behavior exposing a genuine data-provenance gap, not
  a bug in this script. Making backfilled scores admissible requires a
  future enhancement to persist those fields at write time; fabricating
  them here would be exactly the "manufactured admitted: true" problem
  this rewrite exists to remove.

Usage::

    python -m experiments.ensemble_phase0.backfill_scores \\
        --runs-db /path/to/runs.alpaca.db \\
        --output-dir experiments/ensemble_phase0/output/backfill \\
        --expert-name xgb \\
        --start-date 2024-01-02 \\
        --end-date 2026-07-13
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from experiments.ensemble_phase0.admissibility_ledger import (
    US_EQUITY_CLOSE,
    DecisionSchedule,
    ExpertSpec,
    SessionCalendar,
    build_calendar_evidence,
    build_exchange_session_calendar,
    build_ledger,
    extract_metadata_from_score,
    load_score_file,
    write_calendar_evidence,
    write_ledger,
)

#: Query/schema-version tag persisted in every provenance record. Bump this
#: whenever the extraction SQL or the as-of contract's semantics change, so
#: an old backfill's provenance is distinguishable from a new one even if
#: the score/manifest JSON shapes otherwise look similar.
QUERY_SCHEMA_VERSION = "backfill_scores.runs_alpaca_db.v2_asof_gated"

#: The real numeric candidate-scoring columns in ``candidate_scores``
#: (renquant-pipeline ``kernel/persistence.py`` schema). ``--score-column``
#: is validated against this FIXED allowlist before it ever reaches a SQL
#: string -- deliberately excludes bookkeeping/sizing columns
#: (``selected``, ``blocked_by``, ``model_type``, ``active_scorer``,
#: ``qp_*``, ``kelly_target_pct``, ``expected_return*``, ...) which are not
#: "the panel score" concept this backfill extracts.
ALLOWED_SCORE_COLUMNS = frozenset({
    "mu", "raw_score", "panel_score", "rank_score", "rs_score", "sigma",
})


class ScoreColumnNotAllowedError(ValueError):
    """Raised when ``--score-column`` is not on :data:`ALLOWED_SCORE_COLUMNS`."""


def validate_score_column(score_column: str) -> str:
    """Validate ``score_column`` against the fixed allowlist.

    Returns the validated column name unchanged, or raises
    :class:`ScoreColumnNotAllowedError` (a SQL-injection guard: an
    unrecognized value is rejected here and NEVER reaches a query string).
    """
    if score_column not in ALLOWED_SCORE_COLUMNS:
        raise ScoreColumnNotAllowedError(
            f"--score-column={score_column!r} is not an allowed "
            f"candidate_scores column. Allowed: {sorted(ALLOWED_SCORE_COLUMNS)}. "
            f"Refusing to build a SQL query from an unvalidated column name."
        )
    return score_column


@dataclass
class RunSelection:
    """The single as-of-eligible 'live' pipeline run selected for one date."""

    run_id: str
    run_date: str
    created_at_utc: str  # ISO-8601, UTC -- this run's score-availability timestamp
    commit_sha: str | None = None
    active_scorer: str | None = None
    model_type: str | None = None
    panel_ltr_artifact: str | None = None


@dataclass
class AsOfExclusion:
    """A prediction date excluded by the as-of contract (never silently dropped)."""

    run_date: str
    reason: str


@dataclass
class BackfillManifest:
    """Provenance record for one backfill run."""

    backfill_id: str = ""
    expert_name: str = ""
    runs_db_path: str = ""
    runs_db_digest: str = ""
    start_date: str = ""
    end_date: str = ""
    n_dates_exported: int = 0
    n_dates_skipped_no_scores: int = 0
    n_dates_excluded_asof_contract: int = 0
    asof_exclusion_reasons: dict[str, str] = field(default_factory=dict)
    n_total_ticker_scores: int = 0
    score_column: str = "mu"
    universe_source: str = ""
    universe_size: int = 0
    classification: str = "EXPLORATORY_ONLY"
    created_at: str = ""
    output_dir: str = ""
    score_file_digests: dict[str, str] = field(default_factory=dict)
    returns_file_digest: str = ""
    returns_file_path: str = ""
    query_schema_version: str = ""
    session_calendar_digest: str = ""
    calendar_evidence_path: str = ""
    ledger_fingerprint: str = ""
    ledger_admitted: int = 0
    ledger_rejected: int = 0
    ledger_summary: dict[str, Any] = field(default_factory=dict)


def _db_digest(db_path: Path) -> str:
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _parse_sqlite_utc_timestamp(value: str) -> datetime:
    """Parse a ``pipeline_runs.created_at`` value as UTC.

    SQLite's ``CURRENT_TIMESTAMP`` default (what ``record_pipeline_run``
    relies on -- it never passes an explicit value) writes a NAIVE
    ``YYYY-MM-DD HH:MM:SS`` string that IS already UTC (SQLite documents
    ``CURRENT_TIMESTAMP`` as UTC). A naive value is therefore always
    interpreted as UTC here -- never local time. ISO-8601 strings with an
    explicit offset or trailing ``Z`` are also accepted and normalized to
    UTC, for forward-compatibility with a future writer that stamps an
    explicit timezone.
    """
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _session_close_cutoff_utc(
    run_date: str,
    *,
    calendar: SessionCalendar,
    schedule: DecisionSchedule,
) -> datetime | None:
    """The as-of cutoff for ``run_date``: NYSE session close (early-close
    aware), in UTC.

    This MUST stay numerically identical to
    ``admissibility_ledger._decision_ts_from_schedule`` -- the canonical
    validator independently recomputes the same quantity when this
    backfill's output is later fed through :func:`admissibility_ledger.
    build_ledger`; any drift here would let a score pass this gate but be
    rejected (or wrongly accepted) by the validator's own recheck of
    ``score_timestamp <= decision_timestamp``.

    Returns ``None`` when ``run_date`` is not a session in the calendar
    (fail-closed exclusion -- see :func:`select_asof_runs`).
    """
    if not calendar.contains(run_date):
        return None
    local_time = calendar.decision_time_for(run_date, schedule.decision_time)
    tz = ZoneInfo(schedule.session_timezone)
    local_dt = datetime.combine(date.fromisoformat(run_date), local_time, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def select_asof_runs(
    db_path: Path,
    *,
    start_date: str,
    end_date: str,
    calendar: SessionCalendar,
    schedule: DecisionSchedule = US_EQUITY_CLOSE,
) -> tuple[dict[str, RunSelection], list[AsOfExclusion]]:
    """Select, per prediction date, the ONE committed 'live' pipeline run
    that was available at-or-before that date's own session-close cutoff.

    This is the as-of contract (Codex review on model#54, finding 1):
    ``ORDER BY created_at DESC LIMIT 1`` alone is not proof of point-in-time
    availability -- it can select a rerun produced after the target
    session's decision time, which IS look-ahead. Only runs with
    ``created_at <= cutoff`` are eligible; among eligible runs for a date,
    the LATEST is selected (the most complete state actually committed
    by that date's own close). A date with zero eligible runs -- no live
    run at all, or every live run for it was committed after its own
    session closed -- is returned in the exclusion list with a documented
    reason, never silently admitted or silently dropped.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT run_id, run_date, created_at, commit_sha
            FROM pipeline_runs
            WHERE run_type = 'live'
              AND run_date >= ? AND run_date <= ?
            ORDER BY run_date, created_at
            """,
            (start_date, end_date),
        ).fetchall()
    finally:
        conn.close()

    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(row["run_date"], []).append(row)

    selected: dict[str, RunSelection] = {}
    excluded: list[AsOfExclusion] = []
    for run_date, candidates in sorted(by_date.items()):
        cutoff = _session_close_cutoff_utc(run_date, calendar=calendar, schedule=schedule)
        if cutoff is None:
            excluded.append(
                AsOfExclusion(
                    run_date,
                    "not a valid exchange session in the declared NYSE calendar",
                )
            )
            continue

        eligible: list[tuple[datetime, sqlite3.Row]] = []
        n_late = 0
        for row in candidates:
            if not row["created_at"]:
                continue
            try:
                created_at_utc = _parse_sqlite_utc_timestamp(row["created_at"])
            except ValueError:
                continue
            if created_at_utc <= cutoff:
                eligible.append((created_at_utc, row))
            else:
                n_late += 1

        if not eligible:
            if candidates:
                reason = (
                    f"{len(candidates)} live run(s) exist for {run_date} but all "
                    f"{n_late} were committed AFTER the session-close cutoff "
                    f"({cutoff.isoformat()}) -- look-ahead; excluded rather than "
                    f"substituting a later rerun"
                )
            else:
                reason = "no committed 'live' pipeline run found for this date"
            excluded.append(AsOfExclusion(run_date, reason))
            continue

        eligible.sort(key=lambda pair: pair[0])
        created_at_utc, row = eligible[-1]
        selected[run_date] = RunSelection(
            run_id=row["run_id"],
            run_date=run_date,
            created_at_utc=created_at_utc.isoformat(),
            commit_sha=row["commit_sha"],
        )
    return selected, excluded


def _summarize_identity(values: set[str]) -> str:
    if not values:
        return "MISSING"
    if len(values) == 1:
        return next(iter(values))
    return "MIXED:" + ",".join(sorted(values))


def extract_daily_scores(
    db_path: Path,
    *,
    score_column: str,
    run_selection: dict[str, RunSelection],
) -> dict[str, dict[str, float]]:
    """Extract per-date ``{ticker: score}`` for an already-resolved as-of
    run selection (see :func:`select_asof_runs`).

    This function never re-derives which run is eligible -- it only pulls
    the score-family column for the already-approved ``run_id`` set, and
    refuses any ``score_column`` not on :data:`ALLOWED_SCORE_COLUMNS`
    (SQL-injection guard) before building any query.

    Only ``role='candidate'`` rows are extracted -- holdings are a subset
    and would double-count. Each selected :class:`RunSelection` is
    enriched IN PLACE with the scorer/model identity fields discovered
    from ``candidate_scores`` (``active_scorer``/``model_type``/
    ``panel_ltr_artifact``), since those columns live on this table, not
    ``pipeline_runs``.
    """
    validated_column = validate_score_column(score_column)
    if not run_selection:
        return {}

    run_id_to_date = {rs.run_id: d for d, rs in run_selection.items()}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in run_id_to_date)
        rows = conn.execute(
            f"""
            SELECT cs.run_id, cs.ticker, cs.{validated_column} AS score,
                   cs.active_scorer, cs.model_type, cs.panel_ltr_artifact
            FROM candidate_scores cs
            WHERE cs.role = 'candidate'
              AND cs.{validated_column} IS NOT NULL
              AND cs.run_id IN ({placeholders})
            ORDER BY cs.run_id, cs.ticker
            """,  # noqa: S608 -- validated_column is checked against
                  # ALLOWED_SCORE_COLUMNS above and is never CLI/attacker-
                  # controlled text at this point; run_id values are bound
                  # parameters, never interpolated.
            list(run_id_to_date.keys()),
        ).fetchall()
    finally:
        conn.close()

    by_date: dict[str, dict[str, float]] = {}
    identity_seen: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        d = run_id_to_date.get(row["run_id"])
        if d is None:
            continue
        by_date.setdefault(d, {})[row["ticker"]] = float(row["score"])
        slots = identity_seen.setdefault(
            d, {"active_scorer": set(), "model_type": set(), "panel_ltr_artifact": set()}
        )
        for field_name in ("active_scorer", "model_type", "panel_ltr_artifact"):
            val = row[field_name]
            if val is not None:
                slots[field_name].add(val)

    for d, slots in identity_seen.items():
        rs = run_selection[d]
        rs.active_scorer = _summarize_identity(slots["active_scorer"])
        rs.model_type = _summarize_identity(slots["model_type"])
        rs.panel_ltr_artifact = _summarize_identity(slots["panel_ltr_artifact"])

    return by_date


def extract_forward_returns(
    db_path: Path,
    *,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Extract forward returns from the runs DB."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT as_of_date, ticker, fwd_60d
            FROM ticker_forward_returns
            WHERE as_of_date >= ? AND as_of_date <= ?
              AND fwd_60d IS NOT NULL
            ORDER BY as_of_date, ticker
            """,
            (start_date, end_date),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def write_forward_returns_csv(
    returns: list[dict[str, Any]],
    output_path: Path,
) -> str:
    """Write forward returns CSV and return its digest."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["date,ticker,fwd_return\n"]
    for r in returns:
        lines.append(f"{r['as_of_date']},{r['ticker']},{r['fwd_60d']}\n")
    raw = "".join(lines).encode()
    output_path.write_bytes(raw)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass
class ProvenanceContext:
    """Everything :func:`write_score_files` needs to build a full,
    immutable, per-date provenance record -- bundled to keep the per-date
    payload builder's signature manageable."""

    score_column: str
    session_calendar: SessionCalendar
    decision_schedule: DecisionSchedule
    db_digest: str
    db_path: str
    has_realized_labels_by_date: dict[str, bool]
    label_artifact_ref_by_date: dict[str, str]
    label_observation_end_by_date: dict[str, str]


def build_score_payload(
    dt_str: str,
    scores: dict[str, float],
    *,
    expert_name: str,
    backfill_id: str,
    run_sel: RunSelection,
    provenance: ProvenanceContext,
) -> dict[str, Any]:
    """Build one date's CANDIDATE EVIDENCE payload.

    Top-level keys (``as_of_date``, ``data_watermark``, ``score_timestamp``,
    ``training_cutoff``, ``model_content_sha256``, ``has_realized_labels``,
    ``label_artifact_ref``, ``label_observation_end``) are exactly the
    fields ``admissibility_ledger.extract_metadata_from_score`` reads from a
    score file -- placing them at the top level (not nested) is required
    for the canonical validator to actually see them.

    ``training_cutoff`` and ``model_content_sha256`` are always the literal
    string ``"MISSING"``: ``runs.alpaca.db`` does not persist either field
    today. This is an honest data gap, not a placeholder -- the canonical
    validator will correctly REJECT these records rather than admit an
    unproven score (Codex review finding 3: never manufacture
    ``admitted: true``).
    """
    cutoff = _session_close_cutoff_utc(
        dt_str, calendar=provenance.session_calendar, schedule=provenance.decision_schedule,
    )
    return {
        "date": dt_str,
        "expert": expert_name,
        "scores": scores,
        # -- fields read by admissibility_ledger.extract_metadata_from_score --
        "as_of_date": dt_str,
        "data_watermark": dt_str,
        "score_timestamp": run_sel.created_at_utc,
        "training_cutoff": "MISSING",
        "model_content_sha256": "MISSING",
        "has_realized_labels": provenance.has_realized_labels_by_date.get(dt_str, False),
        "label_artifact_ref": provenance.label_artifact_ref_by_date.get(dt_str, "MISSING"),
        "label_observation_end": provenance.label_observation_end_by_date.get(dt_str, "MISSING"),
        # -- audit-trail / extended provenance (Codex review finding 2) --
        "metadata": {
            "backfill_id": backfill_id,
            "classification": "EXPLORATORY_ONLY",
            "score_column": provenance.score_column,
            "n_tickers": len(scores),
            "provenance_note": (
                "training_cutoff and model_content_sha256 are the literal "
                "string 'MISSING', not a placeholder: runs.alpaca.db's "
                "pipeline_runs/candidate_scores schema does not persist "
                "either at write time. The canonical admissibility "
                "validator will correctly REJECT these records rather than "
                "admit an unproven score -- intended fail-closed behavior."
            ),
            "provenance": {
                "source_run_id": run_sel.run_id,
                "source_run_type": "live",
                "source_run_created_at_utc": run_sel.created_at_utc,
                "decision_session_cutoff_utc": (
                    cutoff.isoformat() if cutoff is not None else "MISSING"
                ),
                "pipeline_commit_sha": run_sel.commit_sha or "MISSING",
                "active_scorer": run_sel.active_scorer or "MISSING",
                "model_type": run_sel.model_type or "MISSING",
                "panel_ltr_artifact": run_sel.panel_ltr_artifact or "MISSING",
                "universe_calendar_name": "NYSE",
                "universe_calendar_provider": "pandas_market_calendars",
                "backfill_query_schema_version": QUERY_SCHEMA_VERSION,
                "source_db_digest": provenance.db_digest,
                "source_db_path": provenance.db_path,
            },
        },
    }


def write_score_files(
    scores_by_date: dict[str, dict[str, float]],
    output_dir: Path,
    *,
    expert_name: str,
    backfill_id: str,
    run_selection: dict[str, RunSelection],
    provenance: ProvenanceContext,
) -> dict[str, str]:
    """Write per-date candidate-evidence JSON files and return
    ``{date: digest}``."""
    score_dir = output_dir / expert_name
    score_dir.mkdir(parents=True, exist_ok=True)

    digests: dict[str, str] = {}
    for dt_str, scores in sorted(scores_by_date.items()):
        payload = build_score_payload(
            dt_str, scores,
            expert_name=expert_name, backfill_id=backfill_id,
            run_sel=run_selection[dt_str], provenance=provenance,
        )
        raw = json.dumps(payload, indent=2, sort_keys=True).encode()
        out_path = score_dir / f"{dt_str}.json"
        out_path.write_bytes(raw)
        digests[dt_str] = f"sha256:{hashlib.sha256(raw).hexdigest()}"

    return digests


def _score_file_loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
    """Load one date's candidate-evidence JSON for the canonical validator.

    Mirrors ``admissibility_ledger.main()``'s own ``_file_score_loader`` --
    reuses the SAME public loader (:func:`load_score_file`) and metadata
    extractor (:func:`extract_metadata_from_score`) rather than
    reimplementing the parsing contract.
    """
    candidate = expert.score_dir / f"{dt}.json"
    missing_meta = {
        "model_fingerprint": "MISSING",
        "training_cutoff": "MISSING",
        "feature_data_cutoff": "MISSING",
        "score_timestamp": "MISSING",
        "score_artifact_digest": "MISSING",
    }
    if not candidate.exists():
        return missing_meta
    result = load_score_file(candidate)
    if result is None:
        return missing_meta
    data, file_digest = result
    meta = extract_metadata_from_score(data, expert)
    meta["score_artifact_digest"] = file_digest
    return meta


def run_backfill(
    *,
    runs_db: Path,
    output_dir: Path,
    expert_name: str,
    start_date: str,
    end_date: str,
    score_column: str = "mu",
    universe_file: Path | None = None,
    label_horizon_days: int = 60,
    decision_schedule: DecisionSchedule = US_EQUITY_CLOSE,
) -> BackfillManifest:
    """Execute the full backfill pipeline.

    Produces CANDIDATE evidence (per-date score files with full point-in-
    time provenance) and defers the actual admission decision to the
    canonical validator (:func:`admissibility_ledger.build_ledger`) -- this
    function does not itself decide ``admitted``.
    """
    validated_column = validate_score_column(score_column)

    backfill_id = (
        f"backfill_{expert_name}_{start_date}_{end_date}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    cal_start = (date.fromisoformat(start_date) - timedelta(days=7)).isoformat()
    cal_end = (date.fromisoformat(end_date) + timedelta(days=7)).isoformat()
    print(f"Building NYSE session calendar {cal_start} .. {cal_end}...")
    session_calendar = build_exchange_session_calendar(cal_start, cal_end)
    cal_evidence = build_calendar_evidence(
        session_calendar, calendar_name="NYSE", query_range=(cal_start, cal_end),
    )
    cal_evidence_path = write_calendar_evidence(cal_evidence, output_dir)

    print(
        f"Resolving as-of run selection for {expert_name} "
        f"({start_date} -> {end_date})..."
    )
    run_selection, asof_exclusions = select_asof_runs(
        runs_db, start_date=start_date, end_date=end_date,
        calendar=session_calendar, schedule=decision_schedule,
    )
    print(
        f"  {len(run_selection)} date(s) with a committed run at-or-before "
        f"its session-close cutoff; {len(asof_exclusions)} excluded by the "
        f"as-of contract"
    )
    for exclusion in asof_exclusions[:10]:
        print(f"    EXCLUDED {exclusion.run_date}: {exclusion.reason}", file=sys.stderr)
    if len(asof_exclusions) > 10:
        print(f"    ... and {len(asof_exclusions) - 10} more", file=sys.stderr)

    print(f"Extracting {validated_column} scores for eligible runs...")
    scores_by_date = extract_daily_scores(
        runs_db, score_column=validated_column, run_selection=run_selection,
    )
    n_skipped_empty = 0
    clean: dict[str, dict[str, float]] = {}
    for dt_str, scores in scores_by_date.items():
        if not scores:
            n_skipped_empty += 1
            continue
        clean[dt_str] = scores
    print(f"  {len(clean)} date(s) with scores, {n_skipped_empty} skipped (empty)")

    print("Extracting forward returns...")
    returns = extract_forward_returns(runs_db, start_date=start_date, end_date=end_date)
    returns_path = output_dir / "forward_returns.csv"
    returns_digest = write_forward_returns_csv(returns, returns_path)
    print(f"  {len(returns)} return records written")

    returns_dates_set = {r["as_of_date"] for r in returns}
    label_ref = f"{returns_digest}@{returns_path.name}"
    has_realized_labels_by_date = {d: d in returns_dates_set for d in clean}
    label_artifact_ref_by_date = {
        d: (label_ref if d in returns_dates_set else "MISSING") for d in clean
    }
    label_observation_end_by_date = {
        d: (
            (date.fromisoformat(d) + timedelta(days=label_horizon_days)).isoformat()
            if d in returns_dates_set
            else "MISSING"
        )
        for d in clean
    }

    db_digest = _db_digest(runs_db)
    provenance = ProvenanceContext(
        score_column=validated_column,
        session_calendar=session_calendar,
        decision_schedule=decision_schedule,
        db_digest=db_digest,
        db_path=str(runs_db),
        has_realized_labels_by_date=has_realized_labels_by_date,
        label_artifact_ref_by_date=label_artifact_ref_by_date,
        label_observation_end_by_date=label_observation_end_by_date,
    )

    print("Writing per-date candidate-evidence score files...")
    digests = write_score_files(
        clean, output_dir,
        expert_name=expert_name, backfill_id=backfill_id,
        run_selection=run_selection, provenance=provenance,
    )

    if universe_file is not None:
        universe_tickers = [
            line.strip()
            for line in universe_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        universe_source = f"file:{universe_file}"
    else:
        universe_tickers = sorted({t for scores in clean.values() for t in scores})
        universe_source = (
            "derived_from_backfilled_scores (no --universe-file given -- "
            "this is the union of tickers this backfill happened to see, "
            "NOT the true trading universe; missingness/coverage stats in "
            "the ledger are relative to this proxy)"
        )

    ledger_summary: dict[str, Any] = {}
    ledger_fingerprint = ""
    n_admitted = 0
    n_rejected = 0
    prediction_dates = sorted(clean.keys())
    if prediction_dates:
        print(
            "Building admissibility ledger via the canonical validator "
            "(admissibility_ledger.build_ledger) -- this script does not "
            "decide admission itself..."
        )
        expert_spec = ExpertSpec(name=expert_name, score_dir=output_dir / expert_name)
        ledger = build_ledger(
            [expert_spec], prediction_dates, universe_tickers,
            score_loader=_score_file_loader,
            decision_schedule=decision_schedule,
            session_calendar=session_calendar,
            calendar_evidence=cal_evidence,
            calendar_evidence_locator_str=cal_evidence_path.name,
            require_realized_labels=True,
            label_horizon_days=label_horizon_days,
        )
        ledger_path = write_ledger(ledger, output_dir)
        ledger_summary = ledger.summary
        ledger_fingerprint = ledger.ledger_fingerprint
        stats = ledger.summary.get("per_expert", {}).get(expert_name, {})
        n_admitted = stats.get("admitted", 0)
        n_rejected = stats.get("rejected", 0)
        print(f"  Ledger written to {ledger_path}")
        print(f"  Fingerprint: {ledger_fingerprint}")
        print(
            f"  Admitted: {n_admitted}/{n_admitted + n_rejected} "
            f"(canonical validator verdict)"
        )
        if n_admitted == 0:
            print(
                "  NOTE: 0 admitted is EXPECTED for this data source today -- "
                "runs.alpaca.db does not persist training_cutoff or a model "
                "content fingerprint, so every record fails those required "
                "fields. This is fail-closed, not a bug in this script.",
                file=sys.stderr,
            )
    else:
        print(
            "  No prediction dates with candidate evidence -- no ledger built",
            file=sys.stderr,
        )

    manifest = BackfillManifest(
        backfill_id=backfill_id,
        expert_name=expert_name,
        runs_db_path=str(runs_db),
        runs_db_digest=db_digest,
        start_date=start_date,
        end_date=end_date,
        n_dates_exported=len(clean),
        n_dates_skipped_no_scores=n_skipped_empty,
        n_dates_excluded_asof_contract=len(asof_exclusions),
        asof_exclusion_reasons={e.run_date: e.reason for e in asof_exclusions},
        n_total_ticker_scores=sum(len(s) for s in clean.values()),
        score_column=validated_column,
        universe_source=universe_source,
        universe_size=len(universe_tickers),
        created_at=datetime.now(timezone.utc).isoformat(),
        output_dir=str(output_dir),
        score_file_digests=digests,
        returns_file_digest=returns_digest,
        returns_file_path=str(returns_path),
        query_schema_version=QUERY_SCHEMA_VERSION,
        session_calendar_digest=session_calendar.digest(),
        calendar_evidence_path=str(cal_evidence_path),
        ledger_fingerprint=ledger_fingerprint,
        ledger_admitted=n_admitted,
        ledger_rejected=n_rejected,
        ledger_summary=ledger_summary,
    )

    manifest_path = output_dir / "backfill_manifest.json"
    manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    classification_path = output_dir / "_experiment_classification.json"
    classification_path.write_text(
        json.dumps({
            "classification": "EXPLORATORY_ONLY",
            "backfill_id": backfill_id,
            "created_at": manifest.created_at,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nBackfill complete: {backfill_id}")
    print(f"  Dates with candidate evidence: {len(clean)} ({start_date} -> {end_date})")
    print(f"  Dates excluded by as-of contract: {len(asof_exclusions)}")
    print(f"  Scores: {manifest.n_total_ticker_scores} total")
    print(f"  Returns: {len(returns)} records")
    print(f"  Admitted by canonical validator: {n_admitted}/{n_admitted + n_rejected}")
    print(f"  Output: {output_dir}")
    print("  Classification: EXPLORATORY_ONLY")

    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract historical panel scores from runs.alpaca.db for Phase A ensemble experiments",
    )
    parser.add_argument("--runs-db", required=True, type=Path, help="Path to runs.alpaca.db")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--expert-name", required=True, help="Expert name (e.g. xgb, patchtst)")
    parser.add_argument("--start-date", default="2024-01-02", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-07-13", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--score-column", default="mu",
        help=(
            "Score column to extract (default: mu). Must be one of: "
            f"{sorted(ALLOWED_SCORE_COLUMNS)}."
        ),
    )
    parser.add_argument(
        "--universe-file", type=Path, default=None,
        help=(
            "Optional ticker universe file (one ticker per line, '#' "
            "comments allowed). Defaults to the union of tickers seen in "
            "the backfilled scores if omitted (a proxy, not the true "
            "trading universe)."
        ),
    )
    parser.add_argument(
        "--label-horizon-days", type=int, default=60,
        help="Minimum label horizon in calendar days (default: 60)",
    )
    parser.add_argument(
        "--diagnostic-only", action="store_true",
        help=(
            "Exit 0 even when the canonical validator admits zero records. "
            "Use for intentional rejected-evidence reports where 0-admitted "
            "is expected (e.g. provenance-gap diagnostics). Without this "
            "flag, 0-admitted is treated as a failure (exit 2)."
        ),
    )
    args = parser.parse_args(argv)

    if not args.runs_db.exists():
        print(f"ERROR: runs DB not found: {args.runs_db}", file=sys.stderr)
        return 1

    try:
        validate_score_column(args.score_column)
    except ScoreColumnNotAllowedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.universe_file is not None and not args.universe_file.exists():
        print(f"ERROR: universe file not found: {args.universe_file}", file=sys.stderr)
        return 1

    manifest = run_backfill(
        runs_db=args.runs_db,
        output_dir=args.output_dir,
        expert_name=args.expert_name,
        start_date=args.start_date,
        end_date=args.end_date,
        score_column=args.score_column,
        universe_file=args.universe_file,
        label_horizon_days=args.label_horizon_days,
    )

    if manifest.ledger_admitted == 0 and not args.diagnostic_only:
        print(
            f"ERROR: canonical validator admitted 0/{manifest.ledger_rejected} records. "
            f"No Phase-A-eligible evidence was produced. "
            f"Use --diagnostic-only to exit 0 for intentional rejected-evidence reports.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
