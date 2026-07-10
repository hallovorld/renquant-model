"""Crypto XGB panel training pipeline — the D-C9-facing assembly (RFC §4.1).

Same factory, same governance, new asset class: the crypto panel scorer is
an XGB cross-sectional model trained by the EXISTING ``renquant_model_gbdt``
engine (``ModelTrainingJob``: purged WF CV -> booster -> version:3 artifact,
``kind="panel_ltr_xgboost"`` so the existing scorer entry point serves it)
with crypto data-side and contract-side Tasks around it. Equity family
modules are IMPORTED, never modified — their behavior is pinned
byte-identical by ``tests/crypto/test_equity_family_byte_identity.py``.

Family gating: nothing imports this package from any equity or production
path; a crypto training run must construct :class:`CryptoTrainingContext`
explicitly. Fingerprint stamps ride the unified
``renquant_common.model_fingerprint`` implementation via the SAME
``StampFingerprintTask`` the equity family uses — never a new impl (the M6
lesson). All crypto-specific provenance nests under the artifact's
``metadata`` key (OPERATIONAL in the fingerprint classification tables), so
no new top-level key and no classification-table change is introduced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from renquant_common import Job, Pipeline, Task

from renquant_model_gbdt.panel_data import (
    ArtifactContractJob as _EquityArtifactContractJob,  # noqa: F401 (doc pointer)
    AttachSmokeTask,
    StampFingerprintTask,
    WriteArtifactTask,
)
from renquant_model_gbdt.pipeline import GbdtTrainingContext, ModelTrainingJob

from .fee_gate import (
    DEFAULT_BTC_SLUG,
    default_crypto_cost_spec,
    net_of_cost_wf_evaluation,
)
from .panel_data import (
    BuildCryptoNormalizationTask,
    DEFAULT_CRYPTO_LABEL,
    LoadCryptoPanelTask,
    crypto_universe_stamp,
)


@dataclass
class CryptoTrainingContext(GbdtTrainingContext):
    """Shared context for the crypto panel training pipeline.

    Inherits the equity engine's context contract; crypto defaults are the
    RFC-frozen ones — label ``fwd_20d_raw`` (§4.3), lookahead/embargo 20
    CALENDAR days (§4.4 embargo >= h on the UTC-day axis).
    """

    # RFC-frozen crypto defaults (override the equity defaults).
    label: str = DEFAULT_CRYPTO_LABEL
    lookahead_days: int = 20
    cv_embargo_days: int = 20

    # ── crypto data-side inputs ──
    #: STATIC current-pairs universe (pair or slug form) — §4.6 snapshot.
    pairs: Optional[list[str]] = None

    # ── fee-aware WF gate (D-C8b) config ──
    run_fee_gate: bool = True
    #: cost spec (shared cost_model CostModelSpec); None -> fee-only taker default.
    fee_spec: Any = None
    fee_gate_top_k: int = 5
    fee_gate_rebalance_days: int = 20
    btc_slug: str = DEFAULT_BTC_SLUG

    # ── set by Tasks ──
    closes: Optional[pd.DataFrame] = None
    feature_source: Optional[str] = None
    pairs_loaded: list[str] = field(default_factory=list)
    fee_gate_result: Optional[dict[str, Any]] = None


class NetOfCostWfGateTask(Task):
    """Run the fee-aware net-of-cost WF evaluation + BTC baselines (D-C8b).

    Skipped only when ``ctx.run_fee_gate`` is False (an explicit research
    escape hatch); a crypto artifact intended for promotion review must
    carry the net-of-cost evidence — gross-only evaluation of a crypto
    model is exactly the failure the RFC's M1 gap names.
    """

    def run(self, ctx: CryptoTrainingContext) -> bool | None:
        if not ctx.run_fee_gate:
            return True
        if ctx.train is None or not ctx.feat_cols or ctx.normalization_builder is None:
            raise ValueError("NetOfCostWfGateTask: data-prep tasks must run first")
        if ctx.closes is None:
            raise ValueError("NetOfCostWfGateTask: ctx.closes required (set by LoadCryptoPanelTask)")
        ctx.fee_gate_result = net_of_cost_wf_evaluation(
            ctx.train, ctx.feat_cols, ctx.closes,
            normalization_builder=ctx.normalization_builder,
            label=ctx.label, params=ctx.params, num_boost_round=ctx.num_boost_round,
            n_splits=ctx.cv_n_splits, embargo_days=ctx.cv_embargo_days,
            spec=ctx.fee_spec if ctx.fee_spec is not None else default_crypto_cost_spec(),
            top_k=ctx.fee_gate_top_k, rebalance_days=ctx.fee_gate_rebalance_days,
            btc_slug=ctx.btc_slug,
        )
        return True


class StampCryptoProvenanceTask(Task):
    """Stamp crypto provenance + fee-gate evidence under artifact ``metadata``.

    ``metadata`` is OPERATIONAL in the unified fingerprint tables: these
    stamps never change the model-content fingerprint (they are evidence
    and honesty labels, not predictive content), and no unclassified
    top-level key is ever introduced.
    """

    def run(self, ctx: CryptoTrainingContext) -> bool | None:
        if ctx.artifact is None:
            raise ValueError("StampCryptoProvenanceTask: artifact required (run ModelTrainingJob first)")
        md = ctx.artifact.setdefault("metadata", {})
        md["crypto_panel_v1"] = crypto_universe_stamp(
            list(ctx.pairs or []), list(ctx.pairs_loaded),
            feature_source=ctx.feature_source,
        )
        if ctx.fee_gate_result is not None:
            md["crypto_fee_gate_v1"] = ctx.fee_gate_result
        return True


class CryptoDataPrepJob(Job):
    """Crypto data preparation: assemble panel -> fit train-only normalization."""

    @property
    def tasks(self) -> list[Task]:
        return [LoadCryptoPanelTask(), BuildCryptoNormalizationTask()]


class CryptoArtifactContractJob(Job):
    """Fee gate -> provenance stamps -> unified fingerprint -> smoke -> write.

    Fingerprint/smoke/write are the SAME Tasks the equity family runs
    (``renquant_model_gbdt.panel_data``) — one stamping implementation.
    """

    @property
    def tasks(self) -> list[Task]:
        return [
            NetOfCostWfGateTask(),
            StampCryptoProvenanceTask(),
            StampFingerprintTask(),
            AttachSmokeTask(),
            WriteArtifactTask(),
        ]


def build_crypto_training_pipeline() -> Pipeline:
    """The full self-contained crypto panel training Pipeline.

    Run against a :class:`CryptoTrainingContext` with ``data_dir`` (D-C2
    store root), ``pairs`` (static universe) and ``params`` set: assembles
    the price/volume panel with the frozen raw-20cd label, runs the shared
    engine's purged WF CV + booster + version:3 artifact build, evaluates
    net-of-cost WF + BTC baselines, stamps provenance + the unified content
    fingerprint, and persists to ``output_path``.
    """
    return Pipeline(
        [CryptoDataPrepJob(), ModelTrainingJob(), CryptoArtifactContractJob()],
        name="crypto-panel-gbdt-training",
    )
