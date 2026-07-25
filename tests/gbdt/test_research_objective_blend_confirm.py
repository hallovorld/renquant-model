"""Synthetic-data tests for the objective-blend confirmatory executor
(prereg `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md`,
script `scripts/research_objective_blend_confirm.py`).

These tests do NOT touch the panel, xgboost, or any production path — they
exercise `decide_verdict`, `block_bootstrap_ci`, and the
`serialize_result`/`deserialize_result`/`verdict_from_bundle` replay path
against hand-built series, pinning the frozen guard/decision-rule branches
and the round trip a reviewer needs to replay a persisted `--out` bundle
(model#68 review round 3 BLOCKER 1, round 4 "add focused synthetic tests
for the exact w50 guard and decision branches").
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SPEC_PATH = (Path(__file__).resolve().parents[2] / "scripts"
              / "research_objective_blend_confirm.py")
_spec = importlib.util.spec_from_file_location("research_objective_blend_confirm", _SPEC_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules["research_objective_blend_confirm"] = mod
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


# --- frozen constants are LOCKED (prereg — the whole point of a prereg) ------
def test_frozen_decision_rule_constants():
    assert mod.SEEDS == tuple(range(42, 52))
    assert len(mod.SEEDS) == 10
    assert mod.BLK == 60
    assert mod.TOP_N == 10
    assert mod.MIN_SEEDS_POSITIVE == 8


DATES = pd.bdate_range("2020-01-01", periods=300)


def _series(values, dates=DATES):
    return pd.Series(dict(zip(dates, values)))


# --- decide_verdict: the three decision branches -----------------------------
def test_decide_verdict_confirmed_needs_all_three_conditions():
    # CI lower bound > 0, >=8/10 seeds positive, winsorized guard >= 0
    assert mod.decide_verdict(ci_lo=0.001, diff_mean=0.05, n_pos=8, wins_diff=0.0) == "CONFIRMED"
    assert mod.decide_verdict(ci_lo=0.001, diff_mean=0.05, n_pos=10, wins_diff=0.02) == "CONFIRMED"


def test_decide_verdict_ci_touching_zero_is_not_confirmed():
    # lower bound exactly 0 does not satisfy "> 0"
    assert mod.decide_verdict(ci_lo=0.0, diff_mean=0.05, n_pos=10, wins_diff=0.02) != "CONFIRMED"


def test_decide_verdict_seed_instability_blocks_confirmed_even_with_positive_ci():
    out = mod.decide_verdict(ci_lo=0.01, diff_mean=0.05, n_pos=7, wins_diff=0.02)
    assert out != "CONFIRMED"
    assert out == "INCONCLUSIVE"


def test_decide_verdict_negative_winsorized_guard_blocks_confirmed():
    out = mod.decide_verdict(ci_lo=0.01, diff_mean=0.05, n_pos=10, wins_diff=-0.01)
    assert out != "CONFIRMED"
    assert out == "INCONCLUSIVE"


def test_decide_verdict_refuted_on_nonpositive_point_estimate():
    assert mod.decide_verdict(ci_lo=-0.05, diff_mean=-0.01, n_pos=3, wins_diff=-0.02) == "REFUTED"
    assert mod.decide_verdict(ci_lo=-0.05, diff_mean=0.0, n_pos=3, wins_diff=-0.02) == "REFUTED"


def test_decide_verdict_inconclusive_when_ci_spans_zero_but_point_estimate_positive():
    out = mod.decide_verdict(ci_lo=-0.01, diff_mean=0.03, n_pos=9, wins_diff=0.01)
    assert out == "INCONCLUSIVE"


# --- block_bootstrap_ci: deterministic, seed-controlled -----------------------
def test_block_bootstrap_ci_is_deterministic_for_a_fixed_seed():
    diff = _series(np.random.default_rng(0).normal(0.02, 0.05, len(DATES)))
    lo1, hi1 = mod.block_bootstrap_ci(diff, n_boot=500)
    lo2, hi2 = mod.block_bootstrap_ci(diff, n_boot=500)
    assert (lo1, hi1) == (lo2, hi2)


def test_block_bootstrap_ci_brackets_the_mean_for_a_clear_positive_signal():
    diff = _series(np.full(len(DATES), 0.05) + np.random.default_rng(1).normal(0, 0.005, len(DATES)))
    lo, hi = mod.block_bootstrap_ci(diff, n_boot=500)
    assert lo < diff.mean() < hi
    assert lo > 0  # signal swamps the noise -> CI should clear zero


def test_block_bootstrap_ci_spans_zero_for_pure_noise():
    diff = _series(np.random.default_rng(2).normal(0.0, 0.05, len(DATES)))
    lo, hi = mod.block_bootstrap_ci(diff, n_boot=500)
    assert lo < 0 < hi


# --- serialize/deserialize round trip -> verdict_from_bundle -----------------
def _make_clean_series(rng_seed=1, blend_bias=0.05, rank60_bias=0.02, noise=0.01):
    rng = np.random.default_rng(rng_seed)
    blend_by_seed, rank60_by_seed = {}, {}
    for seed in mod.SEEDS:
        blend_by_seed[seed] = _series(blend_bias + rng.normal(0, noise, len(DATES)))
        rank60_by_seed[seed] = _series(rank60_bias + rng.normal(0, noise, len(DATES)))
    blend_df = pd.DataFrame(blend_by_seed)
    rank60_df = pd.DataFrame(rank60_by_seed)
    return {
        "blend": blend_df.mean(axis=1).sort_index(),
        "rank60": rank60_df.mean(axis=1).sort_index(),
        "blend_w50": blend_df.mean(axis=1).sort_index() * 0.2,
        "rank60_w50": rank60_df.mean(axis=1).sort_index() * 0.2,
        "blend_by_seed": blend_df,
        "rank60_by_seed": rank60_df,
    }


def _direct_verdict(clean_series):
    a, b_ = clean_series["blend"], clean_series["rank60"]
    c = a.index.intersection(b_.index)
    diff = (a[c] - b_[c]).sort_index()
    aw, bw = clean_series["blend_w50"], clean_series["rank60_w50"]
    cw = aw.index.intersection(bw.index)
    wins_diff_series = (aw[cw] - bw[cw]).sort_index()
    lo, hi = mod.block_bootstrap_ci(diff)
    by_seed_a, by_seed_b = clean_series["blend_by_seed"], clean_series["rank60_by_seed"]
    seed_signs = []
    for s in mod.SEEDS:
        ca, cb = by_seed_a[s].dropna(), by_seed_b[s].dropna()
        cc = ca.index.intersection(cb.index)
        seed_signs.append(float((ca[cc] - cb[cc]).mean()))
    n_pos = sum(1 for x in seed_signs if x > 0)
    verdict = mod.decide_verdict(lo, float(diff.mean()), n_pos, float(wins_diff_series.mean()))
    return diff, wins_diff_series, {"diff_mean": float(diff.mean()), "ci90": [lo, hi],
                                     "seeds_positive": n_pos,
                                     "winsorized_w50_diff": float(wins_diff_series.mean()),
                                     "verdict": verdict}


def test_serialize_deserialize_round_trip_reproduces_verdict():
    clean_series = _make_clean_series()
    diff, wins_diff_series, expected = _direct_verdict(clean_series)

    import json as _json
    payload = _json.loads(_json.dumps(
        mod.serialize_result(clean_series, diff, wins_diff_series)))
    bundle = mod.deserialize_result(payload)
    reloaded = mod.verdict_from_bundle(bundle)

    assert reloaded["verdict"] == expected["verdict"]
    assert reloaded["seeds_positive"] == expected["seeds_positive"]
    assert reloaded["diff_mean"] == pytest.approx(expected["diff_mean"])
    assert reloaded["ci90"] == pytest.approx(expected["ci90"])
    assert reloaded["winsorized_w50_diff"] == pytest.approx(expected["winsorized_w50_diff"])


def test_serialize_deserialize_round_trip_on_a_refuted_case():
    clean_series = _make_clean_series(rng_seed=5, blend_bias=0.01, rank60_bias=0.03, noise=0.02)
    diff, wins_diff_series, expected = _direct_verdict(clean_series)
    assert expected["verdict"] in ("REFUTED", "INCONCLUSIVE")  # sanity: this fixture is not a win

    import json as _json
    payload = _json.loads(_json.dumps(
        mod.serialize_result(clean_series, diff, wins_diff_series)))
    bundle = mod.deserialize_result(payload)
    reloaded = mod.verdict_from_bundle(bundle)
    assert reloaded["verdict"] == expected["verdict"]


def test_serialized_bundle_carries_per_seed_series_not_just_the_average():
    clean_series = _make_clean_series()
    diff, wins_diff_series, _ = _direct_verdict(clean_series)
    payload = mod.serialize_result(clean_series, diff, wins_diff_series)
    assert set(payload["blend_by_seed"]) == {str(s) for s in mod.SEEDS}
    assert set(payload["rank60_by_seed"]) == {str(s) for s in mod.SEEDS}
    assert "diff_by_date" in payload
    assert "wins_diff_by_date" in payload


# --- manifest: digests + pre-run-freeze timestamps ----------------------------
def test_build_manifest_digests_command_and_timestamps(tmp_path):
    from renquant_model_gbdt.panel_data import PANEL_FILE

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / PANEL_FILE).write_bytes(b"fake panel bytes")

    manifest = mod.build_manifest(
        data_dir=data_dir, argv=["research_objective_blend_confirm.py", "--out", "x.json"],
        run_started_at="2026-07-25T08:00:00+00:00",
        run_finished_at="2026-07-25T09:00:00+00:00")

    assert manifest["data_digest"] == "sha256:" + mod._sha256_file(data_dir / PANEL_FILE)
    assert manifest["prereg_digest"] == "sha256:" + mod._sha256_file(mod.PREREG_PATH)
    assert manifest["command"] == "research_objective_blend_confirm.py --out x.json"
    assert manifest["code_revision"]  # non-empty: a real SHA inside this repo's checkout
    assert manifest["run_started_at"] == "2026-07-25T08:00:00+00:00"
    assert manifest["run_finished_at"] == "2026-07-25T09:00:00+00:00"


def test_build_manifest_missing_data_file_reports_none_digest_not_a_crash(tmp_path):
    manifest = mod.build_manifest(
        data_dir=tmp_path / "nope", argv=["x"],
        run_started_at="t0", run_finished_at="t1")
    assert manifest["data_digest"] is None
    # the prereg file itself is real (committed in this repo) -> always present
    assert manifest["prereg_digest"] is not None
