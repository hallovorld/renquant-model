"""G4 forward series consumer — v4 §5 step 3 (score "backfill" RETIRED).

CRUX FINDING (v4 §4 data hygiene): under the merged v4 amendment
(``DESIGN_AMENDMENT_v4_executable_next_open_evaluation.md``), **backfill
has NO inferential role left**. The terminal/inferential series comprises
ONLY sessions admitted AFTER the activation commit, produced by the
canonical shadow job (:mod:`renquant_orchestrator.g4_shadow_job`) running
FORWARD (§4 "post-activation-only clause": "No backfill of pilot,
pre-freeze, or inter-stage sessions into the terminal series under any
circumstance"). The old close-anchored ``runs.alpaca.db`` extractor —
including its private as-of helper ``select_asof_runs`` — manufactured an
inferential series from PRE-FREEZE historical sessions, which is exactly
the operation §4 prohibits (and whose 15-20 accrued shadow sessions are
DOUBLY inadmissible: old contract + prior analytical exposure in
model#58/#59). It is therefore RETIRED IN FULL:

* ``select_asof_runs`` / ``AsOfExclusion`` / ``RunSelection`` — GONE. v4
  §5 subsumes the close-anchored as-of helper into the pipeline-owned
  decision-schedule API; "no private cross-repo as-of helper survives
  anywhere". This module holds none.
* the ``runs.alpaca.db`` / ``candidate_scores`` scan, ``--score-column``,
  the per-date candidate-evidence JSON, and the local ledger build — GONE.
  There is no database-scan enrollment path in this file at all, so a
  legacy row is STRUCTURALLY incapable of feeding the inferential series.

What this tool IS now: a **read-only forward consumer** of the canonical
G4 evidence store. It CONSUMES the merged step-1 public contract
``renquant_pipeline.decision_schedule`` (validate_arm_record /
validate_session_records / SessionWindow / job_identity, pipeline#209)
and the step-2 store + admission ledger
(:mod:`renquant_orchestrator.g4_shadow_job.G4EvidenceStore` +
:func:`renquant_orchestrator.g4_admission.admit_g4_session`, orch#551).
For a set of decision sessions it reports which are eligible to enter the
inferential/terminal series and REFUSES every session that is not, with
three fail-closed gates layered on the step-2 admission verdict:

1. **Canonical-store provenance.** A session is evaluated only from the
   canonical store's write-once records. A missing session, a non-canonical
   record, a tampered/forged record, a divergent retry, or a watermark
   after close makes ``admit_g4_session`` return ``admissible=False`` —
   the session is ``REFUSED`` (integrity), never enrolled.
2. **Registration binding (series_eligible).** The step-2 verdict's
   ``series_eligible`` is True only when the frozen registration
   identifiers (calendar id + price-source id, frozen at the
   pilot-registration commit — v4 §4) were supplied AND match the record.
   This tool READS that flag; it NEVER mints series-eligibility itself.
3. **Post-activation data hygiene (the model-side gate this tool adds).**
   Even a canonical, contract-valid, registration-bound session is
   enrolled ONLY when its ``decision_session`` is strictly AFTER the
   frozen ``activation_session`` (v4 §4). A pre-freeze / pre-activation
   session is demoted to ``DIAGNOSTIC_ONLY`` (discussable descriptively,
   never enrolled) — this is what keeps the burned pre-freeze sessions
   out of any inferential series.

``INFERENTIAL_SERIES_CANDIDATE`` is reachable ONLY through all three
gates; ``DIAGNOSTIC_ONLY`` marks a clean canonical observation that is
structurally barred from the series; ``REFUSED`` marks an integrity
failure. Because there is no non-canonical (DB-scan) code path, no row
can acquire an inferential role by any route other than the canonical
forward store.

Diagnostic coverage of the burned pre-freeze shadow sessions is
explicitly OUT OF SCOPE here: v4 §4 already disqualifies them from
inference and model#58/#59 already produced their descriptive analysis;
re-reading them would only re-manufacture the exposure §4 burns. This
tool never touches ``runs.alpaca.db``.

Read-only / RESEARCH-ONLY: reads the caller-chosen store root, writes a
report ONLY under a caller-chosen experiment output directory, never a
production path (LONG ledger #2), never the store. Phase 0 stays BLOCKED;
the canonical shadow job is not yet scheduled, so a forward run today
enrolls ZERO sessions — the correct fail-closed state.

Usage::

    python -m experiments.ensemble_phase0.backfill_scores \\
        --store-root /path/to/g4_evidence_store \\
        --activation-session 2026-08-01 \\
        --frozen-calendar-id XNYS/v1 \\
        --frozen-price-source-id alpaca_sip/v1 \\
        --session 2026-08-03 --session 2026-08-04 \\
        --output-dir experiments/ensemble_phase0/output/forward_series
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from renquant_pipeline.decision_schedule import (
    EXPECTED_ARMS,
    SessionWindow,
)
from renquant_orchestrator.g4_admission import admit_g4_session
from renquant_orchestrator.g4_shadow_job import (
    G4EvidenceStore,
    resolve_session_window,
)

#: What this file is after v4 §5 step 3. Kept as a machine-readable marker
#: so a grep for the old "backfill" role lands on the retirement notice.
TOOL_ROLE = "g4_forward_series_consumer"

#: Classification of one evaluated session (the only three outcomes).
INFERENTIAL_SERIES_CANDIDATE = "inferential_series_candidate"
DIAGNOSTIC_ONLY = "diagnostic_only"
REFUSED = "refused"

#: Model-side data-hygiene refusal codes (additive to the step-2 admission
#: reason codes, which are reported verbatim alongside). These are the
#: gates this tool layers ON TOP of the orchestrator admission verdict.
REASON_PRE_ACTIVATION = "pre_activation_session"
REASON_NO_ACTIVATION_REGISTERED = "no_activation_session_registered"
REASON_REGISTRATION_UNBOUND = "registration_unbound"

#: Report classification tag for the written artifact.
CLASSIFICATION = "RESEARCH_ONLY_FORWARD_CONSUMER"


@dataclass
class ForwardSessionOutcome:
    """One decision session's forward-consumer verdict.

    ``inferential_role`` is the single load-bearing enrollment decision:
    True ONLY for a canonical, contract-admissible, registration-bound,
    post-activation session. ``admission_series_eligible`` is the step-2
    verdict's flag (READ, never minted here); this tool's
    ``inferential_role`` additionally requires the post-activation gate,
    so it can only ever be a SUBSET of admission-series-eligible sessions.
    """

    decision_session: str
    classification: str
    inferential_role: bool
    admission_series_eligible: bool
    admissible: bool
    registration_bound: bool
    post_activation: bool
    activation_session: "str | None"
    model_refusals: list[str] = field(default_factory=list)
    admission_reason_codes: list[str] = field(default_factory=list)
    admission_budget: "str | None" = None
    detail: str = ""
    admission: dict[str, Any] = field(default_factory=dict)


def _is_post_activation(decision_session: str, activation_session: "str | None") -> bool:
    """Strictly-after test (v4 §4: "admitted AFTER the activation commit").

    Fail-closed: with no frozen ``activation_session`` (the current
    reality — nothing has been registered) NO session is post-activation,
    so nothing is enrollable.
    """
    if activation_session is None:
        return False
    return dt.date.fromisoformat(decision_session) > dt.date.fromisoformat(activation_session)


def evaluate_forward_session(
    store: G4EvidenceStore,
    *,
    decision_session: str,
    activation_session: "str | None",
    frozen_calendar_id: "str | None" = None,
    frozen_price_source_id: "str | None" = None,
    session_window: "SessionWindow | None" = None,
    calendar: Any | None = None,
    expected_arms: Sequence[str] = EXPECTED_ARMS,
    evaluated_at: "dt.datetime | None" = None,
) -> ForwardSessionOutcome:
    """Evaluate ONE decision session against the canonical store + contract.

    Consumes the step-2 admission verdict (``admit_g4_session`` with
    ``persist=False`` — read-only, writes nothing) and layers the
    model-side post-activation data-hygiene gate on top. Never raises on
    a verdict outcome; only on caller errors (bad session date,
    unresolvable window).
    """
    if session_window is None:
        session_window = resolve_session_window(decision_session, calendar=calendar)

    verdict = admit_g4_session(
        store,
        expected_session=decision_session,
        session_window=session_window,
        expected_arms=tuple(expected_arms),
        expected_calendar_id=frozen_calendar_id,
        expected_price_source_id=frozen_price_source_id,
        evaluated_at=evaluated_at,
        persist=False,  # read-only consumer — admission EXECUTION is the orchestrator's job
    )

    admissible = bool(verdict.get("admissible"))
    registration_bound = bool(verdict.get("registration_bound"))
    admission_series_eligible = bool(verdict.get("series_eligible"))
    post_activation = _is_post_activation(decision_session, activation_session)

    model_refusals: list[str] = []
    if admissible:
        if activation_session is None:
            model_refusals.append(REASON_NO_ACTIVATION_REGISTERED)
        elif not post_activation:
            model_refusals.append(REASON_PRE_ACTIVATION)
        if not registration_bound:
            model_refusals.append(REASON_REGISTRATION_UNBOUND)

    # Enrollment is the AND of all three gates. series_eligible already
    # encodes (admissible AND registration_bound); the post-activation gate
    # is the extra model-side data-hygiene condition.
    inferential_role = admissible and admission_series_eligible and post_activation

    if not admissible:
        classification = REFUSED
    elif inferential_role:
        classification = INFERENTIAL_SERIES_CANDIDATE
    else:
        classification = DIAGNOSTIC_ONLY

    detail_bits = []
    if classification == DIAGNOSTIC_ONLY:
        detail_bits.append(
            "clean canonical observation, but STRUCTURALLY barred from the "
            "inferential series: " + ", ".join(model_refusals or ["not_series_eligible"])
        )
    elif classification == REFUSED:
        detail_bits.append("integrity refusal from the step-2 admission verdict")
    if verdict.get("detail"):
        detail_bits.append(str(verdict["detail"]))

    return ForwardSessionOutcome(
        decision_session=decision_session,
        classification=classification,
        inferential_role=inferential_role,
        admission_series_eligible=admission_series_eligible,
        admissible=admissible,
        registration_bound=registration_bound,
        post_activation=post_activation,
        activation_session=activation_session,
        model_refusals=model_refusals,
        admission_reason_codes=list(verdict.get("reason_codes", [])),
        admission_budget=verdict.get("budget"),
        detail="; ".join(detail_bits),
        admission=dict(verdict),
    )


@dataclass
class InferentialSeriesReport:
    """The assembled forward series report — enrolled sessions plus the
    full fail-closed ledger of every evaluated session."""

    tool_role: str = TOOL_ROLE
    classification: str = CLASSIFICATION
    store_root: str = ""
    activation_session: "str | None" = None
    frozen_calendar_id: "str | None" = None
    frozen_price_source_id: "str | None" = None
    created_at: str = ""
    n_evaluated: int = 0
    n_enrolled: int = 0
    n_diagnostic_only: int = 0
    n_refused: int = 0
    enrolled_sessions: list[str] = field(default_factory=list)
    diagnostic_only_sessions: list[str] = field(default_factory=list)
    refused_sessions: list[str] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)


class SeriesIntegrityError(RuntimeError):
    """A structural invariant of series assembly was violated — a session
    reached the enrolled set without passing all three gates. Raised loudly
    (fail-closed) so a hygiene regression can never silently enroll a
    pre-freeze / non-canonical session."""


def assemble_inferential_series(
    store: G4EvidenceStore,
    *,
    sessions: Sequence[str],
    activation_session: "str | None",
    frozen_calendar_id: "str | None" = None,
    frozen_price_source_id: "str | None" = None,
    calendar: Any | None = None,
    session_windows: "dict[str, SessionWindow] | None" = None,
    evaluated_at: "dt.datetime | None" = None,
    store_root: "str | None" = None,
) -> InferentialSeriesReport:
    """Evaluate every session and assemble the enrolled inferential series.

    The enrolled set is EXACTLY the ``INFERENTIAL_SERIES_CANDIDATE``
    outcomes; every other session is quarantined (diagnostic-only) or
    refused. A closing structural assertion re-checks that no enrolled
    session lacks any gate — a pre-freeze, unregistered, or non-canonical
    session can never appear in ``enrolled_sessions``.
    """
    outcomes: list[ForwardSessionOutcome] = []
    for session in sessions:
        window = (session_windows or {}).get(session)
        outcomes.append(
            evaluate_forward_session(
                store,
                decision_session=session,
                activation_session=activation_session,
                frozen_calendar_id=frozen_calendar_id,
                frozen_price_source_id=frozen_price_source_id,
                session_window=window,
                calendar=calendar,
                evaluated_at=evaluated_at,
            )
        )

    enrolled = [o for o in outcomes if o.classification == INFERENTIAL_SERIES_CANDIDATE]
    diagnostic = [o for o in outcomes if o.classification == DIAGNOSTIC_ONLY]
    refused = [o for o in outcomes if o.classification == REFUSED]

    # Structural invariant (belt-and-suspenders, fail-closed): every
    # enrolled session must have passed ALL gates.
    for o in enrolled:
        if not (o.admissible and o.admission_series_eligible and o.post_activation and o.inferential_role):
            raise SeriesIntegrityError(
                f"session {o.decision_session} reached the enrolled set without "
                f"all gates: admissible={o.admissible} "
                f"series_eligible={o.admission_series_eligible} "
                f"post_activation={o.post_activation}"
            )

    return InferentialSeriesReport(
        store_root=store_root if store_root is not None else str(store.root),
        activation_session=activation_session,
        frozen_calendar_id=frozen_calendar_id,
        frozen_price_source_id=frozen_price_source_id,
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        n_evaluated=len(outcomes),
        n_enrolled=len(enrolled),
        n_diagnostic_only=len(diagnostic),
        n_refused=len(refused),
        enrolled_sessions=[o.decision_session for o in enrolled],
        diagnostic_only_sessions=[o.decision_session for o in diagnostic],
        refused_sessions=[o.decision_session for o in refused],
        outcomes=[asdict(o) for o in outcomes],
    )


def write_report(report: InferentialSeriesReport, output_dir: Path) -> Path:
    """Write the forward-series report under a caller-chosen output dir
    (never a production path, never the store)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "forward_series_report.json"
    path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "_experiment_classification.json").write_text(
        json.dumps(
            {"classification": CLASSIFICATION, "tool_role": TOOL_ROLE,
             "created_at": report.created_at},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _load_sessions(args: argparse.Namespace) -> list[str]:
    sessions = list(args.session or [])
    if args.sessions_file is not None:
        sessions.extend(
            line.strip()
            for line in args.sessions_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )
    # Validate + dedupe, preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for s in sessions:
        dt.date.fromisoformat(s)  # caller error on malformed date
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="G4 forward series consumer (v4 §5 step 3; score backfill RETIRED)",
    )
    parser.add_argument(
        "--store-root", required=True, type=Path,
        help="Root of the canonical G4 evidence store (read-only).",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Experiment output directory for the report (never a production path).",
    )
    parser.add_argument(
        "--activation-session", default=None,
        help=(
            "The frozen activation-commit session (v4 §4). Sessions must be "
            "strictly AFTER it to enter the inferential series. Omitted = "
            "nothing enrollable (fail-closed; the current pre-registration state)."
        ),
    )
    parser.add_argument(
        "--frozen-calendar-id", default=None,
        help="Frozen registration calendar id (v4 §4). Required for series eligibility.",
    )
    parser.add_argument(
        "--frozen-price-source-id", default=None,
        help="Frozen registration price-source id (v4 §4). Required for series eligibility.",
    )
    parser.add_argument(
        "--session", action="append", default=[],
        help="A decision session to evaluate (repeatable).",
    )
    parser.add_argument(
        "--sessions-file", type=Path, default=None,
        help="File of decision sessions, one per line ('#' comments allowed).",
    )
    args = parser.parse_args(argv)

    if not args.store_root.exists():
        print(f"ERROR: store root not found: {args.store_root}", file=sys.stderr)
        return 1
    if args.sessions_file is not None and not args.sessions_file.exists():
        print(f"ERROR: sessions file not found: {args.sessions_file}", file=sys.stderr)
        return 1

    sessions = _load_sessions(args)
    if not sessions:
        print("ERROR: no decision sessions given (--session / --sessions-file)", file=sys.stderr)
        return 1

    store = G4EvidenceStore(args.store_root)
    report = assemble_inferential_series(
        store,
        sessions=sessions,
        activation_session=args.activation_session,
        frozen_calendar_id=args.frozen_calendar_id,
        frozen_price_source_id=args.frozen_price_source_id,
        calendar=None,  # real NYSE at the CLI; tests inject a fake calendar
    )
    path = write_report(report, args.output_dir)

    print(f"G4 forward series consumer ({TOOL_ROLE})")
    print(f"  Store: {args.store_root}")
    print(f"  Activation session: {args.activation_session or '(none registered — nothing enrollable)'}")
    print(f"  Evaluated: {report.n_evaluated}")
    print(f"  Enrolled (inferential series): {report.n_enrolled} -> {report.enrolled_sessions}")
    print(f"  Diagnostic-only (barred from series): {report.n_diagnostic_only}")
    print(f"  Refused (integrity): {report.n_refused}")
    print(f"  Report: {path}")
    print(f"  Classification: {CLASSIFICATION}")
    if report.n_enrolled == 0:
        print(
            "  NOTE: 0 enrolled is EXPECTED pre-registration — no activation "
            "commit + no forward canonical sessions exist yet (Phase 0 BLOCKED). "
            "Fail-closed, not an error.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
