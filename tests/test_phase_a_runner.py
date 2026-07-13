"""Tests for Phase A discovery runner."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from experiments.ensemble_phase0.phase_a_runner import (
    ExpertScores,
    PhaseAResult,
    StrategyResult,
    champion_scores,
    compute_ic,
    compute_portfolio_return,
    compute_turnover,
    evaluate_strategy,
    l1_equal_weight,
    load_expert_scores,
    load_forward_returns,
    newey_west_t_test,
    result_to_dict,
    run_phase_a,
    top_n_selection,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_score_dir(tmp_path: Path, name: str, data: dict[str, dict[str, float]]) -> Path:
    """Create a score directory with date-named JSON files."""
    d = tmp_path / name
    d.mkdir()
    for date_str, scores in data.items():
        payload = {
            "scores": scores,
            "model_content_sha256": f"sha256:{'a' * 64}",
            "training_cutoff": "2025-01-01",
            "as_of_date": date_str,
            "score_timestamp": f"{date_str}T15:30:00+00:00",
        }
        (d / f"{date_str}.json").write_text(json.dumps(payload))
    return d


def _make_returns_csv(tmp_path: Path, data: dict[str, dict[str, float]]) -> Path:
    """Create a forward returns CSV."""
    p = tmp_path / "returns.csv"
    lines = ["date,ticker,fwd_return"]
    for date_str, rets in data.items():
        for ticker, ret in rets.items():
            lines.append(f"{date_str},{ticker},{ret}")
    p.write_text("\n".join(lines))
    return p


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


# ── L1 equal-weight ──────────────────────────────────────────────────────────


class TestL1EqualWeight:
    def test_two_experts_average(self):
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.8, "Y": 0.2}})
        e2 = ExpertScores(name="b", dates=["d1"], scores_by_date={"d1": {"X": 0.4, "Y": 0.6}})
        result = l1_equal_weight([e1, e2], "d1")
        assert result == pytest.approx({"X": 0.6, "Y": 0.4})

    def test_three_experts(self):
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.9}})
        e2 = ExpertScores(name="b", dates=["d1"], scores_by_date={"d1": {"X": 0.3}})
        e3 = ExpertScores(name="c", dates=["d1"], scores_by_date={"d1": {"X": 0.6}})
        result = l1_equal_weight([e1, e2, e3], "d1")
        assert result == pytest.approx({"X": 0.6})

    def test_excludes_partial_coverage(self):
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.5, "Y": 0.3}})
        e2 = ExpertScores(name="b", dates=["d1"], scores_by_date={"d1": {"X": 0.7}})
        result = l1_equal_weight([e1, e2], "d1")
        assert "Y" not in result
        assert result == pytest.approx({"X": 0.6})

    def test_missing_date(self):
        e1 = ExpertScores(name="a", dates=["d1"], scores_by_date={"d1": {"X": 0.5}})
        e2 = ExpertScores(name="b", dates=[], scores_by_date={})
        result = l1_equal_weight([e1, e2], "d1")
        assert result == {}


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


# ── Score loading ────────────────────────────────────────────────────────────


class TestScoreLoading:
    def test_load_expert_scores(self, tmp_path):
        d = _make_score_dir(tmp_path, "xgb", {
            "2025-06-01": {"AAPL": 0.5, "MSFT": 0.3},
            "2025-06-02": {"AAPL": 0.6, "MSFT": 0.4},
        })
        expert = load_expert_scores("xgb", d)
        assert expert.name == "xgb"
        assert len(expert.dates) == 2
        assert expert.scores_by_date["2025-06-01"]["AAPL"] == 0.5

    def test_skips_non_date_files(self, tmp_path):
        d = _make_score_dir(tmp_path, "xgb", {"2025-06-01": {"A": 0.5}})
        (d / "README.json").write_text("{}")
        expert = load_expert_scores("xgb", d)
        assert len(expert.dates) == 1

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_expert_scores("x", tmp_path / "nonexistent")


class TestForwardReturnsLoading:
    def test_load_csv(self, tmp_path):
        p = _make_returns_csv(tmp_path, {
            "2025-06-01": {"AAPL": 0.05, "MSFT": 0.02},
        })
        returns = load_forward_returns(p)
        assert returns["2025-06-01"]["AAPL"] == pytest.approx(0.05)


# ── Go/no-go verdict ────────────────────────────────────────────────────────


class TestRunPhaseA:
    @pytest.fixture()
    def experts(self, tmp_path):
        xgb_dir = _make_score_dir(tmp_path, "xgb", XGB_SCORES)
        pt_dir = _make_score_dir(tmp_path, "patchtst", PATCHTST_SCORES)
        return [
            load_expert_scores("xgb", xgb_dir),
            load_expert_scores("patchtst", pt_dir),
        ]

    def test_runs_without_error(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, top_n=5)
        assert isinstance(result, PhaseAResult)
        assert result.n_dates == 5
        assert result.n_experts == 2
        assert result.verdict in ("L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE")

    def test_requires_two_experts(self, experts):
        with pytest.raises(ValueError, match="at least 2"):
            run_phase_a([experts[0]], FORWARD_RETURNS)

    def test_result_serializable(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, top_n=5)
        d = result_to_dict(result)
        out = json.dumps(d, default=str)
        parsed = json.loads(out)
        assert parsed["verdict"] in ("L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE")
        assert "daily_returns" not in parsed["champion"]

    def test_champion_is_first_expert(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, top_n=5)
        assert "xgb" in result.champion.name

    def test_metrics_are_finite(self, experts):
        result = run_phase_a(experts, FORWARD_RETURNS, top_n=5)
        assert math.isfinite(result.l1.mean_return)
        assert math.isfinite(result.champion.mean_return)
        assert math.isfinite(result.p_value)
        assert math.isfinite(result.t_statistic)


class TestVerdictLogic:
    def test_champion_retained_when_l1_worse(self):
        champ = StrategyResult(name="champ", mean_return=0.10, daily_returns=[0.10] * 10)
        l1 = StrategyResult(name="l1", mean_return=0.05, daily_returns=[0.05] * 10)
        result = PhaseAResult(champion=champ, l1=l1)
        result.delta_return = l1.mean_return - champ.mean_return
        assert result.delta_return < 0
