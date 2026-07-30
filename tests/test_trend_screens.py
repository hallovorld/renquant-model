"""POSITIVE CONTROLS for the two trend screens' estimator plumbing.

A screen whose estimator cannot detect a known effect can only produce
uninformative negatives, and would look exactly like a real negative. So before
any verdict from either screen is read, the plumbing must be shown to (a)
recover a PLANTED signal and (b) stay null on a signal-free panel.

These are behavioural tests on synthetic panels with a known ground truth. A
source-grep test would pass on an estimator wired backwards.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s1 = _load("vol_conditioned_trend_screen")
s2 = _load("momentum_family_screen")

N_DATES, N_NAMES = 300, 60


def synthetic(effect: float, seed: int = 0) -> pd.DataFrame:
    """A panel where `score` predicts `y` with a known cross-sectional effect."""
    rng = np.random.default_rng(seed)
    dates = np.repeat(np.arange(N_DATES), N_NAMES)
    score = rng.normal(size=N_DATES * N_NAMES)
    y = effect * score + rng.normal(size=N_DATES * N_NAMES)
    frame = pd.DataFrame({"date": pd.to_datetime("2020-01-01")
                          + pd.to_timedelta(dates, unit="D"),
                          "score": score, "y": y})
    frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
    frame["_dcode"] = pd.factorize(frame["date"])[0]
    return frame


def test_positive_control_planted_signal_is_recovered():
    e1, e2 = s1.per_date_stats(synthetic(effect=0.30), "score", "y")
    assert s1.aggregate(e1)["mean"] > 0.10, "IC missed a planted +0.30 effect"
    assert s1.aggregate(e2)["mean"] > 0.10, "spread missed a planted effect"


def test_negative_control_signal_free_panel_stays_null():
    e1, e2 = s1.per_date_stats(synthetic(effect=0.0, seed=5), "score", "y")
    assert abs(s1.aggregate(e1)["mean"]) < 0.05
    assert abs(s1.aggregate(e2)["mean"]) < 0.10


def test_sign_is_not_inverted():
    """The single most damaging plumbing bug: a screen that reports the sign
    backwards would report every real positive as a negative."""
    pos, _ = s1.per_date_stats(synthetic(effect=+0.40), "score", "y")
    neg, _ = s1.per_date_stats(synthetic(effect=-0.40), "score", "y")
    assert s1.aggregate(pos)["mean"] > 0 > s1.aggregate(neg)["mean"]


def test_shuffle_preserves_the_per_date_label_distribution():
    """The control must destroy the score-label LINK without touching the
    per-date cross-sectional distribution -- otherwise it is not a null of the
    same shape, and its |t| is not comparable to the real arm's."""
    frame = synthetic(effect=0.3)
    shuffled = frame.copy()
    shuffled["y"] = s1.shuffle_within_date(frame, seed=1)
    for _, (a, b) in pd.concat(
            [frame.groupby("date")["y"].apply(lambda s: np.sort(s.values)).rename("a"),
             shuffled.groupby("date")["y"].apply(lambda s: np.sort(s.values)).rename("b")],
            axis=1).head(20).iterrows():
        assert np.allclose(a, b)


def test_shuffle_actually_destroys_the_signal():
    frame = synthetic(effect=0.50)
    shuffled = frame.copy()
    shuffled["y"] = s1.shuffle_within_date(frame, seed=2)
    real, _ = s1.per_date_stats(frame, "score", "y")
    null, _ = s1.per_date_stats(shuffled, "score", "y")
    assert s1.aggregate(real)["mean"] > 0.15
    assert abs(s1.aggregate(null)["mean"]) < 0.05


def test_top_decile_k_matches_the_frozen_definition():
    """k = round(0.10 * n), k >= 1 -- the definition frozen in model#101 §2, not
    a rank-percentile approximation."""
    rng = np.random.default_rng(1)
    rows = []
    for i, n in enumerate((23, 47, 100)):     # k = 2, 5, 10
        for j in range(n):
            rows.append((pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                         rng.normal(), 1.0 if j == 0 else 0.0))
    frame = pd.DataFrame(rows, columns=["date", "score", "y"])
    # Make the top-k deterministic: y = 1 exactly for the k highest scores.
    for _, grp in frame.groupby("date"):
        k = max(1, round(len(grp) * 0.10))
        top = grp.score.nlargest(k).index
        frame.loc[grp.index, "y"] = 0.0
        frame.loc[top, "y"] = 1.0
    _, e2 = s1.per_date_stats(frame, "score", "y")
    # top mean = 1, rest mean = 0 => spread exactly 1 on every date.
    assert np.allclose(e2.values, 1.0)


def test_ret_inverts_roc_because_roc_is_past_over_today():
    # ROC{n} = close[t-n]/close[t]. A doubling => ROC = 0.5 => ret = +1.0.
    assert s1.ret(pd.Series([0.5]))[0] == pytest.approx(1.0)
    # A halving => ROC = 2.0 => ret = -0.5.
    assert s1.ret(pd.Series([2.0]))[0] == pytest.approx(-0.5)
    # Non-positive ROC is not a price ratio; it must not produce a number.
    assert np.isnan(s1.ret(pd.Series([0.0]))[0])


def test_screen2_omits_ret60_because_it_is_screen1_arm_r1():
    """Counting the same test twice would inflate the family and understate the
    multiplicity correction."""
    rng = np.random.default_rng(0)
    n = 400
    panel = pd.DataFrame({
        "date": np.repeat(pd.date_range("2020-01-01", periods=20), 20),
        "ticker": np.tile([f"T{i}" for i in range(20)], 20),
        "STD60": rng.uniform(0.01, 0.2, n),
        "ROC5": rng.uniform(0.9, 1.1, n), "ROC20": rng.uniform(0.8, 1.2, n),
        "ROC60": rng.uniform(0.7, 1.3, n), s1.LABEL: rng.normal(size=n)})
    arms = s2.build_arms(panel)
    assert set(arms.columns) - {"date", "ticker", "y"} == {"M1", "M2", "M3", "M4"}


def test_screen2_joint_bar_is_stricter_than_screen1():
    """The bar may be tightened after freezing, never loosened."""
    assert s2.JOINT_BONFERRONI_T > s1.BONFERRONI_T
