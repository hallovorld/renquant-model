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
        T.require_golden_pass(tmp_path / "golden_report.json")


def test_batch_refuses_a_FAILED_golden(tmp_path):
    import json
    p = tmp_path / "golden_report.json"
    p.write_text(json.dumps(
        {"parity_pass": False, "prediction_parity_max_abs_delta": 0.649}))
    with pytest.raises(ValueError, match="golden parity FAILED"):
        T.require_golden_pass(p)


def test_batch_admits_only_a_PASSED_golden(tmp_path):
    import json
    p = tmp_path / "golden_report.json"
    p.write_text(json.dumps(
        {"parity_pass": True, "prediction_parity_max_abs_delta": 3e-7}))
    assert T.require_golden_pass(p)["parity_pass"] is True


# ── vintage-seam mode (operator decision 2026-08-02) ─────────────────────────

DIGESTS = {"panel_sha256": "p" * 64, "fundamentals_sha256": "f" * 64,
           "alpha_stats_sha256": "a" * 64, "wf_manifest_sha256": "m" * 64,
           "strategy_config_sha256": "s" * 64, "spy_ohlcv_sha256": "y" * 64,
           "gmm_artifact_sha256": "g" * 64}


def _failed_report() -> dict:
    return {"parity_pass": False,
            "prediction_parity_max_abs_delta": 0.6489841341972351,
            "feature_means_max_abs_delta": 0.007131227576620575,
            "feature_stds_max_abs_delta": 0.009450348912744377,
            "input_digests": {"panel": "/x/panel.parquet", **DIGESTS}}


def _passed_report() -> dict:
    """A PASSED golden bound to the current vintage. Round 2: a passed report must
    carry input_digests like a failed one, because the vintage check now runs before
    either parity branch."""
    return {"parity_pass": True, "prediction_parity_max_abs_delta": 3e-7,
            "feature_means_max_abs_delta": 1e-9, "feature_stds_max_abs_delta": 1e-9,
            "input_digests": {"panel": "/x/panel.parquet", **DIGESTS}}


def _write(tmp_path, payload) -> "pathlib.Path":
    import json
    p = tmp_path / "golden_report.json"
    p.write_text(json.dumps(payload))
    return p


def test_seam_flag_without_any_golden_refuses(tmp_path):
    with pytest.raises(ValueError, match="run --golden first"):
        T.resolve_vintage_seam(tmp_path / "golden_report.json", True, DIGESTS)


def test_seam_flag_over_a_PASSED_golden_refuses(tmp_path):
    """A passed golden means no seam exists — declaring one would be a false
    record, so the flag must refuse rather than write it."""
    p = _write(tmp_path, _passed_report())
    with pytest.raises(ValueError, match="no seam exists"):
        T.resolve_vintage_seam(p, True, DIGESTS)


def test_seam_flag_over_a_BOUND_FAILED_golden_returns_the_evidence(tmp_path):
    """The true report + matching input digests -> admitted, and the returned
    file sha binds the exact evidence bytes."""
    import hashlib as h
    p = _write(tmp_path, _failed_report())
    report, sha = T.resolve_vintage_seam(p, True, DIGESTS)
    assert report["parity_pass"] is False
    assert report["prediction_parity_max_abs_delta"] == 0.6489841341972351
    assert sha == h.sha256(p.read_bytes()).hexdigest()


def test_seam_admission_refuses_a_STALE_report_naming_the_digest(tmp_path):
    """Inputs rebuilt since the golden ran: one digest diverges -> refused,
    and the message NAMES the diverging digest."""
    p = _write(tmp_path, _failed_report())
    current = dict(DIGESTS, panel_sha256="q" * 64)
    with pytest.raises(ValueError, match="STALE.*'panel_sha256'"):
        T.resolve_vintage_seam(p, True, current)


def test_seam_admission_refuses_a_SUBSTITUTED_report(tmp_path):
    """A different failed report recorded against different bytes: its digest
    set does not match the pending batch -> refused (digest binding); a report
    with no digests at all is unusable."""
    stale = _failed_report()
    stale["input_digests"] = {"panel_sha256": "z" * 64}  # different vintage
    p = _write(tmp_path, stale)
    with pytest.raises(ValueError, match="panel_sha256|lacks input digest"):
        T.resolve_vintage_seam(p, True, DIGESTS)
    p2 = _write(tmp_path, {"parity_pass": False,
                           "prediction_parity_max_abs_delta": 0.1})
    with pytest.raises(ValueError, match="no input\\s+digests|no input digests"):
        T.resolve_vintage_seam(p2, True, DIGESTS)


def test_without_the_flag_batch_admission_is_UNCHANGED(tmp_path):
    """No flag -> the golden-pass gate exactly as before the seam decision."""
    p = _write(tmp_path, _failed_report())
    with pytest.raises(ValueError, match="golden parity FAILED"):
        T.resolve_vintage_seam(p, False, DIGESTS)
    p = _write(tmp_path, _passed_report())
    assert T.resolve_vintage_seam(p, False, DIGESTS) is None


def test_seam_block_carries_the_required_fields_from_the_report():
    inputs = [{"file": "/x/sec_fundamentals_daily.parquet",
               "sha256_at_read_time": "ab" * 32,
               "mtime_date_measured": "2026-08-01"}]
    seam = T.build_vintage_seam(_failed_report(), inputs,
                                evidence_path="/runs/run-001/golden_report.json",
                                evidence_sha256="cd" * 32)
    # the field set the seam decision requires, exactly
    assert seam["input_vintage"] == "2026-08-01-rebuild"
    assert seam["evidence_golden_report"] == "/runs/run-001/golden_report.json"
    assert seam["evidence_golden_report_sha256"] == "cd" * 32
    assert seam["golden_parity_max_abs_delta"] == 0.6489841341972351
    assert seam["drift"]["feature_means_max_abs_delta"] == 0.007131227576620575
    assert seam["drift"]["feature_stds_max_abs_delta"] == 0.009450348912744377
    assert seam["rebuilt_inputs"] == inputs
    assert seam["rebuild_date_measured"] == "2026-08-01"
    assert "no longer exist on disk" in seam["non_reproducibility"]
    assert "NOT byte-reproducible" in seam["non_reproducibility"]
    assert "do NOT regenerate" in seam["decision"]
    assert "third parallel corpus" in seam["decision_rationale"]


def test_seam_block_refuses_a_report_missing_the_evidence_numbers():
    with pytest.raises(ValueError, match="seam-evidence fields"):
        T.build_vintage_seam({"parity_pass": False}, [])


# ── atomic predeclared run dirs (goal7_momentum_run.py claim pattern) ─────────

def test_claim_creates_the_run_dir_with_an_in_progress_claim(tmp_path):
    import json
    run_dir = T.claim_run_dir(tmp_path, "001", "golden")
    assert run_dir == (tmp_path / "run-001").resolve()
    claim = json.loads((run_dir / "RUN_CLAIM.json").read_text())
    assert claim["status"] == "in-progress" and claim["mode"] == "golden"


def test_claim_refuses_an_existing_run_dir(tmp_path):
    (tmp_path / "run-001").mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        T.claim_run_dir(tmp_path, "001", "golden")


def test_claim_refuses_an_existing_claim_ie_a_crashed_run(tmp_path):
    """A crashed run leaves its claim in force: refuse-and-investigate."""
    T.claim_run_dir(tmp_path, "001", "extension")  # claim taken, never sealed
    with pytest.raises(ValueError, match="already exists.*in-progress"):
        T.claim_run_dir(tmp_path, "001", "extension")


def test_repeat_refusal_after_a_COMPLETED_sealed_run(tmp_path):
    """A completed run seals its outputs; rerunning the same run id refuses —
    a sealed corpus is superseded by a NEW run id, never overwritten."""
    import os
    run_dir = T.claim_run_dir(tmp_path, "002", "golden")
    (run_dir / "golden_report.json").write_text("{}")
    T.seal_run(run_dir, {"outcome": "golden", "parity_pass": False})
    with pytest.raises(ValueError, match="already exists.*consumed"):
        T.claim_run_dir(tmp_path, "002", "golden")
    # ... and the sealed outputs are read-only (0444)
    mode = os.stat(run_dir / "golden_report.json").st_mode & 0o777
    assert mode == 0o444
    assert (os.stat(run_dir / "RUN_CLAIM.json").st_mode & 0o777) == 0o444


def test_writers_refuse_an_UNCLAIMED_run_dir_so_no_write_precedes_the_claim(
        tmp_path, monkeypatch):
    """The 'no write before the claim' guarantee at runtime: every writing mode
    asserts an in-progress claim BEFORE touching anything. With all heavy
    readers/writers/trainers monkeypatched to raise, an unclaimed run dir must
    be refused before ANY of them is reached."""
    def _boom(*a, **k):
        raise AssertionError("writer/trainer invoked before the run claim")
    for fn in ("_load_ref_artifact", "_existing_window_rows", "_panel_dates",
               "_train_window", "sha256_file"):
        monkeypatch.setattr(T, fn, _boom, raising=True)
    with pytest.raises(ValueError, match="RUN_CLAIM"):
        T.run_extension(tmp_path / "run-009", {"retrains": []}, "2019-01-02",
                        250, DIGESTS, plan_only=False)
    with pytest.raises(ValueError, match="RUN_CLAIM"):
        T.run_golden(tmp_path / "run-009", {"retrains": []}, DIGESTS)


def test_writers_refuse_a_SEALED_run_dir(tmp_path, monkeypatch):
    """A consumed claim is terminal: even with the dir present, writers refuse."""
    def _boom(*a, **k):
        raise AssertionError("writer/trainer invoked on a sealed run")
    run_dir = T.claim_run_dir(tmp_path, "003", "extension")
    T.seal_run(run_dir, {"outcome": "extension"})
    for fn in ("_load_ref_artifact", "_existing_window_rows", "_panel_dates",
               "_train_window", "sha256_file"):
        monkeypatch.setattr(T, fn, _boom, raising=True)
    with pytest.raises(ValueError, match="not in-progress"):
        T.run_extension(run_dir, {"retrains": []}, "2019-01-02",
                        250, DIGESTS, plan_only=False)


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


# --- review round 2: the PASSED path was never bound to the input vintage -------------

def test_a_PASSED_golden_from_a_DIFFERENT_VINTAGE_is_refused(tmp_path):
    """THE round-2 finding. Round 1 bound only the failed-golden path, so the ordinary
    admission asked "did parity pass?" and never "on which inputs?" — a green report
    recorded against different panel/fundamentals/config bytes authorized a current
    batch, which is precisely the mixed-vintage lineage the whole gate exists to stop.

    A pass is evidence about the vintage it measured and about nothing else. It is the
    more dangerous of the two carried-forward cases, because nothing else in the passed
    path looks at the inputs at all.
    """
    stale_pass = _passed_report()
    stale_pass["input_digests"] = {**stale_pass["input_digests"],
                                   "panel_sha256": "z" * 64}
    p = _write(tmp_path, stale_pass)
    with pytest.raises(ValueError, match="STALE.*'panel_sha256'"):
        T.resolve_vintage_seam(p, False, DIGESTS)


def test_a_PASSED_golden_carrying_NO_digests_is_refused(tmp_path):
    """The unbindable case on the passed path: a report with no input digests cannot be
    tied to the pending batch at all, so it cannot authorize it. Before round 2 this was
    the *default* shape of a passing report — nothing required a passed golden to record
    what it ran on."""
    p = _write(tmp_path, {"parity_pass": True,
                          "prediction_parity_max_abs_delta": 3e-7})
    with pytest.raises(ValueError, match="no input\\s+digests|no input digests"):
        T.resolve_vintage_seam(p, False, DIGESTS)


def test_a_PASSED_golden_MISSING_ONE_digest_the_batch_recorded_is_refused(tmp_path):
    """Set EQUALITY, not subset containment: dropping one key from the report must not
    buy admission for that input. This is the passed-path twin of the seam path's
    existing unbound-key check."""
    partial = _passed_report()
    digests = {k: v for k, v in partial["input_digests"].items()
               if k != "gmm_artifact_sha256"}
    partial["input_digests"] = digests
    p = _write(tmp_path, partial)
    with pytest.raises(ValueError, match="lacks input digest.*gmm_artifact_sha256"):
        T.resolve_vintage_seam(p, False, DIGESTS)


def test_a_PASSED_golden_ON_THE_CURRENT_VINTAGE_still_admits(tmp_path):
    """Anti-vacuity: the three refusals above must come from the vintage mismatch, not
    from a gate that now refuses every passed golden."""
    p = _write(tmp_path, _passed_report())
    assert T.resolve_vintage_seam(p, False, DIGESTS) is None
