"""Readiness checks for the Track B full walk-forward GBDT retrain.

This module is deliberately validation-only: it checks the config/artifact
contract that a full WF retrain must satisfy, without loading panels or fitting
models. The actual long-running retrain remains owned by the orchestrator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .panel_data import TRACK_B_FEATURES
from .vol_trend_features import VOL_TREND_FEATURE_SET_VERSION, VOL_TREND_FEATURES

READINESS_CONFIG_VERSION = 1
TRIAD_METADATA_KEYS = ("sanity_triad", "placebo_triad", "placebo_sanity_triad")
VERDICT_METADATA_KEYS = ("verdict_metadata", "verdict_inputs")
FEATURE_SET_VERSION_KEYS = ("feature_set_version", "feature_set")


def config_declares_vol_trend_feature_set(config: dict[str, Any]) -> bool:
    """True when a retrain config opts into the ``vol_trend_v2`` feature set.

    Declared via ``feature_set_version`` (or ``feature_set``) at the top level or
    inside a ``full_wf_retrain`` object. Configs that do not declare the key are
    entirely unaffected — the vol_trend checks below are only appended when this
    returns True (zero default behavior change; production configs keep the old
    recipe until a gated retrain adopts the new one).
    """

    scopes: list[dict[str, Any]] = [config]
    retrain = config.get("full_wf_retrain")
    if isinstance(retrain, dict):
        scopes.append(retrain)
    for scope in scopes:
        for key in FEATURE_SET_VERSION_KEYS:
            if str(scope.get(key) or "").strip().lower() == VOL_TREND_FEATURE_SET_VERSION:
                return True
    return False


def is_full_wf_retrain_config(config: dict[str, Any]) -> bool:
    """Return true when a model config declares the full WF retrain mode."""

    mode = str(config.get("mode") or config.get("workflow") or "").replace("-", "_").lower()
    return bool(config.get("full_wf_retrain") is True or mode == "full_wf_retrain")


def validate_full_wf_retrain_readiness(
    config: dict[str, Any],
    artifact: dict[str, Any] | None = None,
    *,
    require_full_wf_retrain: bool = True,
) -> dict[str, Any]:
    """Return an audit report for Track B full-WF-retrain readiness.

    Required properties:
    - the config explicitly declares full WF retrain mode;
    - the config requires all four Track B features;
    - when an artifact is supplied, it carries all four features, the Track B
      addendum, and either sanity-triad or verdict metadata.
    """

    required = list(TRACK_B_FEATURES)
    checks: list[dict[str, Any]] = []

    full_wf = is_full_wf_retrain_config(config)
    _add_check(
        checks,
        "full_wf_retrain_config",
        full_wf or not require_full_wf_retrain,
        {"full_wf_retrain": config.get("full_wf_retrain"), "mode": config.get("mode")},
    )

    config_features = _config_required_features(config)
    missing_config = _missing(required, config_features)
    _add_check(
        checks,
        "config_requires_track_b_features",
        not missing_config,
        {"required_features": config_features, "missing": missing_config},
    )

    metadata_requirement = _config_metadata_requirement(config)
    _add_check(
        checks,
        "config_requires_triad_or_verdict_metadata",
        metadata_requirement["present"],
        metadata_requirement,
    )

    if artifact is not None:
        artifact_features = _artifact_features(artifact)
        missing_artifact = _missing(required, artifact_features)
        _add_check(
            checks,
            "artifact_contains_track_b_features",
            not missing_artifact,
            {"feature_cols": artifact_features, "missing": missing_artifact},
        )

        addendum = artifact.get("feature_addendum_v1") or {}
        active = [str(v) for v in addendum.get("track_b_features_active", [])] if isinstance(addendum, dict) else []
        missing_addendum = _missing(required, active)
        _add_check(
            checks,
            "artifact_stamps_track_b_addendum",
            not missing_addendum,
            {"track_b_features_active": active, "missing": missing_addendum},
        )

        evidence = _triad_or_verdict_metadata(artifact)
        _add_check(
            checks,
            "artifact_has_triad_or_verdict_metadata",
            evidence["present"],
            evidence,
        )

    # Vol/trend feature-set v2 checks (STD60 provenance, orchestrator #475/#476) —
    # appended ONLY when the config declares feature_set_version=vol_trend_v2, so
    # existing configs (production today) produce a byte-identical report.
    vol_trend_declared = config_declares_vol_trend_feature_set(config)
    required_vol_trend = list(VOL_TREND_FEATURES)
    if vol_trend_declared:
        missing_vt_config = _missing(required_vol_trend, config_features)
        _add_check(
            checks,
            "config_requires_vol_trend_features",
            not missing_vt_config,
            {"required_features": config_features, "missing": missing_vt_config},
        )
        if artifact is not None:
            artifact_features = _artifact_features(artifact)
            missing_vt_artifact = _missing(required_vol_trend, artifact_features)
            _add_check(
                checks,
                "artifact_contains_vol_trend_features",
                not missing_vt_artifact,
                {"feature_cols": artifact_features, "missing": missing_vt_artifact},
            )
            # The v2 stamp is NESTED under feature_addendum_v1 (the recipe-
            # identity field renquant-common's fingerprint table classifies
            # PREDICTIVE as one atomic unit) — see panel_data.LoadPanelTask.
            addendum_v1 = artifact.get("feature_addendum_v1")
            vol_trend_stamp = (addendum_v1 or {}).get("vol_trend_v2") if isinstance(addendum_v1, dict) else None
            if isinstance(vol_trend_stamp, dict):
                active_v2 = [str(v) for v in vol_trend_stamp.get("vol_trend_features_active", [])]
                stamped_version = vol_trend_stamp.get("feature_set_version")
            else:
                active_v2, stamped_version = [], None
            missing_vt_addendum = _missing(required_vol_trend, active_v2)
            version_ok = stamped_version == VOL_TREND_FEATURE_SET_VERSION
            _add_check(
                checks,
                "artifact_stamps_vol_trend_addendum",
                version_ok and not missing_vt_addendum,
                {
                    "feature_set_version": stamped_version,
                    "expected_feature_set_version": VOL_TREND_FEATURE_SET_VERSION,
                    "vol_trend_features_active": active_v2,
                    "missing": missing_vt_addendum,
                },
            )

    report = {
        "ok": all(bool(c["ok"]) for c in checks),
        "readiness_config_version": READINESS_CONFIG_VERSION,
        "required_track_b_features": required,
        "checks": checks,
    }
    if vol_trend_declared:
        report["feature_set_version"] = VOL_TREND_FEATURE_SET_VERSION
        report["required_vol_trend_features"] = required_vol_trend
    return report


def require_full_wf_retrain_readiness(
    config: dict[str, Any],
    artifact: dict[str, Any] | None = None,
    *,
    require_full_wf_retrain: bool = True,
) -> dict[str, Any]:
    """Validate readiness and raise with concrete failed checks on failure."""

    report = validate_full_wf_retrain_readiness(
        config,
        artifact,
        require_full_wf_retrain=require_full_wf_retrain,
    )
    if not report["ok"]:
        failed = [
            f"{check['name']}={check['detail']}"
            for check in report["checks"]
            if not check["ok"]
        ]
        raise ValueError("full WF retrain readiness failed: " + "; ".join(failed))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Track B full WF retrain readiness.")
    parser.add_argument("--config", required=True, type=Path, help="JSON model/retrain readiness config")
    parser.add_argument("--artifact", type=Path, help="Optional artifact JSON to validate after a retrain")
    parser.add_argument("--json", action="store_true", help="Print the full readiness report as JSON")
    args = parser.parse_args(argv)

    config = _read_json(args.config)
    artifact = _read_json(args.artifact) if args.artifact is not None else None
    report = validate_full_wf_retrain_readiness(config, artifact)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "ok" if report["ok"] else "failed"
        print(f"Track B full WF retrain readiness: {status}")
        for check in report["checks"]:
            mark = "OK" if check["ok"] else "FAIL"
            print(f"- {mark} {check['name']}: {check['detail']}")
    return 0 if report["ok"] else 1


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _config_required_features(config: dict[str, Any]) -> list[str]:
    for key in ("required_features", "required_feature_cols", "feature_cols"):
        value = config.get(key)
        if isinstance(value, list):
            return [str(v) for v in value]
    retrain = config.get("full_wf_retrain")
    if isinstance(retrain, dict):
        for key in ("required_features", "required_feature_cols", "feature_cols"):
            value = retrain.get(key)
            if isinstance(value, list):
                return [str(v) for v in value]
    return []


def _config_metadata_requirement(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("required_artifact_metadata")
    if not isinstance(value, dict):
        return {"present": False, "required_artifact_metadata": value}
    one_of = value.get("one_of")
    options = [str(v) for v in one_of] if isinstance(one_of, list) else []
    has_triad = any(option in TRIAD_METADATA_KEYS for option in options)
    has_verdict = any("verdict" in option for option in options)
    return {
        "present": bool(has_triad or has_verdict),
        "one_of": options,
        "accepted_triad_keys": list(TRIAD_METADATA_KEYS),
        "accepted_verdict_forms": ["verdict + verdict_metadata", "verdict + verdict_inputs"],
    }


def _artifact_features(artifact: dict[str, Any]) -> list[str]:
    for key in ("feature_cols", "feature_columns", "input_feature_cols"):
        value = artifact.get(key)
        if isinstance(value, list):
            return [str(v) for v in value]
    return []


def _triad_or_verdict_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    metadata = artifact.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    for scope_name, scope in (("artifact", artifact), ("metadata", nested)):
        for key in TRIAD_METADATA_KEYS:
            value = scope.get(key)
            if _has_value(value):
                return {
                    "present": True,
                    "source": scope_name,
                    "kind": "triad",
                    "key": key,
                }
        verdict = scope.get("verdict")
        for key in VERDICT_METADATA_KEYS:
            value = scope.get(key)
            if _has_value(verdict) and _has_value(value):
                return {
                    "present": True,
                    "source": scope_name,
                    "kind": "verdict",
                    "key": key,
                    "verdict": verdict,
                }
    return {
        "present": False,
        "accepted_keys": {
            "triad": list(TRIAD_METADATA_KEYS),
            "verdict": ["verdict + verdict_metadata", "verdict + verdict_inputs"],
        },
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        return len(value) > 0
    return True


def _missing(required: list[str], seen: list[str]) -> list[str]:
    have = set(seen)
    return [feature for feature in required if feature not in have]


def _add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: dict[str, Any]) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
