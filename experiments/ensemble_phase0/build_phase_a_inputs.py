"""Convert a walk-forward sim DB + its WF manifest into Phase A ensemble inputs.

The Phase A runner (:mod:`phase_a_runner`) consumes, per expert, a *score
directory* of per-date ``YYYY-MM-DD.json`` files that pass the Stage-0
admissibility ledger (:mod:`admissibility_ledger`), plus one shared
forward-returns CSV. The daily/backtest pipeline persists walk-forward-sim
scores to a sim DB (``score_distribution``) and forward-return labels to
``ticker_forward_returns``, but never exports them in that per-date schema.
This converter bridges the gap for ANY single scorer's walk-forward-sim run.

Why this exists (and why it is not :mod:`backfill_scores`): the retired
``backfill_scores`` read ``runs.alpaca.db``, which does NOT persist a model's
training cutoff or a content fingerprint, so every record honestly carried
``training_cutoff="MISSING"`` and was correctly rejected by the canonical
validator. A *walk-forward sim*, by contrast, is driven by a WF manifest whose
per-fold provenance (``cutoff_date``, ``lookahead_days``, ``artifact_uri``) is
exactly the missing point-in-time vintage. This converter stamps that real
provenance, so the produced scores are genuinely admissible — not fabricated.

Point-in-time correctness (addresses Codex feedback on model#64):

* A sim date ``D``'s PIT-clean model vintage is the walk-forward fold whose
  ``cutoff_date + BUSINESS-DAYS(lookahead_days)`` is **strictly before** ``D``.
  The offset is ``pandas.tseries.offsets.BDay`` (business days), NOT a calendar
  ``timedelta`` — this matches the real ``effective_train_cutoff_date`` /
  ``WalkForwardModelLoader.entry_as_of`` semantics (a fold's labels use data
  through ``cutoff + lookahead`` business days, so the model only becomes
  usable for prediction dates strictly after that effective cutoff). The
  selected fold is the LATEST such eligible fold (the entry active as-of ``D``).
* ``training_cutoff`` is stamped as the selected fold's real ``cutoff_date``
  (never ``"MISSING"``). The model content fingerprint is the SHA-256 of the
  fold's resolved ``artifact_uri`` file when readable (a genuine content
  digest). When the artifact cannot be resolved on disk, the date is
  EXCLUDED from output entirely -- a provenance-bound surrogate digest is
  computed internally only to decide this exclusion; it is never written to
  a score file, since the canonical validator checks digest SYNTAX only and
  cannot otherwise distinguish a real digest from an unverified one.
* A sim date before the first fold's effective cutoff has NO PIT-clean vintage
  and is EXCLUDED (leakage-correct), never stamped with a leaky model.

Scorer-agnostic by construction: the sim DB path, the WF manifest, and the
score column are all parameters. The XGB expert runs it against the GBDT
walk-forward sim DB now; the PatchTST expert reuses the SAME converter later
against the sim DB produced by re-running the sim driver with the fresh
PatchTST WF manifest.

All output goes to an experiment-specific directory, never to production
paths. Source DBs are opened read-only. Records carry an EXPLORATORY_ONLY
classification.

Usage::

    python -m experiments.ensemble_phase0.build_phase_a_inputs \\
        --sim-db /path/to/sim_runs.db \\
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
    SessionCalendar,
    _decision_ts_from_schedule,
    build_calendar_evidence,
    build_exchange_session_calendar,
    build_ledger,
    extract_metadata_from_score,
    load_score_file,
    write_calendar_evidence,
    write_ledger,
)

#: Query/schema-version tag persisted in every provenance record. Bump when
#: the extraction SQL or the PIT fold-selection semantics change.
QUERY_SCHEMA_VERSION = "build_phase_a_inputs.wf_sim_db.v1_bday_pit"

#: The real numeric per-ticker score columns in ``score_distribution``.
#: ``--score-column`` is validated against this FIXED allowlist BEFORE it ever
#: reaches a SQL string (a SQL-injection guard). Bookkeeping / labelling
#: columns (``regime``, ``is_holding``, ``run_type``, ``model_type``,
#: ``sector``, ``blocked_by``, ``*_horizon_days``) are deliberately excluded —
#: they are not "the panel score" this converter extracts.
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
# Walk-forward fold provenance
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
    """Select the PIT-clean walk-forward fold for a prediction date.

    Returns the LATEST fold whose ``cutoff_date + BDay(lookahead_days)`` is
    STRICTLY before ``prediction_date`` (the entry active as-of that date).
    Returns ``None`` when no fold is PIT-clean (the date precedes all
    coverage) -- such a date has no admissible model vintage and must be
    excluded, never stamped with a leaky (future) model.

    ``folds`` must be sorted ascending by ``cutoff_date`` (as returned by
    :func:`load_folds`); the effective cutoff is then monotonic, so the last
    eligible fold in iteration order is the latest eligible fold.
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
    """Resolve a fold's model content fingerprint.

    Returns ``(fingerprint, locator, is_real_content_digest)``.

    When the fold's ``artifact_uri`` resolves to a readable file under
    ``artifact_base_dir``, the fingerprint is the SHA-256 of that file's exact
    bytes -- a genuine model-content digest, and ``is_real_content_digest`` is
    True. Otherwise it is a deterministic digest bound to the fold's immutable
    provenance (cutoff + artifact_uri + trained_date), clearly distinguishable
    via ``is_real_content_digest=False`` and the ``provenance_bound:`` locator.

    The canonical validator only checks digest SYNTAX, so it cannot tell a
    real digest from this fallback -- ``run_build`` therefore uses
    ``is_real_content_digest`` to EXCLUDE any date whose selected fold
    resolves to the fallback, rather than writing a score file the validator
    would admit on unverified provenance. This function itself still returns
    the fallback tuple (never raises) so callers can make that fail-closed
    decision explicitly.
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


# =====================================================================
# Sim DB extraction
# =====================================================================
def db_digest(db_path: Path) -> str:
    """Content digest of a source DB file (audit provenance)."""
    return f"sha256:{hashlib.sha256(db_path.read_bytes()).hexdigest()}"


def read_scores_by_date(
    db_path: Path,
    *,
    score_column: str,
    start_date: str,
    end_date: str,
) -> dict[str, dict[str, float]]:
    """Read per-date ``{ticker: score}`` from ``score_distribution``.

    Only rows with a non-NULL score in the validated ``score_column`` are
    returned. ``score_column`` MUST already be validated
    (:func:`validate_score_column`).
    """
    validate_score_column(score_column)  # defence in depth
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT date, ticker, {score_column} AS score
            FROM score_distribution
            WHERE date >= ? AND date <= ?
              AND {score_column} IS NOT NULL
            ORDER BY date, ticker
            """,
            (start_date, end_date),
        ).fetchall()
    finally:
        conn.close()
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r["date"], {})[r["ticker"]] = float(r["score"])
    return out


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
    fold: WalkForwardFold,
    artifact_fingerprint: str,
    artifact_is_real_digest: bool,
    artifact_locator: str,
    decision_ts: str,
    labels: LabelContext,
    score_column: str,
    source_db_digest: str,
    source_db_path: str,
    manifest_path: str,
) -> dict[str, Any]:
    """Build one date's score payload in the admissibility-ledger schema.

    The top-level keys (``as_of_date``, ``data_watermark``,
    ``score_timestamp``, ``training_cutoff``, ``model_content_sha256``,
    ``has_realized_labels``, ``label_artifact_ref``, ``label_observation_end``)
    are exactly the fields
    :func:`admissibility_ledger.extract_metadata_from_score` reads.

    ``as_of_date`` / ``data_watermark`` / ``score_timestamp`` are stamped as
    the prediction date's real NYSE session-close timestamp (``decision_ts``,
    holiday/early-close aware, computed with the SAME primitive the validator
    uses). A walk-forward sim scores date ``D`` from data available through
    ``D``'s close, so the feature/data available-time equals the decision
    close -- this sits exactly on the causal boundary
    ``feature_data_cutoff <= decision_timestamp`` and admits, whereas a
    naive date-only ``as_of_date`` would parse to end-of-day (23:59:59 UTC)
    and be rejected as post-decision look-ahead.
    """
    return {
        "date": dt_str,
        "expert": expert_name,
        "scores": scores,
        # -- fields read by admissibility_ledger.extract_metadata_from_score --
        "as_of_date": decision_ts,
        "data_watermark": decision_ts,
        "score_timestamp": decision_ts,
        "training_cutoff": fold.cutoff_date,
        "model_content_sha256": artifact_fingerprint,
        "has_realized_labels": labels.has_realized_labels_by_date.get(dt_str, False),
        "label_artifact_ref": labels.label_artifact_ref_by_date.get(dt_str, "MISSING"),
        "label_observation_end": labels.label_observation_end_by_date.get(dt_str, "MISSING"),
        # -- audit-trail / extended provenance --
        "metadata": {
            "classification": "EXPLORATORY_ONLY",
            "score_column": score_column,
            "n_tickers": len(scores),
            "query_schema_version": QUERY_SCHEMA_VERSION,
            "walkforward_fold": {
                "cutoff_date": fold.cutoff_date,
                "lookahead_days": fold.lookahead_days,
                "effective_train_cutoff_date": fold.effective_train_cutoff_date(),
                "artifact_uri": fold.artifact_uri,
                "trained_date": fold.trained_date,
                "calibrator_uri": fold.calibrator_uri,
            },
            "model_fingerprint_is_real_content_digest": artifact_is_real_digest,
            "model_artifact_locator": artifact_locator,
            "pit_contract": (
                "training_cutoff is the selected fold's real cutoff_date; the "
                "fold is the latest whose cutoff_date + BDay(lookahead_days) is "
                "strictly before this prediction date (business-day offset, not "
                "calendar timedelta -- WalkForwardModelLoader.entry_as_of "
                "semantics)."
            ),
            "source_db_path": source_db_path,
            "source_db_digest": source_db_digest,
            "source_manifest_path": manifest_path,
        },
    }


def write_score_files(
    scores_by_date: dict[str, dict[str, float]],
    fold_by_date: dict[str, WalkForwardFold],
    output_dir: Path,
    *,
    expert_name: str,
    fingerprint_by_fold: dict[str, tuple[str, bool, str]],
    decision_ts_by_date: dict[str, str],
    labels: LabelContext,
    score_column: str,
    source_db_digest: str,
    source_db_path: str,
    manifest_path: str,
) -> dict[str, str]:
    """Write per-date score JSON files; return ``{date: file_digest}``."""
    score_dir = output_dir / expert_name
    score_dir.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for dt_str in sorted(scores_by_date):
        fold = fold_by_date[dt_str]
        fp, is_real, locator = fingerprint_by_fold[fold.cutoff_date]
        payload = build_score_payload(
            dt_str,
            scores_by_date[dt_str],
            expert_name=expert_name,
            fold=fold,
            artifact_fingerprint=fp,
            artifact_is_real_digest=is_real,
            artifact_locator=locator,
            decision_ts=decision_ts_by_date[dt_str],
            labels=labels,
            score_column=score_column,
            source_db_digest=source_db_digest,
            source_db_path=source_db_path,
            manifest_path=manifest_path,
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
    score_column: str
    label_column: str
    start_date: str
    end_date: str
    n_dates_with_scores: int
    n_dates_excluded_no_pit_fold: int
    excluded_no_pit_fold_dates: list[str]
    n_dates_excluded_no_real_digest: int
    excluded_no_real_digest_dates: list[str]
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
    score_file_digests: dict[str, str] = field(default_factory=dict)
    fold_fingerprints: dict[str, dict[str, Any]] = field(default_factory=dict)
    ledger_admitted: int = 0
    ledger_rejected: int = 0
    ledger_fingerprint: str = ""


# =====================================================================
# Orchestration
# =====================================================================
def run_build(
    *,
    sim_db: Path,
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
    """Build the Phase-A score-dir + returns CSV for one scorer's WF sim."""
    validate_score_column(score_column)

    # Default: resolve fold artifact_uris relative to the manifest's
    # renquant_104 root (manifest lives at <root>/artifacts/sim/<manifest>).
    if artifact_base_dir is None:
        artifact_base_dir = manifest_file.parent.parent.parent

    folds = load_folds(manifest_file)
    print(f"Loaded {len(folds)} walk-forward folds "
          f"({folds[0].cutoff_date} .. {folds[-1].cutoff_date})")

    scores_by_date = read_scores_by_date(
        sim_db, score_column=score_column,
        start_date=start_date, end_date=end_date,
    )
    print(f"Read {len(scores_by_date)} sim score date(s) for column "
          f"'{score_column}' in [{start_date}, {end_date}]")

    # PIT fold selection per date (BDay contract). Dates before all coverage
    # are excluded.
    fold_by_date: dict[str, WalkForwardFold] = {}
    excluded_no_fold: list[str] = []
    for dt_str in sorted(scores_by_date):
        fold = select_pit_fold(folds, dt_str)
        if fold is None:
            excluded_no_fold.append(dt_str)
        else:
            fold_by_date[dt_str] = fold
    for dt_str in excluded_no_fold:
        del scores_by_date[dt_str]
    if excluded_no_fold:
        print(f"Excluded {len(excluded_no_fold)} date(s) with no PIT-clean fold "
              f"(before WF coverage): {excluded_no_fold[:5]}"
              f"{'...' if len(excluded_no_fold) > 5 else ''}")

    if not scores_by_date:
        raise ValueError(
            "no admissible-vintage dates: every date with scores precedes the "
            "first walk-forward fold's effective cutoff (fail-closed)"
        )

    # Resolve one fingerprint per distinct fold (content digest when readable).
    fingerprint_by_fold: dict[str, tuple[str, bool, str]] = {}
    for fold in {f.cutoff_date: f for f in fold_by_date.values()}.values():
        fp, locator, is_real = resolve_artifact_digest(fold, artifact_base_dir)
        fingerprint_by_fold[fold.cutoff_date] = (fp, is_real, locator)
    n_real = sum(1 for _, is_real, _ in fingerprint_by_fold.values() if is_real)
    print(f"Resolved fingerprints for {len(fingerprint_by_fold)} distinct fold(s) "
          f"({n_real} real content digest, "
          f"{len(fingerprint_by_fold) - n_real} provenance-bound fallback)")

    # Fail-closed: a fold whose artifact does not resolve to a real content
    # digest has no genuine model identity. Such dates are excluded from
    # output entirely -- the provenance-bound fallback is a syntactically
    # valid but unverified surrogate that the canonical validator cannot
    # distinguish from a real digest, so it must never reach a score file
    # (Codex CR on model#65: "reject missing/unavailable artifact identity
    # rather than emitting a synthetic digest").
    excluded_no_real_digest = sorted(
        dt_str for dt_str, fold in fold_by_date.items()
        if not fingerprint_by_fold[fold.cutoff_date][1]
    )
    for dt_str in excluded_no_real_digest:
        del scores_by_date[dt_str]
        del fold_by_date[dt_str]
    if excluded_no_real_digest:
        print(f"Excluded {len(excluded_no_real_digest)} date(s) whose selected "
              f"fold's artifact could not be resolved to a real content digest "
              f"(fail-closed, no provenance-bound fallback admitted): "
              f"{excluded_no_real_digest[:5]}"
              f"{'...' if len(excluded_no_real_digest) > 5 else ''}")

    if not scores_by_date:
        raise ValueError(
            "no admissible-vintage dates: every PIT-clean date's selected "
            "fold artifact failed to resolve to a real content digest "
            "(fail-closed)"
        )

    # Decision timestamps per date (holiday/early-close aware, SAME primitive
    # the validator uses -> guarantees feature==decision boundary admits).
    cal_start = (date.fromisoformat(min(scores_by_date)) - timedelta(days=7)).isoformat()
    cal_end = (date.fromisoformat(max(scores_by_date)) + timedelta(days=7)).isoformat()
    session_calendar = build_exchange_session_calendar(cal_start, cal_end)
    decision_ts_by_date = {
        dt_str: _decision_ts_from_schedule(
            decision_schedule, dt_str, calendar=session_calendar
        )
        for dt_str in scores_by_date
    }

    # Forward-return labels -> shared CSV.
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
        scores_by_date, fold_by_date, output_dir,
        expert_name=expert_name,
        fingerprint_by_fold=fingerprint_by_fold,
        decision_ts_by_date=decision_ts_by_date,
        labels=labels,
        score_column=score_column,
        source_db_digest=src_db_digest,
        source_db_path=str(sim_db),
        manifest_path=str(manifest_file),
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
        score_column=score_column,
        label_column=label_column,
        start_date=start_date,
        end_date=end_date,
        n_dates_with_scores=(
            len(scores_by_date) + len(excluded_no_fold) + len(excluded_no_real_digest)
        ),
        n_dates_excluded_no_pit_fold=len(excluded_no_fold),
        excluded_no_pit_fold_dates=excluded_no_fold,
        n_dates_excluded_no_real_digest=len(excluded_no_real_digest),
        excluded_no_real_digest_dates=excluded_no_real_digest,
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
        score_file_digests=digests,
        fold_fingerprints={
            cutoff: {
                "fingerprint": fp,
                "is_real_content_digest": is_real,
                "locator": locator,
            }
            for cutoff, (fp, is_real, locator) in fingerprint_by_fold.items()
        },
    )

    # Verify the produced score-dir loads through the CANONICAL validator.
    # This converter does not decide admission itself -- it defers to
    # admissibility_ledger.build_ledger (the SAME loader/validator Phase A
    # uses). Reported counts are the validator's verdict.
    if build_admissibility_ledger:
        expert_spec = ExpertSpec(name=expert_name, score_dir=output_dir / expert_name)
        cal_evidence = build_calendar_evidence(
            session_calendar, calendar_name="NYSE", query_range=(cal_start, cal_end),
        )
        cal_evidence_path = write_calendar_evidence(cal_evidence, output_dir)

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
        ledger = build_ledger(
            [expert_spec], prediction_dates, universe_tickers,
            score_loader=_loader,
            decision_schedule=decision_schedule,
            session_calendar=session_calendar,
            calendar_evidence=cal_evidence,
            calendar_evidence_locator_str=cal_evidence_path.name,
            require_realized_labels=True,
            label_horizon_days=label_horizon_days,
        )
        write_ledger(ledger, output_dir)
        stats = ledger.summary.get("per_expert", {}).get(expert_name, {})
        manifest.ledger_admitted = stats.get("admitted", 0)
        manifest.ledger_rejected = stats.get("rejected", 0)
        manifest.ledger_fingerprint = ledger.ledger_fingerprint
        print(f"Canonical admissibility ledger: "
              f"{manifest.ledger_admitted} admitted / "
              f"{manifest.ledger_admitted + manifest.ledger_rejected} evaluated "
              f"(fingerprint {ledger.ledger_fingerprint})")

    manifest_out = output_dir / f"build_manifest_{expert_name}.json"
    manifest_out.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    print(f"Build manifest written to {manifest_out}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a walk-forward sim DB + its WF manifest into Phase A "
            "ensemble inputs (per-date score-dir + shared returns CSV) with "
            "real point-in-time fold provenance (BDay-correct training_cutoff)."
        )
    )
    parser.add_argument("--sim-db", required=True, type=Path,
                        help="Path to the walk-forward sim DB (score_distribution)")
    parser.add_argument("--manifest-file", required=True, type=Path,
                        help="Path to the walk-forward manifest JSON (retrains[])")
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
                        help="Base dir to resolve fold artifact_uris (default: "
                             "manifest's <root>/artifacts/sim -> <root>)")
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
    if not args.manifest_file.exists():
        print(f"ERROR: manifest not found: {args.manifest_file}", file=sys.stderr)
        return 2

    manifest = run_build(
        sim_db=args.sim_db,
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

    print(
        f"\nDONE: expert={manifest.expert_name} "
        f"wrote={manifest.n_dates_written} "
        f"excluded_no_fold={manifest.n_dates_excluded_no_pit_fold} "
        f"excluded_no_real_digest={manifest.n_dates_excluded_no_real_digest} "
        f"admitted={manifest.ledger_admitted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
