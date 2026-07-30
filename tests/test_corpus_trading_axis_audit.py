"""Codex P2 (PR #109): the CLI shipped with no committed tests. These pin the
three things the tool actually computes — trading-axis stepping (vs a
BDay offset, which a holiday makes wrong), the cutoff sanity check, and the
label-maturity fraction — plus fail-loud behaviour on a malformed corpus.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import corpus_trading_axis_audit as ctaa  # noqa: E402


def _axis_with_holiday(start: str, end: str, holiday: str) -> pd.DatetimeIndex:
    bdays = pd.bdate_range(start, end)
    return pd.DatetimeIndex(sorted(set(bdays) - {pd.Timestamp(holiday)}))


def test_nth_trading_day_after_sees_the_holiday_a_bday_offset_misses():
    axis = _axis_with_holiday("2024-01-01", "2024-02-09", "2024-01-15")
    start = pd.Timestamp("2024-01-02")
    n = 10
    true_end = ctaa.nth_trading_day_after(axis, [start], n)[start]
    bday_end = start + pd.offsets.BDay(n)
    assert true_end > bday_end, (
        "the holiday pushes the true n-th trading day later than a BDay "
        "offset that doesn't know about it")


def test_nth_trading_day_after_returns_nat_when_it_runs_off_the_axis():
    axis = pd.bdate_range("2024-01-01", "2024-01-05")
    out = ctaa.nth_trading_day_after(axis, [pd.Timestamp("2024-01-05")], 5)
    assert pd.isna(out.iloc[0])


def test_nth_trading_day_after_rejects_an_off_axis_weekend_date():
    # searchsorted would otherwise silently snap this Saturday to the
    # following Monday's position instead of failing on the malformed input.
    axis = pd.bdate_range("2024-01-01", "2024-02-09")
    saturday = pd.Timestamp("2024-01-06")
    with pytest.raises(ValueError):
        ctaa.nth_trading_day_after(axis, [saturday], 1)


def test_audit_rejects_a_corpus_with_an_off_axis_score_date():
    axis = pd.bdate_range("2024-01-01", "2024-06-01")
    corpus = pd.DataFrame({"date": [pd.Timestamp("2024-01-06")]})  # Saturday
    with pytest.raises(ValueError):
        ctaa.audit(corpus, axis, lookahead=5)


def test_audit_flags_rows_at_or_before_their_own_cutoff():
    axis = pd.bdate_range("2024-01-01", "2024-06-01")
    corpus = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-10"), pd.Timestamp("2024-01-11")],
        "cutoff": [pd.Timestamp("2024-01-10"), pd.Timestamp("2024-01-05")],
    })
    r = ctaa.audit(corpus, axis, lookahead=5)
    assert r["rows_at_or_before_cutoff"] == 1  # only the 01-10 row is <= its cutoff


def test_audit_flags_dates_whose_label_window_runs_past_the_corpus_span():
    axis = pd.bdate_range("2024-01-01", "2024-06-01")
    dates = pd.bdate_range("2024-01-01", "2024-01-31")
    corpus = pd.DataFrame({"date": dates})
    r = ctaa.audit(corpus, axis, lookahead=60)
    assert r["n_unverifiable_dates"] == r["n_dates"], (
        "every date's 60-trading-day window runs past 2024-01-31")
    assert r["frac_unverifiable"] == 1.0


def test_audit_flags_only_the_trailing_lookahead_dates_as_unverifiable():
    # "unverifiable" is relative to the CORPUS's own last date, not the
    # axis's: the trailing `lookahead` trading days always fail, because
    # their forward window necessarily runs past whatever the corpus holds.
    axis = pd.bdate_range("2024-01-01", "2024-12-31")
    corpus = pd.DataFrame({"date": axis})
    lookahead = 5
    r = ctaa.audit(corpus, axis, lookahead=lookahead)
    assert r["n_unverifiable_dates"] == lookahead
    assert r["frac_unverifiable"] == pytest.approx(lookahead / len(axis))


def test_audit_raises_on_a_corpus_missing_the_required_date_column():
    axis = pd.bdate_range("2024-01-01", "2024-06-01")
    malformed = pd.DataFrame({"score": [0.1, 0.2]})
    with pytest.raises(KeyError):
        ctaa.audit(malformed, axis, lookahead=5)


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    df.to_parquet(path)


def test_cli_exits_zero_when_under_an_explicit_tolerance(tmp_path, capsys):
    axis = pd.bdate_range("2024-01-01", "2024-12-31")
    axis_path = tmp_path / "axis.parquet"
    corpus_path = tmp_path / "corpus.parquet"
    _write_parquet(axis_path, pd.DataFrame({"date": axis}))
    _write_parquet(corpus_path, pd.DataFrame({"date": axis}))

    # 5 trailing dates out of 262 = ~1.9%; an explicit 5% tolerance passes.
    rc = ctaa.main(["--corpus", str(corpus_path), "--axis", str(axis_path),
                     "--lookahead", "5", "--max-unverifiable-frac", "0.05"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_cli_exits_nonzero_when_the_default_gate_is_violated(tmp_path, capsys):
    axis_df = pd.DataFrame({"date": pd.bdate_range("2024-01-01", "2024-02-29")})
    corpus_df = pd.DataFrame({"date": pd.bdate_range("2024-01-01", "2024-01-31")})
    axis_path = tmp_path / "axis.parquet"
    corpus_path = tmp_path / "corpus.parquet"
    _write_parquet(axis_path, axis_df)
    _write_parquet(corpus_path, corpus_df)

    rc = ctaa.main(["--corpus", str(corpus_path), "--axis", str(axis_path),
                     "--lookahead", "60"])
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out
