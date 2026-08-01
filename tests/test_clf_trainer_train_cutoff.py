"""The clf lane could not produce a walk-forward corpus, because its trainer had no cutoff.

Measured 2026-08-01: clf's recipe matches **0 of 85** WF corpus folds. A WF corpus is a
series of POINT-IN-TIME artifacts each trained to a different cutoff, and
`train_topdecile_clf_shadow.py` had only `--data-dir/--out/--seed`: it trained on whatever
the data directory held and then *reported* where that ended. So "the certified clf recipe
has no out-of-sample corpus" was never a scheduling oversight — the lane could not make one.

The load-bearing detail is WHERE the truncation goes: before `build_normalization`, which
fits feature moments on `train`. Truncating after it would leak post-cutoff statistics into
a fold that must know nothing after its cutoff — a corpus that looks valid and is worthless.
"""

from __future__ import annotations

import ast
import pathlib

import pandas as pd
import pytest

SRC = (pathlib.Path(__file__).resolve().parent.parent / "scripts"
       / "train_topdecile_clf_shadow.py")


def _main_body() -> list[ast.stmt]:
    tree = ast.parse(SRC.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    return fn.body


def _line_of(pred) -> int:
    for node in ast.walk(ast.parse(SRC.read_text())):
        if pred(node):
            return node.lineno
    raise AssertionError("not found")


# ------------------------------------------------------- the ordering that matters --
def test_truncation_happens_BEFORE_build_normalization():
    """The leak this prevents: fitting feature means/stds on the full panel and only then
    cutting gives every fold post-cutoff moments."""
    src = SRC.read_text()
    cut_at = src.index("train = train[train[\"date\"] <= cut]")
    norm_at = src.index("build_normalization(train")
    assert cut_at < norm_at, "truncation must precede normalisation"


def test_truncation_also_precedes_the_label_and_the_matrix():
    src = SRC.read_text()
    cut_at = src.index("train = train[train[\"date\"] <= cut]")
    assert cut_at < src.index("y = top_decile_label(train)")
    assert cut_at < src.index("panel_training_matrix(train")


# ------------------------------------------------------------------ the interface --
def test_the_flag_exists_and_DEFAULTS_TO_OFF():
    """Omitting it must reproduce the existing behaviour exactly — this trainer already
    produced a deployed shadow artifact, and changing that silently would invalidate it."""
    src = SRC.read_text()
    assert '"--train-cutoff"' in src
    assert 'default=None' in src


def test_an_empty_result_REFUSES_rather_than_training_on_nothing():
    """A cutoff before the panel starts must not yield a model fitted on zero rows and a
    cheerfully stamped cutoff."""
    src = SRC.read_text()
    i = src.index("--train-cutoff {args.train_cutoff}")
    assert "refusing to train on an empty panel" in src[i:i + 400]
    assert "raise SystemExit" in src[max(0, i - 300):i + 100]


def test_the_filter_is_INCLUSIVE_of_the_cutoff_date():
    """`<=`, not `<`: a fold trained 'to 2024-01-31' includes that session, which is what
    the GBDT schedule's cutoffs mean."""
    assert 'train["date"] <= cut' in SRC.read_text()


# --------------------------------------------------------------- the semantics -----
def test_effective_train_cutoff_reports_the_TRUNCATED_max():
    """The stamped cutoff must describe the fold, not the data directory. It is computed
    from `train` after truncation, so this is a property of the ordering above."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("clf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-06-01", "2025-01-01"]),
                       m.LABEL: [0.1, 0.2, 0.3]})
    assert m.effective_train_cutoff(df) == "2025-01-01"
    assert m.effective_train_cutoff(df[df["date"] <= pd.Timestamp("2024-06-01")]) \
        == "2024-06-01"


def test_top_decile_label_is_PER_DATE_so_truncation_cannot_change_kept_rows():
    """Ranking is within date, so dropping later dates leaves earlier rows' labels
    untouched — which is what makes a per-fold retrain comparable to the full one."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("clf2", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"] * 10 + ["2025-01-01"] * 10),
        m.LABEL: list(range(10)) + list(range(10))})
    full = m.top_decile_label(df)
    cut = m.top_decile_label(df[df["date"] <= pd.Timestamp("2024-01-01")])
    assert list(full[:10]) == list(cut)
