from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_common import ArtifactManifest, OOSEvidence
from renquant_model_alpha158_linear.calibrator import fit_alpha158_linear_calibrator
from renquant_model_alpha158_linear.scorer import PanelLinearScorer, load
from renquant_model_alpha158_linear.trainer import train_panel_linear


pytest.importorskip("pyarrow")
pytest.importorskip("sklearn")


def _write_alpha158_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    rng = np.random.default_rng(158)
    dates = pd.bdate_range("2024-01-02", periods=120)
    tickers = [f"T{i:02d}" for i in range(12)]
    rows = []
    raw_rows = []
    for date_idx, day in enumerate(dates):
        raw_by_ticker: dict[str, float] = {}
        day_rows = []
        for ticker_idx, ticker in enumerate(tickers):
            a0 = rng.normal() + ticker_idx / 20.0
            a1 = rng.normal() - date_idx / 600.0
            raw = 0.015 * a0 - 0.011 * a1 + rng.normal(0, 0.006)
            raw_by_ticker[ticker] = raw
            day_rows.append((ticker, a0, a1, raw))
        z = (pd.Series(raw_by_ticker) - np.mean(list(raw_by_ticker.values()))) / np.std(list(raw_by_ticker.values()))
        split_label = "train" if date_idx < 90 else "val" if date_idx < 105 else "test"
        for ticker, a0, a1, raw in day_rows:
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "split_label": split_label,
                    "alpha0": a0,
                    "alpha1": a1,
                    "fwd_5d_excess": float(z[ticker]),
                }
            )
            raw_rows.append({"date": day, "ticker": ticker, "fwd_5d_excess": raw})

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    panel = pd.DataFrame(rows)
    raw = pd.DataFrame(raw_rows)
    panel_path = data_dir / "alpha158_qlib_dataset.parquet"
    raw_path = data_dir / "transformer_dataset_engineered.parquet"
    panel.to_parquet(panel_path, index=False)
    raw.to_parquet(raw_path, index=False)
    stats = {
        "feature_cols": ["alpha0", "alpha1"],
        "feature_means": [0.0, 0.0],
        "feature_stds": [1.0, 1.0],
    }
    panel_path.with_suffix(".stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return data_dir, panel_path, raw_path


def test_panel_linear_scorer_round_trips_and_loads_from_manifest(tmp_path: Path) -> None:
    path = tmp_path / "panel-ltr.alpha158_linear.json"
    scorer = PanelLinearScorer(
        coef=np.array([0.4, -0.2]),
        intercept=0.0,
        feature_cols=["alpha0", "alpha1"],
        feature_means=np.array([0.0, 0.0]),
        feature_stds=np.array([1.0, 1.0]),
        metadata={"label": "fwd_5d_excess"},
    )
    scorer.save(path)

    manifest = ArtifactManifest(
        kind="panel_linear",
        family="alpha158-linear",
        artifact_uri=f"file://{path}",
        feature_fingerprint="test:alpha158",
        config_fingerprint="test:config",
        training_data_fingerprint="test:data",
        trained_at=datetime.now(timezone.utc),
        lookahead_days=5,
        oos_evidence=OOSEvidence(mean_ic=0.1, std_ic=0.0, per_fold_ic=(0.1,), cv_method="fixture", embargo_days=0),
        owner_repo="renquant-model",
    )

    loaded = load(manifest)
    assert loaded.feature_fingerprint() == "test:alpha158"
    assert loaded.predict_rows({"A": {"alpha0": 2.0, "alpha1": 1.0}})["A"] == pytest.approx(0.6)


def test_train_panel_linear_writes_auditable_artifact(tmp_path: Path) -> None:
    _data_dir, panel_path, _raw_path = _write_alpha158_fixture(tmp_path)
    out = tmp_path / "panel-ltr.alpha158_linear.json"

    result = train_panel_linear(dataset=panel_path, output=out)

    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["kind"] == "panel_linear"
    assert payload["feature_cols"] == ["alpha0", "alpha1"]
    assert payload["label"] == "fwd_5d_excess"
    assert payload["n_train_rows"] == 90 * 12
    assert payload["feature_means"] == [0.0, 0.0]
    assert payload["feature_stds"] == [1.0, 1.0]
    assert payload["test_mean_ic"] is not None


def test_fit_alpha158_linear_calibrator_uses_raw_return_labels(tmp_path: Path) -> None:
    data_dir, panel_path, _raw_path = _write_alpha158_fixture(tmp_path)
    scorer_path = tmp_path / "panel-ltr.alpha158_linear.json"
    train_panel_linear(dataset=panel_path, output=scorer_path)
    out = tmp_path / "panel-rank-calibration.alpha158_linear.json"

    result = fit_alpha158_linear_calibrator(
        data_dir=data_dir,
        scorer_artifact=scorer_path,
        out_path=out,
        min_rows=100,
    )

    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["kind"] == "global_panel_calibration"
    meta = payload["metadata"]
    assert meta["scorer_kind"] == "panel_linear"
    assert meta["expected_return_label_col"] == "fwd_5d_excess"
    assert meta["expected_return_label_contract"] == "raw_return_units_required"
    assert meta["n_rows"] >= 100


def test_fit_alpha158_linear_calibrator_requires_raw_label_panel(tmp_path: Path) -> None:
    data_dir, panel_path, raw_path = _write_alpha158_fixture(tmp_path)
    scorer_path = tmp_path / "panel-ltr.alpha158_linear.json"
    train_panel_linear(dataset=panel_path, output=scorer_path)
    raw_path.unlink()

    with pytest.raises(FileNotFoundError, match="raw-label panel"):
        fit_alpha158_linear_calibrator(
            data_dir=data_dir,
            scorer_artifact=scorer_path,
            out_path=tmp_path / "bad.json",
            min_rows=100,
        )
