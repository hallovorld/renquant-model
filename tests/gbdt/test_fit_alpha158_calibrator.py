from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_gbdt.fit_calibrator_alpha158_fund import fit_alpha158_fund_calibrator


xgb = pytest.importorskip("xgboost")
pytest.importorskip("pyarrow")
pytest.importorskip("sklearn")


def _write_panel_and_artifact(tmp_path: Path) -> tuple[Path, Path, Path]:
    rng = np.random.default_rng(104)
    dates = pd.bdate_range("2024-01-02", periods=120)
    tickers = [f"T{i:02d}" for i in range(12)]
    rows = []
    raw_rows = []
    for date_idx, date in enumerate(dates):
        day_values = []
        for ticker_idx, ticker in enumerate(tickers):
            a0 = rng.normal() + ticker_idx / 20.0
            a1 = rng.normal() + date_idx / 500.0
            raw_return = 0.018 * a0 - 0.010 * a1 + rng.normal(0, 0.008)
            day_values.append((ticker, a0, a1, raw_return))
        raw_by_ticker = pd.Series({ticker: raw for ticker, _, _, raw in day_values})
        z = (raw_by_ticker - raw_by_ticker.mean()) / raw_by_ticker.std()
        for ticker, a0, a1, raw_return in day_values:
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "a0": a0,
                    "a1": a1,
                    "fwd_60d_excess": float(z[ticker]),
                }
            )
            raw_rows.append({"date": date, "ticker": ticker, "fwd_60d_excess_raw": raw_return})

    panel = pd.DataFrame(rows)
    raw_panel = pd.DataFrame(raw_rows)
    panel_path = tmp_path / "alpha158_291_fundamental_dataset.parquet"
    raw_path = tmp_path / "alpha158_291_fundamental_dataset_rawlabel.parquet"
    panel.to_parquet(panel_path, index=False)
    raw_panel.to_parquet(raw_path, index=False)

    dtrain = xgb.DMatrix(panel[["a0", "a1"]].values.astype(float), label=raw_panel["fwd_60d_excess_raw"].values)
    booster = xgb.train(
        {"objective": "reg:squarederror", "max_depth": 2, "eta": 0.2, "verbosity": 0, "seed": 104},
        dtrain,
        num_boost_round=20,
    )
    artifact = {
        "kind": "panel_ltr_xgboost",
        "feature_cols": ["a0", "a1"],
        "feature_means": [0.0, 0.0],
        "feature_stds": [1.0, 1.0],
        "feature_norm_kind": ["identity", "identity"],
        "label_col": "fwd_60d_excess",
        "fingerprint_schema_version": 1,
        "booster_raw_json": bytes(booster.save_raw(raw_format="json")).decode("utf-8"),
    }
    artifact_path = tmp_path / "panel-ltr.alpha158_fund.json"
    artifact_path.write_text(json.dumps(artifact))
    return panel_path, raw_path, artifact_path


def test_fit_alpha158_fund_calibrator_writes_auditable_artifact(tmp_path: Path) -> None:
    _panel_path, _raw_path, artifact_path = _write_panel_and_artifact(tmp_path)
    out = tmp_path / "panel-rank-calibration.json"

    result = fit_alpha158_fund_calibrator(
        data_dir=tmp_path,
        scorer_artifact=artifact_path,
        out_path=out,
        min_rows=100,
    )

    payload = json.loads(result.read_text())
    meta = payload["metadata"]
    assert payload["kind"] == "global_panel_calibration"
    assert meta["scorer_artifact_fingerprint"].startswith("sha256:")
    assert meta["scorer_fingerprint_schema_version"] == 1
    assert meta["expected_return_label_col"] == "fwd_60d_excess_raw"
    assert meta["expected_return_label_contract"] == "raw_return_units_required"
    assert meta["scorer_ic_scope"] == "calibrator_fit_window"
    assert meta["n_rows"] >= 100


def test_fit_alpha158_fund_calibrator_keeps_legacy_scorer_undeclared(tmp_path: Path) -> None:
    _panel_path, _raw_path, artifact_path = _write_panel_and_artifact(tmp_path)
    artifact = json.loads(artifact_path.read_text())
    artifact.pop("fingerprint_schema_version")
    artifact_path.write_text(json.dumps(artifact))

    result = fit_alpha158_fund_calibrator(
        data_dir=tmp_path,
        scorer_artifact=artifact_path,
        out_path=tmp_path / "legacy-calibrator.json",
        min_rows=100,
    )

    assert "scorer_fingerprint_schema_version" not in json.loads(result.read_text())["metadata"]


def test_fit_alpha158_fund_calibrator_requires_raw_er_label(tmp_path: Path) -> None:
    _panel_path, raw_path, artifact_path = _write_panel_and_artifact(tmp_path)
    raw_path.unlink()

    with pytest.raises(FileNotFoundError, match="raw-label panel"):
        fit_alpha158_fund_calibrator(
            data_dir=tmp_path,
            scorer_artifact=artifact_path,
            out_path=tmp_path / "bad.json",
            min_rows=100,
        )
