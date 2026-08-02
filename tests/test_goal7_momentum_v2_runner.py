"""v2 runner tests: gap-block machine, frozen controls, decision map, NEW-dir claim.

Synthetic fixtures ONLY — no real IC/score/label statistic is computed here, and the
autouse fixture (the v1 test module's idiom) isolates every claim path from the
operator's real store before any test body runs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "goal7_momentum_v2_run", REPO / "tools" / "goal7_momentum_v2_run.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

#: Captured at import, BEFORE the autouse redirect: the runner's REAL predeclared
#: surfaces (asserted-on below, never written to).
_REAL_LEDGER = R.RUN_LEDGER_DIR
_REAL_V1_LEDGER = Path(R.V1.RUN_LEDGER_DIR)

_CLAIM_ATTRS = ("RUN_LEDGER_DIR", "EXECUTION_CLAIM", "RESULT_PATH", "REFUSALS_LOG")


def _redirect_claim(monkeypatch, tmp_path) -> Path:
    d = tmp_path / "v2-run-ledger"
    monkeypatch.setattr(R, "RUN_LEDGER_DIR", d)
    monkeypatch.setattr(R, "EXECUTION_CLAIM", d / "EXECUTION_CLAIM.json")
    monkeypatch.setattr(R, "RESULT_PATH", d / "result.json")
    monkeypatch.setattr(R, "REFUSALS_LOG", d / "refusals.jsonl")
    return d


@pytest.fixture(autouse=True)
def _never_touch_the_real_claim(monkeypatch, tmp_path):
    """AUTOUSE (v1 idiom): the safe path must not be opt-in — a forgetful test must
    land in tmp, never in the operator's durable v2 store."""
    _redirect_claim(monkeypatch, tmp_path)


def _boom(*a, **k):
    raise AssertionError("a component was touched that this path must never reach")


def _series_with_block_means(means: np.ndarray) -> np.ndarray:
    """A per-date IC series whose §2.1 blocks have EXACTLY the given means: block k
    occupies positions [k*40, k*40+20); gap positions are NaN (discarded anyway)."""
    n = len(means)
    v = np.full((n - 1) * 40 + 20 if n else 0, np.nan)
    for k, m in enumerate(means):
        v[k * 40:k * 40 + 20] = m
    return v


# ---------- the NEW predeclared run dir ----------


def test_the_predeclared_dir_is_the_NEW_v2_store_not_v1s():
    assert _REAL_LEDGER.name == "goal7-momentum-v2-prereg-run"
    assert _REAL_LEDGER.parent.name == "renquant-data-store"
    assert _REAL_LEDGER != _REAL_V1_LEDGER


def test_v2_frozen_constants_agree_with_the_carried_v1_pins():
    """h and the base seed are CARRIED from v1 (prereg §1/§3), not re-chosen."""
    assert R.FROZEN_V2["h"] == R.V1.FROZEN["h"] == 20
    assert R.FROZEN_V2["base_seed"] == R.V1.FROZEN["seed"] == 20260801


# ---------- §2.1 partition arithmetic ----------


def test_partition_at_the_v1_realized_T_gives_59_blocks():
    blocks = R.partition_blocks(2378, 20, 20)
    assert len(blocks) == 59
    assert blocks[0] == (0, 20)
    assert blocks[1] == (40, 60)
    assert blocks[-1] == (2320, 2340)
    assert all(hi - lo == 20 for lo, hi in blocks)


def test_partition_edge_lengths():
    assert R.partition_blocks(19, 20, 20) == []
    assert R.partition_blocks(20, 20, 20) == [(0, 20)]
    assert R.partition_blocks(59, 20, 20) == [(0, 20)]      # tail < full cycle: 1
    assert R.partition_blocks(60, 20, 20) == [(0, 20), (40, 60)]


def test_thin_dates_do_not_shift_the_partition():
    """Thin dates never ENTER the scored sequence (the loop skips them), so they
    change T only; NaNs INSIDE the sequence affect usability, never boundaries."""
    v = np.zeros(2378)
    v[100:600] = np.nan
    st = R.block_stats(v, 20, 20, 10)
    assert st["n_blocks_formed"] == 59


# ---------- §2.2 drop-and-count ----------


def test_blocks_with_too_few_usable_dates_are_dropped_and_counted():
    rng = np.random.default_rng(1)
    v = rng.normal(0.05, 0.01, 2378)
    v[2 * 40:2 * 40 + 11] = np.nan     # block 2 keeps 9 usable -> dropped
    v[5 * 40:5 * 40 + 5] = np.nan      # block 5 keeps 15 usable -> survives
    st = R.block_stats(v, 20, 20, 10)
    assert st["n_blocks_formed"] == 59
    assert st["n_dropped"] == 1
    assert st["n_surviving"] == 58
    assert st["usable_counts"][2] == 9
    assert st["usable_counts"][5] == 15
    # the surviving block-5 mean is over its 15 finite dates only; with block 2
    # dropped, block 5 sits at position 4 of the surviving means
    w = v[5 * 40:5 * 40 + 20]
    assert abs(st["means"][4] - w[np.isfinite(w)].mean()) < 1e-15


# ---------- §3.1(b): POWER before controls ----------


def test_too_few_surviving_blocks_is_POWER_and_controls_are_never_touched(monkeypatch):
    monkeypatch.setattr(R, "run_controls", _boom)
    monkeypatch.setattr(R, "t_bar", _boom)
    monkeypatch.setattr(np.random, "default_rng", _boom)   # no rng on this path
    v = np.full(30 * 40, 0.05)                             # T=1200 -> 30 blocks < 40
    rep, code = R.run_inference(v, v.copy(), 0.001)
    assert code == R.EXIT_UNRESOLVED_POWER == 6
    assert rep["status"] == "UNRESOLVED-POWER"
    assert rep["blocks_S"]["n_surviving"] == 30
    assert "controls" not in rep


# ---------- §3.1(c'): degenerate-scale valve ----------


def test_degenerate_block_sd_is_published_METHOD_and_controls_never_run(monkeypatch):
    monkeypatch.setattr(R, "run_controls", _boom)
    monkeypatch.setattr(R, "t_bar", _boom)
    # 0.5 is exactly representable, so the 59 identical block means give sd EXACTLY
    # 0.0 — the frozen §3.1(c') clause is literally "<= 0.0" (no invented epsilon;
    # a non-representable constant like 0.05 leaves sd ~ 1.4e-17, which the frozen
    # text does NOT treat as degenerate)
    v = np.full(2378, 0.5)
    rep, code = R.run_inference(v, v.copy(), 0.001)
    assert code == R.EXIT_UNRESOLVED_METHOD == 5
    assert rep["status"] == "UNRESOLVED-METHOD"
    assert rep["realized_block_sd"] == 0.0          # PUBLISHED, per §3.1(c')
    assert "rho1_blocks" not in rep                 # the sd valve fires FIRST
    assert "controls" not in rep


# ---------- §2.5: rho_1 valve ----------


def test_autocorrelated_block_means_trip_the_rho1_valve(monkeypatch):
    monkeypatch.setattr(R, "run_controls", _boom)
    v = _series_with_block_means(np.linspace(0.0, 0.058, 59))
    rep, code = R.run_inference(v, v.copy(), 0.001)
    assert code == 5
    assert rep["status"] == "UNRESOLVED-METHOD"
    assert abs(rep["rho1_blocks"]) >= R.FROZEN_V2["rho1_ceiling"]
    assert "rho_1" in rep["why"]
    assert "controls" not in rep


# ---------- §2.3 / §2.4: the t and its bar ----------


def test_one_sample_t_hand_checked():
    # mean 2.5, sd(ddof=1) = sqrt(5/3), n=4 -> t = 2.5/(sqrt(5/3)/2) = sqrt(15)
    assert abs(R.one_sample_t(np.array([1.0, 2.0, 3.0, 4.0])) - np.sqrt(15)) < 1e-12


def test_bar_matches_the_prereg_derived_value_at_df_58():
    assert round(R.t_bar(58), 4) == 2.0017


# ---------- §3.2: the frozen control generator, exactly ----------


def test_default_rng_is_PCG64_as_frozen():
    assert isinstance(np.random.default_rng(R.FROZEN_V2["base_seed"]).bit_generator,
                      np.random.PCG64)


def test_control_generator_is_the_frozen_recipe_exactly_tiny_case():
    """Hand-replicated rep-by-rep: default_rng(20260801 + r), exactly n draws of
    Normal(mu, sd), the §2.3 t, the H1 comparison t >= bar."""
    out = R.run_controls(0.0, 1.0, 4, 1.0, base_seed=20260801, n_reps=3)
    exp = []
    for r in range(3):
        d = np.random.default_rng(20260801 + r).normal(0.0, 1.0, 4)
        exp.append(bool(d.mean() / (d.std(ddof=1) / np.sqrt(4)) >= 1.0))
    assert out["per_rep_clear"] == "".join("1" if e else "0" for e in exp)
    assert out["n_clear"] == sum(exp)
    assert out["n_fail"] == 3 - sum(exp)
    assert out["rate"] == sum(exp) / 3


def test_controls_are_byte_reproducible_at_the_full_frozen_size():
    a = R.run_controls(0.04, 0.004, 59, 2.0017, base_seed=20260801, n_reps=1000)
    b = R.run_controls(0.04, 0.004, 59, 2.0017, base_seed=20260801, n_reps=1000)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["n_clear"] + a["n_fail"] == 1000
    assert len(a["per_rep_clear"]) == 1000


# ---------- §4 decision map ----------

_BAR = 2.0


def test_decision_map_mde_gate_first():
    d = R.decide(0.05, 5.0, _BAR, 0.001, 0.5, 0.05, 5.0, mde=0.061)
    assert d["verdict"] == "UNRESOLVED-POWER"


def test_decision_map_kill_on_mean():
    d = R.decide(0.039, 5.0, _BAR, 0.001, 0.5, 0.05, 5.0, mde=0.01)
    assert d["verdict"] == "KILL"


def test_decision_map_t_is_signed_not_absolute():
    """§4 writes t_S >= bar (SIGNED): a strongly NEGATIVE t must KILL even though
    |t| clears the bar — the v1 map used |t| and must not leak in."""
    d = R.decide(0.05, -3.0, _BAR, 0.001, 0.5, 0.05, 5.0, mde=0.01)
    assert d["verdict"] == "KILL"


def test_decision_map_kill_on_placebo():
    d = R.decide(0.05, 5.0, _BAR, 0.02, 0.5, 0.05, 5.0, mde=0.01)
    assert d["verdict"] == "KILL"


def test_decision_map_retain_f1():
    d = R.decide(0.05, 5.0, _BAR, 0.001, 1.0, 0.05, 4.0, mde=0.01)
    assert d["verdict"] == "RETAIN-F1"


def test_decision_map_retain_s_when_f1_does_not_independently_clear():
    d = R.decide(0.05, 5.0, _BAR, 0.001, 1.0, 0.03, 4.0, mde=0.01)
    assert d["verdict"] == "RETAIN-S"


def test_decision_map_retain_s_when_family_adds_value():
    d = R.decide(0.05, 5.0, _BAR, 0.001, 3.0, 0.05, 4.0, mde=0.01)
    assert d["verdict"] == "RETAIN-S"


# ---------- §3.1 end-to-end on synthetic series ----------


def test_full_inference_on_clean_synthetic_series_completes_RETAIN_S():
    rng = np.random.default_rng(20260802)
    s = rng.normal(0.05, 0.01, 2378)
    f1 = rng.normal(0.0, 0.01, 2378)
    rep, code = R.run_inference(s, f1, 0.001)
    assert code == 0
    assert rep["status"] == "COMPLETED"
    assert rep["blocks_S"]["n_surviving"] == 59
    assert rep["df"] == 58
    assert rep["controls"]["positive"]["ok"]
    assert rep["controls"]["negative"]["ok"]
    assert len(rep["controls"]["positive"]["per_rep_clear"]) == 1000
    assert rep["verdict"]["verdict"] == "RETAIN-S"


def test_full_inference_retain_f1_when_composite_adds_nothing():
    rng = np.random.default_rng(7)
    f1 = rng.normal(0.05, 0.01, 2378)
    s = f1 + rng.normal(0.0, 0.001, 2378)
    rep, code = R.run_inference(s, f1, 0.001)
    assert code == 0
    assert rep["verdict"]["verdict"] == "RETAIN-F1"


# ---------- v2 preflight additions ----------


def _stub_v1_preflight(monkeypatch, tmp_path):
    """The v1 check set is REUSED, not re-verified here (its own tests own it) —
    and letting it run for real would hash the operator's snapshot store."""
    monkeypatch.setattr(R.V1, "verify_preconditions",
                        lambda: {"checks": {}, "unresolved_data": [], "ok": True})
    a2 = tmp_path / "amendment-2.md"
    a2.write_text("present")
    monkeypatch.setattr(R.V1, "AMENDMENT_2", a2)


def test_preflight_requires_the_v2_prereg_and_the_v1_result(monkeypatch, tmp_path):
    _stub_v1_preflight(monkeypatch, tmp_path)
    monkeypatch.setattr(R, "V2_PREREG", tmp_path / "absent-prereg.md")
    monkeypatch.setattr(R.V1, "RESULT_PATH", tmp_path / "absent-v1-result.json")
    pre = R.verify_preconditions()
    assert not pre["ok"]
    assert "v2_prereg_present" in pre["unresolved_data"]
    assert "v1_result_present" in pre["unresolved_data"]
    assert pre["v2_prereg_sha256_at_run"] is None


def test_preflight_passes_and_records_the_v2_prereg_sha(monkeypatch, tmp_path):
    _stub_v1_preflight(monkeypatch, tmp_path)
    prereg = tmp_path / "v2-prereg.md"
    prereg.write_text("# the governing text\n")
    v1res = tmp_path / "v1-result.json"
    v1res.write_text("{}")
    monkeypatch.setattr(R, "V2_PREREG", prereg)
    monkeypatch.setattr(R.V1, "RESULT_PATH", v1res)
    pre = R.verify_preconditions()
    assert pre["ok"]
    assert pre["v2_prereg_sha256_at_run"] == hashlib.sha256(
        prereg.read_bytes()).hexdigest()


# ---------- single-execution guard on the NEW dir ----------


def test_second_invocation_is_refused_BEFORE_any_data_read(monkeypatch, tmp_path,
                                                           capsys):
    d = _redirect_claim(monkeypatch, tmp_path)
    d.mkdir(parents=True)
    (d / "EXECUTION_CLAIM.json").write_text('{"status": "consumed"}')
    monkeypatch.setattr(R, "verify_preconditions", _boom)
    monkeypatch.setattr(R.V1, "load_snapshot_manifest", _boom)
    rc = R.execute()
    assert rc == R.EXIT_ALREADY_EXECUTED == 4
    out = capsys.readouterr().out
    assert "ALREADY-EXECUTED" in out
    assert "result selection" in out


def test_concurrent_claim_is_atomic(monkeypatch, tmp_path):
    _redirect_claim(monkeypatch, tmp_path)
    assert R._claim_execution() is None            # first caller wins
    assert R._claim_execution() == 4               # second (concurrent) refused


def test_pre_inference_unresolved_data_releases_the_claim_but_is_LEDGERED(
        monkeypatch, tmp_path, capsys):
    d = _redirect_claim(monkeypatch, tmp_path)
    monkeypatch.setattr(R, "verify_preconditions", lambda: {
        "ok": False, "checks": {}, "unresolved_data": ["v2_prereg_present"]})
    rc = R.execute()
    assert rc == 3
    assert not (d / "EXECUTION_CLAIM.json").exists(), "identity refusal releases"
    lines = (d / "refusals.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert "v2_prereg_present" in lines[0]


def test_a_computed_outcome_CONSUMES_the_shot_and_seals_both_files(
        monkeypatch, tmp_path, capsys):
    d = _redirect_claim(monkeypatch, tmp_path)
    assert R._claim_execution() is None
    rc = R._finish({"status": "UNRESOLVED-POWER", "why": "synthetic"}, 6)
    assert rc == 6
    result = d / "result.json"
    claim = d / "EXECUTION_CLAIM.json"
    assert result.is_file() and (result.stat().st_mode & 0o777) == 0o444
    assert (claim.stat().st_mode & 0o777) == 0o444
    c = json.loads(claim.read_text())
    assert c["status"] == "consumed"
    assert c["exit_code"] == 6
    # the shot is gone even though the verdict was UNRESOLVED
    assert R._claim_execution() == 4


def test_execute_refuses_a_caller_selected_output(tmp_path, capsys):
    rc = R.main(["--execute", "--json-out", str(tmp_path / "x.json")])
    assert rc == 2
    assert "PREDECLARED" in capsys.readouterr().err


def test_cli_without_flags_is_usage_error(capsys):
    assert R.main([]) == 2


def test_NO_test_in_this_module_can_reach_the_real_claim_store(tmp_path):
    """The guard on the guard (v1 idiom): with the autouse fixture active, every
    claim path already points inside tmp_path."""
    for attr in _CLAIM_ATTRS:
        value = Path(getattr(R, attr))
        assert value.is_relative_to(tmp_path), f"{attr} -> {value}"
        assert "renquant-data-store" not in str(value), f"{attr} -> {value}"


def test_a_forgetful_test_still_cannot_consume_the_licence(monkeypatch, tmp_path):
    """End-to-end: run the real entry point with no isolation call of its own and
    confirm the claim lands in tmp and the operator's real v2 store is untouched
    (before/after listing, the v1 module's updated idiom)."""
    real = _REAL_LEDGER
    before = sorted(q.name for q in real.iterdir()) if real.exists() else None
    monkeypatch.setattr(R, "verify_preconditions", lambda: {
        "ok": False, "checks": {}, "unresolved_data": ["v2_prereg_present"]})
    R.execute()
    assert Path(R.EXECUTION_CLAIM).parent.is_relative_to(tmp_path)
    after = sorted(q.name for q in real.iterdir()) if real.exists() else None
    assert after == before, "the test leaked into the operator's real v2 store"
