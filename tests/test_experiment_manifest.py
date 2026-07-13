"""Tests for the experiment manifest builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "experiments" / "ensemble_phase0"))

from experiment_manifest import (
    ExperimentManifest,
    build_default_manifest,
    load_and_verify_manifest,
    write_manifest,
)


class TestBuildDefaultManifest:
    def test_creates_manifest_with_all_required_fields(self) -> None:
        manifest = build_default_manifest()
        assert manifest.manifest_id == "ensemble-combination-l1l3-v1"
        assert len(manifest.experts) == 3
        assert len(manifest.expert_sets) == 2
        assert manifest.score_normalization["causal"] is True
        assert manifest.missing_score_rule == "exclude_and_renormalize"
        assert manifest.portfolio_mapping["fixed_across_levels"] is True
        assert manifest.statistical_test["alpha"] == 0.05
        assert manifest.statistical_test["minimum_effect_size_delta_ic"] == 0.005
        assert len(manifest.hypothesis_family) == 6
        assert len(manifest.stopping_rules) == 4
        assert manifest.confirmation_status == "UNREAD"

    def test_fingerprint_is_deterministic(self) -> None:
        m1 = build_default_manifest(admissibility_ledger_fingerprint="sha256:abc")
        m2 = build_default_manifest(admissibility_ledger_fingerprint="sha256:abc")
        assert m1.manifest_fingerprint == m2.manifest_fingerprint
        assert m1.manifest_fingerprint.startswith("sha256:")

    def test_fingerprint_changes_with_content(self) -> None:
        m1 = build_default_manifest(admissibility_ledger_fingerprint="sha256:abc")
        m2 = build_default_manifest(admissibility_ledger_fingerprint="sha256:def")
        assert m1.manifest_fingerprint != m2.manifest_fingerprint

    def test_correction_procedure_is_specified(self) -> None:
        manifest = build_default_manifest()
        assert manifest.correction_procedure == "hierarchical_sequential_gatekeeping"

    def test_hypothesis_family_has_six_comparisons(self) -> None:
        manifest = build_default_manifest()
        ids = [h["id"] for h in manifest.hypothesis_family]
        assert ids == ["H1", "H2", "H3", "H4", "H5", "H6"]


class TestWriteAndLoad:
    def test_roundtrip(self, tmp_path: Path) -> None:
        manifest = build_default_manifest(admissibility_ledger_fingerprint="sha256:test")
        output_path = write_manifest(manifest, tmp_path)
        assert output_path.exists()

        loaded = load_and_verify_manifest(output_path)
        assert loaded.manifest_id == manifest.manifest_id
        assert loaded.manifest_fingerprint == manifest.manifest_fingerprint

    def test_detects_tampering(self, tmp_path: Path) -> None:
        manifest = build_default_manifest()
        output_path = write_manifest(manifest, tmp_path)

        data = json.loads(output_path.read_text())
        data["statistical_test"]["alpha"] = 0.10  # tamper
        output_path.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="fingerprint mismatch"):
            load_and_verify_manifest(output_path)
