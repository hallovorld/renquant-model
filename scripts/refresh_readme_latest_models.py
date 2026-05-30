"""Refresh the renquant-model README's "Latest trained models" section.

Reads `data/sim_runs.db::training_runs` (umbrella) for the most recent runs and
rewrites the table between the `<!-- LATEST_MODELS:START -->` /
`<!-- LATEST_MODELS:END -->` markers in README.md.

The training drivers (renquant_orchestrator.train_gbdt, hf_trainer.train_one)
should call this at end of training so the README is always current.

    python scripts/refresh_readme_latest_models.py \\
      --db /path/to/RenQuant/data/sim_runs.db \\
      --readme README.md
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

_START = "<!-- LATEST_MODELS:START -->"
_END = "<!-- LATEST_MODELS:END -->"


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--readme", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args(argv)
    if not a.db.exists():
        raise SystemExit(f"db not found: {a.db}")
    conn = sqlite3.connect(a.db)
    try:
        block = render_table(conn, a.limit)
    finally:
        conn.close()
    patch_readme(a.readme, block)
    print(f"refreshed {a.readme}: {len(block.splitlines())} lines in block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
