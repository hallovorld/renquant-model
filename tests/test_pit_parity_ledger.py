"""Tests for the MODEL-ONLY PIT input-parity comparator (v4 §2/§5 step 3).

The prod-vs-shadow ``runs.alpaca.db`` bundle scan, the private
``select_asof_runs`` import, AND the model → orchestrator store/admission
imports are ALL retired. Parity is now computed by a portable, data-contract
function over PLAIN decision-record mappings (as the umbrella integration
harness loads them from the canonical G4 evidence store). These tests build
those mappings directly — no orchestrator import, no store, tmp fixtures only.
"""
from __future__ import annotations

from pathlib import Path

from renquant_pipeline.decision_schedule import ARM_CHAMPION, ARM_L1

from experiments.ensemble_phase0 import pit_parity_ledger as pit
from experiments.ensemble_phase0.pit_parity_ledger import (
    ContractIntegrity,
    build_parity_ledger,
    compare_input_parity,
    write_parity_ledger,
)

CAL_ID = "XNYS/v1"
PS_ID = "alpaca_sip/v1"
SESSION = "2026-08-05"
NXT = "2026-08-06"
WATERMARK = f"{SESSION}T19:00:00+00:00"

_MODULE_SRC = Path(pit.__file__).read_text(encoding="utf-8")


def _manifest(digest: str = "sha256:" + "d" * 64, mev: str = WATERMARK) -> dict:
    return {"universe": {"digest": digest, "max_event_time": mev}}


def _record(
    arm: str,
    *,
    manifest: "dict | None" = None,
    calendar_id: str = CAL_ID,
    price_source_id: str = PS_ID,
    watermark: str = WATERMARK,
    scheduled_for: str = NXT,
    schema_version: int = 1,
    artifact: str = "a",
) -> dict:
    """A plain qualifying decision-record mapping (the comparator's data
    contract) — exactly the fields the canonical job persists, hand-built."""
    return {
        "schema_version": schema_version,
        "execution_mode": "shadow",
        "arm": arm,
        "decision_session": SESSION,
        "declared_input_watermark": watermark,
        "input_manifest": manifest if manifest is not None else _manifest(),
        "artifact_digests": {arm: "sha256:" + artifact * 64},
        "config_digest": "sha256:" + "c" * 64,
        "calendar_id": calendar_id,
        "price_source_id": price_source_id,
        "scores": {"AAPL": 0.1},
        "orders": [],
        "orders_scheduled_for": scheduled_for,
        "run_bundle_timestamp": f"{SESSION}T21:00:00+00:00",
        "job_id": f"job-{arm}",
    }


def _pair(manifest: "dict | None" = None) -> list:
    """The two frozen arms sharing ONE input manifest (parity by design),
    differing only in the scorer artifact (informational)."""
    m = manifest if manifest is not None else _manifest()
    return [_record(ARM_L1, manifest=m, artifact="a"),
            _record(ARM_CHAMPION, manifest=m, artifact="b")]


def _ok() -> ContractIntegrity:
    return ContractIntegrity(ok=True, reason_codes=[])


class TestRetirement:
    def test_no_private_asof_db_scan_or_orchestrator(self):
        # Retired symbols/imports are not defined on the module.
        for name in ("select_asof_runs", "RunSelection", "AsOfExclusion",
                     "sqlite3", "compare_session_parity", "G4EvidenceStore",
                     "admit_g4_session", "recompute_watermark_from_store",
                     "resolve_session_window"):
            assert not hasattr(pit, name), name

    def test_module_source_never_imports_orchestrator(self):
        # Strong guard against reintroducing the reverse cross-repo edge:
        # the model-only comparator must never IMPORT renquant_orchestrator.
        # (Docstring prose may name it when explaining the boundary; an
        # actual import statement is what we forbid.)
        assert "from renquant_orchestrator" not in _MODULE_SRC
        assert "import renquant_orchestrator" not in _MODULE_SRC
        assert "sqlite3" not in _MODULE_SRC  # the retired runs.alpaca.db path


class TestParityVerdicts:
    def test_canonical_pair_is_parity(self):
        v = compare_input_parity(_pair(), session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "parity"
        assert not v.reasons
        assert v.contract_evaluated is True

    def test_scorer_artifact_difference_stays_parity(self):
        # l1 and champion carry DIFFERENT artifact digests by design; the
        # shared input manifest still makes them parity.
        v = compare_input_parity(_pair(), session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "parity"
        assert v.informational["artifact_digests_equal"] is False

    def test_contract_not_evaluated_still_reports_input_parity(self):
        # A model-only run (no contract result supplied) computes INPUT parity
        # only and is honest that the contract/watermark gate is the umbrella's.
        v = compare_input_parity(_pair(), session_date=SESSION)
        assert v.verdict == "parity"
        assert v.contract_evaluated is False
        dim = next(d for d in v.dimensions if d.dimension == "contract_integrity")
        assert dim.match is False and "not_evaluated" in dim.detail

    def test_contract_failure_is_not_parity(self):
        v = compare_input_parity(
            _pair(), session_date=SESSION,
            contract_integrity=ContractIntegrity(ok=False, reason_codes=["watermark_after_close"]),
        )
        assert v.verdict == "not_parity"
        assert "contract:watermark_after_close" in v.reasons

    def test_input_manifest_divergence_is_not_parity(self):
        records = [
            _record(ARM_L1, manifest=_manifest(digest="sha256:" + "1" * 64), artifact="a"),
            _record(ARM_CHAMPION, manifest=_manifest(digest="sha256:" + "2" * 64), artifact="b"),
        ]
        v = compare_input_parity(records, session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert "input_manifest_divergence" in v.reasons

    def test_declared_watermark_mismatch_is_not_parity(self):
        records = [
            _record(ARM_L1, watermark=f"{SESSION}T19:00:00+00:00"),
            _record(ARM_CHAMPION, watermark=f"{SESSION}T19:05:00+00:00"),
        ]
        v = compare_input_parity(records, session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert "declared_watermark_mismatch" in v.reasons

    def test_frozen_id_mismatch_is_not_parity(self):
        records = [_record(ARM_L1, calendar_id=CAL_ID),
                   _record(ARM_CHAMPION, calendar_id="OTHER/v1")]
        v = compare_input_parity(records, session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert "calendar_id_mismatch" in v.reasons

    def test_schema_and_schedule_mismatch_is_not_parity(self):
        records = [_record(ARM_L1, schema_version=1, scheduled_for=NXT),
                   _record(ARM_CHAMPION, schema_version=2, scheduled_for="2026-08-07")]
        v = compare_input_parity(records, session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert "schema_version_mismatch" in v.reasons
        assert "schedule_target_mismatch" in v.reasons

    def test_missing_arm_is_not_parity(self):
        v = compare_input_parity([_record(ARM_L1)], session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert any("missing_qualifying_arm" in r for r in v.reasons)

    def test_missing_session_is_not_parity(self):
        v = compare_input_parity([], session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert any("missing_session" in r for r in v.reasons)

    def test_failure_and_unreadable_records_are_skipped(self):
        # A failure/unreadable record for an arm does not qualify -> missing arm.
        records = [
            _record(ARM_L1),
            {"arm": ARM_CHAMPION, "failure": {"kind": "arm_failed"}},
            {"__unreadable__": "corrupt"},
        ]
        v = compare_input_parity(records, session_date=SESSION, contract_integrity=_ok())
        assert v.verdict == "not_parity"
        assert any("missing_qualifying_arm" in r for r in v.reasons)
        assert v.arm_job_ids[ARM_L1] == f"job-{ARM_L1}"


class TestLedger:
    def test_build_and_write_ledger(self, tmp_path):
        records_by_session = {SESSION: _pair()}
        contract_by_session = {SESSION: _ok()}
        verdicts = build_parity_ledger(
            records_by_session, contract_by_session=contract_by_session)
        assert len(verdicts) == 1 and verdicts[0].verdict == "parity"

        out = tmp_path / "out"
        path = write_parity_ledger(verdicts, out)
        assert path.exists()
        lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1

    def test_ledger_without_contract_map(self, tmp_path):
        verdicts = build_parity_ledger({SESSION: _pair()})
        assert verdicts[0].verdict == "parity"
        assert verdicts[0].contract_evaluated is False
