"""Production regime-label plane, consumed BY PATH (orch#985 ranked item 1).

The renquant-orchestrator #985 memo measured four regime label planes at
25-70% same-day agreement; the consolidation target is the PRODUCTION
task-chain plane (the one the WF gate's ``sanity_regime_ic`` leg replays).
renquant-model may not import that chain: the boundary tests forbid
``renquant_pipeline`` and ``renquant_backtesting`` imports in the model
families (tests/patchtst/test_import_boundaries.py;
tests/test_model_common_import.py; codex round-2 on model#65). Production
labels therefore arrive as DATA — the committed corpus published by
renquant-backtesting ``tools/publish_production_regime_labels.py`` — the
same producer/consumer pattern as the frozen fold-provenance vectors
(tests/test_build_phase_a_inputs.py).

Env contract (mirrors ``renquant_backtesting.analysis.regime_plane``;
duplicated here because importing it is exactly what the boundary forbids):

* ``RENQUANT_REGIME_PLANE`` — ``production`` (default) or
  ``legacy_stateless`` (reproduce results keyed to the historical
  ``renquant_common.hmm_regime_labels`` stateless approximation).
* ``RENQUANT_REGIME_LABELS_PATH`` — corpus file override. Default: the
  sibling-checkout path
  ``../renquant-backtesting/doc/research/data/production_regime_labels.csv``
  (the same sibling layout the Makefile uses for renquant-common etc.).

Fail-closed: on the production plane a missing corpus surfaces as a loud
error/empty diagnostics — never a silent fallback to another plane.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

REGIME_PLANE_ENV = "RENQUANT_REGIME_PLANE"
REGIME_LABELS_PATH_ENV = "RENQUANT_REGIME_LABELS_PATH"
PLANE_PRODUCTION = "production"
PLANE_LEGACY_STATELESS = "legacy_stateless"
VALID_PLANES = (PLANE_PRODUCTION, PLANE_LEGACY_STATELESS)

#: Corpus location inside a renquant-backtesting checkout.
CORPUS_RELPATH = Path("doc/research/data/production_regime_labels.csv")


def resolve_regime_plane(environ: Any | None = None) -> str:
    """Resolve the active regime label plane (fail-closed on typos)."""
    env = os.environ if environ is None else environ
    raw = str(env.get(REGIME_PLANE_ENV, PLANE_PRODUCTION) or PLANE_PRODUCTION)
    if raw not in VALID_PLANES:
        raise ValueError(
            f"{REGIME_PLANE_ENV}={raw!r} is not a valid regime plane; "
            f"expected one of {VALID_PLANES}"
        )
    return raw


def default_corpus_path() -> Path:
    """Sibling-checkout default: ``../renquant-backtesting/<relpath>``."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root.parent / "renquant-backtesting" / CORPUS_RELPATH


def resolve_corpus_path(environ: Any | None = None) -> Path:
    env = os.environ if environ is None else environ
    override = env.get(REGIME_LABELS_PATH_ENV)
    return Path(override).expanduser() if override else default_corpus_path()


def corpus_manifest_path(corpus_path: Path) -> Path:
    return corpus_path.with_suffix("").with_suffix(".manifest.json") \
        if corpus_path.suffix == ".csv" else corpus_path.parent / (
            corpus_path.name + ".manifest.json")


def load_corpus_manifest(corpus_path: Path | None = None) -> dict | None:
    """Provenance sidecar of the corpus (series sha, chain identity) or None."""
    p = corpus_manifest_path(corpus_path or resolve_corpus_path())
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def load_production_regime_labels(path: Path | None = None) -> pd.DataFrame:
    """Load the production-plane per-date label series (date parsed).

    Raises FileNotFoundError with the remediation options when the corpus
    is absent — the caller decides whether that is fatal (contract gates)
    or degrades to empty diagnostics (per-regime IC logging).
    """
    p = path or resolve_corpus_path()
    if not p.exists():
        raise FileNotFoundError(
            f"production regime label corpus missing at {p}; either check "
            f"out renquant-backtesting as a sibling (corpus is committed at "
            f"{CORPUS_RELPATH}), point {REGIME_LABELS_PATH_ENV} at a copy, "
            f"or set {REGIME_PLANE_ENV}={PLANE_LEGACY_STATELESS} to "
            f"reproduce legacy stateless-plane results"
        )
    df = pd.read_csv(p)
    if "date" not in df.columns or "regime" not in df.columns:
        raise ValueError(
            f"corpus at {p} lacks required date/regime columns: "
            f"{sorted(df.columns)}"
        )
    df["date"] = pd.to_datetime(df["date"])
    return df


def corpus_identity(path: Path | None = None) -> dict:
    """Stampable identity of the corpus actually consumed."""
    p = path or resolve_corpus_path()
    out: dict[str, Any] = {"corpus_path": str(p)}
    if p.exists():
        out["corpus_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = load_corpus_manifest(p)
    if manifest:
        out["manifest_series_sha256"] = manifest.get("series_sha256")
        out["manifest_generated_on"] = manifest.get("generated_on")
        out["chain"] = manifest.get("chain")
    return out
