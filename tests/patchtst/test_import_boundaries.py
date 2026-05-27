"""Import-boundary tests for the PatchTST family.

Two checks:
- The PatchTST package, imported in a fresh subprocess, must not pull
  execution / GBDT-family runtime. A subprocess is used so the result is
  not polluted by other tests in the same pytest session that legitimately
  import renquant_model_gbdt (test isolation per RFC §5.13.1).
- An AST scan asserts the PatchTST source never imports the GBDT family or
  execution/broker code. Families share only through
  renquant_model_common / renquant_common; they must not import each other.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PATCHTST_SRC = (
    Path(__file__).parent.parent.parent / "src" / "renquant_model_patchtst"
)

FORBIDDEN_ROOT_IMPORTS = (
    "alpaca",
    "ib_insync",
    "live",
    "renquant_execution",
    "renquant_model_gbdt",
    "renquant_pipeline",
    "renquant_backtesting",
)


def test_patchtst_fresh_import_does_not_pull_execution_or_gbdt() -> None:
    """Fresh-subprocess runtime check — isolation-proof."""
    code = (
        "import importlib, sys\n"
        "importlib.import_module('renquant_model_patchtst')\n"
        f"forbidden = {FORBIDDEN_ROOT_IMPORTS!r}\n"
        "bad = sorted(n for n in sys.modules "
        "if n in forbidden or n.startswith(forbidden))\n"
        "assert bad == [], bad\n"
    )
    src_paths = [
        str(PATCHTST_SRC.parent),
        str(PATCHTST_SRC.parent.parent.parent / "renquant-common" / "src"),
        str(PATCHTST_SRC.parent.parent.parent / "renquant-base-data" / "src"),
        str(PATCHTST_SRC.parent.parent.parent / "renquant-artifacts" / "src"),
    ]
    env_pythonpath = ":".join(src_paths)
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={"PYTHONPATH": env_pythonpath, "PATH": ""},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"patchtst fresh import pulled forbidden modules: {result.stderr}"
    )


def _root(module_name: str) -> str:
    return module_name.split(".", 1)[0]


def _collect_imports(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(_root(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.level == 0:
                roots.add(_root(node.module))
    return roots


def test_patchtst_source_does_not_import_gbdt_or_execution() -> None:
    offenders: list[tuple[Path, str]] = []
    for py in PATCHTST_SRC.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        bad = _collect_imports(tree) & set(FORBIDDEN_ROOT_IMPORTS)
        for root in sorted(bad):
            offenders.append((py.relative_to(PATCHTST_SRC), root))
    assert offenders == [], (
        f"patchtst source imports forbidden families: {offenders}. Share "
        f"via renquant_model_common / renquant_common only."
    )
