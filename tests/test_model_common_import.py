"""Smoke-import tests for lifted cross-family model utilities."""
from __future__ import annotations

import importlib
import ast
from pathlib import Path

import pandas as pd
import pytest

LIFTED_MODULES = [
    "renquant_model_common.calibrator_quality",
    "renquant_model_common.triple_barrier",
    "renquant_model_common.acceptance_entry_ic",
    "renquant_model_common.challenger",
    "renquant_model_common.news_sentiment_finbert",
]


@pytest.mark.parametrize("module_name", LIFTED_MODULES)
def test_lifted_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_model_common_source_does_not_import_downstream_runtime() -> None:
    src_dir = Path(__file__).parent.parent / "src" / "renquant_model_common"
    forbidden = {
        "alpaca",
        "ib_insync",
        "kernel",
        "live",
        "renquant_backtesting",
        "renquant_execution",
        "renquant_pipeline",
    }
    offenders: list[tuple[str, str]] = []
    for py in src_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots = [node.module.split(".", 1)[0]]
            for root in set(roots) & forbidden:
                offenders.append((py.name, root))
    assert offenders == []


def test_challenger_maybe_load_uses_injected_loader(tmp_path: Path) -> None:
    from renquant_model_common.challenger import ChallengerEvaluator

    artifact = tmp_path / "challenger.json"
    artifact.write_text("{}")
    config = {
        "acceptance": {
            "challenger": {
                "enabled": True,
                "artifact_path": artifact.name,
                "name": "unit",
                "shadow_period_days": 3,
            }
        }
    }
    seen: list[Path] = []

    class _Scorer:
        def predict_rows(self, rows):
            return {ticker: float(row["alpha"]) for ticker, row in rows.items()}

    def loader(path: Path):
        seen.append(path)
        return _Scorer()

    evaluator = ChallengerEvaluator.maybe_load(config, tmp_path, scorer_loader=loader)

    assert evaluator is not None
    assert seen == [artifact]
    scores = evaluator.score(pd.DataFrame({"alpha": [1.0, 2.0]}, index=["AAPL", "MSFT"]))
    assert scores.to_dict() == {"AAPL": 1.0, "MSFT": 2.0}
