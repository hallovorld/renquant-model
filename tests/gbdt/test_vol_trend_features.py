"""Vol/trend feature-set v2 (C1/F1 returns-based vol + C2/F2 trend interactions).

Candidate implementation for the preregistered baseline-vs-vol_trend_v2
experiment orchestrator #476 §7 specifies as required future work — NOT a
validated fix. #476's H3 ("qlib STD60 = std(close LEVELS)/close mistakes trend
for calm on trending names") is, after Codex's review, an explicit hypothesis:
"mechanical decomposition independently reproduced [on the META path]；
causal-mechanism claim not established" (#476 §3). The reproduced decomposition
itself (during META's 07-06..07-10 +11.5% rally STD60 fell ~10% almost entirely
via the denominator while 60d returns-vol ROSE) is a re-verified fact about that
one path, not a general-adoption verdict about the feature or the fitted model.
These tests pin:

1. recipe correctness on synthetic fixtures (brute-force golden checks);
2. the reproduced-decomposition property, on synthetic fixtures mirroring the
   #476 §3 path — returns-vol/resid-vol do not read a smooth rally as "calming
   down", and the interactions separate "trending-quiet" from "flat-quiet"
   names. This demonstrates the candidate features behave as designed on a
   controlled fixture; it does NOT demonstrate that STD60 is a defect in the
   live model or that adopting C1/C2 improves it — that is exactly what the
   not-yet-run #476 §7 preregistered comparison would establish;
3. the version-key mechanics — the ``vol_trend_v2`` stamp (nested inside the
   PREDICTIVE-classified ``feature_addendum_v1`` recipe-identity field) appears
   only when the columns are present; baseline and Track-B-only panels produce
   byte-identical stamps/artifacts (old-version outputs unchanged), and the
   stamp binds into ``model_content_sha256`` with no fingerprint-table change;
4. WF-retrain readiness accepts the new set only behind the declared version
   key, with a byte-identical report for configs that do not declare it; and
   the experiment-contract promotion gate — a config declaring ``vol_trend_v2``
   must also declare an ``experiment_id``, and the artifact must stamp a
   matching ``experiment_id`` + non-empty ``run_bundle_ref``, or the recipe is
   never promotion-eligible regardless of the feature/addendum checks passing.
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
    config_declared_vol_trend_experiment_id,
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


# ── 2. the reproduced #476 §3 decomposition, on controlled synthetic fixtures.
# These pin that C1/C2 behave as designed on a fixture built to mirror the
# reproduced META-path decomposition; they do NOT establish that this
# generalizes to the live model or corpus — see #476 §7 for what would. ──


def test_smooth_rally_deflates_std60_but_not_returns_vol() -> None:
    """Synthetic fixture mirroring the #476 §3 META-path decomposition: 55
    flat-noise days then a sharp smooth +11.5% rally. On this fixture qlib
    STD60 falls mechanically (denominator) while the candidate returns-vol
    feature does NOT fall — it rises (rally returns add dispersion). This is a
    controlled-fixture property, not a claim about the live model."""
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
        "qlib STD60 must fall >5% across the rally on this fixture (denominator effect)"
    )
    assert feats["ret_vol_60d"].iloc[after] >= feats["ret_vol_60d"].iloc[before], (
        "returns-vol must NOT read the orderly rally as 'calming down' on this fixture"
    )


def test_trending_quiet_vs_flat_quiet_separate() -> None:
    """The required separation on this fixture: same return noise, drift on vs
    off. C1/F1 gives the two names the SAME risk reading; the C2/F2 interaction
    tells them apart."""
    trending = compute_vol_trend_features(_trending_quiet())
    flat = compute_vol_trend_features(_flat_quiet())
    t = -1

    # F1: identical noise scale → returns-vol agrees across the two names.
    ratio = trending["ret_vol_60d"].iloc[t] / flat["ret_vol_60d"].iloc[t]
    assert 0.75 < ratio < 1.33, "returns-vol must not vary with trend on this fixture"

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
    """On this controlled fixture: adding a linear trend to the SAME additive
    noise leaves the 60d linear-fit residuals bit-identical (the fit absorbs the
    trend), while qlib STD60 inflates with the trend. This reproduces, on a
    fixture, the same numerator/denominator mechanics #476 §3 measured on the
    META path; it is not a claim that this generalizes as a defect across all
    trending names in the live corpus (that is exactly the open question #476
    §7's preregistered comparison would answer)."""
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
    # Experimentation is unrestricted: computing/training vol_trend_v2 with no
    # experiment context set requires no special declaration; the stamp simply
    # carries None placeholders (readiness — not training — is what gates on
    # these being populated; see the WF-retrain-readiness tests below).
    assert stamp["experiment_id"] is None
    assert stamp["run_bundle_ref"] is None
    # No Track B columns in this fixture → no Track B keys are invented.
    assert "track_b_features_active" not in addendum
    for col in VOL_TREND_FEATURES:
        assert col in ctx.feat_cols


def test_load_panel_task_stamps_experiment_contract_when_ctx_provides_it(tmp_path: Path) -> None:
    """When the caller (the orchestrator's retrain driver) sets ctx.experiment_id
    / ctx.experiment_run_bundle_ref, LoadPanelTask carries them verbatim into the
    nested vol_trend_v2 stamp — this is what lets the WF-retrain-readiness
    experiment-contract check later confirm the artifact belongs to a declared,
    preregistered experiment run."""
    data_dir = _make_vol_trend_data_dir(tmp_path)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=10, data_dir=str(data_dir),
        experiment_id="std60-baseline-vs-vol_trend_v2-2026w29",
        experiment_run_bundle_ref="renquant-artifacts:evidence/std60-baseline-vs-vol_trend_v2-2026w29/run-bundle.json",
    )
    LoadPanelTask().run(ctx)

    stamp = ctx.extra_artifact_fields["feature_addendum_v1"]["vol_trend_v2"]
    assert stamp["experiment_id"] == "std60-baseline-vs-vol_trend_v2-2026w29"
    assert (stamp["run_bundle_ref"]
            == "renquant-artifacts:evidence/std60-baseline-vs-vol_trend_v2-2026w29/run-bundle.json")


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


_EXPERIMENT_ID = "std60-baseline-vs-vol_trend_v2-2026w29"
_RUN_BUNDLE_REF = f"renquant-artifacts:evidence/{_EXPERIMENT_ID}/run-bundle.json"


def _declared_config(*, experiment_id: str | None = _EXPERIMENT_ID) -> dict:
    config = {
        "full_wf_retrain": True,
        "feature_set_version": "vol_trend_v2",
        "required_features": list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES),
        "required_artifact_metadata": {"one_of": ["sanity_triad", "verdict_metadata"]},
    }
    if experiment_id is not None:
        config["experiment_id"] = experiment_id
    return config


def _artifact_with(
    features: list[str],
    *,
    v2_stamp: bool,
    experiment_id: str | None = None,
    run_bundle_ref: str | None = None,
) -> dict:
    art: dict = {
        "feature_cols": features,
        "feature_addendum_v1": {"track_b_features_active": list(TRACK_B_FEATURES)},
        "sanity_triad": {"present": True},
    }
    if v2_stamp:
        stamp: dict = {
            "feature_set_version": VOL_TREND_FEATURE_SET_VERSION,
            "vol_trend_features_active": list(VOL_TREND_FEATURES),
        }
        if experiment_id is not None:
            stamp["experiment_id"] = experiment_id
        if run_bundle_ref is not None:
            stamp["run_bundle_ref"] = run_bundle_ref
        art["feature_addendum_v1"]["vol_trend_v2"] = stamp
    return art


def test_readiness_accepts_declared_vol_trend_config_and_artifact() -> None:
    """The full-acceptance path: config declares BOTH feature_set_version and a
    matching experiment_id; the artifact stamp carries that same experiment_id
    plus a run_bundle_ref. Only then is report['ok'] True."""
    config = _declared_config()
    assert config_declares_vol_trend_feature_set(config)
    artifact = _artifact_with(
        list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES) + ["a0"], v2_stamp=True,
        experiment_id=_EXPERIMENT_ID, run_bundle_ref=_RUN_BUNDLE_REF,
    )
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert report["ok"], report
    assert report["feature_set_version"] == VOL_TREND_FEATURE_SET_VERSION
    assert report["required_vol_trend_features"] == list(VOL_TREND_FEATURES)
    assert report["vol_trend_experiment_id"] == _EXPERIMENT_ID
    names = {c["name"] for c in report["checks"]}
    assert {"config_requires_vol_trend_features",
            "config_requires_vol_trend_experiment_id",
            "artifact_contains_vol_trend_features",
            "artifact_stamps_vol_trend_addendum",
            "artifact_stamps_vol_trend_experiment_contract"} <= names


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
    assert "vol_trend_experiment_id" not in report


# ── 6. the experiment-contract promotion-eligibility gate ──
#
# vol_trend_v2 is a candidate implementation for the #476 §7 preregistered
# experiment, not a validated replacement (see module docstrings). These tests
# pin that an artifact tagged vol_trend_v2 is NEVER promotion-eligible
# (report['ok']) without a declared, matching experiment_id + a non-empty
# run_bundle_ref — closing exactly the gap Codex's review flagged.


def test_readiness_fails_when_config_omits_experiment_id() -> None:
    """The recipe must remain disabled outside a declared experiment: a config
    that opts into vol_trend_v2 but declares no experiment_id fails readiness
    even when every feature/addendum check would otherwise pass."""
    config = _declared_config(experiment_id=None)
    artifact = _artifact_with(
        list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES) + ["a0"], v2_stamp=True,
        experiment_id=None, run_bundle_ref=_RUN_BUNDLE_REF,
    )
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert not report["ok"]
    failed = {c["name"] for c in report["checks"] if not c["ok"]}
    assert "config_requires_vol_trend_experiment_id" in failed
    assert "artifact_stamps_vol_trend_experiment_contract" in failed
    assert report["vol_trend_experiment_id"] is None


def test_readiness_fails_when_artifact_missing_experiment_contract() -> None:
    """An artifact tagged vol_trend_v2 (feature/addendum checks pass) but with NO
    experiment_id/run_bundle_ref stamped is NOT promotion-eligible, even though
    the config itself declares a valid experiment_id."""
    config = _declared_config()
    artifact = _artifact_with(
        list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES) + ["a0"], v2_stamp=True,
    )  # no experiment_id / run_bundle_ref on the artifact stamp
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert not report["ok"]
    failed = {c["name"] for c in report["checks"] if not c["ok"]}
    assert "artifact_stamps_vol_trend_experiment_contract" in failed
    # The feature/addendum checks (a different concern) still pass — this is
    # specifically the experiment-contract gate doing its job.
    assert "artifact_contains_vol_trend_features" not in failed
    assert "artifact_stamps_vol_trend_addendum" not in failed


def test_readiness_fails_on_experiment_id_mismatch() -> None:
    """An artifact stamped with a DIFFERENT experiment_id than the config
    declares is not promotion-eligible — this closes the "re-stamp any old
    vol_trend_v2 artifact with a fresh experiment_id after the fact" loophole,
    since the config's declared id and the artifact's stamped id must agree."""
    config = _declared_config()
    artifact = _artifact_with(
        list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES) + ["a0"], v2_stamp=True,
        experiment_id="some-other-unrelated-experiment", run_bundle_ref=_RUN_BUNDLE_REF,
    )
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert not report["ok"]
    failed = {c["name"] for c in report["checks"] if not c["ok"]}
    assert "artifact_stamps_vol_trend_experiment_contract" in failed


def test_readiness_fails_when_run_bundle_ref_missing() -> None:
    """A matching experiment_id alone is not sufficient — a non-empty
    run_bundle_ref (pointing at the persisted evidence for that specific run)
    is also required."""
    config = _declared_config()
    artifact = _artifact_with(
        list(TRACK_B_FEATURES) + list(VOL_TREND_FEATURES) + ["a0"], v2_stamp=True,
        experiment_id=_EXPERIMENT_ID, run_bundle_ref=None,
    )
    report = validate_full_wf_retrain_readiness(config, artifact)
    assert not report["ok"]
    failed = {c["name"] for c in report["checks"] if not c["ok"]}
    assert "artifact_stamps_vol_trend_experiment_contract" in failed


def test_vol_trend_v2_disabled_by_default_in_production_config() -> None:
    """The production readiness config must NOT declare vol_trend_v2 — the
    recipe stays disabled outside an explicitly-declared experiment. This is a
    direct check against the actual committed config file, not a restated
    constant, so it fails if anyone flips the production config on directly."""
    config_path = (
        Path(__file__).resolve().parents[2]
        / "configs" / "gbdt_track_b_full_wf_retrain_readiness.json"
    )
    config = json.loads(config_path.read_text())
    assert not config_declares_vol_trend_feature_set(config)
    assert config_declared_vol_trend_experiment_id(config) is None
