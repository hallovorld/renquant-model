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
  (h) per-date weekly-cadence momentum serving (review m221-r2): each
      scored day maps to its OWN latest weekly cutoff <= that day, the
      arm is asked for exactly the scheduled cutoffs, and a later date
      is provably scored by the later cutoff's (changed) score map;
  (i) cross-PR contract pin (review m221-r1): the COMMITTED artifacts
      in doc/design/frozen/ carry exactly the shapes the orch#956
      join-only consumer reads — nested manifest sha pins that
      recompute over the committed files, top-level fold_<n> stamps
      with regimes maps, the frozen scores CSV header — so a producer-
      side schema change breaks tests here before it breaks the
      orchestrator handoff.
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
    # (f) golden-check failure -> the failing cutoffs' dates drop the
    # leg, degradation recorded per cutoff, composite degrades to
    # z(panel) alone but scores + stamps still emit
    res = _run(world, world["closes_mono"], mom_arm=_mom_arm_dropped)
    assert res["meta"]["momentum_degraded"] is True
    vm = res["meta"]["validation"]["momentum"]
    tm = res["meta"]["test"]["momentum"]
    assert vm["dropped_cutoffs"] == sorted(vm["cutoffs"])
    assert tm["dropped_cutoffs"] == sorted(tm["cutoffs"])
    dropped_days = [d for d, r in
                    res["meta"]["test"]["degenerate_leg_days"].items()
                    if "momentum_dropped" in r]
    assert len(dropped_days) == res["meta"]["test"]["n_days"]
    assert len(res["scores"]) > 0
    assert np.isfinite(res["scores"]["recipe_score"]).all()
    assert "BULL_CALM" in res["stamps"]["regimes"]


def test_per_date_weekly_cutoff_schedule(world, run_mono):
    # (h) review m221-r2: every scored day is served by its OWN latest
    # weekly cutoff <= that day (live publish cadence), never one
    # segment-fixed artifact; the schedule is emitted per fold
    grid = world["grid"]
    for seg in ("validation", "test"):
        sched = run_mono["meta"][seg]["momentum"]["cutoff_schedule"]
        assert sched, seg
        for d, c in sched.items():
            assert c == qp.serving_cutoff(grid, d)
            assert c <= d
        by_date = [sched[d] for d in sorted(sched)]
        assert by_date == sorted(by_date)      # cutoffs advance with the date
        assert len(set(by_date)) > 1           # genuinely weekly, not fixed
    assert len(run_mono["meta"]["validation"]["momentum"]["cutoff_schedule"]) \
        == run_mono["meta"]["validation"]["n_entry_days"]
    assert len(run_mono["meta"]["test"]["momentum"]["cutoff_schedule"]) \
        == run_mono["meta"]["test"]["n_days"]


def test_run_fold_requests_every_scheduled_cutoff(world):
    # (h) wiring: run_fold asks the arm for EXACTLY the scheduled
    # cutoffs, memoised one compute per cutoff — not the r1 two-cutoff
    # shape (one per segment)
    calls: list[str] = []

    def capturing_arm(cutoff):
        calls.append(cutoff)
        return _mom_arm(cutoff)

    res = _run(world, world["closes_mono"], mom_arm=capturing_arm)
    want = (set(res["meta"]["validation"]["momentum"]["cutoff_schedule"].values())
            | set(res["meta"]["test"]["momentum"]["cutoff_schedule"].values()))
    assert set(calls) == want
    assert len(calls) == len(set(calls))       # memoised per cutoff
    assert len(want) > 2                       # r1 served exactly 2 artifacts


def test_later_dates_use_later_cutoff_scores():
    # (h) the review's exact fixture: the weekly inputs CHANGE across
    # cutoffs — a later score date must be scored by the LATER cutoff's
    # map. Panel leg is degenerate (all zeros) so composite == z(mom).
    days = ["2017-05-15", "2017-05-22"]
    frame = pd.DataFrame({
        "date": np.repeat(days, 4),
        "ticker": np.tile(["A", "B", "C", "D"], 2),
        "panel_raw": 0.0,
    })
    up = {t: float(i) for i, t in enumerate(["A", "B", "C", "D"])}
    down = {t: -float(i) for i, t in enumerate(["A", "B", "C", "D"])}
    comp, reasons = qp.composite_over_frame(
        frame, {days[0]: up, days[1]: down})
    d0, d1 = comp[:4], comp[4:]
    assert d0[3] > d0[0]                       # early date: early map's ranking
    assert d1[3] < d1[0]                       # later date: the LATER map's
    assert np.allclose(d0, -d1)                # exact per-date maps, no bleed
    assert all("panel_degenerate" in v for v in reasons.values())


def test_frozen_momentum_fingerprint_literal():
    # (g) the freeze §4 fingerprint literal is the packaged recipe's own
    from renquant_model_momentum.train import (
        params_config_fingerprint,
        params_v0,
    )
    assert qp.FROZEN_MOMENTUM_FP == params_config_fingerprint(params_v0())


def test_committed_artifacts_match_consumer_contract():
    # (i) review m221-r1 regression pin: the committed handoff artifacts
    # ARE the shapes orch#956 reads (nested manifest sha pins, top-level
    # fold_<n> stamps, frozen CSV header), and the recorded shas
    # recompute over the committed files themselves.
    import hashlib

    frozen = REPO / "doc" / "design" / "frozen"
    man = json.loads((frozen / qp.MANIFEST_BASENAME).read_text())

    def _sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    # the consumer's exact pin paths (orch#956 runner: the pins dict)
    assert man["outputs"]["scores_csv"]["sha256"] == _sha(
        frozen / qp.SCORES_BASENAME)
    assert man["outputs"]["stamps_json"]["sha256"] == _sha(
        frozen / qp.STAMPS_BASENAME)
    assert man["inputs"]["frozen_corpus"]["sha256"] == qp.FROZEN_CORPUS_SHA256

    # expected_schedule: top-level, keyed "1".."8", the frozen day counts
    sched = man["expected_schedule"]
    assert sorted(sched) == sorted(str(i) for i in range(1, 9))
    assert tuple(len(sched[str(i)]) for i in range(1, 9)) \
        == qp.FROZEN_TEST_DAY_COUNTS

    # stamps: TOP-LEVEL fold_<n> objects with the consumer-read fields
    stamps = json.loads((frozen / qp.STAMPS_BASENAME).read_text())
    assert sorted(stamps) == sorted(f"fold_{i}" for i in range(1, 9))
    for fs in stamps.values():
        assert {"boundaries", "passed", "reason", "regimes"} <= set(fs)
        for st in fs["regimes"].values():
            assert {"eligible", "passed"} <= set(st)

    # scores CSV: the frozen header the consumer asserts verbatim
    with open(frozen / qp.SCORES_BASENAME) as f:
        assert f.readline().strip() == "fold,date,ticker,recipe_score,regime"
