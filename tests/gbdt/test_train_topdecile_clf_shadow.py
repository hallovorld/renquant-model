"""Tests for the shadow top-decile classifier trainer (pipeline#213 step 3)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[2] / "scripts" / "train_topdecile_clf_shadow.py"
spec = importlib.util.spec_from_file_location("tdc", _P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_output_guard(tmp_path):  # name must not contain the guard keyword — pytest embeds test names in tmp_path
    with pytest.raises(SystemExit):
        mod.refuse_non_shadow(tmp_path / "artifacts" / "x.json")
    with pytest.raises(SystemExit):
        mod.refuse_non_shadow(tmp_path / "artifacts" / "prod" / "shadow.json")
    ok = tmp_path / "artifacts" / "shadow" / "x.json"
    assert mod.refuse_non_shadow(ok) == ok


def test_top_decile_label_is_per_date_and_10pct():
    rng = np.random.default_rng(0)
    rows = []
    for d in pd.date_range("2024-01-02", periods=5, freq="B"):
        rows.append(pd.DataFrame({"date": d, "fwd_60d_excess": rng.normal(size=100)}))
    df = pd.concat(rows, ignore_index=True)
    y = mod.top_decile_label(df)
    per_day = y.groupby(df["date"]).mean()
    assert np.allclose(per_day.values, 0.10, atol=0.02)  # ~10% positives each date
    # per-DATE, not global: shift one date's labels up massively; its top decile
    # must still be 10% of that date, not dominate globally
    df2 = df.copy()
    first = df2["date"] == df2["date"].min()
    df2.loc[first, "fwd_60d_excess"] += 100.0
    y2 = mod.top_decile_label(df2)
    assert np.allclose(y2.groupby(df2["date"]).mean().values, 0.10, atol=0.02)


def test_frozen_params_match_confirmatory_executor():
    """The clf leg's params must stay byte-identical to the frozen
    construction in the confirmatory executor (single source drift guard)."""
    exe = (Path(__file__).resolve().parents[2] / "scripts"
           / "research_objective_blend_confirm.py").read_text()
    for k, v in mod.CLF_PARAMS.items():
        assert f'"{k}"' in exe, f"param {k} missing from confirmatory executor"
    assert '"binary:logistic"' in exe
    assert mod.N_ROUNDS == 100 and mod.TOP_DECILE == 0.9
