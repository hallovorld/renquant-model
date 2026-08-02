"""Append-only, digest-chained momentum artifact ledger. (GOAL-7 slice 2)

Mirrors the Job B depth-extension manifest idiom (renquant-model,
doc/research/data/2026-08-02-jobb-gbdt-depth-extension-run001): identity lives
in digests, ordering is explicit, and history is never rewritten. Here the
chain is per-row: each JSONL row carries ``prev_row_sha`` (the previous row's
``row_sha``) and its own ``row_sha`` over the canonical row body, so ANY edit
of an already-written row breaks every later link and is detected before any
append.

Refusals (all ``LedgerIntegrityError``):
- appending to a ledger whose existing rows fail chain/self-digest checks
  (someone rewrote history — refuse-and-investigate, never repair silently);
- appending a second row for the same (cutoff_date, params_version) — one
  training run per cutoff per params version; a re-run that disagrees is a
  dispute to investigate, not a row to overwrite;
- appending an artifact whose self-carried content_sha256 does not recompute.

There is deliberately NO rewrite/compact/delete API in this module.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from renquant_model_momentum.train import verify_artifact_content_sha

__all__ = ["LedgerIntegrityError", "append_to_artifact_ledger",
           "load_and_verify_ledger", "row_sha256_of"]


class LedgerIntegrityError(RuntimeError):
    """The ledger's append-only / chain contract is violated."""


#: Fields every row must carry (beyond these, rows may add context fields).
_ROW_REQUIRED = ("row_index", "prev_row_sha", "appended_at_utc", "kind",
                 "cutoff_date", "params_version", "artifact_content_sha256",
                 "row_sha")


def row_sha256_of(row: Mapping[str, Any]) -> str:
    """sha256 over the canonical JSON of the row WITHOUT row_sha."""
    body = {k: v for k, v in row.items() if k != "row_sha"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"),
                       allow_nan=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def load_and_verify_ledger(ledger_path: str | Path) -> list[dict]:
    """Parse + verify the full chain; raise LedgerIntegrityError on ANY defect.

    A missing file is an empty ledger (first append creates it)."""
    path = Path(ledger_path)
    if not path.exists():
        return []
    rows: list[dict] = []
    prev_sha: str | None = None
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                raise LedgerIntegrityError(f"row {i}: blank line in ledger")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerIntegrityError(f"row {i}: unparseable ({exc})")
            missing = [k for k in _ROW_REQUIRED if k not in row]
            if missing:
                raise LedgerIntegrityError(f"row {i}: missing fields {missing}")
            if row["row_index"] != i:
                raise LedgerIntegrityError(
                    f"row {i}: row_index says {row['row_index']} — rows were "
                    "reordered or removed")
            if row["prev_row_sha"] != prev_sha:
                raise LedgerIntegrityError(
                    f"row {i}: prev_row_sha {row['prev_row_sha']!r} does not "
                    f"match the previous row's row_sha {prev_sha!r} — the "
                    "chain is broken (a row was rewritten or removed)")
            actual = row_sha256_of(row)
            if row["row_sha"] != actual:
                raise LedgerIntegrityError(
                    f"row {i}: row_sha {row['row_sha']!r} does not recompute "
                    f"({actual}) — the row was edited after it was written")
            prev_sha = row["row_sha"]
            rows.append(row)
    return rows


def append_to_artifact_ledger(artifact: Mapping[str, Any],
                              ledger_path: str | Path) -> dict:
    """Append ONE artifact's row; returns the appended row.

    The whole existing ledger is verified first — a tampered ledger refuses
    the append instead of extending a broken chain. The file is only ever
    opened in append mode; existing bytes are never touched."""
    try:
        verify_artifact_content_sha(artifact)
    except ValueError as exc:
        raise LedgerIntegrityError(f"refusing to ledger the artifact: {exc}")
    for key in ("kind", "cutoff_date", "params"):
        if key not in artifact:
            raise LedgerIntegrityError(f"artifact missing {key!r}")
    params_version = artifact["params"].get("params_version")
    if not params_version:
        raise LedgerIntegrityError("artifact params carry no params_version")

    path = Path(ledger_path)
    rows = load_and_verify_ledger(path)
    for r in rows:
        if (r["cutoff_date"] == artifact["cutoff_date"]
                and r["params_version"] == params_version):
            raise LedgerIntegrityError(
                f"a row for cutoff_date={artifact['cutoff_date']} "
                f"params_version={params_version} already exists (row "
                f"{r['row_index']}, artifact "
                f"{r['artifact_content_sha256'][:12]}…) — append-only means "
                "this run is a dispute to investigate, never a rewrite")

    row: dict[str, Any] = {
        "row_index": len(rows),
        "prev_row_sha": rows[-1]["row_sha"] if rows else None,
        "appended_at_utc": _dt.datetime.now(_dt.timezone.utc)
                              .isoformat(timespec="seconds"),
        "kind": artifact["kind"],
        "cutoff_date": artifact["cutoff_date"],
        "effective_train_cutoff_date": artifact.get(
            "effective_train_cutoff_date"),
        "cutoff_embargo_days": artifact.get("cutoff_embargo_days"),
        "params_version": params_version,
        "artifact_content_sha256": artifact["content_sha256"],
        "n_scored": artifact.get("n_scored"),
        "names_floor_ok": artifact.get("names_floor_ok"),
        "read_digests": dict(artifact.get("inputs", {})
                             .get("read_digests", {})),
    }
    row["row_sha"] = row_sha256_of(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                            allow_nan=False) + "\n")
    return row
