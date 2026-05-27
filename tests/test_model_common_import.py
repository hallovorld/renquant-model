"""Smoke-import tests for lifted cross-family model utilities."""
from __future__ import annotations

import importlib

import pytest

LIFTED_MODULES = [
    "renquant_model_common.calibrator_quality",
    "renquant_model_common.triple_barrier",
    "renquant_model_common.acceptance_entry_ic",
    "renquant_model_common.challenger",
]


@pytest.mark.parametrize("module_name", LIFTED_MODULES)
def test_lifted_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None
