"""Tests for the walk-forward-sim -> Phase A inputs converter.

Covers the point-in-time correctness the converter exists to guarantee
(Codex feedback on model#64):

1. The PIT fold gate uses BUSINESS-DAY offsets (``BDay``), not a calendar
   ``timedelta`` -- a date that a naive calendar offset would (leakily) admit
   is correctly excluded, and the effective-cutoff / boundary is strict.
2. ``training_cutoff`` is stamped as the selected fold's real ``cutoff_date``
   (never ``"MISSING"``).
3. A date before all walk-forward coverage has no PIT-clean vintage and is
   excluded, never stamped with a future (leaky) model.

Plus an end-to-end build on a synthetic sim DB + manifest proving the
produced score-dir is ADMITTED by the canonical validator (the session-close
``as_of`` stamping sits on the causal boundary and admits).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from pandas.tseries.offsets import BDay

from experiments.ensemble_phase0.build_phase_a_inputs import (
    ALLOWED_SCORE_COLUMNS,
    ScoreColumnNotAllowedError,
    WalkForwardFold,
    build_score_payload,
    load_folds,
    resolve_artifact_digest,
    run_build,
    select_pit_fold,
    validate_score_column,
    LabelContext,
)

CUTOFF = "2025-05-12"
LOOKAHEAD = 60
# Verified via pandas: 2025-05-12 + BDay(60) == 2025-08-04; +60 calendar days
# == 2025-07-11. A date between those two is BDay-ineligible but would be
# calendar-eligible -- the exact leakage the BDay contract prevents.
EFF_BDAY = "2025-08-04"
CAL_PLUS_60 = "2025-07-11"
DISCRIMINATING = "2025-07-20"  # after calendar+60, before BDay eff


def _fold(cutoff: str = CUTOFF, lookahead: int = LOOKAHEAD) -> WalkForwardFold:
    return WalkForwardFold(
        cutoff_date=cutoff,
        lookahead_days=lookahead,
        artifact_uri=f"artifacts/wf/{cutoff}/panel-ltr.json",
        trained_date="2026-06-15",
    )


# ---------------------------------------------------------------------
# 1. BDay admissibility boundary (the model#64 fix)
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
# 2. training_cutoff stamping (real fold cutoff, never MISSING)
# ---------------------------------------------------------------------
def test_training_cutoff_stamped_from_selected_fold():
    fold = _fold()
    labels = LabelContext(
        has_realized_labels_by_date={"2025-09-15": True},
        label_artifact_ref_by_date={"2025-09-15": "sha256:" + "b" * 64 + "@returns.csv"},
        label_observation_end_by_date={"2025-09-15": "2025-11-14"},
    )
    payload = build_score_payload(
        "2025-09-15",
        {"AAA": 0.1, "BBB": -0.2},
        expert_name="xgb",
        fold=fold,
        artifact_fingerprint="sha256:" + "a" * 64,
        artifact_is_real_digest=True,
        artifact_locator="/x/panel-ltr.json",
        decision_ts="2025-09-15T20:00:00+00:00",
        labels=labels,
        score_column="raw_panel",
        source_db_digest="sha256:" + "d" * 64,
        source_db_path="/x/sim.db",
        manifest_path="/x/manifest.json",
    )
    assert payload["training_cutoff"] == CUTOFF
    assert payload["training_cutoff"] != "MISSING"
    assert payload["metadata"]["walkforward_fold"]["effective_train_cutoff_date"] == EFF_BDAY
    # feature/data/score available-time all stamped at the session close.
    assert payload["as_of_date"] == "2025-09-15T20:00:00+00:00"
    assert payload["data_watermark"] == payload["as_of_date"]


# ---------------------------------------------------------------------
# 3. date-before-coverage exclusion
# ---------------------------------------------------------------------
def test_date_before_coverage_is_excluded():
    fold = _fold()  # eff 2025-08-04
    # A date before the earliest fold's effective cutoff has no PIT vintage.
    assert select_pit_fold([fold], "2025-06-01") is None


# ---------------------------------------------------------------------
# score-column SQL guard + artifact-digest fallback
# ---------------------------------------------------------------------
def test_score_column_allowlist_guard():
    for col in ALLOWED_SCORE_COLUMNS:
        assert validate_score_column(col) == col
    with pytest.raises(ScoreColumnNotAllowedError):
        validate_score_column("raw_panel; DROP TABLE score_distribution")


def test_artifact_digest_real_vs_fallback(tmp_path: Path):
    art = tmp_path / "artifacts" / "wf" / CUTOFF / "panel-ltr.json"
    art.parent.mkdir(parents=True)
    art.write_bytes(b'{"model": "content"}')
    fold = _fold()
    fp, locator, is_real = resolve_artifact_digest(fold, tmp_path)
    assert is_real is True
    assert fp.startswith("sha256:") and len(fp) == 71
    # Unresolvable base dir -> deterministic provenance-bound fallback.
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
# End-to-end: synthetic sim DB + manifest -> canonical validator ADMITS
# ---------------------------------------------------------------------
def _make_sim_db(db_path: Path, dates: list[str], tickers: list[str]) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE score_distribution (
               run_id TEXT, date TEXT, ticker TEXT, raw_panel REAL, mu REAL,
               sigma REAL, PRIMARY KEY (run_id, ticker))"""
    )
    conn.execute(
        """CREATE TABLE ticker_forward_returns (
               as_of_date DATE, ticker TEXT, fwd_60d REAL,
               PRIMARY KEY (as_of_date, ticker))"""
    )
    for d in dates:
        for i, t in enumerate(tickers):
            conn.execute(
                "INSERT INTO score_distribution VALUES (?,?,?,?,?,?)",
                (f"legacy-{d}", d, t, 0.1 * (i + 1) - 0.2, None, 0.05),
            )
            conn.execute(
                "INSERT INTO ticker_forward_returns VALUES (?,?,?)",
                (d, t, 0.01 * (i + 1)),
            )
    conn.commit()
    conn.close()


def test_end_to_end_build_is_admitted_by_canonical_validator(tmp_path: Path):
    # Two real NYSE sessions, fully covered by a 3-ticker universe.
    dates = ["2025-09-15", "2025-09-16"]
    tickers = ["AAA", "BBB", "CCC"]
    sim_db = tmp_path / "sim_runs.db"
    _make_sim_db(sim_db, dates, tickers)

    manifest = tmp_path / "wf_manifest.json"
    manifest.write_text(json.dumps({
        "retrains": [
            {"cutoff_date": "2025-05-12", "lookahead_days": 60,
             "artifact_uri": "artifacts/wf/2025-05-12/panel-ltr.json",
             "trained_date": "2026-06-15"},
        ]
    }))
    # Real, readable artifact so the fold resolves a genuine content digest
    # (a fallback provenance-bound digest is now excluded, never written).
    artifact = tmp_path / "artifacts" / "wf" / "2025-05-12" / "panel-ltr.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'{"model": "content"}')

    out = tmp_path / "out"
    result = run_build(
        sim_db=sim_db,
        manifest_file=manifest,
        output_dir=out,
        expert_name="xgb",
        score_column="raw_panel",
        start_date="2025-09-01",
        end_date="2025-09-30",
        artifact_base_dir=tmp_path,
        build_admissibility_ledger=True,
    )

    # Both fully-covered, labelled, PIT-clean dates are admitted.
    assert result.n_dates_written == 2
    assert result.n_dates_excluded_no_pit_fold == 0
    assert result.ledger_admitted == 2
    assert result.ledger_rejected == 0

    # Every written score file carries the real fold cutoff + boundary as_of.
    sf = json.loads((out / "xgb" / "2025-09-15.json").read_text())
    assert sf["training_cutoff"] == "2025-05-12"
    assert sf["as_of_date"] == "2025-09-15T20:00:00+00:00"
    assert sf["has_realized_labels"] is True

    # Shared returns CSV in the runner's expected schema.
    returns = (out / "returns.csv").read_text().splitlines()
    assert returns[0] == "date,ticker,fwd_return"
    assert len(returns) == 1 + len(dates) * len(tickers)


def test_dates_with_unresolvable_artifact_are_excluded_not_stamped_with_fallback(
    tmp_path: Path,
):
    """A fold whose artifact_uri does not resolve to a real file must never
    reach a score file with the provenance-bound surrogate digest (Codex CR
    on model#65: the canonical validator only checks digest syntax, so a
    fallback digest would be silently admitted as if it were real).
    """
    dates = ["2025-09-15", "2025-09-16"]
    tickers = ["AAA", "BBB", "CCC"]
    sim_db = tmp_path / "sim_runs.db"
    _make_sim_db(sim_db, dates, tickers)

    manifest = tmp_path / "wf_manifest.json"
    manifest.write_text(json.dumps({
        "retrains": [
            {"cutoff_date": "2025-05-12", "lookahead_days": 60,
             "artifact_uri": "artifacts/wf/2025-05-12/panel-ltr.json",
             "trained_date": "2026-06-15"},
        ]
    }))
    # No artifact file written under tmp_path -> resolve_artifact_digest
    # falls back to a provenance-bound (non-real) digest for every date.

    out = tmp_path / "out"
    with pytest.raises(ValueError, match="no admissible-vintage dates"):
        run_build(
            sim_db=sim_db,
            manifest_file=manifest,
            output_dir=out,
            expert_name="xgb",
            score_column="raw_panel",
            start_date="2025-09-01",
            end_date="2025-09-30",
            artifact_base_dir=tmp_path,
            build_admissibility_ledger=True,
        )

    # No score file was written for either date.
    assert not (out / "xgb" / "2025-09-15.json").exists()
    assert not (out / "xgb" / "2025-09-16.json").exists()


def test_second_expert_build_does_not_clobber_first_experts_root_artifacts(
    tmp_path: Path,
):
    """Multi-expert output isolation regression.

    Building a SECOND expert into the SAME ``output_dir`` must not destroy the
    first expert's per-expert evidence. The admissibility ledger and its
    calendar evidence are expert-specific; before the fix they were written to
    the shared ``output_dir`` root (``output_dir/admissibility_ledger.json`` /
    ``output_dir/calendar_evidence.json``), so a patchtst build clobbered the
    xgb build's root artifacts. They must now live under ``output_dir/<expert>/``.
    The forward-returns CSV is expert-independent label data and stays shared at
    the root by design.
    """
    dates = ["2025-09-15", "2025-09-16"]
    tickers = ["AAA", "BBB", "CCC"]
    sim_db = tmp_path / "sim_runs.db"
    _make_sim_db(sim_db, dates, tickers)

    manifest = tmp_path / "wf_manifest.json"
    manifest.write_text(json.dumps({
        "retrains": [
            {"cutoff_date": "2025-05-12", "lookahead_days": 60,
             "artifact_uri": "artifacts/wf/2025-05-12/panel-ltr.json",
             "trained_date": "2026-06-15"},
        ]
    }))
    # Real, readable artifact so both experts' folds resolve a genuine
    # content digest (a fallback provenance-bound digest is excluded, never
    # written -- see test_dates_with_unresolvable_artifact_are_excluded_*).
    artifact = tmp_path / "artifacts" / "wf" / "2025-05-12" / "panel-ltr.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'{"model": "content"}')

    out = tmp_path / "out"

    def _build(expert: str):
        return run_build(
            sim_db=sim_db,
            manifest_file=manifest,
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
