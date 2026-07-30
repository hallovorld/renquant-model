"""The flip count is permitted ONLY under label isolation. Enforce it, don't promise it.

Codex on model#129: the measurement "can remain a descriptive feasibility measurement
only if it is explicitly isolated from outcome labels and cannot select a favorable
evaluation rule". Prose cannot enforce that. These tests can.

The isolation has to be at COLUMN level: measured 2026-07-30, two of the three pinned
panels carry `fwd_60d_excess` inline, so choosing which FILE to open isolates nothing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
_S = importlib.util.spec_from_file_location(
    "flip", REPO / "tools" / "goal4_decision_flip_count.py")
flip = importlib.util.module_from_spec(_S)
_S.loader.exec_module(flip)


@pytest.mark.parametrize("col", [
    "fwd_60d_excess", "label", "y_true", "target_60d", "excess_ret",
    "forward_return", "daily_ret",
])
def test_a_label_shaped_column_is_REFUSED_at_load(tmp_path, col):
    p = tmp_path / "x.parquet"
    pd.DataFrame({"date": ["2026-01-02"], "ticker": ["AAPL"], "cal": [0.1],
                  col: [0.0]}).to_parquet(p)
    with pytest.raises(ValueError, match="label-shaped"):
        flip.load_label_free(p, ["date", "ticker", "cal", col], "ticker", "cal")


def test_the_permitted_columns_still_load(tmp_path):
    """Anti-vacuity: a pattern that refused everything would pass every test above."""
    p = tmp_path / "x.parquet"
    pd.DataFrame({"date": ["2026-01-02"], "ticker": ["AAPL"], "cal": [0.1],
                  "fwd_60d_excess": [0.0]}).to_parquet(p)
    got = flip.load_label_free(p, ["date", "ticker", "cal"], "ticker", "cal")
    assert list(got.columns) == ["date", "ticker", "score"]
    assert "fwd_60d_excess" not in got.columns


def test_no_configured_panel_requests_a_label_column():
    """The committed configuration itself must be clean, not merely the loader."""
    for name, (_p, cols, _i, _s) in flip.PANELS.items():
        bad = [c for c in cols if flip.LABEL_RE.search(c)]
        assert bad == [], (name, bad)


def test_the_result_carries_no_performance_field():
    """Condition 2. A single return/IC/Sharpe key would turn a feasibility count into
    an unregistered screen."""
    panels = {}
    for i, name in enumerate(("prod_xgb", "certified_clf", "patchtst")):
        panels[name] = pd.DataFrame({
            "date": pd.to_datetime(["2026-01-02"] * 20),
            "ticker": [f"T{j}" for j in range(20)],
            "score": [(j * (i + 1)) % 20 for j in range(20)]})
    out = flip.flip_count(panels, top_n=5)
    assert out["REPORTS_NO_PERFORMANCE"] is True
    for k in out:
        assert not flip.LABEL_RE.search(k) or k == "REPORTS_NO_PERFORMANCE", k
    for banned in ("ic", "sharpe", "mean_return", "pnl", "alpha"):
        assert banned not in {kk.lower() for kk in out}


def test_the_ensemble_uses_RANKS_not_raw_scores():
    """Condition 3. The members are on different scales; a raw mean would be an
    unregistered weighting choice, i.e. exactly a 'favourable evaluation rule'
    selected after the fact. Rank-mean needs no scale information."""
    src = (REPO / "tools" / "goal4_decision_flip_count.py").read_text()
    assert 'rank(pct=True)' in src
    assert 'r_ens' in src
