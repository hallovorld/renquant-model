#!/usr/bin/env python3
"""Pin the RAW OHLCV inputs the total-return builders read, not just their
two derived parquets.

`tools/momentum_total_return_run.py` already sha256-pins
`total_return_close.parquet` and `momentum_factor_matrix_tr.parquet`, but a
pin on a DERIVED file only proves that file didn't change — it says nothing
about the raw `data/ohlcv/<T>/1d.parquet` files (the 145-name watchlist,
which already contains SPY as one of the 145) or the watchlist config that
produced it. If the umbrella corpus is edited later and someone reruns the
two builders, they get a fresh derived-file hash that either matches (by
luck, or because nothing relevant changed) or mismatches (and nobody can
tell whether that is a REAL corpus change or a builder bug) -- there was no
committed record of what the raw layer looked like when the pinned derived
files were built.

This tool builds that record, reusing the existing content-addressed corpus
index (`tools/corpus_index.py`) rather than re-implementing hashing: it
copies each ticker's `1d.parquet` into a `<ticker>/1d.parquet` mirror tree
(~16 MB total), then indexes that tree.

    # build + commit the manifest (run once, when the raw layer is trusted)
    python tools/raw_input_manifest.py generate --out <path>

    # before building from raw OHLCV: confirm nothing has moved underneath
    python tools/raw_input_manifest.py verify --manifest <path>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
CORPUS_INDEX = TOOLS_DIR / "corpus_index.py"

LIVE = Path("/Users/renhao/git/github/RenQuant")
OHLCV = LIVE / "data" / "ohlcv"
CFG = (LIVE / ".subrepo_runtime" / "repos" / "renquant-strategy-104"
       / "configs" / "strategy_config.json")
BENCH = "SPY"

# The pin both build_total_return_series.py and build_tr_factor_matrix.py
# verify against before touching the raw corpus. Committed once via
# `generate`; regenerated deliberately when the corpus is intentionally
# refreshed.
MOMENTUM_TOTAL_RETURN_PIN = (
    TOOLS_DIR.parent / "doc" / "research" / "data"
    / "2026-07-30-momentum-total-return" / "raw_input_manifest.json")

SCHEMA = "raw_input_manifest.v1"


def _watchlist() -> list[str]:
    return list(json.loads(CFG.read_text())["watchlist"])


def _universe() -> list[str]:
    wl = _watchlist()
    return wl + [BENCH] if BENCH not in wl else list(wl)


def _mirror_and_index(universe: list[str]) -> dict:
    """Copy each ticker's 1d.parquet into `<ticker>/1d.parquet` under a scratch
    root, then delegate hashing/digesting to `corpus_index.py` so there is
    exactly one implementation of the canonical digest construction. A copy
    (not a hardlink) because the scratch root and the umbrella corpus are not
    guaranteed to be on the same filesystem/volume; the universe is ~16 MB
    total, so the extra I/O is negligible.
    """
    missing = [t for t in universe if not (OHLCV / t / "1d.parquet").exists()]
    if missing:
        raise SystemExit(
            f"ABORT: {len(missing)} universe ticker(s) missing "
            f"data/ohlcv/<T>/1d.parquet: {missing}")
    with tempfile.TemporaryDirectory(prefix="raw_input_manifest_") as td:
        mirror = Path(td) / "ohlcv"
        for t in universe:
            dest_dir = mirror / t
            dest_dir.mkdir(parents=True)
            shutil.copyfile(OHLCV / t / "1d.parquet", dest_dir / "1d.parquet")
        idx_path = Path(td) / "corpus_index.json"
        r = subprocess.run(
            [sys.executable, str(CORPUS_INDEX), "generate",
             "--root", str(mirror), "--out", str(idx_path)],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"ABORT: corpus_index.py generate failed:\n{r.stderr}")
        return json.loads(idx_path.read_text())


def build_manifest() -> dict:
    watchlist = _watchlist()
    universe = _universe()
    config_sha256 = hashlib.sha256(CFG.read_bytes()).hexdigest()
    corpus_index = _mirror_and_index(universe)
    return {
        "schema": SCHEMA,
        "config": {
            "path": str(CFG.relative_to(LIVE)),
            "sha256": config_sha256,
        },
        "universe": {
            "watchlist_n": len(watchlist),
            "bench": BENCH,
            "n": len(universe),
        },
        "raw_source_root": str(OHLCV.relative_to(LIVE)) + "/<ticker>/1d.parquet",
        "corpus_index": corpus_index,
    }


def cmd_generate(args) -> int:
    manifest = build_manifest()
    text = json.dumps(manifest, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}: {manifest['universe']['n']} raw inputs, "
              f"corpus_fingerprint="
              f"{manifest['corpus_index']['root_digest_sha256']}, "
              f"config_sha256={manifest['config']['sha256'][:16]}…")
    else:
        print(text)
    return 0


def _diff(committed: dict, actual: dict) -> list[str]:
    problems: list[str] = []
    cc = committed.get("config", {}).get("sha256")
    ac = actual["config"]["sha256"]
    if cc != ac:
        problems.append(
            f"watchlist config changed: manifest pins {cc}, actual is {ac}")
    cf = committed.get("corpus_index", {}).get("root_digest_sha256")
    af = actual["corpus_index"]["root_digest_sha256"]
    if cf != af:
        problems.append(
            f"raw OHLCV corpus fingerprint changed: manifest pins {cf}, "
            f"actual is {af}")
    return problems


def cmd_verify(args) -> int:
    committed = json.loads(Path(args.manifest).read_text())
    actual = build_manifest()
    problems = _diff(committed, actual)
    if problems:
        print(f"VERIFY FAILED ({len(problems)} problem(s)):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"VERIFY OK: {actual['universe']['n']} raw inputs, "
          f"corpus_fingerprint={actual['corpus_index']['root_digest_sha256']}, "
          f"config_sha256={actual['config']['sha256'][:16]}…")
    return 0


def verify_or_abort(manifest_path: Path, *, allow_missing: bool = False) -> None:
    """For builder scripts to call before touching the raw OHLCV corpus.

    ABORTS when the pin is missing or unreadable, not just when it mismatches.

    An earlier version printed a `[NOTE]` and RETURNED on a missing manifest,
    on a bootstrap rationale: the pin does not exist until `generate` has been
    run and committed once. That rationale expired the moment the pin was
    committed (it is in this repo at ``MOMENTUM_TOTAL_RETURN_PIN``), and it
    left a function named ``verify_or_abort`` doing neither on its most
    important failure mode -- a builder producing output with NO provenance at
    all, which is a strictly worse state than a mismatch and the one the
    repository rule against continuing without fingerprints exists to forbid.

    A malformed manifest aborts for the same reason: unparseable is unverified.

    ``allow_missing=True`` is the genuine bootstrap escape -- a caller
    generating the very first pin. It must be passed EXPLICITLY, so skipping
    the check is a visible decision at the call site rather than the default.
    """
    if not manifest_path.exists():
        if allow_missing:
            print(f"[BOOTSTRAP] no raw-input manifest at {manifest_path}; "
                  f"proceeding because the caller passed allow_missing=True.")
            return
        raise SystemExit(
            f"ABORT: no committed raw-input manifest at {manifest_path}. A "
            f"builder must not touch the raw OHLCV corpus without a pin -- "
            f"output with no provenance is worse than output that fails a "
            f"pin check, because nothing downstream can tell it apart from "
            f"verified output. Generate and COMMIT the pin first:\n"
            f"  python tools/raw_input_manifest.py generate --out {manifest_path}\n"
            f"If you are genuinely bootstrapping the first pin, call "
            f"verify_or_abort(..., allow_missing=True) explicitly.")
    try:
        committed = json.loads(manifest_path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(
            f"ABORT: raw-input manifest at {manifest_path} could not be read "
            f"or parsed ({exc}). An unreadable pin is an UNVERIFIED pin; it "
            f"must not be treated as absent-and-therefore-fine.") from exc
    actual = build_manifest()
    problems = _diff(committed, actual)
    if problems:
        raise SystemExit(
            "ABORT: raw input layer changed since the pinned manifest was "
            f"committed ({manifest_path}):\n  - " + "\n  - ".join(problems) +
            f"\nIf this is an intentional corpus refresh, regenerate the "
            f"pin: python tools/raw_input_manifest.py generate --out "
            f"{manifest_path}")
    print(f"RAW INPUT PIN OK  "
          f"corpus_fingerprint="
          f"{actual['corpus_index']['root_digest_sha256'][:16]}…  "
          f"config_sha256={actual['config']['sha256'][:16]}…")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--out", default=None)
    g.set_defaults(func=cmd_generate)
    v = sub.add_parser("verify")
    v.add_argument("--manifest", required=True)
    v.set_defaults(func=cmd_verify)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
