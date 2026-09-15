"""The calibrator fit must stamp the identity the LIVE RUNTIME presents.

2026-09-01 (monthly_calibrator_refresh): Step 3b BINDING MISMATCH quarantined
the staged calibrator — the fifth occurrence of the calibrator/scorer
fingerprint class (05-27, 06-22, 07-01, 07-14/16). renquant-model#56 made
both producers import ONE `model_content_sha256`, but the runtime does not
identify a LEGACY (unstamped) artifact by that function at all: `PanelScorer
.load` stamps `renquant_common.model_fingerprint.stamp_artifact_metadata`,
whose `model_content_fingerprint` is the 0.8.1 denylist hash. Reproduced
2026-09-15 on the served scorer: v1 `0660bc89…` vs runtime `2d5a0288…`;
`verify_calibrator_scorer_binding.py` FAILS a fit stamped the v1 way and
PASSES one stamped with the runtime identity.

These tests pin: (1) an unstamped artifact is stamped with the runtime's
identity, which differs from the v1 hash for a realistic payload (so the
test cannot pass vacuously); (2) a schema-v1 stamped artifact keeps its own
stamp; (3) the shim's own answer is what we return, not a re-implementation.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

from renquant_common.model_fingerprint import (
    model_content_sha256,
    stamp_artifact_metadata,
)

import renquant_model_gbdt.fit_calibrator_alpha158_fund as fit


def _legacy_payload() -> dict:
    # Shape of the served panel-ltr.alpha158_fund.json: booster + feature
    # contract + params + a metadata block, and NO fingerprint fields.
    return {
        "booster_raw_json": json.dumps({"learner": {"attributes": {}, "gradient_booster": {"model": {"trees": []}}}}),
        "feature_cols": ["alpha_1", "alpha_2", "fund_roe"],
        "feature_means": {"alpha_1": 0.0, "alpha_2": 0.1, "fund_roe": 0.2},
        "feature_stds": {"alpha_1": 1.0, "alpha_2": 1.1, "fund_roe": 1.2},
        "params": {"eta": 0.05, "max_depth": 4},
        # keys the served artifact carries that the two hashers classify
        # DIFFERENTLY: `label_col` is excluded by the 0.8.1 denylist but
        # PREDICTIVE in schema v1; `best_iter` / `version` / `cv_folds` are
        # kept by the denylist but absent from the v1 allowlist.
        "label_col": "fwd_60d_excess",
        "lookahead_days": 60,
        "best_iter": 412,
        "version": "gbdt-alpha158-fund-v3",
        "cv_folds": 5,
        "trained_date": "2026-08-31",
        "metadata": {"trained_date": "2026-08-31", "note": "legacy, unstamped"},
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "panel-ltr.alpha158_fund.json"
    p.write_text(json.dumps(payload))
    return p


def test_unstamped_artifact_is_stamped_with_the_runtime_identity(tmp_path):
    payload = _legacy_payload()
    path = _write(tmp_path, payload)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        runtime_identity = stamp_artifact_metadata({}, path, payload=payload)["model_content_fingerprint"]
    v1 = model_content_sha256(payload)
    # Anti-vacuity: the two identities MUST differ for this payload, otherwise
    # the test could not tell which one the fit script chose.
    assert runtime_identity != v1, "payload does not discriminate legacy vs v1"
    assert fit._artifact_fingerprint(path, payload) == runtime_identity
    assert fit._artifact_fingerprint(path, payload) != v1


def test_a_v1_stamped_artifact_keeps_its_own_stamp(tmp_path):
    payload = _legacy_payload()
    payload["fingerprint_schema_version"] = 1
    payload["model_content_fingerprint"] = "sha256:" + "ab" * 32
    path = _write(tmp_path, payload)
    assert fit._artifact_fingerprint(path, payload) == payload["model_content_fingerprint"]


def test_the_runtime_identity_is_the_shims_answer_not_a_copy(tmp_path):
    """If the shim moves, we move with it: no second implementation here."""
    payload = _legacy_payload()
    path = _write(tmp_path, payload)
    assert fit._runtime_legacy_identity(path, payload) == fit._artifact_fingerprint(path, payload)


def test_a_missing_file_falls_through_to_the_historical_chain(tmp_path):
    """The shim needs the file for its artifact hash; without it the helper
    returns None and `_artifact_fingerprint` uses the v1 hash as before."""
    payload = _legacy_payload()
    missing = tmp_path / "not-written.json"
    assert fit._runtime_legacy_identity(missing, payload) is None
    assert fit._artifact_fingerprint(missing, payload) == model_content_sha256(payload)
