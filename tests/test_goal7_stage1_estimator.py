"""The GOAL-7 Stage-1 estimator, pinned against independent implementations.

The prereg (doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md) fixes
an estimand, a tie-break, a residualisation and a blocking rule. A fast numpy
re-implementation of any of those is exactly the kind of code that passes a
smoke test while computing a different object, so each piece is checked against
a slow, obviously-correct reference (pandas group-by loops, numpy.linalg.lstsq,
scipy.ttest_1samp, scipy.spearmanr) rather than against itself.

The two that would have silently changed the verdict:
  * `top_spread` subtracts the CROSS-SECTIONAL MEAN (§3), not the mean of the
    complement — a top-minus-rest spread is a different, larger statistic;
  * ties are broken by ASCENDING TICKER (§4), so the run is reproducible; a
    default sort would break them by row order.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm, spearmanr, ttest_1samp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import goal7_stage1_two_sided_run as G  # noqa: E402


@pytest.fixture(scope="module")
def panel() -> G.Panel:
    """A deliberately INTERLEAVED frame: rows do not arrive grouped by date, so
    any implementation that assumes date-contiguous input fails here."""
    rng = np.random.default_rng(7)
    n_dates, n_names = 200, 31
    dates = pd.bdate_range("2017-01-02", periods=n_dates)
    rows = [(d, f"T{i:03d}", rng.normal(), rng.normal(), rng.normal())
            for d in dates for i in range(n_names)]
    f = pd.DataFrame(rows, columns=["date", "ticker", "mom", "vol", "lab"])
    return G.Panel(f.sample(frac=1.0, random_state=3).reset_index(drop=True))


def _naive_top_spread(df: pd.DataFrame, score: np.ndarray,
                      label: np.ndarray) -> np.ndarray:
    g = df.assign(s=score, y=label)
    out = []
    for _, gg in g.groupby("date", sort=True):
        gg = gg.sort_values(["s", "ticker"], ascending=[False, True],
                            kind="mergesort")
        k = max(1, int(round(G.TOP_FRACTION * len(gg))))
        out.append(gg["y"].iloc[:k].mean() - gg["y"].mean())
    return np.asarray(out)


def test_per_date_z_matches_pandas(panel):
    got = panel.gz(panel.df["mom"].to_numpy())
    want = panel.df.groupby("date")["mom"].transform(
        lambda v: (v - v.mean()) / v.std()).to_numpy()
    assert np.allclose(got, want, atol=1e-12)


def test_top_spread_matches_a_naive_loop(panel):
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    lab = panel.df["lab"].to_numpy()
    assert np.allclose(panel.top_spread(u, lab),
                       _naive_top_spread(panel.df, u, lab), atol=1e-12)


def test_top_spread_is_versus_the_cross_sectional_mean_not_the_complement(panel):
    """§3 says 'minus the cross-sectional mean'. Top-minus-rest is a DIFFERENT
    statistic (larger by 1/(1-k/n)); this pins which one is computed."""
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    lab = panel.df["lab"].to_numpy()
    got = panel.top_spread(u, lab)
    g = panel.df.assign(s=u, y=lab)
    rest = []
    for _, gg in g.groupby("date", sort=True):
        gg = gg.sort_values(["s", "ticker"], ascending=[False, True],
                            kind="mergesort")
        k = max(1, int(round(G.TOP_FRACTION * len(gg))))
        rest.append(gg["y"].iloc[:k].mean() - gg["y"].iloc[k:].mean())
    rest = np.asarray(rest)
    assert not np.allclose(got, rest, atol=1e-6)
    n, k = int(panel.counts[0]), int(panel.k[0])
    assert np.allclose(got, rest * (1.0 - k / n), atol=1e-12)


def test_ties_break_by_ascending_ticker(panel):
    """A constant score is all ties: the top-k must be the alphabetically first
    tickers, deterministically, on every date."""
    lab = panel.df["lab"].to_numpy()
    const = np.zeros(len(panel.df))
    assert np.allclose(panel.top_spread(const, lab),
                       _naive_top_spread(panel.df, const, lab), atol=1e-12)
    order = panel.order_desc(const)
    first_date = panel.df["ticker"].to_numpy()[order[:panel.k[0]]]
    expected = sorted(panel.df.loc[panel.df.date == panel.dates[0], "ticker"]
                      )[:panel.k[0]]
    assert list(first_date) == list(expected)


def test_residualise_matches_lstsq_and_is_orthogonal_within_date(panel):
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    x = np.abs(panel.gz(panel.df["vol"].to_numpy()))
    got = panel.residualise(u, x)
    want = np.empty_like(got)
    for _, gg in panel.df.assign(u=u, x=x).groupby("date", sort=True):
        A = np.c_[np.ones(len(gg)), gg["x"].to_numpy()]
        beta, *_ = np.linalg.lstsq(A, gg["u"].to_numpy(), rcond=None)
        want[gg.index.to_numpy()] = gg["u"].to_numpy() - A @ beta
    assert np.allclose(got, want, atol=1e-10)
    for _, gg in panel.df.assign(r=got, x=x).groupby("date"):
        assert abs(np.corrcoef(gg["r"], gg["x"])[0, 1]) < 1e-8


def test_residualise_refuses_a_degenerate_regressor(panel):
    """A zero-variance regressor makes the §4 regression undefined. It must
    ABORT, not fall back to a demean — a silent fallback would turn the kill
    condition into a no-op on exactly the dates it cannot evaluate."""
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    with pytest.raises(SystemExit):
        panel.residualise(u, np.zeros(len(u)))


def test_block_t_drops_the_remainder_and_matches_scipy(panel):
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    s = panel.top_spread(u, panel.df["lab"].to_numpy())
    nb = len(s) // G.BLOCK
    assert len(s) % G.BLOCK != 0, "fixture must have a remainder to drop"
    got = G.block_t(s, nb)
    bm = s[:nb * G.BLOCK].reshape(nb, G.BLOCK).mean(axis=1)
    assert got["n_blocks"] == nb
    assert abs(got["t"] - float(ttest_1samp(bm, 0.0).statistic)) < 1e-12
    # the dropped tail must not enter the statistic at any weight
    poisoned = s.copy()
    poisoned[nb * G.BLOCK:] = 1e6
    assert G.block_t(poisoned, nb)["t"] == got["t"]


def test_estimand_rejects_nan(panel):
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    lab = panel.df["lab"].to_numpy().copy()
    lab[0] = np.nan
    with pytest.raises(SystemExit):
        panel.top_spread(u, lab)


def test_normal_scores_and_spearman_match_references(panel):
    lab = panel.df["lab"].to_numpy()
    ns = G.normal_scores_asc(panel, lab)
    for _, q in list(panel.df.assign(y=lab, ns=ns).groupby("date"))[:3]:
        q = q.sort_values(["y", "ticker"], kind="mergesort")
        n = len(q)
        assert np.allclose(q["ns"].to_numpy(),
                           norm.ppf((np.arange(n) + 0.5) / n), atol=1e-12)
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    sp = G.spearman_per_date(panel, u, lab)
    for i, (_, q) in enumerate(list(panel.df.assign(u=u, y=lab)
                                    .groupby("date"))[:5]):
        assert abs(sp[i] - float(spearmanr(q["u"], q["y"]).statistic)) < 1e-10


def test_positive_control_is_bit_reproducible_from_the_date_seed(panel):
    def draw() -> np.ndarray:
        g = np.empty(len(panel.df))
        for gi in range(panel.n_dates):
            s, n = panel.starts[gi], panel.counts[gi]
            rng = np.random.default_rng(
                G.SEED_BASE + int(panel.dates[gi].strftime("%Y%m%d")))
            g[s:s + n] = rng.random(n)
        return g
    assert np.array_equal(draw(), draw())
    assert abs((6 / math.pi) * math.asin(G.ALPHA_PC / 2) - 0.05) < 1e-12


def test_harness_detects_an_injected_effect_and_not_pure_noise(panel):
    """The estimator must be able to see a real effect (else a null result is a
    statement about the harness) and must not manufacture one from noise."""
    rng = np.random.default_rng(11)
    u = np.abs(panel.gz(panel.df["mom"].to_numpy()))
    nb = len(panel.dates) // G.BLOCK
    injected = 0.30 * u + rng.normal(size=len(u))
    assert abs(G.block_t(panel.top_spread(u, injected), nb)["t"]) > 5.0
    lab = panel.df["lab"].to_numpy()
    noise = [abs(G.block_t(panel.top_spread(rng.normal(size=len(u)), lab),
                           nb)["t"]) for _ in range(40)]
    assert np.median(noise) < 3.0
