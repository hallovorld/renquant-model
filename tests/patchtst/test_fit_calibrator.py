from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from renquant_model_patchtst import fit_calibrator as fc


class _MeanModel(torch.nn.Module):
    def forward(self, past_values: torch.Tensor, **_: object) -> dict[str, torch.Tensor]:
        score = past_values.mean(dim=(1, 2))
        return {
            "score": score,
            "loc": score + 0.01,
            "scale": torch.ones_like(score) * 0.2,
        }


class _FakeCalibration:
    def __init__(self) -> None:
        self.metadata = {"n_rows": 4, "pool_ic": 0.25}
        self.prob_x = np.asarray([-1.0, 1.0])
        self.prob_y = np.asarray([0.25, 0.75])
        self.er_x = np.asarray([-1.0, 1.0])
        self.er_y = np.asarray([-0.02, 0.02])

    def save(self, path: str | Path, metadata: dict | None = None) -> None:
        payload = {
            "kind": "global_panel_calibration",
            "metadata": metadata or {},
            "probability": {"x": self.prob_x.tolist(), "y": self.prob_y.tolist()},
            "expected_return": {"x": self.er_x.tolist(), "y": self.er_y.tolist()},
        }
        Path(path).write_text(json.dumps(payload, default=str))


def _panel() -> pd.DataFrame:
    rows = []
    for ticker, base in (("A", 1.0), ("B", 10.0), ("C", 20.0), ("D", 30.0), ("E", 40.0)):
        for i, date in enumerate(pd.bdate_range("2024-01-02", periods=4)):
            rows.append({
                "ticker": ticker,
                "date": date,
                "f1": base + i,
                "fwd_60d_excess": 0.1 * base + i,
            })
    return pd.DataFrame(rows)


def test_source_has_no_umbrella_kernel_imports() -> None:
    src = Path(fc.__file__).read_text()
    assert "kernel." not in src
    assert "training_panel.global_calibrator" not in src
    assert "scripts/fit_hf_patchtst_calibrator.py" not in src


def test_infer_raw_er_label_preserves_raw_and_common_fwd_pattern() -> None:
    assert fc._infer_raw_er_label("fwd_60d_excess") == "fwd_60d_excess_raw"
    assert fc._infer_raw_er_label("fwd_60d_excess_raw") == "fwd_60d_excess_raw"
    assert fc._infer_raw_er_label("custom_label") == "custom_label_raw"


def test_score_sequences_replays_only_requested_window() -> None:
    scorer = SimpleNamespace(
        feature_cols=["f1"],
        seq_len=2,
        model=_MeanModel(),
        device="cpu",
    )
    panel = pd.DataFrame({
        "ticker": ["A", "A", "A", "B", "B", "B"],
        "date": pd.to_datetime([
            "2024-01-02", "2024-01-03", "2024-01-04",
            "2024-01-02", "2024-01-03", "2024-01-04",
        ]),
        "f1": [1.0, 2.0, 3.0, 10.0, 20.0, 30.0],
    })

    scored = fc._score_sequences(
        scorer,
        panel,
        data_start="2024-01-03",
        data_end="2024-01-05",
        batch_size=2,
        use_csranknorm_preprocessing=False,
    )

    got = {
        (row.ticker, row.date.date().isoformat()): row.panel_score
        for row in scored.itertuples(index=False)
    }
    assert got == {
        ("A", "2024-01-03"): pytest.approx(1.5),
        ("A", "2024-01-04"): pytest.approx(2.5),
        ("B", "2024-01-03"): pytest.approx(15.0),
        ("B", "2024-01-04"): pytest.approx(25.0),
    }
    assert {"mu", "sigma"}.issubset(scored.columns)


def test_fit_patchtst_calibrator_stamps_fingerprint_and_raw_label_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "hf_patchtst_all_seed44_model.pt"
    torch.save({
        "kind": "hf_patchtst",
        "feature_cols": ["f1"],
        "seq_len": 2,
        "label_col": "fwd_60d_excess",
        "lookahead_days": 60,
        "best_val_ic": 0.03,
        "uses_csranknorm_preprocessing": False,
    }, model_path)
    model_path.with_name(model_path.name + ".metadata.json").write_text(json.dumps({
        "artifact_fingerprint": "sha256:artifact",
        "val_ic": 0.031,
    }))

    panel_path = tmp_path / "panel.parquet"
    raw_path = tmp_path / "raw.parquet"
    panel = _panel()
    panel.to_parquet(panel_path)
    panel[["ticker", "date"]].assign(
        fwd_60d_excess_raw=panel["fwd_60d_excess"] * 0.01,
    ).to_parquet(raw_path)

    fake_scorer = SimpleNamespace(
        feature_cols=["f1"],
        seq_len=2,
        model=_MeanModel(),
        device="cpu",
    )
    monkeypatch.setattr(fc, "_load_patchtst_scorer", lambda _: fake_scorer)
    monkeypatch.setattr(fc, "fit_global_calibrator", lambda *_, **__: _FakeCalibration())

    out = tmp_path / "calibration.json"
    fc.fit_patchtst_calibrator(
        scorer_artifact=model_path,
        out_path=out,
        panel_path=panel_path,
        raw_label_panel_path=raw_path,
        data_start="2024-01-03",
        data_end="2024-01-06",
        batch_size=3,
        min_rows=1,
    )

    meta = json.loads(out.read_text())["metadata"]
    assert meta["scorer_artifact_fingerprint"] == "sha256:artifact"
    assert meta["scorer_model_content_fingerprint"] == "sha256:artifact"
    assert meta["scorer_val_ic"] == pytest.approx(0.03)
    assert meta["model_label_col"] == "fwd_60d_excess"
    assert meta["expected_return_label_col"] == "fwd_60d_excess_raw"
    assert meta["expected_return_label_contract"] == "raw_return_units_required"
    assert meta["expected_return_label_source"] == str(raw_path.resolve())
    assert meta["scorer_ic_scope"] == "calibrator_fit_window"
    assert meta["scorer_oos_mean_ic"] is None
    assert meta["lookahead_days_used"] == 60
