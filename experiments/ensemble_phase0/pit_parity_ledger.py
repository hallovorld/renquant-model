"""PIT input-parity ledger — v4 §2/§5 step 3, re-homed onto the canonical store.

v4 §2: "The PIT parity ledger is NOT schedule-agnostic: it must be rerun
against these exact watermark, universe-membership, artifact-selection,
and execution fields. Its report is an input to admission, not a
substitute for it." This module produces that per-session parity report by
CONSUMING the merged contracts, exact-pinned — never a private as-of scan:

* step-1 ``renquant_pipeline.decision_schedule`` (validate_session_records,
  SessionWindow, EXPECTED_ARMS — pipeline#209) for record integrity,
  watermark recomputation, job identity, and pairing;
* step-2 ``renquant_orchestrator.g4_shadow_job.G4EvidenceStore`` +
  ``g4_admission.recompute_watermark_from_store`` (orch#551) as the
  canonical, write-once, digest-named evidence source and the BYTE-LEVEL
  watermark hook (v4 §2 r2: the declared watermark is not self-certifying).

RETIRED (v4 §5, "no private cross-repo as-of helper survives anywhere"):
the old close-anchored ``select_asof_runs`` import, the ``RunSelection``
type, and the twin ``runs.alpaca.db`` / ``runs.alpaca_shadow.db`` bundle
scan. The two arms are no longer prod-vs-shadow pipeline runs selected by
commit order; they are the frozen registered pair (``l1`` / ``champion``,
v4 §3) whose immutable records live side-by-side in ONE canonical store.

Because the canonical job (``run_g4_shadow_session``) builds BOTH arms
from a single manifested input set, input parity is largely by
construction — but this ledger independently RE-VERIFIES it against the
persisted bytes (its report is an input to admission, not a substitute),
which is the exact-pinned check v4 §2 requires.

Verdict-bearing dimensions (INPUTS only — the arms differ in scorer
artifact BY DESIGN, so scorer identity must never enter the verdict):

* ``contract_integrity`` — ``validate_session_records`` passes for the
  session (both arms present, schema/fields valid, declared watermark
  ``<= close`` and equal to the BYTE-recomputed max event-time, one
  canonical job identity per arm, orders scheduled for open(T+1)). Any
  contract reason code ⇒ ``not_parity``.
* ``input_manifest`` — the two arms' ``input_manifest`` must be IDENTICAL
  (same input names → same ``{digest, max_event_time}``). This is the v4
  §3 "same manifested information set" at the strongest resolution: the
  content-addressed digests themselves, not a bundle summary.
* ``declared_watermark`` — equal ``declared_input_watermark``.
* ``frozen_identifiers`` — equal ``calendar_id`` and ``price_source_id``.
* ``schedule_target`` — equal ``orders_scheduled_for`` (both = open(T+1)).
* ``schema_version`` — equal record ``schema_version``.

Excluded from the verdict (reported informationally): ``artifact_digests``
/ ``config_digest`` (embed the scorer choice — the experimental variable),
``scores`` / ``orders`` (decision OUTCOMES, not inputs), and
``run_bundle_timestamp`` (evidence only per v4 §2 — the old
``decision_skew`` dimension is GONE: both arms are produced in one
canonical job run from one input set, so cross-arm commit skew is not a
meaningful input-parity signal).

RESEARCH-ONLY: reads the caller-chosen store root; writes ONLY under a
caller-chosen output directory, never a production path, never the store.
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
    ARM_CHAMPION,
    ARM_L1,
    SessionWindow,
    validate_session_records,
)
from renquant_orchestrator.g4_admission import recompute_watermark_from_store
from renquant_orchestrator.g4_shadow_job import (
    G4EvidenceStore,
    resolve_session_window,
)

LEDGER_SCHEMA_VERSION = "pit_parity_ledger.v2_canonical_store"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "pit_parity"

#: The two frozen registered arms (v4 §3). Parity is defined between them.
PARITY_ARMS: tuple[str, ...] = (ARM_L1, ARM_CHAMPION)


@dataclass
class DimensionResult:
    dimension: str
    match: bool
    detail: str = ""


@dataclass
class ParityVerdict:
    session_date: str
    verdict: str  # "parity" | "not_parity"
    reasons: list[str] = field(default_factory=list)
    dimensions: list[DimensionResult] = field(default_factory=list)
    arm_job_ids: dict[str, Any] = field(default_factory=dict)
    informational: dict[str, Any] = field(default_factory=dict)
    ledger_schema_version: str = LEDGER_SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def _qualifying_by_arm(
    records: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """First qualifying (non-failure, non-unreadable) record per arm.

    Retries are byte-identical by contract, so the first is representative;
    ``validate_session_records`` independently flags any divergent retry."""
    by_arm: dict[str, dict[str, Any]] = {}
    for record in records:
        if "__unreadable__" in record or isinstance(record.get("failure"), dict):
            continue
        arm = str(record.get("arm"))
        by_arm.setdefault(arm, record)
    return by_arm


def compare_session_parity(
    store: G4EvidenceStore,
    decision_session: str,
    *,
    session_window: SessionWindow,
    expected_calendar_id: "str | None" = None,
    expected_price_source_id: "str | None" = None,
    expected_arms: Sequence[str] = PARITY_ARMS,
) -> ParityVerdict:
    """Fail-closed PIT input-parity verdict for one canonical session."""
    v = ParityVerdict(session_date=decision_session, verdict="not_parity")

    loaded = store.load_session_records(decision_session)
    records = [rec for _path, rec in loaded]
    if not records:
        v.reasons.append("missing_session: no records under the canonical store")
        return v

    # Contract integrity gate (byte-level watermark hook, exact-pinned ids).
    session_verdict = validate_session_records(
        records,
        session_window=session_window,
        expected_arms=tuple(expected_arms),
        recompute_max_event_time=recompute_watermark_from_store(store),
        expected_calendar_id=expected_calendar_id,
        expected_price_source_id=expected_price_source_id,
    )
    contract_ok = bool(session_verdict.ok)
    v.dimensions.append(
        DimensionResult(
            "contract_integrity",
            contract_ok,
            "" if contract_ok else f"reason_codes={list(session_verdict.reason_codes)}",
        )
    )
    if not contract_ok:
        v.reasons.extend(f"contract:{c}" for c in session_verdict.reason_codes)

    by_arm = _qualifying_by_arm(records)
    v.arm_job_ids = {arm: by_arm.get(arm, {}).get("job_id") for arm in expected_arms}

    missing = [arm for arm in expected_arms if arm not in by_arm]
    if missing:
        # Cannot compute cross-arm dimensions without both arms; verdict
        # stays "not_parity" (the dataclass default).
        v.reasons.append(f"missing_qualifying_arm: {missing}")
        return v

    # Exactly the frozen pair for the pairwise comparison.
    a_arm, b_arm = expected_arms[0], expected_arms[1]
    a, b = by_arm[a_arm], by_arm[b_arm]

    def _dim(name: str, va: Any, vb: Any, reason: str) -> None:
        ok = va == vb
        v.dimensions.append(
            DimensionResult(name, ok, "" if ok else f"{a_arm}={va!r} {b_arm}={vb!r}")
        )
        if not ok:
            v.reasons.append(reason)

    _dim("input_manifest", a.get("input_manifest"), b.get("input_manifest"),
         "input_manifest_divergence")
    _dim("declared_watermark", a.get("declared_input_watermark"),
         b.get("declared_input_watermark"), "declared_watermark_mismatch")
    _dim("frozen_calendar_id", a.get("calendar_id"), b.get("calendar_id"),
         "calendar_id_mismatch")
    _dim("frozen_price_source_id", a.get("price_source_id"), b.get("price_source_id"),
         "price_source_id_mismatch")
    _dim("schedule_target", a.get("orders_scheduled_for"),
         b.get("orders_scheduled_for"), "schedule_target_mismatch")
    _dim("schema_version", a.get("schema_version"), b.get("schema_version"),
         "schema_version_mismatch")

    # Informational — NEVER verdict-bearing (the scorer choice is the
    # experimental variable; decision outcomes are not inputs).
    v.informational = {
        "artifact_digests": {a_arm: a.get("artifact_digests"),
                             b_arm: b.get("artifact_digests")},
        "config_digest": {a_arm: a.get("config_digest"), b_arm: b.get("config_digest")},
        "artifact_digests_equal": a.get("artifact_digests") == b.get("artifact_digests"),
        "run_bundle_timestamp": {a_arm: a.get("run_bundle_timestamp"),
                                 b_arm: b.get("run_bundle_timestamp")},
    }

    if not v.reasons:
        v.verdict = "parity"
    return v


def build_parity_ledger(
    store: G4EvidenceStore,
    *,
    sessions: Sequence[str],
    session_windows: "dict[str, SessionWindow] | None" = None,
    calendar: Any | None = None,
    expected_calendar_id: "str | None" = None,
    expected_price_source_id: "str | None" = None,
) -> list[ParityVerdict]:
    """PIT parity verdicts for an EXPLICIT session list (exact-pinned;
    no DB scan, no as-of selection)."""
    verdicts: list[ParityVerdict] = []
    for session in sessions:
        window = (session_windows or {}).get(session)
        if window is None:
            window = resolve_session_window(session, calendar=calendar)
        verdicts.append(
            compare_session_parity(
                store,
                session,
                session_window=window,
                expected_calendar_id=expected_calendar_id,
                expected_price_source_id=expected_price_source_id,
            )
        )
    return verdicts


def write_parity_ledger(
    verdicts: list[ParityVerdict], output_dir: Path = DEFAULT_OUTPUT_DIR
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"pit_parity_{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(v.to_json() + "\n")
    return path


def _load_sessions(args: argparse.Namespace) -> list[str]:
    sessions = list(args.session or [])
    if args.sessions_file is not None:
        sessions.extend(
            line.strip()
            for line in args.sessions_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )
    seen: set[str] = set()
    ordered: list[str] = []
    for s in sessions:
        dt.date.fromisoformat(s)
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store-root", required=True, type=Path,
                    help="Root of the canonical G4 evidence store (read-only).")
    ap.add_argument("--session", action="append", default=[],
                    help="A decision session to check (repeatable).")
    ap.add_argument("--sessions-file", type=Path, default=None,
                    help="File of decision sessions, one per line ('#' comments allowed).")
    ap.add_argument("--calendar-id", default=None, help="Frozen calendar id to bind against.")
    ap.add_argument("--price-source-id", default=None,
                    help="Frozen price-source id to bind against.")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = ap.parse_args(argv)

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
    verdicts = build_parity_ledger(
        store, sessions=sessions, calendar=None,
        expected_calendar_id=args.calendar_id,
        expected_price_source_id=args.price_source_id,
    )
    path = write_parity_ledger(verdicts, args.output_dir)
    n_par = sum(1 for v in verdicts if v.verdict == "parity")
    print(f"pit_parity: {n_par}/{len(verdicts)} sessions parity -> {path}")
    for v in verdicts:
        if v.verdict != "parity":
            print(f"  {v.session_date}: {'; '.join(v.reasons)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
