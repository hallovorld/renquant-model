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
    build_ledger,
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
        "scored_count": len(UNIVERSE),
        "has_realized_labels": True,
    }


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
        meta["scored_count"] = 5  # 50% of 10-ticker universe
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("missingness" in r for r in record.rejection_reasons)

    def test_accepts_moderate_missingness(self) -> None:
        meta = _good_meta()
        meta["scored_count"] = 9  # 10% missing, under 20% threshold
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is True

    def test_rejects_score_timestamp_before_prediction_date(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "2026-01-10T09:00:00Z"  # before prediction date
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("score_timestamp" in r for r in record.rejection_reasons)

    def test_rejects_missing_score_timestamp(self) -> None:
        meta = _good_meta()
        meta["score_timestamp"] = "MISSING"
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert any("score timestamp" in r for r in record.rejection_reasons)

    def test_has_realized_labels_defaults_false(self) -> None:
        """has_realized_labels must default to False (fail-closed)."""
        meta = _good_meta()
        del meta["has_realized_labels"]
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.has_realized_labels is False

    def test_accumulates_multiple_rejections(self) -> None:
        meta = {
            "model_fingerprint": "MISSING",
            "training_cutoff": "2026-02-01",
            "feature_data_cutoff": "MISSING",
            "score_timestamp": "MISSING",
            "scored_count": 0,
        }
        expert = ExpertSpec(name="xgb", score_dir=Path("."))
        record = validate_expert_date(expert, "2026-01-15", meta, UNIVERSE)
        assert record.admitted is False
        assert len(record.rejection_reasons) >= 3


class TestBuildLedger:
    def test_empty_ledger_fails_closed(self) -> None:
        """Zero prediction dates -> all_experts_fully_admitted must be False."""
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

        ledger = build_ledger(experts, dates, UNIVERSE, score_loader=loader)
        assert ledger.summary["total_records"] == 6  # 2 experts × 3 dates
        assert ledger.summary["all_experts_fully_admitted"] is True
        for name in ["xgb", "patchtst"]:
            assert ledger.summary["per_expert"][name]["admitted"] == 3
            assert ledger.summary["per_expert"][name]["rejected"] == 0

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
                "scored_count": 0,
            }

        ledger = build_ledger(experts, dates, UNIVERSE, score_loader=loader)
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

        ledger = build_ledger(experts, dates, UNIVERSE, score_loader=loader)
        output_path = write_ledger(ledger, tmp_path)
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["experts"] == ["xgb"]
        assert data["summary"]["total_records"] == 1
        assert data["ledger_fingerprint"].startswith("sha256:")
