"""Auditable control surface for scripts/qp_evidence_scorer.py (orch#955 §7).

Synthetic rehearsal fixture (model#220 convention — committed BEFORE the
real run): a small fake corpus whose label and 5d price outcomes are both
PLANTED monotone in a per-ticker rank, so the nested gate-fit/validation
replay must produce passed=True stamps; a price world with the SAME
scores but inverted outcomes must produce passed=False. The stamps come
from the PRODUCTION scripts/trade_monotonicity.py, loaded verbatim from
the sibling RenQuant checkout (skipped loudly where that checkout is
absent — the repo's sealed-runner-mirror tests use the same policy).

Controls:
  (a) planted monotone -> per-regime passed=True; anti-monotone ->
      passed=False (eligible, negative spearman/spread);
  (b) determinism — two full run_fold passes produce byte-identical
      scores CSV bytes and identical stamps JSON;
  (c) leak guard — a validation day injected into the emitted test
      scores fails loudly; so do schedule gaps, a two-regime
      (fold, date) group, and unsorted rows (orch#956 contract);
  (d) manifest sha integrity — recorded output shas recompute; a
      corrupted artifact is detected;
  (e) momentum golden checks — a real train_momentum_artifact over
      synthetic readers passes all checks; a tampered artifact fails;
  (f) a dropped momentum leg records the degradation flag and still
      emits scores + stamps (freeze §4 fallback: z(panel) alone);
  (g) the frozen momentum fingerprint literal matches params_v0();
  (h) live weekly cadence through the test fold (review P0 2026-08-10):
      two adjacent test days straddling a weekly cutoff are scored by
      DIFFERENT momentum artifacts when the recipe outputs differ.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

_spec = importlib.util.spec_from_file_location(
    "qp_evidence_scorer", REPO / "scripts" / "qp_evidence_scorer.py")
qp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qp)

N_TICKERS = 14
TICKERS = [f"T{i:02d}" for i in range(N_TICKERS)]
FEATS = ["F1", "F2", "F3", "F4", "F5", "F6"]
CUT = ("2015-01-05", "2017-03-31", "2017-05-15", "2017-06-30")
N_ROUNDS = 25  # test-speed knob only; the real run uses DEFAULT_N_ROUNDS


def _renquant_root():
    root = qp.find_renquant_root(REPO)
    if root is None:
        pytest.skip("sibling RenQuant checkout absent — the verbatim "
                    "production trade_monotonicity module cannot be loaded "
                    "(same policy as the sealed-runner mirror tests)")
    return root


@pytest.fixture(scope="module")
def world():
    """Synthetic corpus + two price worlds + injected legs/regime."""
    rng = np.random.default_rng(20260810)
    sessions = list(pd.bdate_range("2015-01-05", "2017-06-30")
                    .strftime("%Y-%m-%d"))
    n = len(sessions) * N_TICKERS
    rank = np.tile(np.arange(N_TICKERS, dtype=float), len(sessions))
    corpus = pd.DataFrame({
        "date": np.repeat(sessions, N_TICKERS),
        "ticker": np.tile(TICKERS, len(sessions)),
    })
    corpus["F1"] = rank + 0.05 * rng.normal(size=n)
    for c in FEATS[1:]:
        corpus[c] = rng.normal(size=n)
    corpus[qp.LABEL] = corpus["F1"].values + 0.5 * rng.normal(size=n)

    dt_index = pd.to_datetime(sessions)
    k = np.arange(len(sessions), dtype=float)

    def price_world(monotone_up: bool):
        closes = {}
        for i, t in enumerate(TICKERS):
            g = 0.001 * (i if monotone_up else (N_TICKERS - 1 - i))
            closes[t] = pd.Series(100.0 * (1.0 + g) ** k, index=dt_index)
        return closes

    spy = pd.Series(100.0, index=dt_index)
    idx = {d: i for i, d in enumerate(sessions)}
    return {
        "corpus": corpus, "sessions": sessions, "idx": idx,
        "ep": qp.endpoint_map(sessions),
        "grid": qp.weekly_cutoff_grid(sessions),
        "closes_mono": price_world(True),
        "closes_anti": price_world(False),
        "spy": spy,
    }


def _mom_arm(cutoff):
    return ({t: float(i) for i, t in enumerate(TICKERS)},
            {"cutoff": cutoff, "dropped": False, "golden_failures": []})


def _mom_arm_dropped(cutoff):
    return (None, {"cutoff": cutoff, "dropped": True,
                   "golden_failures": ["content_sha_mismatch:test"]})


def _run(world, closes, mom_arm=_mom_arm):
    evaluator = qp.load_monotonicity_evaluator(_renquant_root())
    return qp.run_fold(
        world["corpus"], FEATS, world["sessions"], world["idx"], world["ep"],
        CUT, 1,
        close_of=lambda t: closes.get(t), spy_close=world["spy"],
        regime_of=lambda d: "BULL_CALM", momentum_arm=mom_arm,
        evaluator=evaluator, weekly_grid=world["grid"],
        num_boost_round=N_ROUNDS)


@pytest.fixture(scope="module")
def run_mono(world):
    return _run(world, world["closes_mono"])


@pytest.fixture(scope="module")
def run_anti(world):
    return _run(world, world["closes_anti"])


def test_planted_monotone_passes_and_anti_fails(run_mono, run_anti):
    # (a) the designed criteria, verbatim thresholds, on planted worlds
    mono = run_mono["stamps"]["regimes"]["BULL_CALM"]
    assert mono["eligible"] and mono["n"] >= 30
    assert mono["passed"] is True
    assert mono["spearman"] > 0.5 and mono["top_bottom_return_spread"] > 0
    assert run_mono["stamps"]["passed"] is True

    anti = run_anti["stamps"]["regimes"]["BULL_CALM"]
    assert anti["eligible"]
    assert anti["passed"] is False
    assert anti["spearman"] < 0
    assert run_anti["stamps"]["passed"] is False

    # boundaries recorded and internally consistent
    b = run_mono["meta"]["boundaries"]
    assert b["validation_start"] > b["gate_fit_end"]
    assert b["train_end"] < b["test_start"]
    assert run_mono["meta"]["validation"]["n_segment_days"] == 252
    assert run_mono["meta"]["validation"]["n_entry_days"] == 247
    # every validation trade exits on/before train_end (freeze §4)
    assert run_mono["trades"]["exit_date"].max() <= b["train_end"]

    # emitted surface: label-free score rows over the test interval only
    sc = run_mono["scores"]
    assert list(sc.columns) == ["fold", "date", "ticker",
                                "recipe_score", "regime"]
    assert sc["date"].min() >= CUT[2] and sc["date"].max() <= CUT[3]


def test_determinism_across_two_runs(world, run_mono):
    # (b) byte-identical scores CSV + identical stamps across runs
    again = _run(world, world["closes_mono"])
    assert (run_mono["scores"].to_csv(index=False)
            == again["scores"].to_csv(index=False))
    assert (json.dumps(run_mono["stamps"], sort_keys=True)
            == json.dumps(again["stamps"], sort_keys=True))


def test_leak_and_contract_guards(world, run_mono):
    # (c) a validation day leaking into the emitted test scores is loud
    b = run_mono["meta"]["boundaries"]
    bounds = {1: b}
    qp.assert_no_validation_leak(run_mono["scores"], bounds)  # clean passes
    leak_day = world["sessions"][world["idx"][b["train_end"]] - 10]
    leaked = pd.concat([run_mono["scores"], pd.DataFrame([{
        "fold": 1, "date": leak_day, "ticker": "T00",
        "recipe_score": 0.0, "regime": "BULL_CALM"}])], ignore_index=True)
    with pytest.raises(AssertionError, match="boundary violated"):
        qp.assert_no_validation_leak(leaked, bounds)

    # orch#956 contract: schedule coverage, one regime per (fold, date),
    # (fold, date, ticker) sort order
    schedule = qp.expected_schedule(world["sessions"], bounds)
    assert schedule["1"] == [d for d in world["sessions"]
                             if CUT[2] <= d <= CUT[3]]
    qp.assert_scores_contract(run_mono["scores"], schedule)  # clean passes
    gap = run_mono["scores"][run_mono["scores"]["date"] != schedule["1"][0]]
    with pytest.raises(AssertionError, match="coverage"):
        qp.assert_scores_contract(gap.reset_index(drop=True), schedule)
    two_regime = run_mono["scores"].copy().reset_index(drop=True)
    two_regime.loc[0, "regime"] = "BEAR"
    with pytest.raises(AssertionError, match="regime"):
        qp.assert_scores_contract(two_regime, schedule)
    shuffled = run_mono["scores"].iloc[::-1].reset_index(drop=True)
    with pytest.raises(AssertionError, match="sorted"):
        qp.assert_scores_contract(shuffled, schedule)


def test_manifest_sha_integrity(run_mono, tmp_path):
    # (d) recorded output shas recompute; corruption is detected
    outputs = qp.write_outputs(tmp_path, run_mono["scores"],
                               {"fold_1": run_mono["stamps"]})
    manifest = {"outputs": outputs}
    qp.verify_output_shas(manifest, tmp_path)  # clean passes
    with open(tmp_path / qp.SCORES_BASENAME, "ab") as f:
        f.write(b"\ncorruption")
    with pytest.raises(AssertionError, match="sha mismatch"):
        qp.verify_output_shas(manifest, tmp_path)


class _SyntheticMomentumReaders:
    """Deterministic in-memory MomentumReaders (60 names, ample history)."""

    def __init__(self, cutoff: str, n_names: int = 60):
        rng = np.random.default_rng(7)
        end = pd.Timestamp(cutoff)
        idx = pd.bdate_range(end=end, periods=320)
        self.names = [f"M{i:02d}" for i in range(n_names)]
        self._r = {t: pd.Series(0.01 * rng.standard_normal(len(idx)),
                                index=idx) for t in self.names}
        self._v = {t: pd.Series(rng.uniform(1e5, 1e6, len(idx)), index=idx)
                   for t in self.names}
        self._m = pd.Series(0.008 * rng.standard_normal(len(idx)), index=idx)

    def tr_returns(self, t):
        return self._r.get(t)

    def volume(self, t):
        return self._v.get(t)

    def market_tr_returns(self):
        return self._m

    def sector_of(self):
        return {t: f"S{i % 5}" for i, t in enumerate(self.names)}

    def read_digests(self):
        return {}


def test_momentum_golden_checks_real_artifact_and_tamper():
    # (e) the frozen recipe over synthetic readers clears every golden
    # check; tampering trips them (drop-the-leg machinery is real)
    from renquant_model_momentum.train import (
        params_v0,
        train_momentum_artifact,
    )
    readers = _SyntheticMomentumReaders("2017-03-31")
    artifact = train_momentum_artifact(
        pd.Timestamp("2017-03-31"), readers.names, params_v0(),
        readers=readers)
    assert qp.momentum_golden_checks(artifact) == []
    assert artifact["names_floor_ok"]

    tampered = json.loads(json.dumps(artifact))
    victim = next(t for t, s in tampered["scores"].items() if s is not None)
    tampered["scores"][victim] = float(tampered["scores"][victim]) + 0.1
    fails = qp.momentum_golden_checks(tampered)
    assert any(f.startswith("content_sha_mismatch") for f in fails)
    assert any(f.startswith("scores_reconstruction_mismatch") for f in fails)


def test_dropped_momentum_leg_records_degradation(world):
    # (f) golden-check failure -> leg dropped, flag recorded, composite
    # degrades to z(panel) alone but scores + stamps still emit
    res = _run(world, world["closes_mono"], mom_arm=_mom_arm_dropped)
    assert res["meta"]["momentum_degraded"] is True
    assert res["meta"]["validation"]["momentum"]["dropped"] is True
    mom_t = res["meta"]["test"]["momentum"]
    assert mom_t["n_serving_cutoffs"] >= 1
    assert mom_t["dropped_cutoffs"] == sorted(mom_t["serving_cutoffs"])
    assert len(res["scores"]) > 0
    assert np.isfinite(res["scores"]["recipe_score"]).all()
    assert "BULL_CALM" in res["stamps"]["regimes"]


def test_momentum_cadence_advances_through_test_fold(world):
    # (h) review P0 2026-08-10: the full-train momentum leg must advance
    # weekly THROUGH the test fold — adjacent test days straddling a
    # weekly cutoff are scored by DIFFERENT artifacts when the recipe
    # outputs differ. The post-FLIP artifact scores only half the
    # universe, so days it serves carry NaN composites for the unscored
    # names: a threshold-free value-level proof the serving leg advanced.
    FLIP = "2017-06-01"
    HALF = set(TICKERS[:7])

    def flip_arm(cutoff):
        info = {"cutoff": cutoff, "dropped": False, "golden_failures": []}
        if cutoff < FLIP:
            return ({t: float(i) for i, t in enumerate(TICKERS)}, info)
        return ({t: float(i) for i, t in enumerate(TICKERS) if t in HALF},
                info)

    res = _run(world, world["closes_mono"], mom_arm=flip_arm)
    mom = res["meta"]["test"]["momentum"]
    assert mom["n_serving_cutoffs"] >= 2
    serving = sorted(mom["serving_cutoffs"])
    assert any(c < FLIP for c in serving) and any(c >= FLIP for c in serving)

    sc = res["scores"]
    test_days = sorted(sc["date"].unique())
    cmap = qp.serving_cutoff_map(world["grid"], test_days)
    flip_days = [d for d in test_days if cmap[d] >= FLIP]
    assert flip_days, "no test day served by a post-flip cutoff"
    d2 = flip_days[0]
    d1 = test_days[test_days.index(d2) - 1]
    assert cmap[d1] < FLIP, "the straddle pair must span the flip cutoff"
    assert world["idx"][d2] == world["idx"][d1] + 1  # adjacent sessions
    g1 = sc[sc["date"] == d1]
    g2 = sc[sc["date"] == d2]
    fin1 = g1[np.isfinite(g1["recipe_score"].astype(float))]
    fin2 = g2[np.isfinite(g2["recipe_score"].astype(float))]
    assert len(fin1) == N_TICKERS          # pre-flip artifact scored all
    assert set(fin2["ticker"]) == HALF     # post-flip artifact: its half


def test_frozen_momentum_fingerprint_literal():
    # (g) the freeze §4 fingerprint literal is the packaged recipe's own
    from renquant_model_momentum.train import (
        params_config_fingerprint,
        params_v0,
    )
    assert qp.FROZEN_MOMENTUM_FP == params_config_fingerprint(params_v0())
