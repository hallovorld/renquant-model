from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_common.meta_label_exit import (
    FEATURE_COLUMNS,
    generate_meta_labels,
    label_snapshots,
    select_path_rule_training_events,
    train_meta_label_xgb,
)


pytest.importorskip("pyarrow")
pytest.importorskip("xgboost")


def _snapshot_row(date: pd.Timestamp, ticker: str = "AAA", label: float | None = None) -> dict:
    row = {col: 0.0 for col in FEATURE_COLUMNS}
    row.update(
        {
            "date": date,
            "ticker": ticker,
            "realized_vol_20d": 0.1587,
            "trigger_stop_loss": 1,
            "any_trigger": 1,
            "meta_label": label,
        }
    )
    return row


def test_label_snapshots_labels_only_path_rule_triggers() -> None:
    dates = pd.bdate_range("2026-01-01", periods=30)
    close = pd.Series(np.linspace(100, 80, len(dates)), index=dates)
    frame = pd.DataFrame(
        [
            _snapshot_row(dates[5]),
            {**_snapshot_row(dates[6]), "trigger_stop_loss": 0, "any_trigger": 1},
        ]
    )

    labeled = label_snapshots(frame, {"AAA": close}, pt_mult=1.0, sl_mult=1.0, fwd_window=5)

    assert labeled.loc[0, "meta_label"] == 1
    assert pd.isna(labeled.loc[1, "meta_label"])
    assert pd.notna(labeled.loc[0, "fwd_5d_ret"])


def test_generate_meta_labels_reads_ohlcv_cache(tmp_path: Path) -> None:
    dates = pd.bdate_range("2026-01-01", periods=30)
    ohlcv_dir = tmp_path / "ohlcv" / "AAA"
    ohlcv_dir.mkdir(parents=True)
    pd.DataFrame({"close": np.linspace(100, 80, len(dates))}, index=dates).to_parquet(ohlcv_dir / "1d.parquet")
    snapshots = tmp_path / "snapshots.parquet"
    pd.DataFrame([_snapshot_row(dates[5])]).to_parquet(snapshots, index=False)

    summary = generate_meta_labels(
        snapshots=snapshots,
        out=tmp_path / "labels.parquet",
        data_dir=tmp_path,
        pt_mult=1.0,
        sl_mult=1.0,
        fwd_window=5,
    )

    assert summary["ok"] is True
    labels = pd.read_parquet(tmp_path / "labels.parquet")
    assert labels.loc[0, "meta_label"] == 1


def test_select_path_rule_training_events_filters_model_only_triggers() -> None:
    frame = pd.DataFrame(
        [
            _snapshot_row(pd.Timestamp("2026-01-01"), label=1),
            {**_snapshot_row(pd.Timestamp("2026-01-02"), label=0), "trigger_stop_loss": 0, "any_trigger": 1},
        ]
    )

    selected = select_path_rule_training_events(frame)

    assert len(selected) == 1
    assert selected.loc[0, "meta_label"] == 1


def test_train_meta_label_xgb_writes_artifact(tmp_path: Path) -> None:
    dates = pd.bdate_range("2026-01-01", periods=80)
    rows = []
    for i, event_date in enumerate(dates):
        row = _snapshot_row(event_date, label=float(i % 2))
        row["cum_pnl_pct"] = float(i % 7) / 10.0
        row["panel_score_current"] = float(i % 5)
        rows.append(row)
    labels = tmp_path / "labels.parquet"
    pd.DataFrame(rows).to_parquet(labels, index=False)
    out = tmp_path / "meta-label-exit.json"

    summary = train_meta_label_xgb(
        labels=labels,
        out=out,
        n_splits=3,
        label_horizon_days=1,
        pct_embargo=0.0,
        n_estimators=5,
        min_events=20,
    )

    assert summary["ok"] is True
    payload = json.loads(out.read_text())
    assert payload["kind"] == "meta_label_exit_xgb"
    assert payload["training_data_summary"]["n_events"] == 80
