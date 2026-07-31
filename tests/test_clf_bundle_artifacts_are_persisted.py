"""The clf/WF closure bundle's artifacts are version-controlled, not in a temp dir.

Ten committed documents cite this bundle. Its README recorded that the index was
committed *"ahead of the 6.97 MB of artifacts it names, because the artifacts live in
a session scratchpad that is garbage-collected"*.

Measured 2026-08-01: they were still alive — in THAT session's scratchpad, one session
boundary from unrecoverable. These tests hold the corpus in the repo and verify it
against the index that ten documents cite.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

DIR = (pathlib.Path(__file__).resolve().parent.parent
       / "doc/research/data/2026-07-29-clf-wf-closure-bundle")
INDEX = json.loads((DIR / "bundle_index.json").read_text(encoding="utf-8"))
ART = DIR / "artifacts"


def test_every_indexed_file_is_present_in_the_repo():
    missing = [rel for rel in INDEX["files"] if not (ART / rel).exists()]
    assert missing == [], missing
    assert len(INDEX["files"]) == 61


def test_every_file_matches_the_digest_the_documents_cite():
    bad = []
    for rel, meta in INDEX["files"].items():
        h = hashlib.sha256((ART / rel).read_bytes()).hexdigest()
        if h != meta["sha256"]:
            bad.append(rel)
    assert bad == [], bad


def test_the_total_size_matches_the_index_exactly():
    total = sum((ART / rel).stat().st_size for rel in INDEX["files"])
    assert total == INDEX["total_bytes"] == 6_969_817


def test_the_root_digest_is_the_one_the_retraction_cites():
    assert INDEX["root_digest_sha256"].startswith("901f0add")


def test_the_gitignore_interception_is_recorded():
    """`.gitignore` excludes `data/`, so a plain `git add -A` stages nothing here.
    That nearly let a 61-file copy be reported as persisted while it was not."""
    doc = (DIR / "PERSISTED.md").read_text(encoding="utf-8")
    assert "git add -f" in doc
    assert ".gitignore:12" in doc
