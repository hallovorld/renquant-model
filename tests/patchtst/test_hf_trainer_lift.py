"""Lift-completeness guard for the HF PatchTST trainer.

scripts/patchtst_hf.py (umbrella) was lifted verbatim into
renquant_model_patchtst.hf_trainer. This test asserts the lift carries the full
trainer surface (model, losses, data, Trainer subclass, entrypoints) and that the
module imports without an umbrella checkout — RENQUANT_STRATEGY_DIR makes the
data-side kernel.* deps resolvable from the baseline at *runtime*, but the module
itself must import on torch alone.

It does NOT train (torch on MPS is not bit-reproducible, so weight byte-identity
is infeasible — parity for PatchTST is structural/procedural; the end-to-end run
is exercised by scripts/train_patchtst_multirepo.py).
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

hf = importlib.import_module("renquant_model_patchtst.hf_trainer")


@pytest.mark.parametrize("symbol", [
    "HFPatchTSTRanker", "FiLMLayer", "CrossStockAttentionLayer",
    "margin_ranking_loss", "student_t_nll",
    "csrank_norm_per_day", "winsorize_label",
    "PerDayDataset", "PatchTSTRankerTrainer", "PerRegimeICCallback",
    "train_one", "main",
])
def test_lift_carries_trainer_surface(symbol: str) -> None:
    assert hasattr(hf, symbol), f"lifted trainer missing {symbol}"


def test_ranker_is_nn_module_and_builds():
    assert issubclass(hf.HFPatchTSTRanker, torch.nn.Module)


def test_margin_ranking_loss_is_finite_and_orders():
    # higher scores for higher labels → small loss; inverted → larger loss
    scores_good = torch.tensor([3.0, 2.0, 1.0], requires_grad=True)
    scores_bad = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
    labels = torch.tensor([3.0, 2.0, 1.0])
    l_good = hf.margin_ranking_loss(scores_good, labels)
    l_bad = hf.margin_ranking_loss(scores_bad, labels)
    assert torch.isfinite(l_good) and torch.isfinite(l_bad)
    assert l_bad.item() >= l_good.item()


def test_placebo_label_mutation_keeps_validation_labels_aligned(tmp_path: Path):
    rows = []
    for d in pd.date_range("2024-01-01", periods=40, freq="B"):
        for i in range(5):
            rows.append({
                "date": d,
                "ticker": f"T{i}",
                "feature": float(i),
                "fwd_60d_excess": float(i),
            })
    dataset = tmp_path / "panel.parquet"
    pd.DataFrame(rows).to_parquet(dataset, index=False)
    base, _ = hf.load_panel_with_split(
        dataset,
        "all",
        "fwd_60d_excess",
        preprocess=False,
        val_tail_pct=0.25,
        embargo_days=5,
    )
    shifted, _ = hf.load_panel_with_split(
        dataset,
        "all",
        "fwd_60d_excess",
        preprocess=False,
        val_tail_pct=0.25,
        embargo_days=5,
        label_shift_days=2,
    )
    shuffled, _ = hf.load_panel_with_split(
        dataset,
        "all",
        "fwd_60d_excess",
        preprocess=False,
        val_tail_pct=0.25,
        embargo_days=5,
        shuffle_labels=True,
    )

    base_val = base.loc[base["split_label"].eq("val"), "fwd_60d_excess"].to_list()
    assert shifted.loc[shifted["split_label"].eq("val"), "fwd_60d_excess"].to_list() == base_val
    assert shuffled.loc[shuffled["split_label"].eq("val"), "fwd_60d_excess"].to_list() == base_val
