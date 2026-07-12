"""Tests for the Stage 0 admissibility ledger builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "experiments" / "ensemble_phase0"))

from admissibility_ledger import (
    AdmissibilityLedger,
    ExpertAdmissibilityRecord,
    ExpertSpec,
    build_complementarity_report,
    build_ledger,
    extract_metadata_from_score,
    load_score_file,
    validate_expert_date,
    write_ledger,
)


UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ"]


def _good_meta(prediction_date: str = "2026-01-15") -> dict[str, Any]:
    return {
        "model_fingerprint": "sha256:abc123",
        "training_cutoff": "2025-12-31",
        "feature_data_cutoff": prediction_date,
        "score_timestamp": f"{prediction_date}T16:00:00Z",
        "score_keys": list(UNIVERSE),
        "has_realized_labels": True,
    }


class TestExtractMetadata:
    def test_extracts_has_realized_labels_true(self) -> None:
        score_data = {
            "model_content_sha256": "sha256:abc",
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
            "model_content_sha256": "sha256:abc",
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

    def test_rejects_score_timestamp_before_prediction_date(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-10T09:00:00Z"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("score_timestamp" in r for r in record.rejection_reasons)

    def test_rejects_score_timestamp_after_decision_cutoff(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-17T09:00:00Z"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(
            expert, "2026-01-15", meta, UNIVERSE,
            decision_timestamp_max="2026-01-16",
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

    def test_rejects_missing_score_timestamp(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "MISSING"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("score timestamp" in r for r in record.rejection_reasons)

    def test_has_realized_labels_defaults_false(self) -> None:
        meta = _good_meta()
        del meta["has_realized_labels"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.has_realized_labels is False

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
        fingerprint: str = "sha256:abc",
        training_cutoff: str = "2025-12-31",
        feature_cutoff: str | None = None,
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
