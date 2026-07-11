"""Vol/trend feature-set v2 (F1 returns-based vol + F2 trend interactions).

Provenance: orchestrator #476 (STD60 rule provenance) + #475 (META score
attribution). qlib STD60 = std(close LEVELS)/close is 92-101% trend-confounded
on trending names — during META's 07-06..07-10 +11.5% rally STD60 fell purely
via the denominator while 60d returns-vol ROSE. These tests pin:

1. recipe correctness on synthetic fixtures (brute-force golden checks);
2. the honesty property — returns-vol/resid-vol do not read a smooth rally as
   "calming down", and the interactions separate "trending-quiet" from
   "flat-quiet" names;
3. the version-key mechanics — the ``vol_trend_v2`` stamp (nested inside the
   PREDICTIVE-classified ``feature_addendum_v1`` recipe-identity field) appears
   only when the columns are present; baseline and Track-B-only panels produce
   byte-identical stamps/artifacts (old-version outputs unchanged), and the
   stamp binds into ``model_content_sha256`` with no fingerprint-table change;
4. WF-retrain readiness accepts the new set only behind the declared version
   key, with a byte-identical report for configs that do not declare it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

xgb = pytest.importorskip("xgboost")

from renquant_model_gbdt import GbdtTrainingContext, build_training_pipeline  # noqa: E402
from renquant_model_gbdt.panel_data import (  # noqa: E402
    ALPHA_STATS_FILE,
    FUND_COLS,
    FUND_FILE,
    PANEL_FILE,
    TRACK_B_FEATURES,
    LoadPanelTask,
)
from renquant_model_gbdt.panel_trainer import PANEL_LTR_PARAMS  # noqa: E402
from renquant_model_gbdt.pipelines import _RUNTIME_ARTIFACT_FIELDS  # noqa: E402
from renquant_common.model_fingerprint import model_content_sha256  # noqa: E402
from renquant_model_gbdt.vol_trend_features import (  # noqa: E402
    RET_VOL_FEATURES,
    TREND_INTERACTION_FEATURES,
    VOL_TREND_FEATURE_SET_VERSION,
    VOL_TREND_FEATURES,
    augment_panel_with_vol_trend_features,
    compute_vol_trend_features,
    qlib_std60,
)
from renquant_model_gbdt.wf_retrain_readiness import (  # noqa: E402
    config_declares_vol_trend_feature_set,
    validate_full_wf_retrain_readiness,
)

# ── synthetic close-series fixtures ──


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2022-01-03", periods=n, freq="B")


def _geometric_series(n: int, *, drift: float, noise: float, seed: int,
                      start: float = 100.0) -> pd.Series:
    """Geometric price path: r_t = drift + noise_t (same noise scale throughout)."""
    rng = np.random.default_rng(seed)
    rets = drift + rng.normal(scale=noise, size=n - 1)
    close = start * np.concatenate([[1.0], np.cumprod(1.0 + rets)])
    return pd.Series(close, index=_dates(n))


def _flat_quiet(n: int = 420, seed: int = 7) -> pd.Series:
    """Quiet dead money: no drift, small return noise."""
    return _geometric_series(n, drift=0.0, noise=0.003, seed=seed)


def _trending_quiet(n: int = 420, seed: int = 7) -> pd.Series:
    """Quiet steady riser: strong drift, the SAME small return noise."""
    return _geometric_series(n, drift=0.0015, noise=0.003, seed=seed)


def _volatile(n: int = 420, seed: int = 11) -> pd.Series:
    return _geometric_series(n, drift=0.0, noise=0.03, seed=seed)


# ── 1. recipe correctness (brute-force goldens) ──


def test_feature_set_names_and_count() -> None:
    """4-8 self-documenting columns; F1 (returns-vol) + F2 (trend interaction)."""
    assert VOL_TREND_FEATURES == RET_VOL_FEATURES + TREND_INTERACTION_FEATURES
    assert 4 <= len(VOL_TREND_FEATURES) <= 8
    assert set(RET_VOL_FEATURES) == {
        "ret_vol_20d", "ret_vol_60d", "ret_semivol_down_60d",
    }
    assert set(TREND_INTERACTION_FEATURES) == {
        "resid_vol_60d", "std60_x_ret_120d", "high_52wk_dist_x_ret_vol_60d",
    }
    assert VOL_TREND_FEATURE_SET_VERSION == "vol_trend_v2"
    # No collision with the existing recipe families.
    assert not set(VOL_TREND_FEATURES) & set(TRACK_B_FEATURES)
    assert not set(VOL_TREND_FEATURES) & set(FUND_COLS)


def test_ret_vol_matches_bruteforce_std_of_returns() -> None:
    close = _volatile(200, seed=3)
    feats = compute_vol_trend_features(close)
    r = (close / close.shift(1) - 1.0).to_numpy()
    for window, col in ((20, "ret_vol_20d"), (60, "ret_vol_60d")):
        for t in (window + 5, 120, 199):
            expected = np.std(r[t - window + 1: t + 1], ddof=1)
            assert feats[col].iloc[t] == pytest.approx(expected, rel=1e-12)


def test_semivol_matches_bruteforce_and_is_downside_only() -> None:
    close = _volatile(200, seed=5)
    feats = compute_vol_trend_features(close)
    r = (close / close.shift(1) - 1.0).to_numpy()
    for t in (80, 150, 199):
        window = np.minimum(r[t - 59: t + 1], 0.0)
        expected = np.sqrt((window ** 2).sum() / 59.0)
        assert feats["ret_semivol_down_60d"].iloc[t] == pytest.approx(expected, rel=1e-12)
    # A monotonic riser (all returns positive) has ZERO downside semivol —
    # returns-vol still sees its noise, but no downside risk is invented.
    riser = pd.Series(100.0 * 1.002 ** np.arange(200), index=_dates(200))
    riser_feats = compute_vol_trend_features(riser)
    assert (riser_feats["ret_semivol_down_60d"].iloc[60:] == 0.0).all()


def test_resid_vol_matches_bruteforce_polyfit() -> None:
    close = _trending_quiet(160, seed=13)
    feats = compute_vol_trend_features(close)
    y = close.to_numpy()
    x = np.arange(60, dtype=float)
    for t in (59, 100, 159):
        w = y[t - 59: t + 1]
        coef = np.polyfit(x, w, 1)
        ssr = float(((w - np.polyval(coef, x)) ** 2).sum())
        expected = np.sqrt(ssr / 58.0) / y[t]
        assert feats["resid_vol_60d"].iloc[t] == pytest.approx(expected, rel=1e-9)


def test_warmup_nan_policy_strict_full_window() -> None:
    close = _flat_quiet(300, seed=2)
    feats = compute_vol_trend_features(close)
    first_valid = {
        "ret_vol_20d": 20,          # 20 returns need 21 closes
        "ret_vol_60d": 60,
        "ret_semivol_down_60d": 60,
        "resid_vol_60d": 59,        # 60 closes
        "std60_x_ret_120d": 120,    # max(60 closes, 120d return)
        "high_52wk_dist_x_ret_vol_60d": 251,  # 252d rolling high dominates
    }
    for col, idx in first_valid.items():
        assert feats[col].iloc[:idx].isna().all(), f"{col}: warmup must be NaN"
        assert feats[col].iloc[idx:].notna().all(), f"{col}: post-warmup must be finite"


# ── 2. the honesty property (the #475/#476 confound, on synthetic fixtures) ──


def test_smooth_rally_deflates_std60_but_not_returns_vol() -> None:
    """META-week replication (#475): 55 flat-noise days then a sharp smooth
    +11.5% rally. qlib STD60 falls mechanically (denominator); the honest
    returns-vol does NOT fall — it rises (rally returns add dispersion)."""
    rng = np.random.default_rng(42)
    n_flat = 120
    rets_flat = rng.normal(scale=0.01, size=n_flat - 1)
    rets_rally = np.full(5, 1.115 ** (1 / 5) - 1.0)  # +11.5% over 5 sessions
    close = pd.Series(
        600.0 * np.concatenate([[1.0], np.cumprod(1.0 + np.concatenate([rets_flat, rets_rally]))]),
        index=_dates(n_flat + 5),
    )
    feats = compute_vol_trend_features(close)
    before, after = -6, -1  # last pre-rally session vs last rally session

    std60 = qlib_std60(close)
    assert std60.iloc[after] < std60.iloc[before] * 0.95, (
        "qlib STD60 must fall >5% across the rally (the denominator confound)"
    )
    assert feats["ret_vol_60d"].iloc[after] >= feats["ret_vol_60d"].iloc[before], (
        "returns-vol must NOT read the orderly rally as 'calming down'"
    )


def test_trending_quiet_vs_flat_quiet_separate() -> None:
    """The required separation: same return noise, drift on vs off. F1 says the
    two names carry the SAME risk; the F2 interaction tells them apart."""
    trending = compute_vol_trend_features(_trending_quiet())
    flat = compute_vol_trend_features(_flat_quiet())
    t = -1

    # F1: identical noise scale → returns-vol agrees across the two names.
    ratio = trending["ret_vol_60d"].iloc[t] / flat["ret_vol_60d"].iloc[t]
    assert 0.75 < ratio < 1.33, "returns-vol must not be trend-confounded"

    # F2: the interaction separates trending-quiet from flat-quiet by an order
    # of magnitude (drift 0.15%/day → 120d return ≈ +20% vs ≈ 0).
    trending_ix = trending["std60_x_ret_120d"].iloc[t]
    flat_ix = flat["std60_x_ret_120d"].iloc[t]
    assert trending_ix > 0.0
    assert abs(trending_ix) > 5.0 * abs(flat_ix), (
        f"std60_x_ret_120d must separate quiet-riser ({trending_ix:.5f}) "
        f"from quiet-dead-money ({flat_ix:.5f})"
    )

    # And a genuinely volatile name is separated by F1 itself.
    volatile = compute_vol_trend_features(_volatile())
    assert volatile["ret_vol_60d"].iloc[t] > 3.0 * trending["ret_vol_60d"].iloc[t]


def test_resid_vol_is_exactly_trend_invariant_while_std60_is_confounded() -> None:
    """Adding a linear trend to the SAME additive noise leaves the 60d linear-fit
    residuals bit-identical (the fit absorbs the trend), while qlib STD60
    inflates with the trend — the 92-101% confound from #476."""
    n = 220
    rng = np.random.default_rng(9)
    noise = rng.normal(scale=0.5, size=n)
    flat_close = pd.Series(100.0 + noise, index=_dates(n))
    trend_close = pd.Series(100.0 + 0.8 * np.arange(n) + noise, index=_dates(n))

    flat_feats = compute_vol_trend_features(flat_close)
    trend_feats = compute_vol_trend_features(trend_close)
    # resid std (resid_vol * close undoes the denominator) is identical.
    flat_resid_std = (flat_feats["resid_vol_60d"] * flat_close).iloc[59:]
    trend_resid_std = (trend_feats["resid_vol_60d"] * trend_close).iloc[59:]
    np.testing.assert_allclose(flat_resid_std, trend_resid_std, rtol=1e-6)

    # qlib STD60 numerator explodes with the trend on the same noise.
    flat_num = (qlib_std60(flat_close) * flat_close).iloc[-1]
    trend_num = (qlib_std60(trend_close) * trend_close).iloc[-1]
    assert trend_num > 3.0 * flat_num


def test_high_52wk_dist_interaction_zero_at_high_and_positive_in_drawdown() -> None:
    # A monotone riser sits AT its 52wk high: interaction pins to exactly 0 —
    # "quiet at highs" is not confused with "volatile in a hole".
    riser = pd.Series(100.0 * 1.001 ** np.arange(400), index=_dates(400))
    riser_feats = compute_vol_trend_features(riser)
    assert (riser_feats["high_52wk_dist_x_ret_vol_60d"].iloc[251:] == 0.0).all()

    # A name 30% off its high with real vol carries a clearly positive value.
    n = 400
    rng = np.random.default_rng(21)
    rets = np.concatenate([
        np.full(300, 0.001), np.full(30, -0.012),
        rng.normal(scale=0.02, size=n - 1 - 330),
    ])
    drawdown = pd.Series(100.0 * np.concatenate([[1.0], np.cumprod(1 + rets)]),
                         index=_dates(n))
    dd_feats = compute_vol_trend_features(drawdown)
    assert dd_feats["high_52wk_dist_x_ret_vol_60d"].iloc[-1] > 0.002


# ── 3. augmentation helper ──


def test_augment_panel_joins_on_ticker_date_and_preserves_columns() -> None:
    closes = {"AAA": _trending_quiet(300, seed=1), "BBB": _flat_quiet(300, seed=2)}
    dates = closes["AAA"].index[260:280]
    rows = [
        {"date": d, "ticker": t, "a0": float(i), "fwd_60d_excess": 0.1}
        for i, (t, d) in enumerate((t, d) for t in closes for d in dates)
    ]
    panel = pd.DataFrame(rows)
    out = augment_panel_with_vol_trend_features(panel, closes)

    assert list(out.columns) == list(panel.columns) + list(VOL_TREND_FEATURES)
    assert len(out) == len(panel)
    pd.testing.assert_series_equal(out["a0"], panel["a0"])  # untouched
    # Values line up with the per-ticker computation at the exact date.
    expected = compute_vol_trend_features(closes["AAA"]).loc[dates[0], "ret_vol_60d"]
    got = out.loc[(out["ticker"] == "AAA") & (out["date"] == dates[0]), "ret_vol_60d"].iloc[0]
    assert got == pytest.approx(expected, rel=1e-12)
    # Refuses to double-augment.
    with pytest.raises(ValueError, match="already carries"):
        augment_panel_with_vol_trend_features(out, closes)


# ── 4. version-key mechanics (feature_addendum_v2 / vol_trend_v2) ──


def _write_common_sidecars(tmp: Path, alpha_cols: list[str], dates, tickers) -> None:
    rng = np.random.default_rng(0)
    (tmp / ALPHA_STATS_FILE).write_text(json.dumps({
        "feature_cols": alpha_cols,
        "feature_means": [0.0] * len(alpha_cols),
        "feature_stds": [1.0] * len(alpha_cols),
    }))
    fund_rows = [
        {"date": d, "ticker": t, **{c: float(rng.normal()) for c in FUND_COLS}}
        for d in dates for t in tickers
    ]
    pd.DataFrame(fund_rows).to_parquet(tmp / FUND_FILE)


def _make_baseline_data_dir(tmp: Path, n_dates: int = 60, n_tickers: int = 12,
                            seed: int = 3) -> Path:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    tickers = [f"T{t}" for t in range(n_tickers)]
    rows = []
    for d in dates:
        for t in tickers:
            x = rng.normal(size=2)
            rows.append({
                "date": d, "ticker": t, "a0": x[0], "a1": x[1],
                "fwd_60d_excess": 0.5 * x[0] + rng.normal(scale=0.5),
            })
    pd.DataFrame(rows).to_parquet(tmp / PANEL_FILE)
    _write_common_sidecars(tmp, ["a0", "a1"], dates, tickers)
    return tmp


def _make_vol_trend_data_dir(tmp: Path, n_dates: int = 60, n_tickers: int = 12,
                             seed: int = 3, with_track_b: bool = False) -> Path:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    tickers = [f"T{t}" for t in range(n_tickers)]
    rows = []
    for d in dates:
        for t in tickers:
            x = rng.normal(size=2)
            row = {
                "date": d, "ticker": t, "a0": x[0], "a1": x[1],
                **{c: float(abs(rng.normal()) * 0.02) for c in VOL_TREND_FEATURES},
                "fwd_60d_excess": 0.5 * x[0] + rng.normal(scale=0.5),
            }
            if with_track_b:
                row.update({c: float(rng.normal()) for c in TRACK_B_FEATURES})
            rows.append(row)
    pd.DataFrame(rows).to_parquet(tmp / PANEL_FILE)
    _write_common_sidecars(tmp, ["a0", "a1"], dates, tickers)
    return tmp


def test_load_panel_task_stamps_v2_addendum_when_columns_present(tmp_path: Path) -> None:
    data_dir = _make_vol_trend_data_dir(tmp_path)
    ctx = GbdtTrainingContext(params=dict(PANEL_LTR_PARAMS), num_boost_round=10,
                              data_dir=str(data_dir))
    LoadPanelTask().run(ctx)

    addendum = ctx.extra_artifact_fields.get("feature_addendum_v1")
    assert addendum is not None
    stamp = addendum.get("vol_trend_v2")
    assert stamp is not None, "vol_trend_v2 stamp must nest under feature_addendum_v1"
    assert stamp["feature_set_version"] == VOL_TREND_FEATURE_SET_VERSION
    assert set(stamp["vol_trend_features_active"]) == set(VOL_TREND_FEATURES)
    assert stamp["source"] == "renquant-model:vol_trend_features"
    assert stamp["memo"] == "doc/progress/2026-07-11-vol-trend-feature-set-v2.md"
    # No Track B columns in this fixture → no Track B keys are invented.
    assert "track_b_features_active" not in addendum
    for col in VOL_TREND_FEATURES:
        assert col in ctx.feat_cols


def test_track_b_only_panel_stamps_byte_identical_pre_v2_addendum(tmp_path: Path) -> None:
    """Old-version proof at the stamp level: a Track-B-only panel (the current
    production recipe) must produce EXACTLY the pre-vol_trend addendum dict —
    same keys, same order, no vol_trend trace — so re-stamped artifacts hash
    identically under renquant-common's model_content_sha256."""
    rng = np.random.default_rng(17)
    dates = pd.date_range("2020-01-01", periods=30, freq="B")
    tickers = [f"T{t}" for t in range(6)]
    rows = []
    for d in dates:
        for t in tickers:
            x = rng.normal(size=5)
            rows.append({
                "date": d, "ticker": t, "a0": x[0],
                "mom_carry_12_1": x[1], "beta_dm": x[2],
                "rvar_total": x[3] ** 2, "idio_vol_market": abs(x[4]),
                "fwd_60d_excess": 0.4 * x[0] + rng.normal(scale=0.5),
            })
    pd.DataFrame(rows).to_parquet(tmp_path / PANEL_FILE)
    _write_common_sidecars(tmp_path, ["a0"], dates, tickers)

    ctx = GbdtTrainingContext(params=dict(PANEL_LTR_PARAMS), num_boost_round=10,
                              data_dir=str(tmp_path))
    LoadPanelTask().run(ctx)

    assert ctx.extra_artifact_fields["feature_addendum_v1"] == {
        "track_b_features_active": ["mom_carry_12_1", "beta_dm", "rvar_total",
                                    "idio_vol_market"],
        "source": "renquant-base-data:track_b_features",
        "memo": "doc/research/2026-06-02-track-b-feature-audit.md",
    }
    assert list(ctx.extra_artifact_fields["feature_addendum_v1"]) == [
        "track_b_features_active", "source", "memo",
    ]


def test_vol_trend_stamp_binds_into_model_content_fingerprint() -> None:
    """The minted version key is fingerprint-bound with NO renquant-common
    classification-table change: feature_addendum_v1 is already PREDICTIVE and
    hashed atomically, so two otherwise-identical payloads with/without the
    nested vol_trend_v2 stamp hash differently — and neither raises
    UnclassifiedKeyError (which a new top-level key would)."""
    base = {
        "params": {"objective": "rank:pairwise"},
        "feature_cols": ["a0", *VOL_TREND_FEATURES],
        "feature_addendum_v1": {
            "track_b_features_active": list(TRACK_B_FEATURES),
            "source": "renquant-base-data:track_b_features",
            "memo": "doc/research/2026-06-02-track-b-feature-audit.md",
        },
    }
    variant = json.loads(json.dumps(base))
    variant["feature_addendum_v1"]["vol_trend_v2"] = {
        "feature_set_version": VOL_TREND_FEATURE_SET_VERSION,
        "vol_trend_features_active": list(VOL_TREND_FEATURES),
    }
    assert model_content_sha256(base) != model_content_sha256(variant)


def test_load_panel_task_baseline_panel_untouched_by_v2(tmp_path: Path) -> None:
    """Old-version contract: a panel without the new columns produces NO v2
    stamp, no extra feat_cols, no new extra_artifact_fields — byte-identity
    with the current production recipe is preserved."""
    data_dir = _make_baseline_data_dir(tmp_path)
    ctx = GbdtTrainingContext(params=dict(PANEL_LTR_PARAMS), num_boost_round=10,
                              data_dir=str(data_dir))
    LoadPanelTask().run(ctx)

    assert "feature_addendum_v2" not in ctx.extra_artifact_fields
    assert ctx.extra_artifact_fields == {}
    assert ctx.feat_cols == ["a0", "a1"]


def test_baseline_full_pipeline_artifact_has_no_v2_trace(tmp_path: Path) -> None:
    """End-to-end old-version proof: the persisted artifact JSON from a baseline
    panel contains no vol_trend marker or column anywhere. (Byte-identity of the
    trainer itself is separately pinned by test_panel_trainer_parity.)"""
    data_dir = _make_baseline_data_dir(tmp_path)
    out = tmp_path / "panel-ltr.baseline.json"
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=10, cv_n_splits=2,
        cv_embargo_days=2, data_dir=str(data_dir), output_path=str(out),
        train_run_id="vol-trend-baseline-test",
    )
    result = build_training_pipeline().run(ctx)
    assert result.ok, f"pipeline failed: {result}"

    raw = out.read_text()
    assert "vol_trend" not in raw
    reloaded = json.loads(raw)
    assert "feature_addendum_v1" not in reloaded
    assert reloaded["feature_cols"] == ["a0", "a1"]


def test_full_pipeline_artifact_carries_v2_addendum(tmp_path: Path) -> None:
    data_dir = _make_vol_trend_data_dir(tmp_path, with_track_b=True)
    out = tmp_path / "panel-ltr.v2.json"
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=10, cv_n_splits=2,
        cv_embargo_days=2, data_dir=str(data_dir), output_path=str(out),
        train_run_id="vol-trend-v2-test",
    )
    result = build_training_pipeline().run(ctx)
    assert result.ok, f"pipeline failed: {result}"

    art = ctx.artifact
    assert art is not None
    addendum = art.get("feature_addendum_v1")
    assert addendum is not None
    stamp = addendum["vol_trend_v2"]
    assert stamp["feature_set_version"] == VOL_TREND_FEATURE_SET_VERSION
    assert set(stamp["vol_trend_features_active"]) == set(VOL_TREND_FEATURES)
    for col in VOL_TREND_FEATURES:
        assert col in art["feature_cols"]
    # Track B keys coexist untouched in the same addendum.
    assert set(addendum["track_b_features_active"]) == set(TRACK_B_FEATURES)
    # Round-trips through the persisted JSON.
    reloaded = json.loads(out.read_text())
    assert (reloaded["feature_addendum_v1"]["vol_trend_v2"]["feature_set_version"]
            == VOL_TREND_FEATURE_SET_VERSION)


def test_runtime_artifact_fields_propagate_the_addendum() -> None:
    """The DI-shell manifest already propagates feature_addendum_v1 — the nested
    vol_trend_v2 stamp rides it into the artifact manifest with no new field."""
    assert "feature_addendum_v1" in _RUNTIME_ARTIFACT_FIELDS


# ── 5. WF-retrain readiness behind the version key ──


def _declared_config() -> dict:
    return {
        "full_wf_retrain": True,
        "feature_set_version": "vol_trend_v2",
        "required_features": list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES),
        "required_artifact_metadata": {"one_of": ["sanity_triad", "verdict_metadata"]},
    }


def _artifact_with(features: list[str], *, v2_stamp: bool) -> dict:
    art: dict = {
        "feature_cols": features,
        "feature_addendum_v1": {"track_b_features_active": list(TRACK_B_FEATURES)},
        "sanity_triad": {"present": True},
    }
    if v2_stamp:
        art["feature_addendum_v1"]["vol_trend_v2"] = {
            "feature_set_version": VOL_TREND_FEATURE_SET_VERSION,
            "vol_trend_features_active": list(VOL_TREND_FEATURES),
        }
    return art


def test_readiness_accepts_declared_vol_trend_config_and_artifact() -> None:
    config = _declared_config()
    assert config_declares_vol_trend_feature_set(config)
    artifact = _artifact_with(
        list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES) + ["a0"], v2_stamp=True)
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert report["ok"], report
    assert report["feature_set_version"] == VOL_TREND_FEATURE_SET_VERSION
    assert report["required_vol_trend_features"] == list(VOL_TREND_FEATURES)
    names = {c["name"] for c in report["checks"]}
    assert {"config_requires_vol_trend_features",
            "artifact_contains_vol_trend_features",
            "artifact_stamps_vol_trend_addendum"} <= names


def test_readiness_fails_declared_config_when_artifact_missing_columns() -> None:
    config = _declared_config()
    artifact = _artifact_with(list(TRACK_B_FEATURES) + ["a0"], v2_stamp=False)
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert not report["ok"]
    failed = {c["name"] for c in report["checks"] if not c["ok"]}
    assert "artifact_contains_vol_trend_features" in failed
    assert "artifact_stamps_vol_trend_addendum" in failed


def test_readiness_report_unchanged_when_version_key_not_declared() -> None:
    """Zero default behavior change: an undeclared (current production) config
    yields the exact pre-v2 check list and no vol_trend report keys."""
    config = {
        "full_wf_retrain": True,
        "required_features": list(TRACK_B_FEATURES),
        "required_artifact_metadata": {"one_of": ["sanity_triad"]},
    }
    assert not config_declares_vol_trend_feature_set(config)
    artifact = _artifact_with(list(TRACK_B_FEATURES) + ["a0"], v2_stamp=False)
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert report["ok"], report
    assert [c["name"] for c in report["checks"]] == [
        "full_wf_retrain_config",
        "config_requires_track_b_features",
        "config_requires_triad_or_verdict_metadata",
        "artifact_contains_track_b_features",
        "artifact_stamps_track_b_addendum",
        "artifact_has_triad_or_verdict_metadata",
    ]
    assert "feature_set_version" not in report
    assert "required_vol_trend_features" not in report
