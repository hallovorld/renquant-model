"""Slice-2 TRAIN package tests: golden identity vs the v1 runner's assemble_day,
artifact contract completeness/types, digest recording, params_version pinning,
and the append-only digest-chained ledger. Synthetic fixtures everywhere; the
two live-surface tests are LOUD env-skips off-machine."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_momentum import (LedgerIntegrityError,
                                     append_to_artifact_ledger,
                                     content_sha256_of, load_and_verify_ledger,
                                     params_v0, train_momentum_artifact,
                                     verify_artifact_content_sha)
from renquant_model_momentum.ledger import row_sha256_of

REPO = Path(__file__).resolve().parent.parent


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name,
                                                  REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V1 = _load_tool("goal7_momentum_run")          # the sealed v1 runner
CLI = _load_tool("momentum_train_run")         # the slice-2 CLI

LIVE = (CLI.PANEL_PATH.is_file() and CLI.SECTORS_PATH.is_file()
        and (CLI.OHLCV_ROOT / CLI.MARKET / "1d.parquet").is_file())
OFF_MACHINE = ("live RenQuant data surfaces absent (off-machine) — this test "
               "reads the live ohlcv/panel READ-ONLY and cannot run in CI")

SHA_HEX = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------- fixtures --
class SyntheticReaders:
    """In-memory MomentumReaders with real sha256 digests over the arrays."""

    def __init__(self, trs, vols, market, sectors):
        self._trs, self._vols, self._market, self._sectors = \
            trs, vols, market, sectors
        import hashlib

        def dig(s: pd.Series) -> str:
            h = hashlib.sha256()
            h.update(np.ascontiguousarray(s.to_numpy(dtype=float)).tobytes())
            h.update(",".join(str(i) for i in s.index).encode())
            return h.hexdigest()

        self._digests = {f"synthetic/tr/{t}": dig(s) for t, s in trs.items()}
        self._digests |= {f"synthetic/vol/{t}": dig(s) for t, s in vols.items()}
        self._digests["synthetic/market"] = dig(market)

    def tr_returns(self, t):
        return self._trs.get(t)

    def volume(self, t):
        return self._vols.get(t)

    def market_tr_returns(self):
        return self._market

    def sector_of(self):
        return self._sectors

    def read_digests(self):
        return dict(self._digests)


def _world():
    """Deterministic synthetic panel: 8 names (5 sectored, 1 ETF, 1 thin,
    1 missing series), 320 business days."""
    idx = pd.bdate_range("2024-01-02", periods=320)
    rng = np.random.default_rng(11)
    market = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)

    def name(beta, drift, noise):
        return pd.Series(beta * market.to_numpy() + drift
                         + rng.normal(0, noise, len(idx)), index=idx)

    trs = {
        "AAA": name(0.6, 0.0012, 0.004),
        "BBB": name(1.4, -0.0004, 0.006),
        "CCC": name(1.0, 0.0006, 0.005),
        "DDD": name(0.9, 0.0, 0.007),
        "EEE": name(1.1, 0.0009, 0.005),
        "GLD": pd.Series(rng.normal(0.0002, 0.005, len(idx)), index=idx),
        "THIN": pd.Series(rng.normal(0, 0.01, 100), index=idx[-100:]),
    }
    vols = {t: pd.Series(np.abs(rng.normal(1e6, 1e5, len(s))), index=s.index)
            for t, s in trs.items()}
    sectors = {"AAA": "tech", "BBB": "tech", "CCC": "tech",
               "DDD": "energy", "EEE": "energy", "THIN": "energy"}
    universe = sorted(trs) + ["MISS"]          # MISS: no series anywhere
    asof = idx[-1] + pd.tseries.offsets.BDay(1)
    return {"idx": idx, "trs": trs, "vols": vols, "market": market,
            "sectors": sectors, "universe": universe, "asof": asof,
            "readers": SyntheticReaders(trs, vols, market, sectors)}


@pytest.fixture(scope="module")
def world():
    return _world()


@pytest.fixture(scope="module")
def artifact(world):
    return train_momentum_artifact(world["asof"], world["universe"],
                                   params_v0(), readers=world["readers"])


def _variant(artifact: dict, **overrides) -> dict:
    """A second valid artifact (new cutoff etc.) with a recomputed sha."""
    art = json.loads(json.dumps(artifact))
    art.update(overrides)
    art["content_sha256"] = content_sha256_of(art)
    return art


# ------------------------------------------------------------------ golden --
def test_golden_scores_match_v1_assemble_day(world, artifact):
    """The package's scores must equal the sealed v1 runner's assemble_day
    output to <1e-9 on the same fixed synthetic panel (design slice 2)."""
    day = pd.DataFrame({"ticker": sorted(world["universe"])})
    out = V1.assemble_day(day, world["trs"], world["market"], world["vols"],
                          world["sectors"], world["asof"])
    assert set(artifact["scores"]) == set(out["scores"])
    deltas = []
    for t, v1_score in out["scores"].items():
        pkg = artifact["scores"][t]
        if np.isfinite(v1_score):
            assert pkg is not None, f"{t}: package dropped a v1-scored name"
            deltas.append(abs(pkg - v1_score))
        else:
            assert pkg is None, f"{t}: package scored a v1-nan name"
    assert deltas and max(deltas) < 1e-9, f"max |delta| = {max(deltas)}"
    assert artifact["n_used"] == out["n_used"]
    assert artifact["n_scored"] == out["n_scored"]


def test_golden_fixture_actually_exercises_the_paths(artifact):
    """Positive control on the fixture: scored names exist, the thin name is
    nan-not-dropped, the missing series is counted, the ETF clears 3-of-5."""
    assert artifact["n_scored"] >= 5
    assert artifact["scores"]["THIN"] is None
    assert "MISS" not in artifact["scores"]
    assert artifact["n_missing_series"] == 1
    assert artifact["n_used"]["GLD"] >= 3


# ------------------------------------------------------- artifact contract --
REQUIRED_FIELDS = {
    "kind": str, "artifact_schema_version": int, "trained_at_utc": str,
    "cutoff_date": str, "cutoff_embargo_days": int,
    "effective_train_cutoff_date": str, "formation_window": dict,
    "params": dict, "universe": list, "n_names": int, "n_missing_series": int,
    "n_scored": int, "names_floor_ok": bool, "features": dict,
    "formation_return": dict, "cross_sectional_stats": dict, "scores": dict,
    "n_used": dict, "inputs": dict, "content_sha256": str,
}


def test_artifact_field_completeness_and_types(artifact):
    for field, typ in REQUIRED_FIELDS.items():
        assert field in artifact, f"missing {field}"
        assert isinstance(artifact[field], typ), \
            f"{field}: {type(artifact[field]).__name__} != {typ.__name__}"
    assert artifact["kind"] == "momentum_residual_v0"
    assert SHA_HEX.match(artifact["content_sha256"])
    assert artifact["n_names"] == 8


def test_artifact_lists_stay_lists_through_json(artifact):
    """The stringified-norm_kind lesson: strict-JSON round trip is identity,
    every list stays a list, no NaN token anywhere (allow_nan=False)."""
    text = json.dumps(artifact, allow_nan=False)   # raises on any NaN/Inf
    back = json.loads(text)
    assert back == artifact
    assert isinstance(back["universe"], list)
    assert all(isinstance(t, str) for t in back["universe"])
    assert isinstance(back["params"]["window"], int)


def test_cutoff_fields_are_consistent(world, artifact):
    """effective_train_cutoff_date is MEASURED and must sit exactly at
    cutoff - skip business days on a gap-free synthetic calendar."""
    skip = artifact["params"]["skip"]
    hi = world["asof"] - pd.tseries.offsets.BDay(skip)
    assert artifact["cutoff_embargo_days"] == skip
    assert pd.Timestamp(artifact["effective_train_cutoff_date"]) == hi
    assert artifact["cutoff_date"] == str(world["asof"].date())


def test_cross_sectional_stats_reconstruct_the_scores(artifact):
    """The serving contract: (features, cross_sectional_stats) alone must
    reproduce the composite score for every scored name."""
    stats = artifact["cross_sectional_stats"]
    for f, st in stats.items():
        assert set(st) == {"n_finite", "mean", "sd", "used_in_composite"}
    for t, score in artifact["scores"].items():
        if score is None:
            continue
        zs = [(artifact["features"][t][f] - stats[f]["mean"]) / stats[f]["sd"]
              for f in ("f1", "f2", "f3", "f4", "f5")
              if stats[f]["used_in_composite"]
              and artifact["features"][t][f] is not None]
        assert len(zs) == artifact["n_used"][t]
        assert abs(float(np.mean(zs)) - score) < 1e-9


def test_content_sha_verifies_and_detects_tamper(artifact):
    verify_artifact_content_sha(artifact)
    tampered = json.loads(json.dumps(artifact))
    tampered["n_scored"] += 1
    with pytest.raises(ValueError, match="content_sha256 mismatch"):
        verify_artifact_content_sha(tampered)


def test_names_floor_is_measured_not_silently_enforced(artifact):
    """8 synthetic names < the frozen floor of 50: the artifact must SAY so
    (names_floor_ok false) while still carrying the full construction —
    refusal belongs to the consumers, as in the v1 runner's thin-date skip."""
    assert artifact["names_floor_ok"] is False
    assert artifact["params"]["names_per_date_floor"] == 50
    assert artifact["n_scored"] >= 5


# ------------------------------------------------------------------ params --
def test_params_v0_pins_the_frozen_constants():
    """BY-IMPORT sourcing, pinned to the published literals (model#164 §2 +
    the #177 F5 floor): any drift in the sealed module fails loudly here."""
    p = params_v0()
    assert p["params_version"] == "v0"
    pins = {"window": 252, "skip": 21, "min_obs": 200, "min_features": 3,
            "names_per_date_floor": 50, "min_side_obs": 30}
    assert {k: p[k] for k in pins} == pins
    v1_frozen = {k: V1.FROZEN[k] for k in
                 ("window", "skip", "min_obs", "min_features",
                  "names_per_date_floor")}
    assert {k: p[k] for k in v1_frozen} == v1_frozen
    assert p["min_side_obs"] == V1.MIN_SIDE_OBS


def test_params_v0_mirrors_the_sealed_v1_runner():
    """THE test that makes the packaged mirror safe (review round 1).

    `params_v0` no longer imports the sealed runner — it reads
    `_frozen_params_v0`, which ships in the wheel. That trades a
    cannot-drift-by-construction property for a copy, and this is what pays for the
    trade: every mirrored constant must still equal the sealed runner's own value.
    It runs wherever the repo is present, which is CI.

    If this ever fails, the mirror is what changed and the sealed runner is right.
    """
    from renquant_model_momentum import _frozen_params_v0 as F

    assert F.WINDOW == V1.FROZEN["window"]
    assert F.SKIP == V1.FROZEN["skip"]
    assert F.MIN_OBS == V1.FROZEN["min_obs"]
    assert F.MIN_FEATURES == V1.FROZEN["min_features"]
    assert F.NAMES_PER_DATE_FLOOR == V1.FROZEN["names_per_date_floor"]
    assert F.MIN_SIDE_OBS == V1.MIN_SIDE_OBS
    # ...and the provenance string still names the sealed runner as the authority
    assert "goal7_momentum_run.py::FROZEN" in F.PARAMS_SOURCE


def test_params_v0_needs_NOTHING_outside_the_installed_package():
    """The reviewer's reproduction, as a permanent test.

    The defect was that `params_v0()` read a path outside `src/`, so an installed wheel
    raised `FileNotFoundError` at first use while every in-repo test passed. Asserted
    structurally rather than by building a wheel each run: the module that supplies the
    constants must live inside the package, and `train.py` must not reference the repo
    root or the tools directory at all.
    """
    import renquant_model_momentum as pkg
    from renquant_model_momentum import _frozen_params_v0 as F
    from renquant_model_momentum import train as T

    pkg_dir = Path(pkg.__file__).resolve().parent
    assert Path(F.__file__).resolve().is_relative_to(pkg_dir)

    # BEHAVIOURAL, not a grep of the source: copy ONLY the package into a temp tree
    # with no `tools/` anywhere above it — the shape of an installed wheel — and call
    # params_v0() from there. A source-substring check would pass on a docstring that
    # merely MENTIONS the old path, which is the wrong object to be checking.
    import shutil
    import subprocess
    import sys
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(pkg_dir, Path(tmp) / pkg_dir.name)
        out = subprocess.run(
            [sys.executable, "-c",
             "from renquant_model_momentum.train import params_v0;"
             "p = params_v0(); print(p['window'], p['min_side_obs'])"],
            cwd=tmp, env={"PYTHONPATH": tmp, "PATH": "/usr/bin:/bin"},
            capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-600:]
        assert out.stdout.split() == ["252", "30"], out.stdout
    assert params_v0()["window"] == 252


def test_params_version_is_required(world):
    p = params_v0()
    del p["params_version"]
    with pytest.raises(ValueError, match="params_version"):
        train_momentum_artifact(world["asof"], world["universe"], p,
                                readers=world["readers"])


def test_params_missing_key_refused(world):
    p = params_v0()
    del p["min_side_obs"]
    with pytest.raises(ValueError, match="min_side_obs"):
        train_momentum_artifact(world["asof"], world["universe"], p,
                                readers=world["readers"])


def test_params_non_int_constant_refused(world):
    p = params_v0()
    p["window"] = 252.0
    with pytest.raises(ValueError, match="window"):
        train_momentum_artifact(world["asof"], world["universe"], p,
                                readers=world["readers"])


@pytest.mark.parametrize("key,bad_value,match", [
    ("window", 0, "window"),
    ("skip", -1, "skip"),
    ("min_obs", 0, "min_obs"),
    ("min_features", 0, "min_features"),
    ("min_features", 6, "min_features"),
    ("names_per_date_floor", 0, "names_per_date_floor"),
    ("min_side_obs", 0, "min_side_obs"),
])
def test_params_v0_domain_violation_refused(world, key, bad_value, match):
    """Type-valid but out-of-domain v0 params must be refused before reader
    access (codex review, PR #196) — a permissive-type-only check let a
    negative skip / zero window / impossible feature floor produce a
    self-identifying, gate-compatible-looking artifact."""
    p = params_v0()
    p[key] = bad_value
    with pytest.raises(ValueError, match=match):
        train_momentum_artifact(world["asof"], world["universe"], p,
                                readers=world["readers"])


def test_params_min_obs_greater_than_window_refused(world):
    p = params_v0()
    p["min_obs"] = p["window"] + 1
    with pytest.raises(ValueError, match="min_obs"):
        train_momentum_artifact(world["asof"], world["universe"], p,
                                readers=world["readers"])


def test_params_unsupported_version_refused(world):
    """A new params_version must not silently inherit v0's domain semantics —
    fail closed until an explicit validator is registered for it."""
    p = params_v0()
    p["params_version"] = "v1"
    with pytest.raises(ValueError, match="unsupported params_version"):
        train_momentum_artifact(world["asof"], world["universe"], p,
                                readers=world["readers"])


# ---------------------------------------------------------- digest recording -
def test_read_digests_recorded_per_input(artifact, world):
    digs = artifact["inputs"]["read_digests"]
    assert digs, "no read digests recorded"
    for name, sha in digs.items():
        assert isinstance(name, str) and isinstance(sha, str)
        assert SHA_HEX.match(sha), f"{name}: not a sha256 hex ({sha!r})"
    for t in world["trs"]:
        assert f"synthetic/tr/{t}" in digs
    assert "synthetic/market" in digs
    assert artifact["inputs"]["digest_policy"].startswith("recorded-at-read")


# ------------------------------------------------------------------ ledger --
def test_ledger_appends_and_chain_verifies(tmp_path, artifact):
    ledger = tmp_path / "ledger.jsonl"
    r0 = append_to_artifact_ledger(artifact, ledger)
    art2 = _variant(artifact, cutoff_date="2026-01-09")
    r1 = append_to_artifact_ledger(art2, ledger)
    rows = load_and_verify_ledger(ledger)
    assert [r["row_index"] for r in rows] == [0, 1]
    assert rows[0]["prev_row_sha"] is None
    assert rows[1]["prev_row_sha"] == rows[0]["row_sha"]
    assert rows[0]["row_sha"] == row_sha256_of(rows[0]) == r0["row_sha"]
    assert rows[1]["artifact_content_sha256"] == art2["content_sha256"]
    assert r1["read_digests"] == artifact["inputs"]["read_digests"]


def test_ledger_append_preserves_existing_bytes(tmp_path, artifact):
    ledger = tmp_path / "ledger.jsonl"
    append_to_artifact_ledger(artifact, ledger)
    first = ledger.read_bytes()
    append_to_artifact_ledger(_variant(artifact, cutoff_date="2026-01-09"),
                              ledger)
    assert ledger.read_bytes().startswith(first), \
        "append rewrote already-written bytes"


def test_ledger_refuses_rewritten_history(tmp_path, artifact):
    ledger = tmp_path / "ledger.jsonl"
    append_to_artifact_ledger(artifact, ledger)
    row = json.loads(ledger.read_text())
    row["n_scored"] = 999                       # rewrite an existing row
    ledger.write_text(json.dumps(row, sort_keys=True,
                                 separators=(",", ":")) + "\n")
    with pytest.raises(LedgerIntegrityError, match="edited after"):
        load_and_verify_ledger(ledger)
    with pytest.raises(LedgerIntegrityError, match="edited after"):
        append_to_artifact_ledger(_variant(artifact,
                                           cutoff_date="2026-01-09"), ledger)


def test_ledger_refuses_broken_chain(tmp_path, artifact):
    ledger = tmp_path / "ledger.jsonl"
    append_to_artifact_ledger(artifact, ledger)
    append_to_artifact_ledger(_variant(artifact, cutoff_date="2026-01-09"),
                              ledger)
    lines = ledger.read_text().splitlines()
    ledger.write_text(lines[1] + "\n")          # drop row 0: chain must break
    with pytest.raises(LedgerIntegrityError):
        load_and_verify_ledger(ledger)


def test_ledger_refuses_duplicate_cutoff_and_params_version(tmp_path, artifact):
    ledger = tmp_path / "ledger.jsonl"
    append_to_artifact_ledger(artifact, ledger)
    with pytest.raises(LedgerIntegrityError, match="already exists"):
        append_to_artifact_ledger(artifact, ledger)
    n_lines = len(ledger.read_text().splitlines())
    assert n_lines == 1, "the refused append still wrote a row"


def test_ledger_refuses_artifact_with_stale_content_sha(tmp_path, artifact):
    bad = json.loads(json.dumps(artifact))
    bad["n_scored"] += 1                        # sha NOT recomputed
    with pytest.raises(LedgerIntegrityError, match="content_sha256"):
        append_to_artifact_ledger(bad, tmp_path / "ledger.jsonl")
    assert not (tmp_path / "ledger.jsonl").exists()


# --------------------------------------------------------------------- CLI --
def test_cli_refuses_when_surfaces_missing(monkeypatch, capsys, tmp_path):
    """Fail-closed without live surfaces — runs everywhere, no env-skip."""
    monkeypatch.setattr(CLI, "PANEL_PATH", tmp_path / "absent.parquet")
    rc = CLI.main(["--asof", "2026-07-01", "--dry-run",
                   "--out-root", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert rc == 3
    assert "REFUSED-SURFACES-MISSING" in out
    assert not (tmp_path / "out").exists()


def _wire_fake_cli_surfaces(monkeypatch, tmp_path, world):
    """Point the CLI at tmp-path surface stubs + the synthetic readers so the
    real-run path executes end-to-end with no live data. Returns
    (out_root, asof_str, cutoff_dir)."""
    ohlcv_market_dir = tmp_path / "ohlcv" / CLI.MARKET
    ohlcv_market_dir.mkdir(parents=True)
    (ohlcv_market_dir / "1d.parquet").touch()
    sectors_path = tmp_path / "sectors.json"
    sectors_path.write_text("{}")
    panel_path = tmp_path / "panel.parquet"
    panel_path.touch()

    monkeypatch.setattr(CLI, "PANEL_PATH", panel_path)
    monkeypatch.setattr(CLI, "SECTORS_PATH", sectors_path)
    monkeypatch.setattr(CLI, "OHLCV_ROOT", tmp_path / "ohlcv")
    monkeypatch.setattr(CLI, "resolve_universe",
                        lambda asof: (world["universe"], "2024-01-01"))
    monkeypatch.setattr(world["readers"], "record_digest",
                        lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(CLI, "LiveReaders", lambda *a, **kw: world["readers"])
    out_root = tmp_path / "out"
    asof_str = str(world["asof"].date())
    return out_root, asof_str, out_root / asof_str


def test_finalize_happens_before_ledger_append(monkeypatch, tmp_path, world):
    """Two-file protocol invariant (codex review round 3, #196): by the time
    append_to_artifact_ledger is called, the final-named artifact must
    already exist on disk — proving the order is finalize-THEN-ledger, never
    the reverse. The reverse order left the more authoritative failure mode:
    a crash between ledger-append and rename could leave an append-only
    ledger row permanently pointing at a missing artifact, unrepairable
    because a retry hits the duplicate-row refusal."""
    out_root, asof_str, cutoff_dir = _wire_fake_cli_surfaces(
        monkeypatch, tmp_path, world)
    real_append = CLI.append_to_artifact_ledger
    seen = {}

    def _spy(artifact, ledger_path):
        seen["artifact_exists_at_append_time"] = \
            (cutoff_dir / CLI.ARTIFACT_BASENAME).is_file()
        seen["no_tmp_at_append_time"] = not any(cutoff_dir.glob("*.tmp"))
        return real_append(artifact, ledger_path)
    monkeypatch.setattr(CLI, "append_to_artifact_ledger", _spy)

    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    assert rc == 0
    assert seen["artifact_exists_at_append_time"] is True
    assert seen["no_tmp_at_append_time"] is True


def test_cli_ledger_refusal_leaves_a_reconcilable_artifact(monkeypatch,
                                                           tmp_path, world):
    """Regression (codex review round 3, PR #196): under the two-file
    protocol the artifact is finalized BEFORE the ledger append is
    attempted, so a ledger-append failure leaves the finalized artifact ON
    DISK (never a bare orphaned .tmp) with the ledger untouched. A retry
    must RECONCILE — append the row for the artifact already on disk —
    rather than re-run training (the artifact bytes, including
    trained_at_utc, must be unchanged by the retry)."""
    out_root, asof_str, cutoff_dir = _wire_fake_cli_surfaces(
        monkeypatch, tmp_path, world)
    real_append = CLI.append_to_artifact_ledger

    def _boom(artifact, ledger_path):
        raise RuntimeError("simulated ledger refusal")
    monkeypatch.setattr(CLI, "append_to_artifact_ledger", _boom)

    with pytest.raises(RuntimeError, match="simulated ledger refusal"):
        CLI.main(["--asof", asof_str, "--out-root", str(out_root)])

    final = cutoff_dir / CLI.ARTIFACT_BASENAME
    assert final.is_file(), \
        "the artifact must already be finalized when the ledger append fails"
    assert not any(cutoff_dir.glob("*.tmp")), "staging file survived finalize"
    ledger_path = out_root / CLI.LEDGER_BASENAME
    assert load_and_verify_ledger(ledger_path) == []
    original_sha = json.loads(final.read_text())["content_sha256"]

    # RETRY AFTER THE FAILURE CLEARS: reconcile, never retrain.
    monkeypatch.setattr(CLI, "append_to_artifact_ledger", real_append)
    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    assert rc == 0, "retry after a cleared ledger failure must reconcile"
    assert not any(cutoff_dir.glob("*.tmp"))
    rows = load_and_verify_ledger(ledger_path)
    assert len(rows) == 1
    assert json.loads(final.read_text())["content_sha256"] == original_sha, \
        "reconciliation must not re-train — the artifact bytes are unchanged"
    assert rows[0]["artifact_content_sha256"] == original_sha


def test_cli_ledger_integrity_refusal_is_clean_exit_5(monkeypatch, tmp_path,
                                                      world, capsys):
    """A LedgerIntegrityError is an EXPECTED refusal, not a crash: clean
    REFUSED-LEDGER JSON + exit 5. Under the two-file protocol the finalized
    artifact is already on disk when this refusal fires (never orphaned as a
    bare .tmp); a retry reconciles that same artifact rather than
    re-training once the cause clears."""
    out_root, asof_str, cutoff_dir = _wire_fake_cli_surfaces(
        monkeypatch, tmp_path, world)
    real_append = CLI.append_to_artifact_ledger
    calls = {"n": 0}

    def _flaky(artifact, ledger_path):
        if calls["n"] == 0:
            calls["n"] += 1
            raise LedgerIntegrityError("transient: simulated tampered ledger")
        return real_append(artifact, ledger_path)
    monkeypatch.setattr(CLI, "append_to_artifact_ledger", _flaky)

    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    out = capsys.readouterr().out
    assert rc == 5
    assert "REFUSED-LEDGER" in out
    final = cutoff_dir / CLI.ARTIFACT_BASENAME
    assert final.is_file(), \
        "the artifact must already be finalized when the ledger refuses"
    assert not any(cutoff_dir.glob("*.tmp"))
    original_sha = json.loads(final.read_text())["content_sha256"]

    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    out = capsys.readouterr().out
    assert rc == 0, "retry after the transient refusal must reconcile"
    assert "RECONCILED" in out
    assert json.loads(final.read_text())["content_sha256"] == original_sha, \
        "reconciliation must not re-train — the artifact bytes are unchanged"
    assert len(load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME)) == 1


def test_cli_refuses_when_artifact_already_ledgered(monkeypatch, tmp_path,
                                                    world):
    """The common case: a fully-processed cutoff (artifact finalized AND
    ledgered) must refuse a second run rather than reconcile — reconciliation
    is only for a finalized artifact with NO matching ledger row."""
    out_root, asof_str, cutoff_dir = _wire_fake_cli_surfaces(
        monkeypatch, tmp_path, world)
    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    assert rc == 0
    original_sha = json.loads(
        (cutoff_dir / CLI.ARTIFACT_BASENAME).read_text())["content_sha256"]

    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    assert rc == 4
    rows = load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME)
    assert len(rows) == 1, "the second run must not append a duplicate row"
    assert json.loads(
        (cutoff_dir / CLI.ARTIFACT_BASENAME).read_text()
    )["content_sha256"] == original_sha


def test_cli_refuses_when_existing_artifact_fails_content_sha(monkeypatch,
                                                              tmp_path,
                                                              world, capsys):
    """A finalized artifact whose bytes were tampered with (self-carried
    content_sha256 no longer recomputes) must be refused, not silently
    reconciled — reconciliation trusts only a verified artifact."""
    out_root, asof_str, cutoff_dir = _wire_fake_cli_surfaces(
        monkeypatch, tmp_path, world)
    final = cutoff_dir / CLI.ARTIFACT_BASENAME
    final.parent.mkdir(parents=True, exist_ok=True)
    tampered = dict(json.loads(json.dumps({
        "kind": "momentum_residual_v0", "cutoff_date": asof_str,
        "params": {"params_version": "v0"}, "content_sha256": "00" * 32})))
    final.write_text(json.dumps(tampered))

    rc = CLI.main(["--asof", asof_str, "--out-root", str(out_root)])
    out = capsys.readouterr().out
    assert rc == 4
    assert "REFUSED-ARTIFACT-EXISTS" in out
    assert "content-sha" in out
    assert load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME) == [], \
        "a tampered artifact must never be ledgered"


@pytest.mark.skipif(not LIVE, reason=OFF_MACHINE)
def test_cli_dry_run_smoke_on_live_surfaces(tmp_path):
    """READ-ONLY smoke: --dry-run resolves the universe and writes NOTHING."""
    out_root = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "momentum_train_run.py"),
         "--asof", "2026-07-01", "--dry-run", "--out-root", str(out_root)],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    rep = json.loads(proc.stdout)
    assert rep["dry_run"] is True
    assert rep["params"]["params_version"] == "v0"
    assert rep["universe_n"] >= 50, "live universe under the names floor"
    assert not out_root.exists(), "--dry-run wrote something"


@pytest.mark.skipif(not LIVE, reason=OFF_MACHINE)
def test_real_data_golden_subset_matches_v1_assemble_day():
    """Real-data golden (READ-ONLY, env-skipped off-machine): on a 60-name
    subset of the live universe at a fixed asof, the package must equal
    assemble_day to <1e-9 through the REAL total-return construction."""
    asof = pd.Timestamp("2026-07-01")
    universe, _ = CLI.resolve_universe(asof)
    subset = sorted(universe[:60])
    readers = CLI.LiveReaders()
    art = train_momentum_artifact(asof, subset, params_v0(), readers=readers)

    trs, vols = {}, {}
    for t in subset:
        r = readers.tr_returns(t)
        if r is not None:
            trs[t] = r
            vols[t] = readers.volume(t)
    day = pd.DataFrame({"ticker": subset})
    out = V1.assemble_day(day, trs, readers.market_tr_returns(), vols,
                          dict(readers.sector_of()), asof)
    assert set(art["scores"]) == set(out["scores"])
    deltas = [abs(art["scores"][t] - s) for t, s in out["scores"].items()
              if np.isfinite(s)]
    assert deltas and max(deltas) < 1e-9, f"max |delta| = {max(deltas)}"
    for t, s in out["scores"].items():
        assert (art["scores"][t] is None) == (not np.isfinite(s))
    digs = art["inputs"]["read_digests"]
    assert all(SHA_HEX.match(v) for v in digs.values())
    assert any(k.startswith("ohlcv/") for k in digs)
