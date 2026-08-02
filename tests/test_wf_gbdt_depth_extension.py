"""Pure/fast contracts of the Job B gbdt depth-extension driver (no training).

Everything here exercises the tool's PURE surface — ladder math, the artifact
field-parity guard, the #94 append-only lineage root, and the out-dir refusal.
The heavy path (panel load, sentiment gate, xgb fit) is covered by the tool's
--golden mode against the real earliest production window, deliberately not
re-run in CI.
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOD = ROOT / "tools" / "wf_gbdt_depth_extension.py"


def _load():
    spec = importlib.util.spec_from_file_location("wf_gbdt_depth_extension", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules["wf_gbdt_depth_extension"] = m
    spec.loader.exec_module(m)
    return m


T = _load()

# a synthetic ladder with the production convention: 21-calendar-day grid,
# Mondays, no holiday adjustment (2023-12-25 is Christmas and stays a cutoff).
LADDER = ["2023-10-02", "2023-10-23", "2023-11-13", "2023-12-04", "2023-12-25",
          "2024-01-15"]


# ── ladder-extension math ────────────────────────────────────────────────────

def test_cadence_is_DERIVED_from_the_manifest_not_assumed():
    assert T.derive_cadence_days(LADDER) == 21
    assert T.derive_cadence_days(["2020-01-01", "2020-01-08"]) == 7


def test_nonuniform_cadence_refuses():
    with pytest.raises(ValueError, match="not uniform"):
        T.derive_cadence_days(["2023-10-02", "2023-10-23", "2023-11-10"])


def test_backward_extension_is_unique_ordered_and_grid_aligned():
    import pandas as pd
    new = T.backward_extension(LADDER, "2023-01-01")
    assert new == sorted(new) and len(set(new)) == len(new)
    earliest = pd.Timestamp(LADDER[0])
    for c in new:
        delta = (earliest - pd.Timestamp(c)).days
        assert delta > 0 and delta % 21 == 0
    # covers down to the first grid point >= target
    assert pd.Timestamp(new[0]) >= pd.Timestamp("2023-01-01")
    assert pd.Timestamp(new[0]) - pd.Timedelta(days=21) < pd.Timestamp("2023-01-01")
    # and hands over contiguously to the existing ladder
    assert (earliest - pd.Timestamp(new[-1])).days == 21


def test_backward_extension_refuses_a_target_at_or_after_the_ladder():
    with pytest.raises(ValueError, match="not before"):
        T.backward_extension(LADDER, LADDER[0])


def test_duplicate_ladder_refuses():
    with pytest.raises(ValueError, match="duplicates"):
        T.validate_ladder(["2023-10-02", "2023-10-02", "2023-10-23"])


def test_unordered_ladder_refuses():
    with pytest.raises(ValueError, match="not chronologically ordered"):
        T.validate_ladder(["2023-10-23", "2023-10-02"])


# ── artifact field-set completeness (the stringified-norm_kind guard) ────────

def _ref_artifact() -> dict:
    """A synthetic existing-window artifact: the production key set in
    miniature, with the real fields' TYPES."""
    return {
        "version": 3,
        "kind": "panel_ltr_xgboost",
        "trained_date": "2026-06-16",
        "feature_cols": ["KMID", "roe"],
        "feature_means": [0.1, 0.2],
        "feature_stds": [1.0, 2.0],
        "feature_norm_kind": ["global_z", "robust_z"],
        "feature_source_contract": {"raw": "…", "panel": "…"},
        "params": {"objective": "rank:pairwise", "seed": 42},
        "best_iter": 100,
        "booster_raw_json": "{}",
        "panel_shape": {"rows": 10, "tickers": 2, "dates": 5},
        "label_col": "fwd_60d_excess",
        "lookahead_days": 60,
        "train_run_id": "3b94fcc5",
        "training_train_ic": 0.13,
        "training_notes": "…",
        "feature_raw_clip_low": [-0.1, None],
        "feature_raw_clip_high": [0.1, None],
        "feature_raw_clip_fit_split": "train",
        "feature_preprocess_version": 2,
        "cutoff_date": "2023-10-02T00:00:00",
        "cutoff_embargo_days": 60,
        "effective_train_cutoff_date": "2023-07-10T00:00:00",
        "side_label": "wf_r4_regen",
        "sentiment_runtime_gate_contract": "trained_zeroing",
        "sentiment_runtime_gate_feature_cols": ["mean_sentiment"],
        "sentiment_runtime_gate_disabled_regimes": ["BULL_CALM"],
        "sentiment_runtime_gate_zeroed_rows": 5,
        "sentiment_runtime_gate_warmup_zeroed_rows": 1,
        "sentiment_runtime_gate_missing_regime_policy": "warmup_zero_only",
        "sentiment_runtime_gate_policy": {"BULL_CALM": False},
        "config_fingerprint": "sha256:f8fb2259b2bf1537",
        "config_fingerprint_fields": {"watchlist": ["AAPL"]},
        "metadata": {"score_sample_range": [-0.5, 0.1],
                     "inference_smoke_test": {"n": 32},
                     "config_fingerprint_source": {"label_used": "fwd_60d_excess"}},
    }


def test_field_parity_passes_on_an_exact_key_and_type_mirror():
    import copy
    new = copy.deepcopy(_ref_artifact())
    new["trained_date"] = "2026-08-02"          # values may differ …
    new["sentiment_runtime_gate_zeroed_rows"] = 999  # … keys and types may not
    assert T.check_artifact_field_parity(new, _ref_artifact()) == []


def test_field_parity_flags_missing_and_extra_keys():
    import copy
    ref = _ref_artifact()
    new = copy.deepcopy(ref)
    del new["cutoff_embargo_days"]
    new["surprise_key"] = 1
    problems = "\n".join(T.check_artifact_field_parity(new, ref))
    assert "cutoff_embargo_days" in problems
    assert "surprise_key" in problems


def test_field_parity_flags_the_stringified_norm_kind_incident():
    """The exact recurrence: str(norm_kind) collapses the per-feature list to
    ONE string; every digest keeps verifying. The guard must flag the TYPE."""
    import copy
    ref = _ref_artifact()
    new = copy.deepcopy(ref)
    new["feature_norm_kind"] = str(ref["feature_norm_kind"])
    problems = "\n".join(T.check_artifact_field_parity(new, ref))
    assert "feature_norm_kind" in problems
    assert isinstance(ref["feature_norm_kind"], list)  # anti-vacuity


def test_field_parity_flags_norm_kind_length_drift():
    import copy
    ref = _ref_artifact()
    new = copy.deepcopy(ref)
    new["feature_norm_kind"] = ["global_z"]  # list, but not per-feature
    assert any("length" in p for p in T.check_artifact_field_parity(new, ref))


def test_field_parity_flags_metadata_subkey_drift():
    import copy
    ref = _ref_artifact()
    new = copy.deepcopy(ref)
    del new["metadata"]["config_fingerprint_source"]
    assert any("config_fingerprint_source" in p
               for p in T.check_artifact_field_parity(new, ref))


# ── append-only lineage root (#94 identity rule) ─────────────────────────────

def _shas(n: int, salt: str = "") -> list[str]:
    return [hashlib.sha256(f"{salt}{i}".encode()).hexdigest() for i in range(n)]


def test_root_rule_is_the_94_formula_byte_for_byte():
    shas = _shas(3)
    payload = "rid" + "\n" + "\n".join(shas) + "\n"
    assert T.lineage_root("rid", shas) == hashlib.sha256(payload.encode()).hexdigest()


def test_extending_the_list_moves_the_root():
    old = _shas(43)
    new = _shas(5, "new") + old
    assert T.lineage_root("rid", new) != T.lineage_root("rid", old)


def test_root_is_ORDER_sensitive():
    shas = _shas(6)
    swapped = list(shas)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert T.lineage_root("rid", swapped) != T.lineage_root("rid", shas)


def test_old_root_recomputes_from_the_suffix_of_the_extended_list():
    """Append-only backwards: the existing ladder is the SUFFIX of the new
    ordered list, so the old root must recompute from new_list[-43:]."""
    old = _shas(43)
    old_root = T.lineage_root("rid", old)
    extended = _shas(82, "new") + old
    assert T.lineage_root("rid", extended[-43:]) == old_root
    assert T.lineage_root("rid", extended) != old_root


def test_recipe_fingerprint_ignores_execution_only_params():
    a = _ref_artifact()
    b = {**a, "params": {**a["params"], "nthread": 8, "verbosity": 0}}
    assert T.recipe_fingerprint(a) == T.recipe_fingerprint(b)
    c = {**a, "params": {**a["params"], "eta": 0.99}}
    assert T.recipe_fingerprint(a) != T.recipe_fingerprint(c)


# ── batch gate: no extension training over a failed/absent golden ────────────

def test_batch_refuses_without_a_golden_report(tmp_path):
    with pytest.raises(ValueError, match="run --golden first"):
        T.require_golden_pass(tmp_path)


def test_batch_refuses_a_FAILED_golden(tmp_path):
    import json
    (tmp_path / "golden_report.json").write_text(json.dumps(
        {"parity_pass": False, "prediction_parity_max_abs_delta": 0.649}))
    with pytest.raises(ValueError, match="golden parity FAILED"):
        T.require_golden_pass(tmp_path)


def test_batch_admits_only_a_PASSED_golden(tmp_path):
    import json
    (tmp_path / "golden_report.json").write_text(json.dumps(
        {"parity_pass": True, "prediction_parity_max_abs_delta": 3e-7}))
    assert T.require_golden_pass(tmp_path)["parity_pass"] is True


# ── out-dir refusal ──────────────────────────────────────────────────────────

def test_out_dir_inside_the_umbrella_refuses():
    with pytest.raises(ValueError, match="read-only umbrella"):
        T.resolve_out_dir("/Users/renhao/git/github/RenQuant/data/depth-ext")


def test_out_dir_refusal_defeats_dot_dot_escapes_INTO_the_umbrella():
    with pytest.raises(ValueError, match="read-only umbrella"):
        T.resolve_out_dir("/Users/renhao/git/github/renquant-model/../RenQuant/x")


def test_out_dir_umbrella_root_itself_refuses():
    with pytest.raises(ValueError, match="read-only umbrella"):
        T.resolve_out_dir("/Users/renhao/git/github/RenQuant")


def test_out_dir_outside_the_umbrella_is_allowed(tmp_path):
    assert T.resolve_out_dir(tmp_path) == tmp_path.resolve()
