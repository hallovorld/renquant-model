"""Stage-0 runner tests: geometry, statistics, determinism, decision maps, gates."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "goal6_stage0_run", REPO / "tools" / "goal6_stage0_run.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


# ------------------------------------------------------------- block geometry ----
def test_gap_blocks_worked_examples_from_amendment_3():
    assert R.n_eff(508, 20) == 13 and len(R.gap_blocks(508, 20)) == 13
    assert R.n_eff(508, 60) == 4 and len(R.gap_blocks(508, 60)) == 4
    assert R.n_eff(19, 20) == 0 and R.gap_blocks(19, 20) == []
    # terminal partial retained window discarded: T=59, h=20 -> retained [0,20),
    # gap [20,40), retained [40,60) INCOMPLETE -> only 1 block
    assert R.gap_blocks(59, 20) == [(0, 20)]
    assert R.n_eff(59, 20) == 1
    # no two blocks share any label window: consecutive starts differ by 2h
    b = R.gap_blocks(400, 20)
    assert all(b2[0] - b1[0] == 40 for b1, b2 in zip(b, b[1:]))


def test_gap_block_t_on_a_constant_series_has_zero_se_guard():
    out = R.gap_block_t(np.ones(200), 20)
    assert out["n_eff"] == 5 and out["t"] is None  # zero variance -> no t, not inf


# --------------------------------------------------------------- statistics ----
def test_per_date_stats_on_a_perfect_monotone_cross_section():
    idx = [f"T{i:02d}" for i in range(30)]
    scores = pd.Series(np.arange(30, dtype=float), index=idx)
    labels = pd.Series(np.arange(30, dtype=float) - 5.0, index=idx)
    st = R.per_date_stats(scores, labels)
    assert st["ic"] == pytest.approx(1.0)
    assert st["spread"] == pytest.approx(labels[-3:].mean() - labels[:3].mean())
    assert st["hit"] == 1.0 and st["n"] == 30


def test_per_date_stats_refuses_thin_cross_sections():
    idx = list("ABCDEFGHIJ")
    assert R.per_date_stats(pd.Series(range(10), index=idx, dtype=float),
                            pd.Series(range(10), index=idx, dtype=float)) is None


def _toy_arm(n_dates=8, n_names=25, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    rows = []
    for d in dates:
        for i in range(n_names):
            rows.append({"date": d, "ticker": f"T{i:02d}",
                         "score": float(rng.normal())})
    return pd.DataFrame(rows), dates


def _toy_labels(dates, n_names=25, seed=4):
    rng = np.random.default_rng(seed)
    return {d: pd.Series(rng.normal(size=n_names),
                         index=[f"T{i:02d}" for i in range(n_names)])
            for d in dates}


def test_permutation_arm_is_deterministic_across_calls():
    arm, dates = _toy_arm()
    labels = _toy_labels(dates)
    e1 = R.build_effect_series(arm, labels, 20)
    e2 = R.build_effect_series(arm, labels, 20)
    for k in R.STAT_KEYS:
        assert np.array_equal(e1["perm"][k], e2["perm"][k], equal_nan=True)


def test_persistence_arm_drop_rule_and_coverage(monkeypatch):
    """With lag=2 positions on an 8-date grid, the first 2 dates have no
    persistence cell; coverage counts real vs persist cells honestly."""
    monkeypatch.setitem(R.FROZEN, "persistence_lag_positions", 2)
    arm, dates = _toy_arm()
    labels = _toy_labels(dates)
    e = R.build_effect_series(arm, labels, 20)
    assert len(e["persist"]["dates"]) == len(e["dates"]) - 2
    cov = e["persist"]["coverage"]
    assert cov["cells_persist"] <= cov["cells_real"]
    assert cov["cells_persist"] > 0


# --------------------------------------------------------------- decisions ----
def _c(t, n=13, mean=None):
    return {"t": t, "n_eff": n, "df": n - 1,
            "mean": (mean if mean is not None else (0.1 if t and t > 0 else -0.1))}


def _veto_ok():
    return {"spread": {"t": 1.5, "mean": 0.02}, "hit": {"t": 1.5, "mean": 0.02}}


def test_h1_supported_when_both_tails_clear_and_holm_significant():
    contrasts = {"spread_vs_ic": _c(4.0), "hit_vs_ic": _c(3.5), "spread_vs_hit": _c(0.5)}
    own = {"ic": 1.0, "spread": 3.0, "hit": 2.5}
    out = R.decide_h1(contrasts, own, _veto_ok())
    assert out["verdict"] == "SUPPORTED" and out["primary_statistic"] == "spread"


def test_h1_without_veto_data_cannot_be_supported():
    """§5's veto applies to every hypothesis; absent veto data must fail CLOSED,
    not silently pass (the fail-open-default lesson)."""
    contrasts = {"spread_vs_ic": _c(4.0), "hit_vs_ic": _c(3.5), "spread_vs_hit": _c(0.5)}
    own = {"ic": 1.0, "spread": 3.0, "hit": 2.5}
    out = R.decide_h1(contrasts, own)          # no veto data at all
    assert out["verdict"] == "INCONCLUSIVE" and "persistence veto" in out["why"]


def test_h1_refuted_when_nothing_clears():
    contrasts = {"spread_vs_ic": _c(0.3), "hit_vs_ic": _c(-0.2), "spread_vs_hit": _c(0.1)}
    own = {"ic": 1.5, "spread": 0.4, "hit": 0.2}
    assert R.decide_h1(contrasts, own)["verdict"] == "REFUTED"


def test_h1_inconclusive_when_exactly_one_tail_clears():
    contrasts = {"spread_vs_ic": _c(4.0), "hit_vs_ic": _c(0.1), "spread_vs_hit": _c(2.0)}
    own = {"ic": 1.0, "spread": 3.0, "hit": 0.5}
    out = R.decide_h1(contrasts, own)
    assert out["verdict"] == "INCONCLUSIVE" and out["primary_statistic"] == "ic"


def test_h2_amendment2_suspension_c_failure_is_inconclusive_never_refuted():
    t_pair = {"t": 3.0, "mean": 0.05, "n_eff": 4, "df": 3}
    out = R.decide_h2(t_pair, own_t_20=2.5, d20=0.09, d60=0.05)  # (c) FAILS: d20 > d60
    assert out["verdict"] == "INCONCLUSIVE"
    assert "Amendment 2" in out["why"]


def test_h2_refuted_only_on_a_or_b():
    t_pair = {"t": 0.5, "mean": 0.01, "n_eff": 4, "df": 3}
    assert R.decide_h2(t_pair, own_t_20=2.5, d20=0.03, d60=0.05)["verdict"] == "REFUTED"


def test_holm_orders_by_p_and_stops_at_first_failure():
    sig = R.holm({"a": 0.001, "b": 0.04, "c": 0.5}, alpha=0.10)
    assert sig["a"] and sig["b"] and not sig["c"]
    # first bar is alpha/3 = 0.0333: p=0.05 fails it, and the sequential stop
    # keeps everything after the first failure non-significant; None never passes
    sig2 = R.holm({"a": 0.05, "b": 0.5, "c": None}, alpha=0.10)
    assert not sig2["a"] and not sig2["b"] and not sig2["c"]
    sig3 = R.holm({"a": 0.01, "b": 0.04, "c": None}, alpha=0.10)
    assert sig3["a"] and sig3["b"] and not sig3["c"]


# ------------------------------------------------------------------- gates ----
def test_corpus_content_hash_mirrors_the_pick_table_algorithm_exactly():
    """Format pinned by hand-derivation on a 2-row frame (order-independence
    included): date|name|score(.10f)|decile|label(.10f)|regime, '\n'-joined + '\n'."""
    df = pd.DataFrame({
        "date": [pd.Timestamp("2024-02-05"), pd.Timestamp("2024-02-02")],
        "name": ["BBB", "AAA"],
        "score": [1.5, -0.25],
        "decile_rank": [10, 1],
        "fwd_60d_excess": [0.125, -1.0],
        "regime": ["BULL_CALM", "BEAR"],
    })
    expected_lines = [
        "2024-02-02|AAA|-0.2500000000|1|-1.0000000000|BEAR",
        "2024-02-05|BBB|1.5000000000|10|0.1250000000|BULL_CALM",
    ]
    expected = hashlib.sha256(("\n".join(expected_lines) + "\n").encode()).hexdigest()
    assert R.xgb_corpus_content_sha(df) == expected
    # order independence: reversed input, same hash
    assert R.xgb_corpus_content_sha(df.iloc[::-1]) == expected


def test_preflight_refuses_on_a_missing_amendment(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "AMENDMENTS", (tmp_path / "absent1.md",
                                          tmp_path / "absent2.md",
                                          tmp_path / "absent3.md",
                                          tmp_path / "absent4.md"))
    pre = R.verify_preconditions(None)
    assert not pre["ok"]
    assert "amendment_1_present" in pre["unresolved"]
    assert "xgb_corpus_provided" in pre["unresolved"]


def test_preflight_refuses_on_a_labels_digest_mismatch(monkeypatch, tmp_path):
    bogus = tmp_path / "labels.parquet"
    bogus.write_bytes(b"not the frozen table")
    monkeypatch.setattr(R, "LABELS", bogus)
    pre = R.verify_preconditions(None)
    assert not pre["ok"]
    assert "labels_digest" in pre["unresolved"]


def test_gap_block_reports_the_terminal_dropped_tail():
    """Amendment 3: the terminal partial retained window's dropped count is REPORTED."""
    out = R.gap_block_t(np.random.default_rng(1).normal(size=59), 20)
    assert out["dropped_tail_dates"] == 19          # [40, 59) partial retained window
    out508 = R.gap_block_t(np.random.default_rng(2).normal(size=508), 60)
    assert out508["n_eff"] == 4 and out508["dropped_tail_dates"] == 28   # 508 - 480


def test_h1_persistence_veto_reroutes_or_blocks_supported():
    """§5 veto: a cleared tail whose REAL − persistence is not positive at t ≥ 1.0
    cannot win; the other cleared, unvetoed tail takes the win; both vetoed →
    INCONCLUSIVE naming the veto."""
    contrasts = {"spread_vs_ic": _c(4.0), "hit_vs_ic": _c(3.5), "spread_vs_hit": _c(0.5)}
    own = {"ic": 1.0, "spread": 3.0, "hit": 2.5}
    veto_spread_fails = {"spread": {"t": 0.4, "mean": 0.01},
                         "hit": {"t": 1.6, "mean": 0.02}}
    out = R.decide_h1(contrasts, own, veto_spread_fails)
    assert out["verdict"] == "SUPPORTED" and out["primary_statistic"] == "hit"
    both_fail = {"spread": {"t": 0.4, "mean": 0.01},
                 "hit": {"t": 1.2, "mean": -0.01}}      # positive-t but negative mean
    out2 = R.decide_h1(contrasts, own, both_fail)
    assert out2["verdict"] == "INCONCLUSIVE" and "persistence veto" in out2["why"]


def test_h2_persistence_veto_blocks_supported():
    t_pair = {"t": 3.0, "mean": 0.05, "n_eff": 4, "df": 3}
    out = R.decide_h2(t_pair, own_t_20=2.5, d20=0.03, d60=0.05,
                      veto20={"t": 0.2, "mean": 0.01})
    assert out["verdict"] == "INCONCLUSIVE" and "persistence veto" in out["why"]
    ok = R.decide_h2(t_pair, own_t_20=2.5, d20=0.03, d60=0.05,
                     veto20={"t": 1.4, "mean": 0.02})
    assert ok["verdict"] == "SUPPORTED" and ok["veto_passed"] is True


def test_cli_requires_the_explicit_corpus_path():
    assert R.main(["--preflight"]) == 2                 # missing required --xgb-corpus
