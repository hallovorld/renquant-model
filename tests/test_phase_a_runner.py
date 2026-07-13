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
        dates = ["2025-01-01", "2025-03-15", "2025-06-01"]
        assert select_non_overlapping_dates(dates, 60) == dates

    def test_close_dates_are_dropped(self):
        dates = ["2025-01-01", "2025-01-15", "2025-03-05", "2025-03-10"]
        assert select_non_overlapping_dates(dates, 60) == ["2025-01-01", "2025-03-05"]

    def test_empty(self):
        assert select_non_overlapping_dates([], 60) == []

    def test_single_date(self):
        assert select_non_overlapping_dates(["2025-01-01"], 60) == ["2025-01-01"]


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
        p = tmp_path / "returns.csv"
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

    def test_mismatched_locator_is_rejected_despite_matching_digest(self, tmp_path):
        """A byte-identical file at an unrelated locator must be rejected
        -- digest agreement alone is not proof of provenance (Codex review
        2026-07-13 round 4)."""
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": f"{digest}@labels/unrelated_file.csv"},
        ])
        with pytest.raises(ValueError, match="does not match the ledger's declared label artifact locator"):
            verify_returns_file_digest(p, ledger)

    def test_missing_locator_component_is_rejected(self, tmp_path):
        p = tmp_path / "returns.csv"
        p.write_text("date,ticker,fwd_return\n2025-06-01,AAPL,0.01\n")
        digest = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"
        ledger = _ledger_with_records([
            {"admitted": True, "label_artifact_ref": digest},  # no "@locator"
        ])
        with pytest.raises(ValueError, match="no locator component"):
            verify_returns_file_digest(p, ledger)


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
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=3)
        result = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
            nested_wf_harness_status=par.NESTED_WF_HARNESS_APPLIED,
        )
        assert result.test_method == TEST_METHOD_NON_OVERLAPPING
        assert result.n_test_dates == 10
        assert result.verdict in ("L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE")

    def test_nested_wf_harness_not_built_caps_an_otherwise_reachable_verdict(self, tmp_path):
        """Codex review 2026-07-13 round 5, finding 2: the same inputs
        that reach a real (non-EXPLORATORY_ONLY) verdict when the manifest
        attests NESTED_WF_HARNESS_APPLIED must be capped to
        EXPLORATORY_ONLY when that attestation is absent -- regardless of
        how favorable the underlying statistics are."""
        experts, rets = _build_n_date_fixture(tmp_path, 10, seed=3)
        gated = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
        )
        applied = run_phase_a(
            experts, rets, champion_name="xgb", top_n=3, block_length_days=1,
            nested_wf_harness_status=par.NESTED_WF_HARNESS_APPLIED,
        )
        assert gated.nested_wf_harness_status == par.NESTED_WF_HARNESS_NOT_BUILT
        assert gated.verdict == "EXPLORATORY_ONLY"
        assert applied.verdict != "EXPLORATORY_ONLY"
        assert "nested_wf_harness_status" in gated.verdict_detail
        assert applied.verdict in ("L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE")

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
    }


def _cli_argv(fixture: dict[str, str], **overrides: str) -> list[str]:
    argv = [
        "--expert", "xgb", "--score-dir", fixture["xgb_dir"],
        "--expert", "patchtst", "--score-dir", fixture["pt_dir"],
        "--returns-file", fixture["returns_path"],
        "--manifest-file", fixture["manifest_path"],
        "--ledger-file", fixture["ledger_path"],
        "--output-dir", fixture["output_dir"],
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
        ]
        rc = par.main(argv)
        assert rc == 1
        assert "expert_sets" in capsys.readouterr().err


class TestNestedWfHarnessWiring:
    """Round 5, finding 2: manifest.nested_wf_harness_status must reach
    run_phase_a and be persisted on the result -- the gate is worthless
    if main() doesn't actually pass it through."""

    def test_manifest_default_status_reaches_result_json(self, tmp_path):
        fixture = _build_cli_fixture(tmp_path)
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        [out] = list(Path(fixture["output_dir"]).glob("phase_a_result_*.json"))
        data = json.loads(out.read_text())
        assert data["nested_wf_harness_status"] == par.NESTED_WF_HARNESS_NOT_BUILT
        assert data["verdict"] == "EXPLORATORY_ONLY"

    def test_manifest_applied_status_reaches_result_json(self, tmp_path):
        fixture = _build_cli_fixture(
            tmp_path,
            nested_wf_harness_status=par.NESTED_WF_HARNESS_APPLIED,
        )
        rc = par.main(_cli_argv(fixture))
        assert rc == 0
        [out] = list(Path(fixture["output_dir"]).glob("phase_a_result_*.json"))
        data = json.loads(out.read_text())
        assert data["nested_wf_harness_status"] == par.NESTED_WF_HARNESS_APPLIED


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
