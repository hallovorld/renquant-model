"""Tests for walkforward_admissibility (GOAL-4 sim-DB admissibility).

The contract: a walkforward-sim prediction date is admissible iff (1) a
retrain fold with business-day, effective-cutoff-aware safe-label-date
STRICTLY before the date exists (mirroring
``WalkForwardModelLoader.entry_as_of`` via the canonical
``renquant_common.walk_forward_fold_selection`` selector), AND (2) the
record's own observed provenance matches that fold — and the admission
stamps a truthful ``training_cutoff``. This is the leakage-correct
replacement for the live-DB ``created_at`` check when the source is a
walkforward-sim DB (all sim runs share one batch ``created_at``).

Codex review (PR #64) boundary coverage added here:
  * Friday/weekend prediction dates, proving BUSINESS-day (not calendar-day)
    lookahead arithmetic.
  * ``effective_train_cutoff_date`` entries that differ from ``cutoff_date``,
    proving the loader's preference is mirrored.
  * A record whose observed provenance does not match the eligibility-selected
    fold is REJECTED, not admitted (the provenance-verification gap).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "experiments" / "ensemble_phase0"))

from walkforward_admissibility import (  # noqa: E402
    ObservedFoldProvenance,
    WalkforwardFold,
    load_walkforward_folds,
    select_walkforward_fold,
    walkforward_admissibility,
)


def _fold(
    cutoff: str,
    lookahead: int = 60,
    uri: str = "",
    effective: str | None = None,
    artifact_sha256: str | None = None,
) -> WalkforwardFold:
    return WalkforwardFold(
        cutoff_date=cutoff,
        lookahead_days=lookahead,
        artifact_uri=uri,
        effective_train_cutoff_date=effective,
        artifact_sha256=artifact_sha256,
    )


class TestUsableFrom:
    def test_usable_from_adds_lookahead(self):
        f = _fold("2023-10-02", 60)
        assert f.usable_from.isoformat() == "2023-12-25"  # 60 BUSINESS days

    def test_usable_from_is_business_day_not_calendar_day(self):
        # 2023-12-01 is a Friday. +1 business day = Monday 2023-12-04, NOT
        # 2023-12-02 (Saturday) -- the calendar-day answer the PR's first
        # cut computed via `cutoff_date + datetime.timedelta(lookahead_days)`.
        f = _fold("2023-12-01", 1)
        assert pd.Timestamp("2023-12-01").day_name() == "Friday"
        assert f.usable_from.isoformat() == "2023-12-04"
        calendar_day_wrong_answer = "2023-12-02"
        assert f.usable_from.isoformat() != calendar_day_wrong_answer

    def test_usable_from_prefers_effective_train_cutoff_date(self):
        # effective_train_cutoff_date (2023-09-01) pre-embargoes labels
        # before cutoff_date (2023-12-01); usable_from must be measured from
        # the EFFECTIVE date.
        f = _fold("2023-12-01", 1, effective="2023-09-01")
        assert f.usable_from.isoformat() == "2023-09-04"  # Fri + 1 BDay


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

    def test_parses_effective_train_cutoff_date_and_artifact_sha256(self, tmp_path):
        m = {"retrains": [
            {
                "cutoff_date": "2024-01-01",
                "lookahead_days": 60,
                "artifact_uri": "fold.json",
                "effective_train_cutoff_date": "2023-11-01",
                "artifact_sha256": "sha256:" + "a" * 64,
            },
        ]}
        p = tmp_path / "m.json"
        p.write_text(json.dumps(m))
        folds = load_walkforward_folds(p)
        assert folds[0].effective_train_cutoff_date == "2023-11-01"
        assert folds[0].artifact_sha256 == "sha256:" + "a" * 64

    def test_missing_effective_cutoff_and_digest_default_to_none(self, tmp_path):
        m = {"retrains": [{"cutoff_date": "2024-01-01", "lookahead_days": 60}]}
        p = tmp_path / "m.json"
        p.write_text(json.dumps(m))
        folds = load_walkforward_folds(p)
        assert folds[0].effective_train_cutoff_date is None
        assert folds[0].artifact_sha256 is None


class TestFoldSelection:
    def setup_method(self):
        self.folds = [
            _fold("2023-10-02", 60, "f1"),
            _fold("2023-10-23", 60, "f2"),
            _fold("2024-01-15", 60, "f3"),
        ]

    def test_picks_latest_usable_fold(self):
        # f3's usable_from (2024-01-15 + 60 BDay = 2024-04-08) has passed by
        # 2024-05-01 -> latest cutoff wins
        f = select_walkforward_fold(self.folds, "2024-05-01")
        assert f.cutoff_date == "2024-01-15"

    def test_strict_before_boundary_excludes_equal_date(self):
        # usable_from of f1 (60 BDay from 2023-10-02) is 2023-12-25; a
        # prediction exactly on it is NOT covered (strict <, mirrors
        # model_as_of).
        boundary = self.folds[0].usable_from.isoformat()
        assert boundary == "2023-12-25"
        assert select_walkforward_fold([self.folds[0]], boundary) is None
        assert select_walkforward_fold([self.folds[0]], "2023-12-26").cutoff_date == "2023-10-02"

    def test_before_coverage_returns_none(self):
        assert select_walkforward_fold(self.folds, "2023-01-01") is None

    def test_middle_date_picks_correct_vintage(self):
        # f1 usable 2023-12-25 (eligible), f2 usable 2024-01-15 (eligible),
        # f3 usable 2024-04-08 (NOT yet eligible) -> latest eligible cutoff
        # is f2.
        f = select_walkforward_fold(self.folds, "2024-02-01")
        assert f.cutoff_date == "2023-10-23"

    def test_weekend_prediction_date_around_fold_boundary(self):
        # A Friday cutoff with a short lookahead: prediction dates that fall
        # on the intervening Saturday/Sunday must not be spuriously admitted
        # by calendar-day drift.
        folds = [_fold("2023-12-01", 1, "friday_fold")]  # usable 2023-12-04 (Mon)
        assert select_walkforward_fold(folds, "2023-12-02") is None  # Saturday
        assert select_walkforward_fold(folds, "2023-12-03") is None  # Sunday
        assert select_walkforward_fold(folds, "2023-12-04") is None  # exactly usable_from (strict <)
        assert select_walkforward_fold(folds, "2023-12-05").cutoff_date == "2023-12-01"

    def test_effective_train_cutoff_date_entry_selected_correctly(self):
        # A fold whose effective_train_cutoff_date differs from cutoff_date
        # must be selected/rejected based on the EFFECTIVE date, not
        # cutoff_date -- proving the loader's preference end-to-end.
        folds = [
            _fold("2023-06-01", 0),
            _fold("2023-09-01", 0, effective="2023-07-01"),
        ]
        # 2023-08-15 is after fold[0]'s cutoff (06-01, no lookahead) and after
        # fold[1]'s EFFECTIVE cutoff (07-01) -- fold[1] (latest cutoff_date,
        # 09-01) should be selected, proving admission came via the
        # effective_train_cutoff_date, since a plain cutoff_date-only
        # comparison would still place 09-01 in the future relative to
        # 2023-08-15 and wrongly exclude it.
        chosen = select_walkforward_fold(folds, "2023-08-15")
        assert chosen.cutoff_date == "2023-09-01"


class TestAdmissibility:
    def test_admits_and_stamps_truthful_training_cutoff(self):
        folds = [_fold("2023-12-01", 60, "art.pt")]  # usable ~2024-02-23 (BDay)
        usable = folds[0].usable_from.isoformat()
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(training_cutoff="2023-12-01"),
        )
        assert adm.admitted is True
        assert adm.training_cutoff == "2023-12-01"  # the fold's cutoff, NOT "MISSING"
        assert adm.feature_data_cutoff == "2024-06-15"  # inference as-of = the date
        assert adm.fold_artifact_uri == "art.pt"
        assert adm.rejection_reasons == ()
        assert usable < "2024-06-15"  # sanity: date really is covered

    def test_rejects_before_coverage_with_reason(self):
        folds = [_fold("2024-06-01", 60)]
        adm = walkforward_admissibility(
            folds, "2024-01-01",
            observed=ObservedFoldProvenance(training_cutoff="2024-06-01"),
        )
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
        # a real sim date in the 558-date window is admitted, with matching
        # observed provenance
        chosen = select_walkforward_fold(folds, "2024-06-03")
        adm = walkforward_admissibility(
            folds, "2024-06-03",
            observed=ObservedFoldProvenance(training_cutoff=chosen.cutoff_date),
        )
        assert adm.admitted is True
        # a date before the first fold's usable_from is rejected
        assert walkforward_admissibility(
            folds, "2023-10-15",
            observed=ObservedFoldProvenance(training_cutoff="2023-10-02"),
        ).admitted is False

    # ── Provenance verification (Codex review gap) ──────────────────────

    def test_rejects_when_observed_provenance_missing_entirely(self):
        # No ObservedFoldProvenance at all -- coverage alone must NOT admit.
        folds = [_fold("2023-12-01", 60, "art.pt")]
        adm = walkforward_admissibility(folds, "2024-06-15", observed=None)
        assert adm.admitted is False
        assert "missing_observed_provenance" in adm.rejection_reasons

    def test_rejects_when_observed_training_cutoff_missing(self):
        folds = [_fold("2023-12-01", 60, "art.pt")]
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(training_cutoff=None),
        )
        assert adm.admitted is False
        assert "missing_observed_training_cutoff" in adm.rejection_reasons

    def test_rejects_when_observed_training_cutoff_is_a_different_fold(self):
        # The eligibility check independently selects the fold with
        # cutoff_date=2023-12-01, but the record CLAIMS a different vintage
        # (2023-06-01) actually scored it -- a wrong-vintage score must be
        # rejected, not admitted just because SOME fold covers the date.
        folds = [
            _fold("2023-06-01", 60, "old.json"),
            _fold("2023-12-01", 60, "new.json"),
        ]
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(training_cutoff="2023-06-01"),
        )
        assert adm.admitted is False
        assert any("does not match selected fold" in r for r in adm.rejection_reasons)

    def test_admits_when_observed_training_cutoff_matches_effective_cutoff(self):
        # When the selected fold declares effective_train_cutoff_date, the
        # OBSERVED provenance is expected to match THAT (the true feature
        # cutoff), not the plain cutoff_date.
        folds = [_fold("2023-12-01", 0, "art.json", effective="2023-09-01")]
        adm = walkforward_admissibility(
            folds, "2023-10-01",
            observed=ObservedFoldProvenance(training_cutoff="2023-09-01"),
        )
        assert adm.admitted is True

    def test_rejects_when_artifact_sha256_stamped_but_observed_missing(self):
        folds = [
            _fold("2023-12-01", 60, "art.json", artifact_sha256="sha256:" + "a" * 64),
        ]
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(
                training_cutoff="2023-12-01", artifact_sha256=None,
            ),
        )
        assert adm.admitted is False
        assert any("missing_observed_artifact_sha256" in r for r in adm.rejection_reasons)

    def test_rejects_when_artifact_sha256_mismatches(self):
        folds = [
            _fold("2023-12-01", 60, "art.json", artifact_sha256="sha256:" + "a" * 64),
        ]
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(
                training_cutoff="2023-12-01", artifact_sha256="sha256:" + "b" * 64,
            ),
        )
        assert adm.admitted is False
        assert any(
            "artifact_sha256" in r and "!=" in r for r in adm.rejection_reasons
        )

    def test_admits_when_artifact_sha256_matches(self):
        digest = "sha256:" + "a" * 64
        folds = [_fold("2023-12-01", 60, "art.json", artifact_sha256=digest)]
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(
                training_cutoff="2023-12-01", artifact_sha256=digest,
            ),
        )
        assert adm.admitted is True

    def test_no_digest_stamped_on_fold_does_not_require_observed_digest(self):
        # Older manifests (no artifact_sha256 stamped anywhere) must still be
        # admissible on training_cutoff match alone -- the digest check is
        # additive verification, not a hard requirement when the manifest
        # itself carries no digest to check against.
        folds = [_fold("2023-12-01", 60, "art.json")]  # no artifact_sha256
        adm = walkforward_admissibility(
            folds, "2024-06-15",
            observed=ObservedFoldProvenance(training_cutoff="2023-12-01"),
        )
        assert adm.admitted is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
