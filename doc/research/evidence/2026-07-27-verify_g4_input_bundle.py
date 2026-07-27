#!/usr/bin/env python3
"""verify_g4_input_bundle v1 — the MANDATORY frozen-input checker of
model#79 (G4 XGB rerun, amendment 1 §2).

Usage:
    python3 verify_g4_input_bundle.py <bundle_dir> <worktree_dir> \
        --frozen-root <64-hex sha256 of MANIFEST.sha256>

Checks, in order (ANY failure => exit 4, printing every mismatch):
  1. sha256(<bundle>/MANIFEST.sha256) == --frozen-root.
  2. Every manifest-listed file exists in <worktree> with a matching
     sha256 (manifest line format: "sha256  size  relpath").
  3. Bidirectional file-set membership inside the covered groups: any
     file present under a covered directory of <worktree> but absent
     from the manifest is a mismatch.
  4. The derived config's digest equals its manifest entry (it is a
     listed file; called out separately for the §1 config row).

Output: one "VOID ..." line per mismatch, then "PREFLIGHT FAILED: N
mismatch(es)" (exit 4); or "VERIFY OK: <n> files verified, membership
clean, root=<digest>" (exit 0). Deterministic; no network; read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

COVERED_GROUPS = [
    "data/ohlcv",
    "data/earnings_surprise",
    "data/news_sentiment_alpaca",
    "backtesting/renquant_104/artifacts/walkforward_gbdt_prod_recipe_v2",
    "backtesting/renquant_104/artifacts/sim/walkforward_calibrators",
    "backtesting/renquant_104/models",
]
DERIVED_CONFIG = ("backtesting/renquant_104/artifacts/diagnostics/"
                  "wf_eval_configs/strategy_config.sim_g4rerun_prod_semantic.json")
META_FILES = {"MANIFEST.sha256", "ROOT_DIGEST"}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle_dir")
    ap.add_argument("worktree_dir")
    ap.add_argument("--frozen-root", required=True)
    args = ap.parse_args()

    manifest_path = os.path.join(args.bundle_dir, "MANIFEST.sha256")
    got_root = sha256_file(manifest_path)
    if got_root != args.frozen_root:
        print(f"VOID root digest: {got_root} != frozen {args.frozen_root}")
        print("PREFLIGHT FAILED: 1 mismatch(es)")
        return 4

    listed: dict[str, str] = {}
    for line in open(manifest_path):
        digest, _size, rel = line.split(None, 2)
        rel = rel.strip()
        if rel.startswith("./"):
            rel = rel[2:]
        if rel in META_FILES:
            continue
        listed[rel] = digest

    bad = 0
    for rel, digest in sorted(listed.items()):
        p = os.path.join(args.worktree_dir, rel)
        if not os.path.exists(p):
            print(f"VOID missing: {rel}")
            bad += 1
            continue
        if sha256_file(p) != digest:
            print(f"VOID digest mismatch: {rel}")
            bad += 1

    for group in COVERED_GROUPS:
        root = os.path.join(args.worktree_dir, group)
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f),
                                      args.worktree_dir)
                if rel not in listed:
                    print(f"VOID extra file not in manifest: {rel}")
                    bad += 1

    if DERIVED_CONFIG not in listed:
        print(f"VOID derived config absent from manifest: {DERIVED_CONFIG}")
        bad += 1

    if bad:
        print(f"PREFLIGHT FAILED: {bad} mismatch(es)")
        return 4
    print(f"VERIFY OK: {len(listed)} files verified, membership clean, "
          f"root={got_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
