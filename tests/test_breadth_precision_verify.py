"""The memo's numbers are only reviewable if the script is honest about
whether it ran on the pinned input, and reproduces bit-identically when it
did. These pin that contract, not the substantive finding (measured against
real corpora in the research doc, independently reproduced there).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import breadth_precision_verify as bpv  # noqa: E402


def test_check_pin_passes_on_matching_bytes(tmp_path):
    p = tmp_path / "clf_wf_scores.parquet"
    p.write_bytes(b"x")
    bpv.PINNED[p.name] = bpv.sha256(p)
    try:
        assert bpv.check_pin(p, allow_mismatch=False) == bpv.sha256(p)
    finally:
        del bpv.PINNED[p.name]


def test_check_pin_aborts_on_mismatch(tmp_path):
    p = tmp_path / "clf_wf_scores.parquet"
    p.write_bytes(b"x")
    bpv.PINNED[p.name] = "0" * 64
    try:
        with pytest.raises(SystemExit, match="ABORT"):
            bpv.check_pin(p, allow_mismatch=False)
    finally:
        del bpv.PINNED[p.name]


def test_check_pin_mismatch_proceeds_with_allow_flag(tmp_path, capsys):
    p = tmp_path / "clf_wf_scores.parquet"
    p.write_bytes(b"x")
    bpv.PINNED[p.name] = "0" * 64
    try:
        digest = bpv.check_pin(p, allow_mismatch=True)
        assert digest == bpv.sha256(p)
        assert "WARNING" in capsys.readouterr().out
    finally:
        del bpv.PINNED[p.name]


def test_unpinned_file_is_reported_not_rejected(tmp_path):
    p = tmp_path / "unrelated.parquet"
    p.write_bytes(b"x")
    assert bpv.check_pin(p, allow_mismatch=False) == bpv.sha256(p)


def test_breadth_ladder_is_deterministic_across_runs():
    rng = np.random.default_rng(0)
    rows = []
    for i, dt in enumerate(pd.date_range("2024-01-01", periods=40)):
        n = 260
        rows.append(pd.DataFrame({
            "date": dt,
            "raw": rng.normal(size=n),
            "fwd_60d_excess": rng.normal(size=n),
        }))
    corpus = pd.concat(rows, ignore_index=True)
    a = bpv.breadth_ladder(corpus)
    b = bpv.breadth_ladder(corpus)
    assert a == b, "two runs on the same corpus must be bit-identical"
    assert [n for n, _ in a] == list(bpv.LADDER)


def test_fit_recovers_known_a_plus_b_over_n():
    a_true, b_true = 0.03, 1.0
    rows = [(n, a_true + b_true / n) for n in (20, 50, 100, 200, 300)]
    a, b = bpv.fit_a_plus_b_over_n(rows)
    assert a == pytest.approx(a_true, abs=1e-9)
    assert b == pytest.approx(b_true, abs=1e-9)


def test_survivorship_probe_flags_zero_exits_as_backfilled():
    dates = pd.date_range("2020-01-01", periods=5, freq="60D")
    panel = pd.DataFrame({
        "date": list(dates) * 2,
        "ticker": ["AAA"] * 5 + ["BBB"] * 5,
    })
    probe = bpv.survivorship_probe(panel)
    assert probe["n_tickers"] == 2
    assert probe["n_ever_but_absent_at_end"] == 0


def test_survivorship_probe_counts_a_real_exit():
    dates = pd.date_range("2020-01-01", periods=5, freq="60D")
    panel = pd.DataFrame({
        "date": list(dates) + list(dates[:2]),
        "ticker": ["AAA"] * 5 + ["BBB"] * 2,   # BBB exits before the end
    })
    probe = bpv.survivorship_probe(panel)
    assert probe["n_ever_but_absent_at_end"] == 1
