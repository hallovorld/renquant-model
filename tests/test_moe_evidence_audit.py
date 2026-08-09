from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE = Path(__file__).resolve().parents[1] / "tools/moe_evidence_audit.py"
SPEC = importlib.util.spec_from_file_location("moe_evidence_audit", MODULE)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_block_summary_discards_partial_final_block() -> None:
    report = audit.block_summary(pd.Series(range(130)), block_size=60)

    assert report["n_blocks"] == 2
    assert report["n_dates_used"] == 120
    assert report["n_dates_dropped"] == 10
    assert report["mean"] == 59.5


def test_date_metrics_uses_panel_label_and_equal_rank_blend() -> None:
    frame = pd.DataFrame(
        {
            "panel": list(range(30)),
            "clf": list(range(29, -1, -1)),
            "label": list(range(30)),
        }
    )

    result = audit._date_metrics(frame, top_n=3)

    assert result["ic_panel"] == pytest.approx(1.0)
    assert result["ic_clf"] == pytest.approx(-1.0)
    assert result["top_n_panel"] == 28.0
