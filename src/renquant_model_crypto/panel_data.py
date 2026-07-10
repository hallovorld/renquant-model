"""Crypto cross-sectional panel data-side (crypto RFC D-C3 model slice / §4.2-4.3).

Assembles the training panel for the crypto XGB panel scorer from the D-C2
crypto bar store (``{data_dir}/crypto_ohlcv/{SLUG}/1d.parquet``, UTC daily
bars): alpha158 price/volume features + the FROZEN primary label — raw
forward return over h = 20 CALENDAR days on the daily UTC bar axis (RFC
§4.3, frozen before any WF evidence; BTC-excess is a pre-registered
diagnostic only and is NOT computed as a label here).

Feature transform consumption (soft-consume, merge-order free):

* canonical: ``renquant_base_data.crypto_bars.build_crypto_features_for_pair``
  (base-data #41, D-C2) when the installed base-data ships it;
* fallback: ``renquant_base_data.alpha158_qlib_panel.build_features_for_ticker``
  called directly on the crypto store — the EXACT call D-C2's helper makes
  (verified asset-agnostic: shared ``alpha158_ops`` kbar/price/rolling over
  OHLCV only; no fundamentals). Which path served is recorded in the
  artifact provenance stamp.

Survivorship honesty (RFC §4.6, frozen resolution): the training universe is
a STATIC current-pairs list supplied by the caller — never discovered
dynamically — and every artifact is stamped ``exploratory_survivor_only_panel``
(evidence tier 1). The PIT-interval upgrade is a Stage-0 item; nothing here
may present tier-1 output as a full-universe validation.

Boundary: model repo consumes base-data transforms and emits model
artifacts. No live-execution logic, no broker code, no ``kernel.*`` imports.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from renquant_common import Task

from renquant_model_gbdt.panel_data import infer_label_lookahead_days

log = logging.getLogger("renquant_model_crypto.panel_data")

#: D-C2 store dirname under ``data_dir`` (mirrors base-data crypto_bars).
CRYPTO_OHLCV_DIRNAME = "crypto_ohlcv"

#: FROZEN primary label (RFC §4.3): raw 20-calendar-day forward return.
DEFAULT_CRYPTO_LABEL = "fwd_20d_raw"
CRYPTO_LABEL_HORIZON_CALENDAR_DAYS = 20

#: §4.6 pre-registered weaker claim, stamped on every artifact.
SURVIVORSHIP_CLAIM = "exploratory_survivor_only_panel"
EVIDENCE_TIER = "tier1_exploratory_survivor_only"

#: Crypto trades ~365 days/year (RFC gap P4); stamped for downstream honesty.
CRYPTO_ANNUALIZATION_DAYS = 365


# ---------------------------------------------------------------------------
# Symbol policy (RFC §3.0) — soft-consume D-C2's helpers, identical fallback
# ---------------------------------------------------------------------------

def _pair_slug_local(pair: str) -> str:
    """``"BTC/USD"`` -> ``"BTC-USD"`` (frozen D-C2/D-C1 stand-in semantics)."""
    p = str(pair).strip().upper()
    if p.count("/") != 1 or "-" in p:
        raise ValueError(f"not a canonical crypto pair (expected 'BASE/QUOTE'): {pair!r}")
    base, _, quote = p.partition("/")
    if not base or not quote:
        raise ValueError(f"not a canonical crypto pair (expected 'BASE/QUOTE'): {pair!r}")
    return f"{base}-{quote}"


def _slug_pair_local(slug: str) -> str:
    """``"BTC-USD"`` -> ``"BTC/USD"`` (exact inverse of :func:`_pair_slug_local`)."""
    s = str(slug).strip().upper()
    if s.count("-") != 1 or "/" in s:
        raise ValueError(f"not a canonical crypto slug (expected 'BASE-QUOTE'): {slug!r}")
    base, _, quote = s.partition("-")
    if not base or not quote:
        raise ValueError(f"not a canonical crypto slug (expected 'BASE-QUOTE'): {slug!r}")
    return f"{base}/{quote}"


def _slug_helpers():
    try:
        from renquant_base_data.crypto_bars import pair_slug, slug_pair  # noqa: PLC0415
        return pair_slug, slug_pair
    except ImportError:
        return _pair_slug_local, _slug_pair_local


def as_slug(symbol: str) -> str:
    """Accept pair (``BTC/USD``) or slug (``BTC-USD``) form; return the slug.

    Malformed symbols raise (never a colliding store path — RFC gap B5).
    """
    pair_slug, slug_pair = _slug_helpers()
    s = str(symbol).strip().upper()
    return pair_slug(s) if "/" in s else pair_slug(slug_pair(s))


# ---------------------------------------------------------------------------
# Bars + label
# ---------------------------------------------------------------------------

def _normalize_utc_day_index(index: pd.Index) -> pd.DatetimeIndex:
    """Normalize any datetime-like index to tz-naive UTC calendar days."""
    idx = pd.DatetimeIndex(pd.to_datetime(index))
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx.normalize()


def load_crypto_close(data_dir: Path | str, symbol: str) -> pd.Series:
    """Daily close series for one pair from the D-C2 store, UTC-day indexed.

    Index: tz-naive UTC calendar-day Timestamps, sorted, de-duplicated
    (last write wins — the store's closed-and-fetched contract makes
    duplicates a store defect, but the label math must stay deterministic).
    """
    slug = as_slug(symbol)
    path = Path(data_dir) / CRYPTO_OHLCV_DIRNAME / slug / "1d.parquet"
    if not path.exists():
        raise FileNotFoundError(f"no crypto bars for {slug}: {path}")
    df = pd.read_parquet(path)
    if "close" not in df.columns:
        raise ValueError(f"{path} lacks a 'close' column")
    date_col = next((c for c in ("date", "Date", "timestamp", "Timestamp") if c in df.columns), None)
    if date_col is not None:
        df = df.set_index(date_col)
    close = pd.Series(
        df["close"].to_numpy(dtype=float),
        index=_normalize_utc_day_index(df.index),
        name="close",
    ).sort_index()
    close = close[~close.index.duplicated(keep="last")]
    return close


def compute_raw_forward_return_label(
    close: pd.Series,
    horizon_days: int = CRYPTO_LABEL_HORIZON_CALENDAR_DAYS,
) -> pd.Series:
    """Raw forward return over EXACTLY ``horizon_days`` calendar days.

    ``label[D] = close[D + horizon_days] / close[D] - 1`` with an EXACT
    calendar-day match: when the ``D + horizon_days`` bar is absent from the
    store (vendor gap, end of history) the label is NaN — never a
    nearest-bar substitute, which would silently vary the horizon (RFC §4.3
    freeze). Calendar days, not trading days: crypto's UTC daily axis is the
    365-day market's native clock (gap B4).
    """
    if int(horizon_days) <= 0:
        raise ValueError(f"horizon_days must be positive, got {horizon_days!r}")
    c = close.sort_index()
    target = c.index + pd.Timedelta(days=int(horizon_days))
    fwd = c.reindex(target)  # exact-match only; missing -> NaN
    label = pd.Series(fwd.to_numpy(dtype=float) / c.to_numpy(dtype=float) - 1.0, index=c.index)
    return label


# ---------------------------------------------------------------------------
# Features (soft-consume D-C2's transform)
# ---------------------------------------------------------------------------

def crypto_features_for_pair(
    symbol: str,
    crypto_ohlcv_dir: Path | str,
) -> tuple[Optional[pd.DataFrame], str]:
    """alpha158 price/volume features for one pair + which source served.

    Returns ``(frame, source)`` where ``source`` is
    ``"renquant_base_data.crypto_bars.build_crypto_features_for_pair"``
    (canonical, D-C2 merged) or
    ``"renquant_base_data.alpha158_qlib_panel.build_features_for_ticker"``
    (identical fallback call). ``frame`` is None when the pair lacks enough
    stored history (base-data's MIN_OHLCV_ROWS contract).
    """
    try:
        from renquant_base_data.crypto_bars import build_crypto_features_for_pair  # noqa: PLC0415

        return (
            build_crypto_features_for_pair(symbol, crypto_ohlcv_dir),
            "renquant_base_data.crypto_bars.build_crypto_features_for_pair",
        )
    except ImportError:
        from renquant_base_data.alpha158_qlib_panel import build_features_for_ticker  # noqa: PLC0415

        return (
            build_features_for_ticker(as_slug(symbol), crypto_ohlcv_dir),
            "renquant_base_data.alpha158_qlib_panel.build_features_for_ticker",
        )


# ---------------------------------------------------------------------------
# Panel assembly
# ---------------------------------------------------------------------------

def assemble_crypto_panel(
    data_dir: Path | str,
    pairs: list[str],
    *,
    label: str = DEFAULT_CRYPTO_LABEL,
    horizon_days: Optional[int] = None,
) -> tuple[pd.DataFrame, list[str], str, pd.DataFrame]:
    """Assemble the crypto training panel from the D-C2 store.

    :param pairs: STATIC, explicit universe list (pair or slug form) — the
        §4.6 survivor-only current-pairs snapshot. Never discovered
        dynamically here; auditability requires the caller to pin it.
    :returns: ``(panel, feat_cols, label, closes)`` — ``panel`` has
        ``ticker`` (slug form), ``date`` (tz-naive UTC day), the alpha158
        price/volume feature columns, and the label column (NaN where the
        exact ``D + h`` bar is absent); ``closes`` is a long frame
        ``[date, ticker, close]`` for downstream net-of-cost replay.
    """
    if not pairs:
        raise ValueError("assemble_crypto_panel: pairs must be a non-empty static list (RFC §4.6)")
    h = int(infer_label_lookahead_days(label) if horizon_days is None else horizon_days)

    frames: list[pd.DataFrame] = []
    close_frames: list[pd.DataFrame] = []
    skipped: list[str] = []
    feature_source = None
    for symbol in pairs:
        slug = as_slug(symbol)
        feats, source = crypto_features_for_pair(symbol, Path(data_dir) / CRYPTO_OHLCV_DIRNAME)
        feature_source = feature_source or source
        if feats is None or feats.empty:
            skipped.append(slug)
            log.warning("crypto panel: %s skipped (insufficient stored history)", slug)
            continue
        feats = feats.copy()
        feats["date"] = _normalize_utc_day_index(pd.Index(feats["date"]))
        feats["ticker"] = slug

        close = load_crypto_close(data_dir, slug)
        feats[label] = compute_raw_forward_return_label(close, h).reindex(feats["date"]).to_numpy()
        frames.append(feats)
        close_frames.append(pd.DataFrame({"date": close.index, "ticker": slug, "close": close.to_numpy()}))

    if not frames:
        raise ValueError(
            f"assemble_crypto_panel: no pair in {list(pairs)!r} produced features "
            f"from {Path(data_dir) / CRYPTO_OHLCV_DIRNAME}"
        )
    panel = pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"], kind="mergesort")
    panel = panel.reset_index(drop=True)
    feat_cols = [c for c in panel.columns if c not in {"ticker", "date", label}]
    closes = pd.concat(close_frames, ignore_index=True).sort_values(["date", "ticker"], kind="mergesort")
    closes = closes.reset_index(drop=True)
    log.info(
        "Crypto panel: %d rows, %d pairs (%d skipped), %d dates, %d features, label=%s (h=%dcd) via %s",
        len(panel), panel["ticker"].nunique(), len(skipped), panel["date"].nunique(),
        len(feat_cols), label, h, feature_source,
    )
    panel.attrs["crypto_feature_source"] = feature_source
    panel.attrs["crypto_pairs_skipped"] = skipped
    return panel, feat_cols, label, closes


def build_crypto_normalization(
    train: pd.DataFrame,
    feat_cols: list[str],
) -> tuple[np.ndarray, np.ndarray, list[str], list[Optional[float]], list[Optional[float]]]:
    """Train-fit global z normalization for the RAW crypto panel features.

    Unlike the equity panel (alpha columns pre-normalized at panel build,
    stats sidecar on disk), the crypto panel stores features RAW; the chain
    is fit here from the TRAIN slice only (per-fold via the CV's
    ``normalization_builder`` injection — no leakage). ``feature_norm_kind``
    is ``"panel_raw_z"`` for every column: normalized in panel space at
    training time AND in raw space at serving time
    (:func:`renquant_model_gbdt.transform_feature_frame` masks both).
    """
    mu: list[float] = []
    sd: list[float] = []
    for c in feat_cols:
        col = pd.to_numeric(train[c], errors="coerce")
        m = float(col.mean())
        s = float(col.std(ddof=0))
        mu.append(m if np.isfinite(m) else 0.0)
        sd.append(s if np.isfinite(s) and s > 1e-9 else 1.0)
    kinds = ["panel_raw_z"] * len(feat_cols)
    return (
        np.asarray(mu, dtype=float),
        np.asarray(sd, dtype=float),
        kinds,
        [None] * len(feat_cols),
        [None] * len(feat_cols),
    )


def crypto_universe_stamp(
    pairs_requested: list[str],
    pairs_loaded: list[str],
    *,
    feature_source: Optional[str] = None,
) -> dict:
    """§4.6 survivorship-honesty stamp for the artifact provenance block.

    Every consumer-facing surface (model card, gate output, operator
    summaries) must carry the pre-registered WEAKER claim: this is a
    survivor-only, tier-1 EXPLORATORY panel — directional evidence only,
    never a 5-year validation of the current universe and never tier-2
    (prospective) evidence. PIT tradability intervals are a Stage-0 item;
    if they materialize, the panel upgrades and this stamp changes.
    """
    return {
        "asset_class": "crypto",
        "universe_mode": "static_current_pairs_snapshot",
        "pairs_requested": sorted(as_slug(p) for p in pairs_requested),
        "pairs_loaded": sorted(pairs_loaded),
        "survivorship_claim": SURVIVORSHIP_CLAIM,
        "evidence_tier": EVIDENCE_TIER,
        "evidence_tier_note": (
            "RFC 2026-07-10 §4.6 tier 1: survivor-only by construction; may inform "
            "model-family/feature choices; may NOT alone justify promotion for the "
            "full universe. Tier 2 (prospective shadow/canary) is the decision-grade "
            "evidence and is owned by Stage 1/2/2.5."
        ),
        "pit_upgrade": "stage0_item_pending",
        "label_policy": (
            f"raw {CRYPTO_LABEL_HORIZON_CALENDAR_DAYS}-calendar-day forward return, "
            "FROZEN primary (RFC §4.3); BTC-excess = pre-registered diagnostic only"
        ),
        "calendar": "utc_calendar_days",
        "annualization_days": CRYPTO_ANNUALIZATION_DAYS,
        "feature_source": feature_source,
    }


# ---------------------------------------------------------------------------
# Data-side Tasks (populate the shared training context)
# ---------------------------------------------------------------------------

class LoadCryptoPanelTask(Task):
    """Assemble + slice the crypto panel; seed cutoff artifact fields.

    Cutoff embargo is in CALENDAR days (the crypto axis) — the equity
    loader's business-day embargo would under-embargo a 365-day market.
    """

    def run(self, ctx) -> bool | None:  # ctx: CryptoTrainingContext
        if ctx.data_dir is None:
            raise ValueError("LoadCryptoPanelTask: ctx.data_dir required")
        if not getattr(ctx, "pairs", None):
            raise ValueError("LoadCryptoPanelTask: ctx.pairs (static universe list) required")
        panel, feat_cols, label, closes = assemble_crypto_panel(
            Path(ctx.data_dir), list(ctx.pairs), label=ctx.label,
        )
        if ctx.exclude_features:
            drop = set(ctx.exclude_features)
            feat_cols = [c for c in feat_cols if c not in drop]
        train = panel.dropna(subset=[label])
        ctx.lookahead_days = infer_label_lookahead_days(label)
        if ctx.cutoff_date is not None:
            embargo = int(ctx.lookahead_days if ctx.cutoff_embargo_days is None
                          else ctx.cutoff_embargo_days)
            effective_cutoff = pd.Timestamp(ctx.cutoff_date) - pd.Timedelta(days=max(0, embargo))
            train = train[train["date"] < effective_cutoff]
            if len(train) == 0:
                raise ValueError(f"no crypto training rows with date < {effective_cutoff.date()}")
            ctx.extra_artifact_fields["cutoff_date"] = pd.Timestamp(ctx.cutoff_date).isoformat()
            ctx.extra_artifact_fields["cutoff_embargo_days"] = embargo
            ctx.extra_artifact_fields["effective_train_cutoff_date"] = effective_cutoff.isoformat()
        if ctx.side_label is not None:
            ctx.extra_artifact_fields["side_label"] = ctx.side_label
        ctx.train, ctx.feat_cols, ctx.label = train.reset_index(drop=True), feat_cols, label
        ctx.closes = closes
        ctx.feature_source = panel.attrs.get("crypto_feature_source")
        ctx.pairs_loaded = sorted(train["ticker"].unique().tolist())
        return True


class BuildCryptoNormalizationTask(Task):
    """Fit the train-only normalization chain; expose the per-fold builder."""

    def run(self, ctx) -> bool | None:  # ctx: CryptoTrainingContext
        if ctx.train is None or not ctx.feat_cols:
            raise ValueError("BuildCryptoNormalizationTask: train panel + feat_cols required")
        ctx.mu, ctx.sd, ctx.norm_kind, ctx.raw_clip_low, ctx.raw_clip_high = (
            build_crypto_normalization(ctx.train, ctx.feat_cols))
        ctx.normalization_builder = build_crypto_normalization
        return True
