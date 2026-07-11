"""Fee-aware gate (D-C8b): delayed-fill replay hand math, lookahead
regression, measured-cost attestation gating, canonical spec identity."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# HARD dependency (model#43 r2): the crypto family fails closed without the
# shared cost primitive (renquant-common>=0.12.0, common#28). In an env whose
# sibling common predates D-C8a these tests skip — they can never fake-pass
# through a local fallback, because none exists.
pytest.importorskip(
    "renquant_common.cost_model",
    reason="renquant-common>=0.12.0 (D-C8a, common#28) required — no local fallback by design",
)

from renquant_model_crypto import fee_gate  # noqa: E402
from renquant_model_crypto.fee_gate import (  # noqa: E402
    BTC_TIMING_LOOKBACK_CALENDAR_DAYS,
    CRYPTO_TAKER_FEE_BPS_DEFAULT,
    NET_VERDICT_WITHHELD,
    btc_buy_and_hold_net,
    btc_timing_rule_net,
    cost_model,
    crypto_promotion_diagnostic,
    default_crypto_cost_spec,
    net_of_cost_wf_evaluation,
    simulate_topk_net,
    validate_cost_attestation,
)


def _closes_long(data: dict[str, list[float]], dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for tkr, vals in data.items():
        for d, v in zip(dates, vals):
            rows.append({"date": d, "ticker": tkr, "close": float(v)})
    return pd.DataFrame(rows)


VALID_ATTESTATION = {
    "source": "stage0_battery",
    "measured_at": "2026-07-09",
    "evidence_ref": "synthetic Stage-0 battery report (test fixture)",
}


class TestHardDependency:
    def test_cost_model_is_the_shared_primitive(self) -> None:
        # No fallback exists: the gate's cost_model IS renquant_common's.
        import renquant_common.cost_model as common_cm

        assert fee_gate.cost_model is common_cm
        import renquant_model_crypto

        assert not hasattr(renquant_model_crypto, "_cost_model_fallback")

    def test_taker_default_is_guess_25bps_research_only(self) -> None:
        # [GUESS: Stage-0 battery verifies] — 25 bps taker, fee-only, and
        # never accepted as a measured net-verdict input (tests below).
        spec = default_crypto_cost_spec()
        assert spec.fee_bps == CRYPTO_TAKER_FEE_BPS_DEFAULT == 25.0
        assert cost_model.per_side_cost_bps(spec) == 25.0

    def test_spec_provenance_stamps_canonical_identity(self) -> None:
        # Cross-repo golden: must equal renquant-common's frozen digest for
        # the fee-only 25 bps spec.
        prov = fee_gate._spec_provenance(default_crypto_cost_spec(), None)
        assert prov["cost_spec_sha256"] == (
            "sha256:00db27bbca21c5292077b6d4135a12f60c952fcc5be211768f9feb8f2d825661")
        assert prov["cost_spec"] == {
            "fee_bps": 25.0, "spread_bps": 0.0, "slippage_bps": 0.0,
            "increment_rounding_bps": 0.0}
        assert prov["cost_model_fingerprint_schema_version"] == 1
        assert prov["fee_default_status"] == "GUESS_stage0_verifies"
        assert prov["cost_model_impl"] == "renquant_common.cost_model"
        # verifier flow round-trips
        rebuilt = cost_model.cost_model_spec_from_dict(prov["cost_spec"])
        assert cost_model.cost_model_content_sha256(rebuilt) == prov["cost_spec_sha256"]

    def test_timing_lookback_frozen(self) -> None:
        assert BTC_TIMING_LOOKBACK_CALENDAR_DAYS == 20


class TestCostAttestation:
    def test_valid_attestation_canonicalized(self) -> None:
        out = validate_cost_attestation(VALID_ATTESTATION)
        assert out == {
            "source": "stage0_battery",
            "measured_at": "2026-07-09",
            "evidence_ref": "synthetic Stage-0 battery report (test fixture)",
        }

    @pytest.mark.parametrize("bad", [
        {"source": "vibes", "measured_at": "2026-07-09", "evidence_ref": "x"},
        {"measured_at": "2026-07-09", "evidence_ref": "x"},
        {"source": "stage0_battery", "measured_at": "not-a-date", "evidence_ref": "x"},
        {"source": "stage0_battery", "measured_at": "2026-07-09", "evidence_ref": "  "},
        {"source": "stage0_battery", "measured_at": "2026-07-09", "evidence_ref": "x",
         "extra": 1},
        "stage0_battery",
    ])
    def test_malformed_attestation_is_hard_error(self, bad) -> None:
        with pytest.raises(ValueError):
            validate_cost_attestation(bad)

    def test_spec_without_attestation_is_hard_error_in_gate(self) -> None:
        # never a silent net verdict from an unattested spec, never a
        # silent downgrade either — the caller must choose explicitly.
        with pytest.raises(ValueError, match="without a measured attestation"):
            net_of_cost_wf_evaluation(
                pd.DataFrame({"date": []}), [], pd.DataFrame(),
                normalization_builder=None, label="fwd_20d_raw",
                spec=default_crypto_cost_spec(), cost_attestation=None,
            )

    def test_attestation_without_spec_is_hard_error_in_gate(self) -> None:
        with pytest.raises(ValueError, match="without\\s+the attested spec"):
            net_of_cost_wf_evaluation(
                pd.DataFrame({"date": []}), [], pd.DataFrame(),
                normalization_builder=None, label="fwd_20d_raw",
                spec=None, cost_attestation=VALID_ATTESTATION,
            )


class TestExecutionDelay:
    """THE lookahead fix (Codex review, model#43 r2): decisions from bar D
    fill at bar D+1's close — never at a price inside their information set."""

    def test_hand_computed_rotation_with_delayed_fills(self) -> None:
        """4 days, top-1, decisions at d1 (A) and d3 (B), fills at d2/d4.

        A compounds +10%/day from d2; B flat. rate = 25 bps. Hand math:
          d1: cash; decide A                       -> gross 0,   traded 0
          d2: still cash during d1->d2; FILL A     -> gross 0,   traded 1.0
          d3: hold A d2->d3 = +10%; decide B       -> gross 0.10, traded 0
          d4: hold A d3->d4 = +10%; FILL B (A->B)  -> gross 0.10, traded 2.0
        gross_total = 1.1 * 1.1 - 1 = 0.21
        net = [0, -0.0025, 0.10, 0.095]; net_total = 0.9975*1.1*1.095 - 1
        total_cost_fraction = 0.0025 * 3 = 0.0075
        """
        dates = pd.date_range("2025-03-01", periods=4, freq="D")
        closes = _closes_long(
            {"A": [100.0, 110.0, 121.0, 133.1], "B": [50.0, 50.0, 50.0, 50.0]}, dates)
        scores = pd.concat([
            pd.DataFrame({"date": list(dates), "ticker": ["A", "A", "B", "B"],
                          "score": [1.0, 1.0, 1.0, 1.0]}),
            pd.DataFrame({"date": list(dates), "ticker": ["B", "B", "A", "A"],
                          "score": [0.5, 0.5, 0.5, 0.5]}),
        ], ignore_index=True)
        spec = cost_model.CostModelSpec(fee_bps=25.0)
        out = simulate_topk_net(scores, closes, spec, top_k=1, rebalance_days=2)

        assert out["gross_returns"] == pytest.approx([0.0, 0.0, 0.10, 0.10])
        assert out["traded_fractions"] == pytest.approx([0.0, 1.0, 0.0, 2.0])
        assert out["net_returns"] == pytest.approx([0.0, -0.0025, 0.10, 0.095])
        assert out["gross_total_return"] == pytest.approx(0.21)
        assert out["net_total_return"] == pytest.approx(0.9975 * 1.1 * 1.095 - 1.0)
        assert out["total_cost_fraction"] == pytest.approx(0.0075)
        assert out["n_decisions"] == 2 and out["n_rebalances"] == 2
        assert out["n_expired_decisions"] == 0
        assert out["fill_dates"] == [dates[1].date().isoformat(),
                                     dates[3].date().isoformat()]
        assert out["execution_convention"]["execution_delay_bars"] == 1

    def test_regression_decision_bar_close_cannot_alter_fill(self) -> None:
        """Codex-required regression: perturbing the DECISION bar's close
        must leave the replay's accounting bit-identical — the fill is
        priced at the next bar, outside the decision's information set."""
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        scores = _closes_long({"A": [1, 1, 1]}, dates).rename(columns={"close": "score"})
        spec = cost_model.CostModelSpec(fee_bps=25.0)

        outs = []
        for d1_close in (100.0, 999.0):  # wildly different decision-bar close
            closes = _closes_long({"A": [d1_close, 50.0, 60.0]}, dates)
            outs.append(simulate_topk_net(scores, closes, spec, top_k=1,
                                          rebalance_days=3))
        base, perturbed = outs
        for key in ("gross_returns", "net_returns", "traded_fractions",
                    "gross_total_return", "net_total_return",
                    "total_cost_fraction", "fill_dates"):
            assert base[key] == perturbed[key], f"decision-bar close leaked into {key}"
        # and the fill is genuinely priced at d2: the position earns d2->d3
        assert base["gross_returns"] == pytest.approx([0.0, 0.0, 60.0 / 50.0 - 1.0])
        assert base["traded_fractions"] == pytest.approx([0.0, 1.0, 0.0])

    def test_same_bar_fill_rejected(self) -> None:
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        closes = _closes_long({"A": [1, 1, 1]}, dates)
        scores = _closes_long({"A": [1, 1, 1]}, dates).rename(columns={"close": "score"})
        with pytest.raises(ValueError, match="execution_delay_bars"):
            simulate_topk_net(scores, closes, cost_model.CostModelSpec(), top_k=1,
                              rebalance_days=1, execution_delay_bars=0)
        idx = pd.date_range("2025-01-01", periods=30, freq="D")
        with pytest.raises(ValueError, match="execution_delay_bars"):
            btc_timing_rule_net(pd.Series(100.0 + np.arange(30), index=idx),
                                cost_model.CostModelSpec(), execution_delay_bars=0)

    def test_decision_beyond_window_expires_unexecuted(self) -> None:
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        closes = _closes_long({"A": [100, 110, 121]}, dates)
        scores = _closes_long({"A": [1, 1, 1]}, dates).rename(columns={"close": "score"})
        out = simulate_topk_net(scores, closes, cost_model.CostModelSpec(), top_k=1,
                                rebalance_days=2)  # decisions at j0, j2; j2 expires
        assert out["n_decisions"] == 2
        assert out["n_rebalances"] == 1
        assert out["n_expired_decisions"] == 1
        assert out["traded_fractions"][-1] == 0.0  # expired: zero cost, no fill

    def test_weight_drift_measured_at_the_fill_bar(self) -> None:
        """Fill at d2 sets {A:.5, B:.5}; A doubles d2->d3 so weights drift to
        {A:2/3, B:1/3}; the d4 fill back to equal weight trades
        |0.5-2/3| + |0.5-1/3| = 1/3 against the DRIFTED weights."""
        dates = pd.date_range("2025-03-01", periods=4, freq="D")
        closes = _closes_long({"A": [100, 100, 200, 200], "B": [100, 100, 100, 100]}, dates)
        scores = _closes_long({"A": [1, 1, 1, 1], "B": [1, 1, 1, 1]}, dates).rename(
            columns={"close": "score"})
        out = simulate_topk_net(scores, closes, cost_model.CostModelSpec(), top_k=2,
                                rebalance_days=2)
        assert out["gross_returns"] == pytest.approx([0.0, 0.0, 0.5, 0.0])
        assert out["traded_fractions"] == pytest.approx([0.0, 1.0, 0.0, 1.0 / 3.0])

    def test_missing_bar_for_held_name_fails_closed(self) -> None:
        # A (held, top-scored) misses its d3 bar while B keeps the date
        # alive in the close matrix -> hard error, never a silent zero-fill.
        dates = pd.date_range("2025-03-01", periods=3, freq="D")
        closes = _closes_long({"A": [100, 100, np.nan], "B": [50, 50, 50]}, dates)
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
        # net_total = 0.9975 * 1.21 - 1 = 0.206975. No delay: buy-and-hold
        # conditions on nothing.
        idx = pd.date_range("2025-01-01", periods=3, freq="D")
        out = btc_buy_and_hold_net(pd.Series([100.0, 110.0, 121.0], index=idx),
                                   cost_model.CostModelSpec(fee_bps=25.0))
        assert out["gross_total_return"] == pytest.approx(0.21)
        assert out["net_total_return"] == pytest.approx(0.9975 * 1.21 - 1.0)

    def test_timing_rule_delayed_fill_hand_computed(self) -> None:
        """close = 100 + i, 30 days. Signal turns long at close of day 20
        (120 > 100, exact 20cd lookback); with the 1-bar delay the position
        FILLS at close of day 21 (one switch, cost charged there on a 0
        gross period) and earns days 22..29 only."""
        idx = pd.date_range("2025-01-01", periods=30, freq="D")
        close = pd.Series(100.0 + np.arange(30), index=idx)
        out = btc_timing_rule_net(close, cost_model.CostModelSpec(fee_bps=25.0))
        assert out["n_switches"] == 1
        gross_expected = 1.0
        for i in range(22, 30):
            gross_expected *= (100.0 + i) / (100.0 + i - 1)
        assert out["gross_total_return"] == pytest.approx(gross_expected - 1.0)
        net_expected = (1.0 - 0.0025) * gross_expected - 1.0
        assert out["net_total_return"] == pytest.approx(net_expected)
        assert out["execution_convention"]["execution_delay_bars"] == 1

    def test_timing_rule_regression_decision_close_cannot_alter_fill(self) -> None:
        """Perturb the signal bar's close (keeping the signal decision
        unchanged): every consumed quantity must be bit-identical — with
        the delayed fill, close[20] prices NO transaction and earns NO
        held return."""
        idx = pd.date_range("2025-01-01", periods=30, freq="D")
        base_close = pd.Series(100.0 + np.arange(30), index=idx)
        perturbed_close = base_close.copy()
        perturbed_close.iloc[20] = 120.5  # still > close[0]=100 -> same signal
        spec = cost_model.CostModelSpec(fee_bps=25.0)
        a = btc_timing_rule_net(base_close, spec)
        b = btc_timing_rule_net(perturbed_close, spec)
        assert a["gross_total_return"] == b["gross_total_return"]
        assert a["net_total_return"] == b["net_total_return"]
        assert a["n_switches"] == b["n_switches"]

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

    def test_diagnostic_never_an_enable_path_and_never_decision_grade(self) -> None:
        d = crypto_promotion_diagnostic(
            {"net_total_return": 1.0, "gross_total_return": 1.0},
            {"net_total_return": 0.0},
            {"net_total_return": 0.0},
        )
        assert d["diagnostic_only"] is True
        assert d["enable_path"] is False
        assert d["decision_grade"] is False
        assert "stage_2_5" in d["owner_of_enablement"]
        assert d["evidence_tier"] == "tier1_exploratory_survivor_only"

    def test_gross_pass_net_fail_is_a_fail(self) -> None:
        # RFC §4.4: a crypto model that passes gross and fails net is a FAIL.
        d = crypto_promotion_diagnostic(
            {"net_total_return": 0.10, "gross_total_return": 0.50},
            {"net_total_return": 0.15},
        )
        assert d["wf_promotion_bar_met"] is False


def test_withheld_status_constant_is_stable() -> None:
    # downstream consumers grep for this literal in stamped artifacts
    assert NET_VERDICT_WITHHELD == "withheld_unmeasured_cost_spec"
