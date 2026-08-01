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


def test_execute_gates_on_the_amendment_before_touching_anything(monkeypatch, tmp_path, capsys):
    """UPDATED again: with Amendment 2 merged the real tree is fully provisioned, so a
    subprocess --execute would RUN THE STUDY — which no test may do (§7: single
    post-merge invocation). The gate is exercised in-process instead, with the
    amendment path pointed at nothing: execute() must stop at UNRESOLVED-DATA naming
    it, before loading any data."""
    monkeypatch.setattr(R, "AMENDMENT_2", tmp_path / "absent.md")
    rc = R.execute(None)
    out = capsys.readouterr().out
    assert rc == 3
    assert "amendment_2_present" in out
    assert "UNRESOLVED-DATA" in out


def test_preflight_refuses_when_the_snapshot_manifest_is_absent(monkeypatch):
    """Amendment 3: §2 resolves THROUGH the base-data manifest; a missing manifest is
    UNRESOLVED-DATA, and there is deliberately NO fallback to the live data/ paths."""
    monkeypatch.setattr(R, "MANIFEST", Path("/nonexistent/manifest.json"))
    pre = R.verify_preconditions()
    assert not pre["ok"]
    assert "snapshot_manifest_present" in pre["unresolved_data"]
    # the resolution-dependent checks never ran — nothing read a live path instead
    for dependent in ("panel_digest", "sector_digest", "ohlcv_combined_digest"):
        assert dependent not in pre["checks"]


def test_manifest_loader_rejects_a_wrong_dataset_id(monkeypatch, tmp_path):
    import json as _json
    bogus = tmp_path / "m.json"
    bogus.write_text(_json.dumps({"dataset_id": "something-else", "files": {}}))
    monkeypatch.setattr(R, "MANIFEST", bogus)
    assert R.load_snapshot_manifest() is None


def test_manifest_identity_check_fails_on_a_drifted_headline_digest(monkeypatch, tmp_path):
    """A manifest whose headline digests differ from the frozen §2 pins must fail
    manifest_identity — the manifest never overrides the prereg, it only locates it."""
    import json as _json
    drifted = tmp_path / "m.json"
    drifted.write_text(_json.dumps({
        "dataset_id": "momentum-prereg-inputs-20260801",
        "location": {"path": str(tmp_path)},
        "combined_ohlcv_digest": {"value": "00" * 32},
        "files": {"panel.parquet": {"sha256": "00" * 32},
                  "ticker_sectors.json": {"sha256": "00" * 32}}}))
    monkeypatch.setattr(R, "MANIFEST", drifted)
    pre = R.verify_preconditions()
    assert not pre["ok"]
    assert any(c == "manifest_identity" for c in pre["unresolved_data"])


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
