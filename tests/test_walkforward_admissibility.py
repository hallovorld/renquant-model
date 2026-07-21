"""Tests for walkforward_admissibility (GOAL-4 sim-DB admissibility).

The contract: a walkforward-sim prediction date is admissible iff a retrain
fold with cutoff_date+lookahead_days STRICTLY before the date exists (mirroring
model_as_of), and the admission stamps a truthful training_cutoff. This is the
leakage-correct replacement for the live-DB created_at check when the source is
a walkforward-sim DB (all sim runs share one batch created_at).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "experiments" / "ensemble_phase0"))

from walkforward_admissibility import (  # noqa: E402
    WalkforwardFold,
    load_walkforward_folds,
    select_walkforward_fold,
    walkforward_admissibility,
)


def _fold(cutoff: str, lookahead: int = 60, uri: str = "") -> WalkforwardFold:
    return WalkforwardFold(cutoff_date=cutoff, lookahead_days=lookahead, artifact_uri=uri)


class TestUsableFrom:
    def test_usable_from_adds_lookahead(self):
        f = _fold("2023-10-02", 60)
        assert f.usable_from.isoformat() == "2023-12-01"


class TestLoadManifest:
    def test_parses_retrains_schema_and_sorts(self, tmp_path):
        m = {
            "retrains": [
                {"cutoff_date": "2023-10-23", "lookahead_days": 60, "artifact_uri": "b.json"},
                {"cutoff_date": "2023-10-02", "lookahead_days": 60, "artifact_uri": "a.json"},
            ]
        }
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps(m))
        folds = load_walkforward_folds(p)
        assert [f.cutoff_date for f in folds] == ["2023-10-02", "2023-10-23"]  # sorted
        assert folds[0].artifact_uri == "a.json"

    def test_accepts_folds_alias_and_lookahead_alias(self, tmp_path):
        m = {"folds": [{"cutoff_date": "2024-01-01", "lookahead": 60}]}
        p = tmp_path / "m.json"
        p.write_text(json.dumps(m))
        folds = load_walkforward_folds(p)
        assert len(folds) == 1 and folds[0].lookahead_days == 60

    def test_skips_incomplete_entries_never_silently_admits(self, tmp_path):
        # a fold missing cutoff or lookahead must be dropped, not defaulted
        m = {"retrains": [
            {"cutoff_date": "2024-01-01"},  # no lookahead
            {"lookahead_days": 60},          # no cutoff
            {"cutoff_date": "2024-02-01", "lookahead_days": 60},
        ]}
        p = tmp_path / "m.json"
        p.write_text(json.dumps(m))
        folds = load_walkforward_folds(p)
        assert [f.cutoff_date for f in folds] == ["2024-02-01"]


class TestFoldSelection:
    def setup_method(self):
        self.folds = [
            _fold("2023-10-02", 60, "f1"),  # usable 2023-12-01
            _fold("2023-10-23", 60, "f2"),  # usable 2023-12-22
            _fold("2024-01-15", 60, "f3"),  # usable 2024-03-15
        ]

    def test_picks_latest_usable_fold(self):
        # 2024-04-01 is past all three usable_from -> latest cutoff wins
        f = select_walkforward_fold(self.folds, "2024-04-01")
        assert f.cutoff_date == "2024-01-15"

    def test_strict_before_boundary_excludes_equal_date(self):
        # usable_from of f1 is 2023-12-01; a prediction exactly on 2023-12-01
        # is NOT covered (strict <, mirrors model_as_of)
        assert select_walkforward_fold([self.folds[0]], "2023-12-01") is None
        assert select_walkforward_fold([self.folds[0]], "2023-12-02").cutoff_date == "2023-10-02"

    def test_before_coverage_returns_none(self):
        assert select_walkforward_fold(self.folds, "2023-01-01") is None

    def test_middle_date_picks_correct_vintage(self):
        # 2024-01-01: f1 (usable 12-01) and f2 (usable 12-22) usable, f3 (03-15) not
        f = select_walkforward_fold(self.folds, "2024-01-01")
        assert f.cutoff_date == "2023-10-23"


class TestAdmissibility:
    def test_admits_and_stamps_truthful_training_cutoff(self):
        folds = [_fold("2023-12-01", 60, "art.pt")]  # usable 2024-01-30
        adm = walkforward_admissibility(folds, "2024-02-15")
        assert adm.admitted is True
        assert adm.training_cutoff == "2023-12-01"  # the fold's cutoff, NOT "MISSING"
        assert adm.feature_data_cutoff == "2024-02-15"  # inference as-of = the date
        assert adm.fold_artifact_uri == "art.pt"
        assert adm.rejection_reasons == ()

    def test_rejects_before_coverage_with_reason(self):
        folds = [_fold("2024-06-01", 60)]  # usable 2024-07-31
        adm = walkforward_admissibility(folds, "2024-01-01")
        assert adm.admitted is False
        assert adm.training_cutoff == ""
        assert "before_walkforward_coverage" in adm.rejection_reasons

    def test_realistic_43_fold_window_admits_2024_rejects_pre_coverage(self, tmp_path):
        # a 43-fold-shaped manifest starting 2023-10-02 @21d cadence, lookahead 60
        from datetime import date, timedelta
        start = date(2023, 10, 2)
        retrains = [
            {"cutoff_date": (start + timedelta(days=21 * i)).isoformat(),
             "lookahead_days": 60, "artifact_uri": f"fold{i}.json"}
            for i in range(43)
        ]
        p = tmp_path / "wf.json"
        p.write_text(json.dumps({"retrains": retrains}))
        folds = load_walkforward_folds(p)
        # a real sim date in the 558-date window is admitted
        assert walkforward_admissibility(folds, "2024-06-03").admitted is True
        # a date before the first fold's usable_from (2023-12-01) is rejected
        assert walkforward_admissibility(folds, "2023-11-15").admitted is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
