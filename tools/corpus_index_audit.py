#!/usr/bin/env python3
"""Which committed corpus indexes can still be verified, and which cannot.

A `artifact_corpus_index.v2` file records `{relpath: {bytes, sha256}}` for a bundle of
evidence. Committing the index without the bytes leaves a promise nobody can check:
the digests stay reproducible in principle and unverifiable in practice.

Measured 2026-08-01 across this repo, that was the state of **two** indexes, not one --
the clf/WF closure bundle (61 files, rescued from a session scratchpad in model#139)
and the PatchTST 43-fold corpus (133 files, 14.8 MB), which could not be located at
all.

WHAT THIS DOES NOT SAY. "Not locatable" is not "fabricated". This programme has a
2026-07-28/29 incident on exactly that distinction, including one occasion where a
REAL corpus was wrongly re-flagged as fake. The audit reports where each file was
looked for and how many were found; it draws no conclusion about why.

Exit codes: 0 every index fully locatable, 1 at least one is not, 2 usage/IO error.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import pathlib
import sys

EXIT_OK, EXIT_UNVERIFIABLE, EXIT_ERROR = 0, 1, 2
SCHEMA = "artifact_corpus_index.v2"


def find_indexes(root: pathlib.Path) -> list[pathlib.Path]:
    out = []
    for pat in ("doc/**/*.json", "docs/**/*.json"):
        for f in glob.glob(str(root / pat), recursive=True):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:                      # noqa: BLE001 - not an index
                continue
            if isinstance(d, dict) and d.get("schema") == SCHEMA:
                out.append(pathlib.Path(f))
    return sorted(out)


def search_roots(index_path: pathlib.Path, extra: list[str] | None = None) -> list[pathlib.Path]:
    """Where a bundle's files may live. Stated explicitly so a nil result is
    interpretable: 'not found' means 'not found HERE', and here is written down."""
    base = index_path.parent
    roots = [base, base / "artifacts"]
    roots += [pathlib.Path(p) for p in (extra or [])]
    return [r for r in roots if r.exists()]


def audit_one(index_path: pathlib.Path, extra: list[str] | None = None) -> dict:
    d = json.load(open(index_path, encoding="utf-8"))
    files = d.get("files") or {}
    roots = search_roots(index_path, extra)
    found, matched, drifted = 0, 0, []
    for rel, meta in files.items():
        hit = next((r / rel for r in roots if (r / rel).exists()), None)
        if hit is None:
            continue
        found += 1
        h = hashlib.sha256(hit.read_bytes()).hexdigest()
        if h == meta.get("sha256"):
            matched += 1
        else:
            drifted.append(rel)
    return {
        "index": str(index_path),
        "n_files": len(files),
        "found": found,
        "digest_matched": matched,
        "drifted": len(drifted),
        "drifted_sample": drifted[:3],
        "searched_roots": [str(r) for r in roots],
        "verifiable": found == len(files) and matched == len(files),
        "root_digest_sha256": d.get("root_digest_sha256"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument("--also-search", action="append", default=[])
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)
    root = pathlib.Path(a.repo)
    if not root.exists():
        print(f"corpus-index-audit: {root} does not exist", file=sys.stderr)
        return EXIT_ERROR
    rows = [audit_one(p, a.also_search) for p in find_indexes(root)]
    if not rows:
        print("corpus-index-audit: no artifact_corpus_index.v2 files found — the scan "
              "has no subjects, which is not the same as a clean repo", file=sys.stderr)
        return EXIT_ERROR
    print(f"{'index':<64}{'n':>5}{'found':>7}{'match':>7}  verifiable")
    for r in rows:
        print(f"{os.path.relpath(r['index'], root)[-62:]:<64}{r['n_files']:>5}"
              f"{r['found']:>7}{r['digest_matched']:>7}  {r['verifiable']}")
    bad = [r for r in rows if not r["verifiable"]]
    if bad:
        print(f"\n{len(bad)} of {len(rows)} index(es) NOT verifiable from this checkout.")
        for r in bad:
            print(f"  {os.path.relpath(r['index'], root)}: {r['found']}/{r['n_files']} "
                  f"files found under {r['searched_roots']}")
        print("\n'Not locatable' is NOT 'fabricated'. This reports where it looked and "
              "what it found; it draws no conclusion about why.")
    if a.json_out:
        json.dump(rows, open(a.json_out, "w", encoding="utf-8"), indent=2, sort_keys=True)
    return EXIT_UNVERIFIABLE if bad else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
