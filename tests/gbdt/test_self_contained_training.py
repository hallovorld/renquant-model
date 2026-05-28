"""The data-side pipeline trains a model end-to-end with NO umbrella / real data.

Builds tiny synthetic parquets + stats in a tmp data_dir, runs the full
build_training_pipeline (LoadPanel → BuildNormalization → CV → TrainBooster →
BuildArtifact → fingerprint → smoke → write), and asserts a complete artifact.
This proves renquant-model trains the panel-LTR model self-contained — the
orchestrator only points it at a data directory.
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
    ALPHA_STATS_FILE, FUND_COLS, FUND_FILE, PANEL_FILE,
)
from renquant_model_gbdt.panel_trainer import PANEL_LTR_PARAMS  # noqa: E402


def _make_data_dir(tmp: Path, n_dates: int = 60, n_tickers: int = 12, seed: int = 9) -> Path:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    alpha_cols = ["a0", "a1", "a2"]
    rows = []
    for d in dates:
        for t in range(n_tickers):
            x = rng.normal(size=3)
            rows.append({"date": d, "ticker": f"T{t}", "a0": x[0], "a1": x[1], "a2": x[2],
                         "fwd_60d_excess": 0.6 * x[0] - 0.3 * x[1] + rng.normal(scale=0.5)})
    pd.DataFrame(rows).to_parquet(tmp / PANEL_FILE)

    (tmp / ALPHA_STATS_FILE).write_text(json.dumps({
        "feature_cols": alpha_cols,
        "feature_means": [0.0, 0.0, 0.0],
        "feature_stds": [1.0, 1.0, 1.0],
    }))
    # fund file is always read by build_normalization (even if the panel has no fund cols)
    fund_rows = [{"date": d, "ticker": f"T{t}", **{c: float(rng.normal()) for c in FUND_COLS}}
                 for d in dates for t in range(n_tickers)]
    pd.DataFrame(fund_rows).to_parquet(tmp / FUND_FILE)
    return tmp


def test_self_contained_pipeline_trains_complete_artifact(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path)
    out = tmp_path / "panel-ltr.json"
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=25,
        cv_n_splits=3, cv_embargo_days=2,
        data_dir=str(data_dir), output_path=str(out), train_run_id="selftest",
    )
    result = build_training_pipeline().run(ctx)

    assert result.ok and result.name == "panel-gbdt-training"
    assert [s.job_name for s in result.steps] == ["DataPrepJob", "ModelTrainingJob", "ArtifactContractJob"]
    art = ctx.artifact
    assert art is not None
    assert art["kind"] == "panel_ltr_xgboost" and art["version"] == 3
    assert art["booster_raw_json"]
    assert art["config_fingerprint"].startswith("sha256:")
    assert art["feature_cols"] == ["a0", "a1", "a2"]
    assert art["oos_per_fold_ic"] and all(np.isfinite(v) for v in art["oos_per_fold_ic"])
    assert art["metadata"]["inference_smoke_test"]["all_finite"] is True
    # persisted + reloadable
    assert out.exists()
    reloaded = json.loads(out.read_text())
    assert reloaded["config_fingerprint"] == art["config_fingerprint"]


def test_self_contained_skip_cv(tmp_path: Path) -> None:
    data_dir = _make_data_dir(tmp_path, n_dates=30)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=15, skip_cv=True,
        data_dir=str(data_dir), train_run_id="x",
    )
    build_training_pipeline().run(ctx)
    assert ctx.artifact is not None and "oos_mean_ic" not in ctx.artifact
    assert ctx.booster is not None


def test_exclude_features_drops_columns(tmp_path: Path) -> None:
    """exclude_features removes the named columns from the trained feature set."""
    data_dir = _make_data_dir(tmp_path, n_dates=30)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=15, skip_cv=True,
        data_dir=str(data_dir), train_run_id="x", exclude_features=["a1"],
    )
    build_training_pipeline().run(ctx)
    assert ctx.feat_cols == ["a0", "a2"]
    assert ctx.artifact["feature_cols"] == ["a0", "a2"]
