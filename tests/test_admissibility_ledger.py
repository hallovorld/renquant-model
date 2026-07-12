"""Tests for the Stage 0 admissibility ledger builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "experiments" / "ensemble_phase0"))

from admissibility_ledger import (
    FINGERPRINT_RE,
    AdmissibilityLedger,
    ExpertAdmissibilityRecord,
    ExpertSpec,
    _assess_complementarity,
    build_complementarity_report,
    build_ledger,
    extract_metadata_from_score,
    load_score_file,
    validate_expert_date,
    write_ledger,
)


UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ"]
VALID_FP = "sha256:" + "0123456789abcdef" * 4  # 64 hex chars


def _good_meta(prediction_date: str = "2026-01-15") -> dict[str, Any]:
    return {
        "model_fingerprint": VALID_FP,
        "training_cutoff": "2025-12-31",
        "feature_data_cutoff": prediction_date,
        "data_watermark": prediction_date,
        "score_timestamp": f"{prediction_date}T16:00:00Z",
        "score_keys": list(UNIVERSE),
        "has_realized_labels": True,
    }


class TestExtractMetadata:
    def test_extracts_has_realized_labels_true(self) -> None:
        score_data = {
            "model_content_sha256": VALID_FP,
            "training_cutoff": "2025-12-31",
            "as_of_date": "2026-01-15",
            "score_timestamp": "2026-01-15T16:00:00Z",
            "has_realized_labels": True,
            "scores": {"AAPL": 0.5, "MSFT": 0.3},
        }
        meta = extract_metadata_from_score(score_data, ExpertSpec(name="xgb", score_dir=Path(".")))
        assert meta["has_realized_labels"] is True
        assert meta["score_keys"] == ["AAPL", "MSFT"]

    def test_has_realized_labels_defaults_false(self) -> None:
        score_data = {
            "model_content_sha256": VALID_FP,
            "scores": {},
        }
        meta = extract_metadata_from_score(score_data, ExpertSpec(name="xgb", score_dir=Path(".")))
        assert meta["has_realized_labels"] is False

    def test_score_keys_from_scores_dict(self) -> None:
        score_data = {
            "scores": {"AAPL": 0.1, "GOOGL": 0.2, "UNKNOWN": 0.3},
        }
        meta = extract_metadata_from_score(score_data, ExpertSpec(name="x", score_dir=Path(".")))
        assert set(meta["score_keys"]) == {"AAPL", "GOOGL", "UNKNOWN"}

    def test_data_watermark_extracted(self) -> None:
        score_data = {
            "model_content_sha256": VALID_FP,
            "as_of_date": "2026-01-15",
            "data_watermark": "2026-01-15T09:30:00Z",
            "scores": {},
        }
        meta = extract_metadata_from_score(score_data, ExpertSpec(name="xgb", score_dir=Path(".")))
        assert meta["data_watermark"] == "2026-01-15T09:30:00Z"

    def test_data_watermark_defaults_to_feature_cutoff(self) -> None:
        score_data = {
            "model_content_sha256": VALID_FP,
            "as_of_date": "2026-01-15",
            "scores": {},
        }
        meta = extract_metadata_from_score(score_data, ExpertSpec(name="xgb", score_dir=Path(".")))
        assert meta["data_watermark"] == "2026-01-15"


class TestValidateExpertDate:
    def test_admits_valid_record(self) -> None:
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(
            expert, "2026-01-15", _good_meta(), UNIVERSE
        )
        assert record.admitted is True
        assert record.rejection_reasons == []
        assert record.missingness_rate == 0.0

    def test_rejects_missing_fingerprint(self) -> None:
        meta = _good_meta()
        meta["model_fingerprint"] = "MISSING"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("fingerprint" in r for r in record.rejection_reasons)

    def test_rejects_invalid_fingerprint_syntax(self) -> None:
        """Non-SHA-256 fingerprint string is rejected."""
        meta = _good_meta()
        meta["model_fingerprint"] = "sha256:abc123"  # too short
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("invalid fingerprint syntax" in r for r in record.rejection_reasons)

    def test_rejects_uppercase_hex_fingerprint(self) -> None:
        """Uppercase hex is rejected — canonical form is lowercase."""
        meta = _good_meta()
        meta["model_fingerprint"] = "sha256:" + "ABCDEF01" * 8  # 64 uppercase
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("invalid fingerprint syntax" in r for r in record.rejection_reasons)

    def test_rejects_wrong_prefix_fingerprint(self) -> None:
        meta = _good_meta()
        meta["model_fingerprint"] = "md5:" + "a" * 64
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("invalid fingerprint syntax" in r for r in record.rejection_reasons)

    def test_fingerprint_regex_matches_valid(self) -> None:
        assert FINGERPRINT_RE.match(VALID_FP)
        assert not FINGERPRINT_RE.match("sha256:abc123")
        assert not FINGERPRINT_RE.match("sha256:" + "G" * 64)

    def test_rejects_training_cutoff_lookahead(self) -> None:
        meta = _good_meta()
        meta["training_cutoff"] = "2026-02-01"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("lookahead" in r for r in record.rejection_reasons)

    def test_rejects_feature_cutoff_lookahead(self) -> None:
        meta = _good_meta()
        meta["feature_data_cutoff"] = "2026-01-16"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("lookahead" in r for r in record.rejection_reasons)

    def test_rejects_training_cutoff_after_data_watermark(self) -> None:
        """Causal violation: training on data at/after inference watermark."""
        meta = _good_meta()
        meta["training_cutoff"] = "2026-01-15"
        meta["data_watermark"] = "2026-01-15"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-16", meta, UNIVERSE)
        assert record.admitted is False
        assert any("causal violation" in r for r in record.rejection_reasons)

    def test_rejects_missing_data_watermark(self) -> None:
        """Missing data_watermark must reject, not silently skip."""
        meta = _good_meta()
        meta["data_watermark"] = "MISSING"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("missing data watermark" in r for r in record.rejection_reasons)

    def test_rejects_unparseable_data_watermark(self) -> None:
        """Garbage data_watermark must reject with clear message."""
        meta = _good_meta()
        meta["data_watermark"] = "not-a-date-at-all"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("unparseable" in r for r in record.rejection_reasons)

    def test_rejects_data_watermark_after_prediction_date(self) -> None:
        """data_watermark after prediction_date is lookahead."""
        meta = _good_meta()
        meta["data_watermark"] = "2026-01-16T09:30:00+00:00"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("lookahead" in r for r in record.rejection_reasons)

    def test_admits_valid_timestamp_watermark(self) -> None:
        """Timezone-aware watermark within chain is admitted."""
        meta = _good_meta()
        meta["data_watermark"] = "2026-01-15T09:30:00+00:00"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_rejects_high_missingness(self) -> None:
        meta = _good_meta()
        meta["score_keys"] = UNIVERSE[:5]  # 50% missing
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("missingness" in r for r in record.rejection_reasons)

    def test_accepts_moderate_missingness(self) -> None:
        meta = _good_meta()
        meta["score_keys"] = UNIVERSE[:9]  # 10% missing, under 20%
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_admits_d_minus_1_overnight_scoring(self) -> None:
        """D-1 overnight scoring is valid: score produced after D-1 close."""
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-14T22:00:00Z"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_admits_pre_prediction_date_scoring(self) -> None:
        """Pre-D scoring is valid when within decision window."""
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-10T09:00:00Z"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_rejects_score_timestamp_after_decision_timestamp(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-17T09:00:00Z"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(
            expert, "2026-01-15", meta, UNIVERSE,
            decision_timestamp="2026-01-16T23:59:59+00:00",
        )
        assert record.admitted is False
        assert any("late score" in r for r in record.rejection_reasons)

    def test_rejects_score_timestamp_after_default_same_day_cap(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-16T09:00:00Z"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("late score" in r for r in record.rejection_reasons)

    def test_handles_timezone_offset_in_score_timestamp(self) -> None:
        """Score at 11pm ET (4am+1 UTC) on prediction date is within window."""
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-15T23:00:00-05:00"  # 4am UTC Jan 16
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        # Default decision_timestamp = 2026-01-15T23:59:59+00:00 (UTC)
        # 23:00 ET = 04:00 UTC Jan 16 > 23:59:59 UTC Jan 15 → rejected
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("late score" in r for r in record.rejection_reasons)

    def test_admits_within_timezone_offset_window(self) -> None:
        """Score at 6pm ET on prediction date is within UTC end-of-day."""
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-15T18:00:00-05:00"  # 23:00 UTC
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_rejects_missing_score_timestamp(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "MISSING"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("score timestamp" in r for r in record.rejection_reasons)

    def test_has_realized_labels_defaults_false_and_rejects(self) -> None:
        """Missing has_realized_labels defaults to False and rejects."""
        meta = _good_meta()
        del meta["has_realized_labels"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.has_realized_labels is False
        assert record.admitted is False
        assert any("no realized labels" in r for r in record.rejection_reasons)

    def test_no_labels_admitted_when_not_required(self) -> None:
        """When require_realized_labels=False, absent labels do not reject."""
        meta = _good_meta()
        meta["has_realized_labels"] = False
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(
            expert, "2026-01-15", meta, UNIVERSE,
            require_realized_labels=False,
        )
        assert record.has_realized_labels is False
        assert record.admitted is True

    def test_rejects_absent_realized_labels(self) -> None:
        """Explicit has_realized_labels=False under default policy rejects."""
        meta = _good_meta()
        meta["has_realized_labels"] = False
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("no realized labels" in r for r in record.rejection_reasons)

    def test_rejects_unknown_tickers(self) -> None:
        meta = _good_meta()
        meta["score_keys"] = list(UNIVERSE) + ["FAKE1", "FAKE2"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("unknown" in r for r in record.rejection_reasons)

    def test_rejects_duplicate_keys(self) -> None:
        meta = _good_meta()
        meta["score_keys"] = list(UNIVERSE) + ["AAPL", "AAPL"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("duplicate" in r for r in record.rejection_reasons)

    def test_scored_count_uses_universe_intersection(self) -> None:
        meta = _good_meta()
        meta["score_keys"] = ["AAPL", "MSFT", "UNKNOWN_TICKER"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.scored_count == 2  # only AAPL+MSFT in universe
        assert record.missing_count == 8
        assert record.admitted is False  # 80% missingness + unknown ticker

    def test_accumulates_multiple_rejections(self) -> None:
        meta = {
            "model_fingerprint": "MISSING",
            "training_cutoff": "2026-02-01",
            "feature_data_cutoff": "MISSING",
            "score_timestamp": "MISSING",
            "score_keys": [],
        }
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert len(record.rejection_reasons) >= 3


class TestBuildLedger:
    def test_empty_ledger_fails_closed(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        ledger = build_ledger(experts, [], UNIVERSE)
        assert ledger.summary["total_records"] == 0
        assert ledger.summary["all_experts_fully_admitted"] is False
        assert ledger.experts == ["xgb"]

    def test_builds_ledger_with_loader(self) -> None:
        experts = [
            ExpertSpec(name="xgb", score_dir=Path(".")),
            ExpertSpec(name="patchtst", score_dir=Path(".")),
        ]
        dates = ["2026-01-13", "2026-01-14", "2026-01-15"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="PLAUSIBLE",
        )
        assert ledger.summary["total_records"] == 6
        assert ledger.summary["all_experts_fully_admitted"] is True
        assert ledger.summary["complementarity_ok"] is True
        for name in ["xgb", "patchtst"]:
            assert ledger.summary["per_expert"][name]["admitted"] == 3
            assert ledger.summary["per_expert"][name]["rejected"] == 0

    def test_fails_without_complementarity(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(experts, dates, UNIVERSE, score_loader=loader)
        assert ledger.summary["complementarity_assessment"] == "NOT_EVALUATED"
        assert ledger.summary["all_experts_fully_admitted"] is False

    def test_fails_with_insufficient_complementarity(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="INSUFFICIENT_DATA",
        )
        assert ledger.summary["all_experts_fully_admitted"] is False

    def test_fails_with_near_duplicate(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="NEAR_DUPLICATE — experts produce near-identical scores",
        )
        assert ledger.summary["all_experts_fully_admitted"] is False

    def test_partial_rejection(self) -> None:
        experts = [ExpertSpec(name="bad_model", score_dir=Path("."))]
        dates = ["2026-01-13", "2026-01-14"]

        call_count = 0

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _good_meta(dt)
            return {
                "model_fingerprint": "MISSING",
                "training_cutoff": "MISSING",
                "feature_data_cutoff": "MISSING",
                "score_timestamp": "MISSING",
                "score_keys": [],
            }

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="PLAUSIBLE",
        )
        assert ledger.summary["all_experts_fully_admitted"] is False
        stats = ledger.summary["per_expert"]["bad_model"]
        assert stats["admitted"] == 1
        assert stats["rejected"] == 1

    def test_ledger_fingerprint_is_deterministic(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        l1 = build_ledger(experts, dates, UNIVERSE, score_loader=loader)
        l2 = build_ledger(experts, dates, UNIVERSE, score_loader=loader)
        assert l1.ledger_fingerprint == l2.ledger_fingerprint
        assert l1.ledger_fingerprint.startswith("sha256:")


class TestWriteLedger:
    def test_writes_json(self, tmp_path: Path) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="PLAUSIBLE",
        )
        output_path = write_ledger(ledger, tmp_path)
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["experts"] == ["xgb"]
        assert data["summary"]["total_records"] == 1
        assert data["ledger_fingerprint"].startswith("sha256:")


class TestLoadScoreFile:
    def test_loads_json(self, tmp_path: Path) -> None:
        score = {"scores": {"AAPL": 0.5}, "model_content_sha256": "abc"}
        p = tmp_path / "2026-01-15.json"
        p.write_text(json.dumps(score))
        result = load_score_file(p)
        assert result["scores"]["AAPL"] == 0.5

    def test_rejects_parquet(self, tmp_path: Path) -> None:
        p = tmp_path / "2026-01-15.parquet"
        p.write_bytes(b"dummy")
        result = load_score_file(p)
        assert result is None

    def test_rejects_unknown_format(self, tmp_path: Path) -> None:
        p = tmp_path / "2026-01-15.csv"
        p.write_text("a,b\n1,2")
        result = load_score_file(p)
        assert result is None


class TestIntegrationArtifactToLedger:
    """End-to-end CLI-style integration tests from score files to ledger."""

    def _write_score(
        self, score_dir: Path, dt: str, *,
        tickers: list[str] | None = None,
        fingerprint: str = VALID_FP,
        training_cutoff: str = "2025-12-31",
        feature_cutoff: str | None = None,
        data_watermark: str | None = None,
        score_timestamp: str | None = None,
        has_labels: bool = True,
    ) -> Path:
        if tickers is None:
            tickers = list(UNIVERSE)
        if feature_cutoff is None:
            feature_cutoff = dt
        if score_timestamp is None:
            score_timestamp = f"{dt}T16:00:00Z"
        score = {
            "model_content_sha256": fingerprint,
            "training_cutoff": training_cutoff,
            "as_of_date": feature_cutoff,
            "data_watermark": data_watermark or feature_cutoff,
            "score_timestamp": score_timestamp,
            "has_realized_labels": has_labels,
            "scores": {t: 0.01 * i for i, t in enumerate(tickers)},
        }
        p = score_dir / f"{dt}.json"
        p.write_text(json.dumps(score))
        return p

    def test_valid_scores_admitted(self, tmp_path: Path) -> None:
        score_dir = tmp_path / "xgb"
        score_dir.mkdir()
        self._write_score(score_dir, "2026-01-15")
        expert = ExpertSpec(name="xgb", score_dir=score_dir)

        data = load_score_file(score_dir / "2026-01-15.json")
        meta = extract_metadata_from_score(data, expert)
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_stale_training_cutoff_rejected(self, tmp_path: Path) -> None:
        score_dir = tmp_path / "xgb"
        score_dir.mkdir()
        self._write_score(score_dir, "2026-01-15", training_cutoff="2026-02-01")
        expert = ExpertSpec(name="xgb", score_dir=score_dir)

        data = load_score_file(score_dir / "2026-01-15.json")
        meta = extract_metadata_from_score(data, expert)
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("lookahead" in r for r in record.rejection_reasons)

    def test_late_score_rejected(self, tmp_path: Path) -> None:
        score_dir = tmp_path / "xgb"
        score_dir.mkdir()
        self._write_score(
            score_dir, "2026-01-15",
            score_timestamp="2026-01-17T09:00:00Z",
        )
        expert = ExpertSpec(name="xgb", score_dir=score_dir)

        data = load_score_file(score_dir / "2026-01-15.json")
        meta = extract_metadata_from_score(data, expert)
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("late score" in r for r in record.rejection_reasons)

    def test_malformed_score_file(self, tmp_path: Path) -> None:
        score_dir = tmp_path / "xgb"
        score_dir.mkdir()
        (score_dir / "2026-01-15.json").write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_score_file(score_dir / "2026-01-15.json")

    def test_mismatched_universe(self, tmp_path: Path) -> None:
        score_dir = tmp_path / "xgb"
        score_dir.mkdir()
        self._write_score(
            score_dir, "2026-01-15",
            tickers=["AAPL", "MSFT", "UNKNOWN1", "UNKNOWN2"],
        )
        expert = ExpertSpec(name="xgb", score_dir=score_dir)

        data = load_score_file(score_dir / "2026-01-15.json")
        meta = extract_metadata_from_score(data, expert)
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("unknown" in r for r in record.rejection_reasons)
        assert any("missingness" in r for r in record.rejection_reasons)
        assert record.scored_count == 2  # only AAPL+MSFT in universe

    def test_insufficient_complementarity_blocks(self, tmp_path: Path) -> None:
        score_dir = tmp_path / "xgb"
        score_dir.mkdir()
        self._write_score(score_dir, "2026-01-15")
        experts = [ExpertSpec(name="xgb", score_dir=score_dir)]
        dates = ["2026-01-15"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            data = load_score_file(expert.score_dir / f"{dt}.json")
            return extract_metadata_from_score(data, expert)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="INSUFFICIENT_DATA",
        )
        assert ledger.summary["all_experts_fully_admitted"] is False
        assert ledger.summary["complementarity_ok"] is False


class TestComplementarityNaN:
    """NaN/constant score streams must be rejected, not slip through as PLAUSIBLE."""

    def test_assess_rejects_nan_pearson(self) -> None:
        result = _assess_complementarity(float("nan"), 0.5, 0.3)
        assert "NON_FINITE" in result

    def test_assess_rejects_nan_spearman(self) -> None:
        result = _assess_complementarity(0.5, float("nan"), 0.3)
        assert "NON_FINITE" in result

    def test_assess_rejects_inf(self) -> None:
        result = _assess_complementarity(float("inf"), 0.5, 0.3)
        assert "NON_FINITE" in result

    def test_assess_rejects_nan_disagree(self) -> None:
        result = _assess_complementarity(0.5, 0.5, float("nan"))
        assert "NON_FINITE" in result

    def test_assess_none_is_insufficient(self) -> None:
        result = _assess_complementarity(None, None, None)
        assert result == "INSUFFICIENT_DATA"

    def test_constant_scores_produce_degenerate_report(self) -> None:
        """Constant score streams across all tickers produce NaN correlation."""
        pytest.importorskip("numpy")
        pytest.importorskip("scipy")

        expert_scores = {
            "const_expert": {
                "2026-01-15": {t: 0.5 for t in UNIVERSE},  # constant
            },
            "varied_expert": {
                "2026-01-15": {t: 0.01 * i for i, t in enumerate(UNIVERSE)},
            },
        }
        report = build_complementarity_report(
            expert_scores, ["2026-01-15"], UNIVERSE
        )
        # Constant vs. varied should produce NaN Pearson (std=0 for const).
        assert report["n_degenerate_pairs"] >= 1
        # Assessment must NOT be PLAUSIBLE.
        assert "PLAUSIBLE" not in report["complementarity_assessment"]


class TestFingerprintMutation:
    """Tamper detection: mutating records after creation changes the fingerprint."""

    def test_mutation_changes_fingerprint(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="PLAUSIBLE",
        )
        original_fp = ledger.ledger_fingerprint
        assert original_fp.startswith("sha256:")

        # Tamper: flip admission status on the first record.
        ledger.records[0]["admitted"] = not ledger.records[0]["admitted"]
        tampered_fp = ledger.compute_fingerprint()
        assert tampered_fp != original_fp

    def test_fingerprint_covers_all_records(self) -> None:
        experts = [ExpertSpec(name="xgb", score_dir=Path("."))]
        dates = ["2026-01-13", "2026-01-14"]

        def loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        ledger = build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="PLAUSIBLE",
        )
        fp_full = ledger.ledger_fingerprint

        # Remove a record and recompute — fingerprint must change.
        ledger.records.pop()
        assert ledger.compute_fingerprint() != fp_full


class TestPerDateDecisionTimestamp:
    """decision_timestamp must be per-(expert, prediction_date), not global.

    A single global late timestamp would let a late-generated score slip
    through for an early historical date — that is look-ahead.
    """

    def test_global_late_timestamp_blocked_per_date(self) -> None:
        """Multi-date ledger: a score generated after an early date's EOD
        is rejected even though it would fit a later date's window.

        Previously, a global --decision-timestamp="2026-01-20T23:59:59Z"
        would admit a Jan-17 score for a Jan-13 prediction. With per-date
        timestamps, Jan-13 uses 2026-01-13T23:59:59+00:00 and correctly
        rejects the late score.
        """
        dates = ["2026-01-13", "2026-01-14", "2026-01-15"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))

        def loader(exp: ExpertSpec, dt: str) -> dict[str, Any]:
            meta = _good_meta(dt)
            if dt == "2026-01-13":
                # Score was generated on Jan 17 — late for Jan 13.
                meta["score_timestamp"] = "2026-01-17T09:00:00+00:00"
            return meta

        # Without global override: per-date EOD applies, Jan-13 rejects.
        ledger = build_ledger(
            [expert], dates, UNIVERSE, score_loader=loader,
            complementarity_assessment="PLAUSIBLE",
        )
        jan13_record = [
            r for r in ledger.records if r["prediction_date"] == "2026-01-13"
        ][0]
        assert jan13_record["admitted"] is False
        assert any("late score" in r for r in jan13_record["rejection_reasons"])

        # Jan-14 and Jan-15 should still be admitted.
        for dt in ["2026-01-14", "2026-01-15"]:
            rec = [r for r in ledger.records if r["prediction_date"] == dt][0]
            assert rec["admitted"] is True, f"{dt} should be admitted"

    def test_decision_timestamp_fn_called_per_expert_date(self) -> None:
        """Custom decision_timestamp_fn receives (expert_name, date) pairs."""
        dates = ["2026-01-13", "2026-01-14"]
        experts = [
            ExpertSpec(name="xgb", score_dir=Path(".")),
            ExpertSpec(name="patchtst", score_dir=Path(".")),
        ]
        calls: list[tuple[str, str]] = []

        def ts_fn(expert_name: str, pred_date: str) -> str:
            calls.append((expert_name, pred_date))
            return f"{pred_date}T23:59:59+00:00"

        def loader(exp: ExpertSpec, dt: str) -> dict[str, Any]:
            return _good_meta(dt)

        build_ledger(
            experts, dates, UNIVERSE, score_loader=loader,
            decision_timestamp_fn=ts_fn,
            complementarity_assessment="PLAUSIBLE",
        )
        # Exactly 4 calls: 2 experts x 2 dates.
        assert len(calls) == 4
        assert ("xgb", "2026-01-13") in calls
        assert ("xgb", "2026-01-14") in calls
        assert ("patchtst", "2026-01-13") in calls
        assert ("patchtst", "2026-01-14") in calls

    def test_per_date_fn_rejects_late_score(self) -> None:
        """A custom fn that gives each date a tight window rejects late scores."""
        dates = ["2026-01-13"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))

        def loader(exp: ExpertSpec, dt: str) -> dict[str, Any]:
            meta = _good_meta(dt)
            # Score generated well after Jan 13 close.
            meta["score_timestamp"] = "2026-01-14T10:00:00+00:00"
            return meta

        # fn returns EOD for each date.
        def ts_fn(expert_name: str, pred_date: str) -> str:
            return f"{pred_date}T23:59:59+00:00"

        ledger = build_ledger(
            [expert], dates, UNIVERSE, score_loader=loader,
            decision_timestamp_fn=ts_fn,
            complementarity_assessment="PLAUSIBLE",
        )
        assert ledger.records[0]["admitted"] is False
        assert any("late score" in r for r in ledger.records[0]["rejection_reasons"])
