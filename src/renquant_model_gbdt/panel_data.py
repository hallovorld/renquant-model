"""Self-contained data-side for GBDT panel-LTR training.

Loads the alpha158 + fundamentals panel, fits the inference normalization chain,
and stamps contract evidence (content fingerprint + inference smoke) — all from a
configurable ``data_dir``, with no umbrella code and no ``kernel.*`` imports. This
lets renquant-model train the panel-LTR model end-to-end on its own; the
orchestrator only points it at the data directory.

Functions are verbatim ports of the umbrella's scripts/train_production_model.py
data-side (load_and_slice_panel / build_normalization / infer_label_lookahead_days
/ attach_inference_smoke), with hardcoded ``data/`` paths replaced by ``data_dir``.

Out of scope here (umbrella-coupled, injected by the caller if desired): the
per-regime sentiment training gate, which depends on the HMM regime detector +
strategy config. Absent a regime map the model trains on the full feature set.
"""
from __future__ import annotations

import json
import logging
import re
import warnings
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from renquant_common import Job, Pipeline, Task
from renquant_common.model_fingerprint import model_content_sha256

from .panel_trainer import DEFAULT_LABEL
from .pipeline import GbdtTrainingContext, ModelTrainingJob
from .vol_trend_features import VOL_TREND_FEATURE_SET_VERSION, VOL_TREND_FEATURES

log = logging.getLogger("renquant_model_gbdt.panel_data")

PANEL_FILE = "alpha158_291_fundamental_dataset.parquet"
ALPHA_STATS_FILE = "alpha158_qlib_dataset.stats.json"
FUND_FILE = "sec_fundamentals_daily.parquet"
FUND_COLS = ["earnings_yield", "book_to_price", "gross_profitability", "roe", "asset_growth"]
# Track B BULL_CALM-regime features (renquant-base-data feat/bull-calm-track-b-features).
# When present in the panel they ride the alpha158 global_z normalization chain
# (same protocol as other panel features). The presence of any Track B feature is
# stamped into the artifact's ``feature_addendum_v1`` field so the WF gate's
# recipe-match check can distinguish baseline-172 from variant-176.
#
# Naming: ``idio_vol_market`` was originally named ``idio_vol_3f`` but the
# production base-data callers pass ``sector_close=None``, making the feature
# a SPY+size 2-factor residual std (NOT 3-factor). renquant-base-data #16
# renamed the column honestly; this constant tracks the post-#16 name. See
# RenQuant#120 audit memo (doc/research/2026-06-02-track-b-feature-audit.md).
TRACK_B_FEATURES = ("mom_carry_12_1", "beta_dm", "rvar_total", "idio_vol_market")
_LABEL_EXCL = {"ticker", "date", "split_label", "fwd_5d_excess", "fwd_20d_excess", "fwd_60d_excess"}


def infer_label_lookahead_days(label: str) -> int:
    """Infer label lookahead from names such as fwd_60d_excess."""
    m = re.search(r"fwd_(\d+)d", str(label))
    return int(m.group(1)) if m else 60


def load_panel(
    data_dir: Path,
    *,
    label: str = DEFAULT_LABEL,
    cutoff_date: Optional[pd.Timestamp] = None,
    watchlist: Optional[list[str]] = None,
    cutoff_embargo_days: Optional[int] = None,
) -> tuple[pd.DataFrame, list[str], str]:
    """Load the alpha158 + fund panel, optionally filtering by watchlist/cutoff."""
    panel = pd.read_parquet(data_dir / PANEL_FILE)
    panel["date"] = pd.to_datetime(panel["date"])
    feat_cols = [c for c in panel.columns if c not in _LABEL_EXCL]
    if watchlist:
        panel = panel[panel["ticker"].isin(watchlist)].copy()
    train = panel.dropna(subset=[label])
    if cutoff_date is not None:
        embargo = (infer_label_lookahead_days(label)
                   if cutoff_embargo_days is None else int(cutoff_embargo_days))
        effective_cutoff = cutoff_date - pd.offsets.BDay(max(0, embargo))
        train = train[train["date"] < effective_cutoff]
        if len(train) == 0:
            raise ValueError(f"no training rows with date < {effective_cutoff.date()}")
    log.info("Loaded panel: %d rows, %d tickers, %d dates, label=%s",
             len(train), train["ticker"].nunique(), train["date"].nunique(), label)
    return train, feat_cols, label


def build_normalization(
    train: pd.DataFrame,
    feat_cols: list[str],
    data_dir: Path,
) -> tuple[np.ndarray, np.ndarray, list[str], list[Optional[float]], list[Optional[float]]]:
    """Build the inference normalization chain: (mean, std) per feature s.t.
    (raw - mean)/std = normalized. alpha cols from panel z-stats; fund cols robust-z
    refit on the train period; everything else identity."""
    ps = json.loads((data_dir / ALPHA_STATS_FILE).read_text())
    alpha_cols = list(ps["feature_cols"])
    alpha_lows = ps.get("feature_raw_clip_low") or [None] * len(alpha_cols)
    alpha_highs = ps.get("feature_raw_clip_high") or [None] * len(alpha_cols)
    if len(alpha_lows) != len(alpha_cols) or len(alpha_highs) != len(alpha_cols):
        alpha_lows = [None] * len(alpha_cols)
        alpha_highs = [None] * len(alpha_cols)
    alpha_norm = {
        c: {"mean": m, "std": s, "raw_clip_low": lo, "raw_clip_high": hi}
        for c, m, s, lo, hi in zip(alpha_cols, ps["feature_means"], ps["feature_stds"],
                                   alpha_lows, alpha_highs)
    }

    fund_raw = pd.read_parquet(data_dir / FUND_FILE)
    fund_raw["date"] = pd.to_datetime(fund_raw["date"])
    train_dates = set(train["date"])
    fund_train = fund_raw[fund_raw["date"].isin(train_dates)
                          & fund_raw["ticker"].isin(set(train["ticker"]))]
    fund_norm = {}
    for c in FUND_COLS:
        col = fund_train[c].dropna()
        med = float(col.median()) if len(col) else 0.0
        mad = float((col - med).abs().median()) if len(col) else 1.0
        fund_norm[c] = (med, max(mad * 1.4826, 1e-9))

    means, stds, kinds = [], [], []
    clip_lo: list[Optional[float]] = []
    clip_hi: list[Optional[float]] = []
    for c in feat_cols:
        if c in alpha_norm:
            rec = alpha_norm[c]
            means.append(rec["mean"]); stds.append(rec["std"]); kinds.append("global_z")
            clip_lo.append(rec["raw_clip_low"]); clip_hi.append(rec["raw_clip_high"])
        elif c in fund_norm:
            m, s = fund_norm[c]
            means.append(m); stds.append(s); kinds.append("robust_z")
            clip_lo.append(None); clip_hi.append(None)
        else:
            means.append(0.0); stds.append(1.0); kinds.append("identity")
            clip_lo.append(None); clip_hi.append(None)
    log.info("Normalization: %d global_z, %d robust_z, %d identity",
             kinds.count("global_z"), kinds.count("robust_z"), kinds.count("identity"))
    return np.array(means), np.array(stds), kinds, clip_lo, clip_hi


def content_fingerprint(artifact: dict[str, Any]) -> str:
    """DEPRECATED: use ``renquant_common.model_fingerprint.model_content_sha256``.

    This was a LOCAL allowlist-style hash over 4 fields (params, feature_cols,
    label_col, booster_raw_json) — DIFFERENT from the pipeline's denylist-style
    hash. That divergence is the root cause of the recurring 2026-05-27/06-22/
    07-01 fail-closed incidents. Both repos now import the SAME function from
    ``renquant_common.model_fingerprint``. Do not re-fork a local copy.
    """
    warnings.warn(
        "content_fingerprint() is deprecated — use "
        "renquant_common.model_fingerprint.model_content_sha256() directly. "
        "This wrapper will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
    return model_content_sha256(artifact)


def attach_inference_smoke(artifact: dict, booster: Any, feat_cols: list[str]) -> None:
    """Deterministic scorer smoke evidence (synthetic input; serialization sanity)."""
    import xgboost as xgb  # noqa: PLC0415

    rng = np.random.default_rng(104)
    X = rng.standard_normal((32, len(feat_cols))).astype(np.float64)
    scores = booster.predict(xgb.DMatrix(X))
    finite = np.isfinite(scores)
    md = artifact.setdefault("metadata", {})
    md["score_sample_range"] = [
        float(np.nanmin(scores)) if len(scores) else float("nan"),
        float(np.nanmax(scores)) if len(scores) else float("nan"),
    ]
    md["inference_smoke_test"] = {
        "n": int(len(scores)),
        "all_finite": bool(finite.all()) if len(scores) else False,
        "n_unique": int(len(set(np.round(scores[finite], 12)))) if finite.any() else 0,
    }


# ── Data-side Tasks (populate the shared GbdtTrainingContext) ──

class LoadPanelTask(Task):
    """Read + slice the panel from data_dir; seed cutoff/side_label artifact fields."""

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.data_dir is None:
            raise ValueError("LoadPanelTask: ctx.data_dir required")
        train, feat_cols, label = load_panel(
            Path(ctx.data_dir), label=ctx.label, cutoff_date=ctx.cutoff_date,
            watchlist=ctx.watchlist, cutoff_embargo_days=ctx.cutoff_embargo_days,
        )
        if ctx.exclude_features:
            drop = set(ctx.exclude_features)
            feat_cols = [c for c in feat_cols if c not in drop]
            log.info("Excluded %d feature(s); %d remain", len(drop & set(train.columns)), len(feat_cols))
        # Track B recipe stamp — any Track B feature in feat_cols pins a
        # ``feature_addendum_v1`` field on the artifact so the WF gate's
        # recipe-match check distinguishes the variant from baseline.
        addendum: dict[str, Any] = {}
        track_b_active = [c for c in TRACK_B_FEATURES if c in feat_cols]
        if track_b_active:
            # Key order preserved verbatim — a Track-B-only panel must stamp a
            # byte-identical addendum to the pre-vol_trend code.
            addendum.update({
                "track_b_features_active": track_b_active,
                "source": "renquant-base-data:track_b_features",
                "memo": "doc/research/2026-06-02-track-b-feature-audit.md",
            })
        # Vol/trend feature-set v2 stamp (candidate features C1/C2 for the
        # orchestrator #476 §7 preregistered baseline-vs-vol_trend_v2 experiment
        # — NOT a repair for a proven STD60 defect; #476 established only a
        # mechanically-reproduced single-path decomposition plus hypotheses H1-H4,
        # not a general-adoption verdict; see the module docstring). Any
        # vol_trend_v2 column in feat_cols pins a versioned sub-object under
        # ``feature_addendum_v1`` so the WF gate's recipe-match check distinguishes
        # the returns-vol/trend-interaction variant from the current recipe.
        # NESTED (not a new top-level key) on purpose: ``feature_addendum_v1`` is
        # the recipe-identity field already classified PREDICTIVE in
        # renquant-common's fail-closed fingerprint table
        # (model_fingerprint.PREDICTIVE_KEYS, hashed as one atomic unit), so the
        # v2 recipe binds into the model content fingerprint with no cross-repo
        # classification-table change and no FINGERPRINT_SCHEMA_VERSION bump.
        # Panels without these columns (production today) stamp byte-identically.
        #
        # ``experiment_id`` / ``run_bundle_ref`` are ALWAYS stamped (possibly
        # None) when the recipe is active — training/experimentation under
        # vol_trend_v2 is unrestricted either way (this is not a training-time
        # gate). Promotion eligibility is enforced downstream, once, in
        # ``wf_retrain_readiness.validate_full_wf_retrain_readiness``: an
        # artifact cannot pass readiness with a vol_trend_v2 recipe unless both
        # fields are populated and ``experiment_id`` matches the config's
        # declared value. No freshness/manual-override promotion path can
        # satisfy that check after the fact, because it is evaluated on the
        # stamp already baked into the (fingerprint-bound) artifact.
        vol_trend_active = [c for c in VOL_TREND_FEATURES if c in feat_cols]
        if vol_trend_active:
            addendum["vol_trend_v2"] = {
                "feature_set_version": VOL_TREND_FEATURE_SET_VERSION,
                "vol_trend_features_active": vol_trend_active,
                "source": "renquant-model:vol_trend_features",
                "memo": "doc/progress/2026-07-11-vol-trend-feature-set-v2.md",
                "experiment_id": ctx.experiment_id,
                "run_bundle_ref": ctx.experiment_run_bundle_ref,
            }
        if addendum:
            ctx.extra_artifact_fields["feature_addendum_v1"] = addendum
        ctx.train, ctx.feat_cols, ctx.label = train, feat_cols, label
        ctx.lookahead_days = infer_label_lookahead_days(label)
        if ctx.cutoff_date is not None:
            embargo = int(ctx.lookahead_days if ctx.cutoff_embargo_days is None
                          else ctx.cutoff_embargo_days)
            ctx.extra_artifact_fields["cutoff_date"] = pd.Timestamp(ctx.cutoff_date).isoformat()
            ctx.extra_artifact_fields["cutoff_embargo_days"] = embargo
            ctx.extra_artifact_fields["effective_train_cutoff_date"] = (
                pd.Timestamp(ctx.cutoff_date) - pd.offsets.BDay(embargo)).isoformat()
        if ctx.side_label is not None:
            ctx.extra_artifact_fields["side_label"] = ctx.side_label
        return True


class BuildNormalizationTask(Task):
    """Fit the normalization chain; expose it as the CV per-fold builder."""

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.train is None or ctx.data_dir is None:
            raise ValueError("BuildNormalizationTask: train + data_dir required")
        data_dir = Path(ctx.data_dir)
        ctx.mu, ctx.sd, ctx.norm_kind, ctx.raw_clip_low, ctx.raw_clip_high = (
            build_normalization(ctx.train, ctx.feat_cols, data_dir))
        ctx.normalization_builder = lambda tr, fc: build_normalization(tr, fc, data_dir)
        return True


# ── Contract-side Tasks ──

class StampFingerprintTask(Task):
    """Stamp the config fingerprint: the injected production fingerprint when the
    orchestrator provides one (so the runtime scorer matches), else a
    self-describing content hash via the canonical
    ``renquant_common.model_fingerprint.model_content_sha256``.

    Migration note (M6): the fallback previously called the LOCAL
    ``content_fingerprint()`` which hashed only 4 fields — DIFFERENT from
    the pipeline's runtime hash. Both sides now use the same canonical
    function from renquant-common, structurally guaranteeing agreement.
    """

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.artifact is None:
            raise ValueError("StampFingerprintTask: artifact required")
        if ctx.config_fingerprint:
            ctx.artifact["config_fingerprint"] = ctx.config_fingerprint
            if ctx.config_fingerprint_fields is not None:
                ctx.artifact["config_fingerprint_fields"] = ctx.config_fingerprint_fields
            log.info("Production config fingerprint: %s", ctx.config_fingerprint)
        else:
            fp = model_content_sha256(ctx.artifact)
            ctx.artifact["config_fingerprint"] = fp
            log.info("Content fingerprint (no production fp injected): %s", fp)
        return True


class AttachSmokeTask(Task):
    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.artifact is None or ctx.booster is None:
            raise ValueError("AttachSmokeTask: artifact + booster required")
        attach_inference_smoke(ctx.artifact, ctx.booster, ctx.feat_cols)
        return True


class WriteArtifactTask(Task):
    """Persist the artifact to ctx.output_path (when set)."""

    def run(self, ctx: GbdtTrainingContext) -> bool | None:
        if ctx.output_path is None:
            return True
        out = Path(ctx.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(ctx.artifact))
        log.info("Saved artifact: %s (%.1f MB)", out, out.stat().st_size / 1e6)
        return True


class DataPrepJob(Job):
    """Self-contained data preparation: load panel → fit normalization."""

    @property
    def tasks(self) -> list[Task]:
        return [LoadPanelTask(), BuildNormalizationTask()]


class ArtifactContractJob(Job):
    """Stamp contract evidence + persist."""

    @property
    def tasks(self) -> list[Task]:
        return [StampFingerprintTask(), AttachSmokeTask(), WriteArtifactTask()]


def build_training_pipeline() -> Pipeline:
    """The full self-contained GBDT training Pipeline (data → model → contract).

    Run it against a ``GbdtTrainingContext`` whose ``data_dir`` + ``params`` are
    set; it loads the panel, fits normalization, runs CV + trains the booster,
    builds the version:3 artifact, stamps a content fingerprint + smoke, and
    persists to ``output_path``. No umbrella code, no ``kernel.*``.
    """
    return Pipeline(
        [DataPrepJob(), ModelTrainingJob(), ArtifactContractJob()],
        name="panel-gbdt-training",
    )
