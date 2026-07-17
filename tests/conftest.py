"""Shared, repo-wide test fixtures.

``canonical_run_intent_fixture`` builds a REAL, valid F-7 canonical
run-intent record -- 3 real git checkouts for the canonical code-pin
subrepos (``renquant-strategy-104``/``renquant-pipeline``/``renquant-model``)
+ a matching ``subrepos.lock.json`` + a ``run_intent.json`` written via
``renquant_artifacts.canonical_registry.write_canonical_run_intent`` -- so
tests across both the ``gbdt`` and ``patchtst`` families can declare
``workflow_class=WORKFLOW_CLASS_CANONICAL`` and pass the real,
independently-verifying check
``renquant_model_common.workflow_provenance`` now performs (F-7 round 6,
renquant-model#55). This mirrors the exact real-git-repo technique
renquant-artifacts' own test suite already uses for this same check
(``tests/test_experiment_registry.py::_CanonicalFixture``), generalized into
one reusable pytest fixture here rather than each test file hand-rolling its
own copy of the same non-canonical-role subprocess/git plumbing.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

#: Which subrepo (matching
#: ``renquant_artifacts.canonical_registry.CANONICAL_CODE_PIN_SUBREPOS``)
#: gets a real temp git checkout, and the (fake, never actually pushed to)
#: remote URL declared for it -- same fixture URLs
#: renquant-artifacts' own ``_CanonicalFixture`` uses.
_CANONICAL_REPOS = {
    "renquant-strategy-104": "https://github.com/hallovorld/renquant-strategy-104",
    "renquant-pipeline": "https://github.com/hallovorld/renquant-pipeline",
    "renquant-model": "https://github.com/hallovorld/renquant-model",
}


def _init_repo(path: Path, *, remote: str) -> str:
    """Create a real, single-commit git repo at ``path`` with ``remote`` set
    as its ``origin``, and return the real HEAD commit hash -- the same
    technique ``renquant_artifacts``' own test suite
    (``tests/test_experiment_registry.py::_init_repo``) uses to exercise
    ``verify_code_pin`` against a real checkout rather than a mock.
    """
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=path, check=True)
    return subprocess.check_output(
        ["git", "-C", str(path), "log", "-1", "--format=%H"], text=True,
    ).strip()


@dataclass
class CanonicalRunIntentFixture:
    """Everything a test needs to declare a genuinely-verifiable
    ``workflow_class=WORKFLOW_CLASS_CANONICAL`` claim: a real
    ``run_intent.json`` (``run_intent_path``), the real git checkouts backing
    its code pins, and ``repo_root`` (where ``subrepos.lock.json`` lives, for
    tests that want to call ``verify_canonical_run_intent`` directly)."""

    tmp_path: Path
    repo_root: Path
    run_intent_path: Path
    commits: dict[str, str]


def build_canonical_run_intent_fixture(
    tmp_path: Path, **run_intent_overrides: Any,
) -> CanonicalRunIntentFixture:
    """Build a real ``run_intent.json`` + matching real git checkouts under
    ``tmp_path``. Callers may override any
    ``write_canonical_run_intent`` keyword via ``run_intent_overrides`` (e.g.
    to construct an adversarial/negative scenario -- an unknown producer, a
    stale code pin, etc).

    Deferred import: ``renquant_artifacts.canonical_registry`` only exists on
    the (as of this PR, unmerged) renquant-artifacts#24 branch -- see
    ``renquant_model_common.workflow_provenance``'s module-level NOTE for why
    this repo's own non-test code defers this same import. Deferring it here
    too means a test module that does NOT use this fixture is unaffected if
    the local sibling checkout is ever on main instead.
    """
    from renquant_artifacts import canonical_registry  # noqa: PLC0415

    commits = {
        name: _init_repo(tmp_path / name, remote=remote)
        for name, remote in _CANONICAL_REPOS.items()
    }
    lock = {
        "subrepos": [
            {
                "name": name,
                "local_path": str(tmp_path / name),
                "commit": commits[name],
                "remote": remote,
            }
            for name, remote in _CANONICAL_REPOS.items()
        ]
    }
    (tmp_path / "subrepos.lock.json").write_text(json.dumps(lock))

    code_pins = {
        name: {"commit": commits[name], "remote": remote}
        for name, remote in _CANONICAL_REPOS.items()
    }
    output_dir = tmp_path / "canonical_run_intent_output"
    kwargs: dict[str, Any] = {
        "run_id": "run-fixture-2026-07-16-001",
        "run_type": "daily_full",
        "producer": {
            "repo": "renquant-orchestrator",
            "entrypoint": "daily.TrainGbdtArtifactTask",
        },
        "strategy_manifest_fingerprint": "sha256:strategy",
        "data_manifest_fingerprint": "sha256:data",
        "strategy_config_digest": "sha256:strategyconfig",
        "model_config_digest": "sha256:modelconfig",
        "calendar_universe_digest": "sha256:universe",
        "as_of": "2026-07-16",
        "code_pins": code_pins,
    }
    kwargs.update(run_intent_overrides)
    run_intent_path = canonical_registry.write_canonical_run_intent(output_dir, **kwargs)
    return CanonicalRunIntentFixture(
        tmp_path=tmp_path,
        repo_root=tmp_path,
        run_intent_path=run_intent_path,
        commits=commits,
    )


@pytest.fixture
def canonical_run_intent_fixture(tmp_path: Path) -> CanonicalRunIntentFixture:
    """Pytest fixture wrapping :func:`build_canonical_run_intent_fixture`,
    scoped to its own subdirectory of the test's ``tmp_path`` so it never
    collides with a test's separate use of ``tmp_path`` for the training
    pipeline's own ``output_dir``.
    """
    pytest.importorskip("renquant_artifacts.canonical_registry")
    return build_canonical_run_intent_fixture(tmp_path / "canonical_fixture")
