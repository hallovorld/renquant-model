"""The plausibility bound must be reproducible, or it is not a pinned threshold."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import goal4_plausibility_bound as pb  # noqa: E402


def test_seed_reproduces_the_registered_value():
    """The whole point: the document's number must be recomputable from the document.

    This is the assertion A1.8 could not make — its +0.01897 has no committed
    construction, so nothing could check it.
    """
    p, se = pb.plausibility_bound()
    assert p == pytest.approx(0.01355, abs=5e-5)
    assert se == pytest.approx(0.00274, abs=5e-5)


def test_same_seed_is_bit_identical_across_calls():
    assert pb.plausibility_bound(n_draws=50) == pb.plausibility_bound(n_draws=50)


def test_different_seed_moves_within_noise_not_arbitrarily():
    """A seed change must perturb P by sampling noise, not restructure it."""
    base, se = pb.plausibility_bound()
    other, _ = pb.plausibility_bound(seed=pb.SEED + 1)
    assert abs(other - base) < 6 * se


def test_spearman_pearson_identity_inverts():
    for rho_s in (0.05, 0.07312, 0.404):
        rho = pb.spearman_to_pearson(rho_s)
        assert (6 / math.pi) * math.asin(rho / 2) == pytest.approx(rho_s, abs=1e-12)


def test_unrealisable_targets_abort_rather_than_being_nudged():
    """A silently repaired correlation matrix would measure a different quantity.

    Two scores each near-perfectly correlated with the return cannot also be
    uncorrelated with each other; that triple has no Gaussian realisation.
    """
    with pytest.raises(SystemExit, match="not jointly realisable"):
        pb.target_matrix(ic=0.99, red=0.0)


def test_realisable_targets_do_not_abort():
    m = pb.target_matrix()
    assert m.shape == (3, 3)
    assert float(m.min()) > 0


def test_the_registered_disposition_is_invariant_across_both_bounds():
    """The reason this correction is safe to land: no verdict moves.

    If this ever fails, the two constructions disagree about GOAL-4's outcome and the
    threshold must be resolved before any re-run is adjudicated.
    """
    p, _ = pb.plausibility_bound()
    assert pb.MDG > p
    assert pb.MDG > pb.A18_PUBLISHED_P


def test_p_is_a_gain_not_an_ic():
    """P must be far below the benchmark IC it is derived from.

    Guards the unit error the discarded competing amendment would have made:
    bounding a member IC where the decision rule consumes a gain.
    """
    p, _ = pb.plausibility_bound()
    assert 0 < p < pb.IC_BENCH
