"""AC-1 executable consumer evidence: calibrator loaders vs the 176-col sidecar.

Companion to renquant-base-data
``doc/design/2026-07-18-rawlabel-sidecar-sentiment-reconciliation.md`` (AC-1).
Both calibrator fits read the served
``alpha158_291_fundamental_dataset_rawlabel.parquet`` with an explicit
column-pruned read — ``columns=["ticker", "date", <er_label_col>]`` —
so the sentiment-column removal (179 -> 176) cannot affect them. These tests
prove that executably against a fixture carrying the builder's EXACT
176-column contract:

- ``renquant_model_patchtst.fit_calibrator._load_panel_with_raw_label``
- ``renquant_model_gbdt.fit_calibrator_alpha158_fund._load_expected_return_labels``

Fixture provenance: ``tests/data/rawlabel_sidecar_columns_176.json`` is an
export of renquant-base-data ``rawlabel_sidecar.RAWLABEL_SIDECAR_COLUMNS`` at
main ``b72dd92``; base-data ``tests/test_rawlabel_sidecar_schema_export.py``
is the drift guard for every embedded copy (this file is named there).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_gbdt.fit_calibrator_alpha158_fund import (
    _load_expected_return_labels,
)
from renquant_model_patchtst.fit_calibrator import _load_panel_with_raw_label

pytest.importorskip("pyarrow")

SIDECAR_COLUMNS = json.loads(
    (Path(__file__).parent / "data" / "rawlabel_sidecar_columns_176.json").read_text()
)
SENTIMENT_COLS = {"sentiment_pos_share", "mean_sentiment", "n_articles_log"}


def _write_sidecar_fixture(path: Path) -> pd.DataFrame:
    """A tiny sidecar parquet with the EXACT 176-column contract.

    ``fwd_60d_excess_raw`` uses raw return-scale values (std ~1%) so the
    calibrators' EXPECTED-RETURN-LABEL scale contract accepts it.
    """
    assert len(SIDECAR_COLUMNS) == 176
    assert not SENTIMENT_COLS & set(SIDECAR_COLUMNS)
    dates = pd.bdate_range("2024-01-02", periods=8)
    rows = [(t, d) for t in ("AAA", "BBB", "CCC") for d in dates]
    rng = np.random.default_rng(104)
    frame = pd.DataFrame({
        "ticker": pd.array([t for t, _ in rows], dtype="string"),
        "date": [d for _, d in rows],
    })
    for col in SIDECAR_COLUMNS:
        if col in ("ticker", "date"):
            continue
        if col == "split_label":
            frame[col] = pd.array(["train"] * len(rows), dtype="string")
        elif col == "fwd_60d_excess_raw":
            frame[col] = rng.normal(0.0, 0.01, size=len(rows))
        else:
            frame[col] = rng.normal(size=len(rows))
    frame = frame.loc[:, SIDECAR_COLUMNS]
    frame.to_parquet(path, index=False)
    return frame


def _write_scoring_panel(path: Path, sidecar: pd.DataFrame) -> pd.DataFrame:
    """A minimal training-panel-shaped frame WITHOUT the raw label column."""
    panel = sidecar[["ticker", "date"]].copy()
    rng = np.random.default_rng(11)
    panel["a0"] = rng.normal(size=len(panel))
    panel["a1"] = rng.normal(size=len(panel))
    panel["fwd_60d_excess"] = rng.normal(size=len(panel))
    panel.to_parquet(path, index=False)
    return panel


def test_patchtst_loader_merges_er_label_from_176_col_sidecar(tmp_path):
    sidecar_path = tmp_path / "alpha158_291_fundamental_dataset_rawlabel.parquet"
    sidecar = _write_sidecar_fixture(sidecar_path)
    panel_path = tmp_path / "panel.parquet"
    _write_scoring_panel(panel_path, sidecar)

    panel, diagnostics, er_source = _load_panel_with_raw_label(
        panel_path=panel_path,
        raw_label_panel_path=sidecar_path,
        feature_cols=["a0", "a1"],
        label_col="fwd_60d_excess",
        er_label_col="fwd_60d_excess_raw",
        allow_normalized_er_label=False,
    )

    assert er_source == str(sidecar_path)
    assert panel["fwd_60d_excess_raw"].notna().all()
    assert diagnostics["looks_cross_sectional_standardized"] is False
    # The loader consumed ONLY keys + the er label from the sidecar: none of
    # the removed sentiment columns (nor any other sidecar feature) leaked in.
    assert not SENTIMENT_COLS & set(panel.columns)


def test_gbdt_loader_merges_er_label_from_176_col_sidecar(tmp_path):
    sidecar_path = tmp_path / "alpha158_291_fundamental_dataset_rawlabel.parquet"
    sidecar = _write_sidecar_fixture(sidecar_path)
    panel_path = tmp_path / "panel.parquet"
    scoring_panel = _write_scoring_panel(panel_path, sidecar)

    merged, chosen, diagnostics, source = _load_expected_return_labels(
        scoring_panel=scoring_panel,
        panel_path=panel_path,
        raw_label_panel_path=sidecar_path,
        model_label_col="fwd_60d_excess",
        er_label_col=None,
        allow_normalized_er_label=False,
    )

    assert chosen == "fwd_60d_excess_raw"
    assert source == str(sidecar_path)
    assert merged["fwd_60d_excess_raw"].notna().all()
    assert not SENTIMENT_COLS & set(merged.columns)
