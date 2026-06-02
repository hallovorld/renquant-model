"""Track B (post renquant-base-data #16 rename): pin that ``LoadPanelTask``
correctly stamps ``feature_addendum_v1`` with all four post-#16 Track B
features when they appear in the panel.

The upstream feature was renamed ``idio_vol_3f`` → ``idio_vol_market`` (the
prior ``_3f`` suffix was a misnomer; production base-data callers pass
``sector_close=None`` so the feature is a SPY+size 2-factor residual, not
a 3-factor residual). Without this update, a panel produced by the fixed
base-data branch would carry ``idio_vol_market`` in ``feature_cols`` but
LoadPanelTask would NOT include it in ``feature_addendum_v1``, leaving the
recipe marker incomplete so consumers cannot distinguish the real 4-feature
variant from baseline.

Paired with umbrella RenQuant#120. Audit memo:
``doc/research/2026-06-02-track-b-feature-audit.md`` (in the umbrella).
§3.5: this is the same change as the umbrella's TRACK_B_FEATURES swap.
§7.2.1 R3 / §7.7: test ships in the SAME PR as the rename so the gate fires
on the first artifact.
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


def test_track_b_constant_uses_renamed_column() -> None:
    """Pin the post-#16 rename at the data-side source of truth. If anyone
    reverts the constant to ``idio_vol_3f`` this test catches it immediately.
    """
    assert "idio_vol_market" in TRACK_B_FEATURES
    assert "idio_vol_3f" not in TRACK_B_FEATURES
    # All four are present (recipe completeness).
    assert set(TRACK_B_FEATURES) == {
        "mom_carry_12_1", "beta_dm", "rvar_total", "idio_vol_market",
    }


def _make_track_b_data_dir(tmp: Path, n_dates: int = 60, n_tickers: int = 12,
                            seed: int = 17) -> Path:
    """Synthetic data_dir whose alpha158 panel carries the 4 post-#16
    Track B columns alongside a baseline alpha158 column.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    # 1 alpha158-style baseline col + 4 Track B cols (using the renamed name)
    alpha_cols = ["a0"]
    rows = []
    for d in dates:
        for t in range(n_tickers):
            x = rng.normal(size=5)
            rows.append({
                "date": d, "ticker": f"T{t}",
                "a0": x[0],
                "mom_carry_12_1": x[1],
                "beta_dm": x[2],
                "rvar_total": x[3] ** 2,            # non-negative by construction
                "idio_vol_market": abs(x[4]),       # the renamed column
                "fwd_60d_excess": 0.4 * x[0] + 0.2 * x[1] + rng.normal(scale=0.5),
            })
    pd.DataFrame(rows).to_parquet(tmp / PANEL_FILE)

    (tmp / ALPHA_STATS_FILE).write_text(json.dumps({
        "feature_cols": alpha_cols,
        "feature_means": [0.0],
        "feature_stds": [1.0],
    }))
    fund_rows = [
        {"date": d, "ticker": f"T{t}",
         **{c: float(rng.normal()) for c in FUND_COLS}}
        for d in dates for t in range(n_tickers)
    ]
    pd.DataFrame(fund_rows).to_parquet(tmp / FUND_FILE)
    return tmp


def test_load_panel_task_stamps_addendum_with_all_four_renamed_features(tmp_path: Path) -> None:
    """Regression: a panel containing the 4 post-#16 Track B columns
    (including the renamed ``idio_vol_market``) MUST be stamped with the
    complete addendum recipe — all 4 features listed in
    ``feature_addendum_v1.track_b_features_active``. Pre-fix, only 3 would
    have been listed because the constant still carried the old name.
    """
    data_dir = _make_track_b_data_dir(tmp_path)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS),
        num_boost_round=10,
        data_dir=str(data_dir),
    )
    LoadPanelTask().run(ctx)

    addendum = ctx.extra_artifact_fields.get("feature_addendum_v1")
    assert addendum is not None, (
        "feature_addendum_v1 MUST be stamped when Track B columns are present "
        "in the panel"
    )
    active = addendum["track_b_features_active"]
    # All 4 renamed Track B features must be listed (the WHOLE point of the
    # rename fix — distinguishing the real 4-feature variant from baseline).
    assert set(active) == {
        "mom_carry_12_1", "beta_dm", "rvar_total", "idio_vol_market",
    }, f"expected all 4 renamed Track B features in addendum; got {active!r}"
    assert addendum["source"] == "renquant-base-data:track_b_features"
    assert addendum["memo"] == "doc/research/2026-06-02-track-b-feature-audit.md"


def test_load_panel_task_includes_renamed_column_in_feat_cols(tmp_path: Path) -> None:
    """``feat_cols`` MUST include ``idio_vol_market`` when present in the
    panel (consumed by the trainer; absent here the model trains on the
    wrong recipe).
    """
    data_dir = _make_track_b_data_dir(tmp_path)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS),
        num_boost_round=10,
        data_dir=str(data_dir),
    )
    LoadPanelTask().run(ctx)

    assert "idio_vol_market" in ctx.feat_cols
    assert "mom_carry_12_1" in ctx.feat_cols
    assert "beta_dm" in ctx.feat_cols
    assert "rvar_total" in ctx.feat_cols


def test_load_panel_task_omits_addendum_when_no_track_b_columns(tmp_path: Path) -> None:
    """Baseline contract: a panel without any Track B columns produces NO
    ``feature_addendum_v1`` stamp. Preserves byte-identity with the
    baseline-172 recipe artifact.
    """
    rng = np.random.default_rng(3)
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    rows = []
    for d in dates:
        for t in range(8):
            x = rng.normal(size=2)
            rows.append({
                "date": d, "ticker": f"T{t}",
                "a0": x[0], "a1": x[1],
                "fwd_60d_excess": 0.5 * x[0] + rng.normal(scale=0.5),
            })
    pd.DataFrame(rows).to_parquet(tmp_path / PANEL_FILE)
    (tmp_path / ALPHA_STATS_FILE).write_text(json.dumps({
        "feature_cols": ["a0", "a1"],
        "feature_means": [0.0, 0.0],
        "feature_stds": [1.0, 1.0],
    }))
    fund_rows = [
        {"date": d, "ticker": f"T{t}",
         **{c: float(rng.normal()) for c in FUND_COLS}}
        for d in dates for t in range(8)
    ]
    pd.DataFrame(fund_rows).to_parquet(tmp_path / FUND_FILE)

    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS),
        num_boost_round=10,
        data_dir=str(tmp_path),
    )
    LoadPanelTask().run(ctx)
    assert "feature_addendum_v1" not in ctx.extra_artifact_fields


def test_full_pipeline_artifact_carries_renamed_addendum(tmp_path: Path) -> None:
    """End-to-end: when the full training pipeline runs against a panel
    carrying the 4 renamed Track B features, the persisted artifact's
    ``feature_addendum_v1`` lists all 4. Guards against any later pipeline
    step accidentally dropping the addendum (decoration risk per §7.7).
    """
    data_dir = _make_track_b_data_dir(tmp_path)
    out = tmp_path / "panel-ltr.json"
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS),
        num_boost_round=10,
        cv_n_splits=2,
        cv_embargo_days=2,
        data_dir=str(data_dir),
        output_path=str(out),
        train_run_id="track-b-rename-test",
    )
    result = build_training_pipeline().run(ctx)
    assert result.ok, f"pipeline failed: {result}"

    art = ctx.artifact
    assert art is not None
    addendum = art.get("feature_addendum_v1")
    assert addendum is not None, "artifact MUST carry feature_addendum_v1"
    assert set(addendum["track_b_features_active"]) == {
        "mom_carry_12_1", "beta_dm", "rvar_total", "idio_vol_market",
    }
    # Renamed column is also in feature_cols so the recipe fingerprint
    # distinguishes the variant from baseline-172.
    assert "idio_vol_market" in art["feature_cols"]

    # Persisted artifact round-trips.
    reloaded = json.loads(out.read_text())
    assert set(reloaded["feature_addendum_v1"]["track_b_features_active"]) == {
        "mom_carry_12_1", "beta_dm", "rvar_total", "idio_vol_market",
    }
