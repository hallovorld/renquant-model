"""The v2 filed-column census must not manufacture its own evidence.

codex on model#146: dropping duplicate rows on the comparison key silently chooses an
arbitrary date when one key carries two different ones — which would fabricate the very
deltas and coverage the census exists to report.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOD = ROOT / "tools" / "v2_filed_column_census.py"


def _load():
    spec = importlib.util.spec_from_file_location("vfc", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


C = _load()


def _write(root, name, rows, cols):
    pd.DataFrame(rows, columns=cols).to_parquet(root / name)


def _corpus(tmp_path, fd_rows, av_rows):
    _write(tmp_path, "filing_dates.parquet", fd_rows,
           ["ticker", "period_end", "form", "filing_date"])
    _write(tmp_path, "available_at_v2.parquet", av_rows,
           ["ticker", "fiscal_period_end", "form", "available_v2"])
    return str(tmp_path)


def test_CONFLICTING_duplicate_dates_make_the_pair_AMBIGUOUS(tmp_path):
    """The case named in review: one (ticker, form, period_end) with TWO different
    filing dates. Pre-fix, `drop_duplicates` kept whichever row came first and reported
    a delta computed from an arbitrary choice."""
    root = _corpus(
        tmp_path,
        [("AAPL", "2025-03-31", "10-Q", "2025-05-01"),
         ("AAPL", "2025-03-31", "10-Q", "2025-05-09")],   # conflicting
        [("AAPL", "2025-03-31", "10-Q", "2025-05-02")])
    rep = C.census(root)
    assert rep["n_ambiguous_pairs"] == 1, rep["pairwise"]
    p = rep["pairwise"][0]
    assert p["status"] == "AMBIGUOUS_KEYS"
    assert "choose arbitrarily" in p["note"]
    assert "n_joined" not in p, "no delta may be reported for an ambiguous pair"


def test_IDENTICAL_duplicates_are_collapsed_not_flagged(tmp_path):
    """The distinction has to cut both ways: repeated rows carrying the SAME date are a
    representation detail, not an ambiguity, and flagging them would make the census
    unusable on any table with redundant rows."""
    root = _corpus(
        tmp_path,
        [("AAPL", "2025-03-31", "10-Q", "2025-05-01"),
         ("AAPL", "2025-03-31", "10-Q", "2025-05-01")],   # identical
        [("AAPL", "2025-03-31", "10-Q", "2025-05-01")])
    rep = C.census(root)
    assert rep["n_ambiguous_pairs"] == 0
    assert rep["pairwise"][0]["n_joined"] == 1


def test_an_ambiguous_pair_makes_main_EXIT_NONZERO(tmp_path):
    """'Unresolvable key' must never read as 'the TBD is resolved'."""
    root = _corpus(
        tmp_path,
        [("AAPL", "2025-03-31", "10-Q", "2025-05-01"),
         ("AAPL", "2025-03-31", "10-Q", "2025-05-09")],
        [("AAPL", "2025-03-31", "10-Q", "2025-05-02")])
    assert C.main(["--root", root]) == 1


def test_the_report_REFUSES_to_assign_semantics(tmp_path, capsys):
    """codex, second point: `filing_date` being named that is not evidence that it IS
    the filed date. Inferring meaning from a column name is the exact guess Amendment 2a
    refused to make."""
    root = _corpus(tmp_path,
                   [("AAPL", "2025-03-31", "10-Q", "2025-05-01")],
                   [("AAPL", "2025-03-31", "10-Q", "2025-05-02")])
    C.main(["--root", root])
    out = capsys.readouterr().out
    assert "SEMANTICS ARE NOT ASSIGNED HERE" in out
    assert "a name is not a contract" in out
    assert "SOURCE-SCHEMA evidence" in out


def test_an_EMPTY_root_exits_2_not_0(tmp_path, capsys):
    assert C.main(["--root", str(tmp_path)]) == 2
    assert "no subjects" in capsys.readouterr().err


def test_ANTI_VACUITY_agreeing_candidates_exit_zero(tmp_path):
    """Without this the census could flag everything and prove nothing."""
    root = _corpus(tmp_path,
                   [("AAPL", "2025-03-31", "10-Q", "2025-05-01")],
                   [("AAPL", "2025-03-31", "10-Q", "2025-05-01")])
    assert C.main(["--root", root]) == 0


def test_the_REAL_corpus_has_NO_ambiguous_keys():
    """Measured 2026-08-01: codex's concern was valid as a possibility and did NOT occur
    here — so the published deltas were not manufactured. That is now verified rather
    than assumed."""
    import os
    root = "/Users/renhao/git/github/RenQuant/data/edgar_pit"
    if not os.path.isdir(root):
        pytest.skip("v2 corpus not present on this machine")
    rep = C.census(root)
    assert rep["n_ambiguous_pairs"] == 0, rep["pairwise"]
