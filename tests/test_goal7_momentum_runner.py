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
    _ledger(monkeypatch, tmp_path)   # isolate the claim/ledger from the real store
    rc = R.execute()
    out = capsys.readouterr().out
    assert rc == 3
    assert "amendment_2_present" in out
    assert "UNRESOLVED-DATA" in out


def test_preflight_refuses_when_the_snapshot_manifest_is_absent(monkeypatch):
    """Amendment 3: §2 resolves THROUGH the base-data manifest; a missing manifest is
    UNRESOLVED-DATA, and there is deliberately NO fallback to the live data/ paths."""
    monkeypatch.setattr(R, "MANIFEST_CANDIDATES", (Path("/nonexistent/manifest.json"),))
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
    monkeypatch.setattr(R, "MANIFEST_CANDIDATES", (bogus,))
    assert R.load_snapshot_manifest() is None


def test_manifest_identity_check_fails_on_a_drifted_headline_digest(monkeypatch, tmp_path):
    """A manifest whose headline digests differ from the frozen §2 pins must fail
    manifest_identity — the manifest never overrides the prereg, it only locates it."""
    import json as _json
    drifted = tmp_path / "m.json"
    drifted.write_text(_json.dumps({
        "dataset_id": "momentum-prereg-inputs-20260801",
        "resolver": {"scheme": "content-addressed-v1",
                     "candidate_roots": [{"path": str(tmp_path)}]},
        "combined_ohlcv_digest": {"value": "00" * 32},
        "files": {"panel.parquet": {"sha256": "00" * 32},
                  "ticker_sectors.json": {"sha256": "00" * 32}}}))
    monkeypatch.setattr(R, "MANIFEST_CANDIDATES", (drifted,))
    pre = R.verify_preconditions()
    assert not pre["ok"]
    assert any(c == "manifest_identity" for c in pre["unresolved_data"])


def test_resolution_refuses_when_no_candidate_root_exists(monkeypatch, tmp_path):
    """content-addressed-v1: identity digests can be perfect, but if no candidate
    root carries the bytes the runner refuses (snapshot_root_resolves) rather than
    falling back to any live path."""
    import json as _json
    man = tmp_path / "m.json"
    man.write_text(_json.dumps({
        "dataset_id": "momentum-prereg-inputs-20260801",
        "resolver": {"scheme": "content-addressed-v1",
                     "candidate_roots": [{"path": str(tmp_path / "nowhere")}]},
        "combined_ohlcv_digest": {"value": R.FROZEN["ohlcv_combined_sha256"]},
        "files": {"panel.parquet": {"sha256": R.FROZEN["panel_sha256"]},
                  "ticker_sectors.json": {"sha256": R.FROZEN["sector_sha256"]}}}))
    monkeypatch.setattr(R, "MANIFEST_CANDIDATES", (man,))
    pre = R.verify_preconditions()
    assert not pre["ok"]
    assert "snapshot_root_resolves" in pre["unresolved_data"]
    assert "manifest_identity" not in pre["unresolved_data"]
    for dependent in ("panel_digest", "sector_digest"):
        assert dependent not in pre["checks"]


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


# ---------- §7 single-execution guard (codex on #177) ----------


#: The four paths that, left alone, point at the operator's REAL durable store.
_CLAIM_ATTRS = ("RUN_LEDGER_DIR", "EXECUTION_CLAIM", "RESULT_PATH", "REFUSALS_LOG")


def _redirect_claim(monkeypatch, tmp_path) -> Path:
    d = tmp_path / "run-ledger"
    monkeypatch.setattr(R, "RUN_LEDGER_DIR", d)
    monkeypatch.setattr(R, "EXECUTION_CLAIM", d / "EXECUTION_CLAIM.json")
    monkeypatch.setattr(R, "RESULT_PATH", d / "result.json")
    monkeypatch.setattr(R, "REFUSALS_LOG", d / "refusals.jsonl")
    return d


@pytest.fixture(autouse=True)
def _never_touch_the_real_claim(monkeypatch, tmp_path):
    """AUTOUSE, because the safe path must not be opt-in.

    `_ledger()` was a helper each test had to remember to call, and the claim now lives
    at `~/renquant-data-store/goal7-momentum-prereg-run/` — OUTSIDE the repository. So a
    new test that calls `R.execute()` and forgets the helper consumes the single licensed
    execution of a frozen study, and `git status` shows nothing, because nothing in the
    repo changed. The failure is silent, durable and unrecoverable without an operator
    deliberately deleting the claim.

    That is the `enumerated-allow-list` shape: the dangerous path was the default and
    safety was the thing you had to remember. Inverted — every test in this module is
    redirected, and touching the real store now requires opting IN.
    """
    _redirect_claim(monkeypatch, tmp_path)


def _ledger(monkeypatch, tmp_path):
    """Kept for the tests that name it. The autouse fixture has already redirected;
    calling this again is idempotent and returns the same directory."""
    return _redirect_claim(monkeypatch, tmp_path)


def test_second_invocation_is_refused_BEFORE_any_data_read(monkeypatch, tmp_path, capsys):
    d = _ledger(monkeypatch, tmp_path)
    d.mkdir(parents=True)
    (d / "EXECUTION_CLAIM.json").write_text('{"status": "consumed"}')

    def boom(*a, **k):
        raise AssertionError("data was read AFTER the claim refusal")

    monkeypatch.setattr(R, "verify_preconditions", boom)
    monkeypatch.setattr(R, "load_snapshot_manifest", boom)
    rc = R.execute()
    assert rc == R.EXIT_ALREADY_EXECUTED == 4
    out = capsys.readouterr().out
    assert "ALREADY-EXECUTED" in out and "result selection" in out


def test_concurrent_claim_is_atomic(monkeypatch, tmp_path):
    """O_EXCL semantics: once one caller owns the claim, the second sees refusal —
    the same primitive covers concurrency and later reruns."""
    _ledger(monkeypatch, tmp_path)
    assert R._claim_execution() is None            # first caller wins
    assert R._claim_execution() == 4               # second (concurrent) refused


def test_pre_inference_unresolved_data_releases_the_claim_but_is_LEDGERED(
        monkeypatch, tmp_path, capsys):
    d = _ledger(monkeypatch, tmp_path)
    monkeypatch.setattr(R, "verify_preconditions", lambda: {
        "ok": False, "checks": {}, "unresolved_data": ["snapshot_manifest_present"]})
    rc = R.execute()
    assert rc == 3
    assert not (d / "EXECUTION_CLAIM.json").exists(), "identity refusal releases"
    lines = (d / "refusals.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1 and "snapshot_manifest_present" in lines[0]


def test_a_computed_outcome_CONSUMES_the_shot_and_seals_both_files(
        monkeypatch, tmp_path, capsys):
    d = _ledger(monkeypatch, tmp_path)
    assert R._claim_execution() is None
    rc = R._finish({"status": "UNRESOLVED-METHOD", "why": "calibration failed"}, 5)
    assert rc == 5
    result = d / "result.json"
    claim = d / "EXECUTION_CLAIM.json"
    assert result.is_file() and (result.stat().st_mode & 0o777) == 0o444
    assert (claim.stat().st_mode & 0o777) == 0o444
    import json as _json
    c = _json.loads(claim.read_text())
    assert c["status"] == "consumed" and c["exit_code"] == 5
    # ...and the shot is gone even though the verdict was UNRESOLVED
    assert R._claim_execution() == 4


def test_execute_refuses_a_caller_selected_output(tmp_path, capsys):
    rc = R.main(["--execute", "--json-out", str(tmp_path / "x.json")])
    assert rc == 2
    assert "PREDECLARED" in capsys.readouterr().err



def test_NO_test_in_this_module_can_reach_the_real_claim_store(monkeypatch, tmp_path):
    """The guard on the guard.

    Asserts the property rather than the convention: with the autouse fixture active and
    WITHOUT calling `_ledger()`, every claim path already points inside `tmp_path`. If
    the fixture is ever removed or renamed, this fails instead of a future test quietly
    burning the licence.
    """
    for attr in _CLAIM_ATTRS:
        value = Path(getattr(R, attr))
        assert value.is_relative_to(tmp_path), f"{attr} -> {value}"
        assert "renquant-data-store" not in str(value), f"{attr} -> {value}"


def test_a_forgetful_test_still_cannot_consume_the_licence(monkeypatch, tmp_path):
    """End-to-end version of the above: run the real entry point with no isolation call
    of its own and confirm the claim lands in tmp, not in the operator's store."""
    real = Path.home() / "renquant-data-store" / "goal7-momentum-prereg-run"
    before = sorted(q.name for q in real.iterdir()) if real.exists() else None
    monkeypatch.setattr(R, "AMENDMENT_2", tmp_path / "absent.md")
    R.execute()
    assert Path(R.EXECUTION_CLAIM).is_relative_to(tmp_path)
    # UPDATED 2026-08-02: the original asserted the real store DOES NOT EXIST,
    # which becomes false the moment a REAL execution runs — the test would then
    # fail on every branch forever. The property that matters is that THIS TEST
    # left the real store untouched: identical before/after listing.
    after = sorted(q.name for q in real.iterdir()) if real.exists() else None
    assert after == before, "the test leaked into the operator's real store"


# -------- the 2026-08-02 import-crash regression (guard validating the wrong object) --------


def test_tr_builder_import_has_NO_side_effects():
    """Importing the TR construction must not execute the July build script —
    its module-level raw-corpus guard crashed the single --execute on
    2026-08-02 (SystemExit at import, pre-inference). The package home is pure."""
    import importlib
    import sys as _sys

    mod = importlib.import_module("renquant_model_common.total_return")
    assert callable(mod.total_return_close)
    # the build SCRIPT must not have been pulled in by the package import
    assert "build_total_return_series" not in _sys.modules


def test_tr_function_arithmetic_is_unchanged_by_the_move():
    """Pin the moved-verbatim body on a hand-checked case: one $1 dividend on a
    $100 bar grosses up every EARLIER close by 1.01; the last bar is untouched."""
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    close = pd.Series([100.0, 100.0, 100.0], index=idx)
    div = pd.Series([0.0, 1.0, 0.0], index=idx)
    tr = R._load_tr_builder()(close, div)
    assert abs(tr.iloc[2] - 100.0) < 1e-12          # last bar: empty product
    assert abs(tr.iloc[1] - 100.0) < 1e-12          # gross-up applies to s > t only
    assert abs(tr.iloc[0] - 100.0 / 1.01) < 1e-9    # pre-event bar deflated


def test_an_import_time_guard_becomes_a_PREFLIGHT_refusal_not_a_crash(monkeypatch):
    """The stranded-claim shape: if the builder import ever raises again —
    including SystemExit — preflight fails tr_builder_importable, so execute()
    takes the claim-releasing UNRESOLVED-DATA path instead of dying mid-run."""
    def boom():
        raise SystemExit("ABORT: raw input layer changed")

    monkeypatch.setattr(R, "_load_tr_builder", boom)
    rep = R.verify_preconditions()
    assert "tr_builder_importable" in rep["unresolved_data"]
    assert "SystemExit" in rep["checks"]["tr_builder_importable"]["detail"]
