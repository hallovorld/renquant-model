"""Immutable experiment manifest builder for ensemble combination experiments.

Per §4.5A of the ensemble design (model PR #48): before the first discovery
run, create an immutable experiment manifest that lists every considered
expert, expert set, score normalization, missing-score rule,
covariance/window rule, portfolio mapping, rebalance cadence, cost
assumption, risk constraint, test, and stopping rule.

The manifest is frozen before any outer-fold evaluation begins.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ExperimentManifest:
    """Immutable experiment manifest per §4.5A."""

    manifest_id: str = ""
    created_at: str = ""
    design_doc_ref: str = "doc/research/2026-07-12-ensemble-combination-experiment.md"
    design_doc_pr: str = "model#48"

    # §4.5A: every considered expert
    experts: list[dict[str, Any]] = field(default_factory=list)
    expert_sets: list[dict[str, Any]] = field(default_factory=list)

    # §4.1bis: causal normalization
    score_normalization: dict[str, Any] = field(default_factory=dict)
    missing_score_rule: str = ""
    score_orientation_convention: str = ""

    # §3.3: covariance/window rule (L2)
    covariance_window_rule: dict[str, Any] = field(default_factory=dict)

    # §4.4: portfolio mapping (fixed across levels)
    portfolio_mapping: dict[str, Any] = field(default_factory=dict)
    rebalance_cadence: str = ""
    cost_assumptions: dict[str, Any] = field(default_factory=dict)
    risk_constraints: dict[str, Any] = field(default_factory=dict)

    # §4.4: test specification
    statistical_test: dict[str, Any] = field(default_factory=dict)
    correction_procedure: str = ""
    hypothesis_family: list[dict[str, str]] = field(default_factory=list)

    # §4.5A: stopping rules
    stopping_rules: list[str] = field(default_factory=list)

    # §4.5B: chronological evidence stages
    discovery_period: dict[str, str] = field(default_factory=dict)
    confirmation_period: dict[str, str] = field(default_factory=dict)
    confirmation_status: str = "UNREAD"

    # §4.5A: rejected candidates and failed runs
    rejected_candidates: list[dict[str, Any]] = field(default_factory=list)
    failed_runs: list[dict[str, Any]] = field(default_factory=list)

    # Ledger reference
    admissibility_ledger_fingerprint: str = ""

    # Manifest integrity
    manifest_fingerprint: str = ""

    def compute_fingerprint(self) -> str:
        d = asdict(self)
        d.pop("manifest_fingerprint", None)
        d.pop("created_at", None)
        content = json.dumps(d, sort_keys=True).encode()
        return f"sha256:{hashlib.sha256(content).hexdigest()}"


def build_default_manifest(
    *,
    admissibility_ledger_fingerprint: str = "",
) -> ExperimentManifest:
    """Build the default manifest for the L1-L3 ensemble experiment.

    This encodes the pre-registered design from model PR #48.
    """
    manifest = ExperimentManifest(
        manifest_id="ensemble-combination-l1l3-v1",
        created_at=datetime.utcnow().isoformat() + "Z",
        experts=[
            {
                "name": "xgb",
                "model_family": "xgb-panel",
                "status": "primary_live",
                "score_orientation": "higher_is_bullish",
            },
            {
                "name": "patchtst",
                "model_family": "hf-patchtst-panel",
                "status": "shadow_demoted",
                "score_orientation": "higher_is_bullish",
            },
            {
                "name": "per_ticker",
                "model_family": "per-ticker-tournament",
                "status": "frozen_since_april",
                "score_orientation": "higher_is_bullish",
                "prerequisite": "timeout fix 600->3600s",
            },
        ],
        expert_sets=[
            {"set_id": "2E", "experts": ["xgb", "patchtst"], "levels": ["L1", "L2"]},
            {
                "set_id": "3E",
                "experts": ["xgb", "patchtst", "per_ticker"],
                "levels": ["L1-3E", "L3"],
                "prerequisite": "per_ticker unfrozen and ledgered",
            },
        ],
        score_normalization={
            "method": "cross_sectional_zscore",
            "causal": True,
            "description": "z-score using only information available as of prediction timestamp",
        },
        missing_score_rule="exclude_and_renormalize",
        score_orientation_convention="higher_is_bullish",
        covariance_window_rule={
            "window_days": 60,
            "shrinkage": "toward_equal_weights",
            "residual_correlation_threshold": 0.3,
            "description": "per §3.3: fixed 60-day trailing, shrunk toward equal weights",
        },
        portfolio_mapping={
            "method": "fixed_top_n_selection",
            "description": "same score-to-portfolio mapping as frozen champion",
            "fixed_across_levels": True,
        },
        rebalance_cadence="daily",
        cost_assumptions={
            "base_cost_bps": 5,
            "adverse_cost_2x_bps": 10,
            "slippage_model": "existing_sim_infrastructure",
        },
        risk_constraints={
            "concentration_cap": "existing_champion_convention",
            "max_turnover": "existing_champion_convention",
            "fixed_across_levels": True,
        },
        statistical_test={
            "type": "dependence_robust_paired_test",
            "primary": "non_overlapping_outer_blocks",
            "fallback": "moving_block_bootstrap_or_hac",
            "block_length_days": 60,
            "alpha": 0.05,
            "minimum_effect_size_delta_ic": 0.005,
            "one_sided": True,
        },
        correction_procedure="hierarchical_sequential_gatekeeping",
        hypothesis_family=[
            {"id": "H1", "comparison": "L1 vs frozen champion"},
            {"id": "H2", "comparison": "L2 vs L1"},
            {"id": "H3", "comparison": "L1-3E vs L2"},
            {"id": "H4", "comparison": "L3 vs L2"},
            {"id": "H5", "comparison": "L3 vs L1-3E"},
            {"id": "H6", "comparison": "final candidate vs frozen champion"},
        ],
        stopping_rules=[
            "L1 fails champion -> STOP (cost decision, not statistical necessity)",
            "L2 fails L1 -> deploy L1",
            "L3 fails L1-3E -> deploy L1-3E (gain from expert, not method)",
            "No level passes confirmation -> champion unchanged",
        ],
        discovery_period={
            "description": "nested purged walk-forward on inner/outer split",
            "status": "NOT_STARTED",
        },
        confirmation_period={
            "description": "final chronological holdout, embargoed from discovery",
            "status": "UNREAD",
        },
        confirmation_status="UNREAD",
        admissibility_ledger_fingerprint=admissibility_ledger_fingerprint,
    )

    manifest.manifest_fingerprint = manifest.compute_fingerprint()
    return manifest


def write_manifest(manifest: ExperimentManifest, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "experiment_manifest.json"
    output_path.write_text(json.dumps(asdict(manifest), indent=2) + "\n")
    return output_path


def load_and_verify_manifest(path: Path) -> ExperimentManifest:
    """Load a manifest and verify its fingerprint hasn't been tampered with."""
    data = json.loads(path.read_text())
    stored_fp = data.get("manifest_fingerprint", "")

    manifest = ExperimentManifest(**{
        k: v for k, v in data.items()
        if k in ExperimentManifest.__dataclass_fields__
    })

    computed_fp = manifest.compute_fingerprint()
    if stored_fp and computed_fp != stored_fp:
        raise ValueError(
            f"manifest fingerprint mismatch: stored={stored_fp}, "
            f"computed={computed_fp} — manifest may have been modified"
        )

    return manifest


def resolve_champion_name(manifest: ExperimentManifest) -> str:
    """Resolve the frozen champion's name from the manifest's declared
    experts, never from caller/CLI argument order.

    Exactly one manifest expert must carry ``status == "primary_live"`` --
    that is the pre-registered frozen champion (Codex review 2026-07-13
    on model#53, finding 3: "first --expert" is CLI-order-dependent, not a
    frozen identity).
    """
    candidates = [e["name"] for e in manifest.experts if e.get("status") == "primary_live"]
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one manifest expert with status=primary_live "
            f"to serve as the frozen champion, found {len(candidates)}: {candidates}"
        )
    return candidates[0]
