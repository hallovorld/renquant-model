from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from renquant_common import ArtifactManifest, OOSEvidence
from renquant_model_gbdt.scorer import load


pytest.importorskip("xgboost")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GITHUB_ROOT = _REPO_ROOT.parent
_UMBRELLA_STRATEGY = _GITHUB_ROOT / "RenQuant" / "backtesting" / "renquant_104"
_PROD_ARTIFACT = _UMBRELLA_STRATEGY / "artifacts" / "prod" / "panel-ltr.alpha158_fund.json"


def test_scorer_predictions_match_umbrella_panel_scorer() -> None:
    if not _PROD_ARTIFACT.exists():
        pytest.skip(f"production artifact absent: {_PROD_ARTIFACT}")
    sys.path.insert(0, str(_UMBRELLA_STRATEGY))
    from renquant_pipeline.kernel.panel_pipeline.feature_transform import transform_feature_frame  # noqa: PLC0415
    from renquant_pipeline.kernel.panel_pipeline.panel_scorer import PanelScorer  # noqa: PLC0415

    artifact = json.loads(_PROD_ARTIFACT.read_text(encoding="utf-8"))
    raw_frame = _raw_sample_frame(artifact)
    transformed = transform_feature_frame(
        raw_frame,
        list(artifact["feature_cols"]),
        artifact,
        source_space="raw",
        clip=5.0,
    )

    pr_scorer = load(_manifest_for(_PROD_ARTIFACT, artifact))
    pr_scores = pr_scorer.predict_rows(transformed.to_dict(orient="index"))

    umbrella_scorer = PanelScorer.load(_PROD_ARTIFACT)
    umbrella_scores = umbrella_scorer.score(transformed).to_dict()

    assert set(pr_scores) == set(umbrella_scores)
    for ticker, score in pr_scores.items():
        assert score == pytest.approx(umbrella_scores[ticker], abs=1e-9)


def test_scorer_requires_aligned_feature_rows() -> None:
    if not _PROD_ARTIFACT.exists():
        pytest.skip(f"production artifact absent: {_PROD_ARTIFACT}")
    artifact = json.loads(_PROD_ARTIFACT.read_text(encoding="utf-8"))
    scorer = load(_manifest_for(_PROD_ARTIFACT, artifact))

    with pytest.raises(KeyError, match="missing columns"):
        scorer.predict_rows({"AAPL": {artifact["feature_cols"][0]: 1.0}})


def _manifest_for(path: Path, artifact: dict) -> ArtifactManifest:
    return ArtifactManifest(
        kind="panel_ltr_xgboost",
        family="gbdt-panel-ltr",
        artifact_uri=f"file://{path}",
        feature_fingerprint=str(artifact.get("feature_fingerprint") or "legacy:unknown"),
        config_fingerprint=str(artifact.get("config_fingerprint") or "legacy:unknown"),
        training_data_fingerprint=str(
            artifact.get("training_data_fingerprint") or "legacy:unknown"
        ),
        trained_at=datetime.now(timezone.utc),
        lookahead_days=int(artifact.get("lookahead_days") or 1),
        oos_evidence=OOSEvidence(
            mean_ic=float(artifact.get("oos_mean_ic") or 0.0),
            std_ic=float(artifact.get("oos_std_ic") or 0.0),
            per_fold_ic=tuple(float(v) for v in artifact.get("oos_per_fold_ic") or ()),
            cv_method=str(artifact.get("cv_method") or "unknown"),
            embargo_days=int(artifact.get("cv_embargo_days") or 0),
        ),
        owner_repo="renquant-model",
    )


def _raw_sample_frame(artifact: dict) -> pd.DataFrame:
    feature_cols = list(artifact["feature_cols"])
    means = artifact.get("feature_means") or []
    stds = artifact.get("feature_stds") or []
    rows = {}
    for ticker, offset in (("AAPL", -0.4), ("MSFT", 0.1), ("NVDA", 0.6)):
        row = {}
        for idx, col in enumerate(feature_cols):
            mean = _finite_at(means, idx, 0.0)
            std = abs(_finite_at(stds, idx, 1.0)) or 1.0
            row[col] = mean + std * (offset + ((idx % 7) - 3) * 0.03)
        rows[ticker] = row
    return pd.DataFrame.from_dict(rows, orient="index")


def _finite_at(values: list, idx: int, default: float) -> float:
    try:
        value = float(values[idx])
    except (IndexError, TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default
