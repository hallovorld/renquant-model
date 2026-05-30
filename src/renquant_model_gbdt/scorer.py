"""Runtime scorer for GBDT panel-LTR artifacts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pandas as pd

from renquant_common import ArtifactManifest


@dataclass
class PanelLtrXgboostScorer:
    """Scorer Protocol implementation for ``kind=panel_ltr_xgboost``."""

    artifact: dict[str, Any]
    booster: Any
    feature_cols: list[str]
    _feature_fingerprint: str

    def feature_fingerprint(self) -> str:
        return self._feature_fingerprint

    def predict_rows(self, rows: dict[str, dict[str, float]]) -> dict[str, float]:
        if not rows:
            return {}
        frame = pd.DataFrame.from_dict(rows, orient="index")
        missing = [col for col in self.feature_cols if col not in frame.columns]
        if missing:
            raise KeyError(f"PanelLtrXgboostScorer.predict_rows missing columns: {missing}")
        matrix = frame[self.feature_cols]
        import xgboost as xgb  # noqa: PLC0415

        preds = self.booster.predict(xgb.DMatrix(matrix.values.astype(float)))
        return {
            ticker: float(score)
            for ticker, score in zip(matrix.index.astype(str), preds)
        }

    def predict_variance(self, rows: dict[str, dict[str, float]]) -> dict[str, float] | None:
        return None


def load(manifest: ArtifactManifest) -> PanelLtrXgboostScorer:
    """Load a local XGBoost panel scorer from an ArtifactManifest."""
    path = _local_path(manifest.artifact_uri)
    artifact = json.loads(path.read_text(encoding="utf-8"))
    feature_cols = [str(c) for c in artifact.get("feature_cols") or []]
    if not feature_cols:
        raise ValueError(f"artifact missing feature_cols: {path}")
    raw_json = artifact.get("booster_raw_json")
    if not isinstance(raw_json, str) or not raw_json:
        raise ValueError(f"artifact missing booster_raw_json: {path}")

    import xgboost as xgb  # noqa: PLC0415

    booster = xgb.Booster()
    booster.load_model(bytearray(raw_json.encode("utf-8")))
    return PanelLtrXgboostScorer(
        artifact=artifact,
        booster=booster,
        feature_cols=feature_cols,
        _feature_fingerprint=manifest.feature_fingerprint,
    )


def _local_path(uri: str) -> Path:
    parsed = urlparse(str(uri))
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    elif parsed.scheme == "":
        path = Path(str(uri))
    else:
        raise ValueError(f"unsupported local scorer artifact URI: {uri!r}")
    if not path.exists():
        raise FileNotFoundError(path)
    return path


__all__ = ["PanelLtrXgboostScorer", "load"]
