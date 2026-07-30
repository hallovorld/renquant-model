"""`tools/M.py` pins the RAW OHLCV layer, not just the two
derived parquets `momentum_total_return_run.py` already sha256-pins.

Module-level `LIVE`/`OHLCV`/`CFG` are monkeypatched to a synthetic fixture so
these tests never touch the real umbrella corpus -- the tool's own hashing
logic and its reuse of `corpus_index.py` are what's under test, not any
particular ticker's bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import raw_input_manifest as M  # noqa: E402


@pytest.fixture()
def fake_universe(tmp_path, monkeypatch):
    live = tmp_path / "live"
    ohlcv = live / "data" / "ohlcv"
    cfg_dir = (live / ".subrepo_runtime" / "repos" / "renquant-strategy-104"
               / "configs")
    cfg_dir.mkdir(parents=True)
    cfg_path = cfg_dir / "strategy_config.json"
    watchlist = ["AAA", "BBB", "SPY"]  # SPY already IN the watchlist, as in prod
    cfg_path.write_text(json.dumps({"watchlist": watchlist}))
    for t in watchlist:
        d = ohlcv / t
        d.mkdir(parents=True)
        (d / "1d.parquet").write_bytes(f"{t}-bytes".encode())
    monkeypatch.setattr(M, "LIVE", live)
    monkeypatch.setattr(M, "OHLCV", ohlcv)
    monkeypatch.setattr(M, "CFG", cfg_path)
    return live, ohlcv, cfg_path, watchlist


def test_generate_pins_every_raw_file_and_the_config(fake_universe):
    _, ohlcv, cfg_path, watchlist = fake_universe
    manifest = M.build_manifest()
    assert manifest["universe"]["n"] == len(watchlist)
    assert manifest["corpus_index"]["n_files"] == len(watchlist)
    assert set(manifest["corpus_index"]["files"]) == {
        f"{t}/1d.parquet" for t in watchlist}
    assert (manifest["config"]["sha256"]
            == hashlib.sha256(cfg_path.read_bytes()).hexdigest())


def test_bench_already_in_watchlist_is_not_double_counted(fake_universe):
    # SPY is one of the fixture's 3 watchlist names, matching production
    # (SPY is one of the 145 watchlist tickers, not a 146th name); the tool
    # must not append it a second time.
    manifest = M.build_manifest()
    assert manifest["universe"]["n"] == 3
    assert manifest["universe"]["bench"] == "SPY"


def test_generate_then_verify_round_trips(fake_universe, tmp_path):
    out = tmp_path / "manifest.json"
    assert M.cmd_generate(argparse.Namespace(out=str(out))) == 0
    assert M.cmd_verify(argparse.Namespace(manifest=str(out))) == 0


def test_a_tampered_raw_file_fails_verification(fake_universe, tmp_path, capsys):
    ohlcv = fake_universe[1]
    out = tmp_path / "manifest.json"
    M.cmd_generate(argparse.Namespace(out=str(out)))
    (ohlcv / "AAA" / "1d.parquet").write_bytes(b"tampered")
    rc = M.cmd_verify(argparse.Namespace(manifest=str(out)))
    assert rc == 1
    err = capsys.readouterr().err
    assert "raw OHLCV corpus fingerprint changed" in err


def test_a_changed_watchlist_config_fails_verification(fake_universe, tmp_path):
    cfg_path = fake_universe[2]
    out = tmp_path / "manifest.json"
    M.cmd_generate(argparse.Namespace(out=str(out)))
    # widen the watchlist without adding the matching data dir: this must
    # abort loudly at build time (see test below), so change it to a
    # same-length, different-content watchlist instead to isolate the
    # config-fingerprint check from the missing-file check.
    cfg_path.write_text(json.dumps({"watchlist": ["AAA", "BBB", "CCC"]}))
    (fake_universe[1] / "CCC").mkdir()
    (fake_universe[1] / "CCC" / "1d.parquet").write_bytes(b"CCC-bytes")
    rc = M.cmd_verify(argparse.Namespace(manifest=str(out)))
    assert rc == 1


def test_missing_raw_file_aborts_loudly_instead_of_silently_skipping(fake_universe):
    (fake_universe[1] / "BBB" / "1d.parquet").unlink()
    with pytest.raises(SystemExit, match="missing"):
        M.build_manifest()


def test_digest_is_stable_across_repeated_builds(fake_universe):
    a = M.build_manifest()
    b = M.build_manifest()
    assert (a["corpus_index"]["root_digest_sha256"]
            == b["corpus_index"]["root_digest_sha256"])


# --- a missing or malformed pin must ABORT, not be waved through -----------
#
# verify_or_abort() printed a [NOTE] and RETURNED when the manifest was absent,
# on a bootstrap rationale that expired once the pin was committed. That left a
# function named verify_or_abort doing neither on its worst failure mode: a
# builder producing output with NO provenance, which downstream cannot tell
# apart from verified output.


def test_a_missing_manifest_aborts(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(SystemExit) as ei:
        M.verify_or_abort(missing)
    msg = str(ei.value)
    assert "ABORT" in msg
    assert "no committed raw-input manifest" in msg
    assert "generate --out" in msg, "must tell the caller how to fix it"


def test_a_malformed_manifest_aborts(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text("{not json at all")
    with pytest.raises(SystemExit) as ei:
        M.verify_or_abort(bad)
    assert "could not be read" in str(ei.value)


def test_bootstrap_escape_requires_an_explicit_flag(tmp_path, capsys):
    """The escape still exists for generating the first pin, but it must be
    asked for at the call site rather than being the default."""
    missing = tmp_path / "nope.json"
    M.verify_or_abort(missing, allow_missing=True)   # no raise
    assert "BOOTSTRAP" in capsys.readouterr().out


def test_the_committed_pin_is_present_so_the_escape_is_not_load_bearing():
    """Guards the rationale: the bootstrap path must not be what production
    actually takes."""
    assert M.MOMENTUM_TOTAL_RETURN_PIN.exists(), (
        "the committed pin is missing, so every builder would now abort — "
        "regenerate and commit it rather than relaxing the check")
