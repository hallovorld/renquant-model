"""Tests for the Phase A score backfill script.

Covers the Codex review (2026-07-14, model#54) fixes:

1. ``--score-column`` SQL-injection guard (fixed allowlist, validated
   before any query is built).
2/3. The as-of contract (:func:`select_asof_runs`) and the negative test
   proving a later rerun with changed scores, committed after the target
   date's own session-close cutoff, is never selected/admitted.
4. Candidate evidence is written with full point-in-time provenance and
   ``admitted`` is decided ONLY by the canonical validator
   (``admissibility_ledger.build_ledger``), never manufactured here.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from experiments.ensemble_phase0.admissibility_ledger import (
    US_EQUITY_CLOSE,
    build_exchange_session_calendar,
)
from experiments.ensemble_phase0.backfill_scores import (
    ALLOWED_SCORE_COLUMNS,
    BackfillManifest,
    ProvenanceContext,
    RunSelection,
    ScoreColumnNotAllowedError,
    build_score_payload,
    extract_daily_scores,
    extract_forward_returns,
    main,
    run_backfill,
    select_asof_runs,
    validate_score_column,
    write_forward_returns_csv,
)

# NYSE closes 21:00:00 UTC on all of these (regular sessions, no holiday /
# early close) -- verified directly against pandas_market_calendars.
CAL_START = "2023-12-20"
CAL_END = "2024-02-10"


def _calendar():
    return build_exchange_session_calendar(CAL_START, CAL_END)


def _create_test_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE pipeline_runs (
            run_id TEXT PRIMARY KEY,
            run_date DATE NOT NULL,
            run_type TEXT NOT NULL,
            commit_sha TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE candidate_scores (
            run_id TEXT, ticker TEXT, role TEXT,
            raw_score REAL, mu REAL, panel_score REAL,
            rank_score REAL, rs_score REAL, sigma REAL,
            selected INTEGER, blocked_by TEXT,
            active_scorer TEXT, model_type TEXT, panel_ltr_artifact TEXT,
            PRIMARY KEY (run_id, ticker, role)
        )
    """)
    conn.execute("""
        CREATE TABLE ticker_forward_returns (
            as_of_date DATE NOT NULL, ticker TEXT NOT NULL,
            fwd_60d REAL,
            PRIMARY KEY (as_of_date, ticker)
        )
    """)
    conn.executemany(
        "INSERT INTO pipeline_runs (run_id, run_date, run_type, commit_sha, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("run-2024-01-02", "2024-01-02", "live", "abc111", "2024-01-02 20:30:00"),
            ("run-2024-01-03", "2024-01-03", "live", "abc111", "2024-01-03 20:30:00"),
            ("run-2024-01-04", "2024-01-04", "live", "abc222", "2024-01-04 20:00:00"),
            # A later RERUN of 2024-01-04 with CHANGED scores, committed
            # weeks after that session's own close -- must NOT be selected
            # (this is the exact look-ahead shape Codex flagged).
            ("run-2024-01-04-rerun", "2024-01-04", "live", "abc333", "2024-02-01 09:00:00"),
            # 2024-01-05 has ONLY a late (post-cutoff) commit -- there is no
            # eligible run for this date at all.
            ("run-2024-01-05-late-only", "2024-01-05", "live", "abc444", "2024-02-01 09:00:00"),
        ],
    )
    conn.executemany(
        "INSERT INTO candidate_scores "
        "(run_id, ticker, role, mu, raw_score, active_scorer, model_type, panel_ltr_artifact) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("run-2024-01-02", "AAPL", "candidate", 0.05, 1.0, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-02.json"),
            ("run-2024-01-02", "MSFT", "candidate", 0.03, 0.8, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-02.json"),
            ("run-2024-01-02", "GOOG", "candidate", -0.01, -0.5, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-02.json"),
            ("run-2024-01-03", "AAPL", "candidate", 0.04, 0.9, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-03.json"),
            ("run-2024-01-03", "MSFT", "candidate", 0.02, 0.7, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-03.json"),
            ("run-2024-01-04", "AAPL", "candidate", 0.06, 1.1, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-04.json"),
            ("run-2024-01-04", "MSFT", "candidate", 0.01, 0.6, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-04.json"),
            ("run-2024-01-04", "GOOG", "candidate", 0.04, 0.9, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-04.json"),
            # Rerun's CHANGED score for the same (date, ticker) -- must
            # never surface via extract_daily_scores.
            ("run-2024-01-04-rerun", "AAPL", "candidate", 0.99, 5.0, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-02-01.json"),
            # Holdings should be excluded.
            ("run-2024-01-02", "AAPL", "holding", 0.05, 1.0, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-01-02.json"),
            # Late-only date's scores -- should never surface (no eligible run).
            ("run-2024-01-05-late-only", "AAPL", "candidate", 0.5, 2.0, "xgb", "panel_ltr_xgboost", "panel-ltr-2024-02-01.json"),
        ],
    )
    conn.executemany(
        "INSERT INTO ticker_forward_returns (as_of_date, ticker, fwd_60d) VALUES (?, ?, ?)",
        [
            ("2024-01-02", "AAPL", 0.12),
            ("2024-01-02", "MSFT", 0.08),
            ("2024-01-02", "GOOG", -0.02),
            ("2024-01-03", "AAPL", 0.10),
            ("2024-01-03", "MSFT", 0.06),
        ],
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Finding 4: --score-column SQL-injection guard
# ─────────────────────────────────────────────────────────────────────────


class TestScoreColumnAllowlist:
    def test_valid_column_accepted(self):
        assert validate_score_column("mu") == "mu"

    def test_allowlist_is_grounded_in_the_real_schema(self):
        # candidate_scores' real numeric score-family columns
        # (renquant-pipeline kernel/persistence.py schema).
        assert ALLOWED_SCORE_COLUMNS == {
            "mu", "raw_score", "panel_score", "rank_score", "rs_score", "sigma",
        }

    @pytest.mark.parametrize("malicious", [
        "mu; DROP TABLE pipeline_runs--",
        "* FROM sqlite_master--",
        "raw_score); ATTACH DATABASE '/tmp/x' AS x--",
        "mu' OR '1'='1",
        "unknown_column",
        "",
    ])
    def test_malicious_or_unknown_column_rejected(self, malicious):
        with pytest.raises(ScoreColumnNotAllowedError):
            validate_score_column(malicious)

    def test_extract_daily_scores_rejects_malicious_column_before_any_sql(self, tmp_path):
        """A malicious --score-column must be rejected before it ever
        reaches a SQL string, and the database must remain intact."""
        db = tmp_path / "test.db"
        _create_test_db(db)
        run_selection, _ = select_asof_runs(
            db, start_date="2024-01-02", end_date="2024-01-02", calendar=_calendar(),
        )
        with pytest.raises(ScoreColumnNotAllowedError):
            extract_daily_scores(
                db,
                score_column="mu; DROP TABLE pipeline_runs--",
                run_selection=run_selection,
            )
        # Prove nothing executed: pipeline_runs must still exist with its rows.
        conn = sqlite3.connect(str(db))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        n_runs = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        conn.close()
        assert "pipeline_runs" in tables
        assert n_runs == 5


# ─────────────────────────────────────────────────────────────────────────
# Findings 1 & 3: as-of contract + negative rerun test
# ─────────────────────────────────────────────────────────────────────────


class TestAsOfContract:
    def test_eligible_runs_selected_for_ordinary_dates(self, tmp_path):
        db = tmp_path / "test.db"
        _create_test_db(db)
        selection, excluded = select_asof_runs(
            db, start_date="2024-01-02", end_date="2024-01-03", calendar=_calendar(),
        )
        assert set(selection) == {"2024-01-02", "2024-01-03"}
        assert selection["2024-01-02"].run_id == "run-2024-01-02"
        assert selection["2024-01-02"].commit_sha == "abc111"
        assert not excluded

    def test_later_rerun_is_not_selected_look_ahead_guard(self, tmp_path):
        """Negative test (Codex finding 3): a later rerun with CHANGED
        scores, committed after the target date's own session-close
        cutoff, must not be selected even though it is the latest run by
        created_at."""
        db = tmp_path / "test.db"
        _create_test_db(db)
        selection, excluded = select_asof_runs(
            db, start_date="2024-01-04", end_date="2024-01-04", calendar=_calendar(),
        )
        assert selection["2024-01-04"].run_id == "run-2024-01-04"
        assert "2024-01-04" not in [e.run_date for e in excluded]

        scores = extract_daily_scores(db, score_column="mu", run_selection=selection)
        assert scores["2024-01-04"]["AAPL"] == pytest.approx(0.06)  # original
        assert scores["2024-01-04"]["AAPL"] != pytest.approx(0.99)  # NOT the rerun

    def test_date_with_only_a_post_cutoff_run_is_excluded_not_admitted(self, tmp_path):
        """When NO eligible (pre-cutoff) run exists for a date -- only a
        much-later reprocessing commit -- the date must be excluded with a
        documented reason, never silently admitted with the late run's
        scores."""
        db = tmp_path / "test.db"
        _create_test_db(db)
        selection, excluded = select_asof_runs(
            db, start_date="2024-01-05", end_date="2024-01-05", calendar=_calendar(),
        )
        assert "2024-01-05" not in selection
        reasons = {e.run_date: e.reason for e in excluded}
        assert "2024-01-05" in reasons
        assert "AFTER the session-close cutoff" in reasons["2024-01-05"]

        scores = extract_daily_scores(db, score_column="mu", run_selection=selection)
        assert "2024-01-05" not in scores

    def test_holdings_excluded(self, tmp_path):
        db = tmp_path / "test.db"
        _create_test_db(db)
        selection, _ = select_asof_runs(
            db, start_date="2024-01-02", end_date="2024-01-02", calendar=_calendar(),
        )
        scores = extract_daily_scores(db, score_column="mu", run_selection=selection)
        assert len(scores["2024-01-02"]) == 3  # not 4 -- holding row excluded

    def test_identity_fields_populated_from_candidate_scores(self, tmp_path):
        db = tmp_path / "test.db"
        _create_test_db(db)
        selection, _ = select_asof_runs(
            db, start_date="2024-01-02", end_date="2024-01-02", calendar=_calendar(),
        )
        extract_daily_scores(db, score_column="mu", run_selection=selection)
        rs = selection["2024-01-02"]
        assert rs.active_scorer == "xgb"
        assert rs.model_type == "panel_ltr_xgboost"
        assert rs.panel_ltr_artifact == "panel-ltr-2024-01-02.json"


# ─────────────────────────────────────────────────────────────────────────
# Forward returns (unchanged behavior)
# ─────────────────────────────────────────────────────────────────────────


def test_extract_forward_returns(tmp_path):
    db = tmp_path / "test.db"
    _create_test_db(db)
    returns = extract_forward_returns(db, start_date="2024-01-02", end_date="2024-01-03")
    assert len(returns) == 5
    assert returns[0]["as_of_date"] == "2024-01-02"
    assert returns[0]["ticker"] == "AAPL"


def test_write_forward_returns_csv(tmp_path):
    returns = [
        {"as_of_date": "2024-01-02", "ticker": "AAPL", "fwd_60d": 0.12},
        {"as_of_date": "2024-01-02", "ticker": "MSFT", "fwd_60d": 0.08},
    ]
    out = tmp_path / "returns.csv"
    digest = write_forward_returns_csv(returns, out)
    assert out.exists()
    lines = out.read_text().strip().split("\n")
    assert lines[0] == "date,ticker,fwd_return"
    assert len(lines) == 3
    assert digest.startswith("sha256:")


# ─────────────────────────────────────────────────────────────────────────
# Finding 2: immutable per-date provenance
# ─────────────────────────────────────────────────────────────────────────


class TestProvenancePayload:
    def _provenance(self, **overrides) -> ProvenanceContext:
        base = dict(
            score_column="mu",
            session_calendar=_calendar(),
            decision_schedule=US_EQUITY_CLOSE,
            db_digest="sha256:" + "0" * 64,
            db_path="/tmp/runs.db",
            has_realized_labels_by_date={"2024-01-02": True},
            label_artifact_ref_by_date={"2024-01-02": "sha256:" + "1" * 64 + "@forward_returns.csv"},
            label_observation_end_by_date={"2024-01-02": "2024-03-02"},
        )
        base.update(overrides)
        return ProvenanceContext(**base)

    def test_top_level_fields_match_admissibility_validator_contract(self):
        run_sel = RunSelection(
            run_id="run-2024-01-02", run_date="2024-01-02",
            created_at_utc="2024-01-02T20:30:00+00:00",
            commit_sha="abc111", active_scorer="xgb",
            model_type="panel_ltr_xgboost",
            panel_ltr_artifact="panel-ltr-2024-01-02.json",
        )
        payload = build_score_payload(
            "2024-01-02", {"AAPL": 0.05},
            expert_name="xgb", backfill_id="test-001",
            run_sel=run_sel, provenance=self._provenance(),
        )
        # Top-level: exactly the keys
        # admissibility_ledger.extract_metadata_from_score reads.
        assert payload["as_of_date"] == "2024-01-02"
        assert payload["data_watermark"] == "2024-01-02"
        assert payload["score_timestamp"] == "2024-01-02T20:30:00+00:00"
        assert payload["training_cutoff"] == "MISSING"
        assert payload["model_content_sha256"] == "MISSING"
        assert payload["has_realized_labels"] is True
        assert payload["label_artifact_ref"].startswith("sha256:")
        assert payload["label_observation_end"] == "2024-03-02"

    def test_extended_provenance_recorded_in_the_artifact_itself(self):
        run_sel = RunSelection(
            run_id="run-2024-01-02", run_date="2024-01-02",
            created_at_utc="2024-01-02T20:30:00+00:00",
            commit_sha="abc111", active_scorer="xgb",
            model_type="panel_ltr_xgboost",
            panel_ltr_artifact="panel-ltr-2024-01-02.json",
        )
        payload = build_score_payload(
            "2024-01-02", {"AAPL": 0.05},
            expert_name="xgb", backfill_id="test-001",
            run_sel=run_sel, provenance=self._provenance(),
        )
        prov = payload["metadata"]["provenance"]
        assert prov["source_run_id"] == "run-2024-01-02"
        assert prov["source_run_type"] == "live"
        assert prov["source_run_created_at_utc"] == "2024-01-02T20:30:00+00:00"
        assert prov["pipeline_commit_sha"] == "abc111"
        assert prov["active_scorer"] == "xgb"
        assert prov["model_type"] == "panel_ltr_xgboost"
        assert prov["panel_ltr_artifact"] == "panel-ltr-2024-01-02.json"
        assert prov["universe_calendar_name"] == "NYSE"
        assert prov["source_db_digest"].startswith("sha256:")
        assert prov["backfill_query_schema_version"]
        # Decision cutoff is durable in the artifact, not just the manifest.
        assert prov["decision_session_cutoff_utc"] == "2024-01-02T21:00:00+00:00"

    def test_never_manufactures_an_admitted_field(self):
        """The candidate-evidence payload must not carry an ``admitted``
        key anywhere -- admission is decided ONLY by the canonical
        validator, never self-attested by the backfill script."""
        run_sel = RunSelection(
            run_id="r1", run_date="2024-01-02", created_at_utc="2024-01-02T20:30:00+00:00",
        )
        payload = build_score_payload(
            "2024-01-02", {"AAPL": 0.05}, expert_name="xgb", backfill_id="b1",
            run_sel=run_sel,
            provenance=self._provenance(
                has_realized_labels_by_date={}, label_artifact_ref_by_date={},
                label_observation_end_by_date={},
            ),
        )
        assert "admitted" not in payload
        assert "admitted" not in payload["metadata"]

    def test_missing_identity_fields_are_honest_not_fabricated(self):
        """When candidate_scores never recorded active_scorer/model_type
        (older data), the payload must say MISSING -- never guess."""
        run_sel = RunSelection(
            run_id="r1", run_date="2024-01-02", created_at_utc="2024-01-02T20:30:00+00:00",
        )
        payload = build_score_payload(
            "2024-01-02", {"AAPL": 0.05}, expert_name="xgb", backfill_id="b1",
            run_sel=run_sel,
            provenance=self._provenance(
                has_realized_labels_by_date={}, label_artifact_ref_by_date={},
                label_observation_end_by_date={},
            ),
        )
        prov = payload["metadata"]["provenance"]
        assert prov["active_scorer"] == "MISSING"
        assert prov["model_type"] == "MISSING"
        assert prov["panel_ltr_artifact"] == "MISSING"
        assert prov["pipeline_commit_sha"] == "MISSING"


# ─────────────────────────────────────────────────────────────────────────
# Finding 3: admission deferred to the canonical validator (end-to-end)
# ─────────────────────────────────────────────────────────────────────────


class TestRunBackfillDefersAdmissionToCanonicalValidator:
    def test_e2e_writes_candidate_evidence_and_a_real_ledger(self, tmp_path):
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"

        manifest = run_backfill(
            runs_db=db, output_dir=out, expert_name="xgb",
            start_date="2024-01-02", end_date="2024-01-04",
        )

        assert isinstance(manifest, BackfillManifest)
        assert manifest.classification == "EXPLORATORY_ONLY"
        # 2024-01-04's rerun must not create a spurious 4th date.
        assert manifest.n_dates_exported == 3

        f = json.loads((out / "xgb" / "2024-01-04.json").read_text())
        assert f["scores"]["AAPL"] == pytest.approx(0.06)  # original, not the rerun's 0.99
        assert f["training_cutoff"] == "MISSING"
        assert f["model_content_sha256"] == "MISSING"

        # The ledger was built by the REAL canonical validator
        # (admissibility_ledger.build_ledger), not hand-rolled here.
        ledger = json.loads((out / "admissibility_ledger.json").read_text())
        assert len(ledger["records"]) == 3
        for record in ledger["records"]:
            assert record["admitted"] is False
            reasons = " ".join(record["rejection_reasons"])
            assert "training cutoff" in reasons
            assert "fingerprint" in reasons

        # The manifest reports the SAME verdict transparently.
        assert manifest.ledger_admitted == 0
        assert manifest.ledger_rejected == 3
        assert manifest.ledger_fingerprint

    def test_asof_excluded_dates_are_documented_not_silently_dropped(self, tmp_path):
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"

        manifest = run_backfill(
            runs_db=db, output_dir=out, expert_name="xgb",
            start_date="2024-01-02", end_date="2024-01-05",
        )
        assert "2024-01-05" in manifest.asof_exclusion_reasons
        assert not (out / "xgb" / "2024-01-05.json").exists()
        assert manifest.n_dates_excluded_asof_contract >= 1

    def test_score_file_digest_matches_ledger_record(self, tmp_path):
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"

        run_backfill(
            runs_db=db, output_dir=out, expert_name="xgb",
            start_date="2024-01-02", end_date="2024-01-02",
        )

        score_file = out / "xgb" / "2024-01-02.json"
        actual = f"sha256:{hashlib.sha256(score_file.read_bytes()).hexdigest()}"
        ledger = json.loads((out / "admissibility_ledger.json").read_text())
        assert ledger["records"][0]["score_artifact_digest"] == actual

    def test_manifest_and_classification_files_written(self, tmp_path):
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"

        run_backfill(
            runs_db=db, output_dir=out, expert_name="xgb",
            start_date="2024-01-02", end_date="2024-01-03",
        )

        manifest_path = out / "backfill_manifest.json"
        assert manifest_path.exists()
        m = json.loads(manifest_path.read_text())
        assert m["classification"] == "EXPLORATORY_ONLY"
        assert len(m["score_file_digests"]) == 2

        cls_path = out / "_experiment_classification.json"
        assert cls_path.exists()
        cls = json.loads(cls_path.read_text())
        assert cls["classification"] == "EXPLORATORY_ONLY"

    def test_universe_file_used_when_provided(self, tmp_path):
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"
        universe_file = tmp_path / "universe.txt"
        universe_file.write_text("AAPL\nMSFT\nGOOG\nAMZN\n")

        manifest = run_backfill(
            runs_db=db, output_dir=out, expert_name="xgb",
            start_date="2024-01-02", end_date="2024-01-02",
            universe_file=universe_file,
        )
        assert manifest.universe_size == 4
        assert manifest.universe_source == f"file:{universe_file}"


# ─────────────────────────────────────────────────────────────────────────
# CLI exit-code behavior (Codex re-review P1)
# ─────────────────────────────────────────────────────────────────────────


class TestCLIExitCode:
    def test_exits_nonzero_when_zero_admitted_default(self, tmp_path):
        """Default CLI must return non-zero when the canonical ledger
        admits zero records -- a wholly rejected batch is not successful
        Phase-A input production."""
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"
        rc = main([
            "--runs-db", str(db),
            "--output-dir", str(out),
            "--expert-name", "xgb",
            "--start-date", "2024-01-02",
            "--end-date", "2024-01-04",
        ])
        assert rc == 2

    def test_exits_zero_with_diagnostic_only_even_when_zero_admitted(self, tmp_path):
        """--diagnostic-only preserves exit 0 for intentional
        rejected-evidence reports."""
        db = tmp_path / "runs.db"
        _create_test_db(db)
        out = tmp_path / "output"
        rc = main([
            "--runs-db", str(db),
            "--output-dir", str(out),
            "--expert-name", "xgb",
            "--start-date", "2024-01-02",
            "--end-date", "2024-01-04",
            "--diagnostic-only",
        ])
        assert rc == 0

    def test_exits_nonzero_for_missing_db(self, tmp_path):
        rc = main([
            "--runs-db", str(tmp_path / "nonexistent.db"),
            "--output-dir", str(tmp_path / "output"),
            "--expert-name", "xgb",
        ])
        assert rc == 1

    def test_exits_nonzero_for_invalid_score_column(self, tmp_path):
        db = tmp_path / "runs.db"
        _create_test_db(db)
        rc = main([
            "--runs-db", str(db),
            "--output-dir", str(tmp_path / "output"),
            "--expert-name", "xgb",
            "--score-column", "malicious; DROP TABLE x--",
        ])
        assert rc == 1
