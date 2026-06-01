"""Runtime scorer for alpha158 linear panel artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np
import pandas as pd

from renquant_common import ArtifactManifest


@dataclass
class PanelLinearScorer:
    """Linear panel scorer compatible with ``kind=panel_linear`` artifacts."""

    coef: np.ndarray
    intercept: float
    feature_cols: list[str]
    metadata: dict[str, Any] | None = None
    feature_means: np.ndarray | None = None
    feature_stds: np.ndarray | None = None
    clip_sigma: float = 5.0
    _feature_fingerprint: str = "legacy:unknown"

    def __post_init__(self) -> None:
        self.coef = np.asarray(self.coef, dtype=float).reshape(-1)
        self.intercept = float(self.intercept)
        self.feature_cols = list(self.feature_cols)
        self.metadata = dict(self.metadata or {})
        if self.coef.shape != (len(self.feature_cols),):
            raise ValueError(f"coef shape {self.coef.shape} != ({len(self.feature_cols)},)")
        if self.feature_means is not None:
            self.feature_means = np.asarray(self.feature_means, dtype=float).reshape(-1)
            if self.feature_means.shape != (len(self.feature_cols),):
                raise ValueError(f"feature_means shape {self.feature_means.shape} != ({len(self.feature_cols)},)")
        if self.feature_stds is not None:
            self.feature_stds = np.asarray(self.feature_stds, dtype=float).reshape(-1)
            if self.feature_stds.shape != (len(self.feature_cols),):
                raise ValueError(f"feature_stds shape {self.feature_stds.shape} != ({len(self.feature_cols)},)")

    @classmethod
    def from_sklearn(
        cls,
        model: Any,
        feature_cols: list[str],
        *,
        metadata: dict[str, Any] | None = None,
        feature_means: np.ndarray | None = None,
        feature_stds: np.ndarray | None = None,
    ) -> "PanelLinearScorer":
        intercept = (
            float(model.intercept_)
            if hasattr(model, "intercept_") and not isinstance(model.intercept_, np.ndarray)
            else 0.0
        )
        return cls(
            coef=model.coef_,
            intercept=intercept,
            feature_cols=feature_cols,
            metadata=metadata,
            feature_means=feature_means,
            feature_stds=feature_stds,
        )

    @classmethod
    def load_path(cls, path: str | Path, *, feature_fingerprint: str = "legacy:unknown") -> "PanelLinearScorer":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("kind") != "panel_linear":
            raise ValueError(f"artifact kind={payload.get('kind')!r} != 'panel_linear': {path}")
        metadata = {
            key: value
            for key, value in payload.items()
            if key
            not in (
                "coef",
                "intercept",
                "feature_cols",
                "version",
                "feature_means",
                "feature_stds",
                "clip_sigma",
            )
        }
        return cls(
            coef=np.asarray(payload["coef"], dtype=float),
            intercept=float(payload.get("intercept", 0.0)),
            feature_cols=[str(col) for col in payload["feature_cols"]],
            metadata=metadata,
            feature_means=np.asarray(payload["feature_means"], dtype=float)
            if payload.get("feature_means") is not None
            else None,
            feature_stds=np.asarray(payload["feature_stds"], dtype=float)
            if payload.get("feature_stds") is not None
            else None,
            clip_sigma=float(payload.get("clip_sigma", 5.0)),
            _feature_fingerprint=feature_fingerprint,
        )

    # Backward-compatible alias for the umbrella class name.
    load = load_path

    def save(self, path: str | Path, metadata: dict[str, Any] | None = None) -> None:
        merged = {**self.metadata, **(metadata or {})}
        payload: dict[str, Any] = {
            "version": 1,
            "kind": "panel_linear",
            "feature_cols": self.feature_cols,
            "coef": self.coef.tolist(),
            "intercept": self.intercept,
            "clip_sigma": self.clip_sigma,
            **merged,
        }
        if self.feature_means is not None:
            payload["feature_means"] = self.feature_means.tolist()
        if self.feature_stds is not None:
            payload["feature_stds"] = self.feature_stds.tolist()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def feature_fingerprint(self) -> str:
        return self._feature_fingerprint

    def score(self, feature_matrix: pd.DataFrame) -> pd.Series:
        missing = [col for col in self.feature_cols if col not in feature_matrix.columns]
        if missing:
            raise KeyError(f"PanelLinearScorer.score missing columns: {missing[:5]}")
        matrix = feature_matrix[self.feature_cols].values.astype(float)
        matrix = np.where(np.isfinite(matrix), matrix, 0.0)
        preds = np.sum(matrix * self.coef, axis=1) + self.intercept
        return pd.Series(preds, index=feature_matrix.index, name="panel_score")

    def score_raw(self, raw_features: pd.DataFrame) -> pd.Series:
        if self.feature_means is None or self.feature_stds is None:
            raise ValueError("feature_means/feature_stds are required for score_raw")
        missing = [col for col in self.feature_cols if col not in raw_features.columns]
        if missing:
            raise KeyError(f"PanelLinearScorer.score_raw missing columns: {missing[:5]}")
        matrix = raw_features[self.feature_cols].values.astype(float)
        matrix = np.where(np.isfinite(matrix), matrix, np.nan)
        std_safe = np.where(self.feature_stds > 1e-9, self.feature_stds, 1.0)
        matrix = (matrix - self.feature_means) / std_safe
        matrix = np.where(np.isfinite(matrix), matrix, 0.0)
        if self.clip_sigma > 0:
            matrix = np.clip(matrix, -self.clip_sigma, self.clip_sigma)
        preds = np.sum(matrix * self.coef, axis=1) + self.intercept
        return pd.Series(preds, index=raw_features.index, name="panel_score")

    def predict_rows(self, rows: dict[str, dict[str, float]]) -> dict[str, float]:
        if not rows:
            return {}
        frame = pd.DataFrame.from_dict(rows, orient="index")
        scores = self.score_raw(frame) if self.feature_means is not None and self.feature_stds is not None else self.score(frame)
        return {str(ticker): float(score) for ticker, score in scores.items()}

    def predict_variance(self, rows: dict[str, dict[str, float]]) -> dict[str, float] | None:
        return None


def load(manifest: ArtifactManifest) -> PanelLinearScorer:
    """Load a local alpha158 linear scorer from an ArtifactManifest."""
    return PanelLinearScorer.load_path(
        _local_path(manifest.artifact_uri),
        feature_fingerprint=manifest.feature_fingerprint,
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
