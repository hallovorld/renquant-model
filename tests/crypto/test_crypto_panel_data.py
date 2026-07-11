"""Crypto panel data-side: label semantics, determinism, symbol policy."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")
pytest.importorskip(
    "renquant_common.cost_model",
    reason="renquant-common>=0.12.0 (D-C8a, common#28) required — no local fallback by design",
)

from renquant_model_crypto.panel_data import (  # noqa: E402
    CRYPTO_LABEL_HORIZON_CALENDAR_DAYS,
    DEFAULT_CRYPTO_LABEL,
    EVIDENCE_TIER,
    LABEL_EXECUTION_DELAY_CALENDAR_DAYS,
    SURVIVORSHIP_CLAIM,
    as_slug,
    assemble_crypto_panel,
    build_crypto_normalization,
    compute_raw_forward_return_label,
    crypto_universe_stamp,
    load_crypto_close,
)

from .conftest import make_crypto_store


class TestSymbolPolicy:
    def test_pair_and_slug_forms_accepted(self) -> None:
        assert as_slug("BTC/USD") == "BTC-USD"
        assert as_slug("btc/usd") == "BTC-USD"
        assert as_slug("BTC-USD") == "BTC-USD"

    @pytest.mark.parametrize("bad", ["BTC/USD/X", "BTCUSD", "BTC_USD", "/USD", "BTC/", "BTC-USD-X"])
    def test_malformed_symbols_rejected(self, bad: str) -> None:
        with pytest.raises(ValueError):
            as_slug(bad)


class TestRawForwardReturnLabel:
    def test_hand_computed_exact_horizon(self) -> None:
        # close[i] = 100 + i on contiguous calendar days. Execution-timing
        # fix (r2 follow-up): label[D_i] enters at close[i+1] (one bar AFTER
        # the D_i bar whose data produced the signal), exits at
        # close[i+1+20]: label[D_i] = (100+i+21)/(100+i+1) - 1, exactly.
        idx = pd.date_range("2025-01-01", periods=60, freq="D")
        close = pd.Series(100.0 + np.arange(60), index=idx)
        label = compute_raw_forward_return_label(close, 20)
        for i in (0, 17, 38):
            expected = (100.0 + i + 21) / (100.0 + i + 1) - 1.0
            assert label.iloc[i] == pytest.approx(expected)
        # exit bar i+21 must exist within 60 days -> i <= 38 valid, i >= 39 NaN
        # (one MORE day of trailing NaN than the old close[D]-entry formula,
        # from the added 1-day entry delay).
        assert label.iloc[-21:].isna().all()
        assert label.iloc[:-21].notna().all()

    def test_missing_exit_bar_is_nan_not_nearest(self) -> None:
        idx = pd.date_range("2025-01-01", periods=60, freq="D")
        close = pd.Series(100.0 + np.arange(60), index=idx)
        # remove the EXIT bar for D=idx[5]: entry is idx[5]+1, exit is idx[5]+21
        gap = idx[5] + pd.Timedelta(days=21)
        close = close.drop(gap)
        label = compute_raw_forward_return_label(close, 20)
        assert np.isnan(label.loc[idx[5]])
        # neighbors unaffected
        assert label.loc[idx[6]] == pytest.approx((100.0 + 27) / (100.0 + 7) - 1.0)

    def test_missing_entry_bar_is_nan_not_nearest(self) -> None:
        # A failure mode the 2-reference-point formula introduces: the ENTRY
        # bar (D+1) can itself be missing (vendor gap), independent of the
        # exit bar's presence. D=idx[5]'s entry bar IS idx[6] -- dropping it
        # removes idx[6] from the close index entirely (so its own label
        # cannot be computed either), and D=idx[5] must be NaN via the
        # missing-entry path. idx[4] (entry bar idx[5], untouched) proves
        # neighbors are unaffected.
        idx = pd.date_range("2025-01-01", periods=60, freq="D")
        close = pd.Series(100.0 + np.arange(60), index=idx)
        entry_gap = idx[5] + pd.Timedelta(days=1)
        assert entry_gap == idx[6]
        close = close.drop(entry_gap)
        label = compute_raw_forward_return_label(close, 20)
        assert np.isnan(label.loc[idx[5]])
        assert label.loc[idx[4]] == pytest.approx((100.0 + 25) / (100.0 + 5) - 1.0)

    def test_mutating_bar_d_close_never_changes_bar_d_label(self) -> None:
        """Codex review: 'add a hand-checked regression test that changing a
        D close cannot alter a fill priced at D.' label[D] must depend ONLY
        on close[D+1] and close[D+1+horizon] -- never on close[D] itself,
        since close[D] is the very feature the D-dated signal was computed
        from and could not simultaneously be an achievable fill price."""
        idx = pd.date_range("2025-01-01", periods=60, freq="D")
        close = pd.Series(100.0 + np.arange(60), index=idx)
        label_before = compute_raw_forward_return_label(close, 20)

        mutated = close.copy()
        d = idx[10]
        mutated.loc[d] = 999_999.0  # wildly different close[D] -- a feature input, never a fill price
        label_after = compute_raw_forward_return_label(mutated, 20)

        assert label_after.loc[d] == pytest.approx(label_before.loc[d])
        # sanity: the mutation COULD have moved this label if the bug were
        # present (999999 dwarfs every other close), so a false pass via
        # numerical coincidence is not possible here.
        assert label_before.loc[d] < 1.0  # normal small return, not a 999999x blowup

    def test_default_horizon_is_frozen_twenty(self) -> None:
        assert CRYPTO_LABEL_HORIZON_CALENDAR_DAYS == 20
        assert DEFAULT_CRYPTO_LABEL == "fwd_20d_raw"

    def test_invalid_horizon_rejected(self) -> None:
        close = pd.Series([1.0], index=pd.DatetimeIndex(["2025-01-01"]))
        with pytest.raises(ValueError):
            compute_raw_forward_return_label(close, 0)


class TestStoreAndPanel:
    def test_load_crypto_close_normalizes_utc_days(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD"], n_days=90)
        close = load_crypto_close(tmp_path, "BTC/USD")
        assert close.index.tz is None
        assert (close.index == close.index.normalize()).all()
        assert close.index.is_monotonic_increasing and close.index.is_unique

    def test_assemble_panel_labels_and_features(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD", "ETH-USD", "SOL-USD"], n_days=200)
        panel, feat_cols, label, closes = assemble_crypto_panel(
            tmp_path, ["BTC/USD", "ETH/USD", "SOL/USD"])
        assert label == "fwd_20d_raw"
        assert len(feat_cols) == 158, "price/volume alpha158 subset must be exactly 158 features"
        assert set(panel["ticker"]) == {"BTC-USD", "ETH-USD", "SOL-USD"}
        # label hand-check against the store closes for one pair
        btc = load_crypto_close(tmp_path, "BTC-USD")
        sample = panel[panel["ticker"] == "BTC-USD"].iloc[30]
        d = sample["date"]
        expected = btc.loc[d + pd.Timedelta(days=21)] / btc.loc[d + pd.Timedelta(days=1)] - 1.0
        assert sample[label] == pytest.approx(expected)
        # closes frame is the long store view
        assert list(closes.columns) == ["date", "ticker", "close"]
        assert closes["ticker"].nunique() == 3

    def test_assembly_is_deterministic(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD", "ETH-USD"], n_days=150)
        p1, f1, l1, c1 = assemble_crypto_panel(tmp_path, ["BTC/USD", "ETH/USD"])
        p2, f2, l2, c2 = assemble_crypto_panel(tmp_path, ["BTC/USD", "ETH/USD"])
        assert f1 == f2 and l1 == l2
        pd.testing.assert_frame_equal(p1, p2)
        pd.testing.assert_frame_equal(c1, c2)
        assert pd.util.hash_pandas_object(p1.fillna(-999.0)).sum() == \
            pd.util.hash_pandas_object(p2.fillna(-999.0)).sum()

    def test_empty_universe_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="static list"):
            assemble_crypto_panel(tmp_path, [])

    def test_missing_store_pair_skipped_but_all_missing_raises(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD"], n_days=150)
        panel, _, _, _ = assemble_crypto_panel(tmp_path, ["BTC/USD", "DOGE/USD"])
        assert set(panel["ticker"]) == {"BTC-USD"}
        assert panel.attrs["crypto_pairs_skipped"] == ["DOGE-USD"]
        with pytest.raises(ValueError, match="no pair"):
            assemble_crypto_panel(tmp_path, ["ADA/USD"])


class TestNormalization:
    def test_train_fit_panel_raw_z(self) -> None:
        rng = np.random.default_rng(3)
        train = pd.DataFrame({"f0": rng.normal(5, 2, 400), "f1": rng.normal(-1, 0.5, 400)})
        mu, sd, kinds, lo, hi = build_crypto_normalization(train, ["f0", "f1"])
        assert kinds == ["panel_raw_z", "panel_raw_z"]
        assert mu[0] == pytest.approx(train["f0"].mean())
        assert sd[0] == pytest.approx(train["f0"].std(ddof=0))
        assert lo == [None, None] and hi == [None, None]

    def test_degenerate_column_gets_unit_std(self) -> None:
        train = pd.DataFrame({"flat": np.ones(50)})
        mu, sd, kinds, _, _ = build_crypto_normalization(train, ["flat"])
        assert sd[0] == 1.0 and mu[0] == 1.0


class TestUniverseStamp:
    def test_survivorship_honesty_fields(self) -> None:
        stamp = crypto_universe_stamp(["BTC/USD", "ETH-USD"], ["BTC-USD"],
                                      feature_source="fallback")
        assert stamp["survivorship_claim"] == SURVIVORSHIP_CLAIM == "exploratory_survivor_only_panel"
        assert stamp["evidence_tier"] == EVIDENCE_TIER
        assert stamp["universe_mode"] == "static_current_pairs_snapshot"
        assert stamp["pairs_requested"] == ["BTC-USD", "ETH-USD"]
        assert stamp["pairs_loaded"] == ["BTC-USD"]
        assert stamp["pit_upgrade"] == "stage0_item_pending"
        assert stamp["calendar"] == "utc_calendar_days"
        assert stamp["annualization_days"] == 365
        assert "FROZEN" in stamp["label_policy"] or "frozen" in stamp["label_policy"].lower()


def test_label_execution_delay_matches_replay_execution_delay() -> None:
    """panel_data's label entry-delay and fee_gate's replay execution-delay
    are independent constants (data-layer must not import the evaluation-
    layer) but MUST stay numerically equal, or the model would be trained
    to predict a return the replay can no longer realize. Tripwire, not a
    shared import, per this module's own documented reasoning."""
    from renquant_model_crypto.fee_gate import DEFAULT_EXECUTION_DELAY_BARS

    assert LABEL_EXECUTION_DELAY_CALENDAR_DAYS == DEFAULT_EXECUTION_DELAY_BARS
