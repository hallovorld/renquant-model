"""GOAL-7 — the one non-self-referential validation reported `nan`, not a failure.

`build_total_return_series.py` runs V1-V7 on the total-return series. V1/V2/V3/V7
all check the construction against **its own identity**; V5 is the only external
anchor, comparing against the vendor's own `adj close`.

MEASURED 2026-07-31: all six candidate files carry an `adj close` column with 2658
rows and **zero** non-null values. The selector tested the column's PRESENCE, so V5
correlated two all-NaN series and wrote `nan`. In a results bundle a NaN reads as
"ran"; this one meant "measured nothing".
"""

from __future__ import annotations

import ast
import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "build_total_return_series.py"
COVERAGE = ROOT / ("doc/research/evidence/2026-07-31-v5-vacuous/"
                   "vendor_adj_close_coverage.csv")
BUNDLE = ROOT / ("doc/research/data/2026-07-30-momentum-total-return/"
                 "total_return_validation.json")


def test_the_vendor_column_is_present_and_entirely_empty():
    rows = list(csv.DictReader(COVERAGE.open()))
    assert len(rows) == 6
    assert all(r["column"] == "adj close" for r in rows)
    assert all(int(r["rows"]) == 2658 for r in rows)
    assert all(int(r["non_null"]) == 0 for r in rows)      # THE finding


def test_the_published_bundle_recorded_nan_for_every_ticker():
    """Pins what the vacuous run actually produced, so the correction cannot rot."""
    v5 = json.loads(BUNDLE.read_text(encoding="utf-8"))["V5"]
    assert len(v5) == 6
    for t, d in v5.items():
        for k in ("corr", "mean_abs_bp", "max_abs_bp"):
            assert d[k] != d[k], (t, k)                    # NaN != NaN


def test_the_selector_now_requires_CONTENT_not_presence():
    """AST, not grep: the explanatory docstring mentions the old condition."""
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    fns = [n.name for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert "_usable_vendor" in fns


def test_the_run_reports_its_own_V5_status():
    """A bundle of NaNs is indistinguishable from a bundle of results unless the
    run says which it is."""
    src = TOOL.read_text(encoding="utf-8")
    assert '"V5_status"' in src
    assert '"V5_usable_rows_by_ticker"' in src


def test_the_INTERNAL_construction_check_did_collapse():
    """NARROWED after codex on #133: this is an INTERNAL result. It shows the
    construction removed what its own dividend column says was there — it cannot
    show the dividend DATA is right."""
    b = json.loads(BUNDLE.read_text(encoding="utf-8"))
    assert abs(b["V1_raw"]["diff_bp"] + 66.58) < 0.05
    assert abs(b["V1_raw"]["t"]) > 20
    assert abs(b["V1_tr"]["diff_bp"]) < 6.0
    assert abs(b["V1_tr"]["t"]) < 1.96          # no longer significant
    assert b["V2_max_abs_diff_nonpayers"] == 0.0
    assert b["V3_max_identity_error"] < 1e-15


def test_every_surviving_validation_reads_the_SAME_dividend_column():
    """The line of code that makes V1-V3/V7 internal, asserted so the narrowing
    cannot be undone by prose.

    `exdiv_gap` identifies ex-dividend days as `s["dividend"] > 0` -- the same column
    the TR construction consumes. A wrong feed is therefore invisible to BOTH: the
    construction will not adjust for it and the test will not look for it.
    """
    src = (ROOT / "tools" / "build_total_return_series.py").read_text(encoding="utf-8")
    body = src[src.index("def exdiv_gap("):src.index("def ", src.index("def exdiv_gap(") + 10)]
    assert 's["dividend"] > 0' in body
    # and the construction reads the same column
    assert 'dividend' in src[:src.index("def exdiv_gap(")]


def test_the_document_states_the_narrowed_status():
    doc = (ROOT / "doc/progress/2026-07-31-v5-independent-check-was-vacuous.md"
           ).read_text(encoding="utf-8")
    assert "the dividend DATA is not" in doc
    assert "NOT established" in doc
    assert "supersedes the earlier phrasing" in doc
