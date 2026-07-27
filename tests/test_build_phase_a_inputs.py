"""Tests for the walk-forward-sim -> Phase A inputs converter.

The converter consumes the ``wf_sim_provenance.v1`` JSONL ledger (design
``renquant-pipeline doc/design/2026-07-27-wf-sim-provenance-contract.md``
#215 §2.5) as the ONLY source of fold/artifact identity. Covered here:

1. Ledger pair validation (step 1): a complete ``fold_resolved`` +
   ``score_committed`` pair is admissible; orphans (either kind alone),
   non-identical duplicates, ``persisted: false``, ``pit_violation: true``,
   ``is_real_content_digest: false``, artifact-echo mismatch and a null
   ``input_watermark`` are each rejected with a machine-readable reason.
   Idempotent (content-identical modulo the audit clock) duplicates are
   accepted.
2. Sim-DB read-back verification (step 2): the canonical
   ``score_payload_digest`` recomputed over the rows at the recorded
   ``score_observation_key`` must equal the committed digest, and ``n_rows``
   must match.
3. Cross-check demotion (step 3): ``select_pit_fold`` +
   ``resolve_artifact_digest`` run only as independent cross-checks; any
   disagreement with the ledger is a HARD :class:`CrossCheckMismatchError`
   (evidence quarantined, nothing written), never a fallback.
4. The fixed vendored canonical-payload digest matches STORED vectors
   computed once from ``renquant_pipeline.kernel.walk_forward.provenance``
   at the pinned producer revision (KEEP IN SYNC guard). The vectors ARE
   the producer/consumer compatibility contract — renquant-model never
   imports renquant_pipeline (architecture boundary).
5. BDay PIT semantics of the (now cross-check-only) fold replay, kept from
   the model#64 fix.
6. An end-to-end build over a tiny synthetic sim DB + ledger, ADMITTED by
   the canonical validator, with every identity/time field stamped verbatim
   from the ledger records.
7. Per-expert output isolation (folded in from model#66): a second expert
   built into the same ``output_dir`` must not clobber the first expert's
   admissibility ledger / calendar evidence.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from pandas.tseries.offsets import BDay

from experiments.ensemble_phase0.build_phase_a_inputs import (
    ALLOWED_SCORE_COLUMNS,
    PAYLOAD_DIGEST_IMPL,
    CrossCheckMismatchError,
    LabelContext,
    ProvenanceLedgerError,
    ProvenancePair,
    ScoreColumnNotAllowedError,
    WalkForwardFold,
    build_score_payload,
    canonical_score_payload,
    evaluate_provenance_dates,
    load_folds,
    load_provenance_ledger,
    resolve_artifact_digest,
    run_build,
    score_payload_digest,
    select_pit_fold,
    validate_score_column,
    verify_committed_observation,
)

CUTOFF = "2025-05-12"
LOOKAHEAD = 60
# Verified via pandas: 2025-05-12 + BDay(60) == 2025-08-04; +60 calendar days
# == 2025-07-11. A date between those two is BDay-ineligible but would be
# calendar-eligible -- the exact leakage the BDay contract prevents.
EFF_BDAY = "2025-08-04"
CAL_PLUS_60 = "2025-07-11"
DISCRIMINATING = "2025-07-20"  # after calendar+60, before BDay eff

SIM_RUN_ID = "wf-sim-20260726-0001"
ARTIFACT_URI = "artifacts/wf/2025-05-12/panel-ltr.json"
ARTIFACT_BYTES = b'{"model": "content"}'
ARTIFACT_DIGEST = "sha256:" + hashlib.sha256(ARTIFACT_BYTES).hexdigest()
SCORE_TS = "2025-09-15T16:00:00-04:00"
WATERMARK = "2025-09-15T15:59:00-04:00"


def _fold(cutoff: str = CUTOFF, lookahead: int = LOOKAHEAD) -> WalkForwardFold:
    return WalkForwardFold(
        cutoff_date=cutoff,
        lookahead_days=lookahead,
        artifact_uri=f"artifacts/wf/{cutoff}/panel-ltr.json",
        trained_date="2026-06-15",
    )


# ---------------------------------------------------------------------
# wf_sim_provenance.v1 fixtures
# ---------------------------------------------------------------------
def _fold_record(pred_date: str, **over) -> dict:
    rec = {
        "schema_version": "wf_sim_provenance.v1",
        "record_kind": "fold_resolved",
        "sim_run_id": SIM_RUN_ID,
        "prediction_date": pred_date,
        "seed": 7,
        "cutoff_date": CUTOFF,
        "trained_date": "2026-06-15",
        "effective_train_cutoff_date": EFF_BDAY,
        "lookahead_days": LOOKAHEAD,
        "artifact_uri": ARTIFACT_URI,
        "calibrator_uri": None,
        "manifest_path": "/x/wf_manifest.json",
        "manifest_digest": "sha256:" + "c" * 64,
        "artifact_digest": ARTIFACT_DIGEST,
        "is_real_content_digest": True,
        "family": "xgb",
        "fingerprint_schema": "v1",
        "calibrator_digest": None,
        "revision_pins": {"renquant-pipeline": "ac98b50"},
        "emitted_at_utc": "2026-07-27T00:00:00+00:00",
    }
    rec.update(over)
    return rec


def _committed_record(pred_date: str, *, payload_digest: str, n_rows: int,
                      run_id: str | None = None, **over) -> dict:
    ts = over.pop("score_timestamp", SCORE_TS.replace("2025-09-15", pred_date))
    wm = over.pop("input_watermark", WATERMARK.replace("2025-09-15", pred_date))
    rec = {
        "schema_version": "wf_sim_provenance.v1",
        "record_kind": "score_committed",
        "sim_run_id": SIM_RUN_ID,
        "prediction_date": pred_date,
        "score_observation_key": [run_id or f"wf-{pred_date}", pred_date, "sim"],
        "score_payload_digest": payload_digest,
        "n_rows": n_rows,
        "artifact_digest": ARTIFACT_DIGEST,
        "score_timestamp": ts,
        "input_watermark": wm,
        "pit_violation": False,
        "persisted": True,
        "emitted_at_utc": "2026-07-27T00:00:01+00:00",
    }
    rec.update(over)
    return rec


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
        for r in records
    ))
    return path


def _payload_rows(tickers: list[str]) -> list[dict]:
    return [
        {"ticker": t, "raw_panel": 0.1 * (i + 1) - 0.2, "mu": None,
         "rank_score": 0.4 + 0.1 * i, "sigma": 0.05}
        for i, t in enumerate(tickers)
    ]


def _make_sim_db(db_path: Path, dates: list[str], tickers: list[str]) -> dict[str, str]:
    """Create a synthetic sim DB; return {date: payload_digest} per bar."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE score_distribution (
               run_id TEXT, date TEXT, run_type TEXT, ticker TEXT,
               raw_panel REAL, rank_score REAL, mu REAL, sigma REAL,
               PRIMARY KEY (run_id, ticker))"""
    )
    conn.execute(
        """CREATE TABLE ticker_forward_returns (
               as_of_date DATE, ticker TEXT, fwd_60d REAL,
               PRIMARY KEY (as_of_date, ticker))"""
    )
    digests: dict[str, str] = {}
    for d in dates:
        rows = _payload_rows(tickers)
        for i, r in enumerate(rows):
            conn.execute(
                "INSERT INTO score_distribution VALUES (?,?,?,?,?,?,?,?)",
                (f"wf-{d}", d, "sim", r["ticker"], r["raw_panel"],
                 r["rank_score"], r["mu"], r["sigma"]),
            )
            conn.execute(
                "INSERT INTO ticker_forward_returns VALUES (?,?,?)",
                (d, r["ticker"], 0.01 * (i + 1)),
            )
        digests[d] = score_payload_digest(rows)
    conn.commit()
    conn.close()
    return digests


def _write_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "wf_manifest.json"
    manifest.write_text(json.dumps({
        "retrains": [
            {"cutoff_date": CUTOFF, "lookahead_days": LOOKAHEAD,
             "artifact_uri": ARTIFACT_URI, "trained_date": "2026-06-15"},
        ]
    }))
    return manifest


def _write_artifact(tmp_path: Path) -> Path:
    artifact = tmp_path / Path(ARTIFACT_URI)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(ARTIFACT_BYTES)
    return artifact


# ---------------------------------------------------------------------
# 1. BDay admissibility boundary (cross-check replay semantics, model#64)
# ---------------------------------------------------------------------
def test_effective_cutoff_uses_bday_not_calendar_timedelta():
    fold = _fold()
    assert fold.effective_train_cutoff_date() == EFF_BDAY
    # Sanity: BDay(60) is materially later than a naive 60-calendar-day offset.
    calendar_eff = (date.fromisoformat(CUTOFF) + timedelta(days=LOOKAHEAD)).isoformat()
    assert calendar_eff == CAL_PLUS_60
    assert fold.effective_train_cutoff_date() > calendar_eff


def test_bday_boundary_is_strict():
    fold = _fold()
    # A date exactly ON the effective cutoff is NOT eligible (strict <).
    assert select_pit_fold([fold], EFF_BDAY) is None
    # One business day after the effective cutoff IS eligible.
    one_bday_after = str((pd.Timestamp(EFF_BDAY) + BDay(1)).date())
    assert select_pit_fold([fold], one_bday_after) is fold


def test_bday_gate_excludes_a_calendar_eligible_date():
    """The discriminating case: a date a naive calendar timedelta(60) would
    admit (leak) is correctly EXCLUDED by the business-day gate."""
    fold = _fold()
    # Under naive calendar: CUTOFF + 60d = 2025-07-11 < 2025-07-20 -> would admit.
    assert date.fromisoformat(CAL_PLUS_60) < date.fromisoformat(DISCRIMINATING)
    # Under BDay: effective 2025-08-04 > 2025-07-20 -> excluded (no leak).
    assert select_pit_fold([fold], DISCRIMINATING) is None


def test_select_pit_fold_picks_latest_eligible():
    older = _fold(cutoff="2025-05-12")   # eff 2025-08-04
    newer = _fold(cutoff="2025-06-02")   # eff strictly later
    folds = sorted([newer, older], key=lambda f: f.cutoff_date)
    # A date after BOTH effective cutoffs must select the LATER cutoff fold.
    pred = "2025-09-15"
    assert select_pit_fold(folds, pred) is newer


# ---------------------------------------------------------------------
# score-column SQL guard + fold-manifest loading (unchanged surfaces)
# ---------------------------------------------------------------------
def test_score_column_allowlist_guard():
    for col in ALLOWED_SCORE_COLUMNS:
        assert validate_score_column(col) == col
    with pytest.raises(ScoreColumnNotAllowedError):
        validate_score_column("raw_panel; DROP TABLE score_distribution")


def test_artifact_digest_real_vs_fallback(tmp_path: Path):
    art = tmp_path / "artifacts" / "wf" / CUTOFF / "panel-ltr.json"
    art.parent.mkdir(parents=True)
    art.write_bytes(ARTIFACT_BYTES)
    fold = _fold()
    fp, locator, is_real = resolve_artifact_digest(fold, tmp_path)
    assert is_real is True
    assert fp == ARTIFACT_DIGEST
    # Unresolvable base dir -> deterministic provenance-bound fallback,
    # flagged non-real (the caller treats it as a FAILED cross-check).
    fp2, locator2, is_real2 = resolve_artifact_digest(fold, tmp_path / "nope")
    assert is_real2 is False
    assert locator2.startswith("provenance_bound:")
    assert fp2.startswith("sha256:")


def test_load_folds_requires_lookahead(tmp_path: Path):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"retrains": [{"cutoff_date": "2025-01-01"}]}))
    with pytest.raises(ValueError, match="lookahead_days"):
        load_folds(manifest)


# ---------------------------------------------------------------------
# 2. Canonical score-payload digest: fixed vendored copy vs STORED vectors
# ---------------------------------------------------------------------
# STORED vectors, computed ONCE from
# renquant_pipeline.kernel.walk_forward.provenance at origin/main
# ac98b5027c37052291e1091c368bbbddc8ced766 and frozen here. They ARE the
# producer/consumer compatibility contract: renquant-model never imports
# renquant_pipeline (architecture boundary — codex round-2 on model#65),
# so byte-compatibility of the vendored digest is proven against these
# fixed vectors, never by an import. If these fail, the vendored copy
# drifted from the pinned producer revision -- re-sync it (KEEP IN SYNC
# note in the module).
VECTOR_1 = [
    {"ticker": "BBB", "raw_panel": -0.25, "mu": None, "rank_score": 0.5, "sigma": 0.05},
    {"ticker": "AAA", "raw_panel": 1, "mu": 0.1, "rank_score": None, "sigma": 2.5e-3},
]
VECTOR_1_DIGEST = "sha256:f592eb090648767f391e833c75af076e70f5c42fe534ed362cc786b47be1201d"
VECTOR_1_CANONICAL = b'["AAA","1.0","0.1",null,"0.0025"]\n["BBB","-0.25",null,"0.5","0.05"]'
VECTOR_EMPTY_DIGEST = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
VECTOR_3 = [
    {"ticker": "ZZZ", "raw_panel": -0.0, "mu": 1e-17,
     "rank_score": 0.30000000000000004, "sigma": None},
]
VECTOR_3_DIGEST = "sha256:9943fbd2d4870ef5ff7d0e47105394f54eb8951c1e7726909d0f38332e3eecaf"


def test_vendored_digest_matches_stored_producer_vectors():
    # Sorting by ticker + int-through-float normalization + None -> null.
    assert canonical_score_payload(VECTOR_1) == VECTOR_1_CANONICAL
    assert score_payload_digest(VECTOR_1) == VECTOR_1_DIGEST
    # Empty payload = sha256 of the empty byte string.
    assert score_payload_digest([]) == VECTOR_EMPTY_DIGEST
    # repr()-fidelity floats (-0.0, 1e-17, 0.30000000000000004).
    assert score_payload_digest(VECTOR_3) == VECTOR_3_DIGEST
    # The manifest stamps the vendored implementation's pinned identity.
    assert PAYLOAD_DIGEST_IMPL.startswith("vendored:")
    assert "@ac98b502" in PAYLOAD_DIGEST_IMPL


# ---------------------------------------------------------------------
# 3. Ledger pair validation (design #215 §2.5 step 1)
# ---------------------------------------------------------------------
D = "2025-09-15"
ROWS_D = _payload_rows(["AAA", "BBB", "CCC"])


def _evaluate(tmp_path: Path, records: list[dict]):
    ledger = load_provenance_ledger(_write_jsonl(tmp_path / "l.jsonl", records))
    return evaluate_provenance_dates(ledger)


def test_valid_pair_is_admissible(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D), n_rows=3),
    ])
    assert D in pairs and not rejections
    assert pairs[D].fold["cutoff_date"] == CUTOFF


def test_orphaned_fold_resolved_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [_fold_record(D)])
    assert not pairs
    assert rejections[D]["reason_code"] == "orphaned_fold_resolved"


def test_orphaned_score_committed_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _committed_record(D, payload_digest="sha256:" + "a" * 64, n_rows=3),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "orphaned_score_committed"


def test_duplicate_committed_non_identical_rejected(tmp_path: Path):
    digest = score_payload_digest(ROWS_D)
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _committed_record(D, payload_digest=digest, n_rows=3),
        _committed_record(D, payload_digest=digest, n_rows=4),  # re-score
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "duplicate_score_committed_conflict"


def test_duplicate_committed_identical_accepted(tmp_path: Path):
    """Byte-identical re-emits, and re-emits differing ONLY in the audit
    clock (``emitted_at_utc``), are idempotent duplicates — accepted."""
    digest = score_payload_digest(ROWS_D)
    committed = _committed_record(D, payload_digest=digest, n_rows=3)
    audit_only = dict(committed, emitted_at_utc="2026-07-28T09:00:00+00:00")
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        committed,
        committed,      # literally byte-identical line
        audit_only,     # differs only in the audit-write clock
    ])
    assert D in pairs and not rejections


def test_duplicate_fold_resolved_non_identical_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _fold_record(D, cutoff_date="2025-06-02"),  # real double-resolution
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D), n_rows=3),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "duplicate_fold_resolved_conflict"


def test_persisted_false_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D),
                          n_rows=3, persisted=False),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "persisted_false"


def test_pit_violation_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D),
                          n_rows=3, pit_violation=True),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "pit_violation"


def test_non_real_content_digest_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D, is_real_content_digest=False),
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D), n_rows=3),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "artifact_digest_not_real_content"


def test_artifact_echo_mismatch_rejected(tmp_path: Path):
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D),
                          n_rows=3, artifact_digest="sha256:" + "e" * 64),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "artifact_digest_echo_mismatch"


def test_null_input_watermark_rejected(tmp_path: Path):
    """A null watermark means the emit-side PIT check could not run;
    extraction owns that judgement and fails closed (design #215 §2.2)."""
    pairs, rejections = _evaluate(tmp_path, [
        _fold_record(D),
        _committed_record(D, payload_digest=score_payload_digest(ROWS_D),
                          n_rows=3, input_watermark=None),
    ])
    assert not pairs
    assert rejections[D]["reason_code"] == "input_watermark_missing"


def test_mixed_sim_run_ids_is_hard_error(tmp_path: Path):
    with pytest.raises(ProvenanceLedgerError, match="mixed sim_run_ids"):
        load_provenance_ledger(_write_jsonl(tmp_path / "l.jsonl", [
            _fold_record(D),
            _fold_record("2025-09-16", sim_run_id="another-run"),
        ]))


def test_wrong_schema_version_is_hard_error(tmp_path: Path):
    with pytest.raises(ProvenanceLedgerError, match="schema_version"):
        load_provenance_ledger(_write_jsonl(tmp_path / "l.jsonl", [
            _fold_record(D, schema_version="wf_sim_provenance.v0"),
        ]))


# ---------------------------------------------------------------------
# 4. Sim-DB read-back verification (design #215 §2.5 step 2)
# ---------------------------------------------------------------------
def _db_and_pair(tmp_path: Path, *, payload_digest: str | None = None,
                 n_rows: int = 3) -> tuple[Path, ProvenancePair]:
    db = tmp_path / "sim_runs.db"
    digests = _make_sim_db(db, [D], ["AAA", "BBB", "CCC"])
    pair = ProvenancePair(
        fold=_fold_record(D),
        committed=_committed_record(
            D, payload_digest=payload_digest or digests[D], n_rows=n_rows,
        ),
    )
    return db, pair


def test_verified_observation_passes(tmp_path: Path):
    db, pair = _db_and_pair(tmp_path)
    rows, rejection = verify_committed_observation(db, pair)
    assert rejection is None
    assert len(rows) == 3
    assert score_payload_digest(rows) == pair.committed["score_payload_digest"]


def test_digest_mismatch_vs_db_rejected(tmp_path: Path):
    db, pair = _db_and_pair(tmp_path, payload_digest="sha256:" + "f" * 64)
    rows, rejection = verify_committed_observation(db, pair)
    assert rows is None
    assert rejection["reason_code"] == "score_payload_digest_mismatch"


def test_n_rows_mismatch_rejected(tmp_path: Path):
    db, pair = _db_and_pair(tmp_path, n_rows=4)
    rows, rejection = verify_committed_observation(db, pair)
    assert rows is None
    assert rejection["reason_code"] == "n_rows_mismatch"


# ---------------------------------------------------------------------
# 5. Payload stamping: LEDGER facts verbatim, nothing recomputed
# ---------------------------------------------------------------------
def test_payload_stamped_from_ledger_facts_verbatim():
    pair = ProvenancePair(
        fold=_fold_record(D),
        committed=_committed_record(D, payload_digest="sha256:" + "a" * 64, n_rows=3),
    )
    labels = LabelContext(
        has_realized_labels_by_date={D: True},
        label_artifact_ref_by_date={D: "sha256:" + "b" * 64 + "@returns.csv"},
        label_observation_end_by_date={D: "2025-11-14"},
    )
    payload = build_score_payload(
        D, {"AAA": 0.1, "BBB": -0.2},
        expert_name="xgb",
        pair=pair,
        sim_run_id=SIM_RUN_ID,
        labels=labels,
        score_column="raw_panel",
        source_db_digest="sha256:" + "d" * 64,
        source_db_path="/x/sim.db",
        manifest_path="/x/manifest.json",
        provenance_ledger_path="/x/wf_provenance/run.jsonl",
        provenance_ledger_digest="sha256:" + "9" * 64,
    )
    # Identity/time fields copied VERBATIM from the two records.
    assert payload["training_cutoff"] == pair.fold["cutoff_date"] == CUTOFF
    assert payload["model_content_sha256"] == ARTIFACT_DIGEST
    assert payload["score_timestamp"] == pair.committed["score_timestamp"]
    assert payload["as_of_date"] == pair.committed["input_watermark"]
    assert payload["data_watermark"] == pair.committed["input_watermark"]
    # Containment + provenance audit trail.
    assert payload["metadata"]["classification"] == "EXPLORATORY_ONLY"
    prov = payload["metadata"]["provenance"]
    assert prov["sim_run_id"] == SIM_RUN_ID
    assert prov["score_observation_key"] == list(
        pair.committed["score_observation_key"]
    )
    assert prov["score_payload_digest"] == pair.committed["score_payload_digest"]
    assert payload["metadata"]["walkforward_fold"]["effective_train_cutoff_date"] == EFF_BDAY


# ---------------------------------------------------------------------
# 6. Cross-check demotion: disagreement = HARD error, never a fallback
# ---------------------------------------------------------------------
def _e2e_inputs(tmp_path: Path, dates: list[str]) -> dict:
    tickers = ["AAA", "BBB", "CCC"]
    sim_db = tmp_path / "sim_runs.db"
    digests = _make_sim_db(sim_db, dates, tickers)
    records = []
    for d in dates:
        records.append(_fold_record(d))
        records.append(_committed_record(d, payload_digest=digests[d], n_rows=3))
    return {
        "sim_db": sim_db,
        "manifest": _write_manifest(tmp_path),
        "ledger": _write_jsonl(tmp_path / f"{SIM_RUN_ID}.jsonl", records),
        "records": records,
        "digests": digests,
    }


def test_cross_check_disagreement_is_hard_error_and_quarantines(tmp_path: Path):
    """Ledger records a fold the manifest replay disagrees with -> the date
    is quarantined via CrossCheckMismatchError and NOTHING is written. The
    replay is never used as a fallback identity."""
    dates = ["2025-09-15", "2025-09-16"]
    inputs = _e2e_inputs(tmp_path, dates)
    _write_artifact(tmp_path)
    # Corrupt the ledger identity: claim a cutoff the manifest replay
    # cannot re-derive (the manifest's only fold has cutoff 2025-05-12).
    records = [
        (dict(r, cutoff_date="2025-06-02")
         if r["record_kind"] == "fold_resolved" else r)
        for r in inputs["records"]
    ]
    _write_jsonl(inputs["ledger"], records)

    out = tmp_path / "out"
    with pytest.raises(CrossCheckMismatchError) as exc_info:
        run_build(
            sim_db=inputs["sim_db"],
            provenance_ledger=inputs["ledger"],
            manifest_file=inputs["manifest"],
            output_dir=out,
            expert_name="xgb",
            score_column="raw_panel",
            start_date="2025-09-01",
            end_date="2025-09-30",
            artifact_base_dir=tmp_path,
        )
    assert set(exc_info.value.quarantined) == set(dates)
    # HARD abort: no partial output escaped.
    assert not (out / "xgb").exists()
    assert not (out / "returns.csv").exists()


def test_unresolvable_artifact_fails_the_cross_check_hard(tmp_path: Path):
    """If the independent re-hash cannot run (artifact missing on disk),
    that is a FAILED cross-check -> hard quarantine, not a fallback to
    trusting the ledger digest unverified."""
    dates = ["2025-09-15"]
    inputs = _e2e_inputs(tmp_path, dates)
    # No artifact file written under tmp_path.
    out = tmp_path / "out"
    with pytest.raises(CrossCheckMismatchError, match="re-hash"):
        run_build(
            sim_db=inputs["sim_db"],
            provenance_ledger=inputs["ledger"],
            manifest_file=inputs["manifest"],
            output_dir=out,
            expert_name="xgb",
            score_column="raw_panel",
            start_date="2025-09-01",
            end_date="2025-09-30",
            artifact_base_dir=tmp_path,
        )
    assert not (out / "xgb").exists()


# ---------------------------------------------------------------------
# 7. End-to-end: synthetic sim DB + ledger -> canonical validator ADMITS
# ---------------------------------------------------------------------
def test_end_to_end_ledger_build_is_admitted_by_canonical_validator(tmp_path: Path):
    dates = ["2025-09-15", "2025-09-16"]
    inputs = _e2e_inputs(tmp_path, dates)
    _write_artifact(tmp_path)
    # One extra sim-DB bar WITHOUT any ledger record: inadmissible by
    # construction (the pre-provenance-history case), reported honestly.
    conn = sqlite3.connect(str(inputs["sim_db"]))
    conn.execute(
        "INSERT INTO score_distribution VALUES (?,?,?,?,?,?,?,?)",
        ("wf-2025-09-17", "2025-09-17", "sim", "AAA", 0.1, 0.5, None, 0.05),
    )
    conn.commit()
    conn.close()

    out = tmp_path / "out"
    result = run_build(
        sim_db=inputs["sim_db"],
        provenance_ledger=inputs["ledger"],
        manifest_file=inputs["manifest"],
        output_dir=out,
        expert_name="xgb",
        score_column="raw_panel",
        start_date="2025-09-01",
        end_date="2025-09-30",
        artifact_base_dir=tmp_path,
        build_admissibility_ledger=True,
    )

    # Both ledger-backed dates written + ADMITTED by the canonical validator.
    assert result.n_dates_written == 2
    assert result.ledger_admitted == 2
    assert result.ledger_rejected == 0
    assert result.sim_run_id == SIM_RUN_ID
    assert result.payload_digest_impl == PAYLOAD_DIGEST_IMPL
    # The ledgerless DB date was rejected with a machine-readable reason,
    # and no score file was written for it.
    assert result.rejected_dates["2025-09-17"]["reason_code"] == "no_provenance_record"
    assert result.n_db_dates_without_provenance == 1
    assert not (out / "xgb" / "2025-09-17.json").exists()

    # Every stamped identity/time field is the LEDGER fact, verbatim.
    sf = json.loads((out / "xgb" / "2025-09-15.json").read_text())
    assert sf["training_cutoff"] == CUTOFF
    assert sf["model_content_sha256"] == ARTIFACT_DIGEST
    assert sf["score_timestamp"] == "2025-09-15T16:00:00-04:00"
    assert sf["as_of_date"] == "2025-09-15T15:59:00-04:00"
    assert sf["data_watermark"] == sf["as_of_date"]
    assert sf["has_realized_labels"] is True
    assert sf["metadata"]["classification"] == "EXPLORATORY_ONLY"
    assert sf["metadata"]["provenance"]["score_payload_digest"] == inputs["digests"]["2025-09-15"]
    assert sf["metadata"]["provenance"]["ledger_digest"].startswith("sha256:")

    # Scores come from the digest-verified observation rows.
    assert sf["scores"] == {
        "AAA": pytest.approx(-0.1), "BBB": pytest.approx(0.0),
        "CCC": pytest.approx(0.1),
    }

    # Shared returns CSV in the runner's expected schema.
    returns = (out / "returns.csv").read_text().splitlines()
    assert returns[0] == "date,ticker,fwd_return"

    # Per-expert evidence isolation (model#66): the admissibility ledger
    # lives under the expert dir, and the manifest records that path.
    assert result.ledger_path == str(out / "xgb" / "admissibility_ledger.json")


def test_second_expert_build_does_not_clobber_first_experts_root_artifacts(
    tmp_path: Path,
):
    """Multi-expert output isolation regression (folded in from model#66).

    Building a SECOND expert into the SAME ``output_dir`` must not destroy
    the first expert's per-expert evidence. The admissibility ledger and its
    calendar evidence are expert-specific; written to the shared
    ``output_dir`` root (``output_dir/admissibility_ledger.json`` /
    ``output_dir/calendar_evidence.json``) a patchtst build would clobber
    the xgb build's evidence. They must live under ``output_dir/<expert>/``.
    The forward-returns CSV is expert-independent label data and stays
    shared at the root by design. Adapted to the wf_sim_provenance.v1
    evidence schema: both experts consume the same generation-time ledger +
    verified observations here (one synthetic sim run, two expert labels).
    """
    dates = ["2025-09-15", "2025-09-16"]
    inputs = _e2e_inputs(tmp_path, dates)
    _write_artifact(tmp_path)
    out = tmp_path / "out"

    def _build(expert: str):
        return run_build(
            sim_db=inputs["sim_db"],
            provenance_ledger=inputs["ledger"],
            manifest_file=inputs["manifest"],
            output_dir=out,
            expert_name=expert,
            score_column="raw_panel",
            start_date="2025-09-01",
            end_date="2025-09-30",
            artifact_base_dir=tmp_path,
            build_admissibility_ledger=True,
        )

    # First expert.
    result_xgb = _build("xgb")
    assert result_xgb.ledger_admitted == 2
    xgb_ledger = out / "xgb" / "admissibility_ledger.json"
    xgb_cal = out / "xgb" / "calendar_evidence.json"
    assert xgb_ledger.exists()
    assert xgb_cal.exists()
    # Manifest records the isolated per-expert ledger path.
    assert result_xgb.ledger_path == str(xgb_ledger)
    # Snapshot the first expert's evidence bytes to prove the second run
    # leaves them untouched.
    xgb_ledger_bytes = xgb_ledger.read_bytes()
    xgb_cal_bytes = xgb_cal.read_bytes()

    # Second expert into the SAME output_dir.
    result_pt = _build("patchtst")
    assert result_pt.ledger_admitted == 2

    # 1) The first expert's per-expert evidence survived byte-for-byte.
    assert xgb_ledger.read_bytes() == xgb_ledger_bytes, "xgb ledger was clobbered"
    assert xgb_cal.read_bytes() == xgb_cal_bytes, "xgb calendar evidence was clobbered"

    # 2) The second expert wrote its OWN isolated evidence.
    assert (out / "patchtst" / "admissibility_ledger.json").exists()
    assert (out / "patchtst" / "calendar_evidence.json").exists()

    # 3) No expert-specific evidence leaked to the shared root (the pre-fix
    #    clobber target). This assertion fails on the pre-fix code.
    assert not (out / "admissibility_ledger.json").exists()
    assert not (out / "calendar_evidence.json").exists()

    # 4) Per-expert score dirs and build manifests coexist.
    assert (out / "xgb" / "2025-09-15.json").exists()
    assert (out / "patchtst" / "2025-09-15.json").exists()
    assert (out / "build_manifest_xgb.json").exists()
    assert (out / "build_manifest_patchtst.json").exists()

    # 5) The forward-returns CSV is the single shared root artifact.
    assert (out / "returns.csv").exists()


def test_no_admissible_dates_fails_closed(tmp_path: Path):
    """A ledger whose only pair is inadmissible (persisted:false) plus a
    ledgerless DB history must fail closed — pre-provenance sim history is
    permanently inadmissible through this converter, by design."""
    dates = ["2025-09-15"]
    tickers = ["AAA", "BBB", "CCC"]
    sim_db = tmp_path / "sim_runs.db"
    digests = _make_sim_db(sim_db, dates, tickers)
    ledger = _write_jsonl(tmp_path / f"{SIM_RUN_ID}.jsonl", [
        _fold_record("2025-09-15"),
        _committed_record("2025-09-15", payload_digest=digests["2025-09-15"],
                          n_rows=3, persisted=False),
    ])
    _write_artifact(tmp_path)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="no admissible-vintage dates"):
        run_build(
            sim_db=sim_db,
            provenance_ledger=ledger,
            manifest_file=_write_manifest(tmp_path),
            output_dir=out,
            expert_name="xgb",
            score_column="raw_panel",
            start_date="2025-09-01",
            end_date="2025-09-30",
            artifact_base_dir=tmp_path,
        )
    assert not (out / "xgb").exists()
