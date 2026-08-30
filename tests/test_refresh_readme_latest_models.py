"""Tests for ``scripts/refresh_readme_latest_models.py`` — Track D3.

Pins the README-update behaviour: the script reads ``training_runs`` from a
SQLite DB, renders a Markdown table between marker comments, and preserves
content outside the markers.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


REFRESH = Path(__file__).resolve().parent.parent / "scripts" / "refresh_readme_latest_models.py"


def _make_db(path: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE training_runs (
            run_id TEXT PRIMARY KEY,
            run_date TIMESTAMP NOT NULL,
            strategy TEXT, artifact_type TEXT,
            oos_mean_ic REAL, n_features INTEGER, n_tickers INTEGER,
            device TEXT, elapsed_sec REAL, trigger TEXT, commit_sha TEXT,
            artifact_path TEXT, notes TEXT,
            train_ic REAL, n_rows INTEGER, feature_cols TEXT,
            n_dates INTEGER, deterministic INTEGER, training_window_years REAL,
            config_json TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cols = ("run_id", "run_date", "strategy", "artifact_type", "oos_mean_ic",
            "n_features", "n_tickers", "device", "elapsed_sec", "trigger",
            "commit_sha", "artifact_path", "notes")
    for r in rows:
        conn.execute(
            f"INSERT INTO training_runs ({','.join(cols)}) "
            f"VALUES ({','.join('?'*len(cols))})",
            tuple(r.get(c) for c in cols),
        )
    conn.commit()
    conn.close()


def _run(db: Path, readme: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REFRESH), "--db", str(db), "--readme", str(readme)],
        capture_output=True, text=True, check=True,
    )


def test_refresh_writes_table_between_markers(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [{
        "run_id": "abc123",
        "run_date": "2026-05-30T10:00:00Z",
        "strategy": "renquant_104",
        "artifact_type": "hf_patchtst",
        "oos_mean_ic": 0.018,
        "n_features": 169, "n_tickers": 142,
        "device": "mps", "elapsed_sec": 2040, "trigger": "manual",
        "commit_sha": "feedface",
        "artifact_path": "/x/model.pt",
        "notes": "cut=all seed=42",
    }])
    readme = tmp_path / "README.md"
    readme.write_text("# foo\n\nBefore\n")
    _run(db, readme)
    text = readme.read_text()
    assert "<!-- LATEST_MODELS:START -->" in text
    assert "<!-- LATEST_MODELS:END -->" in text
    assert "abc123" in text
    assert "hf_patchtst" in text
    assert "+0.0180" in text
    assert "169" in text
    assert "mps" in text
    # Preceding content preserved
    assert "Before" in text


def test_refresh_replaces_existing_block(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [{
        "run_id": "new1",
        "run_date": "2026-05-30T10:00:00Z",
        "strategy": "renquant_104", "artifact_type": "panel_ltr_xgboost",
        "oos_mean_ic": 0.045, "n_features": 169,
        "device": "cpu", "elapsed_sec": 65, "trigger": "scheduled_weekly",
        "commit_sha": "00112233",
    }])
    readme = tmp_path / "README.md"
    readme.write_text(
        "# foo\n\nPre\n\n"
        "<!-- LATEST_MODELS:START -->\n"
        "STALE CONTENT TO BE REPLACED\n"
        "<!-- LATEST_MODELS:END -->\n\n"
        "After\n"
    )
    _run(db, readme)
    text = readme.read_text()
    assert "STALE CONTENT" not in text
    assert "new1" in text
    assert "Pre" in text and "After" in text


def test_refresh_no_runs_emits_empty_notice(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [])
    readme = tmp_path / "README.md"
    readme.write_text("# foo\n")
    _run(db, readme)
    text = readme.read_text()
    assert "no training runs recorded yet" in text


def test_refresh_respects_limit_arg(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    rows = [{
        "run_id": f"run{i:02d}",
        "run_date": f"2026-05-{20+i:02d}T10:00:00Z",
        "strategy": "renquant_104", "artifact_type": "hf_patchtst",
        "oos_mean_ic": 0.01 * i, "n_features": 169,
        "device": "mps", "elapsed_sec": 1000, "trigger": "manual",
        "commit_sha": f"sha{i:04d}",
    } for i in range(10)]
    _make_db(db, rows)
    readme = tmp_path / "README.md"
    readme.write_text("# foo\n")
    subprocess.run(
        [sys.executable, str(REFRESH), "--db", str(db),
         "--readme", str(readme), "--limit", "3"],
        check=True, capture_output=True, text=True,
    )
    text = readme.read_text()
    # 3 most recent are run09, run08, run07
    assert "run09" in text and "run08" in text and "run07" in text
    # older runs should NOT appear
    assert "run00" not in text and "run01" not in text


def test_refresh_db_missing_fails(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# foo\n")
    result = subprocess.run(
        [sys.executable, str(REFRESH), "--db", str(tmp_path / "no.db"),
         "--readme", str(readme)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "db not found" in (result.stdout + result.stderr)


# --------------------------------------------------------------------------- #
# Write guard (2026-08-30): a training job must never mutate a pinned runtime
# checkout. The 2026-08-23 run rewrote README.md inside
# `RenQuant/.subrepo_runtime/repos/renquant-model/`, dirtying a running tree.
# --------------------------------------------------------------------------- #
_ROW = {
    "run_id": "guard01",
    "run_date": "2026-08-30T10:00:00Z",
    "strategy": "renquant_104", "artifact_type": "panel_ltr_xgboost",
    "oos_mean_ic": 0.012, "n_features": 169,
    "device": "cpu", "elapsed_sec": 70, "trigger": "scheduled_weekly",
    "commit_sha": "deadbeef",
}
_ORIGINAL = "# foo\n\nUntouched\n"


def _run_noraise(db: Path, readme: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REFRESH), "--db", str(db), "--readme", str(readme), *extra],
        capture_output=True, text=True, check=False,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )


def _init_checkout(repo: Path, *, detached: bool) -> Path:
    """A git checkout holding README.md, committed, on a branch or detached."""
    repo.mkdir(parents=True)
    readme = repo / "README.md"
    readme.write_text(_ORIGINAL)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    if detached:
        _git(repo, "checkout", "-q", "--detach", "HEAD")
    return readme


def test_refuses_under_subrepo_runtime(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [_ROW])
    readme = tmp_path / ".subrepo_runtime" / "repos" / "renquant-model" / "README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text(_ORIGINAL)
    result = _run_noraise(db, readme)
    assert result.returncode == 2, result.stderr
    assert "REFUSED" in result.stderr and ".subrepo_runtime" in result.stderr
    # dry-run fallback: the table is rendered to stdout, nothing is written
    assert "guard01" in result.stdout
    assert readme.read_text() == _ORIGINAL


def test_refuses_in_detached_pinned_checkout(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [_ROW])
    readme = _init_checkout(tmp_path / "pinned", detached=True)
    result = _run_noraise(db, readme)
    assert result.returncode == 2, result.stderr
    assert "detached" in result.stderr
    assert "guard01" in result.stdout
    assert readme.read_text() == _ORIGINAL


def test_writes_in_branch_checkout(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [_ROW])
    readme = _init_checkout(tmp_path / "dev", detached=False)
    result = _run_noraise(db, readme)
    assert result.returncode == 0, result.stderr
    text = readme.read_text()
    assert "guard01" in text and "Untouched" in text


def test_allow_runtime_overrides_refusal(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [_ROW])
    readme = tmp_path / ".subrepo_runtime" / "repos" / "renquant-model" / "README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text(_ORIGINAL)
    result = _run_noraise(db, readme, "--allow-runtime")
    assert result.returncode == 0, result.stderr
    assert "guard01" in readme.read_text()


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [_ROW])
    readme = tmp_path / "README.md"
    readme.write_text(_ORIGINAL)
    result = _run_noraise(db, readme, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "guard01" in result.stdout
    assert "dry-run" in result.stderr
    assert readme.read_text() == _ORIGINAL


def test_dry_run_wins_over_allow_runtime(tmp_path: Path) -> None:
    db = tmp_path / "sim.db"
    _make_db(db, [_ROW])
    readme = _init_checkout(tmp_path / "dev", detached=False)
    result = _run_noraise(db, readme, "--dry-run", "--allow-runtime")
    assert result.returncode == 0, result.stderr
    assert readme.read_text() == _ORIGINAL
