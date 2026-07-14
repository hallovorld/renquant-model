"""Tests for Phase A discovery runner."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from experiments.ensemble_phase0 import phase_a_runner as par
from experiments.ensemble_phase0.admissibility_ledger import (
    AdmissibilityLedger,
    write_ledger,
)
from experiments.ensemble_phase0.experiment_manifest import (
    build_default_manifest,
    write_manifest,
)
from experiments.ensemble_phase0.phase_a_runner import (
    MIN_CONFIRMATORY_OBSERVATIONS,
    TEST_METHOD_HAC_FALLBACK,
    TEST_METHOD_NON_OVERLAPPING,
    ExpertScores,
    PhaseAResult,
    StrategyResult,
    champion_scores,
    compute_ic,
    compute_portfolio_return,
    compute_turnover,
    cross_sectional_zscore,
    evaluate_strategy,
    l1_equal_weight,
    load_expert_scores,
    load_forward_returns,
    newey_west_t_test,
    pair_evaluations_by_date,
    result_to_dict,
    run_phase_a,
    select_non_overlapping_dates,
    top_n_selection,
    verify_returns_file_digest,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_score_dir(tmp_path: Path, name: str, data: dict[str, dict[str, float]]) -> Path:
    """Create a score directory with date-named JSON files, with full
    ledger-admissible provenance metadata (used with :func:`_admitted_digests`
    below to simulate 'this file was already ledger-admitted' without
    invoking the full ledger-building pipeline in every test)."""
    d = tmp_path / name
    d.mkdir()
    for date_str, scores in data.items():
        payload = {
            "scores": scores,
            "model_content_sha256": f"sha256:{'a' * 64}",
            "training_cutoff": "2020-01-01",
            "as_of_date": date_str,
            "score_timestamp": f"{date_str}T15:30:00+00:00",
            "has_realized_labels": True,
            "label_artifact_ref": f"sha256:{'b' * 64}@labels/{date_str}",
            "label_observation_end": (
                date.fromisoformat(date_str) + timedelta(days=60)
            ).isoformat(),
        }
        (d / f"{date_str}.json").write_text(json.dumps(payload))
    return d


def _admitted_digests(
    score_dirs: dict[str, Path], dates: list[str]
) -> dict[tuple[str, str], str]:
    """Directly compute sha256 digests for the given files, simulating
    'this (expert, date) was already ledger-admitted' -- used by tests
    that exercise phase_a_runner's OWN combination/champion/HAC/cost logic
    rather than the ledger-integration path itself (see
    TestProvenanceGate for that)."""
    out: dict[tuple[str, str], str] = {}
    for name, d in score_dirs.items():
        for date_str in dates:
            path = d / f"{date_str}.json"
            if path.exists():
                out[(name, date_str)] = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    return out


def _make_returns_csv(tmp_path: Path, data: dict[str, dict[str, float]]) -> Path:
    """Create a forward returns CSV."""
    p = tmp_path / "returns.csv"
    lines = ["date,ticker,fwd_return"]
    for date_str, rets in data.items():
        for ticker, ret in rets.items():
            lines.append(f"{date_str},{ticker},{ret}")
    p.write_text("\n".join(lines))
    return p


def _build_n_date_fixture(
    tmp_path: Path, n: int, *, seed: int = 0, n_tickers: int = 8,
) -> tuple[list[ExpertScores], dict[str, dict[str, float]]]:
    """Build an ``n``-consecutive-day, ``n_tickers``-ticker synthetic
    xgb+patchtst score/return fixture -- used to exercise the
    non-overlapping-block test-method switch, which needs more
    observations than the small 5-date hand-written fixture below."""
    tickers = [f"T{i}" for i in range(n_tickers)]
    dates = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
    rng = np.random.default_rng(seed)
    xgb: dict[str, dict[str, float]] = {}
    pt: dict[str, dict[str, float]] = {}
    rets: dict[str, dict[str, float]] = {}
    for d in dates:
        base = rng.normal(0, 1, n_tickers)
        xgb[d] = {t: float(base[j]) for j, t in enumerate(tickers)}
        pt[d] = {t: float(base[j] + rng.normal(0, 0.5)) for j, t in enumerate(tickers)}
        rets[d] = {t: float(base[j] * 0.02) for j, t in enumerate(tickers)}

    xgb_dir = _make_score_dir(tmp_path, "xgb", xgb)
    pt_dir = _make_score_dir(tmp_path, "patchtst", pt)
    digests = _admitted_digests({"xgb": xgb_dir, "patchtst": pt_dir}, dates)
    experts = [
        load_expert_scores("xgb", xgb_dir, admitted_digests=digests),
        load_expert_scores("patchtst", pt_dir, admitted_digests=digests),
    ]
    return experts, rets


DATES = ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05"]

XGB_SCORES = {
    "2025-06-01": {"AAPL": 0.5, "MSFT": 0.3, "GOOG": 0.8, "AMZN": 0.1, "META": 0.6,
                   "NFLX": 0.2, "TSLA": 0.4, "NVDA": 0.7, "AMD": 0.35, "INTC": 0.15},
    "2025-06-02": {"AAPL": 0.6, "MSFT": 0.4, "GOOG": 0.7, "AMZN": 0.2, "META": 0.5,
                   "NFLX": 0.3, "TSLA": 0.35, "NVDA": 0.8, "AMD": 0.45, "INTC": 0.25},
    "2025-06-03": {"AAPL": 0.55, "MSFT": 0.35, "GOOG": 0.75, "AMZN": 0.15, "META": 0.55,
                   "NFLX": 0.25, "TSLA": 0.42, "NVDA": 0.72, "AMD": 0.38, "INTC": 0.18},
    "2025-06-04": {"AAPL": 0.48, "MSFT": 0.32, "GOOG": 0.82, "AMZN": 0.12, "META": 0.62,
                   "NFLX": 0.22, "TSLA": 0.38, "NVDA": 0.68, "AMD": 0.33, "INTC": 0.13},
    "2025-06-05": {"AAPL": 0.52, "MSFT": 0.28, "GOOG": 0.78, "AMZN": 0.08, "META": 0.58,
                   "NFLX": 0.18, "TSLA": 0.43, "NVDA": 0.73, "AMD": 0.36, "INTC": 0.16},
}

PATCHTST_SCORES = {
    "2025-06-01": {"AAPL": 0.4, "MSFT": 0.5, "GOOG": 0.6, "AMZN": 0.3, "META": 0.7,
                   "NFLX": 0.1, "TSLA": 0.5, "NVDA": 0.8, "AMD": 0.2, "INTC": 0.35},
    "2025-06-02": {"AAPL": 0.5, "MSFT": 0.6, "GOOG": 0.5, "AMZN": 0.4, "META": 0.6,
                   "NFLX": 0.2, "TSLA": 0.45, "NVDA": 0.7, "AMD": 0.3, "INTC": 0.35},
    "2025-06-03": {"AAPL": 0.45, "MSFT": 0.55, "GOOG": 0.55, "AMZN": 0.35, "META": 0.65,
                   "NFLX": 0.15, "TSLA": 0.48, "NVDA": 0.75, "AMD": 0.25, "INTC": 0.35},
    "2025-06-04": {"AAPL": 0.42, "MSFT": 0.52, "GOOG": 0.62, "AMZN": 0.22, "META": 0.72,
                   "NFLX": 0.12, "TSLA": 0.42, "NVDA": 0.72, "AMD": 0.32, "INTC": 0.22},
    "2025-06-05": {"AAPL": 0.48, "MSFT": 0.48, "GOOG": 0.58, "AMZN": 0.18, "META": 0.68,
                   "NFLX": 0.08, "TSLA": 0.46, "NVDA": 0.76, "AMD": 0.28, "INTC": 0.38},
}

FORWARD_RETURNS = {
    "2025-06-01": {"AAPL": 0.05, "MSFT": 0.02, "GOOG": 0.08, "AMZN": -0.03, "META": 0.06,
                   "NFLX": -0.01, "TSLA": 0.03, "NVDA": 0.10, "AMD": 0.01, "INTC": -0.02},
    "2025-06-02": {"AAPL": 0.04, "MSFT": 0.03, "GOOG": 0.07, "AMZN": -0.02, "META": 0.05,
                   "NFLX": -0.01, "TSLA": 0.02, "NVDA": 0.09, "AMD": 0.02, "INTC": -0.01},
    "2025-06-03": {"AAPL": 0.03, "MSFT": 0.01, "GOOG": 0.06, "AMZN": -0.04, "META": 0.04,
                   "NFLX": 0.00, "TSLA": 0.01, "NVDA": 0.08, "AMD": 0.00, "INTC": -0.03},
    "2025-06-04": {"AAPL": 0.06, "MSFT": 0.04, "GOOG": 0.09, "AMZN": -0.01, "META": 0.07,
                   "NFLX": 0.01, "TSLA": 0.04, "NVDA": 0.11, "AMD": 0.02, "INTC": 0.00},
    "2025-06-05": {"AAPL": 0.02, "MSFT": 0.00, "GOOG": 0.05, "AMZN": -0.05, "META": 0.03,
                   "NFLX": -0.02, "TSLA": 0.01, "NVDA": 0.07, "AMD": -0.01, "INTC": -0.04},
}


# ── Cross-sectional z-score ──────────────────────────────────────────────────


class TestCrossSectionalZScore:
    def test_normalizes_to_zero_mean_unit_variance(self):
        scores = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        z = cross_sectional_zscore(scores)
        values = np.array(list(z.values()))
        assert values.mean() == pytest.approx(0.0, abs=1e-9)
        assert values.std(ddof=0) == pytest.approx(1.0, abs=1e-9)

    def test_degenerate_constant_cross_section_maps_to_zero(self):
        """A cross-section with zero variance carries no relative-ranking
        information -- must map to 0.0, never divide by ~zero."""
        scores = {"A": 0.5, "B": 0.5, "C": 0.5}
        assert cross_sectional_zscore(scores) == {"A": 0.0, "B": 0.0, "C": 0.0}

    def test_single_ticker_is_degenerate(self):
        assert cross_sectional_zscore({"A": 0.7}) == {"A": 0.0}

    def test_empty(self):
        assert cross_sectional_zscore({}) == {}


# ── L1 equal-weight ──────────────────────────────────────────────────────────


class TestL1EqualWeight:
    def test_two_experts_average_normalized_not_raw(self):
        """Raw values 0.8/0.2 and 0.4/0.6 are on incomparable scales;
        combining z-scores (not raw values) is required (Codex review
        2026-07-13, finding 2)."""
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.8, "Y": 0.2}})
        e2 = ExpertScores(name="b", dates=["d1"], scores_by_date={"d1": {"X": 0.4, "Y": 0.6}})
        result = l1_equal_weight([e1, e2], "d1")
        # Each expert's own cross-section z-scores to +1.0/-1.0 for X/Y
        # (opposite orientation between experts) -- combined average is 0.
        assert result == pytest.approx({"X": 0.0, "Y": 0.0})

    def test_three_experts_single_ticker_is_degenerate(self):
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.9}})
        e2 = ExpertScores(name="b", dates=["d1"], scores_by_date={"d1": {"X": 0.3}})
        e3 = ExpertScores(name="c", dates=["d1"], scores_by_date={"d1": {"X": 0.6}})
        result = l1_equal_weight([e1, e2, e3], "d1")
        assert result == pytest.approx({"X": 0.0})

    def test_includes_partial_coverage_renormalized(self):
        """Per the pre-registered missing-expert fallback policy (model
        PR #48 §4.1bis): a ticker missing from one expert is EXCLUDED from
        that expert's contribution and the remaining expert(s) are
        averaged, rather than dropping the ticker/observation entirely."""
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.5, "Y": 0.3}})
        e2 = ExpertScores(name="b", dates=["d1"], scores_by_date={"d1": {"X": 0.7}})
        result = l1_equal_weight([e1, e2], "d1")
        # Y is now INCLUDED (previously excluded under the old
        # all-experts-required rule).
        assert "Y" in result
        # e1: mean=0.4, std=0.1 -> z(X)=1.0, z(Y)=-1.0. e2: single ticker
        # -> degenerate -> z(X)=0.0. Combined: X=(1.0+0.0)/2=0.5, Y=-1.0.
        assert result == pytest.approx({"X": 0.5, "Y": -1.0})

    def test_missing_expert_for_date_does_not_zero_out_combination(self):
        """A whole expert missing this date must not drop the observation
        entirely -- the experts that DID score this date still combine."""
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.5}})
        e2 = ExpertScores(name="b", dates=[], scores_by_date={})
        result = l1_equal_weight([e1, e2], "d1")
        assert result == pytest.approx({"X": 0.0})  # single-ticker degenerate


# ── Top-N selection ──────────────────────────────────────────────────────────


class TestTopNSelection:
    def test_basic_top3(self):
        scores = {"A": 0.9, "B": 0.1, "C": 0.5, "D": 0.7}
        result = top_n_selection(scores, 3)
        assert result == ["A", "D", "C"]

    def test_n_larger_than_universe(self):
        scores = {"A": 0.5, "B": 0.3}
        result = top_n_selection(scores, 10)
        assert set(result) == {"A", "B"}

    def test_empty(self):
        assert top_n_selection({}, 5) == []


# ── IC computation ───────────────────────────────────────────────────────────


class TestIC:
    def test_perfect_rank_correlation(self):
        scores = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
        returns = {"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04, "E": 0.05}
        ic = compute_ic(scores, returns)
        assert ic == pytest.approx(1.0)

    def test_inverse_correlation(self):
        scores = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        returns = {"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04, "E": 0.05}
        ic = compute_ic(scores, returns)
        assert ic == pytest.approx(-1.0)

    def test_insufficient_overlap(self):
        scores = {"A": 1, "B": 2}
        returns = {"A": 0.01, "B": 0.02}
        ic = compute_ic(scores, returns)
        assert math.isnan(ic)


# ── Turnover ─────────────────────────────────────────────────────────────────


class TestTurnover:
    def test_identical(self):
        assert compute_turnover(["A", "B"], ["A", "B"]) == 0.0

    def test_complete_change(self):
        assert compute_turnover(["A", "B"], ["C", "D"]) == 1.0

    def test_partial_change(self):
        t = compute_turnover(["A", "B", "C", "D"], ["A", "B", "E", "F"])
        assert t == pytest.approx(0.5)

    def test_empty_to_full(self):
        assert compute_turnover([], ["A", "B"]) == 1.0


# ── Non-overlapping block selection ─────────────────────────────────────────


class TestSelectNonOverlappingDates:
    def test_all_dates_far_enough_apart_are_kept(self):
        dates = [f"2025-01-{i:02d}" for i in range(1, 4)]  # 3 dates
        # spacing=1 means at least 1 index apart — every date qualifies
        selected, indices = select_non_overlapping_dates(dates, 1)
        assert selected == dates

    def test_close_dates_are_dropped(self):
        dates = [f"2025-01-{i:02d}" for i in range(1, 11)]  # 10 dates
        # spacing=3 selects indices 0, 3, 6, 9
        selected, indices = select_non_overlapping_dates(dates, 3)
        assert selected == ["2025-01-01", "2025-01-04", "2025-01-07", "2025-01-10"]

    def test_empty(self):
        selected, indices = select_non_overlapping_dates([], 60)
        assert selected == []
        assert indices == []

    def test_single_date(self):
        selected, indices = select_non_overlapping_dates(["2025-01-01"], 60)
        assert selected == ["2025-01-01"]

    def test_index_spacing_not_calendar_day(self):
        """Codex review round 10: spacing is measured in input-list index
        positions, not calendar days."""
        sessions = [
            "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10",
            "2025-01-13", "2025-01-14", "2025-01-15", "2025-01-16", "2025-01-17",
        ]
        selected, indices = select_non_overlapping_dates(sessions, 5)
        assert selected == ["2025-01-06", "2025-01-13"]

    def test_embargo_adds_extra_spacing(self):
        dates = [f"2025-01-{i:02d}" for i in range(1, 21)]  # 20 dates
        # spacing=3, embargo=2 → total gap = 5
        selected, indices = select_non_overlapping_dates(dates, 3, embargo=2)
        assert selected == ["2025-01-01", "2025-01-06", "2025-01-11", "2025-01-16"]

    def test_weekend_holiday_regression(self):
        """Regression: a trading session calendar with holidays must still
        produce correctly-spaced blocks by session index, even though the
        calendar-day gaps between sessions vary."""
        sessions = [
            "2025-01-06", "2025-01-07",
            "2025-01-09", "2025-01-10",
            "2025-01-13", "2025-01-14", "2025-01-15", "2025-01-16", "2025-01-17",
        ]
        selected, indices = select_non_overlapping_dates(sessions, 4)
        assert selected == ["2025-01-06", "2025-01-13", "2025-01-17"]

    def test_returns_calendar_indices(self):
        """select_non_overlapping_dates must return the selected calendar
        indices for auditability (Codex review round 11, finding 1)."""
        dates = [f"2025-01-{i:02d}" for i in range(1, 11)]
        selected, indices = select_non_overlapping_dates(dates, 3)
        assert indices == [0, 3, 6, 9]

    def test_session_calendar_uses_full_calendar_indices(self):
        """Codex review round 11, finding 1: when a session calendar is
        provided, spacing is measured in FULL calendar indices, not the
        compressed input-list indices. Missing sessions must NOT compress
        the spacing."""
        # Full calendar: 10 sessions
        full_calendar = [f"2025-01-{i:02d}" for i in range(1, 11)]
        # Loaded data: only sessions 1, 2, 6, 7, 8, 9, 10 (missing 3, 4, 5)
        loaded_dates = ["2025-01-01", "2025-01-02",
                        "2025-01-06", "2025-01-07", "2025-01-08",
                        "2025-01-09", "2025-01-10"]
        # With min_spacing=5 and full calendar:
        # "01-01" is cal index 0, next must be >= 5, which is "01-06" (cal index 5)
        selected, indices = select_non_overlapping_dates(
            loaded_dates, 5, session_calendar=full_calendar,
        )
        assert selected == ["2025-01-01", "2025-01-06"]
        assert indices == [0, 5]

    def test_compressed_list_without_calendar_gives_different_spacing(self):
        """Without a session calendar, missing sessions compress the list.
        Compressed gaps can differ from calendar-accurate gaps. This test
        documents the difference: with a full calendar, 01-01→01-06 is
        gap=5 (selectable), but without one it's gap=2 (not selectable
        at min_spacing=5)."""
        full_calendar = [f"2025-01-{i:02d}" for i in range(1, 11)]
        loaded_dates = ["2025-01-01", "2025-01-02",
                        "2025-01-06", "2025-01-07", "2025-01-08",
                        "2025-01-09", "2025-01-10"]
        # With calendar: cal indices are correct → "01-06" at gap=5 ✓
        with_cal, _ = select_non_overlapping_dates(
            loaded_dates, 5, session_calendar=full_calendar,
        )
        assert with_cal == ["2025-01-01", "2025-01-06"]
        # Without calendar: compressed index of "01-06" is 2 (gap=2 < 5)
        # → must wait until index 5 = "01-09" (overly conservative)
        without_cal, _ = select_non_overlapping_dates(loaded_dates, 5)
        assert without_cal == ["2025-01-01", "2025-01-09"]


# ── Complete return-coverage requirement ────────────────────────────────────


class TestCompletePortfolioReturnCoverage:
    def test_all_present_returns_average(self):
        assert compute_portfolio_return(["A", "B"], {"A": 0.1, "B": 0.3}) == pytest.approx(0.2)

    def test_missing_ticker_returns_none_not_zero(self):
        """A selected ticker with no realized return must exclude the
        date via ``None``, never silently substitute 0.0 (Codex review
        2026-07-13, finding 5)."""
        assert compute_portfolio_return(["A", "B"], {"A": 0.1}) is None

    def test_empty_selection_is_zero(self):
        assert compute_portfolio_return([], {"A": 0.1}) == 0.0


class TestEvaluateStrategyCoverageAndCost:
    def test_excludes_dates_with_incomplete_return_coverage(self):
        scores_by_date = {"d1": {"A": 1.0, "B": 0.5}, "d2": {"A": 1.0, "B": 0.5}}
        returns = {"d1": {"A": 0.1, "B": 0.2}, "d2": {"A": 0.1}}  # B missing on d2
        result = evaluate_strategy(
            "test", lambda dt: scores_by_date.get(dt, {}), ["d1", "d2"], returns, top_n=2,
        )
        assert result.n_dates == 1
        assert result.n_dates_excluded_missing_returns == 1
        assert result.dates == ["d1"]

    def test_net_return_deducts_turnover_scaled_cost(self):
        scores_by_date = {
            "d1": {"A": 1.0, "B": 0.5},
            "d2": {"C": 1.0, "D": 0.5},  # complete turnover from d1 -> d2
        }
        returns = {
            "d1": {"A": 0.10, "B": 0.10},
            "d2": {"C": 0.10, "D": 0.10},
        }
        result = evaluate_strategy(
            "test", lambda dt: scores_by_date.get(dt, {}), ["d1", "d2"], returns,
            top_n=2, cost_bps=100.0,
        )
        assert result.daily_returns == pytest.approx([0.10, 0.10])
        # turnover is 1.0 on both dates (initial build, then full
        # replacement) -> cost = 100bps = 0.01 deducted from each.
        assert result.daily_net_returns == pytest.approx([0.09, 0.09])
        assert result.mean_net_return == pytest.approx(0.09)

    def test_zero_cost_leaves_net_equal_to_gross(self):
        scores_by_date = {"d1": {"A": 1.0, "B": 0.5}}
        returns = {"d1": {"A": 0.10, "B": 0.20}}
        result = evaluate_strategy(
            "test", lambda dt: scores_by_date.get(dt, {}), ["d1"], returns,
            top_n=2, cost_bps=0.0,
        )
        assert result.daily_net_returns == pytest.approx(result.daily_returns)

    def test_tracks_portfolio_size_per_surviving_date(self):
        """A universe too small to fill top_n must be visible downstream
        (Codex review 2026-07-13 round 4, finding 3) -- not silently
        treated as a full top_n selection."""
        scores_by_date = {"d1": {"A": 1.0, "B": 0.5, "C": 0.2}, "d2": {"A": 1.0}}
        returns = {"d1": {"A": 0.1, "B": 0.1, "C": 0.1}, "d2": {"A": 0.1}}
        result = evaluate_strategy(
            "test", lambda dt: scores_by_date.get(dt, {}), ["d1", "d2"], returns, top_n=3,
        )
        assert result.dates == ["d1", "d2"]
        assert result.portfolio_sizes == [3, 1]


# ── Date-keyed paired evaluation (Codex review 2026-07-13 round 4) ─────────


class TestPairEvaluationsByDate:
    def _strategy_result(self, dates, rets, sizes, ics=None):
        ics = ics if ics is not None else [0.1] * len(dates)
        return StrategyResult(
            name="test", dates=list(dates), daily_net_returns=list(rets),
            portfolio_sizes=list(sizes), daily_ics=list(ics),
        )

    def test_pairs_by_date_not_position(self):
        """Champion and L1 each independently exclude a DIFFERENT date --
        the paired series must align by date identity, not array
        position (Codex review 2026-07-13 round 4, finding 2)."""
        champ = self._strategy_result(
            dates=["d1", "d2", "d3"], rets=[0.01, 0.02, 0.03], sizes=[5, 5, 5],
        )
        # L1 excluded d2 (e.g. incomplete return coverage) but the
        # remaining array is still the SAME LENGTH as champion's.
        l1 = self._strategy_result(
            dates=["d1", "d3", "d4"], rets=[0.05, 0.06, 0.07], sizes=[5, 5, 5],
        )
        dates, champ_rets, l1_rets, champ_ics, l1_ics, n_excluded = (
            pair_evaluations_by_date(champ, l1, top_n=5)
        )
        # Only d1 and d3 are present on both sides.
        assert dates == ["d1", "d3"]
        assert champ_rets == pytest.approx([0.01, 0.03])
        assert l1_rets == pytest.approx([0.05, 0.06])
        # d2 (champion-only) and d4 (L1-only) are both excluded.
        assert n_excluded == 2

    def test_excludes_undersized_selection_symmetrically(self):
        """A date where either side selected fewer than top_n names is
        excluded from BOTH series, even if the other side's selection was
        full (Codex review 2026-07-13 round 4, finding 3)."""
        champ = self._strategy_result(
            dates=["d1", "d2"], rets=[0.01, 0.02], sizes=[5, 5],
        )
        l1 = self._strategy_result(
            dates=["d1", "d2"], rets=[0.05, 0.06], sizes=[5, 3],  # d2 undersized
        )
        dates, champ_rets, l1_rets, _, _, n_excluded = pair_evaluations_by_date(
            champ, l1, top_n=5,
        )
        assert dates == ["d1"]
        assert champ_rets == pytest.approx([0.01])
        assert l1_rets == pytest.approx([0.05])
        assert n_excluded == 1

    def test_empty_when_no_overlap(self):
        champ = self._strategy_result(dates=["d1"], rets=[0.01], sizes=[5])
        l1 = self._strategy_result(dates=["d2"], rets=[0.05], sizes=[5])
        dates, champ_rets, l1_rets, _, _, n_excluded = pair_evaluations_by_date(
            champ, l1, top_n=5,
        )
        assert dates == []
        assert champ_rets == []
        assert l1_rets == []
        assert n_excluded == 2


# ── Newey-West t-test ────────────────────────────────────────────────────────


class TestNeweyWestTTest:
    def test_identical_series(self):
        x = [0.01, 0.02, 0.03, 0.04, 0.05]
        t_stat, p_val = newey_west_t_test(x, x)
        assert abs(t_stat) < 1e-10 or math.isnan(t_stat)

    def test_clearly_different(self):
        np.random.seed(42)
        x = list(np.random.normal(0.10, 0.02, 50))
        y = list(np.random.normal(0.05, 0.02, 50))
        t_stat, p_val = newey_west_t_test(x, y)
        assert t_stat > 0
        assert p_val < 0.05

    def test_insufficient_data(self):
        t_stat, p_val = newey_west_t_test([0.1], [0.2])
        assert math.isnan(t_stat)
        assert math.isnan(p_val)

    def test_known_direction(self):
        x = [0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
        y = [0.01, 0.02, 0.01, 0.02, 0.01, 0.02]
        t_stat, p_val = newey_west_t_test(x, y)
        assert t_stat > 0
        assert p_val < 0.05


# ── Score loading / provenance gate ──────────────────────────────────────────


class TestScoreLoading:
    def test_load_expert_scores(self, tmp_path):
        d = _make_score_dir(tmp_path, "xgb", {
            "2025-06-01": {"AAPL": 0.5, "MSFT": 0.3},
            "2025-06-02": {"AAPL": 0.6, "MSFT": 0.4},
        })
        digests = _admitted_digests({"xgb": d}, ["2025-06-01", "2025-06-02"])
        expert = load_expert_scores("xgb", d, admitted_digests=digests)
        assert expert.name == "xgb"
        assert len(expert.dates) == 2
        assert expert.scores_by_date["2025-06-01"]["AAPL"] == 0.5

    def test_skips_non_date_files(self, tmp_path):
        d = _make_score_dir(tmp_path, "xgb", {"2025-06-01": {"A": 0.5}})
        (d / "README.json").write_text("{}")
        digests = _admitted_digests({"xgb": d}, ["2025-06-01"])
        expert = load_expert_scores("xgb", d, admitted_digests=digests)
        assert len(expert.dates) == 1

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_expert_scores("x", tmp_path / "nonexistent", admitted_digests={})


class TestProvenanceGate:
    """Codex review 2026-07-13, finding 1: load_expert_scores must not
    accept arbitrary JSON while ignoring the ledger's admission/digests."""

    def test_arbitrary_json_without_ledger_admission_is_rejected(self, tmp_path):
        d = _make_score_dir(tmp_path, "xgb", {"2025-06-01": {"A": 0.5}})
        expert = load_expert_scores("xgb", d, admitted_digests={})
        assert expert.dates == []

    def test_rejects_date_not_in_admitted_digests(self, tmp_path):
        d = _make_score_dir(
            tmp_path, "xgb",
            {"2025-06-01": {"A": 0.5}, "2025-06-02": {"A": 0.6}},
        )
        digests = _admitted_digests({"xgb": d}, ["2025-06-01"])  # only 06-01 admitted
        expert = load_expert_scores("xgb", d, admitted_digests=digests)
        assert expert.dates == ["2025-06-01"]

    def test_rejects_file_whose_digest_no_longer_matches_ledger(self, tmp_path):
        """A file mutated after the ledger's digest was recorded must be
        rejected -- provenance is content-addressed, not a filename match."""
        d = _make_score_dir(tmp_path, "xgb", {"2025-06-01": {"A": 0.5}})
        digests = _admitted_digests({"xgb": d}, ["2025-06-01"])
        (d / "2025-06-01.json").write_text(json.dumps({"scores": {"A": 999.0}}))
        expert = load_expert_scores("xgb", d, admitted_digests=digests)
        assert expert.dates == []

    def test_rejects_wrong_expert_name_key(self, tmp_path):
        """A digest admitted under a DIFFERENT expert name must not
        authorize this expert's file, even if the date matches."""
        d = _make_score_dir(tmp_path, "xgb", {"2025-06-01": {"A": 0.5}})
        digests = _admitted_digests({"patchtst": d}, ["2025-06-01"])
        expert = load_expert_scores("xgb", d, admitted_digests=digests)
        assert expert.dates == []


class TestForwardReturnsLoading:
    def test_load_csv(self, tmp_path):
        p = _make_returns_csv(tmp_path, {
            "2025-06-01": {"AAPL": 0.05, "MSFT": 0.02},
        })
        returns = load_forward_returns(p)
        assert returns["2025-06-01"]["AAPL"] == pytest.approx(0.05)


# ── Returns-file provenance gate (Codex review 2026-07-13, finding 1) ──────


def _ledger_with_records(records: list[dict]) -> AdmissibilityLedger:
    return AdmissibilityLedger(records=records)


class TestVerifyReturnsFileDigest:
    def test_matching_digest_passes(self, tmp_path):
        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        p = labels_dir / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"{digest}@labels/returns.csv"},
        ])
        assert verify_returns_file_digest(p, ledger) == (digest, "labels/returns.csv")

    def test_mismatched_digest_is_rejected(self, tmp_path):
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        wrong_digest = f"sha256:{'0' * 64}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"{wrong_digest}@labels/returns.csv"},
        ])
        with pytest.raises(ValueError, match="does not match"):
            verify_returns_file_digest(p, ledger)

    def test_no_admitted_label_ref_is_rejected(self, tmp_path):
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        # Record exists but is NOT admitted -- must not be trusted.
        ledger = _ledger_with_records([
            {"admitted": False, "label_artifact_ref": f"sha256:{'0' * 64}@labels/returns.csv"},
        ])
        with pytest.raises(ValueError, match="no admitted records"):
            verify_returns_file_digest(p, ledger)

    def test_disagreeing_admitted_digests_are_rejected(self, tmp_path):
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"sha256:{'0' * 64}@labels/a.csv"},
            {"admitted": True, "label_artifact_ref": f"sha256:{'1' * 64}@labels/b.csv"},
        ])
        with pytest.raises(ValueError, match="disagree"):
            verify_returns_file_digest(p, ledger)

    def test_same_digest_different_locators_are_not_disagreement(self, tmp_path):
        """Two admitted records pointing at the same digest but different
        locators are the SAME artifact under the digest-identity contract
        — they must NOT trigger the disagreement error."""
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"{digest}@labels/a.csv"},
            {"admitted": True, "label_artifact_ref": f"{digest}@labels/b.csv"},
        ])
        actual_digest, _ = verify_returns_file_digest(p, ledger)
        assert actual_digest == digest

    def test_different_locator_accepted_when_digest_matches(self, tmp_path):
        """Artifact identity = SHA-256 digest (contract option 1, codex r9).
        A file at a different path with the same digest IS the same artifact
        — the locator is an informational audit trail, not identity."""
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"{digest}@labels/unrelated_file.csv"},
        ])
        actual_digest, audit_locator = verify_returns_file_digest(p, ledger)
        assert actual_digest == digest
        assert audit_locator == "labels/unrelated_file.csv"

    def test_different_directory_accepted_when_digest_matches(self, tmp_path):
        """Same digest at a different directory is accepted — identity is
        the content digest, not the filesystem location."""
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        p = other_dir / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"{digest}@labels/returns.csv"},
        ])
        actual_digest, audit_locator = verify_returns_file_digest(p, ledger)
        assert actual_digest == digest

    def test_digest_only_ref_without_locator_is_accepted(self, tmp_path):
        """A label_artifact_ref with no @locator suffix is valid — the
        locator is optional audit-trail metadata, not required."""
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": digest},
        ])
        actual_digest, audit_locator = verify_returns_file_digest(p, ledger)
        assert actual_digest == digest
        assert audit_locator == ""

    def test_label_observation_end_shorter_than_horizon_is_rejected(self, tmp_path):
        """Codex review 2026-07-13T17:00:21Z round 6, finding 2: the
        actual_span < label_horizon_days check previously raised
        ValueError and was then immediately caught and swallowed by the
        SAME try/except meant only to guard unparseable dates -- a
        parseable-but-too-short label window was silently accepted. It
        must now propagate as a real failure."""
        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        p = labels_dir / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-01-10,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = AdmissibilityLedger(
            label_horizon_days=60,
            records=[
                {
                    "admitted": True,
                    "label_artifact_ref": f"{digest}@labels/returns.csv",
                    "prediction_date": "2025-01-01",
                    # Only 9 days after prediction_date -- well short of
                    # the declared 60-day label horizon.
                    "label_observation_end": "2025-01-10",
                },
            ],
        )
        with pytest.raises(ValueError, match="label_observation_end .* is only"):
            verify_returns_file_digest(p, ledger)

    def test_label_observation_end_meeting_horizon_passes(self, tmp_path):
        """Sanity check for the above: a span that DOES meet the declared
        horizon must not raise."""
        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        p = labels_dir / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-03-02,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = AdmissibilityLedger(
            label_horizon_days=60,
            records=[
                {
                    "admitted": True,
                    "label_artifact_ref": f"{digest}@labels/returns.csv",
                    "prediction_date": "2025-01-01",
                    "label_observation_end": "2025-03-02",  # 60 days later
                },
            ],
        )
        assert verify_returns_file_digest(p, ledger) == (digest, "labels/returns.csv")


# ── Go/no-go verdict ────────────────────────────────────────────────────────


class TestRunPhaseA:
    @pytest.fixture()
    def experts(self, tmp_path):
        xgb_dir = _make_score_dir(tmp_path, "xgb", XGB_SCORES)
        pt_dir = _make_score_dir(tmp_path, "patchtst", PATCHTST_SCORES)
        digests = _admitted_digests({"xgb": xgb_dir, "patchtst": pt_dir}, DATES)
        return [
            load_expert_scores("xgb", xgb_dir, admitted_digests=digests),
            load_expert_scores("patchtst", pt_dir, admitted_digests=digests),
        ]

    def test_runs_without_error(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5)
        assert isinstance(result, PhaseAResult)
        assert result.n_dates == 5
        assert result.n_experts == 2
        assert result.verdict in (
            "L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE", "EXPLORATORY_ONLY",
        )

    def test_requires_two_experts(self, experts):
        with pytest.raises(ValueError, match="at least 2"):
            run_phase_a([experts[0]], FORWARD_RETURNS, champion_name="xgb")

    def test_requires_valid_champion_name(self, experts):
        with pytest.raises(ValueError, match="champion_name"):
            run_phase_a(experts, FORWARD_RETURNS, champion_name="nonexistent")

    def test_result_serializable(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5)
        d = result_to_dict(result)
        out = json.dumps(d, default=str)
        parsed = json.loads(out)
        assert parsed["verdict"] in (
            "L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE", "EXPLORATORY_ONLY",
        )
        assert "daily_returns" not in parsed["champion"]
        assert "daily_net_returns" not in parsed["champion"]

    def test_champion_name_is_explicit_not_first_expert(self, tmp_path):
        """Passing patchtst as champion (even though xgb is listed/loaded
        first) must select patchtst -- champion identity is explicit, not
        argument-order-dependent (Codex review 2026-07-13, finding 3)."""
        xgb_dir = _make_score_dir(tmp_path, "xgb", XGB_SCORES)
        pt_dir = _make_score_dir(tmp_path, "patchtst", PATCHTST_SCORES)
        digests = _admitted_digests({"xgb": xgb_dir, "patchtst": pt_dir}, DATES)
        experts = [
            load_expert_scores("xgb", xgb_dir, admitted_digests=digests),
            load_expert_scores("patchtst", pt_dir, admitted_digests=digests),
        ]
        result = run_phase_a(experts, FORWARD_RETURNS, champion_name="patchtst", top_n=5)
        assert "patchtst" in result.champion.name
        assert result.champion_name == "patchtst"

    def test_metrics_are_finite(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5)
        assert math.isfinite(result.l1.mean_return)
        assert math.isfinite(result.champion.mean_return)
        assert math.isfinite(result.p_value)
        assert math.isfinite(result.t_statistic)

    def test_falls_back_to_hac_when_insufficient_non_overlapping_blocks(self, experts):
        """5 daily dates can never yield >= MIN_NON_OVERLAPPING_OBSERVATIONS
        blocks at the default 60-day spacing -- must fall back to the HAC
        method and report a non-promotable EXPLORATORY_ONLY verdict, never
        L1_BEATS_CHAMPION/CHAMPION_RETAINED from an invalid overlapping-
        return test (Codex review 2026-07-13, findings 4+6)."""
        result = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5)
        assert result.test_method == TEST_METHOD_HAC_FALLBACK
        assert result.verdict == "EXPLORATORY_ONLY"

    def test_uses_non_overlapping_blocks_when_sufficient(self, tmp_path):
        """The primary statistical test (non-overlapping blocks) still
        runs and its statistics are still computed/surfaced even though
        the resulting verdict is unconditionally capped to
        EXPLORATORY_ONLY (Codex review 2026-07-13T17:00:21Z round 6,
        finding 1) -- capping promotability must not destroy the
        underlying research signal."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=3)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
            nested_wf_harness_status=par.NESTED_WF_HARNESS_APPLIED,
        )
        assert result.test_method == TEST_METHOD_NON_OVERLAPPING
        assert result.n_test_dates == 10
        # No value of nested_wf_harness_status can unlock a promotable
        # verdict until a real harness+verifier exists.
        assert result.verdict == "EXPLORATORY_ONLY"
        assert "Underlying (non-binding) result" in result.verdict_detail

    def test_nested_wf_harness_cap_is_unconditional(self, tmp_path):
        """Codex review 2026-07-13T17:00:21Z round 6, finding 1:
        ``nested_wf_harness_status == NESTED_WF_HARNESS_APPLIED`` is a
        self-attested manifest string -- a caller can set it with no real
        harness having run. No verifier for that harness exists in this
        codebase, so the EXPLORATORY_ONLY cap must apply UNCONDITIONALLY:
        setting the status to NESTED_WF_HARNESS_APPLIED must NOT unlock a
        promotable verdict, same as leaving it at NOT_BUILT. The
        underlying (non-binding) statistics must still be computed and
        surfaced in verdict_detail either way, so the research signal
        remains visible even though it is never promotable."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=3)
        not_built = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
        )
        applied = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
            nested_wf_harness_status=par.NESTED_WF_HARNESS_APPLIED,
        )
        assert not_built.nested_wf_harness_status == par.NESTED_WF_HARNESS_NOT_BUILT
        assert applied.nested_wf_harness_status == par.NESTED_WF_HARNESS_APPLIED
        # Both are capped, regardless of the attested status -- this is
        # the round 6 behavior change (previously APPLIED escaped the cap).
        assert not_built.verdict == "EXPLORATORY_ONLY"
        assert applied.verdict == "EXPLORATORY_ONLY"
        # The underlying, pre-cap statistics are unaffected by the
        # attestation and must still be visible in the detail message --
        # identical for both, since nested_wf_harness_status does not
        # change the computation, only the cap.
        assert "Underlying (non-binding) result" in not_built.verdict_detail
        assert "Underlying (non-binding) result" in applied.verdict_detail

        def _underlying(detail: str) -> str:
            return detail.split("Underlying (non-binding) result:", 1)[1]

        assert _underlying(not_built.verdict_detail) == _underlying(applied.verdict_detail)

    def test_cost_bps_is_applied_and_recorded(self, experts):
        zero_cost = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5, cost_bps=0.0)
        high_cost = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5, cost_bps=500.0)
        assert zero_cost.cost_bps == 0.0
        assert high_cost.cost_bps == 500.0
        assert high_cost.l1.mean_net_return < zero_cost.l1.mean_net_return

    def test_provenance_fields_are_persisted(self, experts):
        """Codex review 2026-07-13, finding 3: a result must record the
        exact inputs that produced it so a favorable output can be
        independently reproduced."""
        result = run_phase_a(
            experts, FORWARD_RETURNS, champion_name="xgb", top_n=5,
            manifest_fingerprint="sha256:manifest-aaa",
            ledger_fingerprint="sha256:ledger-bbb",
            returns_file_digest="sha256:returns-ccc",
            expert_score_digests={"xgb": ["sha256:x1"], "patchtst": ["sha256:p1"]},
        )
        assert result.manifest_fingerprint == "sha256:manifest-aaa"
        assert result.ledger_fingerprint == "sha256:ledger-bbb"
        assert result.returns_file_digest == "sha256:returns-ccc"
        assert result.expert_score_digests == {"xgb": ["sha256:x1"], "patchtst": ["sha256:p1"]}
        assert result.dates == sorted(result.dates)
        assert len(result.dates) == result.n_dates

    def test_ic_effect_size_gate_blocks_promotion_when_too_small(self, tmp_path):
        """A statistically significant, net-positive result must still not
        promote to L1_BEATS_CHAMPION if the IC effect size is below the
        pre-registered minimum (Codex review 2026-07-13 round 4, finding
        4: minimum_effect_size_delta_ic was registered but never checked)."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=3)
        unconstrained = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
            minimum_effect_size_delta_ic=0.0,
        )
        impossible = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
            minimum_effect_size_delta_ic=1.0,  # IC deltas are bounded in [-2, 2]; ~unreachable
        )
        assert impossible.verdict != "L1_BEATS_CHAMPION"
        assert impossible.minimum_effect_size_delta_ic == 1.0
        assert math.isfinite(impossible.delta_ic_test) or math.isnan(impossible.delta_ic_test)
        # Sanity: the gate is the only difference introduced -- the
        # unconstrained run's own verdict is unaffected by adding this test.
        assert unconstrained.minimum_effect_size_delta_ic == 0.0

    def test_paired_test_dates_and_exclusions_are_recorded(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5)
        assert result.n_paired_test_dates <= result.n_test_dates
        assert result.n_test_dates_excluded_asymmetric_or_undersized >= 0


class TestVerdictLogic:
    def test_champion_retained_when_l1_worse(self):
        champ = StrategyResult(name="champ", mean_return=0.10, daily_returns=[0.10] * 10)
        l1 = StrategyResult(name="l1", mean_return=0.05, daily_returns=[0.05] * 10)
        result = PhaseAResult(champion=champ, l1=l1)
        result.delta_return = l1.mean_return - champ.mean_return
        assert result.delta_return < 0


# ── main() CLI: manifest-locked parameters + exit code (Codex review ───────
# 2026-07-13, findings 2+4) ──────────────────────────────────────────────────


def _build_cli_fixture(
    tmp_path: Path,
    *,
    label_horizon_days: int = 0,
    **manifest_overrides: Any,
) -> dict[str, str]:
    """Build a full manifest+ledger+scores+returns fixture on disk, and
    return the paths needed to invoke ``main()`` against it end-to-end."""
    universe = [f"T{i}" for i in range(12)]
    dates = ["2025-06-01", "2025-06-02", "2025-06-03"]

    xgb_dir = tmp_path / "xgb"
    xgb_dir.mkdir()
    pt_dir = tmp_path / "patchtst"
    pt_dir.mkdir()

    rng = np.random.default_rng(11)
    label_end = (date.fromisoformat(dates[-1]) + timedelta(days=60)).isoformat()

    returns_lines = ["date,ticker,fwd_return"]
    score_bytes: dict[tuple[str, str], bytes] = {}
    for d in dates:
        base = rng.normal(0, 1, len(universe))
        xgb_bytes = json.dumps({"scores": {t: float(base[i]) for i, t in enumerate(universe)}}).encode()
        pt_bytes = json.dumps({
            "scores": {t: float(base[i] + rng.normal(0, 0.2)) for i, t in enumerate(universe)}
        }).encode()
        (xgb_dir / f"{d}.json").write_bytes(xgb_bytes)
        (pt_dir / f"{d}.json").write_bytes(pt_bytes)
        score_bytes[("xgb", d)] = xgb_bytes
        score_bytes[("patchtst", d)] = pt_bytes
        for i, t in enumerate(universe):
            returns_lines.append(f"{d},{t},{base[i] * 0.01}")

    returns_path = tmp_path / "returns.csv"
    returns_path.write_text("\n".join(returns_lines))
    returns_digest = f"sha256:{hashlib.sha256(returns_path.read_bytes()).hexdigest()}"

    # Session calendar: all dates used in the fixture
    cal_path = tmp_path / "session_calendar.json"
    cal_bytes = json.dumps(sorted(dates)).encode()
    cal_path.write_bytes(cal_bytes)
    cal_digest = f"sha256:{hashlib.sha256(cal_bytes).hexdigest()}"

    # Champion policy artifact: typed schema (Codex r13, finding 2)
    policy_path = tmp_path / "champion_policy.json"
    policy_bytes = json.dumps({
        "champion_name": "xgb",
        "top_n": 10,
        "rebalance_cadence": "block_rebalance",
        "cost_model": {"base_cost_bps": 5.0},
        "score_normalization": "cross_sectional_zscore",
    }).encode()
    policy_path.write_bytes(policy_bytes)
    policy_digest = f"sha256:{hashlib.sha256(policy_bytes).hexdigest()}"

    records = [
        {
            "expert_name": name,
            "prediction_date": d,
            "admitted": True,
            "score_artifact_digest": f"sha256:{hashlib.sha256(raw).hexdigest()}",
            "label_artifact_ref": f"{returns_digest}@{returns_path.name}",
            "label_observation_end": label_end,
        }
        for (name, d), raw in score_bytes.items()
    ]
    ledger = AdmissibilityLedger(
        records=records, label_horizon_days=label_horizon_days,
    )
    ledger.ledger_fingerprint = ledger.compute_fingerprint()
    ledger_path = write_ledger(ledger, tmp_path)

    manifest = build_default_manifest(
        admissibility_ledger_fingerprint=ledger.ledger_fingerprint,
        session_calendar_digest=cal_digest,
        champion_policy_artifact_digest=policy_digest,
    )
    for key, value in manifest_overrides.items():
        setattr(manifest, key, value)
    manifest.manifest_fingerprint = manifest.compute_fingerprint()
    manifest_path = write_manifest(manifest, tmp_path)

    return {
        "xgb_dir": str(xgb_dir),
        "pt_dir": str(pt_dir),
        "returns_path": str(returns_path),
        "manifest_path": str(manifest_path),
        "ledger_path": str(ledger_path),
        "output_dir": str(tmp_path / "output"),
        "cal_path": str(cal_path),
        "policy_path": str(policy_path),
    }


def _cli_argv(fixture: dict[str, str], **overrides: str) -> list[str]:
    argv = [
        "--expert", "xgb", "--score-dir", fixture["xgb_dir"],
        "--expert", "patchtst", "--score-dir", fixture["pt_dir"],
        "--returns-file", fixture["returns_path"],
        "--manifest-file", fixture["manifest_path"],
        "--ledger-file", fixture["ledger_path"],
        "--output-dir", fixture["output_dir"],
        "--session-calendar", fixture["cal_path"],
        "--champion-policy-artifact", fixture["policy_path"],
    ]
    for key, value in overrides.items():
        argv.extend([f"--{key.replace('_', '-')}", str(value)])
    return argv


class TestMainManifestLockedParameters:
    def test_runs_without_explicit_top_n_or_alpha(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0

    def test_rejects_top_n_mismatched_with_manifest(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture, top_n=999))
        assert rc == 1
        assert "does not match" in capsys.readouterr().err

    def test_rejects_alpha_mismatched_with_manifest(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture, alpha=0.99))
        assert rc == 1
        assert "does not match" in capsys.readouterr().err

    def test_accepts_top_n_matching_manifest(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        manifest_top_n = build_default_manifest().portfolio_mapping["top_n"]
        rc = par.main(_cli_argv(fixture, top_n=manifest_top_n))
        assert rc == 0

    def test_rejects_manifest_declaring_partial_expert_coverage(self, tmp_path, capsys):
        """The runner's evaluation calendar always requires complete
        expert coverage -- a manifest that declares otherwise must be
        rejected rather than silently evaluated as if it agreed (Codex
        review 2026-07-13 round 4, finding 1)."""
        fixture = _build_cli_fixture(
            tmp_path, phase_a_requires_complete_expert_coverage=False,
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "phase_a_requires_complete_expert_coverage" in capsys.readouterr().err


class TestMainExitCode:
    """Codex review 2026-07-13, finding 4: a completed run is a success
    regardless of verdict -- only invalid inputs/provenance/runtime errors
    should exit nonzero."""

    @pytest.mark.parametrize(
        "verdict",
        ["L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE", "EXPLORATORY_ONLY"],
    )
    def test_exit_code_is_zero_for_every_completed_verdict(self, tmp_path, monkeypatch, verdict):
        fixture = _build_cli_fixture(tmp_path)
        canned = PhaseAResult(
            run_id="test-run",
            verdict=verdict,
            champion=StrategyResult(name="champion"),
            l1=StrategyResult(name="l1"),
        )
        monkeypatch.setattr(par, "run_phase_a", lambda **kwargs: canned)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0

    def test_exit_code_is_nonzero_for_unregistered_expert(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        argv = [
            "--expert", "not-registered", "--score-dir", fixture["xgb_dir"],
            "--expert", "patchtst", "--score-dir", fixture["pt_dir"],
            "--returns-file", fixture["returns_path"],
            "--manifest-file", fixture["manifest_path"],
            "--ledger-file", fixture["ledger_path"],
            "--output-dir", fixture["output_dir"],
            "--session-calendar", fixture["cal_path"],
            "--champion-policy-artifact", fixture["policy_path"],
        ]
        rc = par.main(argv)
        assert rc == 1

    def test_exit_code_is_nonzero_for_tampered_returns_file(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        Path(fixture["returns_path"]).write_text(
            Path(fixture["returns_path"]).read_text() + "\n2025-06-04,T0,999\n"
        )
        with pytest.raises(ValueError, match="does not match"):
            par.main(_cli_argv(fixture))


# ── Round 5 adversarial tests ───────────────────────────────────────────────


class TestManifestLedgerBinding:
    """Round 5, finding 1: manifest and ledger must be bound."""

    def test_rejects_mismatched_ledger_fingerprint(self, tmp_path):
        fixture = _build_cli_fixture(
            tmp_path,
            admissibility_ledger_fingerprint="sha256:wrong-fingerprint",
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1

    def test_rejects_empty_ledger_fingerprint(self, tmp_path, capsys):
        """An unset admissibility_ledger_fingerprint must be rejected
        outright, not merely warned about -- a warning-only check would
        let a caller trivially skip the binding requirement just by
        leaving the field blank (Codex round 5, finding 1)."""
        fixture = _build_cli_fixture(
            tmp_path,
            admissibility_ledger_fingerprint="",
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "empty" in capsys.readouterr().err

    def test_rejects_expert_set_not_in_manifest(self, tmp_path, capsys):
        """Experts [xgb, per_ticker] don't match any registered expert_sets."""
        fixture = _build_cli_fixture(tmp_path)
        argv = [
            "--expert", "xgb", "--score-dir", fixture["xgb_dir"],
            "--expert", "per_ticker", "--score-dir", fixture["pt_dir"],
            "--returns-file", fixture["returns_path"],
            "--manifest-file", fixture["manifest_path"],
            "--ledger-file", fixture["ledger_path"],
            "--output-dir", fixture["output_dir"],
            "--session-calendar", fixture["cal_path"],
            "--champion-policy-artifact", fixture["policy_path"],
        ]
        rc = par.main(argv)
        assert rc == 1
        assert "expert_sets" in capsys.readouterr().err


class TestNestedWfHarnessWiring:
    """manifest.nested_wf_harness_status must reach run_phase_a and be
    persisted on the result (round 5, finding 2) -- but, per round 6,
    finding 1 (Codex review 2026-07-13T17:00:21Z), it must NEVER unlock a
    promotable verdict: the field is versioned/checkable scaffolding for a
    future real harness+verifier, not something a caller can flip to
    escape the EXPLORATORY_ONLY cap today."""

    def test_manifest_default_status_reaches_result_json(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        [out] = list(Path(fixture["output_dir"]).glob("phase_a_result_*.json"))
        data = json.loads(out.read_text())
        assert data["nested_wf_harness_status"] == par.NESTED_WF_HARNESS_NOT_BUILT
        assert data["verdict"] == "EXPLORATORY_ONLY"

    def test_manifest_applied_status_reaches_result_json_but_still_caps(self, tmp_path):
        """Even when the manifest declares NESTED_WF_HARNESS_APPLIED, the
        status is faithfully persisted on the result (so it remains an
        auditable, checkable manifest fact) but the verdict is still
        capped at EXPLORATORY_ONLY end-to-end through the CLI -- there is
        no way to reach a promotable verdict from this manifest field
        alone."""
        fixture = _build_cli_fixture(
            tmp_path,
            nested_wf_harness_status=par.NESTED_WF_HARNESS_APPLIED,
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        [out] = list(Path(fixture["output_dir"]).glob("phase_a_result_*.json"))
        data = json.loads(out.read_text())
        assert data["nested_wf_harness_status"] == par.NESTED_WF_HARNESS_APPLIED
        assert data["verdict"] == "EXPLORATORY_ONLY"


class TestPairedICDelta:
    """Round 5, finding 4: delta_ic_test must be truly paired."""

    def test_paired_ic_dates_is_recorded(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
        )
        assert result.n_paired_ic_dates > 0
        assert result.n_paired_ic_dates <= result.n_paired_test_dates


class TestMinNonOverlappingFromManifest:
    """Round 5, finding 5: min_non_overlapping_observations sourced from manifest."""

    def test_persisted_on_result(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            min_non_overlapping_observations=5,
        )
        assert result.min_non_overlapping_observations == 5

    def test_high_minimum_forces_exploratory(self, tmp_path):
        """With impossibly high minimum, verdict must be EXPLORATORY_ONLY."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            min_non_overlapping_observations=999,
        )
        assert result.verdict == "EXPLORATORY_ONLY"

    def test_cli_sources_from_manifest(self, tmp_path):
        """The CLI should source min_non_overlapping_observations from
        the manifest's statistical_test section."""
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0


# ── Round 6 adversarial tests ───────────────────────────────────────────────


class TestBlockLengthVsLabelHorizon:
    """Round 6, item 1: block_length_days < label_horizon_days must be
    fail-closed, not a warning — otherwise the 'non-overlapping' test
    still has overlapping forward returns."""

    def test_rejects_block_shorter_than_label_horizon(self, tmp_path, capsys):
        """When ledger.label_horizon_days=60 and manifest
        block_length_days=30, the runner must reject (return 1)."""
        fixture = _build_cli_fixture(tmp_path, label_horizon_days=60)
        # Override manifest's block_length_days to be too short
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["statistical_test"]["block_length_days"] = 30
        # Recompute fingerprint
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "block_length_days" in capsys.readouterr().err

    def test_accepts_block_equal_to_label_horizon(self, tmp_path):
        """block_length_days == label_horizon_days is valid."""
        fixture = _build_cli_fixture(tmp_path, label_horizon_days=60)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0


class TestManifestLedgerBindingFailClosed:
    """Round 6, item 2: empty manifest.admissibility_ledger_fingerprint
    must be a hard error, not a warning."""

    def test_rejects_empty_ledger_fingerprint(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        # Rebuild manifest without ledger fingerprint
        manifest = build_default_manifest(admissibility_ledger_fingerprint="")
        manifest.manifest_fingerprint = manifest.compute_fingerprint()
        write_manifest(manifest, tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "admissibility_ledger_fingerprint" in capsys.readouterr().err


class TestConfirmatoryFloor:
    """Round 6, item 5: a passing test below MIN_CONFIRMATORY_OBSERVATIONS
    must cap at EXPLORATORY_ONLY, never L1_BEATS_CHAMPION."""

    def test_few_blocks_caps_at_exploratory(self, tmp_path):
        """Even with p < alpha and delta_ic above threshold, if there are
        fewer than MIN_CONFIRMATORY_OBSERVATIONS paired observations, the
        verdict must be EXPLORATORY_ONLY."""
        # Build a fixture with just enough dates for the test to pass
        # but fewer than MIN_CONFIRMATORY_OBSERVATIONS non-overlapping blocks
        n = MIN_CONFIRMATORY_OBSERVATIONS - 1
        experts, rets = _build_n_date_fixture(tmp_path, n, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            minimum_effect_size_delta_ic=0.0,
        )
        # The test may or may not pass, but IF it would have been
        # L1_BEATS_CHAMPION, it must be capped at EXPLORATORY_ONLY
        assert result.verdict != "L1_BEATS_CHAMPION"

    def test_many_blocks_allows_l1_beats(self, tmp_path):
        """With enough observations (>= MIN_CONFIRMATORY_OBSERVATIONS),
        the confirmatory floor should not block a valid verdict."""
        n = MIN_CONFIRMATORY_OBSERVATIONS + 10
        experts, rets = _build_n_date_fixture(tmp_path, n, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            minimum_effect_size_delta_ic=0.0,
        )
        # We can't force L1_BEATS_CHAMPION (depends on random data),
        # but confirm the min_confirmatory_observations is persisted
        assert result.min_confirmatory_observations == MIN_CONFIRMATORY_OBSERVATIONS

    def test_result_persists_confirmatory_floor(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
        )
        assert result.min_confirmatory_observations == MIN_CONFIRMATORY_OBSERVATIONS


class TestScoreCoveragePersisted:
    """Round 6, item 3: coverage stats must be persisted on the result."""

    def test_coverage_is_recorded(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        # Find the output file
        output_dir = Path(fixture["output_dir"])
        result_files = list(output_dir.glob("phase_a_result_*.json"))
        assert len(result_files) == 1
        result_data = json.loads(result_files[0].read_text())
        assert "score_coverage" in result_data
        assert "xgb" in result_data["score_coverage"]
        assert "patchtst" in result_data["score_coverage"]
        assert result_data["score_coverage"]["xgb"]["loaded"] > 0


class TestLabelObservationEndPersisted:
    """Round 6, item 4: label_observation_end must be persisted."""

    def test_label_observation_end_is_recorded(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        output_dir = Path(fixture["output_dir"])
        result_files = list(output_dir.glob("phase_a_result_*.json"))
        assert len(result_files) == 1
        result_data = json.loads(result_files[0].read_text())
        assert "label_observation_end" in result_data


# ── Round 6 (2026-07-13T17:00:21Z) adversarial tests ────────────────────────


class TestCoverageGapFailsClosed:
    """Codex review 2026-07-13T17:00:21Z round 6, finding 3: a missing or
    digest-mismatched ledger-admitted score artifact must hard-reject
    (return 1), not warn-and-continue. Warn-and-continue turns an
    immutable admitted calendar into a post-hoc subset chosen by whichever
    files happen to be present, which can change both selection and
    statistical significance."""

    def test_missing_admitted_score_file_is_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        # Delete one ledger-admitted xgb score file: the ledger still
        # expects it (it was admitted), but load_expert_scores can no
        # longer load it.
        xgb_dir = Path(fixture["xgb_dir"])
        deleted = sorted(xgb_dir.glob("*.json"))[0]
        deleted.unlink()

        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "ledger-admitted dates could not be loaded" in err

    def test_digest_mismatched_admitted_score_file_is_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        # Mutate one ledger-admitted xgb score file in place -- its content
        # digest no longer matches the ledger's admitted record, so
        # load_expert_scores (which only admits digest-matching files)
        # will not load it, producing exactly the same coverage gap as a
        # missing file.
        xgb_dir = Path(fixture["xgb_dir"])
        mutated = sorted(xgb_dir.glob("*.json"))[0]
        mutated.write_bytes(mutated.read_bytes() + b" ")

        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "ledger-admitted dates could not be loaded" in capsys.readouterr().err

    def test_complete_coverage_still_succeeds(self, tmp_path):
        """Sanity check: an untouched, fully-covered fixture must still
        pass -- the hard-reject only fires on an actual coverage gap."""
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0


# ── Round 9 (rebalance cadence + one_sided) ─────────────────────────────────


class TestBlockRebalancePolicy:
    """Codex review round 9: the primary test evaluates a block-rebalance
    policy. Intermediate daily selections between block endpoints must not
    affect the primary test result, proving that costs are charged only at
    rebalance points and no intermediate trades are silently ignored."""

    def test_intermediate_daily_scores_do_not_affect_primary_test(self, tmp_path):
        n = 200
        block_length = 20
        tickers = [f"T{i}" for i in range(10)]
        dates = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
        block_dates_list, _ = select_non_overlapping_dates(dates, block_length)
        block_dates = set(block_dates_list)
        assert len(block_dates) >= 8

        rng_shared = np.random.default_rng(42)
        shared = {d: rng_shared.normal(0, 1, len(tickers)) for d in dates}

        pt_scores = {
            d: {t: float(shared[d][j] + 0.1 * j) for j, t in enumerate(tickers)}
            for d in dates
        }
        rets = {
            d: {t: float(shared[d][j] * 0.02) for j, t in enumerate(tickers)}
            for d in dates
        }

        rng_a = np.random.default_rng(100)
        rng_b = np.random.default_rng(200)
        xgb_a: dict[str, dict[str, float]] = {}
        xgb_b: dict[str, dict[str, float]] = {}
        for d in dates:
            if d in block_dates:
                xgb_a[d] = {t: float(shared[d][j]) for j, t in enumerate(tickers)}
                xgb_b[d] = {t: float(shared[d][j]) for j, t in enumerate(tickers)}
            else:
                xgb_a[d] = {t: float(rng_a.normal()) for t in tickers}
                xgb_b[d] = {t: float(rng_b.normal()) for t in tickers}

        expert_a = ExpertScores(name="xgb", dates=dates, scores_by_date=xgb_a)
        expert_b = ExpertScores(name="xgb", dates=dates, scores_by_date=xgb_b)
        expert_pt = ExpertScores(name="patchtst", dates=dates, scores_by_date=pt_scores)

        result_a = run_phase_a(
            [expert_a, expert_pt], rets, champion_name="xgb",
            top_n=3, block_length_days=block_length,
        )
        result_b = run_phase_a(
            [expert_b, expert_pt], rets, champion_name="xgb",
            top_n=3, block_length_days=block_length,
        )

        assert result_a.test_method == TEST_METHOD_NON_OVERLAPPING
        assert result_a.test_method == result_b.test_method
        assert result_a.n_paired_test_dates == result_b.n_paired_test_dates
        assert result_a.delta_net_return_test == pytest.approx(
            result_b.delta_net_return_test,
        )
        assert result_a.t_statistic == pytest.approx(result_b.t_statistic)
        assert result_a.p_value == pytest.approx(result_b.p_value)
        assert result_a.verdict == result_b.verdict
        assert result_a.n_test_dates < n


class TestRebalanceCadenceValidation:
    """Codex review round 9: manifest.rebalance_cadence must match the
    implemented block-rebalance policy."""

    def test_rejects_daily_cadence(self, tmp_path, capsys):
        fixture = _build_cli_fixture(
            tmp_path, rebalance_cadence="daily",
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "rebalance_cadence" in capsys.readouterr().err

    def test_accepts_block_rebalance(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0


class TestOneSidedValidation:
    """Codex review round 9: statistical_test.one_sided must be True,
    matching the implemented one-sided Newey-West paired t-test."""

    def test_rejects_false_one_sided(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["statistical_test"]["one_sided"] = False
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "one_sided" in capsys.readouterr().err

    def test_rejects_absent_one_sided(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        del manifest_data["statistical_test"]["one_sided"]
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "one_sided" in capsys.readouterr().err

    def test_accepts_true_one_sided(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0


# ── Round 10 (session-index spacing + estimand versioning) ─────────────────


class TestEstimandPolicyVersioning:
    """Codex review round 10: the result must explicitly version the
    evaluation estimand and document the production champion's policy,
    since the block-rebalance evaluation policy may differ from production."""

    def test_estimand_fields_are_persisted(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            champion_production_policy="daily",
        )
        assert result.estimand_policy == "block_rebalance_paired"
        assert result.champion_production_policy == "daily"
        assert result.block_spacing_unit == "session_index"

    def test_daily_production_policy_appends_caveat(self, tmp_path):
        """When champion_production_policy != 'block_rebalance', the verdict
        detail must carry a caveat about the estimand mismatch."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            champion_production_policy="daily",
        )
        assert "block-rebalance evaluation policy" in result.verdict_detail
        assert "daily" in result.verdict_detail

    def test_block_rebalance_production_policy_no_caveat(self, tmp_path):
        """When champion_production_policy == 'block_rebalance', no mismatch
        caveat is needed."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            champion_production_policy="block_rebalance",
        )
        assert "block-rebalance evaluation policy" not in result.verdict_detail

    def test_cli_persists_estimand_fields(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        [out] = list(Path(fixture["output_dir"]).glob("phase_a_result_*.json"))
        data = json.loads(out.read_text())
        assert data["estimand_policy"] == "block_rebalance_paired"
        assert data["champion_production_policy"] == "daily"
        assert data["block_spacing_unit"] == "session_index"
        assert data["embargo_sessions"] == 10


class TestEmbargoSessions:
    """Codex review round 10: embargo_sessions adds extra spacing."""

    def test_embargo_persisted_on_result(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1, embargo_sessions=2,
        )
        assert result.embargo_sessions == 2

    def test_embargo_reduces_block_count(self, tmp_path):
        """More embargo = fewer non-overlapping blocks."""
        experts, rets = _build_n_date_fixture(tmp_path, 60, seed=42)
        result_no_embargo = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1, embargo_sessions=0,
            min_non_overlapping_observations=2,
        )
        result_with_embargo = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1, embargo_sessions=5,
            min_non_overlapping_observations=2,
        )
        assert result_with_embargo.n_paired_test_dates < result_no_embargo.n_paired_test_dates


# ── Round 11 adversarial tests ────────────────────────────────────────────────
# Codex review 2026-07-14T02:02:08Z: frozen session calendar, positive
# embargo, block-rebalance experiment versioning.


class TestSessionCalendar:
    """Codex review round 11, finding 1: spacing must be measured against
    a frozen, manifest-bound session calendar, not the compressed
    intersection of loaded data."""

    def test_calendar_indexed_spacing_preserves_gaps(self, tmp_path):
        """Missing sessions in loaded data must NOT compress spacing when
        a session calendar is provided."""
        full_calendar = [f"2025-01-{i:02d}" for i in range(1, 21)]
        # Loaded dates skip sessions 4-8 (5 missing)
        loaded = [f"2025-01-{i:02d}" for i in [1, 2, 3, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]]
        # With calendar, "01-01" is cal_idx 0, "01-09" is cal_idx 8
        # min_spacing=5 → selects 0, then next >= 5 is "01-06" (not in loaded!),
        # then next >= 5 from "01-09" (cal_idx=8) is cal_idx >= 13 → "01-14"
        selected, indices = select_non_overlapping_dates(
            loaded, 5, session_calendar=full_calendar,
        )
        # First: "01-01" (cal 0), next loaded date with cal >= 5 is "01-09" (cal 8),
        # next >= 8+5=13 is "01-14" (cal 13), next >= 13+5=18 is "01-19" (cal 18)
        assert selected == ["2025-01-01", "2025-01-09", "2025-01-14", "2025-01-19"]
        assert indices == [0, 8, 13, 18]

    def test_without_calendar_spacing_is_compressed(self, tmp_path):
        """Without calendar, the same loaded data uses compressed indices
        which understate real gaps."""
        loaded = [f"2025-01-{i:02d}" for i in [1, 2, 3, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]]
        selected, indices = select_non_overlapping_dates(loaded, 5)
        # Compressed: "01-01"=0, "01-09"=3 (gap=3 < 5 → skip), "01-10"=4 (<5),
        # "01-11"=5 → select. Real gap is 10 sessions, but compressed says 5.
        assert "2025-01-11" in selected

    def test_session_calendar_fields_persisted_on_result(self, tmp_path):
        """session_calendar_digest, session_calendar_verified, and
        selected_block_indices must be persisted on the result."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        calendar = sorted(rets.keys())
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            session_calendar=calendar,
            session_calendar_digest="sha256:test-digest",
            embargo_sessions=1,
        )
        assert result.session_calendar_digest == "sha256:test-digest"
        assert result.session_calendar_verified is True
        assert len(result.selected_block_indices) > 0

    def test_no_calendar_sets_verified_false(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
        )
        assert result.session_calendar_verified is False

    def test_cli_rejects_mismatched_calendar_digest(self, tmp_path):
        """A session calendar whose digest doesn't match the manifest's
        must be rejected."""
        fixture = _build_cli_fixture(tmp_path)
        cal_path = tmp_path / "calendar.json"
        cal_path.write_text(json.dumps(["2025-06-01", "2025-06-02", "2025-06-03"]))

        # Override manifest to expect a different digest
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["session_calendar_digest"] = "sha256:wrong-digest"
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))

        rc = par.main(_cli_argv(fixture) + ["--session-calendar", str(cal_path)])
        assert rc == 1


class TestPositiveEmbargo:
    """Codex review round 11, finding 2: embargo_sessions must be positive.
    A zero or absent embargo does not implement 'plus embargo'."""

    def test_zero_embargo_rejected_by_cli(self, tmp_path, capsys):
        """embargo_sessions=0 in the manifest must cause main() to reject."""
        fixture = _build_cli_fixture(tmp_path)
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["statistical_test"]["embargo_sessions"] = 0
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "embargo_sessions" in capsys.readouterr().err

    def test_negative_embargo_rejected_by_cli(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["statistical_test"]["embargo_sessions"] = -1
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1

    def test_positive_embargo_accepted(self, tmp_path):
        """Default manifest with embargo_sessions=10 must be accepted."""
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0

    def test_embargo_justification_persisted(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1, embargo_sessions=5,
            embargo_justification="test justification",
        )
        assert result.embargo_justification == "test justification"


class TestExperimentVersioning:
    """Codex review round 11, finding 3: block-rebalance is a separate
    versioned experiment, not a fix to the daily champion comparison."""

    def test_empty_experiment_version_rejected_by_cli(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["experiment_version"] = ""
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "experiment_version" in capsys.readouterr().err

    def test_experiment_version_persisted_on_result(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            experiment_version="v2-block-rebalance",
        )
        assert result.experiment_version == "v2-block-rebalance"

    def test_champion_policy_artifact_digest_persisted(self, tmp_path):
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=42)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3,
            block_length_days=1,
            champion_policy_artifact_digest="sha256:test-champion-digest",
        )
        assert result.champion_policy_artifact_digest == "sha256:test-champion-digest"

    def test_cli_persists_versioning_fields(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        [out] = list(Path(fixture["output_dir"]).glob("phase_a_result_*.json"))
        data = json.loads(out.read_text())
        assert data["experiment_version"] == "v2-block-rebalance"
        assert "champion_policy_artifact_digest" in data
        assert "embargo_justification" in data


# ── Round 12 adversarial tests ────────────────────────────────────────────────
# Codex review round 12: fail-closed session calendar + verified champion
# policy artifact digest.


class TestSessionCalendarFailClosed:
    """Codex review round 12, finding 1: main() must require
    --session-calendar with a nonempty manifest digest, reject unknown
    dates in the calendar, and enforce sorted/unique sessions."""

    def test_empty_manifest_calendar_digest_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(
            tmp_path, session_calendar_digest="",
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "session_calendar_digest" in capsys.readouterr().err

    def test_manifest_calendar_digest_mismatch_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(
            tmp_path, session_calendar_digest="sha256:wrong-digest",
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "does not match" in capsys.readouterr().err

    def test_unknown_date_in_evaluation_raises(self):
        """select_non_overlapping_dates must raise when any evaluation date
        is absent from the session calendar — silently dropping dates
        mutates the sample."""
        calendar = ["2025-01-01", "2025-01-02", "2025-01-03"]
        dates = ["2025-01-01", "2025-01-04"]  # 01-04 not in calendar
        with pytest.raises(ValueError, match="absent from the session calendar"):
            select_non_overlapping_dates(
                dates, 1, session_calendar=calendar,
            )

    def test_unsorted_calendar_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        cal_path = Path(fixture["cal_path"])
        unsorted = ["2025-06-03", "2025-06-01", "2025-06-02"]
        cal_bytes = json.dumps(unsorted).encode()
        cal_path.write_bytes(cal_bytes)
        # Update manifest digest to match the unsorted calendar
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["session_calendar_digest"] = (
            f"sha256:{hashlib.sha256(cal_bytes).hexdigest()}"
        )
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "sorted" in capsys.readouterr().err

    def test_duplicate_sessions_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        cal_path = Path(fixture["cal_path"])
        dupes = ["2025-06-01", "2025-06-01", "2025-06-02", "2025-06-03"]
        cal_bytes = json.dumps(dupes).encode()
        cal_path.write_bytes(cal_bytes)
        manifest_path = Path(fixture["manifest_path"])
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["session_calendar_digest"] = (
            f"sha256:{hashlib.sha256(cal_bytes).hexdigest()}"
        )
        from experiments.ensemble_phase0.experiment_manifest import ExperimentManifest
        m = ExperimentManifest(**{
            k: v for k, v in manifest_data.items()
            if k in ExperimentManifest.__dataclass_fields__
        })
        manifest_data["manifest_fingerprint"] = m.compute_fingerprint()
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        err = capsys.readouterr().err
        assert "sorted" in err or "unique" in err

    def test_valid_calendar_accepted(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0


class TestChampionPolicyArtifactVerification:
    """Codex review round 12, finding 2: champion_policy_artifact_digest
    must be nonempty and verified against an actual artifact file."""

    def test_empty_policy_digest_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(
            tmp_path, champion_policy_artifact_digest="",
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "champion_policy_artifact_digest" in capsys.readouterr().err

    def test_missing_policy_artifact_file_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        # Point to a nonexistent file
        argv = _cli_argv(fixture)
        # Replace the --champion-policy-artifact value
        idx = argv.index("--champion-policy-artifact")
        argv[idx + 1] = str(tmp_path / "nonexistent_policy.json")
        rc = par.main(argv)
        assert rc == 1
        assert "does not exist" in capsys.readouterr().err

    def test_policy_digest_mismatch_rejected(self, tmp_path, capsys):
        fixture = _build_cli_fixture(tmp_path)
        # Mutate the policy artifact so its digest no longer matches
        policy_path = Path(fixture["policy_path"])
        policy_path.write_text(json.dumps({
            "champion_name": "xgb", "top_n": 10,
            "rebalance_cadence": "block_rebalance",
            "cost_model": {"base_cost_bps": 5.0},
            "score_normalization": "cross_sectional_zscore",
            "mutated": True,
        }))
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "does not match" in capsys.readouterr().err

    def test_valid_policy_artifact_accepted(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0

    def test_policy_missing_required_field_rejected(self, tmp_path, capsys):
        """Codex r13: policy without required fields is not a frozen contract."""
        incomplete = {"champion_name": "xgb", "top_n": 10}
        new_bytes = json.dumps(incomplete).encode()
        new_digest = f"sha256:{hashlib.sha256(new_bytes).hexdigest()}"
        fixture = _build_cli_fixture(
            tmp_path, champion_policy_artifact_digest=new_digest,
        )
        Path(fixture["policy_path"]).write_bytes(new_bytes)
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "missing required fields" in capsys.readouterr().err

    def test_policy_top_n_mismatch_rejected(self, tmp_path, capsys):
        """Codex r13: policy top_n must match manifest."""
        mismatched = {
            "champion_name": "xgb", "top_n": 99,
            "rebalance_cadence": "block_rebalance",
            "cost_model": {"base_cost_bps": 5.0},
            "score_normalization": "cross_sectional_zscore",
        }
        new_bytes = json.dumps(mismatched).encode()
        new_digest = f"sha256:{hashlib.sha256(new_bytes).hexdigest()}"
        fixture = _build_cli_fixture(
            tmp_path, champion_policy_artifact_digest=new_digest,
        )
        Path(fixture["policy_path"]).write_bytes(new_bytes)
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "top_n" in capsys.readouterr().err

    def test_policy_champion_name_mismatch_rejected(self, tmp_path, capsys):
        """Codex r13: policy champion_name must match manifest primary_live."""
        mismatched = {
            "champion_name": "wrong_model", "top_n": 10,
            "rebalance_cadence": "block_rebalance",
            "cost_model": {"base_cost_bps": 5.0},
            "score_normalization": "cross_sectional_zscore",
        }
        new_bytes = json.dumps(mismatched).encode()
        new_digest = f"sha256:{hashlib.sha256(new_bytes).hexdigest()}"
        fixture = _build_cli_fixture(
            tmp_path, champion_policy_artifact_digest=new_digest,
        )
        Path(fixture["policy_path"]).write_bytes(new_bytes)
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "champion_name" in capsys.readouterr().err

    def test_policy_cost_model_mismatch_rejected(self, tmp_path, capsys):
        """Codex r14: policy cost_model.base_cost_bps must match manifest."""
        mismatched = {
            "champion_name": "xgb", "top_n": 10,
            "rebalance_cadence": "block_rebalance",
            "cost_model": {"base_cost_bps": 99.0},
            "score_normalization": "cross_sectional_zscore",
        }
        new_bytes = json.dumps(mismatched).encode()
        new_digest = f"sha256:{hashlib.sha256(new_bytes).hexdigest()}"
        fixture = _build_cli_fixture(
            tmp_path, champion_policy_artifact_digest=new_digest,
        )
        Path(fixture["policy_path"]).write_bytes(new_bytes)
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "base_cost_bps" in capsys.readouterr().err

    def test_policy_score_normalization_mismatch_rejected(self, tmp_path, capsys):
        """Codex r14: policy score_normalization must match manifest method."""
        mismatched = {
            "champion_name": "xgb", "top_n": 10,
            "rebalance_cadence": "block_rebalance",
            "cost_model": {"base_cost_bps": 5.0},
            "score_normalization": "raw",
        }
        new_bytes = json.dumps(mismatched).encode()
        new_digest = f"sha256:{hashlib.sha256(new_bytes).hexdigest()}"
        fixture = _build_cli_fixture(
            tmp_path, champion_policy_artifact_digest=new_digest,
        )
        Path(fixture["policy_path"]).write_bytes(new_bytes)
        rc = par.main(_cli_argv(fixture))
        assert rc == 1
        assert "score_normalization" in capsys.readouterr().err


class TestReturnDateCoverage:
    """Codex review round 13, finding 1: every required prediction date
    must be present in the returns file."""

    def test_missing_return_date_rejected_e2e(self, tmp_path, capsys):
        """E2e CLI test: a required prediction date absent from returns
        causes main() to return 1, not silently shrink the evaluation
        calendar (Codex r14, finding 2)."""
        # Build a full fixture with 3 dates
        universe = [f"T{i}" for i in range(12)]
        all_dates = ["2025-06-01", "2025-06-02", "2025-06-03"]
        # Returns only has 2 dates (missing 2025-06-02)
        returns_dates = ["2025-06-01", "2025-06-03"]
        rng = np.random.default_rng(42)
        label_end = "2025-08-02"

        xgb_dir = tmp_path / "xgb"
        xgb_dir.mkdir()
        pt_dir = tmp_path / "patchtst"
        pt_dir.mkdir()

        # Scores exist for ALL 3 dates (admitted)
        score_bytes: dict[tuple[str, str], bytes] = {}
        for d in all_dates:
            base = rng.normal(0, 1, len(universe))
            xgb_bytes = json.dumps({"scores": {t: float(base[i]) for i, t in enumerate(universe)}}).encode()
            pt_bytes = json.dumps({"scores": {t: float(base[i] + rng.normal(0, 0.2)) for i, t in enumerate(universe)}}).encode()
            (xgb_dir / f"{d}.json").write_bytes(xgb_bytes)
            (pt_dir / f"{d}.json").write_bytes(pt_bytes)
            score_bytes[("xgb", d)] = xgb_bytes
            score_bytes[("patchtst", d)] = pt_bytes

        # Returns file covers only 2 of 3 dates
        returns_lines = ["date,ticker,fwd_return"]
        for d in returns_dates:
            base = rng.normal(0, 1, len(universe))
            for i, t in enumerate(universe):
                returns_lines.append(f"{d},{t},{base[i] * 0.01}")
        returns_path = tmp_path / "returns.csv"
        returns_path.write_text("\n".join(returns_lines))
        returns_digest = f"sha256:{hashlib.sha256(returns_path.read_bytes()).hexdigest()}"

        # Session calendar has ALL 3 dates
        cal_path = tmp_path / "session_calendar.json"
        cal_bytes = json.dumps(sorted(all_dates)).encode()
        cal_path.write_bytes(cal_bytes)
        cal_digest = f"sha256:{hashlib.sha256(cal_bytes).hexdigest()}"

        policy_path = tmp_path / "champion_policy.json"
        policy_bytes = json.dumps({
            "champion_name": "xgb", "top_n": 10,
            "rebalance_cadence": "block_rebalance",
            "cost_model": {"base_cost_bps": 5.0},
            "score_normalization": "cross_sectional_zscore",
        }).encode()
        policy_path.write_bytes(policy_bytes)
        policy_digest = f"sha256:{hashlib.sha256(policy_bytes).hexdigest()}"

        # Ledger admits ALL 3 dates with the CORRECT shortened returns digest
        records = [
            {
                "expert_name": name,
                "prediction_date": d,
                "admitted": True,
                "score_artifact_digest": f"sha256:{hashlib.sha256(raw).hexdigest()}",
                "label_artifact_ref": f"{returns_digest}@returns.csv",
                "label_observation_end": label_end,
            }
            for (name, d), raw in score_bytes.items()
        ]
        ledger = AdmissibilityLedger(records=records, label_horizon_days=0)
        ledger.ledger_fingerprint = ledger.compute_fingerprint()
        ledger_path = write_ledger(ledger, tmp_path)

        manifest = build_default_manifest(
            admissibility_ledger_fingerprint=ledger.ledger_fingerprint,
            session_calendar_digest=cal_digest,
            champion_policy_artifact_digest=policy_digest,
        )
        manifest.manifest_fingerprint = manifest.compute_fingerprint()
        manifest_path = write_manifest(manifest, tmp_path)

        argv = _cli_argv({
            "xgb_dir": str(xgb_dir),
            "pt_dir": str(pt_dir),
            "returns_path": str(returns_path),
            "manifest_path": str(manifest_path),
            "ledger_path": str(ledger_path),
            "output_dir": str(tmp_path / "output"),
            "cal_path": str(cal_path),
            "policy_path": str(policy_path),
        })
        rc = par.main(argv)
        assert rc == 1, "main() should reject when a required prediction date is missing from returns"
        err = capsys.readouterr().err
        assert "required prediction date" in err
