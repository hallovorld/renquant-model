"""Crypto XGB cross-sectional panel family (crypto RFC D-C3/D-C8b/D-C9 slice).

New asset class in the EXISTING GBDT factory harness (RFC §4.1): the crypto
panel scorer reuses ``renquant_model_gbdt``'s engine (``ModelTrainingJob``,
``kind="panel_ltr_xgboost"``) with crypto data-side Tasks (D-C2 store
consumption, frozen raw 20-calendar-day label, survivor-only universe
stamps) and a fee-aware net-of-cost WF gate (D-C8b) consuming the shared
``renquant_common.cost_model`` primitive (D-C8a, soft-consumed with an
identical local fallback).

Family-gated: no equity or production path imports this package; equity
family behavior is pinned byte-identical by tests.
"""

from .fee_gate import (
    BTC_TIMING_LOOKBACK_CALENDAR_DAYS,
    CRYPTO_TAKER_FEE_BPS_DEFAULT,
    DEFAULT_BTC_SLUG,
    USING_COMMON_COST_MODEL,
    btc_buy_and_hold_net,
    btc_timing_rule_net,
    cost_model,
    crypto_promotion_diagnostic,
    default_crypto_cost_spec,
    net_of_cost_wf_evaluation,
    simulate_topk_net,
)
from .panel_data import (
    CRYPTO_ANNUALIZATION_DAYS,
    CRYPTO_LABEL_HORIZON_CALENDAR_DAYS,
    CRYPTO_OHLCV_DIRNAME,
    DEFAULT_CRYPTO_LABEL,
    EVIDENCE_TIER,
    SURVIVORSHIP_CLAIM,
    BuildCryptoNormalizationTask,
    LoadCryptoPanelTask,
    as_slug,
    assemble_crypto_panel,
    build_crypto_normalization,
    compute_raw_forward_return_label,
    crypto_features_for_pair,
    crypto_universe_stamp,
    load_crypto_close,
)
from .training import (
    CryptoArtifactContractJob,
    CryptoDataPrepJob,
    CryptoTrainingContext,
    NetOfCostWfGateTask,
    StampCryptoProvenanceTask,
    build_crypto_training_pipeline,
)

__all__ = [
    "BTC_TIMING_LOOKBACK_CALENDAR_DAYS",
    "CRYPTO_ANNUALIZATION_DAYS",
    "CRYPTO_LABEL_HORIZON_CALENDAR_DAYS",
    "CRYPTO_OHLCV_DIRNAME",
    "CRYPTO_TAKER_FEE_BPS_DEFAULT",
    "BuildCryptoNormalizationTask",
    "CryptoArtifactContractJob",
    "CryptoDataPrepJob",
    "CryptoTrainingContext",
    "DEFAULT_BTC_SLUG",
    "DEFAULT_CRYPTO_LABEL",
    "EVIDENCE_TIER",
    "LoadCryptoPanelTask",
    "NetOfCostWfGateTask",
    "SURVIVORSHIP_CLAIM",
    "StampCryptoProvenanceTask",
    "USING_COMMON_COST_MODEL",
    "as_slug",
    "assemble_crypto_panel",
    "btc_buy_and_hold_net",
    "btc_timing_rule_net",
    "build_crypto_normalization",
    "build_crypto_training_pipeline",
    "compute_raw_forward_return_label",
    "cost_model",
    "crypto_features_for_pair",
    "crypto_promotion_diagnostic",
    "crypto_universe_stamp",
    "default_crypto_cost_spec",
    "load_crypto_close",
    "net_of_cost_wf_evaluation",
    "simulate_topk_net",
]
