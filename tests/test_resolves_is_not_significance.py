"""`resolves` is a SIGN-agreement criterion, not a significance test.

Measured 2026-07-31: the 2026-07-30 GOAL-7 total-return bundle reports
`resolves: True` on a paired contrast with `block_t = 1.682` over 10 blocks, where
the correct Student floor is `t(9) = 2.262`. The block-t leg contributes only its
SIGN to `resolves`; its magnitude is never compared to anything.

That is a documented, deliberate design — and the field name invites the opposite
reading, which is why `clears_student_bar` now exists beside it.
"""

from __future__ import annotations

import json
import pathlib

import pytest

# class name READ from the source, not guessed -- the error class this
# session has been auditing all night.
from renquant_model_common.lag_alignment import DependenceAwareResult


def _m(**kw):
    base = dict(mean=0.3, block_t=1.682, n_blocks=10, block_length=120,
                ci_low=0.0887, ci_high=0.7090, ci_level=0.9,
                lobo_low=0.05, lobo_high=0.8, n_boot=2000)
    base.update(kw)
    return DependenceAwareResult(**base)


def test_resolves_can_be_true_below_the_bar_its_block_count_implies():
    """THE finding, reproduced as a unit."""
    m = _m()
    assert m.resolves is True
    assert m.clears_student_bar is False
    assert m.student_bar == pytest.approx(2.262, abs=5e-4)


def test_the_bar_is_computed_at_the_realised_geometry_not_borrowed():
    assert _m(n_blocks=8).student_bar == pytest.approx(2.3646, abs=5e-4)
    assert _m(n_blocks=10).student_bar == pytest.approx(2.2622, abs=5e-4)
    assert _m(n_blocks=50).student_bar < 2.02          # approaches 1.96 from above
    assert _m(n_blocks=50).student_bar > 1.96          # but never below it


def test_a_clearly_significant_estimate_satisfies_BOTH():
    """CONTROL. If `clears_student_bar` were always False the test above would be
    vacuous."""
    m = _m(block_t=3.767)
    assert m.resolves is True
    assert m.clears_student_bar is True


def test_unknown_is_not_False():
    """Too few blocks yields None, never False: 'cannot be computed' and 'does not
    clear' are different answers."""
    assert _m(n_blocks=1).student_bar is None
    assert _m(n_blocks=1).clears_student_bar is None
    assert _m(block_t=None).clears_student_bar is None


def test_resolves_still_requires_all_three_views_to_agree():
    """Behaviour invariance: this PR must not change what `resolves` means."""
    assert _m(ci_low=-0.01).resolves is False          # bootstrap CI straddles 0
    assert _m(lobo_low=-0.01).resolves is False        # leave-one-block-out straddles
    assert _m(block_t=-1.682).resolves is False        # sign disagrees


def test_describe_now_says_which_side_of_the_bar_it_is_on():
    assert "BELOW t(9)=2.262" in _m().describe()
    assert "clears t(9)=2.262" in _m(block_t=3.767).describe()


def test_the_goal7_bundle_is_the_real_instance():
    p = (pathlib.Path(__file__).resolve().parent.parent
         / "doc/research/data/2026-07-30-momentum-total-return/results.json")
    R = json.loads(p.read_text(encoding="utf-8"))
    paired = R["baseline"]["paired"]
    assert paired["resolves"] is True
    assert paired["n_blocks"] == 10
    assert abs(paired["t"] - 1.682) < 0.01
    assert abs(paired["t"]) < 2.262                    # below its own bar
