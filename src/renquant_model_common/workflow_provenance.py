"""Verified workflow-classification -> artifact-manifest ``provenance`` record.

Both ``renquant_model_gbdt.pipelines.BuildArtifactManifestTask`` and
``renquant_model_patchtst.pipelines.BuildPatchTstArtifactManifestTask`` build a
candidate artifact manifest's REQUIRED ``provenance`` field by calling
:func:`build_verified_provenance` here -- ONE shared implementation, not two
independently hand-copied ones. Families share cross-family logic only through
this package (see ``tests/patchtst/test_import_boundaries.py``); this is
exactly the same "triple-impl" lesson ``renquant_artifacts.experiment_registry``
already documents (three independently hand-copied ``model_content_sha256``
implementations silently diverged before the fix consolidated them into one
shared function).

## Why this module exists (Codex review, 2026-07-14, renquant-model PR #55)

Round 3 of the F-7 provenance chain closed one bypass:
``renquant_artifacts.experiment_registry._verify_none_provenance`` now
independently re-checks a ``kind="none"`` declaration against any real,
pre-existing ``_experiment_classification.json`` marker sitting at the
artifact's own on-disk path. Codex's round-3 follow-up review found a DEEPER
gap that fix did not close:

    "These are generic training entry points; an exploratory or
    registered-experiment invocation can write to a fresh path with no prior
    EXPLORATORY_ONLY marker, so the proposed path lookup cannot distinguish it
    from canonical production. The producer is therefore self-classifying an
    experiment artifact as `none`, precisely the bypass the gate must
    prevent."

``BuildArtifactManifestTask`` / ``BuildPatchTstArtifactManifestTask`` were
hardcoding ``provenance = {"kind": "none"}`` unconditionally, with zero regard
for which context (genuine canonical production vs. a registered
exploratory/experiment run writing to a brand-new path) the code was actually
running in. A registered experiment's fresh output directory has no
pre-existing marker for the round-3 on-disk check to find, so it slipped
through as "none" -- the producer was self-classifying, not reporting a
verified fact.

## The fix: an explicit, caller-declared, independently-verified signal

Investigated first whether this codebase already has a "canonical production
training run" concept to bind to (a scheduled-job flag, a signed run-bundle
digest, a WF-gate-evidence contract produced at canonical-training time) --
see the residual limitation below for what was found. Absent that, the fix
here is narrower than a full cryptographic binding, but it DOES remove the
literal bug Codex flagged (hardcoded regardless of context):

* The caller of ``TrainingContext`` / ``PatchTstTrainingContext`` MUST pass an
  explicit ``workflow_class`` -- :data:`WORKFLOW_CLASS_CANONICAL` or
  :data:`WORKFLOW_CLASS_EXPERIMENT` -- as a REQUIRED constructor argument with
  NO default value. There is no code path where a manifest is built without an
  explicit, auditable, per-invocation declaration. Every call site in this
  repo was grepped and updated (see the PR description for the full list);
  the one known EXTERNAL call site
  (``renquant-orchestrator``'s ``daily.py::TrainGbdtArtifactTask``, which
  constructs ``TrainingContext`` directly for the real daily production
  retrain) is a disclosed, NOT-YET-DONE follow-up -- it will raise
  ``TypeError`` (missing required argument) until that repo is updated in a
  coordinated follow-up PR, exactly the same sequencing this F-7 chain has
  already used for breaking cross-repo changes.
* ``workflow_class=WORKFLOW_CLASS_EXPERIMENT`` is NOT trusted at face value.
  This module independently verifies it by reusing the REAL,
  already-built experiment-registry machinery from
  ``renquant_artifacts.experiment_registry`` (the same module round 3 built
  for the promotion-boundary side) rather than re-implementing verification
  logic a second time:

  1. ``model_config["experiment_registry_index_path"]`` must point at the
     real, git-tracked, immutable manifest-registry index.
  2. A real ``_experiment_classification.json`` marker
     (``renquant_artifacts.experiment_registry.CLASSIFICATION_FILENAME``) must
     actually exist at ``output_dir`` -- written by the registered-experiment
     harness via ``write_experiment_classification()`` BEFORE this task runs.
     A bare declaration with no marker on disk is rejected, not trusted.
  3. The marker's own ``manifest_digest`` / ``experiment_id`` are
     cross-checked against the immutable registry index via
     :func:`renquant_artifacts.experiment_registry.verify_manifest_registered`
     -- the same tamper-resistant check
     ``reject_exploratory_promotion`` uses on the promotion-boundary side.
  4. Only once all three checks pass does this build the real
     ``provenance = {"kind": "experiment", "dir": ..., "registry_index_path": ...}``
     record via
     :func:`renquant_artifacts.experiment_registry.build_experiment_provenance_reference`
     -- never a caller-supplied dict taken on faith.

  This is the adversarial scenario Codex explicitly asked to be proven: run
  the SAME producer under a registered-experiment context at a FRESH path
  with no pre-existing marker for the round-3 on-disk check to find, and
  confirm the manifest now correctly reports ``kind="experiment"``, not
  ``"none"``. See ``tests/gbdt/test_workflow_class_provenance.py`` /
  ``tests/patchtst/test_workflow_class_provenance.py``.

## Round 5 fix: the canonical-side bypass (Codex P0, 2026-07-14)

Round 4 (above) closed the gap for an honest ``workflow_class="experiment"``
caller, but Codex's round-5 review found the exact caller-controlled bypass
still open on the OTHER side of the same ``if``:

    "workflow_class='canonical' remains the exact caller-controlled bypass.
    build_verified_provenance() returns {'kind':'none'} immediately for that
    value, with no verification. [...] Add the required negative integration
    test: create a real registered experiment at a fresh output path, give it
    workflow_class='canonical' instead of the honest value, and prove the
    system does not accept it as canonical/none."

i.e. nothing stopped a caller from taking a directory that IS a real,
registered experiment run (real ``_experiment_classification.json`` marker,
real ``INDEX.json``/registry entry) and simply passing the string
``"canonical"`` instead of ``"experiment"`` -- ``build_verified_provenance``
would return ``{"kind": "none"}`` without even looking at ``output_dir``.

The fix, :func:`_reject_canonical_over_experiment_marker`, closes this the
same way ``renquant_artifacts.experiment_registry._verify_none_provenance``
already closes the analogous gap for a ``kind="none"`` manifest declaration
(same module, read its docstring): before honoring
``workflow_class=WORKFLOW_CLASS_CANONICAL``, independently check ``output_dir``
for a real, on-disk ``_experiment_classification.json`` marker and, if one is
found, reuse the SAME shared enforcement function the experiment path already
depends on -- ``renquant_artifacts.experiment_registry.reject_exploratory_promotion``
-- to reject the "canonical" claim outright, rather than hand-rolling a
fourth copy of "does a marker exist" logic (the same triple-impl lesson this
module's own header already cites). This is a NEGATIVE-only check ("this is
not a known experiment") -- see ``tests/gbdt/test_workflow_class_provenance.py::
test_canonical_declaration_over_registered_experiment_marker_is_rejected`` (and
its PatchTST twin) for the exact adversarial scenario Codex described, proven
end to end against the real, non-mocked producer.

## Round 6: positive canonical verification (F-7 step 2/4, renquant-model#55)

Round 5 (above) closed the NEGATIVE case (a caller cannot relabel a known
experiment as "canonical"), but honestly disclosed that the POSITIVE case --
proving an artifact genuinely IS a canonical production run, not merely that
it is not a known experiment -- had no verification mechanism at all:
``workflow_class=WORKFLOW_CLASS_CANONICAL`` still fell through to the bare,
self-declared ``provenance = {"kind": "none"}``.

This is now closed using the trust anchor
:mod:`renquant_artifacts.canonical_registry` (renquant-artifacts#24, F-7 step
1/4) built for exactly this purpose: a canonical run-intent record
(``run_intent.json``), written atomically by a narrow, code-reviewed
producer entrypoint in ``renquant-orchestrator`` BEFORE training starts (step
3/4 of this chain -- NOT written by this repo, which only consumes/verifies
it), whose own evidence (code pins for the 3 canonical subrepos, a producer
allowlist) is independently re-verifiable against the actual environment.

``workflow_class=WORKFLOW_CLASS_CANONICAL`` now additionally requires, and
verifies, two more things before returning a provenance record:

1. ``artifact_digest`` -- the trained artifact's own content fingerprint --
   is now a REQUIRED parameter of :func:`build_verified_provenance`. It
   cannot be computed inside this module (the artifact file may not be fully
   written yet at the time this function runs); the caller (``BuildArtifactManifestTask``
   / ``BuildPatchTstArtifactManifestTask`` in ``pipelines.py``) threads it
   through from the SAME ``fingerprint`` value the manifest itself already
   uses -- one fingerprint computation, not two independently derived ones
   (the same triple-impl lesson this module's header already cites).
2. ``model_config["canonical_run_intent_path"]`` -- the path to the
   ``run_intent.json`` record the orchestrator wrote before training started.
   This module verifies it against the actual environment via
   :func:`renquant_artifacts.canonical_registry.verify_canonical_run_intent`
   (code pins for ``renquant-strategy-104``/``renquant-pipeline``/
   ``renquant-model`` re-checked against the real current checkouts, plus the
   producer allowlist) and raises ``ValueError`` with the full error list on
   any failure -- a bare declaration with no verifiable record is rejected,
   not trusted, mirroring the same standard the experiment path already
   holds itself to.

Only once both checks pass does this return the real
``provenance = {"kind": "canonical", "run_intent_path": ..., "run_intent_digest":
..., "artifact_digest": ...}`` record via
:func:`renquant_artifacts.canonical_registry.build_canonical_provenance_reference`
-- never a caller-supplied dict taken on faith, and never the old bare
``{"kind": "none"}``.

### Deriving ``repo_root`` for the code-pin check

:func:`renquant_artifacts.canonical_registry.verify_canonical_run_intent`
needs a ``repo_root`` to locate ``subrepos.lock.json`` (this repo has no
independent notion of the umbrella repo root -- it only knows
``output_dir``/``model_config``). Rather than inventing a THIRD required
``model_config`` key for this, this module reuses
:data:`renquant_artifacts.canonical_registry.MAX_REPO_ROOT_SEARCH_LEVELS` --
a bound that module's own docstring already documents as existing "when
auto-deriving a repo_root for a supplemental local verification" -- to walk
bounded-upward from ``canonical_run_intent_path`` looking for
``subrepos.lock.json``, exactly the idiom
``renquant_artifacts.experiment_registry._find_repo_root_with_subrepos_lock``
already uses internally for its own best-effort canonical re-check. That
helper is private to a module this PR does not touch (renquant-artifacts#24
already landed and was independently verified), so it cannot be imported
directly; :func:`_derive_canonical_repo_root` below is a narrow, documented,
intentional duplicate of that same bounded-walk shape rather than a
divergent reimplementation -- see that function's docstring.

## Honestly-disclosed residual limitation (canonical side)

The POSITIVE gap flagged through round 5 is now closed: a genuine canonical
claim is independently verified against a real run-intent record's code pins
and producer identity, not merely self-declared. What remains self-declared,
same status as this codebase's other self-declared manifest fields
(``code_commit``, ``config_fingerprint``): the run-intent record's own
content fields (``strategy_manifest_fingerprint``, ``data_manifest_fingerprint``,
``strategy_config_digest``, ``model_config_digest``, ``calendar_universe_digest``,
``as_of``) are trusted as written by the orchestrator producer, not
independently recomputed here -- verification covers code identity (pins +
producer allowlist) and the binding to THIS artifact
(``artifact_digest == manifest["fingerprint"]``, enforced downstream in
:func:`renquant_artifacts.experiment_registry.verify_artifact_provenance`),
not a full re-derivation of every declared digest from source data. This
matches the honesty standard the round-3 fix set for its own opaque
``store://``/``object://`` URI residual limit (see
``renquant_artifacts.experiment_registry._verify_none_provenance``'s
docstring).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# NOTE: renquant_artifacts.experiment_registry / renquant_artifacts.canonical_registry
# are imported LAZILY, inside _verified_experiment_provenance(),
# _reject_canonical_over_experiment_marker(), and _verified_canonical_provenance()
# below, not at module top level. They only exist on the (as of this PR,
# unmerged) renquant-artifacts#24 branch -- main does not have them yet. A
# top-level import here would make a bare ``import renquant_model_gbdt`` /
# ``import renquant_model_patchtst`` raise ModuleNotFoundError in any
# environment still pinned to renquant-artifacts main, i.e. break EVERY
# canonical-path caller too, not just experiment-path ones. Deferring the
# import until the relevant path actually runs matches this repo's existing
# convention for optional/not-yet-universal dependencies (see the deferred,
# lint-suppressed imports throughout ``renquant_model_patchtst`` for
# torch/transformers).

#: An artifact built by a genuine, non-experiment, canonical production
#: training invocation. Independently verified (round 6) against a real
#: run-intent record's code pins + producer allowlist, and bound to this
#: artifact's own content digest, before ``provenance = {"kind": "canonical",
#: ...}`` is built -- see :func:`build_verified_provenance` and this module's
#: docstring for the full contract and its honestly-disclosed residual
#: limitation.
WORKFLOW_CLASS_CANONICAL = "canonical"

#: An artifact built as part of a registered exploratory/experiment run.
#: Independently verified against the real experiment-registry marker +
#: immutable registration index before ``provenance = {"kind": "experiment",
#: ...}`` is built -- see :func:`build_verified_provenance`.
WORKFLOW_CLASS_EXPERIMENT = "experiment"

WORKFLOW_CLASSES = frozenset({WORKFLOW_CLASS_CANONICAL, WORKFLOW_CLASS_EXPERIMENT})


def build_verified_provenance(
    workflow_class: str,
    *,
    output_dir: Path | str,
    model_config: dict[str, Any],
    artifact_digest: str | None = None,
) -> dict[str, Any]:
    """Build a manifest's ``provenance`` record from an explicit, verified
    workflow-classification signal -- never a hardcoded default.

    ``artifact_digest`` is the trained artifact's own content fingerprint
    (the SAME value the caller already computes for the manifest's own
    ``fingerprint`` field -- see ``pipelines.py``'s ``BuildArtifactManifestTask``
    / ``BuildPatchTstArtifactManifestTask``). It is required (round 6) when
    ``workflow_class=WORKFLOW_CLASS_CANONICAL``; unused otherwise.

    Raises ``ValueError`` if ``workflow_class`` is not a recognized value, if
    ``workflow_class=WORKFLOW_CLASS_CANONICAL`` is declared for an
    ``output_dir`` that a real, on-disk experiment-registry marker proves is
    ALREADY a registered experiment run (round 5, Codex P0 -- see this
    module's docstring), if a canonical declaration is missing
    ``artifact_digest`` or ``model_config["canonical_run_intent_path"]``, if
    that run-intent record fails independent verification (round 6 -- see
    this module's docstring), or if ``workflow_class=WORKFLOW_CLASS_EXPERIMENT``
    cannot be independently verified against the real experiment-registry
    machinery (missing registry index reference, missing on-disk
    classification marker, or a marker whose digest is not actually
    registered).
    """
    if workflow_class not in WORKFLOW_CLASSES:
        raise ValueError(
            f"workflow_class must be one of {sorted(WORKFLOW_CLASSES)}, got "
            f"{workflow_class!r} -- every artifact-manifest build must "
            "declare an explicit, auditable workflow classification; there "
            "is no default (Codex review 2026-07-14: 'the producer is "
            "self-classifying an experiment artifact as none, precisely the "
            "bypass the gate must prevent')"
        )
    if workflow_class == WORKFLOW_CLASS_CANONICAL:
        _reject_canonical_over_experiment_marker(output_dir, model_config)
        return _verified_canonical_provenance(model_config, artifact_digest)
    return _verified_experiment_provenance(output_dir, model_config)


def _reject_canonical_over_experiment_marker(
    output_dir: Path | str, model_config: dict[str, Any],
) -> None:
    """Reject ``workflow_class=WORKFLOW_CLASS_CANONICAL`` when ``output_dir``
    is provably ALREADY a registered experiment run.

    Round 5, Codex P0 (quoted in full in this module's docstring):
    ``workflow_class="canonical"`` used to return ``{"kind": "none"}``
    immediately, with zero regard for ``output_dir`` -- the exact
    caller-controlled bypass Codex asked to be closed. This is the
    negative-only counterpart to :func:`_verified_experiment_provenance`:
    it does not (and cannot, absent a non-forgeable "genuine canonical run"
    attestation -- see the module docstring's honestly-disclosed residual
    limitation) prove ``output_dir`` truly IS a canonical production run. It
    DOES prove ``output_dir`` is NOT a directory a registered-experiment
    harness has already claimed via a real, on-disk
    ``_experiment_classification.json`` marker
    (``renquant_artifacts.experiment_registry.CLASSIFICATION_FILENAME``)
    written by ``write_experiment_classification()`` -- reusing, rather than
    re-implementing, the SAME shared enforcement function
    (``reject_exploratory_promotion``) the experiment path and
    ``renquant_artifacts.experiment_registry._verify_none_provenance`` (the
    existing "kind=none" bypass check this mirrors) already depend on.
    """
    # Deferred import -- see the module-level NOTE above.
    from renquant_artifacts.experiment_registry import (  # noqa: PLC0415
        CLASSIFICATION_FILENAME,
        reject_exploratory_promotion,
    )

    marker_path = Path(output_dir) / CLASSIFICATION_FILENAME
    if not marker_path.exists():
        # No marker at this exact path -- nothing on disk contradicts the
        # "canonical" claim. This is the same residual limit as the "none"
        # path's own on-disk check: an opaque/not-yet-created output_dir
        # gives this check nothing to inspect, so it passes (see the
        # module's honestly-disclosed residual limitation).
        return
    try:
        registry_index_path = model_config.get("experiment_registry_index_path")
        reject_exploratory_promotion(
            output_dir, registry_index_path=registry_index_path,
        )
    except ValueError as exc:
        raise ValueError(
            f"workflow_class='canonical' declared for output_dir="
            f"{output_dir!r}, but a real experiment-registry classification "
            f"marker ({marker_path}) already exists there -- this directory "
            "is a REGISTERED EXPERIMENT run, not a canonical production run "
            "(Codex review 2026-07-14: 'workflow_class=\"canonical\" "
            "remains the exact caller-controlled bypass ... prove the "
            "system does not accept it as canonical/none'). A caller cannot "
            "relabel a known experiment as canonical by changing the "
            "workflow_class string."
        ) from exc
    # reject_exploratory_promotion did not raise: the marker exists but does
    # not itself prove exploratory/registered origin (e.g. a legacy/hand-
    # edited marker with no self-reported EXPLORATORY_ONLY classification
    # and no registry_index_path to cross-check against). Fail closed rather
    # than silently trusting an ambiguous marker either way.
    raise ValueError(
        f"workflow_class='canonical' declared for output_dir={output_dir!r}, "
        f"but an experiment-registry classification marker ({marker_path}) "
        "exists there whose provenance could not be resolved either way -- "
        "ambiguous provenance at a path carrying a real classification "
        "marker is rejected, not accepted, for a canonical claim"
    )


def _derive_canonical_repo_root(run_intent_path: Path) -> Path:
    """Bounded upward walk from ``run_intent_path`` looking for
    ``subrepos.lock.json``, to auto-derive the ``repo_root``
    :func:`renquant_artifacts.canonical_registry.verify_canonical_run_intent`
    needs for its code-pin checks.

    This repo has no independent notion of the umbrella repo root -- it only
    knows ``output_dir``/``model_config`` -- so rather than inventing a THIRD
    required ``model_config`` key on top of ``canonical_run_intent_path`` and
    ``artifact_digest``, this reuses
    :data:`renquant_artifacts.canonical_registry.MAX_REPO_ROOT_SEARCH_LEVELS`,
    a bound that module's own docstring already documents as existing "when
    auto-deriving a repo_root for a supplemental local verification".

    This is a narrow, DOCUMENTED duplicate of the identical bounded-walk shape
    ``renquant_artifacts.experiment_registry._find_repo_root_with_subrepos_lock``
    already implements for its own (private, module-internal) best-effort
    canonical re-check -- not a divergent reimplementation. It cannot be
    imported directly: it is private to a module renquant-artifacts#24
    already landed and was independently verified, which this PR does not
    touch. If no ``subrepos.lock.json`` is found within the bound, this
    returns ``run_intent_path``'s immediate parent directory anyway, so
    :func:`renquant_artifacts.canonical_registry.verify_canonical_run_intent`'s
    own "subrepos.lock.json not found" error (rather than a second,
    differently worded error invented here) is what surfaces to the caller --
    this function itself never silently swallows the not-found case.
    """
    # Deferred import -- see the module-level NOTE above.
    from renquant_artifacts import canonical_registry  # noqa: PLC0415

    start = run_intent_path.resolve().parent
    current = start
    for _ in range(canonical_registry.MAX_REPO_ROOT_SEARCH_LEVELS):
        if (current / "subrepos.lock.json").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return start


def _verified_canonical_provenance(
    model_config: dict[str, Any], artifact_digest: str | None,
) -> dict[str, Any]:
    """Round 6: independently verify a ``workflow_class=WORKFLOW_CLASS_CANONICAL``
    declaration against a real canonical run-intent record, rather than
    returning the old bare, self-declared ``{"kind": "none"}`` -- see this
    module's docstring for the full rationale.
    """
    # Deferred import -- see the module-level NOTE above.
    from renquant_artifacts import canonical_registry  # noqa: PLC0415

    if not artifact_digest:
        raise ValueError(
            "workflow_class='canonical' requires artifact_digest (the "
            "trained artifact's own content fingerprint, e.g. "
            "ctx.model_artifact['fingerprint']) so the provenance record is "
            "bound to THIS artifact rather than merely asserted -- see "
            "build_verified_provenance's artifact_digest parameter"
        )
    run_intent_path = model_config.get("canonical_run_intent_path")
    if not run_intent_path:
        raise ValueError(
            "workflow_class='canonical' requires "
            "model_config['canonical_run_intent_path'] -- the path to the "
            "run_intent.json record the orchestrator must write BEFORE "
            "training starts (renquant_artifacts.canonical_registry."
            "write_canonical_run_intent) -- so the canonical claim can be "
            "independently verified, not merely trusted. This repo does not "
            "write that record itself, it only consumes/verifies it."
        )
    run_intent_path = Path(run_intent_path)
    repo_root = _derive_canonical_repo_root(run_intent_path)
    errors = canonical_registry.verify_canonical_run_intent(
        run_intent_path, repo_root=repo_root,
    )
    if errors:
        raise ValueError(
            f"workflow_class='canonical' declared but the run-intent record "
            f"at {run_intent_path} failed verification against the actual "
            f"environment: {errors}"
        )
    return canonical_registry.build_canonical_provenance_reference(
        run_intent_path, artifact_digest,
    )


def _verified_experiment_provenance(
    output_dir: Path | str, model_config: dict[str, Any],
) -> dict[str, Any]:
    # Deferred import -- see the module-level NOTE above.
    from renquant_artifacts.experiment_registry import (  # noqa: PLC0415
        CLASSIFICATION_FILENAME,
        build_experiment_provenance_reference,
        verify_manifest_registered,
    )

    registry_index_path = model_config.get("experiment_registry_index_path")
    if not registry_index_path:
        raise ValueError(
            "workflow_class='experiment' requires "
            "model_config['experiment_registry_index_path'] (the immutable, "
            "git-tracked manifest-registry index) so the declared "
            "classification can be independently verified, not merely "
            "trusted"
        )
    marker_path = Path(output_dir) / CLASSIFICATION_FILENAME
    if not marker_path.exists():
        raise ValueError(
            f"workflow_class='experiment' declared but no "
            f"{CLASSIFICATION_FILENAME} marker exists at {marker_path} -- "
            "the registered-experiment harness must call "
            "renquant_artifacts.experiment_registry."
            "write_experiment_classification() before this task runs; a "
            "bare declaration with no on-disk marker is not verifiable and "
            "is rejected, not trusted"
        )
    record = json.loads(marker_path.read_text())
    manifest_digest = record.get("manifest_digest")
    experiment_id = record.get("experiment_id")
    if not manifest_digest or not experiment_id:
        raise ValueError(
            f"classification marker at {marker_path} is missing "
            "manifest_digest/experiment_id -- cannot verify registration"
        )
    registration_errors = verify_manifest_registered(
        manifest_digest, experiment_id, registry_index_path,
    )
    if registration_errors:
        raise ValueError(
            f"workflow_class='experiment' declared for "
            f"experiment_id={experiment_id!r} but registration could not be "
            f"verified against {registry_index_path}: {registration_errors}"
        )
    return build_experiment_provenance_reference(output_dir, registry_index_path)
