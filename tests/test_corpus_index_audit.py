"""A committed index without its bytes is a promise nobody can check.

model#139 rescued one such bundle (clf/WF closure, 61 files) from a session scratchpad
hours before it would have been unrecoverable. This audit exists because the obvious
next question — *is it the only one?* — has a measured answer: **no**.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOD = ROOT / "tools" / "corpus_index_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("cia", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules["cia"] = m
    spec.loader.exec_module(m)
    return m


C = _load()


def test_it_finds_every_committed_index_by_SCHEMA_not_by_filename():
    """The three known indexes are named `bundle_index.json`, `INDEX.json` and
    `…-corpus-index.json`. A filename rule would have missed two of three."""
    found = {p.name for p in C.find_indexes(ROOT)}
    assert len(found) >= 3
    assert len({"bundle_index.json", "INDEX.json"} & found) == 2


def test_the_43fold_corpus_is_NOT_locatable(tmp_path):
    idx = ROOT / "doc/research/evidence/2026-07-29-patchtst-43fold-corpus-index.json"
    r = C.audit_one(idx)
    assert r["n_files"] == 133
    assert r["found"] == 0
    assert r["verifiable"] is False
    assert r["root_digest_sha256"].startswith("b8aa2d99")


def test_a_verifiable_index_is_reported_as_such():
    """CONTROL. Without one that passes, 'unverifiable' would just mean the audit
    cannot find anything."""
    idx = ROOT / "doc/research/data/2026-07-30-patchtst-closure-v2/INDEX.json"
    r = C.audit_one(idx)
    assert r["n_files"] == 7
    assert r["found"] == 7 and r["digest_matched"] == 7
    assert r["verifiable"] is True


def test_it_records_WHERE_it_looked():
    """A nil result is only interpretable if the search roots are stated."""
    idx = ROOT / "doc/research/evidence/2026-07-29-patchtst-43fold-corpus-index.json"
    assert C.audit_one(idx)["searched_roots"], "no roots recorded"


def test_no_index_at_all_is_an_ERROR_not_a_pass(tmp_path):
    """The anti-vacuity condition is about the SUBJECTS, never about the finding."""
    (tmp_path / "doc").mkdir()
    assert C.main(["--repo", str(tmp_path)]) == C.EXIT_ERROR


def test_the_tool_does_not_claim_fabrication():
    """This programme has a 2026-07-28/29 incident on exactly this distinction,
    including one occasion where a REAL corpus was wrongly re-flagged as fake."""
    src = MOD.read_text(encoding="utf-8")
    assert "'Not locatable' is NOT 'fabricated'" in src
    assert "draws no conclusion about why" in src


def test_the_tool_does_not_claim_a_search_it_did_not_run():
    """Codex on model#140: the default scan is index-local, so the claim must be too.

    `audit_one` searches the index's directory and its `artifacts/` subdirectory unless
    `--also-search` is passed. A document citing this tool for "not locatable anywhere"
    is citing a search that did not happen. The module docstring is where a reader forms
    that expectation, so it is held here.
    """
    # Whitespace-normalised, and read off the module THIS FILE loads rather than a
    # second import: the phrases held here are prose, and a line wrap moving by one
    # word must not decide whether a scope claim is enforced. It did on the first run
    # of this test -- `NOT "not\nlocatable"` failed a literal match.
    doc = " ".join((C.__doc__ or "").split())
    assert "not present beside this index" in doc
    assert 'NOT "not locatable"' in doc
    assert "--also-search" in doc
    # And the stronger claim must not be sitting somewhere else in the same docstring.
    assert "could not be located at all" not in doc
