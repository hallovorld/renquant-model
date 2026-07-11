"""Vol/trend feature-set v2 — candidate returns-based-vol (C1) + trend-interaction
(C2) recipe for the preregistered baseline-vs-vol_trend_v2 experiment.

**Status: candidate implementation, not a validated replacement.** This module
implements C1/C2 — the two candidate feature changes orchestrator #476 §5 lists
for the preregistered, cross-repo experiment design specified in #476 §7. #476
does NOT establish a general-adoption verdict that STD60 is defective; after
Codex's review it reframes every causal claim as a **hypothesis**: H3 ("the
qlib alpha158 STD60 feature — std(close LEVELS, 60d, ddof=1) / close_today —
mistakes trend for calm on trending names") is "a live hypothesis — mechanical
decomposition independently reproduced [on one path]; causal-mechanism claim not
established" (#476 §3). The reproduced decomposition itself is real and
re-verified: during META's 2026-07-06..07-10 +11.5% rally, STD60 fell 10.2%
almost entirely through the rising denominator (numerator +0.1%) while 60d
*returns* volatility ROSE 4.8% (#476 §3, #475). What is NOT established is that
this generalizes as a general-adoption defect across trending names, or that the
*fitted* production booster's behavior is driven by this channel rather than a
correlated proxy feature — #476 §7 requires a preregistered, purged/embargoed
walk-forward comparison (baseline STD-family recipe vs. this C1+C2 redesign) to
answer that, and states explicitly that "no fix or promotion recommendation
should be read from" the provenance document alone.

This module is the canonical recipe (spec + reference implementation) for the
candidate ``vol_trend_v2`` feature-set addendum that experiment would evaluate;
its existence does not itself validate or invalidate anything about the current
STD60 feature — that determination is exactly what the (not-yet-run)
preregistered experiment would produce.

C1 (F1) — candidate returns-based volatility measure:
  * ``ret_vol_20d``            std of daily simple returns, trailing 20 returns, ddof=1
  * ``ret_vol_60d``            std of daily simple returns, trailing 60 returns, ddof=1
  * ``ret_semivol_down_60d``   downside semi-deviation: sqrt(sum(min(r,0)^2)/(n-1))
                               over the trailing 60 returns (target 0, ddof=1 parallel)

C2 (F2) — candidate trend-interaction features, motivated by the H3 hypothesis
that STD60 conflates trend with dispersion (not yet established as the fitted
model's actual mechanism — #476 §3/§7):
  * ``resid_vol_60d``               detrended level vol: regression standard error of a
                                    60d linear fit of close on time (sqrt(SSR/(n-2))),
                                    divided by close_today. By construction this
                                    removes the trend component STD60 is hypothesized
                                    (H3) to confound with volatility.
  * ``std60_x_ret_120d``            qlib STD60 (std(close,60,ddof=1)/close_today) times
                                    the signed 120d simple return. Low-STD60 rows split
                                    by whether the name is trending or flat.
  * ``high_52wk_dist_x_ret_vol_60d`` (1 - close/rolling_max(close,252)) times
                                    ``ret_vol_60d``. Zero for any name sitting at its
                                    52wk high; grows with vol only when a name is far
                                    below its high.

Conventions (the base-data panel rebuild MUST reproduce these exactly):
  * daily simple returns ``r_t = close_t/close_{t-1} - 1`` on the ticker's own
    trading-day grid (no calendar reindex, no forward fill);
  * strict full-window warmup — every rolling statistic uses
    ``min_periods == window`` and is NaN until the window is full (the 252d rolling
    high included), so no partially-warmed value can leak into training;
  * ``ddof=1`` for return std; ``n-1`` denominator for the downside semivol;
    ``n-2`` (regression degrees of freedom) for the residual vol;
  * all features are stationary ratios/interaction terms in raw units and ride the
    ``identity`` normalization kind in the artifact chain (XGBoost trees are
    invariant to monotone per-feature scaling; raw units keep the recipe auditable).

Versioning contract: these columns are NOT in the production panel today. When a
rebuilt panel carries them, ``LoadPanelTask`` stamps a ``vol_trend_v2`` sub-object
(``feature_set_version = "vol_trend_v2"``) NESTED inside the artifact's
``feature_addendum_v1`` field — the recipe-identity field that renquant-common's
fail-closed fingerprint table (``model_fingerprint.PREDICTIVE_KEYS``) already
classifies PREDICTIVE and hashes as one atomic unit. Nesting (rather than minting
a new top-level artifact key) binds the v2 recipe into the model content
fingerprint without a cross-repo classification-table change or a
``FINGERPRINT_SCHEMA_VERSION`` bump, both of which that module reserves for
reviewed contract migrations. Absent the columns, artifacts are byte-identical to
before this module existed (a Track-B-only panel stamps the exact pre-v2
addendum).

Experiment-contract promotion gate (``wf_retrain_readiness``): computing/training
under ``vol_trend_v2`` is unrestricted — this recipe can be exercised for
experimentation with no extra declaration required. Promotion eligibility is a
separate, stricter gate: a retrain config opting into ``vol_trend_v2`` must also
declare an ``experiment_id`` naming the preregistered #476 §7 comparison it
belongs to, and the resulting artifact's ``vol_trend_v2`` stamp must carry that
same ``experiment_id`` plus a non-empty ``run_bundle_ref``. Absent either, the
readiness report's ``ok`` is False for that artifact — permanently, since the
check is evaluated against the stamp already baked into the fingerprint-bound
artifact, not re-derivable after the fact by a freshness/manual-override
promotion path. Adoption is exclusively via the standard gated retrain +
promotion path (#467 weekly rail) with that experiment contract satisfied;
nothing here changes the scoring of any existing artifact.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

# The minted feature-set version key (predecessor: Track B's ``feature_addendum_v1``).
VOL_TREND_FEATURE_SET_VERSION = "vol_trend_v2"

# C1/F1 — candidate returns-based volatility measure for the preregistered
# baseline-vs-vol_trend_v2 experiment (#476 §5/§7).
RET_VOL_FEATURES: tuple[str, ...] = (
    "ret_vol_20d",
    "ret_vol_60d",
    "ret_semivol_down_60d",
)

# C2/F2 — candidate trend-interaction features testing the H3 hypothesis
# ("quiet steady riser" vs "quiet dead money"; not yet established as the
# fitted model's actual mechanism — #476 §3/§7).
TREND_INTERACTION_FEATURES: tuple[str, ...] = (
    "resid_vol_60d",
    "std60_x_ret_120d",
    "high_52wk_dist_x_ret_vol_60d",
)

VOL_TREND_FEATURES: tuple[str, ...] = RET_VOL_FEATURES + TREND_INTERACTION_FEATURES

_RET_VOL_SHORT_WINDOW = 20
_VOL_WINDOW = 60
_TREND_WINDOW = 120
_HIGH_WINDOW = 252


def _rolling_linear_fit_resid_std(y: np.ndarray, window: int) -> np.ndarray:
    """Std of residuals from a rolling OLS fit ``y ~ a + b*t`` (sqrt(SSR/(n-2))).

    Closed-form via rolling sums (x is the fixed in-window grid 0..n-1):
    with the OLS normal equations, SSR = Syy - a*Sy - b*Sxy. Computed in float64
    on a per-series demeaned copy (demeaning is absorbed by the intercept and
    leaves residuals unchanged; it tames cancellation on price-level magnitudes).
    Verified against a brute-force ``np.polyfit`` in the test suite.
    """
    n = int(window)
    y = np.asarray(y, dtype=np.float64)
    out = np.full(y.shape, np.nan)
    if len(y) < n:
        return out
    y0 = y - np.nanmean(y)
    x = np.arange(n, dtype=np.float64)
    sx = x.sum()
    sxx = (x * x).sum()

    s = pd.Series(y0)
    sy = s.rolling(n, min_periods=n).sum().to_numpy()
    syy = (s * s).rolling(n, min_periods=n).sum().to_numpy()
    # Sxy_t = sum_k k * y0[t-n+1+k]  — a rolling weighted sum == 'valid' correlation
    # of y0 with the weight vector x.
    sxy = np.full(y.shape, np.nan)
    if np.isnan(y0).any():
        # NaN-safe fallback: windows containing NaN stay NaN.
        for t in range(n - 1, len(y0)):
            w = y0[t - n + 1: t + 1]
            sxy[t] = np.nan if np.isnan(w).any() else float((w * x).sum())
    else:
        sxy[n - 1:] = np.correlate(y0, x, mode="valid")

    denom = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    ssr = syy - a * sy - b * sxy
    out = np.sqrt(np.maximum(ssr, 0.0) / (n - 2))
    return out


def compute_vol_trend_features(close: pd.Series) -> pd.DataFrame:
    """Compute the 6 ``vol_trend_v2`` columns from one ticker's close series.

    ``close`` must be a float series on the ticker's trading-day index, oldest
    first. Returns a DataFrame on the same index with exactly the
    ``VOL_TREND_FEATURES`` columns; rows are NaN until every contributing
    window is full (strict ``min_periods == window``).
    """
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series of close prices")
    c = close.astype(np.float64)
    r = c / c.shift(1) - 1.0

    ret_vol_20 = r.rolling(_RET_VOL_SHORT_WINDOW, min_periods=_RET_VOL_SHORT_WINDOW).std(ddof=1)
    ret_vol_60 = r.rolling(_VOL_WINDOW, min_periods=_VOL_WINDOW).std(ddof=1)

    downside = r.where(r < 0.0, 0.0)
    # Parallel to ddof=1: sqrt( sum(min(r,0)^2) / (n-1) ) with target 0.
    semivol_60 = (
        (downside * downside)
        .rolling(_VOL_WINDOW, min_periods=_VOL_WINDOW)
        .sum()
        .div(_VOL_WINDOW - 1)
        .pow(0.5)
    )
    # Keep the warmup contract exact: NaN whenever any return in the window is NaN.
    semivol_60 = semivol_60.where(r.rolling(_VOL_WINDOW, min_periods=_VOL_WINDOW).count() == _VOL_WINDOW)

    resid_std_60 = pd.Series(
        _rolling_linear_fit_resid_std(c.to_numpy(), _VOL_WINDOW), index=c.index
    )
    resid_vol_60 = resid_std_60 / c

    qlib_std60 = c.rolling(_VOL_WINDOW, min_periods=_VOL_WINDOW).std(ddof=1) / c
    ret_120 = c / c.shift(_TREND_WINDOW) - 1.0
    std60_x_ret_120 = qlib_std60 * ret_120

    high_252 = c.rolling(_HIGH_WINDOW, min_periods=_HIGH_WINDOW).max()
    high_dist = 1.0 - c / high_252
    high_dist_x_ret_vol_60 = high_dist * ret_vol_60

    return pd.DataFrame(
        {
            "ret_vol_20d": ret_vol_20,
            "ret_vol_60d": ret_vol_60,
            "ret_semivol_down_60d": semivol_60,
            "resid_vol_60d": resid_vol_60,
            "std60_x_ret_120d": std60_x_ret_120,
            "high_52wk_dist_x_ret_vol_60d": high_dist_x_ret_vol_60,
        },
        index=c.index,
    )


def qlib_std60(close: pd.Series) -> pd.Series:
    """The qlib STD60 feature (std of close LEVELS / close_today) — exposed for
    tests/diagnostics so the reproduced #476 §3 decomposition (H3: hypothesized
    to conflate trend with dispersion on trending names) stays reproducible here."""
    c = close.astype(np.float64)
    return c.rolling(_VOL_WINDOW, min_periods=_VOL_WINDOW).std(ddof=1) / c


def augment_panel_with_vol_trend_features(
    panel: pd.DataFrame,
    close_by_ticker: Mapping[str, pd.Series],
) -> pd.DataFrame:
    """Join the ``vol_trend_v2`` columns onto a (ticker, date) panel.

    Research/fixture helper for training-side experiments: for each ticker in
    ``close_by_ticker`` the features are computed from that ticker's own close
    series and merged onto the panel by exact (ticker, date). Panel rows whose
    ticker/date has no computed value get NaN. Existing panel columns are never
    touched; exactly the ``VOL_TREND_FEATURES`` columns are added.
    """
    if any(col in panel.columns for col in VOL_TREND_FEATURES):
        raise ValueError("panel already carries vol_trend_v2 columns; refusing to overwrite")
    frames = []
    for ticker, close in close_by_ticker.items():
        feats = compute_vol_trend_features(close)
        feats = feats.reset_index().rename(columns={feats.index.name or "index": "date"})
        feats.insert(0, "ticker", ticker)
        frames.append(feats)
    if not frames:
        raise ValueError("close_by_ticker is empty")
    features = pd.concat(frames, ignore_index=True)
    features["date"] = pd.to_datetime(features["date"])
    out = panel.copy()
    out["date"] = pd.to_datetime(out["date"])
    return out.merge(features, on=["ticker", "date"], how="left", validate="many_to_one")
