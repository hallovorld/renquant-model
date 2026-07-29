"""The verifier must catch what an asserted hash cannot: tampering.

A committed index is only a REFERENCE if a reviewer can recompute it and be
told when the bytes disagree. These pin that contract.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "corpus_index.py"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True)


@pytest.fixture()
def corpus(tmp_path):
    root = tmp_path / "corpus"
    (root / "2024-01-01").mkdir(parents=True)
    (root / "2024-01-22").mkdir(parents=True)
    (root / "2024-01-01" / "model.pt").write_bytes(b"weights-a")
    (root / "2024-01-01" / "calib.json").write_text('{"a":1}')
    (root / "2024-01-22" / "model.pt").write_bytes(b"weights-b")
    (root / "manifest.json").write_text('{"n":2}')
    return root


def test_generate_then_verify_round_trips(corpus, tmp_path):
    idx = tmp_path / "index.json"
    assert _run("generate", "--root", str(corpus), "--out", str(idx)).returncode == 0
    body = json.loads(idx.read_text())
    assert body["n_files"] == 4 and len(body["root_digest_sha256"]) == 64
    assert _run("verify", "--root", str(corpus), "--index", str(idx)).returncode == 0


def test_a_single_flipped_byte_fails_verification(corpus, tmp_path):
    idx = tmp_path / "index.json"
    _run("generate", "--root", str(corpus), "--out", str(idx))
    (corpus / "2024-01-22" / "model.pt").write_bytes(b"weights-B")   # one byte
    r = _run("verify", "--root", str(corpus), "--index", str(idx))
    assert r.returncode == 1
    assert "content differs" in r.stderr and "2024-01-22/model.pt" in r.stderr


def test_a_missing_file_fails_verification(corpus, tmp_path):
    idx = tmp_path / "index.json"
    _run("generate", "--root", str(corpus), "--out", str(idx))
    (corpus / "manifest.json").unlink()
    r = _run("verify", "--root", str(corpus), "--index", str(idx))
    assert r.returncode == 1 and "missing from corpus" in r.stderr


def test_an_extra_file_fails_verification(corpus, tmp_path):
    idx = tmp_path / "index.json"
    _run("generate", "--root", str(corpus), "--out", str(idx))
    (corpus / "2024-01-01" / "sneaked.bin").write_bytes(b"x")
    r = _run("verify", "--root", str(corpus), "--index", str(idx))
    assert r.returncode == 1 and "not in the index" in r.stderr.replace(
        "present in corpus but not in index", "not in the index")


def test_digest_is_order_independent_but_content_dependent(corpus, tmp_path):
    a = tmp_path / "a.json"
    _run("generate", "--root", str(corpus), "--out", str(a))
    d1 = json.loads(a.read_text())["root_digest_sha256"]
    # touching mtimes must not change the digest; changing bytes must
    for p in corpus.rglob("*"):
        if p.is_file():
            p.touch()
    b = tmp_path / "b.json"
    _run("generate", "--root", str(corpus), "--out", str(b))
    assert json.loads(b.read_text())["root_digest_sha256"] == d1
    (corpus / "manifest.json").write_text('{"n":3}')
    c = tmp_path / "c.json"
    _run("generate", "--root", str(corpus), "--out", str(c))
    assert json.loads(c.read_text())["root_digest_sha256"] != d1


def test_symlinks_are_rejected_rather_than_silently_followed(corpus, tmp_path):
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"not part of the corpus")
    (corpus / "link.bin").symlink_to(outside)
    r = _run("generate", "--root", str(corpus))
    assert r.returncode != 0 and "symlink" in r.stderr


def test_the_construction_is_documented_in_the_artifact(corpus, tmp_path):
    idx = tmp_path / "index.json"
    _run("generate", "--root", str(corpus), "--out", str(idx))
    dc = json.loads(idx.read_text())["digest_construction"]
    # a reader must be able to reproduce the digest without reading the code
    for key in ("line_format", "sort", "join", "hash", "symlinks"):
        assert dc[key]


def test_index_written_inside_the_root_still_verifies(corpus):
    """The trap I walked into: an index written next to the artifacts.

    The index cannot contain its own digest, so without an exclusion rule
    `verify` fails immediately with 'present in corpus but not in index' —
    confusing, and it points at the tool rather than at the data.
    """
    inside = corpus / "INDEX.json"
    assert _run("generate", "--root", str(corpus), "--out", str(inside)).returncode == 0
    r = _run("verify", "--root", str(corpus), "--index", str(inside))
    assert r.returncode == 0, r.stderr


def test_self_exclusion_does_not_hide_a_real_extra_file(corpus, tmp_path):
    inside = corpus / "INDEX.json"
    _run("generate", "--root", str(corpus), "--out", str(inside))
    (corpus / "sneaked.bin").write_bytes(b"x")
    r = _run("verify", "--root", str(corpus), "--index", str(inside))
    assert r.returncode == 1 and "sneaked.bin" in r.stderr
