"""End-to-end crypto panel training: artifact contract + unified stamps."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")
xgb = pytest.importorskip("xgboost")

from renquant_common.model_fingerprint import (  # noqa: E402
    FINGERPRINT_SCHEMA_VERSION,
    model_content_sha256,
    stamp,
    verify,
)
from renquant_model_gbdt.panel_trainer import PANEL_LTR_PARAMS  # noqa: E402
from renquant_model_crypto import (  # noqa: E402
    CryptoTrainingContext,
    build_crypto_training_pipeline,
)

from .conftest import make_crypto_store

PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "LINK/USD"]
SLUGS = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "LINK-USD"]


@pytest.fixture(scope="module")
def trained(tmp_path_factory) -> CryptoTrainingContext:
    tmp = tmp_path_factory.mktemp("crypto_train")
    make_crypto_store(tmp, SLUGS, n_days=240)
    ctx = CryptoTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=10,
        cv_n_splits=2, cv_embargo_days=20,
        data_dir=str(tmp), pairs=list(PAIRS),
        output_path=str(tmp / "crypto-panel-ltr.json"),
        train_run_id="crypto-selftest",
        fee_gate_top_k=2, fee_gate_rebalance_days=10,
    )
    result = build_crypto_training_pipeline().run(ctx)
    assert result.ok and result.name == "crypto-panel-gbdt-training"
    assert [s.job_name for s in result.steps] == [
        "CryptoDataPrepJob", "ModelTrainingJob", "CryptoArtifactContractJob"]
    assert ctx.artifact is not None
    return ctx


class TestArtifactContract:
    def test_same_family_same_engine(self, trained: CryptoTrainingContext) -> None:
        art = trained.artifact
        assert art["kind"] == "panel_ltr_xgboost" and art["version"] == 3
        assert art["booster_raw_json"]
        assert len(art["feature_cols"]) == 158
        assert art["params"] == PANEL_LTR_PARAMS

    def test_frozen_label_and_horizon(self, trained: CryptoTrainingContext) -> None:
        art = trained.artifact
        assert art["label_col"] == "fwd_20d_raw"
        assert art["lookahead_days"] == 20
        assert art["cv_embargo_days"] == 20

    def test_normalization_is_train_fit_panel_raw_z(self, trained: CryptoTrainingContext) -> None:
        art = trained.artifact
        assert set(art["feature_norm_kind"]) == {"panel_raw_z"}
        assert all(np.isfinite(v) for v in art["feature_means"])
        assert all(np.isfinite(v) and v > 0 for v in art["feature_stds"])

    def test_gross_cv_evidence_present(self, trained: CryptoTrainingContext) -> None:
        art = trained.artifact
        assert art["cv_method"] == "purged_walk_forward"
        assert art["oos_per_fold_ic"] and all(np.isfinite(v) for v in art["oos_per_fold_ic"])

    def test_survivorship_provenance_stamped(self, trained: CryptoTrainingContext) -> None:
        md = trained.artifact["metadata"]["crypto_panel_v1"]
        assert md["survivorship_claim"] == "exploratory_survivor_only_panel"
        assert md["evidence_tier"] == "tier1_exploratory_survivor_only"
        assert md["universe_mode"] == "static_current_pairs_snapshot"
        assert md["pairs_requested"] == sorted(SLUGS)
        assert md["pairs_loaded"] == sorted(SLUGS)
        assert md["pit_upgrade"] == "stage0_item_pending"
        assert md["calendar"] == "utc_calendar_days"
        assert md["annualization_days"] == 365
        assert md["feature_source"] in (
            "renquant_base_data.crypto_bars.build_crypto_features_for_pair",
            "renquant_base_data.alpha158_qlib_panel.build_features_for_ticker",
        )

    def test_fee_gate_evidence_stamped(self, trained: CryptoTrainingContext) -> None:
        gate = trained.artifact["metadata"]["crypto_fee_gate_v1"]
        assert gate["method"] == "purged_walk_forward_net_of_cost"
        assert gate["embargo_days"] == 20
        assert gate["btc_slug"] == "BTC-USD"
        assert gate["folds"], "net-of-cost WF must produce folds"
        assert gate["cost_spec"]["fee_bps"] == 25.0
        assert gate["cost_spec"]["fee_default_status"] == "GUESS_stage0_verifies"
        diag = gate["promotion_diagnostic"]
        assert diag["diagnostic_only"] is True and diag["enable_path"] is False
        assert isinstance(diag["wf_promotion_bar_met"], bool)
        for fold in gate["folds"]:
            # net <= gross always (costs only subtract)
            assert fold["strategy_net_total_return"] <= fold["strategy_gross_total_return"] + 1e-12
            assert fold["strategy_total_cost_fraction"] > 0

    def test_smoke_evidence_coexists_with_crypto_stamps(self, trained: CryptoTrainingContext) -> None:
        md = trained.artifact["metadata"]
        assert md["inference_smoke_test"]["all_finite"] is True
        assert "crypto_panel_v1" in md and "crypto_fee_gate_v1" in md


class TestUnifiedFingerprint:
    def test_config_fingerprint_stamped_via_canonical_impl(self, trained: CryptoTrainingContext) -> None:
        art = trained.artifact
        assert art["config_fingerprint"].startswith("sha256:")
        # the stamped value IS the canonical model_content_sha256 (no fork)
        assert art["config_fingerprint"] == model_content_sha256(art)

    def test_schema_v1_stamp_and_verify_roundtrip(self, trained: CryptoTrainingContext) -> None:
        # every top-level key is classified (no UnclassifiedKeyError), and
        # the schema-versioned stamp()/verify() pair round-trips.
        fields = stamp(trained.artifact)
        assert fields["fingerprint_schema_version"] == FINGERPRINT_SCHEMA_VERSION
        verify(trained.artifact, fields["model_content_fingerprint"],
               fields["fingerprint_schema_version"])

    def test_operational_stamps_do_not_move_the_fingerprint(self, trained: CryptoTrainingContext) -> None:
        art = json.loads(json.dumps(trained.artifact))
        before = model_content_sha256(art)
        art["metadata"]["crypto_fee_gate_v1"]["promotion_diagnostic"]["wf_promotion_bar_met"] = (
            not art["metadata"]["crypto_fee_gate_v1"]["promotion_diagnostic"]["wf_promotion_bar_met"])
        art["trained_date"] = "1999-01-01"
        assert model_content_sha256(art) == before
        # while predictive content DOES move it
        art["label_col"] = "fwd_40d_raw"
        assert model_content_sha256(art) != before

    def test_artifact_persisted_and_reloadable(self, trained: CryptoTrainingContext) -> None:
        out = Path(trained.output_path)
        assert out.exists()
        reloaded = json.loads(out.read_text())
        assert reloaded["config_fingerprint"] == trained.artifact["config_fingerprint"]
        assert model_content_sha256(reloaded) == model_content_sha256(trained.artifact)


class TestVariants:
    def test_skip_gate_and_cv_fast_path(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD", "ETH-USD", "SOL-USD"], n_days=150)
        ctx = CryptoTrainingContext(
            params=dict(PANEL_LTR_PARAMS), num_boost_round=8, skip_cv=True,
            run_fee_gate=False, data_dir=str(tmp_path),
            pairs=["BTC/USD", "ETH/USD", "SOL/USD"], train_run_id="fast",
        )
        result = build_crypto_training_pipeline().run(ctx)
        assert result.ok
        assert "oos_mean_ic" not in ctx.artifact
        assert "crypto_fee_gate_v1" not in ctx.artifact["metadata"]
        assert "crypto_panel_v1" in ctx.artifact["metadata"]

    def test_cutoff_embargo_is_calendar_days(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD", "ETH-USD", "SOL-USD"], n_days=150)
        cutoff = pd.Timestamp("2024-04-01")
        ctx = CryptoTrainingContext(
            params=dict(PANEL_LTR_PARAMS), num_boost_round=8, skip_cv=True,
            run_fee_gate=False, data_dir=str(tmp_path),
            pairs=["BTC/USD", "ETH/USD", "SOL/USD"], train_run_id="cutoff",
            cutoff_date=cutoff,
        )
        build_crypto_training_pipeline().run(ctx)
        art = ctx.artifact
        effective = cutoff - pd.Timedelta(days=20)  # calendar days, not BDay
        assert art["cutoff_date"] == cutoff.isoformat()
        assert art["cutoff_embargo_days"] == 20
        assert art["effective_train_cutoff_date"] == effective.isoformat()
        assert pd.Timestamp(ctx.train["date"].max()) < effective

    def test_missing_pairs_fails_loud(self, tmp_path: Path) -> None:
        make_crypto_store(tmp_path, ["BTC-USD"], n_days=150)
        ctx = CryptoTrainingContext(
            params=dict(PANEL_LTR_PARAMS), data_dir=str(tmp_path), pairs=None)
        with pytest.raises(ValueError, match="static universe list"):
            build_crypto_training_pipeline().run(ctx)

    def test_fee_gate_requires_btc_in_universe(self, tmp_path: Path) -> None:
        # 5 pairs (the gross CV's per-date IC needs >= 5 names) but no BTC.
        slugs = ["ETH-USD", "SOL-USD", "AVAX-USD", "LINK-USD", "DOGE-USD"]
        make_crypto_store(tmp_path, slugs, n_days=240)
        ctx = CryptoTrainingContext(
            params=dict(PANEL_LTR_PARAMS), num_boost_round=8,
            cv_n_splits=2, data_dir=str(tmp_path),
            pairs=[s.replace("-", "/") for s in slugs], train_run_id="nobtc",
        )
        with pytest.raises(ValueError, match="BTC baseline pair"):
            build_crypto_training_pipeline().run(ctx)  # fail closed, never a silent skip
