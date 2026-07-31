"""The clf/WF closure bundle's artifacts are version-controlled, not in a temp dir.

Ten committed documents cite this bundle. Its README recorded that the index was
committed *"ahead of the 6.97 MB of artifacts it names, because the artifacts live in
a session scratchpad that is garbage-collected"*.

Measured 2026-07-31: they were still alive — in THAT session's scratchpad, one session
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


# The full 64 hex characters, as ten documents and `PERSISTED.md:21` cite it.
CITED_ROOT = "901f0addd19b7381775f9dd593e046b862863b8bb04bb0de7260eb405423810a"


def _recompute_root_digest() -> str:
    """Rebuild the root digest FROM THE BYTES, by the index's own documented rule.

    `digest_construction` in the index states the construction, and
    `tools/corpus_index.py:86-87` implements it. Recomputing here rather than
    importing keeps the test honest about the *documented* rule: if the tool and
    the documentation ever disagree, this fails instead of inheriting the tool's
    behaviour as the definition.
    """
    lines = sorted(
        f"{rel}:{hashlib.sha256((ART / rel).read_bytes()).hexdigest()}"
        for rel in INDEX["files"]
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def test_the_root_digest_is_the_one_the_retraction_cites():
    """Codex on model#139: `startswith("901f0add")` is not an identity check.

    Two separate holes, and the prefix test closed neither. (1) Eight hex
    characters is 32 bits -- a *different* bundle sharing that prefix passes while
    the cited identity has changed. (2) More seriously, it compared the index to
    ITSELF: `root_digest_sha256` is a field the index declares, so an index could
    name any digest at all and the assertion would still hold. Nothing tied the
    cited identity to the bytes on disk.

    So: recompute from the bytes, and require the full 64 characters to equal both
    the value the documents cite AND the value the index declares.
    """
    recomputed = _recompute_root_digest()
    assert recomputed == CITED_ROOT, f"bytes on disk hash to {recomputed}"
    assert INDEX["root_digest_sha256"] == CITED_ROOT
    assert len(CITED_ROOT) == 64


def test_a_changed_byte_actually_breaks_the_root_digest():
    """The mutation codex asked for: prove the check above can FAIL.

    A verification that has never been observed to reject anything is a claim, not
    a control. One flipped byte in one of 61 files must change the root digest --
    if it does not, the digest is not a function of the corpus content and every
    "unchanged" claim resting on it is empty.
    """
    victim = sorted(INDEX["files"])[0]
    original = (ART / victim).read_bytes()
    mutated = bytes([original[0] ^ 0x01]) + original[1:]
    lines = sorted(
        f"{rel}:"
        + hashlib.sha256(mutated if rel == victim else (ART / rel).read_bytes()).hexdigest()
        for rel in INDEX["files"]
    )
    assert hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest() != CITED_ROOT

    # And the prefix check this replaced would ALSO have to fail on a real
    # substitution -- it does not, which is the point. A digest differing only
    # after character 8 is a different bundle that the old assertion admitted.
    assert CITED_ROOT.startswith("901f0add")
    assert ("901f0add" + "0" * 56) != CITED_ROOT


def test_the_gitignore_interception_is_recorded():
    """`.gitignore` excludes `data/`, so a plain `git add -A` stages nothing here.
    That nearly let a 61-file copy be reported as persisted while it was not."""
    doc = (DIR / "PERSISTED.md").read_text(encoding="utf-8")
    assert "git add -f" in doc
    assert ".gitignore:12" in doc
