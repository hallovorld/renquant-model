"""model#74 review round 7: `build_manifest()` fails closed (RuntimeError)
whenever `_prereg_freeze()` cannot resolve full git history for the prereg
file — correct for production runs, but it also trips inside CI's real
(non-mocked) manifest tests, which exercise this repo's own live prereg
history against whatever checkout depth CI happens to use.

CI's `actions/checkout@v4` step defaults to a shallow (depth-1) clone, and
this agent's PAT deliberately lacks the `workflow` scope needed to push an
edit to `.github/workflows/ci.yml` (doc/ops/agent-token-storage.md lists
Workflows R&W as opt-in only). Rather than reach for a broader-scoped
credential to bypass that restriction, unshallow the repo here at test
collection time — same effect as `fetch-depth: 0` on the checkout step,
achieved from test-side setup instead of the protected workflow file.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_DIR = Path(__file__).resolve().parents[2]


def _is_shallow(repo_dir: Path) -> bool:
    proc = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=repo_dir,
                          capture_output=True, text=True)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


@pytest.fixture(scope="session", autouse=True)
def _unshallow_repo_for_prereg_freeze_tests():
    if _is_shallow(_REPO_DIR):
        subprocess.run(["git", "fetch", "--unshallow", "origin"], cwd=_REPO_DIR, check=True)
