"""Tests for Phase A discovery runner."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from experiments.ensemble_phase0.phase_a_runner import (
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
    result_to_dict,
    run_phase_a,
    select_non_overlapping_dates,
    top_n_selection,
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
        )
        assert result.test_method == TEST_METHOD_NON_OVERLAPPING
        assert result.n_test_dates == 10
        assert result.verdict in ("L1_BEATS_CHAMPION", "CHAMPION_RETAINED", "INCONCLUSIVE")

    def test_cost_bps_is_applied_and_recorded(self, experts):
        zero_cost = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5, cost_bps=0.0)
        high_cost = run_phase_a(experts, FORWARD_RETURNS, champion_name="xgb", top_n=5, cost_bps=500.0)
        assert zero_cost.cost_bps == 0.0
        assert high_cost.cost_bps == 500.0
        assert high_cost.l1.mean_net_return < zero_cost.l1.mean_net_return


class TestVerdictLogic:
    def test_champion_retained_when_l1_worse(self):
        champ = StrategyResult(name="champ", mean_return=0.10, daily_returns=[0.10] * 10)
        l1 = StrategyResult(name="l1", mean_return=0.05, daily_returns=[0.05] * 10)
        result = PhaseAResult(champion=champ, l1=l1)
        result.delta_return = l1.mean_return - champ.mean_return
        assert result.delta_return < 0
