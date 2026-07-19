"""PIT input-parity comparator — MODEL-ONLY, declared-data-contract (v4 §2/§5 step 3).

v4 §2: "The PIT parity ledger is NOT schedule-agnostic: it must be rerun
against these exact watermark, universe-membership, artifact-selection, and
execution fields. Its report is an input to admission, not a substitute for
it." This module owns the *model-domain* half of that report: given the two
frozen arms' decision records for one session, is their PIT **input** set
identical across the dimensions that must match by design?

REPO-BOUNDARY SPLIT (why this module imports NO orchestrator).
``renquant-orchestrator`` already depends on ``renquant-model``; a
model → orchestrator import would reverse the boundary contract. So the
canonical G4 evidence store (``renquant_orchestrator.g4_shadow_job.
G4EvidenceStore``), the admission ledger (``renquant_orchestrator.
g4_admission.admit_g4_session``), the byte-level watermark hook, and the
``renquant_pipeline.decision_schedule.validate_session_records`` contract
gate are ALL executed by the **umbrella integration harness** (``RenQuant``),
which holds the exact model/pipeline/orchestrator/artifacts pins plus the
canonical store. The umbrella loads the two arms' records from the store,
runs the contract-integrity gate, and passes the results here as PLAIN DATA.

This module therefore never reads the store, never runs admission, and
imports only stdlib + the pipeline arm-name constants (``renquant-pipeline``
is a lower-level contract both the model experiments and the orchestrator
consume — it is not the reverse edge being removed).

DECLARED DATA CONTRACT
----------------------
``compare_input_parity`` accepts, for ONE decision session:

* ``records``: an iterable of decision-record **mappings** (plain dicts,
  JSON-shaped) — exactly the records the canonical job persisted, as the
  umbrella loaded them from the store. Each qualifying (non-failure,
  non-unreadable) record must carry ``arm`` plus the input-bearing keys
  ``input_manifest`` (``{name -> {digest, max_event_time}}``),
  ``declared_input_watermark``, ``calendar_id``, ``price_source_id``,
  ``orders_scheduled_for``, ``schema_version``, and ``job_id``; the
  informational-only keys ``artifact_digests`` / ``config_digest`` /
  ``run_bundle_timestamp`` are reported but never verdict-bearing.
* ``contract_integrity`` (OPTIONAL): the umbrella's pre-computed
  ``validate_session_records`` outcome as a plain :class:`ContractIntegrity`
  (``ok`` + ``reason_codes``). When supplied and not ``ok`` the verdict is
  ``not_parity`` with ``contract:<code>`` reasons; when omitted the
  comparator evaluates INPUT-field parity only and marks the contract
  dimension ``not_evaluated`` (honest that a model-only run did not run the
  contract/watermark gate — that gate is the umbrella's responsibility).

Output is a :class:`ParityVerdict` (plain dataclass, JSON-serialisable).
No orchestrator/store/pipeline-runtime type ever enters the input or output.

Verdict-bearing dimensions (INPUTS only — the arms differ in scorer artifact
BY DESIGN, so scorer identity must never enter the verdict): ``input_manifest``
(digest-equality = v4 §3 "same manifested information set" at the strongest
resolution — the content-addressed digests, not a bundle summary),
``declared_watermark``, frozen ``calendar_id`` / ``price_source_id``,
``schedule_target`` (equal ``orders_scheduled_for`` = open(T+1)), and
``schema_version``. Excluded from the verdict (reported informationally):
``artifact_digests`` / ``config_digest`` (embed the scorer choice — the
experimental variable), ``scores`` / ``orders`` (decision OUTCOMES, not
inputs), and ``run_bundle_timestamp``.

RETIRED (v4 §5, "no private cross-repo as-of helper survives anywhere"): the
old close-anchored ``select_asof_runs`` import, the ``RunSelection`` type,
and the twin ``runs.alpaca.db`` / ``runs.alpaca_shadow.db`` bundle scan. No
database code path exists here.

RESEARCH-ONLY: the optional CLI reads plain-JSON record exports from a
caller-chosen path and writes a report under a caller-chosen output dir —
never a production path, never a store.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from renquant_pipeline.decision_schedule import ARM_CHAMPION, ARM_L1

LEDGER_SCHEMA_VERSION = "pit_parity_ledger.v3_model_only"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "pit_parity"

#: The two frozen registered arms (v4 §3). Parity is defined between them.
PARITY_ARMS: tuple[str, ...] = (ARM_L1, ARM_CHAMPION)

#: Record keys whose cross-arm equality IS the input-parity verdict.
INPUT_PARITY_DIMENSIONS: tuple[tuple[str, str, str], ...] = (
    ("input_manifest", "input_manifest", "input_manifest_divergence"),
    ("declared_watermark", "declared_input_watermark", "declared_watermark_mismatch"),
    ("frozen_calendar_id", "calendar_id", "calendar_id_mismatch"),
    ("frozen_price_source_id", "price_source_id", "price_source_id_mismatch"),
    ("schedule_target", "orders_scheduled_for", "schedule_target_mismatch"),
    ("schema_version", "schema_version", "schema_version_mismatch"),
)


@dataclass
class DimensionResult:
    dimension: str
    match: bool
    detail: str = ""


@dataclass
class ContractIntegrity:
    """The umbrella's pre-computed ``validate_session_records`` outcome,
    passed to the comparator as plain data (no pipeline/orchestrator type).

    ``ok`` is the session-level contract verdict; ``reason_codes`` are the
    contract reason codes (empty when ``ok``). Construct it in the umbrella
    harness from the ``SessionVerdict`` and hand it in — this keeps the
    contract/watermark gate on the umbrella side of the boundary while the
    model comparator still folds the result into a single verdict."""

    ok: bool
    reason_codes: list[str] = field(default_factory=list)


@dataclass
class ParityVerdict:
    session_date: str
    verdict: str  # "parity" | "not_parity"
    reasons: list[str] = field(default_factory=list)
    dimensions: list[DimensionResult] = field(default_factory=list)
    arm_job_ids: dict[str, Any] = field(default_factory=dict)
    informational: dict[str, Any] = field(default_factory=dict)
    contract_evaluated: bool = False
    ledger_schema_version: str = LEDGER_SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def qualifying_records_by_arm(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """First qualifying (non-failure, non-unreadable) record per arm.

    Pure data helper: ``records`` are plain decision-record mappings (as the
    umbrella loaded them from the canonical store). Retries are byte-identical
    by the store's contract, so the first is representative; the umbrella's
    ``validate_session_records`` run independently flags any divergent retry
    and is surfaced via :class:`ContractIntegrity`."""
    by_arm: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        if "__unreadable__" in record or isinstance(record.get("failure"), Mapping):
            continue
        arm = str(record.get("arm"))
        by_arm.setdefault(arm, dict(record))
    return by_arm


def compare_input_parity(
    records: Sequence[Mapping[str, Any]],
    *,
    session_date: str,
    expected_arms: Sequence[str] = PARITY_ARMS,
    contract_integrity: "ContractIntegrity | None" = None,
) -> ParityVerdict:
    """Fail-closed PIT input-parity verdict for ONE session's records.

    See the module docstring for the full declared data contract. ``records``
    is a plain iterable of decision-record mappings; ``contract_integrity`` is
    the umbrella's optional pre-computed contract gate result. Never raises on
    a data outcome — a malformed/absent input yields ``not_parity`` with an
    explanatory reason, never an exception."""
    v = ParityVerdict(session_date=session_date, verdict="not_parity")

    materialized = list(records)
    if not materialized:
        v.reasons.append("missing_session: no records supplied for this session")
        return v

    # Contract-integrity dimension (computed by the umbrella; folded in here).
    if contract_integrity is not None:
        contract_ok = bool(contract_integrity.ok)
        v.contract_evaluated = True
        v.dimensions.append(
            DimensionResult(
                "contract_integrity",
                contract_ok,
                "" if contract_ok else f"reason_codes={list(contract_integrity.reason_codes)}",
            )
        )
        if not contract_ok:
            v.reasons.extend(f"contract:{c}" for c in contract_integrity.reason_codes)
    else:
        v.contract_evaluated = False
        v.dimensions.append(
            DimensionResult(
                "contract_integrity",
                False,
                "not_evaluated: the contract/watermark gate is run by the "
                "umbrella integration harness, not the model-only comparator",
            )
        )

    by_arm = qualifying_records_by_arm(materialized)
    v.arm_job_ids = {arm: by_arm.get(arm, {}).get("job_id") for arm in expected_arms}

    missing = [arm for arm in expected_arms if arm not in by_arm]
    if missing:
        # Cannot compute cross-arm dimensions without both arms; verdict
        # stays "not_parity" (the dataclass default).
        v.reasons.append(f"missing_qualifying_arm: {missing}")
        return v

    a_arm, b_arm = expected_arms[0], expected_arms[1]
    a, b = by_arm[a_arm], by_arm[b_arm]

    for dim_name, record_key, reason in INPUT_PARITY_DIMENSIONS:
        va, vb = a.get(record_key), b.get(record_key)
        ok = va == vb
        v.dimensions.append(
            DimensionResult(dim_name, ok, "" if ok else f"{a_arm}={va!r} {b_arm}={vb!r}")
        )
        if not ok:
            v.reasons.append(reason)

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
    records_by_session: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    contract_by_session: "Mapping[str, ContractIntegrity] | None" = None,
    expected_arms: Sequence[str] = PARITY_ARMS,
) -> list[ParityVerdict]:
    """PIT input-parity verdicts for an EXPLICIT, pre-loaded session map.

    ``records_by_session`` maps ``decision_session -> [record mappings]`` — the
    umbrella loads these from the canonical store (per an explicit, forward-only
    session list; no DB scan, no as-of selection) and hands them in as plain
    data. ``contract_by_session`` optionally supplies each session's
    :class:`ContractIntegrity` from the umbrella's contract gate."""
    contract_by_session = contract_by_session or {}
    verdicts: list[ParityVerdict] = []
    for session in records_by_session:
        verdicts.append(
            compare_input_parity(
                records_by_session[session],
                session_date=session,
                expected_arms=expected_arms,
                contract_integrity=contract_by_session.get(session),
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


# ---------------------------------------------------------------------------
# Optional model-only CLI — reads plain-JSON record exports (never a store).
# ---------------------------------------------------------------------------

def _load_records_json(path: Path) -> "dict[str, list[dict[str, Any]]]":
    """Load ``{session -> [record, ...]}`` from a plain-JSON export."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("--records-json must be an object mapping session -> [records]")
    out: dict[str, list[dict[str, Any]]] = {}
    for session, recs in data.items():
        dt.date.fromisoformat(session)  # caller error on malformed date
        if not isinstance(recs, list):
            raise ValueError(f"session {session!r} must map to a list of record objects")
        out[session] = [r for r in recs if isinstance(r, dict)]
    return out


def _load_contract_json(path: "Path | None") -> "dict[str, ContractIntegrity]":
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, ContractIntegrity] = {}
    for session, res in (data or {}).items():
        out[session] = ContractIntegrity(
            ok=bool(res.get("ok")),
            reason_codes=list(res.get("reason_codes", [])),
        )
    return out


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--records-json", required=True, type=Path,
                    help="Plain-JSON export {session: [decision-record objects]} "
                         "(the umbrella loads these from the canonical store).")
    ap.add_argument("--contract-json", type=Path, default=None,
                    help="Optional plain-JSON {session: {ok, reason_codes}} from "
                         "the umbrella's validate_session_records run.")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = ap.parse_args(argv)

    if not args.records_json.exists():
        print(f"ERROR: records json not found: {args.records_json}", file=sys.stderr)
        return 1
    if args.contract_json is not None and not args.contract_json.exists():
        print(f"ERROR: contract json not found: {args.contract_json}", file=sys.stderr)
        return 1

    records_by_session = _load_records_json(args.records_json)
    contract_by_session = _load_contract_json(args.contract_json)
    if not records_by_session:
        print("ERROR: no sessions in --records-json", file=sys.stderr)
        return 1

    verdicts = build_parity_ledger(
        records_by_session, contract_by_session=contract_by_session
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
