"""Refresh the renquant-model README's "Latest trained models" section.

Reads `data/sim_runs.db::training_runs` (umbrella) for the most recent runs and
rewrites the table between the `<!-- LATEST_MODELS:START -->` /
`<!-- LATEST_MODELS:END -->` markers in README.md.

The training drivers (renquant_orchestrator.train_gbdt, hf_trainer.train_one)
call this at end of training so the README is always current.

    python scripts/refresh_readme_latest_models.py \\
      --db /path/to/RenQuant/data/sim_runs.db \\
      --readme README.md

WRITE GUARD (2026-08-30). The 2026-08-23 training run rewrote the README of the
PINNED RUNTIME checkout (`RenQuant/.subrepo_runtime/repos/renquant-model/`),
leaving a dirty tracked file in a running tree for weeks; that single dirty
file made the daily RUN-SURFACE DRIFT scan alarm and the dawn preflight refuse
("pins not aligned" — a dirty-tree refusal). A pinned runtime tree must never
be mutated by a training job, so this script now REFUSES (non-zero exit,
message on stderr, rendered table on stdout as a dry-run) when the target
README

  * lives under a path containing a `.subrepo_runtime` component, or
  * lives inside a git checkout that is NOT on a branch (a detached / pinned
    checkout).

`--allow-runtime` overrides the guard (an operator's explicit choice — never
passed by jobs). `--dry-run` renders the table to stdout and never writes.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_START = "<!-- LATEST_MODELS:START -->"
_END = "<!-- LATEST_MODELS:END -->"

RUNTIME_MARKER = ".subrepo_runtime"
EXIT_REFUSED = 2


def _fmt_ic(x: float | None) -> str:
    return f"{x:+.4f}" if isinstance(x, (int, float)) and x is not None else "—"


def _fmt_sec(x: float | None) -> str:
    if not isinstance(x, (int, float)):
        return "—"
    return f"{x/60:.1f}m" if x >= 60 else f"{x:.1f}s"


def render_table(conn: sqlite3.Connection, limit: int = 8) -> str:
    cur = conn.execute(
        """SELECT run_id, run_date, artifact_type, oos_mean_ic, n_features, n_tickers,
                  device, elapsed_sec, trigger, commit_sha, artifact_path, notes
           FROM training_runs ORDER BY run_date DESC LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()
    if not rows:
        return f"{_START}\n*(no training runs recorded yet)*\n{_END}"
    lines = [
        _START,
        "## Latest trained models",
        "",
        "_Auto-generated from `data/sim_runs.db::training_runs` by "
        "`scripts/refresh_readme_latest_models.py`._",
        "",
        "| run_id | when | family | OOS IC | features | tickers | device | took | trigger | commit |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        rid, when, family, ic, nf, nt, dev, sec, trig, sha, path, notes = r
        lines.append(
            f"| `{rid}` | {when} | {family} | {_fmt_ic(ic)} | {nf or '—'} | {nt or '—'} | "
            f"{dev or '—'} | {_fmt_sec(sec)} | {trig or '—'} | `{(sha or '')[:8]}` |"
        )
    lines += ["", f"_last refreshed: {datetime.utcnow().isoformat()}Z_", _END]
    return "\n".join(lines)


def patch_readme(readme: Path, block: str) -> None:
    text = readme.read_text() if readme.exists() else "# renquant-model\n"
    if _START in text and _END in text:
        head, _, tail = text.partition(_START)
        _, _, tail = tail.partition(_END)
        text = head + block + tail
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    readme.write_text(text)


# --------------------------------------------------------------------------- #
# Write guard
# --------------------------------------------------------------------------- #
def _containing_checkout(start: Path) -> Path | None:
    """Return the nearest ancestor of ``start`` holding a ``.git`` entry.

    ``.git`` may be a directory (primary checkout) or a file (linked worktree);
    both count. ``None`` when ``start`` is not inside any git checkout.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _branch_of(checkout: Path) -> str | None:
    """Return the branch the checkout has HEAD on; ``None`` when detached.

    Raises ``RuntimeError`` when the answer cannot be determined (no ``git``
    binary, or git errors out) — the caller treats that as a refusal, because
    "cannot tell whether this is a pinned tree" must not silently become
    "write it".
    """
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git binary not found; cannot determine checkout state")
    proc = subprocess.run(
        [git, "-C", str(checkout), "symbolic-ref", "-q", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode == 0:
        return proc.stdout.strip() or None
    if proc.returncode == 1 and not proc.stderr.strip():
        # `symbolic-ref -q` exits 1 silently when HEAD is detached.
        return None
    raise RuntimeError(
        f"git symbolic-ref failed in {checkout} (rc={proc.returncode}): "
        f"{proc.stderr.strip()}"
    )


def refusal_reason(readme: Path) -> str | None:
    """Why writing ``readme`` must be refused, or ``None`` when it is safe.

    Refuses when the README lives under a ``.subrepo_runtime`` path component
    (the umbrella's pinned runtime checkouts) or inside a git checkout whose
    HEAD is detached (a pinned checkout is never on a branch). A README that
    is not inside any git checkout at all (e.g. a scratch directory) is not a
    pinned tree and is allowed.
    """
    absolute = readme.absolute()
    resolved = absolute.resolve()
    for path in (absolute, resolved):
        if RUNTIME_MARKER in path.parts:
            return (
                f"{readme} lives under a pinned runtime checkout "
                f"(path contains '{RUNTIME_MARKER}')"
            )
    checkout = _containing_checkout(resolved.parent)
    if checkout is None:
        return None
    try:
        branch = _branch_of(checkout)
    except RuntimeError as exc:
        return f"cannot determine whether {checkout} is a pinned checkout: {exc}"
    if branch is None:
        return (
            f"{readme} lives in {checkout}, a detached (pinned) checkout that is "
            f"not on a branch"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--readme", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Render the table to stdout; never write the README.",
    )
    ap.add_argument(
        "--allow-runtime", action="store_true",
        help="Write even when the README lives in a pinned runtime / detached "
             "checkout. Operator use only — training jobs never pass this.",
    )
    a = ap.parse_args(argv)
    if not a.db.exists():
        raise SystemExit(f"db not found: {a.db}")
    conn = sqlite3.connect(a.db)
    try:
        block = render_table(conn, a.limit)
    finally:
        conn.close()

    if a.dry_run:
        print(block)
        print(f"dry-run: {a.readme} not written ({len(block.splitlines())} lines rendered)",
              file=sys.stderr)
        return 0

    reason = None if a.allow_runtime else refusal_reason(a.readme)
    if reason is not None:
        print(block)
        print(
            f"REFUSED to write {a.readme}: {reason}. A training job must never "
            f"mutate a pinned tree; the rendered table was printed to stdout "
            f"instead (dry-run). Pass --allow-runtime to override deliberately.",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    patch_readme(a.readme, block)
    print(f"refreshed {a.readme}: {len(block.splitlines())} lines in block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
