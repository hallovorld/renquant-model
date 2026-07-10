"""Fee-aware gate (D-C8b): hand-computed arithmetic, baselines, soft-consume."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from renquant_model_crypto import fee_gate
from renquant_model_crypto.fee_gate import (
    BTC_TIMING_LOOKBACK_CALENDAR_DAYS,
    CRYPTO_TAKER_FEE_BPS_DEFAULT,
    btc_buy_and_hold_net,
    btc_timing_rule_net,
    cost_model,
    crypto_promotion_diagnostic,
    default_crypto_cost_spec,
    simulate_topk_net,
)


def _closes_long(data: dict[str, list[float]], dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for tkr, vals in data.items():
        for d, v in zip(dates, vals):
            rows.append({"date": d, "ticker": tkr, "close": float(v)})
    return pd.DataFrame(rows)


class TestDefaults:
    def test_taker_default_is_guess_25bps(self) -> None:
        # [GUESS: Stage-0 battery verifies] — the default must be 25 bps
        # taker, fee-only, and stamped as a GUESS in provenance.
        spec = default_crypto_cost_spec()
        assert spec.fee_bps == CRYPTO_TAKER_FEE_BPS_DEFAULT == 25.0
        assert cost_model.per_side_cost_bps(spec) == 25.0
        prov = fee_gate._spec_provenance(spec)
        assert prov["fee_default_status"] == "GUESS_stage0_verifies"
        assert prov["round_trip_cost_bps"] == 50.0

    def test_timing_lookback_frozen(self) -> None:
        assert BTC_TIMING_LOOKBACK_CALENDAR_DAYS == 20


class TestSimulateTopkHandComputed:
    def test_two_asset_rotation(self) -> None:
        """Full hand-computed replay: 4 days, top-1, rebalance every 2 days.

        A compounds +10%/day; B flat. Scores pick A at d1, B at d3.
        rate = 25 bps. Hand math:
          d1: gross 0; enter A from cash -> traded 1.0; net -0.0025
          d2: gross +10% (hold A); traded 0
          d3: gross +10%; rotate A->B -> traded 2.0; net 0.10 - 0.005 = 0.095
          d4: gross 0 (B flat)
        gross_total = 1.1 * 1.1 - 1 = 0.21
        net_total = 0.9975 * 1.1 * 1.095 - 1 = 0.20148875...
        total_cost_fraction = 0.0025 * 3 = 0.0075
        """
        dates = pd.date_range("2025-03-01", periods=4, freq="D")
        closes = _closes_long(
            {"A": [100.0, 110.0, 121.0, 133.1], "B": [50.0, 50.0, 50.0, 50.0]}, dates)
        scores = pd.DataFrame({
            "date": list(dates),
            "ticker": ["A", "A", "B", "B"],
            "score": [1.0, 1.0, 1.0, 1.0],
        })
        # give both names a score on every date; A wins d1, B wins d3
        scores = pd.concat([scores, pd.DataFrame({
            "date": list(dates),
            "ticker": ["B", "B", "A", "A"],
            "score": [0.5, 0.5, 0.5, 0.5],
        })], ignore_index=True)
        spec = cost_model.CostModelSpec(fee_bps=25.0)
        out = simulate_topk_net(scores, closes, spec, top_k=1, rebalance_days=2)

        assert out["gross_returns"] == pytest.approx([0.0, 0.10, 0.10, 0.0])
        assert out["traded_fractions"] == pytest.approx([1.0, 0.0, 2.0, 0.0])
        assert out["net_returns"] == pytest.approx([-0.0025, 0.10, 0.095, 0.0])
        assert out["gross_total_return"] == pytest.approx(0.21)
        assert out["net_total_return"] == pytest.approx(0.9975 * 1.1 * 1.095 - 1.0)
        assert out["total_cost_fraction"] == pytest.approx(0.0075)
        assert out["n_rebalances"] == 2
        assert out["cost_spec"]["per_side_cost_bps"] == 25.0

    def test_weight_drift_between_rebalances(self) -> None:
        """Two names held equal-weight; one doubles -> drifted weights, and
        the next rebalance turnover is measured against the DRIFTED weights.

        d1: enter {A:0.5, B:0.5}, traded 1.0.
        d2: A +100%, B 0% -> gross 0.5; drifted weights {A: 2/3, B: 1/3}.
        d3: flat day; rebalance back to {A:0.5, B:0.5}:
            traded = |0.5-2/3| + |0.5-1/3| = 1/3.
        """
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        closes = _closes_long({"A": [100, 200, 200], "B": [100, 100, 100]}, dates)
        scores = _closes_long({"A": [1, 1, 1], "B": [1, 1, 1]}, dates).rename(
            columns={"close": "score"})
        spec = cost_model.CostModelSpec(fee_bps=0.0)
        out = simulate_topk_net(scores, closes, spec, top_k=2, rebalance_days=2)
        assert out["gross_returns"] == pytest.approx([0.0, 0.5, 0.0])
        assert out["traded_fractions"] == pytest.approx([1.0, 0.0, 1.0 / 3.0])

    def test_missing_bar_for_held_name_fails_closed(self) -> None:
        # A (held, top-scored) misses its d2 bar while B keeps the date
        # alive in the close matrix -> hard error, never a silent zero-fill.
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        closes = _closes_long({"A": [100, np.nan, 120], "B": [50, 50, 50]}, dates)
        scores = _closes_long({"A": [2, 2, 2], "B": [1, 1, 1]}, dates).rename(
            columns={"close": "score"})
        with pytest.raises(ValueError, match="missing close"):
            simulate_topk_net(scores, closes, cost_model.CostModelSpec(), top_k=1,
                              rebalance_days=1)

    def test_scored_date_absent_from_closes_fails_closed(self) -> None:
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        closes = _closes_long({"A": [100, 110, 120]}, dates[:2])
        scores = _closes_long({"A": [1, 1, 1]}, dates).rename(columns={"close": "score"})
        with pytest.raises(ValueError, match="lack bars"):
            simulate_topk_net(scores, closes, cost_model.CostModelSpec(), top_k=1,
                              rebalance_days=1)

    def test_invalid_params_rejected(self) -> None:
        dates = pd.date_range("2025-03-01", periods=2, freq="D")
        closes = _closes_long({"A": [1, 1]}, dates)
        scores = _closes_long({"A": [1, 1]}, dates).rename(columns={"close": "score"})
        with pytest.raises(ValueError):
            simulate_topk_net(scores, closes, cost_model.CostModelSpec(), top_k=0)


class TestBtcBaselines:
    def test_buy_and_hold_hand_computed(self) -> None:
        # closes 100 -> 110 -> 121; 25 bps entry, no exit cost on final mark.
        # gross [0, .1, .1]; net [-0.0025, .1, .1];
        # net_total = 0.9975 * 1.21 - 1 = 0.206975
        idx = pd.date_range("2025-01-01", periods=3, freq="D")
        out = btc_buy_and_hold_net(pd.Series([100.0, 110.0, 121.0], index=idx),
                                   cost_model.CostModelSpec(fee_bps=25.0))
        assert out["gross_total_return"] == pytest.approx(0.21)
        assert out["net_total_return"] == pytest.approx(0.9975 * 1.21 - 1.0)

    def test_timing_rule_warmup_flat_then_long(self) -> None:
        # close = 100 + i, 30 days. Days 0-19 lack the exact 20d lookback ->
        # FLAT (frozen rule). Day 20: 120 > 100 -> long from close of day 20
        # (one switch, per-side cost once). Earns days 21..29.
        idx = pd.date_range("2025-01-01", periods=30, freq="D")
        close = pd.Series(100.0 + np.arange(30), index=idx)
        out = btc_timing_rule_net(close, cost_model.CostModelSpec(fee_bps=25.0))
        assert out["n_switches"] == 1
        gross_expected = 1.0
        for i in range(21, 30):
            gross_expected *= (100.0 + i) / (100.0 + i - 1)
        assert out["gross_total_return"] == pytest.approx(gross_expected - 1.0)
        # net: switch day (day 20) charged 25 bps on the flat day's 0 return
        net_expected = (1.0 - 0.0025) * gross_expected - 1.0
        assert out["net_total_return"] == pytest.approx(net_expected)

    def test_timing_rule_never_long_in_downtrend(self) -> None:
        idx = pd.date_range("2025-01-01", periods=50, freq="D")
        close = pd.Series(1000.0 - 5.0 * np.arange(50), index=idx)
        out = btc_timing_rule_net(close, cost_model.CostModelSpec(fee_bps=25.0))
        assert out["n_switches"] == 0
        assert out["gross_total_return"] == pytest.approx(0.0)
        assert out["net_total_return"] == pytest.approx(0.0)


class TestPromotionDiagnostic:
    def test_bar_met_when_beating_both_baselines(self) -> None:
        d = crypto_promotion_diagnostic(
            {"net_total_return": 0.30, "gross_total_return": 0.35},
            {"net_total_return": 0.20},
            {"net_total_return": 0.25},
        )
        assert d["wf_promotion_bar_met"] is True
        assert d["beats_btc_buy_and_hold_net"] is True
        assert d["beats_btc_timing_net"] is True

    def test_bar_not_met_when_tying_buy_and_hold(self) -> None:
        # A tie does NOT pass — superiority framing, never non-inferiority.
        d = crypto_promotion_diagnostic(
            {"net_total_return": 0.20, "gross_total_return": 0.25},
            {"net_total_return": 0.20},
        )
        assert d["wf_promotion_bar_met"] is False

    def test_diagnostic_never_an_enable_path(self) -> None:
        d = crypto_promotion_diagnostic(
            {"net_total_return": 1.0, "gross_total_return": 1.0},
            {"net_total_return": 0.0},
            {"net_total_return": 0.0},
        )
        assert d["diagnostic_only"] is True
        assert d["enable_path"] is False
        assert "stage_2_5" in d["owner_of_enablement"]
        assert d["evidence_tier"] == "tier1_exploratory_survivor_only"

    def test_gross_pass_net_fail_is_a_fail(self) -> None:
        # RFC §4.4: a crypto model that passes gross and fails net is a FAIL.
        d = crypto_promotion_diagnostic(
            {"net_total_return": 0.10, "gross_total_return": 0.50},
            {"net_total_return": 0.15},
        )
        assert d["wf_promotion_bar_met"] is False


class TestSoftConsume:
    def test_cost_model_resolution_recorded(self) -> None:
        prov = fee_gate._spec_provenance(default_crypto_cost_spec())
        if fee_gate.USING_COMMON_COST_MODEL:
            assert prov["cost_model_impl"] == "renquant_common.cost_model"
        else:
            assert prov["cost_model_impl"] == "renquant_model_crypto._cost_model_fallback"

    def test_fallback_parity_with_common(self) -> None:
        """When renquant-common ships cost_model (D-C8a), the frozen local
        fallback must agree with it on a behavior grid — bit-for-bit."""
        try:
            from renquant_common import cost_model as common_cm
        except ImportError:
            pytest.skip("renquant-common without cost_model (D-C8a not merged) — fallback-only env")
        from renquant_model_crypto import _cost_model_fallback as fb

        for fee, spread, slip, rnd in [(25, 0, 0, 0), (25, 10, 5, 2), (0, 3, 0, 1), (15, 8, 12, 0)]:
            s_common = common_cm.CostModelSpec(fee, spread, slip, rnd)
            s_fb = fb.CostModelSpec(fee, spread, slip, rnd)
            assert common_cm.per_side_cost_bps(s_common) == fb.per_side_cost_bps(s_fb)
            assert common_cm.round_trip_cost_bps(s_common) == fb.round_trip_cost_bps(s_fb)
        prev = {"A": 0.6, "B": 0.4}
        nxt = {"A": 0.1, "C": 0.9}
        tb_c = common_cm.turnover_breakdown(prev, nxt)
        tb_f = fb.turnover_breakdown(prev, nxt)
        assert (tb_c.buy_fraction, tb_c.sell_fraction) == (tb_f.buy_fraction, tb_f.sell_fraction)
        spec_c = common_cm.CostModelSpec(fee_bps=25.0)
        spec_f = fb.CostModelSpec(fee_bps=25.0)
        assert common_cm.rebalance_cost_fraction(prev, nxt, spec_c) == \
            fb.rebalance_cost_fraction(prev, nxt, spec_f)
        gross = [0.01, -0.02, 0.005]
        traded = [1.0, 0.0, 2.0]
        assert common_cm.apply_costs_to_period_returns(gross, traded, spec_c) == \
            fb.apply_costs_to_period_returns(gross, traded, spec_f)
        assert common_cm.realized_traded_fraction(0.8, 0.25) == fb.realized_traded_fraction(0.8, 0.25)
