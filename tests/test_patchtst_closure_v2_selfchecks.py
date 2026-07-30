"""§0.3 self-checks for the FROZEN prereg
doc/research/2026-07-30-patchtst-closure-prereg-v2.md ("model#113").

Each of these must PASS before the treatment computation is trusted:

1. the within-date pairing (`admissible_dates`) is asserted to operate on a
   date-sorted frame, and the assertion is proven to REJECT an unsorted frame.
2. the block partition (`block_partition_indices` / `assert_no_undersized_block`)
   is asserted to contain no undersized block.
3. any multiple-comparison correction used is asserted to implement the
   step-down stop — N/A here: §5's decision rule is evaluated at a single lag
   (L=60) with a single test, so no multiple-comparison correction is used
   anywhere in this study. This is asserted by the absence of any such
   function in patchtst_closure_v2_lib.py (test below) rather than by testing
   a correction that does not exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import patchtst_closure_v2_lib as L  # noqa: E402


# ---------------------------------------------------- self-check 1: unsorted
def test_admissible_dates_rejects_unsorted_score_dates():
    label_axis = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=200, freq="B"))
    sorted_scores = label_axis[:150]
    unsorted_scores = pd.DatetimeIndex(
        list(sorted_scores[50:]) + list(sorted_scores[:50]))  # deliberately shuffled
    with pytest.raises(L.UnsortedDateFrameError):
        L.admissible_dates(unsorted_scores, label_axis, L=60, h=60)


def test_admissible_dates_rejects_unsorted_label_axis():
    label_axis = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=200, freq="B"))
    scores = label_axis[:150]
    shuffled_label_axis = pd.DatetimeIndex(
        list(label_axis[100:]) + list(label_axis[:100]))
    with pytest.raises(L.UnsortedDateFrameError):
        L.admissible_dates(scores, shuffled_label_axis, L=60, h=60)


def test_admissible_dates_accepts_sorted_frame_and_matches_hand_count():
    label_axis = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=200, freq="B"))
    scores = label_axis[:150]
    adm = L.admissible_dates(scores, label_axis, L=60, h=60)
    # admissible iff position i (0-indexed on the score axis, positionally
    # contiguous with label_axis by construction here) satisfies i>=60 and
    # i+60 < 200 (=len(label_axis))  ->  i in [60, 139]  ->  80 dates.
    assert len(adm) == 80
    assert pd.DatetimeIndex(adm).is_monotonic_increasing


def test_positional_contiguity_assertion_catches_a_gapped_score_axis():
    label_axis = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=100, freq="B"))
    gapped_scores = label_axis[::2]  # every OTHER trading day: not contiguous
    with pytest.raises(AssertionError):
        L.assert_score_axis_positionally_contiguous(gapped_scores, label_axis)


def test_positional_contiguity_assertion_passes_a_contiguous_axis():
    label_axis = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=100, freq="B"))
    contiguous_scores = label_axis[10:60]
    L.assert_score_axis_positionally_contiguous(contiguous_scores, label_axis)  # no raise


# ---------------------------------------------------- self-check 2: blocks
def test_block_partition_drops_remainder_never_equal_weights_it():
    # 145 admissible dates, block_len=60 -> 2 full blocks (120), 25 dropped.
    # This is exactly the shape of the model#110 ERRATUM the frozen text
    # cites: a trailing partial block must NOT be kept.
    blocks = L.block_partition_indices(n_eval=145, block_len=60)
    assert len(blocks) == 2
    assert blocks == [(0, 60), (60, 120)]
    L.assert_no_undersized_block(blocks, block_len=60)  # must not raise


def test_assert_no_undersized_block_raises_on_a_short_trailing_block():
    bad_blocks = [(0, 60), (60, 120), (120, 145)]  # last block only 25 wide
    with pytest.raises(AssertionError):
        L.assert_no_undersized_block(bad_blocks, block_len=60)


def test_block_t_end_to_end_drops_remainder():
    rng = np.random.default_rng(0)
    d = rng.normal(0.01, 0.05, size=145)
    bs = L.block_t(d, block_len=60)
    assert bs.n_blocks == 2
    assert bs.n_eval == 145
    assert bs.dropped_remainder == 25
    # sanity: matches a hand computation over the first 120 values only
    hand_blocks = [d[0:60].mean(), d[60:120].mean()]
    assert bs.mean == pytest.approx(np.mean(hand_blocks))


def test_block_t_median_aggregation_for_section_6_2():
    rng = np.random.default_rng(1)
    d = rng.normal(0.01, 0.05, size=180)
    bs = L.block_t(d, block_len=60, agg="median")
    assert bs.n_blocks == 3
    hand = [np.median(d[0:60]), np.median(d[60:120]), np.median(d[120:180])]
    assert bs.mean == pytest.approx(np.mean(hand))


# ---------------------------------------------------- self-check 3: no MC correction
def test_no_multiple_comparison_correction_function_exists_in_the_library():
    """§0.3 self-check #3 is conditional: 'if you use any multiple-comparison
    correction, assert it implements the step-down stop.' This study's §5
    decision rule is evaluated at a single lag (L=60) with a single test,
    so no correction (holm or otherwise) is used. This test pins that fact:
    if a future edit adds one, it must ALSO add the step-down-stop test this
    module currently lacks, and this test's failure is the tripwire for
    that."""
    banned = {"holm", "bonferroni", "benjamini_hochberg", "fdr", "step_down"}
    names = {n.lower() for n in dir(L)}
    hit = banned & names
    assert not hit, (
        f"found multiple-comparison correction symbol(s) {hit} in "
        f"patchtst_closure_v2_lib without a step-down-stop test alongside "
        f"them — see §0.3 self-check #3")


# ---------------------------------------------------- critical value plumbing
def test_critical_value_takes_the_max_of_the_two_legs():
    cv = L.critical_value(n_blocks=8, null_abs_t_draws=[1.0] * 190 + [3.0] * 10)
    # student leg at n_blocks=8 -> t.ppf(0.975, 7) = 2.3646...
    assert cv.student_t_leg == pytest.approx(2.3646, abs=1e-3)
    assert cv.bound_by in ("student_t", "p95_null")
    assert cv.t_crit == max(cv.student_t_leg, cv.p95_null_leg)


def test_null_quantile_of_treatment_t():
    draws = [0.5, 1.0, 1.5, 2.0, 2.5]
    q = L.null_quantile_of(2.0, draws)
    assert q == pytest.approx(0.8)  # 4 of 5 draws (<=2.0 in abs) are <= 2.0
