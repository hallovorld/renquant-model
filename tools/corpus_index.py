#!/usr/bin/env python3
"""Generate and VERIFY a content-addressed index of an artifact corpus.

An index whose only evidence is an asserted hash is not a reference — a
reviewer cannot recompute it, and once the producing session's scratch
directory disappears the identified bytes are unreachable. This tool exists so
a corpus claim is falsifiable by anyone with the bytes:

    # regenerate from a corpus root
    python tools/corpus_index.py generate --root <dir> --out index.json

    # verify a committed index against a corpus root (exit 1 on ANY mismatch)
    python tools/corpus_index.py verify --root <dir> --index index.json

CANONICAL DIGEST — the exact construction, so it is reproducible without
reading this implementation:

  1. Walk `root` recursively. For every REGULAR file, compute its SHA-256 over
     the raw bytes, and its path RELATIVE to `root` using POSIX separators.
  2. Build one line per file: ``f"{relpath}:{sha256_hex}"`` (no spaces).
  3. Sort those lines with Python's default lexicographic byte ordering
     (``sorted()`` over ``str``), ascending.
  4. Join with a single ``"\\n"`` — no trailing newline.
  5. ``root_digest = sha256(joined.encode("utf-8")).hexdigest()``.

Directories contribute nothing of their own; an empty directory is invisible
to the digest, which is intentional — it carries no bytes. Symlinks are NOT
followed and are recorded as a hard error, because a corpus whose contents
depend on link targets outside the root is not self-contained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

SCHEMA = "artifact_corpus_index.v2"
_CHUNK = 1 << 20


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def walk_files(root: str) -> list[str]:
    """Relative POSIX paths of every regular file under `root`, unsorted."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                raise SystemExit(
                    f"ERROR: symlink in corpus: {full}. A corpus whose bytes "
                    f"depend on targets outside the root is not self-contained."
                )
            if not os.path.isfile(full):
                continue
            out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return out


def build_index(root: str) -> dict:
    rels = walk_files(root)
    files = {rel: {"sha256": sha256_file(os.path.join(root, rel)),
                   "bytes": os.path.getsize(os.path.join(root, rel))}
             for rel in rels}
    lines = sorted(f"{rel}:{meta['sha256']}" for rel, meta in files.items())
    root_digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return {
        "schema": SCHEMA,
        "digest_construction": {
            "line_format": "{relpath}:{sha256_hex}",
            "path_separator": "/",
            "sort": "python sorted() over the line strings, ascending",
            "join": "\\n (single newline, no trailing newline)",
            "hash": "sha256 of the utf-8 encoded joined string",
            "symlinks": "rejected",
            "directories": "contribute nothing",
        },
        "root_digest_sha256": root_digest,
        "n_files": len(files),
        "total_bytes": sum(m["bytes"] for m in files.values()),
        "files": files,
    }


def cmd_generate(args) -> int:
    idx = build_index(args.root)
    text = json.dumps(idx, indent=1, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {args.out}: {idx['n_files']} files, "
              f"root_digest {idx['root_digest_sha256']}")
    else:
        print(text)
    return 0


def cmd_verify(args) -> int:
    with open(args.index, encoding="utf-8") as f:
        committed = json.load(f)
    actual = build_index(args.root)

    problems: list[str] = []
    if committed.get("root_digest_sha256") != actual["root_digest_sha256"]:
        problems.append(
            f"root digest mismatch: index says "
            f"{committed.get('root_digest_sha256')}, corpus computes "
            f"{actual['root_digest_sha256']}")

    cf, af = committed.get("files", {}), actual["files"]
    for rel in sorted(set(cf) - set(af)):
        problems.append(f"missing from corpus: {rel}")
    for rel in sorted(set(af) - set(cf)):
        problems.append(f"present in corpus but not in index: {rel}")
    for rel in sorted(set(cf) & set(af)):
        if cf[rel]["sha256"] != af[rel]["sha256"]:
            problems.append(f"content differs: {rel}")

    if problems:
        print(f"VERIFY FAILED ({len(problems)} problem(s)):", file=sys.stderr)
        for p in problems[:40]:
            print(f"  - {p}", file=sys.stderr)
        if len(problems) > 40:
            print(f"  … and {len(problems) - 40} more", file=sys.stderr)
        return 1
    print(f"VERIFY OK: {actual['n_files']} files, "
          f"{actual['total_bytes']} bytes, root_digest "
          f"{actual['root_digest_sha256']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--root", required=True)
    g.add_argument("--out", default=None); g.set_defaults(func=cmd_generate)
    v = sub.add_parser("verify"); v.add_argument("--root", required=True)
    v.add_argument("--index", required=True); v.set_defaults(func=cmd_verify)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
