"""F-7 round 4: verified workflow-classification -> manifest provenance.

Codex review 2026-07-14 on PR #55 (quoted in full in
``renquant_model_common.workflow_provenance``'s module docstring) found that
``BuildArtifactManifestTask`` hardcoded ``provenance = {"kind": "none"}``
unconditionally, regardless of whether the invocation was genuine canonical
production training or part of a registered exploratory/experiment run
writing to a brand-new path with no pre-existing classification marker for
the round-3 on-disk check to find -- "the producer is therefore
self-classifying an experiment artifact as none, precisely the bypass the
gate must prevent."

This file proves the fix with the EXACT adversarial scenario Codex asked for:
run the SAME real producer (``BuildArtifactManifestTask`` via
``PanelGbdtTrainingPipeline``, not a mock) under a genuinely registered
experiment context, writing to a FRESH path, and prove it does NOT get
``"none"`` -- it must correctly detect and honestly report ``"experiment"``.
It also proves the guard rails around that: an "experiment" declaration with
no registry index reference, or no on-disk marker, is rejected rather than
trusted; and an unrecognized ``workflow_class`` is rejected too.

The positive control -- genuine canonical publication still succeeds and
still gets ``kind="none"`` -- lives in ``test_training_pipeline.py`` (it
already asserted this for the round-3 fix; F-7 round 4 only changed HOW that
"none" is derived, from a hardcoded default to an explicit
``workflow_class=WORKFLOW_CLASS_CANONICAL`` declaration).

## Round 5: the canonical-side bypass (Codex P0, 2026-07-14)

``test_canonical_declaration_over_registered_experiment_marker_is_rejected``
below proves the round-5 P0 Codex flagged on this same PR: ``workflow_class=
"canonical"`` used to return ``{"kind": "none"}`` unconditionally, with ZERO
regard for ``output_dir`` -- so a caller could take a directory that IS a
real, registered experiment run and simply pass ``"canonical"`` instead of
the honest ``"experiment"`` value to get an unverified pass. This is the
literal negative integration test Codex demanded: "create a real registered
experiment at a fresh output path, give it workflow_class='canonical'
instead of the honest value, and prove the system does not accept it as
canonical/none."
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from renquant_model_gbdt import (
    WORKFLOW_CLASS_CANONICAL,
    WORKFLOW_CLASS_EXPERIMENT,
    PanelGbdtTrainingPipeline,
    TrainingContext,
)

# renquant_artifacts.experiment_registry only exists on the (as of this PR,
# unmerged) renquant-artifacts#24 branch -- skip these tests, rather than
# hard-erroring the whole collection, when the local sibling checkout is
# still on main. Same idiom this repo already uses for torch/transformers
# (see tests/patchtst/test_training_wiring.py).
experiment_registry = pytest.importorskip("renquant_artifacts.experiment_registry")
write_experiment_classification = experiment_registry.write_experiment_classification


def _dataset_manifest() -> dict:
    return {
        "dataset_id": "alpha158_fund_fixture",
        "fingerprint": "sha256:test",
        "schema_version": "fixture-v1",
        "uri": "object://renquant-data/alpha158_fund_fixture.parquet",
        "asset_class": "equity",
    }


def _loader(manifest: dict):
    return {"rows": [1, 2, 3], "manifest": manifest}


def _trainer(dataset, config: dict, output_dir: Path):
    return {
        "artifact_id": "gbdt-workflow-class-fixture",
        "model_family": "gbdt-panel-ltr",
        "fingerprint": "sha256:model",
        "uri": "object://renquant-artifacts/gbdt-workflow-class-fixture.json",
        "promotion_status": "candidate",
        "feature_cols": ["alpha_1", "alpha_2"],
        "local_artifact_path": str(output_dir / "gbdt-workflow-class-fixture.json"),
        "trained_date": "2026-05-25",
        "config_fingerprint": "sha256:config",
        "panel_shape": {"rows": 1000, "cols": 2},
        "lookahead_days": 5,
        "train_run_id": "run-workflow-class",
        "oos_mean_ic": 0.031,
        "oos_std_ic": 0.012,
        "oos_per_fold_ic": [0.02, 0.04, 0.033],
        "cv_method": "purged-walk-forward",
        "cv_embargo_days": 5,
    }, {"kind": "global_calibrator"}


def _validator(artifact: dict, dataset, config: dict):
    return {"oos_mean_ic": 0.031, "train_ic": 0.154}


def _write_registry_index(path: Path, *, experiment_id: str, manifest_digest: str) -> None:
    path.write_text(json.dumps({
        experiment_id: {"digest": manifest_digest, "path": "irrelevant/for/this/test.json"},
    }))


# ---------------------------------------------------------------------------
# workflow_class is a required, no-default, auditable declaration
# ---------------------------------------------------------------------------


def test_workflow_class_has_no_default_and_is_required(tmp_path: Path) -> None:
    """TrainingContext must not silently default workflow_class -- this is
    the literal bug Codex flagged: a caller must make an explicit,
    per-invocation, auditable declaration.
    """
    with pytest.raises(TypeError):
        TrainingContext(  # type: ignore[call-arg]
            dataset_manifest=_dataset_manifest(),
            model_config={},
            output_dir=tmp_path / "out",
        )


def test_invalid_workflow_class_is_rejected(tmp_path: Path) -> None:
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"strategy": "renquant_104"},
        output_dir=tmp_path / "out",
        workflow_class="bogus",
    )

    with pytest.raises(ValueError, match="workflow_class must be one of"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


# ---------------------------------------------------------------------------
# workflow_class="experiment" is independently verified, never trusted
# ---------------------------------------------------------------------------


def test_experiment_declaration_without_registry_index_path_is_rejected(tmp_path: Path) -> None:
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"strategy": "renquant_104"},  # no experiment_registry_index_path
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="experiment_registry_index_path"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


def test_experiment_declaration_without_on_disk_marker_is_rejected(tmp_path: Path) -> None:
    """A bare workflow_class='experiment' claim with no real marker on disk
    must be rejected, not trusted -- this is the "independently verify, not
    just trust" requirement.
    """
    output_dir = tmp_path / "out"
    registry_index_path = tmp_path / "registry_index.json"
    _write_registry_index(registry_index_path, experiment_id="exp-x", manifest_digest="sha256:x")

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="no.*marker exists"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


def test_experiment_declaration_with_unregistered_marker_is_rejected(tmp_path: Path) -> None:
    """A real on-disk marker whose digest is NOT in the immutable registry
    index must also be rejected -- the marker's self-reported content alone
    is not sufficient, it must cross-check against the immutable index.
    """
    output_dir = tmp_path / "out"
    registry_index_path = tmp_path / "registry_index.json"
    # Index registers a DIFFERENT experiment than the one the marker claims.
    _write_registry_index(registry_index_path, experiment_id="some-other-exp", manifest_digest="sha256:other")

    write_experiment_classification(
        output_dir,
        experiment_id="exp-not-registered",
        manifest_path="irrelevant.json",
        manifest_digest="sha256:not-registered",
        config_digest="sha256:cfg",
    )

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="registration could not be verified"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)


# ---------------------------------------------------------------------------
# THE adversarial integration test Codex asked for
# ---------------------------------------------------------------------------


def test_registered_experiment_at_fresh_path_is_never_none(tmp_path: Path) -> None:
    """Adversarial integration test (Codex, 2026-07-14): execute the SAME
    model producer (the real ``BuildArtifactManifestTask``, via
    ``PanelGbdtTrainingPipeline`` -- not a mock) under a registered
    experiment context at a FRESH artifact path, and prove it cannot obtain
    canonical/none classification.

    The path is genuinely fresh: nothing else has ever written to
    ``output_dir`` before this test's own
    ``write_experiment_classification()`` call, mirroring exactly the gap
    Codex described -- "an exploratory or registered-experiment invocation
    can write to a fresh path with no prior EXPLORATORY_ONLY marker."

    Two things are proven together:

    1. The manifest built by ``BuildArtifactManifestTask`` correctly reports
       ``provenance == {"kind": "experiment", ...}`` -- NOT the old
       unconditional ``{"kind": "none"}`` bug -- verified via the real,
       non-mocked ``renquant_artifacts.experiment_registry`` machinery
       (on-disk marker + immutable registry-index cross-check).
    2. That correctly-classified manifest is THEN unconditionally rejected
       by the real, non-mocked registry-side promotion gate
       (``validate_artifact_manifest`` ->
       ``verify_artifact_provenance`` -> ``reject_exploratory_promotion``),
       proving a registered-experiment invocation cannot obtain
       canonical/none classification through this producer end-to-end, not
       merely that a field happens to say the right string.
    """
    output_dir = tmp_path / "fresh_experiment_run"
    assert not output_dir.exists(), "path must be genuinely fresh for this test to be meaningful"

    registry_index_path = tmp_path / "manifest_registry_index.json"
    experiment_id = "exp-adversarial-fresh-path-2026-07-14"
    manifest_digest = "sha256:adversarial-fresh-path-digest"
    _write_registry_index(registry_index_path, experiment_id=experiment_id, manifest_digest=manifest_digest)

    # The registered-experiment harness writes its classification marker
    # BEFORE any reusable output is produced -- exactly like the real
    # run_sim_104.py experiment-mode contract -- at the SAME fresh path this
    # training run uses as its output_dir.
    write_experiment_classification(
        output_dir,
        experiment_id=experiment_id,
        manifest_path="irrelevant/for/this/test.json",
        manifest_digest=manifest_digest,
        config_digest="sha256:config-digest",
    )

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_EXPERIMENT,
    )

    with pytest.raises(ValueError, match="Cannot promote output of registered experiment"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    # The manifest WAS correctly built and correctly classified as
    # "experiment" before the registry-side promotion gate independently
    # rejected it for promotion -- this is NOT the old bug (silent "none"),
    # it is a correctly-detected, correctly-rejected "experiment".
    assert ctx.artifact_manifest is not None
    assert ctx.artifact_manifest["provenance"]["kind"] == "experiment"
    assert ctx.artifact_manifest["provenance"] != {"kind": "none"}
    assert ctx.artifact_manifest["provenance"]["dir"] == str(output_dir)
    assert ctx.artifact_manifest["provenance"]["registry_index_path"] == str(registry_index_path)


# ---------------------------------------------------------------------------
# Round 5: the canonical-side bypass Codex's P0 review demanded proof of
# ---------------------------------------------------------------------------


def test_canonical_declaration_over_registered_experiment_marker_is_rejected(tmp_path: Path) -> None:
    """THE round-5 adversarial integration test Codex's P0 review asked for.

    Quoted in full (also in ``workflow_provenance``'s module docstring):

        "workflow_class='canonical' remains the exact caller-controlled
        bypass. build_verified_provenance() returns {'kind':'none'}
        immediately for that value, with no verification. [...] Add the
        required negative integration test: create a real registered
        experiment at a fresh output path, give it workflow_class='canonical'
        instead of the honest value, and prove the system does not accept it
        as canonical/none."

    This mirrors ``test_registered_experiment_at_fresh_path_is_never_none``
    above EXACTLY -- same fresh path, same real
    ``write_experiment_classification()`` call, same real registry index --
    except the caller now declares ``workflow_class=WORKFLOW_CLASS_CANONICAL``
    (the dishonest value) instead of ``WORKFLOW_CLASS_EXPERIMENT`` (the
    honest one). If this producer accepted that at face value it would
    return ``provenance={"kind": "none"}`` for a directory that is, in
    verifiable, on-disk fact, a registered experiment run -- exactly the
    bypass Codex described. It must instead be rejected, and the
    ``artifact_manifest`` must never be populated with a false "none".
    """
    output_dir = tmp_path / "fresh_experiment_run_lying_as_canonical"
    assert not output_dir.exists(), "path must be genuinely fresh for this test to be meaningful"

    registry_index_path = tmp_path / "manifest_registry_index.json"
    experiment_id = "exp-adversarial-canonical-lie-2026-07-14"
    manifest_digest = "sha256:adversarial-canonical-lie-digest"
    _write_registry_index(registry_index_path, experiment_id=experiment_id, manifest_digest=manifest_digest)

    # A real registered-experiment harness writes its classification marker
    # BEFORE any reusable output is produced, at this same fresh path -- this
    # run IS, in verifiable fact, a registered experiment.
    write_experiment_classification(
        output_dir,
        experiment_id=experiment_id,
        manifest_path="irrelevant/for/this/test.json",
        manifest_digest=manifest_digest,
        config_digest="sha256:config-digest",
    )

    # The dishonest declaration: same output_dir, same registry, but the
    # caller now claims WORKFLOW_CLASS_CANONICAL instead of the honest
    # WORKFLOW_CLASS_EXPERIMENT.
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "experiment_registry_index_path": str(registry_index_path),
        },
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )

    with pytest.raises(ValueError, match="REGISTERED EXPERIMENT run"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    # The false "canonical/none" classification must never have been
    # accepted -- the manifest build itself must have aborted before
    # ctx.artifact_manifest was ever populated.
    assert ctx.artifact_manifest is None


def test_canonical_declaration_over_experiment_marker_is_rejected_even_without_registry_index(
    tmp_path: Path,
) -> None:
    """The canonical-side rejection must not depend on the caller happening
    to also supply ``experiment_registry_index_path`` -- a marker that
    self-reports ``EXPLORATORY_ONLY`` is enough on its own (mirrors
    ``reject_exploratory_promotion``'s legacy-caller fallback, the same
    function ``renquant_artifacts.experiment_registry._verify_none_provenance``
    already relies on for the analogous ``kind="none"`` manifest-level
    check).
    """
    output_dir = tmp_path / "fresh_experiment_run_no_registry_ref"
    assert not output_dir.exists(), "path must be genuinely fresh for this test to be meaningful"

    write_experiment_classification(
        output_dir,
        experiment_id="exp-adversarial-no-registry-ref",
        manifest_path="irrelevant/for/this/test.json",
        manifest_digest="sha256:no-registry-ref-digest",
        config_digest="sha256:config-digest",
    )

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"strategy": "renquant_104"},  # no experiment_registry_index_path at all
        output_dir=output_dir,
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )

    with pytest.raises(ValueError, match="REGISTERED EXPERIMENT run"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    assert ctx.artifact_manifest is None


# ---------------------------------------------------------------------------
# Round 6: positive canonical verification (F-7 step 2/4) -- a genuine
# canonical claim is now independently verified against a real run-intent
# record, not returned as a bare, self-declared {"kind": "none"}.
# ---------------------------------------------------------------------------


def test_canonical_workflow_class_verified_against_real_run_intent_is_accepted(
    tmp_path: Path, canonical_run_intent_fixture,
) -> None:
    """Round 6 positive control: a real, valid ``run_intent.json`` (written
    via ``renquant_artifacts.canonical_registry.write_canonical_run_intent``,
    with genuine temp-git-repo code pins for the 3 canonical subrepos --
    ``tests/conftest.py::canonical_run_intent_fixture`` mirrors the exact
    real-git-repo technique renquant-artifacts' own test suite uses for this
    same check) declared via ``model_config['canonical_run_intent_path']``,
    plus a real ``artifact_digest``, is independently verified and produces a
    genuine ``provenance.kind='canonical'`` record -- accepted end-to-end by
    the real, non-mocked promotion-boundary gate
    (``BuildArtifactManifestTask`` calls ``validate_artifact_manifest`` ->
    ``verify_artifact_provenance`` itself; this test also calls
    ``verify_artifact_provenance`` directly as a second, explicit check).
    """
    fx = canonical_run_intent_fixture
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "canonical_run_intent_path": str(fx.run_intent_path),
        },
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )
    result = PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    assert result.ok is True
    assert ctx.artifact_manifest is not None
    provenance = ctx.artifact_manifest["provenance"]
    assert provenance["kind"] == "canonical"
    assert provenance != {"kind": "none"}
    assert provenance["run_intent_path"] == str(fx.run_intent_path)
    assert provenance["artifact_digest"] == ctx.artifact_manifest["fingerprint"]
    assert "run_intent_digest" in provenance

    # Explicit second check against the real, non-mocked registry-side gate.
    experiment_registry.verify_artifact_provenance(ctx.artifact_manifest)


def test_canonical_declaration_without_run_intent_path_is_rejected(tmp_path: Path) -> None:
    """Round 6 negative control: ``workflow_class='canonical'`` with no
    ``model_config['canonical_run_intent_path']`` must be rejected -- a bare
    canonical declaration with nothing to independently verify it against is
    not trusted."""
    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={"strategy": "renquant_104"},  # no canonical_run_intent_path
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )

    with pytest.raises(ValueError, match="canonical_run_intent_path"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    assert ctx.artifact_manifest is None


def test_canonical_declaration_with_tampered_code_pin_is_rejected(
    tmp_path: Path, canonical_run_intent_fixture,
) -> None:
    """Round 6 negative control: a ``run_intent.json`` whose code pin does
    NOT match the actual checked-out commit must fail verification and
    surface the underlying error list, not silently pass."""
    fx = canonical_run_intent_fixture
    raw = json.loads(fx.run_intent_path.read_text())
    raw["code_pins"]["renquant-model"]["commit"] = "0" * 40
    fx.run_intent_path.write_text(json.dumps(raw))

    ctx = TrainingContext(
        dataset_manifest=_dataset_manifest(),
        model_config={
            "strategy": "renquant_104",
            "canonical_run_intent_path": str(fx.run_intent_path),
        },
        output_dir=tmp_path / "out",
        workflow_class=WORKFLOW_CLASS_CANONICAL,
    )

    with pytest.raises(ValueError, match="failed verification"):
        PanelGbdtTrainingPipeline(_loader, _trainer, _validator).run(ctx)

    assert ctx.artifact_manifest is None
