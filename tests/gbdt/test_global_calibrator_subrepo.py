from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_common.global_calibrator import GlobalPanelCalibration, fit_global_calibrator


pytest.importorskip("sklearn")


def _synthetic_panel(n_tickers: int = 10, n_bars: int = 160, seed: int = 7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=n_bars)
    panel_scores: dict[str, pd.Series] = {}
    future_returns: dict[str, pd.Series] = {}
    for n in range(n_tickers):
        raw = rng.normal(0, 0.5, n_bars)
        fwd = 0.04 * raw + rng.normal(0, 0.015, n_bars)
        panel_scores[f"T{n}"] = pd.Series(raw, index=idx)
        future_returns[f"T{n}"] = pd.Series(fwd, index=idx)
    return panel_scores, future_returns


def test_fit_save_load_round_trip(tmp_path: Path) -> None:
    panel_scores, future_returns = _synthetic_panel()

    calibration = fit_global_calibrator(
        panel_scores,
        future_returns,
        method="platt",
        threshold_mode="crosssectional",
        min_rows=100,
    )
    out = tmp_path / "panel-rank-calibration.json"
    calibration.save(out, metadata={"training_notes": "subrepo-unit"})

    loaded = GlobalPanelCalibration.load(out)

    assert loaded.metadata["training_notes"] == "subrepo-unit"
    assert loaded.metadata["n_rows"] >= 100
    assert loaded.calibrate_probability(1.0) > loaded.calibrate_probability(-1.0)
    assert loaded.expected_return(1.0) > loaded.expected_return(-1.0)
    assert loaded.expected_return(1.0, horizon_days=120) == pytest.approx(
        loaded.expected_return(1.0) * 12.0,
    )


def test_fit_rejects_too_few_rows() -> None:
    idx = pd.bdate_range("2024-01-02", periods=20)
    with pytest.raises(ValueError, match="min_rows"):
        fit_global_calibrator(
            {"A": pd.Series(np.linspace(-1, 1, len(idx)), index=idx)},
            {"A": pd.Series(np.linspace(-0.01, 0.01, len(idx)), index=idx)},
            min_rows=100,
        )
