"""Tests for the shadow top-decile classifier trainer (pipeline#213 step 3)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[2] / "scripts" / "train_topdecile_clf_shadow.py"
spec = importlib.util.spec_from_file_location("tdc", _P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_output_guard(tmp_path):  # name must not contain the guard keyword — pytest embeds test names in tmp_path
    with pytest.raises(SystemExit):
        mod.refuse_non_shadow(tmp_path / "artifacts" / "x.json")
    with pytest.raises(SystemExit):
        mod.refuse_non_shadow(tmp_path / "artifacts" / "prod" / "shadow.json")
    ok = tmp_path / "artifacts" / "shadow" / "x.json"
    assert mod.refuse_non_shadow(ok) == ok


def test_output_guard_rejects_substring_only_bypass():
    """Regression guard: a path containing the SUBSTRING "shadow" without a
    literal ``shadow`` path component (or with a compound production-adjacent
    component) must be refused, not just paths tokenized on "/"."""
    with pytest.raises(SystemExit):
        mod.refuse_non_shadow(Path("/tmp/prod/shadow.json"))
    with pytest.raises(SystemExit):
        mod.refuse_non_shadow(Path("/tmp/production-shadow/model.json"))


def test_top_decile_label_is_per_date_and_10pct():
    rng = np.random.default_rng(0)
    rows = []
    for d in pd.date_range("2024-01-02", periods=5, freq="B"):
        rows.append(pd.DataFrame({"date": d, "fwd_60d_excess": rng.normal(size=100)}))
    df = pd.concat(rows, ignore_index=True)
    y = mod.top_decile_label(df)
    per_day = y.groupby(df["date"]).mean()
    assert np.allclose(per_day.values, 0.10, atol=0.02)  # ~10% positives each date
    # per-DATE, not global: shift one date's labels up massively; its top decile
    # must still be 10% of that date, not dominate globally
    df2 = df.copy()
    first = df2["date"] == df2["date"].min()
    df2.loc[first, "fwd_60d_excess"] += 100.0
    y2 = mod.top_decile_label(df2)
    assert np.allclose(y2.groupby(df2["date"]).mean().values, 0.10, atol=0.02)


def test_frozen_params_match_confirmatory_executor():
    """The clf leg's params must stay byte-identical to the frozen
    construction in the confirmatory executor (single source drift guard)."""
    exe = (Path(__file__).resolve().parents[2] / "scripts"
           / "research_objective_blend_confirm.py").read_text()
    for k, v in mod.CLF_PARAMS.items():
        assert f'"{k}"' in exe, f"param {k} missing from confirmatory executor"
    assert '"binary:logistic"' in exe
    assert mod.N_ROUNDS == 100 and mod.TOP_DECILE == 0.9


def _toy_artifact():
    xgb = pytest.importorskip("xgboost")
    from renquant_model_gbdt.panel_trainer import build_model_artifact

    rng = np.random.default_rng(3)
    feat_cols = ["f0", "f1", "f2"]
    X = rng.standard_normal((64, len(feat_cols)))
    y = rng.integers(0, 2, size=64).astype(float)
    booster = xgb.train({"objective": "binary:logistic", "verbosity": 0},
                        xgb.DMatrix(X, label=y), num_boost_round=5)
    train = pd.DataFrame({"ticker": ["A"] * 64,
                          "date": pd.date_range("2024-01-02", periods=64, freq="B")})
    artifact = build_model_artifact(
        booster, feat_cols, np.zeros(len(feat_cols)), np.ones(len(feat_cols)), train,
        params={"objective": "binary:logistic"}, num_boost_round=5)
    return artifact, booster, feat_cols


def test_stamp_contract_adds_fingerprint_and_smoke():
    """Artifact-level contract test (Codex HIGH 1): the driver must layer the
    same fingerprint/smoke fields the production contract path stamps, not
    just the bare v3 payload."""
    from renquant_common.model_fingerprint import model_content_sha256

    artifact, booster, feat_cols = _toy_artifact()
    assert "config_fingerprint" not in artifact
    assert "metadata" not in artifact

    mod.stamp_contract(artifact, booster, feat_cols)

    assert isinstance(artifact["config_fingerprint"], str) and artifact["config_fingerprint"]
    # config_fingerprint/metadata are both OPERATIONAL (excluded from the
    # PREDICTIVE hash content), so stamping is idempotent/self-consistent.
    assert artifact["config_fingerprint"] == model_content_sha256(artifact)
    assert artifact["metadata"]["inference_smoke_test"]["all_finite"] is True
    assert artifact["metadata"]["inference_smoke_test"]["n"] == 32
    assert "score_sample_range" in artifact["metadata"]


def test_stamp_contract_must_run_before_shadow_only_fields():
    """Regression guard: a BARE top-level shadow-only key (shadow_role etc.)
    is NOT classified in renquant-common's fingerprint tables, so it must
    stay nested under the OPERATIONAL ``metadata`` envelope, never added as
    its own top-level key — this pins that a reintroduced bare top-level
    field (e.g. reverting main()'s ``artifact["metadata"][...]`` nesting
    back to ``artifact[...]``) is caught immediately by a hard failure
    rather than silently producing an unfingerprintable artifact."""
    from renquant_common.model_fingerprint import UnclassifiedKeyError

    artifact, booster, feat_cols = _toy_artifact()
    artifact["shadow_role"] = "blend_clf_leg"
    with pytest.raises(UnclassifiedKeyError):
        mod.stamp_contract(artifact, booster, feat_cols)


def test_full_artifact_with_shadow_fields_is_fingerprint_verifiable():
    """End-to-end contract test (Codex P1): main()'s actual sequence —
    stamp_contract, then nest shadow_role/blend_spec/classifier_label_spec
    under artifact["metadata"] (OPERATIONAL, not new top-level keys) — must
    leave the FINAL artifact hashable and round-trippable through the shared
    fingerprint contract, not just pin a failure on the unfixed shape."""
    from renquant_common.model_fingerprint import model_content_sha256, stamp, verify

    artifact, booster, feat_cols = _toy_artifact()
    mod.stamp_contract(artifact, booster, feat_cols)
    artifact["metadata"]["shadow_role"] = "blend_clf_leg"
    artifact["metadata"]["blend_spec"] = {
        "formula": "z(prod_score) + z(clf_score) per date",
        "prereg": "model#75 doc/research/2026-07-25-blend-confirmatory-v2-prereg.md"}
    artifact["metadata"]["classifier_label_spec"] = {
        "kind": "top_decile_membership", "base_label": "fwd_60d_excess",
        "threshold_pct": 0.9}

    # No UnclassifiedKeyError: every top-level key (incl. "metadata", whose
    # nested shadow fields are now present) is classified.
    fp = model_content_sha256(artifact)
    assert fp == artifact["config_fingerprint"]

    stamped = stamp(artifact)
    artifact.update(stamped)
    verify(artifact, stamped["model_content_fingerprint"], stamped["fingerprint_schema_version"])


def _synthetic_panel(n_dates: int = 10, n_labeled: int = 7) -> pd.DataFrame:
    """Panel whose trailing ``n_dates - n_labeled`` dates have NaN labels —
    the real fwd_60d shape (no forward label for the newest dates)."""
    rng = np.random.default_rng(7)
    dates = pd.date_range("2026-01-05", periods=n_dates, freq="B")
    rows = []
    for i, d in enumerate(dates):
        lab = rng.normal(size=20) if i < n_labeled else np.full(20, np.nan)
        rows.append(pd.DataFrame({"date": d, "ticker": [f"T{j}" for j in range(20)],
                                  "fwd_60d_excess": lab}))
    return pd.concat(rows, ignore_index=True)


def test_effective_train_cutoff_is_max_labeled_date_not_panel_max():
    """The honest cutoff = max date actually TRAINED on (post label-dropna),
    NOT the raw panel max — a trailing unlabeled window must be excluded."""
    panel = _synthetic_panel(n_dates=10, n_labeled=7)
    expected = sorted(panel["date"].unique())[6]  # 7th date = last labeled one
    got = mod.effective_train_cutoff(panel)
    assert got == pd.Timestamp(expected).strftime("%Y-%m-%d")
    assert got < pd.Timestamp(panel["date"].max()).strftime("%Y-%m-%d")
    # fully-labeled panel: cutoff == panel max (dropna is a no-op)
    full = _synthetic_panel(n_dates=5, n_labeled=5)
    assert mod.effective_train_cutoff(full) == pd.Timestamp(
        full["date"].max()).strftime("%Y-%m-%d")
    # all-NaN labels: refuse rather than stamp NaT
    with pytest.raises(SystemExit):
        mod.effective_train_cutoff(_synthetic_panel(n_dates=3, n_labeled=0))


def test_artifact_carries_top_level_effective_train_cutoff():
    """main()'s stamping sequence must put ``effective_train_cutoff_date``
    at the artifact TOP LEVEL — the runtime ``PanelScorer.load`` builds
    ``scorer.metadata`` from top-level payload keys, which is where the
    shadow health record reads it; nesting it under ``metadata`` instead
    would leave the field visible only through a DEPRECATED flatten shim
    (and, once that shim is removed, reproduce ``missing_train_cutoff``)."""
    artifact, booster, feat_cols = _toy_artifact()
    panel = _synthetic_panel()
    artifact["effective_train_cutoff_date"] = mod.effective_train_cutoff(panel)
    mod.stamp_contract(artifact, booster, feat_cols)
    assert artifact["effective_train_cutoff_date"] == "2026-01-13"  # 7th B-day from 01-05
    # top-level, not nested — the runtime reads top-level keys
    assert "effective_train_cutoff_date" not in artifact["metadata"]


def test_effective_train_cutoff_is_fingerprint_stable():
    """``effective_train_cutoff_date`` is OPERATIONAL-classified in
    renquant-common (training-window provenance), so stamping it must NOT
    move ``model_content_sha256`` / ``config_fingerprint`` — the deployed
    shadow artifact's fingerprint must survive the re-stamp unchanged."""
    from renquant_common.model_fingerprint import model_content_sha256

    artifact, booster, feat_cols = _toy_artifact()
    fp_without = model_content_sha256(artifact)
    artifact["effective_train_cutoff_date"] = "2026-04-28"
    mod.stamp_contract(artifact, booster, feat_cols)
    assert artifact["config_fingerprint"] == fp_without
    assert model_content_sha256(artifact) == fp_without
