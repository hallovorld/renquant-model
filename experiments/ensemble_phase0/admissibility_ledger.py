"""Stage 0 admissibility ledger builder for ensemble combination experiments.

Per §3.0 of the ensemble combination experiment design (model PR #48):
every proposed expert must pass an admissibility ledger for every historical
prediction date BEFORE any L1-L3 comparison may start.

The ledger records per-expert, per-prediction-date:
  - model/content fingerprint
  - training cutoff (last training date)
  - feature/data cutoff (as-of date for inference inputs)
  - score timestamp (when the score was generated)
  - universe coverage (how many tickers scored)
  - missingness (fraction of universe with missing scores)
  - score orientation (higher = more bullish? sign convention)
  - realized label availability (whether fwd_60d labels exist for evaluation)
  - score artifact digest (SHA-256 of the score file bytes)
  - label artifact reference (content digest + immutable locator)
  - label observation end date (validated against declared horizon)
  - resolved decision timestamp (UTC, from schedule + optional calendar)

Usage:
    python experiments/ensemble_phase0/admissibility_ledger.py \
        --expert xgb --score-dir /path/to/xgb/scores \
        --expert patchtst --score-dir /path/to/patchtst/scores \
        --universe-file /path/to/universe.csv \
        --output-dir experiments/ensemble_phase0/output
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DecisionSchedule:
    """Declares the decision-point clock for a trading session.

    Every admissibility evaluation needs an explicit decision time:
    scores generated after that point are look-ahead for that date.

    Examples::

        US_EQUITY_CLOSE = DecisionSchedule("America/New_York", time(16, 0))
        US_EQUITY_OPEN  = DecisionSchedule("America/New_York", time(9, 30))
    """

    session_timezone: str  # IANA tz name, e.g. "America/New_York"
    decision_time: time  # local-time decision point, e.g. time(16, 0)


US_EQUITY_CLOSE = DecisionSchedule("America/New_York", time(16, 0))


@dataclass
class SessionCalendar:
    """Declared trading-session calendar for admissibility evaluation.

    When provided, prediction dates not in ``valid_dates`` are rejected.
    Early-close sessions (e.g. day before July 4th) override the default
    decision time from the schedule.

    The calendar is fingerprinted and persisted with the ledger so that
    the same scores cannot be declared admissible under a different
    calendar without changing the ledger fingerprint.
    """

    valid_dates: frozenset[str]
    early_close_times: dict[str, time] = field(default_factory=dict)

    def contains(self, date_str: str) -> bool:
        return date_str in self.valid_dates

    def decision_time_for(self, date_str: str, default_time: time) -> time:
        return self.early_close_times.get(date_str, default_time)

    def digest(self) -> str:
        content = json.dumps({
            "valid_dates": sorted(self.valid_dates),
            "early_close_times": {
                k: v.isoformat()
                for k, v in sorted(self.early_close_times.items())
            },
        }, sort_keys=True).encode()
        return f"sha256:{hashlib.sha256(content).hexdigest()}"


def build_exchange_session_calendar(
    start_date: str,
    end_date: str,
    *,
    calendar_name: str = "NYSE",
    session_timezone: str = "America/New_York",
    full_session_close: time = time(16, 0),
) -> SessionCalendar:
    """Build a :class:`SessionCalendar` from a REAL exchange calendar.

    Uses ``pandas_market_calendars`` (the same exchange-calendar primitive
    ``renquant-execution``/``renquant-orchestrator`` already depend on) so
    ``valid_dates``/``early_close_times`` reflect actual exchange holidays
    and early closes, not a hand-maintained/self-attested date list. A
    session whose real ``market_close`` differs from
    ``full_session_close`` (e.g. the day after Thanksgiving, NYSE closes
    at 13:00 ET) is recorded as an early close override.

    Raises ``ValueError`` if the calendar returns no sessions at all for
    the requested range (fail-closed rather than silently producing an
    empty, always-rejecting calendar).
    """
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar(calendar_name)
    sched = cal.schedule(start_date=start_date, end_date=end_date)
    if sched.empty:
        raise ValueError(
            f"{calendar_name} calendar returned no sessions between "
            f"{start_date} and {end_date}"
        )

    tz = ZoneInfo(session_timezone)
    valid_dates: set[str] = set()
    early_close_times: dict[str, time] = {}
    for session_date, row in sched.iterrows():
        date_str = session_date.date().isoformat() if hasattr(session_date, "date") else str(session_date)[:10]
        valid_dates.add(date_str)
        close_utc = row["market_close"]
        if close_utc.tzinfo is None:
            close_utc = close_utc.tz_localize("UTC")
        local_close = close_utc.astimezone(tz)
        local_close_time = time(local_close.hour, local_close.minute, local_close.second)
        if local_close_time != full_session_close:
            early_close_times[date_str] = local_close_time

    return SessionCalendar(
        valid_dates=frozenset(valid_dates),
        early_close_times=early_close_times,
    )


@dataclass(frozen=True)
class ExpertAdmissibilityRecord:
    """Single-date admissibility record for one expert."""

    expert_name: str
    prediction_date: str
    model_fingerprint: str
    training_cutoff: str
    feature_data_cutoff: str
    data_watermark: str
    score_timestamp: str
    decision_timestamp_utc: str
    universe_size: int
    scored_count: int
    missing_count: int
    missingness_rate: float
    score_orientation: str
    has_realized_labels: bool
    score_artifact_digest: str
    label_artifact_ref: str
    label_observation_end: str
    admitted: bool
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class ExpertSpec:
    """Specification for one expert to be audited."""

    name: str
    score_dir: Path
    orientation: str = "higher_is_bullish"
    model_metadata_key: str = "model_content_sha256"


@dataclass
class AdmissibilityLedger:
    """Complete admissibility ledger for an ensemble experiment."""

    created_at: str = ""
    experts: list[str] = field(default_factory=list)
    universe_size: int = 0
    date_range: tuple[str, str] = ("", "")
    decision_schedule_timezone: str = ""
    decision_schedule_time: str = ""
    decision_schedule_digest: str = ""
    session_calendar_digest: str = ""
    label_horizon_days: int = 0
    records: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    ledger_fingerprint: str = ""

    def compute_fingerprint(self) -> str:
        content = json.dumps({
            "decision_schedule_digest": self.decision_schedule_digest,
            "session_calendar_digest": self.session_calendar_digest,
            "label_horizon_days": self.label_horizon_days,
            "records": self.records,
        }, sort_keys=True).encode()
        return f"sha256:{hashlib.sha256(content).hexdigest()}"


SUPPORTED_SCORE_FORMATS = {".json"}
FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LABEL_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}@\S+$")
MIN_COMMON_NAMES = 10


def _schedule_digest(schedule: DecisionSchedule) -> str:
    content = json.dumps({
        "session_timezone": schedule.session_timezone,
        "decision_time": schedule.decision_time.isoformat(),
    }, sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _decision_ts_from_schedule(
    schedule: DecisionSchedule,
    prediction_date_str: str,
    calendar: SessionCalendar | None = None,
) -> str:
    """Compute a UTC decision timestamp from a schedule and prediction date.

    When a calendar is provided and has an early-close entry for this
    date, the early-close time overrides the schedule's default.

    Returns an ISO-8601 string in UTC.
    """
    tz = ZoneInfo(schedule.session_timezone)
    pred_date = date.fromisoformat(prediction_date_str)
    decision_t = schedule.decision_time
    if calendar is not None:
        decision_t = calendar.decision_time_for(prediction_date_str, decision_t)
    local_dt = datetime.combine(pred_date, decision_t, tzinfo=tz)
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.isoformat()


def load_score_file(path: Path) -> tuple[dict[str, Any], str] | None:
    """Load a single score file and compute its content digest.

    Returns ``(parsed_data, digest_string)`` where digest_string is
    ``sha256:<64 hex chars>`` computed from the exact bytes on disk.
    Only JSON is supported. Parquet is rejected: it cannot carry the
    same provenance metadata inline.
    """
    if path.suffix == ".json":
        raw_bytes = path.read_bytes()
        digest = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
        return json.loads(raw_bytes), digest
    return None


def extract_metadata_from_score(
    score_data: dict[str, Any],
    expert: ExpertSpec,
) -> dict[str, Any]:
    """Extract admissibility-relevant metadata from a score payload."""
    meta: dict[str, Any] = {}

    meta["model_fingerprint"] = score_data.get(
        expert.model_metadata_key,
        score_data.get("fingerprint", "MISSING"),
    )
    meta["training_cutoff"] = score_data.get(
        "training_cutoff",
        score_data.get("train_end_date", "MISSING"),
    )
    meta["feature_data_cutoff"] = score_data.get(
        "as_of_date",
        score_data.get("feature_cutoff", "MISSING"),
    )
    meta["score_timestamp"] = score_data.get(
        "score_timestamp",
        score_data.get("created_at", "MISSING"),
    )

    meta["data_watermark"] = score_data.get(
        "data_watermark",
        meta["feature_data_cutoff"],
    )

    meta["has_realized_labels"] = bool(
        score_data.get("has_realized_labels", False)
    )

    meta["label_artifact_ref"] = score_data.get("label_artifact_ref", "MISSING")
    meta["label_observation_end"] = score_data.get(
        "label_observation_end", "MISSING"
    )

    scores = score_data.get("scores", {})
    if isinstance(scores, dict):
        meta["score_keys"] = list(scores.keys())
        meta["scores"] = scores
    else:
        meta["score_keys"] = []
        meta["scores"] = {}

    return meta


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp, normalising Z to +00:00.

    Date-only inputs (YYYY-MM-DD) are treated as end-of-day UTC so that
    ``decision_timestamp`` derived from a prediction_date includes the
    full trading day.
    """
    normalized = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        if len(normalized) <= 10:
            # Date-only: treat as end-of-day UTC.
            dt = dt.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _try_parse_timestamp(
    raw: str,
    field_name: str,
    reasons: list[str],
) -> datetime | None:
    """Try to parse a timestamp; append rejection reason on failure."""
    try:
        return _parse_timestamp(raw)
    except (ValueError, TypeError):
        reasons.append(f"{field_name} unparseable: {raw!r}")
        return None


def validate_expert_date(
    expert: ExpertSpec,
    prediction_date: str,
    score_meta: dict[str, Any],
    universe_tickers: list[str],
    *,
    decision_timestamp: str,
    require_realized_labels: bool = True,
    label_horizon_days: int = 60,
) -> ExpertAdmissibilityRecord:
    """Validate one expert on one prediction date against Stage 0 requirements.

    Args:
        decision_timestamp: **required** timezone-aware ISO-8601 timestamp
            marking when the decision is made.  Scores generated after
            this are look-ahead.  There is no default — callers must
            provide an explicit decision time, either from
            :class:`DecisionSchedule` via :func:`build_ledger` or
            directly for testing.
        require_realized_labels: if True (default -- for historical
            evaluation), ``has_realized_labels=False`` produces a
            rejection.
        label_horizon_days: minimum calendar days between prediction_date
            and label_observation_end (default 60).  A 1-day label
            cannot satisfy a 60-day forward evaluation.

    Causal chain enforced::

        training_cutoff < data_watermark <= feature_data_cutoff <= decision_timestamp
        score_timestamp <= decision_timestamp
    """
    reasons: list[str] = []

    # =================================================================
    # Phase 1: Parse ALL timestamps/dates upfront.
    # Any parse failure is an immediate reject with clear reason.
    # =================================================================
    parsed_pred = _try_parse_timestamp(prediction_date, "prediction_date", reasons)
    parsed_decision = _try_parse_timestamp(
        decision_timestamp, "decision_timestamp", reasons
    )

    fingerprint = score_meta.get("model_fingerprint", "MISSING")
    training_cutoff_raw = score_meta.get("training_cutoff", "MISSING")
    feature_cutoff_raw = score_meta.get("feature_data_cutoff", "MISSING")
    data_watermark_raw = score_meta.get("data_watermark", "MISSING")
    score_ts_raw = score_meta.get("score_timestamp", "MISSING")

    parsed_training: datetime | None = None
    if training_cutoff_raw == "MISSING":
        reasons.append("missing training cutoff date")
    else:
        parsed_training = _try_parse_timestamp(
            training_cutoff_raw, "training_cutoff", reasons
        )

    parsed_feature: datetime | None = None
    if feature_cutoff_raw == "MISSING":
        reasons.append("missing feature/data cutoff")
    else:
        parsed_feature = _try_parse_timestamp(
            feature_cutoff_raw, "feature_data_cutoff", reasons
        )

    parsed_watermark: datetime | None = None
    if data_watermark_raw == "MISSING":
        reasons.append("missing data watermark")
    else:
        parsed_watermark = _try_parse_timestamp(
            data_watermark_raw, "data_watermark", reasons
        )

    parsed_score_ts: datetime | None = None
    if score_ts_raw == "MISSING":
        reasons.append("missing score timestamp")
    else:
        parsed_score_ts = _try_parse_timestamp(
            score_ts_raw, "score_timestamp", reasons
        )

    # =================================================================
    # Phase 2: Fingerprint validation.
    # =================================================================
    if fingerprint == "MISSING":
        reasons.append("missing model fingerprint")
    elif not FINGERPRINT_RE.match(fingerprint):
        reasons.append(
            f"invalid fingerprint syntax (expected sha256:<64 hex chars>): "
            f"{fingerprint!r}"
        )

    # =================================================================
    # Phase 3: Causal chain checks (using parsed tz-aware datetimes).
    #
    # Full causal ordering enforced:
    #   training_cutoff < data_watermark <= feature_data_cutoff <= decision_timestamp
    #   score_timestamp <= decision_timestamp
    #
    # ALL available-time fields are compared to the actual decision
    # timestamp, not a date-only end-of-day surrogate.
    # =================================================================

    # training_cutoff < prediction_date
    if parsed_training is not None and parsed_pred is not None:
        if parsed_training >= parsed_pred:
            reasons.append(
                f"training cutoff {training_cutoff_raw} >= prediction date "
                f"{prediction_date} (lookahead)"
            )

    # training_cutoff < data_watermark
    if parsed_training is not None and parsed_watermark is not None:
        if parsed_training >= parsed_watermark:
            reasons.append(
                f"training cutoff {training_cutoff_raw} >= data watermark "
                f"{data_watermark_raw} (causal violation)"
            )

    # data_watermark <= decision_timestamp
    if parsed_watermark is not None and parsed_decision is not None:
        if parsed_watermark > parsed_decision:
            reasons.append(
                f"data_watermark {data_watermark_raw} > decision_timestamp "
                f"{decision_timestamp} (post-decision data -- look-ahead)"
            )

    # feature_data_cutoff <= decision_timestamp
    if parsed_feature is not None and parsed_decision is not None:
        if parsed_feature > parsed_decision:
            reasons.append(
                f"feature_data_cutoff {feature_cutoff_raw} > decision_timestamp "
                f"{decision_timestamp} (post-decision features -- look-ahead)"
            )

    # data_watermark <= feature_data_cutoff (ordering within the chain)
    if parsed_watermark is not None and parsed_feature is not None:
        if parsed_watermark > parsed_feature:
            reasons.append(
                f"data_watermark {data_watermark_raw} > feature_data_cutoff "
                f"{feature_cutoff_raw} (causal violation)"
            )

    # score_timestamp <= decision_timestamp
    if parsed_score_ts is not None and parsed_decision is not None:
        if parsed_score_ts > parsed_decision:
            reasons.append(
                f"score_timestamp {score_ts_raw} > decision_timestamp "
                f"{decision_timestamp} (late score -- potential look-ahead)"
            )

    # =================================================================
    # Phase 4: Universe coverage.
    # =================================================================
    score_keys = score_meta.get("score_keys", [])
    universe_set = set(universe_tickers)
    scored_set = set(score_keys)
    unknown_keys = scored_set - universe_set
    if unknown_keys:
        reasons.append(
            f"{len(unknown_keys)} unknown ticker(s) not in universe: "
            f"{sorted(unknown_keys)[:5]}"
        )
    duplicate_keys = len(score_keys) - len(scored_set)
    if duplicate_keys > 0:
        reasons.append(f"{duplicate_keys} duplicate score key(s)")

    scored_expected = universe_set & scored_set
    universe_size = len(universe_tickers)
    scored = len(scored_expected)
    missing = universe_size - scored
    missingness = missing / universe_size if universe_size > 0 else 1.0

    if missingness > 0.20:
        reasons.append(
            f"missingness {missingness:.1%} exceeds 20% threshold"
        )

    # =================================================================
    # Phase 5: Realized labels + artifact provenance.
    # =================================================================
    has_labels = bool(score_meta.get("has_realized_labels", False))
    if require_realized_labels and not has_labels:
        reasons.append("no realized labels for evaluation")

    score_artifact_digest = score_meta.get("score_artifact_digest", "MISSING")
    label_artifact_ref = score_meta.get("label_artifact_ref", "MISSING")
    label_observation_end = score_meta.get("label_observation_end", "MISSING")

    # score_artifact_digest: require canonical sha256:<64 hex>, never MISSING.
    if score_artifact_digest == "MISSING":
        reasons.append("missing score_artifact_digest (required)")
    elif not DIGEST_RE.match(score_artifact_digest):
        reasons.append(
            f"invalid score_artifact_digest syntax "
            f"(expected sha256:<64 hex chars>): {score_artifact_digest!r}"
        )

    if has_labels:
        # label_artifact_ref: require content digest + immutable locator.
        if label_artifact_ref == "MISSING":
            reasons.append(
                "has_realized_labels=True but label_artifact_ref is MISSING"
            )
        elif not LABEL_REF_RE.match(label_artifact_ref):
            reasons.append(
                f"invalid label_artifact_ref syntax "
                f"(expected sha256:<64 hex>@<locator>): {label_artifact_ref!r}"
            )
        if label_observation_end == "MISSING":
            reasons.append(
                "has_realized_labels=True but label_observation_end is MISSING"
            )
        else:
            parsed_label_end = _try_parse_timestamp(
                label_observation_end, "label_observation_end", reasons
            )
            if parsed_label_end is not None and parsed_pred is not None:
                horizon_delta = (
                    parsed_label_end.date() - parsed_pred.date()
                ).days
                if horizon_delta < label_horizon_days:
                    reasons.append(
                        f"label_observation_end {label_observation_end} is only "
                        f"{horizon_delta}d after prediction_date {prediction_date} "
                        f"(need >= {label_horizon_days}d label horizon)"
                    )

    return ExpertAdmissibilityRecord(
        expert_name=expert.name,
        prediction_date=prediction_date,
        model_fingerprint=fingerprint,
        training_cutoff=training_cutoff_raw,
        feature_data_cutoff=feature_cutoff_raw,
        data_watermark=data_watermark_raw,
        score_timestamp=score_ts_raw,
        decision_timestamp_utc=decision_timestamp,
        universe_size=universe_size,
        scored_count=scored,
        missing_count=missing,
        missingness_rate=missingness,
        score_orientation=expert.orientation,
        has_realized_labels=has_labels,
        score_artifact_digest=score_artifact_digest,
        label_artifact_ref=label_artifact_ref,
        label_observation_end=label_observation_end,
        admitted=len(reasons) == 0,
        rejection_reasons=reasons,
    )


def build_complementarity_report(
    expert_scores: dict[str, dict[str, dict[str, float]]],
    prediction_dates: list[str],
    universe_tickers: list[str],
) -> dict[str, Any]:
    """Build the complementarity diagnostics required by S3.0.

    Reports cross-sectional score correlation, rank correlation,
    and disagreement coverage between experts.
    """
    try:
        import numpy as np
        from scipy import stats
    except ImportError:
        return {"error": "numpy/scipy required for complementarity analysis"}

    expert_names = sorted(expert_scores.keys())
    if len(expert_names) < 2:
        return {"error": "need at least 2 experts for complementarity"}

    correlations: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []

    n_degenerate = 0
    for dt in prediction_dates:
        for i, e1 in enumerate(expert_names):
            for e2 in expert_names[i + 1 :]:
                s1 = expert_scores.get(e1, {}).get(dt, {})
                s2 = expert_scores.get(e2, {}).get(dt, {})
                common = sorted(set(s1.keys()) & set(s2.keys()))
                if len(common) < MIN_COMMON_NAMES:
                    continue
                v1 = np.array([s1[t] for t in common])
                v2 = np.array([s2[t] for t in common])
                r_pearson = float(np.corrcoef(v1, v2)[0, 1])
                r_spearman = float(stats.spearmanr(v1, v2).statistic)

                if not math.isfinite(r_pearson) or not math.isfinite(r_spearman):
                    # Degenerate/constant scores -- flag and skip.
                    n_degenerate += 1
                    correlations.append(
                        {
                            "date": dt,
                            "experts": [e1, e2],
                            "pearson": None,
                            "spearman": None,
                            "n_common": len(common),
                            "degenerate": True,
                        }
                    )
                    continue

                correlations.append(
                    {
                        "date": dt,
                        "experts": [e1, e2],
                        "pearson": round(r_pearson, 4),
                        "spearman": round(r_spearman, 4),
                        "n_common": len(common),
                    }
                )

                rank1 = np.argsort(np.argsort(-v1))
                rank2 = np.argsort(np.argsort(-v2))
                rank_diff = np.abs(rank1.astype(int) - rank2.astype(int))
                n_disagree = int(np.sum(rank_diff >= 5))
                disagreements.append(
                    {
                        "date": dt,
                        "experts": [e1, e2],
                        "n_rank_disagree_ge5": n_disagree,
                        "disagree_frac": round(n_disagree / len(common), 4),
                    }
                )

    finite_corrs = [
        c for c in correlations if c.get("degenerate") is not True
    ]
    avg_pearson = (
        sum(c["pearson"] for c in finite_corrs) / len(finite_corrs)
        if finite_corrs
        else None
    )
    avg_spearman = (
        sum(c["spearman"] for c in finite_corrs) / len(finite_corrs)
        if finite_corrs
        else None
    )
    avg_disagree = (
        sum(d["disagree_frac"] for d in disagreements) / len(disagreements)
        if disagreements
        else None
    )

    return {
        "expert_pairs": [
            {"pair": [e1, e2]}
            for i, e1 in enumerate(expert_names)
            for e2 in expert_names[i + 1 :]
        ],
        "n_dates_evaluated": len(prediction_dates),
        "n_degenerate_pairs": n_degenerate,
        "min_common_names": MIN_COMMON_NAMES,
        "avg_pearson_correlation": avg_pearson,
        "avg_spearman_correlation": avg_spearman,
        "avg_rank_disagreement_fraction": avg_disagree,
        "per_date_correlations": correlations[:20],
        "complementarity_assessment": _assess_complementarity(
            avg_pearson, avg_spearman, avg_disagree
        ),
    }


def _assess_complementarity(
    avg_pearson: float | None,
    avg_spearman: float | None,
    avg_disagree: float | None,
) -> str:
    """Produce a falsifiable complementarity assessment per S3.0."""
    if avg_pearson is None or avg_spearman is None:
        return "INSUFFICIENT_DATA"
    if not math.isfinite(avg_pearson) or not math.isfinite(avg_spearman):
        return "NON_FINITE_CORRELATION -- degenerate or constant score streams"
    if abs(avg_pearson) > 0.95 and abs(avg_spearman) > 0.95:
        return "NEAR_DUPLICATE -- experts produce near-identical scores"
    if avg_disagree is not None:
        if not math.isfinite(avg_disagree):
            return "NON_FINITE_CORRELATION -- degenerate disagreement metric"
        if avg_disagree < 0.05:
            return "LOW_DISAGREEMENT -- experts rarely alter each other's rankings"
    return "PLAUSIBLE -- experts show sufficient score diversity for combination"


def build_ledger(
    experts: list[ExpertSpec],
    prediction_dates: list[str],
    universe_tickers: list[str],
    score_loader: Any = None,
    *,
    decision_schedule: DecisionSchedule,
    session_calendar: SessionCalendar | None = None,
    decision_timestamp_fn: Any = None,
    require_realized_labels: bool = True,
    label_horizon_days: int = 60,
    complementarity_assessment: str | None = None,
) -> AdmissibilityLedger:
    """Build the complete admissibility ledger.

    This is the main entry point. In production use, pass a score_loader
    callable that returns score metadata for (expert, date) pairs.
    For testing, the ledger can be built from pre-extracted metadata.

    Args:
        decision_schedule: **required** -- declares the session timezone and
            decision time.  The schedule is used to compute a per-date
            decision timestamp (converted to UTC).  There is no default:
            callers must explicitly declare when decisions are made.
        session_calendar: optional declared trading-session calendar.
            When provided, prediction dates not in the calendar are
            rejected, and early-close sessions override the default
            decision time.  The calendar is fingerprinted and persisted
            with the ledger.
        decision_timestamp_fn: optional override callable
            ``(expert_name: str, prediction_date: str) -> str``
            returning a per-(expert, prediction_date) ISO-8601 decision
            timestamp.  When provided, its output is validated: it must
            not exceed the schedule's decision time for that date.  A
            caller cannot silently widen the window beyond the declared
            schedule.  A single global timestamp is deliberately NOT
            accepted -- it would let a late cutoff authorise scores for
            earlier dates that were generated after those dates' actual
            decisions (look-ahead).
        label_horizon_days: minimum calendar days between prediction_date
            and label_observation_end (default 60).  A 1-day label
            cannot satisfy a 60-day forward evaluation.
        require_realized_labels: if True, experts without realized labels
            are rejected (correct for historical evaluation).
        complementarity_assessment: result string from
            build_complementarity_report. Must be "PLAUSIBLE" for
            all_experts_fully_admitted to be True. None = not yet
            evaluated (fail-closed).
    """
    sched_digest = _schedule_digest(decision_schedule)
    cal_digest = session_calendar.digest() if session_calendar is not None else ""

    ledger = AdmissibilityLedger(
        created_at=datetime.now(tz=timezone.utc).isoformat(),
        experts=[e.name for e in experts],
        universe_size=len(universe_tickers),
        date_range=(
            (prediction_dates[0], prediction_dates[-1])
            if prediction_dates
            else ("", "")
        ),
        decision_schedule_timezone=decision_schedule.session_timezone,
        decision_schedule_time=decision_schedule.decision_time.isoformat(),
        decision_schedule_digest=sched_digest,
        session_calendar_digest=cal_digest,
        label_horizon_days=label_horizon_days,
    )

    per_expert_stats: dict[str, dict[str, int]] = {}
    for expert in experts:
        admitted = 0
        rejected = 0
        for dt in prediction_dates:
            # Reject non-session dates when a calendar is declared.
            if session_calendar is not None and not session_calendar.contains(dt):
                record = ExpertAdmissibilityRecord(
                    expert_name=expert.name,
                    prediction_date=dt,
                    model_fingerprint="MISSING",
                    training_cutoff="MISSING",
                    feature_data_cutoff="MISSING",
                    data_watermark="MISSING",
                    score_timestamp="MISSING",
                    decision_timestamp_utc="",
                    universe_size=len(universe_tickers),
                    scored_count=0,
                    missing_count=len(universe_tickers),
                    missingness_rate=1.0,
                    score_orientation=expert.orientation,
                    has_realized_labels=False,
                    score_artifact_digest="MISSING",
                    label_artifact_ref="MISSING",
                    label_observation_end="MISSING",
                    admitted=False,
                    rejection_reasons=[
                        f"date {dt} is not a valid session in the declared calendar"
                    ],
                )
                ledger.records.append(asdict(record))
                rejected += 1
                continue

            if score_loader is not None:
                score_meta = score_loader(expert, dt)
            else:
                score_meta = {
                    "model_fingerprint": "MISSING",
                    "training_cutoff": "MISSING",
                    "feature_data_cutoff": "MISSING",
                    "score_timestamp": "MISSING",
                    "score_keys": [],
                }

            schedule_ts = _decision_ts_from_schedule(
                decision_schedule, dt, calendar=session_calendar,
            )
            if decision_timestamp_fn is not None:
                dt_ts = decision_timestamp_fn(expert.name, dt)
                fn_dt = _parse_timestamp(dt_ts)
                sched_dt = _parse_timestamp(schedule_ts)
                if fn_dt > sched_dt:
                    raise ValueError(
                        f"decision_timestamp_fn returned {dt_ts} for "
                        f"({expert.name}, {dt}), which exceeds the "
                        f"declared schedule decision time {schedule_ts}. "
                        f"Overrides must not widen the decision window."
                    )
            else:
                dt_ts = schedule_ts

            record = validate_expert_date(
                expert, dt, score_meta, universe_tickers,
                decision_timestamp=dt_ts,
                require_realized_labels=require_realized_labels,
                label_horizon_days=label_horizon_days,
            )
            ledger.records.append(asdict(record))
            if record.admitted:
                admitted += 1
            else:
                rejected += 1

        per_expert_stats[expert.name] = {
            "admitted": admitted,
            "rejected": rejected,
            "total": admitted + rejected,
            "admission_rate": (
                round(admitted / (admitted + rejected), 4)
                if (admitted + rejected) > 0
                else 0
            ),
        }

    total_records = len(ledger.records)
    per_expert_ok = (
        total_records > 0
        and all(
            s["admitted"] > 0 and s["rejected"] == 0
            for s in per_expert_stats.values()
        )
    )
    complementarity_ok = complementarity_assessment == "PLAUSIBLE"

    ledger.summary = {
        "total_records": total_records,
        "per_expert": per_expert_stats,
        "complementarity_assessment": complementarity_assessment or "NOT_EVALUATED",
        "complementarity_ok": complementarity_ok,
        "all_experts_fully_admitted": per_expert_ok and complementarity_ok,
    }
    ledger.ledger_fingerprint = ledger.compute_fingerprint()

    return ledger


def write_ledger(ledger: AdmissibilityLedger, output_dir: Path) -> Path:
    """Write the ledger to disk as a JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "admissibility_ledger.json"
    payload = {
        "created_at": ledger.created_at,
        "experts": ledger.experts,
        "universe_size": ledger.universe_size,
        "date_range": ledger.date_range,
        "decision_schedule": {
            "timezone": ledger.decision_schedule_timezone,
            "decision_time": ledger.decision_schedule_time,
            "digest": ledger.decision_schedule_digest,
        },
        "session_calendar_digest": ledger.session_calendar_digest,
        "label_horizon_days": ledger.label_horizon_days,
        "summary": ledger.summary,
        "ledger_fingerprint": ledger.ledger_fingerprint,
        "records": ledger.records,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    return output_path


def _discover_prediction_dates(experts: list[ExpertSpec]) -> list[str]:
    """Discover prediction dates from score files in expert score directories.

    Scans each expert's score_dir for files named YYYY-MM-DD.{json,parquet}
    and returns the sorted union of all dates found.
    """
    suffixes = "|".join(s.lstrip(".") for s in SUPPORTED_SCORE_FORMATS)
    date_re = re.compile(rf"^(\d{{4}}-\d{{2}}-\d{{2}})\.({suffixes})$")
    dates: set[str] = set()
    for expert in experts:
        if expert.score_dir.is_dir():
            for f in expert.score_dir.iterdir():
                m = date_re.match(f.name)
                if m:
                    dates.add(m.group(1))
    return sorted(dates)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Stage 0 admissibility ledger for ensemble experiments"
    )
    parser.add_argument(
        "--expert",
        action="append",
        required=True,
        help="Expert name (repeat for each expert)",
    )
    parser.add_argument(
        "--score-dir",
        action="append",
        required=True,
        help="Score directory for each expert (same order as --expert)",
    )
    parser.add_argument(
        "--universe-file",
        required=True,
        help="Path to universe ticker list (one ticker per line or CSV)",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/ensemble_phase0/output",
        help="Output directory for ledger files",
    )
    parser.add_argument(
        "--label-horizon-days",
        type=int,
        default=60,
        help="Minimum label horizon in calendar days (default: 60)",
    )
    args = parser.parse_args()

    if len(args.expert) != len(args.score_dir):
        print("ERROR: --expert and --score-dir counts must match", file=sys.stderr)
        sys.exit(1)

    universe_path = Path(args.universe_file)
    if not universe_path.exists():
        print(f"ERROR: universe file not found: {universe_path}", file=sys.stderr)
        sys.exit(1)

    universe_tickers = [
        line.strip()
        for line in universe_path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    experts = [
        ExpertSpec(name=name, score_dir=Path(sd))
        for name, sd in zip(args.expert, args.score_dir)
    ]

    # Discover prediction dates from score directories.
    prediction_dates = _discover_prediction_dates(experts)
    if not prediction_dates:
        print(
            "ERROR: no prediction dates discovered from score directories -- "
            "cannot build a ledger with zero dates (fail-closed)",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Building admissibility ledger for {len(experts)} experts")
    print(f"Universe: {len(universe_tickers)} tickers")
    print(f"Prediction dates: {len(prediction_dates)} ({prediction_dates[0]} .. {prediction_dates[-1]})")

    # Build a REAL NYSE session calendar spanning the discovered prediction
    # dates -- this is the production default (not an opt-in flag): exchange
    # holidays and early-close sessions must always be excluded/handled, per
    # Codex review (a fixed US_EQUITY_CLOSE clock must not be the CLI default).
    # Pad the calendar query a week on each side of the discovered dates:
    # if the discovered range's exact boundary happens to fall on a
    # holiday (e.g. running the ledger for a single date that turns out to
    # be a market holiday), querying that exact zero-width range would
    # itself come back with no sessions at all and raise before we ever
    # get a chance to produce a proper per-date rejection record.
    calendar_query_start = date.fromisoformat(prediction_dates[0]) - timedelta(days=7)
    calendar_query_end = date.fromisoformat(prediction_dates[-1]) + timedelta(days=7)
    session_calendar = build_exchange_session_calendar(
        calendar_query_start.isoformat(), calendar_query_end.isoformat(),
    )
    non_session_dates = [d for d in prediction_dates if not session_calendar.contains(d)]
    if non_session_dates:
        print(
            f"NOTE: {len(non_session_dates)} discovered date(s) are not real "
            f"NYSE trading sessions and will be rejected: {non_session_dates}",
            file=sys.stderr,
        )

    def _file_score_loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
        """Load score metadata from the expert's score directory."""
        for suffix in SUPPORTED_SCORE_FORMATS:
            candidate = expert.score_dir / f"{dt}{suffix}"
            if candidate.exists():
                result = load_score_file(candidate)
                if result is None:
                    continue
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

    # First pass: build ledger without complementarity to collect scores.
    ledger_pass1 = build_ledger(
        experts, prediction_dates, universe_tickers,
        score_loader=_file_score_loader,
        decision_schedule=US_EQUITY_CLOSE,
        session_calendar=session_calendar,
        label_horizon_days=args.label_horizon_days,
    )

    # Compute complementarity report (S3.0) -- required for admission.
    expert_scores: dict[str, dict[str, dict[str, float]]] = {}
    for record in ledger_pass1.records:
        name = record["expert_name"]
        dt = record["prediction_date"]
        if name not in expert_scores:
            expert_scores[name] = {}
        for exp in experts:
            if exp.name == name:
                meta = _file_score_loader(exp, dt)
                scores = meta.get("scores", {})
                if scores:
                    expert_scores[name][dt] = {
                        k: float(v) for k, v in scores.items()
                        if isinstance(v, (int, float))
                    }
                break

    comp_assessment: str | None = None
    if len(expert_scores) >= 2:
        comp = build_complementarity_report(
            expert_scores, prediction_dates, universe_tickers
        )
        comp_assessment = comp.get("complementarity_assessment")
        comp_path = Path(args.output_dir) / "complementarity_report.json"
        comp_path.parent.mkdir(parents=True, exist_ok=True)
        comp_path.write_text(json.dumps(comp, indent=2) + "\n")
        print(f"Complementarity report written to {comp_path}")
        print(f"  Assessment: {comp_assessment}")

    # Rebuild ledger with complementarity result bound in.
    ledger = build_ledger(
        experts, prediction_dates, universe_tickers,
        score_loader=_file_score_loader,
        decision_schedule=US_EQUITY_CLOSE,
        session_calendar=session_calendar,
        label_horizon_days=args.label_horizon_days,
        complementarity_assessment=comp_assessment,
    )
    output_path = write_ledger(ledger, Path(args.output_dir))
    print(f"Ledger written to {output_path}")
    print(f"Fingerprint: {ledger.ledger_fingerprint}")

    # Fail-closed verdict.
    if ledger.summary.get("all_experts_fully_admitted"):
        print("RESULT: All experts fully admitted -- Phase A may proceed")
    else:
        print("RESULT: FAIL -- not all experts fully admitted", file=sys.stderr)
        for name, stats in ledger.summary.get("per_expert", {}).items():
            if stats["rejected"] > 0:
                print(f"  {name}: {stats['rejected']}/{stats['total']} rejected")
        if not ledger.summary.get("complementarity_ok"):
            print(
                f"  complementarity: {ledger.summary.get('complementarity_assessment')} "
                f"(must be PLAUSIBLE)",
                file=sys.stderr,
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
