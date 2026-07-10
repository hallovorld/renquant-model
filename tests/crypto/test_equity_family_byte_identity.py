"""Equity families untouched: byte-identity + import-boundary pins.

The crypto family is additive — it IMPORTS the shared GBDT engine and never
modifies it. These tests pin that promise behaviorally: the equity training
path produces a bit-identical artifact fingerprint whether or not the crypto
package has been imported, and the equity engine's frozen constants are
unchanged.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")
xgb = pytest.importorskip("xgboost")

from renquant_common.model_fingerprint import model_content_sha256  # noqa: E402
from renquant_model_gbdt import GbdtTrainingContext, build_training_pipeline  # noqa: E402
from renquant_model_gbdt.panel_data import (  # noqa: E402
    ALPHA_STATS_FILE, FUND_COLS, FUND_FILE, PANEL_FILE,
)
from renquant_model_gbdt.panel_trainer import (  # noqa: E402
    DEFAULT_LABEL,
    DEFAULT_N_ROUNDS,
    PANEL_LTR_PARAMS,
)


def _make_equity_data_dir(tmp: Path, n_dates: int = 40, n_tickers: int = 10,
                          seed: int = 9) -> Path:
    """Tiny synthetic equity panel (mirrors tests/gbdt conventions)."""
    tmp.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    rows = []
    for d in dates:
        for t in range(n_tickers):
            x = rng.normal(size=3)
            rows.append({"date": d, "ticker": f"T{t}", "a0": x[0], "a1": x[1], "a2": x[2],
                         "fwd_60d_excess": 0.6 * x[0] - 0.3 * x[1] + rng.normal(scale=0.5)})
    pd.DataFrame(rows).to_parquet(tmp / PANEL_FILE)
    (tmp / ALPHA_STATS_FILE).write_text(json.dumps({
        "feature_cols": ["a0", "a1", "a2"],
        "feature_means": [0.0, 0.0, 0.0],
        "feature_stds": [1.0, 1.0, 1.0],
    }))
    fund_rows = [{"date": d, "ticker": f"T{t}", **{c: float(rng.normal()) for c in FUND_COLS}}
                 for d in dates for t in range(n_tickers)]
    pd.DataFrame(fund_rows).to_parquet(tmp / FUND_FILE)
    return tmp


def _train_equity_fingerprint(tmp: Path) -> str:
    data_dir = _make_equity_data_dir(tmp)
    ctx = GbdtTrainingContext(
        params=dict(PANEL_LTR_PARAMS), num_boost_round=12, skip_cv=True,
        data_dir=str(data_dir), train_run_id="byte-identity-pin",
    )
    result = build_training_pipeline().run(ctx)
    assert result.ok and ctx.artifact is not None
    return model_content_sha256(ctx.artifact)


def test_equity_artifact_fingerprint_identical_after_crypto_import(tmp_path: Path) -> None:
    """Train equity, import the crypto family, train equity again: the
    model-content fingerprint (params, features, normalization, booster
    bytes) must be bit-identical — the crypto package may not perturb the
    equity engine in any observable way."""
    before = _train_equity_fingerprint(tmp_path / "before")

    import renquant_model_crypto  # noqa: F401  (the byte-identity subject)
    importlib.reload(importlib.import_module("renquant_model_crypto"))

    after = _train_equity_fingerprint(tmp_path / "after")
    assert before == after


def test_equity_engine_frozen_constants_unchanged() -> None:
    import renquant_model_crypto  # noqa: F401

    assert DEFAULT_LABEL == "fwd_60d_excess"
    assert DEFAULT_N_ROUNDS == 100
    assert PANEL_LTR_PARAMS == {
        "objective": "rank:pairwise", "eta": 0.05, "max_depth": 5,
        "min_child_weight": 50, "subsample": 0.7, "colsample_bytree": 0.7,
        "verbosity": 0, "seed": 42,
    }


def test_crypto_package_import_boundaries() -> None:
    """Mirrors tests/gbdt/test_import_boundaries.py for the crypto family:
    importing the model-side crypto package must not pull execution/broker
    runtime or pipeline kernel code. Runs hermetically in a subprocess so
    other tests' imports (e.g. renquant_pipeline in the calibrator subrepo
    test) cannot pollute the check."""
    import os
    import subprocess

    code = (
        "import sys\n"
        "import renquant_model_crypto\n"
        "forbidden = ('alpaca', 'backtesting', 'ib_insync', 'kernel', 'live',\n"
        "             'renquant_execution', 'renquant_pipeline')\n"
        "offenders = sorted(n for n in sys.modules\n"
        "                   if n in forbidden or n.startswith(forbidden))\n"
        "assert offenders == [], offenders\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, f"import boundary violated:\n{result.stderr}"


def test_crypto_context_defaults_do_not_leak_into_equity_context() -> None:
    import renquant_model_crypto  # noqa: F401

    equity_ctx = GbdtTrainingContext()
    assert equity_ctx.label == "fwd_60d_excess"
    assert equity_ctx.cv_embargo_days == 60
    assert equity_ctx.lookahead_days == 60
