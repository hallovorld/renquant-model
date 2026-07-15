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

## Honestly-disclosed residual limitation (canonical side)

Once the negative check above passes (no experiment marker found at
``output_dir``), ``workflow_class=WORKFLOW_CLASS_CANONICAL`` still results in
the bare, self-declared ``provenance = {"kind": "none"}`` -- there is
currently NO existing "canonical production run" non-forgeable POSITIVE
evidence mechanism anywhere in this multirepo (a signed attestation, a
canonical producer identity, immutable WF-gate evidence bound at manifest-
build time) to independently verify a genuine canonical claim against. This
was investigated, not assumed:

* No environment variable, config flag, or CLI switch already distinguishes
  "canonical production training" from "research/experimental" in
  ``renquant_model_gbdt`` / ``renquant_model_patchtst`` today.
* ``renquant-orchestrator``'s ``run_bundle.json`` (``PersistDailyRunBundleTask``
  in ``daily.py``) is the closest existing "non-forgeable run identity"
  concept in this multirepo, but it is built AFTER the artifact manifest
  already exists, using the manifest as one of its own input fields --
  it cannot be the identity bound INTO the manifest at manifest-build time
  without a circular dependency (the run bundle doesn't exist yet when
  ``BuildArtifactManifestTask`` runs).
* ``experiments/ensemble_phase0/admissibility_ledger.py`` and
  ``experiment_manifest.py`` build real per-run evidence ledgers, but those
  are scoped to that one ensemble feature, not a repo-wide
  "canonical-vs-experiment" contract this task could bind to generically.

This is the SAME residual-trust status this codebase's other self-declared
manifest fields already carry (``code_commit``, ``config_fingerprint``), and
matches the honesty standard the round-3 fix set for its own opaque
``store://``/``object://`` URI residual limit (see
``renquant_artifacts.experiment_registry._verify_none_provenance``'s
docstring). Round 4 closed the literal "hardcoded regardless of context" bug
and made the canonical declaration an explicit, auditable, per-call-site act
rather than an unconditional default; round 5 (this fix) additionally closes
the negative case Codex demanded proof of -- a caller cannot claim
``"canonical"`` for a directory that is ALREADY a real, registered experiment
run. Neither round achieves full cryptographic non-forgeability for the
POSITIVE canonical case (proving an artifact genuinely IS a canonical
production run, as opposed to merely proving it is NOT a known experiment). A
future PR wanting that needs a NEW mechanism (e.g. a signed attestation bound
at training time from a specific, restricted canonical entrypoint) that does
not exist anywhere in this codebase today.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# NOTE: renquant_artifacts.experiment_registry is imported LAZILY, inside
# _verified_experiment_provenance() and _reject_canonical_over_experiment_marker()
# below, not at module top level. It only exists on the (as of this PR,
# unmerged) renquant-artifacts#24 branch -- main does not have it yet. A
# top-level import here would make a bare ``import renquant_model_gbdt`` /
# ``import renquant_model_patchtst`` raise ModuleNotFoundError in any
# environment still pinned to renquant-artifacts main, i.e. break EVERY
# canonical-path caller too, not just experiment-path ones. Deferring the
# import until the relevant path actually runs matches this repo's existing
# convention for optional/not-yet-universal dependencies (see the deferred,
# lint-suppressed imports throughout ``renquant_model_patchtst`` for
# torch/transformers).

#: An artifact built by a genuine, non-experiment, canonical production
#: training invocation. Results in ``provenance = {"kind": "none"}`` -- see
#: this module's docstring for the honestly-disclosed residual limitation
#: (self-declared, not independently verified).
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
) -> dict[str, Any]:
    """Build a manifest's ``provenance`` record from an explicit, verified
    workflow-classification signal -- never a hardcoded default.

    Raises ``ValueError`` if ``workflow_class`` is not a recognized value, if
    ``workflow_class=WORKFLOW_CLASS_CANONICAL`` is declared for an
    ``output_dir`` that a real, on-disk experiment-registry marker proves is
    ALREADY a registered experiment run (round 5, Codex P0 -- see this
    module's docstring), or if ``workflow_class=WORKFLOW_CLASS_EXPERIMENT``
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
        return {"kind": "none"}
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
