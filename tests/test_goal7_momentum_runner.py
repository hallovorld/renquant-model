"""Stage-A runner tests: assembly is pure and countable; the CLI refuses correctly."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "goal7_momentum_run", REPO / "tools" / "goal7_momentum_run.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def _series(idx, vals):
    return pd.Series(vals, index=idx, dtype=float)


def test_assemble_day_counts_and_min_features(monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=300)
    rng = np.random.default_rng(7)
    spy = _series(idx, rng.normal(0, 0.01, len(idx)))
    trs = {
        "AAA": _series(idx, 0.5 * spy.to_numpy() + 0.001 + rng.normal(0, 0.002, len(idx))),
        "BBB": _series(idx, 1.5 * spy.to_numpy() + rng.normal(0, 0.002, len(idx))),
        "GLD": _series(idx, rng.normal(0, 0.005, len(idx))),   # ETF: no sector
        "THIN": _series(idx[-50:], rng.normal(0, 0.01, 50)),   # too short for min_obs
    }
    vols = {t: _series(s.index, np.abs(rng.normal(1e6, 1e5, len(s)))) for t, s in trs.items()}
    day = pd.DataFrame({"ticker": list(trs)})
    out = R.assemble_day(day, trs, spy, vols, {"AAA": "tech", "BBB": "tech"},
                         asof=idx[-1] + pd.tseries.offsets.BDay(1))
    assert out["n_names"] == 4
    assert set(out["scores"]) == set(trs), "every name stays visible, scored or not"
    assert np.isfinite(out["scores"]["AAA"]) and np.isfinite(out["scores"]["BBB"])
    assert np.isnan(out["scores"]["THIN"]), "short history must be nan, not silently scored"
    assert out["n_used"]["THIN"] <= 1
    # GLD: no sector (no F3) but F1/F2/F4/F5 available -> can clear >=3-of-5
    assert out["n_used"]["GLD"] >= 3
    assert out["n_scored"] == sum(np.isfinite(v) for v in out["scores"].values())


def test_cli_execute_gates_on_the_amendment_before_touching_anything():
    """UPDATED: stage B exists now, so --execute runs the preflight — and on this
    branch base (which predates Amendment 2's merge) it must stop at UNRESOLVED-DATA
    with the amendment named, before any data loads."""
    r = subprocess.run([sys.executable, str(REPO / "tools" / "goal7_momentum_run.py"),
                        "--execute"], capture_output=True, text=True)
    assert r.returncode == 3
    assert "amendment_2_present" in r.stdout
    assert "UNRESOLVED-DATA" in r.stdout


def test_cli_without_flags_is_usage_error():
    r = subprocess.run([sys.executable, str(REPO / "tools" / "goal7_momentum_run.py")],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_runner_declared_constant_is_documented_and_bounded():
    """MIN_SIDE_OBS is the one constant the prereg delegated to the runner. It must be
    (a) declared, (b) far below the measured minimum realized side-count (97 down-days
    in the worst 252d window since 2016), so it is a validity floor, not a filter."""
    assert R.MIN_SIDE_OBS == 30
    assert R.MIN_SIDE_OBS < 97 / 2
    assert "MIN_SIDE_OBS" in (REPO / "tools" / "goal7_momentum_run.py").read_text()
