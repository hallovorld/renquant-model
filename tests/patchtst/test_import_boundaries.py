from __future__ import annotations

import importlib
import sys


def test_patchtst_root_import_does_not_pull_execution_or_gbdt_runtime() -> None:
    importlib.import_module("renquant_model_patchtst")

    forbidden_prefixes = (
        "alpaca",
        "ib_insync",
        "live",
        "renquant_execution",
        "renquant_model_gbdt",
    )
    offenders = sorted(
        name for name in sys.modules
        if name in forbidden_prefixes or name.startswith(forbidden_prefixes)
    )
    assert offenders == []
