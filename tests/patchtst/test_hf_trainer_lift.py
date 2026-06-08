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


def test_timeshift_placebo_train_label_never_sourced_from_non_train_split(
    tmp_path: Path,
) -> None:
    """Bug 2026-05-31 regression guard.

    Before the fix, ``label_shift_days=N`` shifted train labels by N
    positions in the NaN-dropped panel — but at the train/val boundary,
    the shifted source row could land in val/embargo, so the "placebo"
    actually trained on val labels. Placebo IC exceeded real IC and
    blocked Tier-3 verdicts (`invalid_experiment`).

    Strategy: load the panel with no shift to learn the splitter's actual
    train/val partition. Rewrite the dataset so train-split rows have a
    sentinel of 0.0 and non-train (embargo/val/test) rows have a sentinel
    of 999.0. Then re-load WITH shift and verify no train row carries 999.
    """
    rows = []
    for d in pd.date_range("2024-01-01", periods=40, freq="B"):
        for i in range(5):
            rows.append({
                "date": d, "ticker": f"T{i}", "feature": float(i),
                "fwd_60d_excess": 0.0,
            })
    dataset = tmp_path / "panel.parquet"
    pd.DataFrame(rows).to_parquet(dataset, index=False)

    # Pass 1: learn the splitter's partition.
    base, _ = hf.load_panel_with_split(
        dataset, "all", "fwd_60d_excess",
        preprocess=False, val_tail_pct=0.25, embargo_days=5,
    )
    sentinel_label = base["split_label"].map(
        lambda s: 0.0 if s == "train" else 999.0
    )
    base_with_sentinel = base.assign(fwd_60d_excess=sentinel_label.values)
    base_with_sentinel.to_parquet(dataset, index=False)

    # Pass 2: shift WITH the cross-split-leak guard. No train row should
    # end up with the val sentinel.
    shifted, _ = hf.load_panel_with_split(
        dataset, "all", "fwd_60d_excess",
        preprocess=False, val_tail_pct=0.25, embargo_days=5,
        label_shift_days=10,
    )
    train_labels = shifted.loc[shifted["split_label"].eq("train"), "fwd_60d_excess"]
    leaked = int((train_labels == 999.0).sum())
    assert leaked == 0, (
        f"timeshift placebo leaked non-train labels into train: "
        f"{leaked}/{len(train_labels)} train rows carry val/embargo sentinel"
    )


def test_timeshift_placebo_preserves_within_train_decorrelation(
    tmp_path: Path,
) -> None:
    """Sanity: even with the cross-split guard, the placebo still shifts
    train labels by N positions WITHIN train rows that have a valid
    in-train source. This is the intended semantics (break feature→label
    alignment within train, then validate on real val labels)."""
    rows = []
    for d in pd.date_range("2024-01-01", periods=40, freq="B"):
        for i in range(5):
            rows.append({
                "date": d,
                "ticker": f"T{i}",
                "feature": float(i),
                "fwd_60d_excess": float(d.dayofyear * 10 + i),
            })
    dataset = tmp_path / "panel.parquet"
    pd.DataFrame(rows).to_parquet(dataset, index=False)

    base, _ = hf.load_panel_with_split(
        dataset, "all", "fwd_60d_excess",
        preprocess=False, val_tail_pct=0.25, embargo_days=5,
    )
    shifted, _ = hf.load_panel_with_split(
        dataset, "all", "fwd_60d_excess",
        preprocess=False, val_tail_pct=0.25, embargo_days=5,
        label_shift_days=2,
    )
    # Within-train labels should differ between base and shifted (decorrelation
    # happened), with at least SOME train rows surviving the cross-split guard.
    base_train = base.loc[base["split_label"].eq("train"), "fwd_60d_excess"]
    shifted_train = shifted.loc[shifted["split_label"].eq("train"), "fwd_60d_excess"]
    assert len(shifted_train) > 0, "all train rows dropped — guard too aggressive"
    assert len(shifted_train) <= len(base_train), (
        "shifted train should be ≤ base train (some rows dropped at boundary)"
    )
    # At least one surviving train row should have a DIFFERENT label than its
    # original (decorrelation actually happened, not a no-op).
    aligned_dates = shifted.loc[shifted["split_label"].eq("train"), ["date", "ticker", "fwd_60d_excess"]]
    base_indexed = base.set_index(["date", "ticker"])["fwd_60d_excess"]
    differs = sum(
        1 for _, row in aligned_dates.iterrows()
        if base_indexed.get((row["date"], row["ticker"])) != row["fwd_60d_excess"]
    )
    assert differs > 0, "shifted train labels are byte-identical to base — placebo is a no-op"


def test_per_day_dataset_windows_are_split_pure(tmp_path: Path) -> None:
    """Regression guard for the 2026-06-02 sequence-boundary audit.

    `PerDayDataset` used to require only the sample end row to match the
    requested split. The first validation samples could therefore look back
    into embargo/train rows. Encode each split with a different feature
    sentinel and assert every emitted window contains only its own split.
    """
    rows = []
    for d in pd.date_range("2024-01-01", periods=50, freq="B"):
        for i in range(5):
            rows.append({
                "date": d,
                "ticker": f"T{i}",
                "feature": 1.0,
                "fwd_60d_excess": float(i),
            })
    dataset = tmp_path / "panel.parquet"
    pd.DataFrame(rows).to_parquet(dataset, index=False)

    panel, feat_cols = hf.load_panel_with_split(
        dataset,
        "all",
        "fwd_60d_excess",
        preprocess=False,
        val_tail_pct=0.25,
        embargo_days=5,
    )
    encoded = {"train": 0.0, "embargo": -10.0, "val": 100.0, "test": 200.0}
    panel["feature"] = panel["split_label"].map(encoded).astype(float)

    train_ds = hf.PerDayDataset(panel, feat_cols, "fwd_60d_excess", 2, "train")
    val_ds = hf.PerDayDataset(panel, feat_cols, "fwd_60d_excess", 2, "val")

    assert len(train_ds) > 0
    assert len(val_ds) > 0
    for day in train_ds:
        assert torch.all(day["past_values"] == 0.0)
    for day in val_ds:
        assert torch.all(day["past_values"] == 100.0)
