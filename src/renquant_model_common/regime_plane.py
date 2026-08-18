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
error/empty diagnostics — never a silent fallback to another plane. The
loader also enforces the provenance contract the publisher exposes: the
corpus is trusted only together with a valid manifest sidecar whose
``series_sha256`` equals SHA-256 of the exact CSV bytes, and only when the
series itself is well-formed (unique monotonic dates, labels drawn from the
closed :class:`~renquant_common.contracts.regime.RegimeLabel` taxonomy).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from renquant_common.contracts.regime import RegimeLabel

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


def _require_manifest(corpus_path: Path) -> dict:
    """Strict manifest load — missing/malformed sidecar is a ValueError.

    The lenient :func:`load_corpus_manifest` (None on any problem) stays for
    identity STAMPING; consuming the corpus requires this strict path.
    """
    p = corpus_manifest_path(corpus_path)
    if not p.exists():
        raise ValueError(
            f"provenance manifest missing at {p}; the production corpus is "
            f"trusted only together with its publisher sidecar — regenerate "
            f"both via renquant-backtesting "
            f"tools/publish_production_regime_labels.py"
        )
    try:
        manifest = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"provenance manifest unreadable at {p}: {exc}"
        ) from exc
    sha = manifest.get("series_sha256") if isinstance(manifest, dict) else None
    if not isinstance(sha, str) or not sha:
        raise ValueError(
            f"provenance manifest at {p} lacks a series_sha256 string; "
            f"malformed sidecar — re-publish the corpus"
        )
    return manifest


def _verify_series_hash(corpus_path: Path, raw: bytes) -> None:
    """SHA-256(CSV bytes) must equal the manifest's series_sha256."""
    expected = _require_manifest(corpus_path)["series_sha256"]
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError(
            f"corpus at {corpus_path} fails provenance verification: "
            f"sha256(csv)={actual} != manifest series_sha256={expected} — "
            f"stale or tampered corpus; re-publish via renquant-backtesting "
            f"tools/publish_production_regime_labels.py"
        )


def _validate_series(corpus_path: Path, df: pd.DataFrame) -> None:
    """Reject invalid planes: null/unknown labels, duplicate/unsorted dates."""
    regimes = df["regime"]
    if regimes.isna().any():
        raise ValueError(
            f"corpus at {corpus_path} contains "
            f"{int(regimes.isna().sum())} null regime labels"
        )
    unknown = sorted(set(regimes.unique()) - set(RegimeLabel.values()))
    if unknown:
        raise ValueError(
            f"corpus at {corpus_path} contains unknown regime labels "
            f"{unknown}; valid: {sorted(RegimeLabel.values())}"
        )
    dates = df["date"]
    if dates.duplicated().any():
        dups = dates[dates.duplicated()].dt.strftime("%Y-%m-%d").unique()
        raise ValueError(
            f"corpus at {corpus_path} contains duplicate dates "
            f"(e.g. {list(dups[:3])})"
        )
    if not dates.is_monotonic_increasing:
        raise ValueError(
            f"corpus at {corpus_path} dates are not monotonically increasing"
        )


def load_production_regime_labels(path: Path | None = None) -> pd.DataFrame:
    """Load the production-plane per-date label series (date parsed).

    Fail-closed provenance contract (codex review on model#228): a valid
    manifest sidecar is REQUIRED and SHA-256 of the exact CSV bytes must
    equal its ``series_sha256`` BEFORE parsing — a stale or tampered corpus
    must not run under the recorded production chain identity. The parsed
    series must have unique, monotonically increasing dates and labels from
    the closed :class:`RegimeLabel` taxonomy. Missing corpus raises
    FileNotFoundError with the remediation options; every provenance or
    validity failure raises ValueError. The caller decides whether that is
    fatal (contract gates) or degrades to empty diagnostics (per-regime IC
    logging) — never a silent fallback to another plane.
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
    raw = p.read_bytes()
    _verify_series_hash(p, raw)
    df = pd.read_csv(io.BytesIO(raw))
    if "date" not in df.columns or "regime" not in df.columns:
        raise ValueError(
            f"corpus at {p} lacks required date/regime columns: "
            f"{sorted(df.columns)}"
        )
    df["date"] = pd.to_datetime(df["date"])
    _validate_series(p, df)
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
