"""Tests for the P0 clean-IC artifact exporter (oos_ic_export).

Pure-metric helpers are tested against constructed frames where the right
answer is known analytically; the CLI is smoke-tested end-to-end with a tiny
real HFPatchTSTRanker checkpoint in the production ``.pt`` format so the
loader, split/OOS contracts, battery, and manifest schema are all exercised.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_patchtst import oos_ic_export as oie


# ─── per_date_ic / mean_ic ───────────────────────────────────────────────────

def _scored_frame(n_dates: int = 12, n_names: int = 8, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range("2025-01-01", periods=n_dates, freq="B"):
        labels = rng.normal(size=n_names)
        for i in range(n_names):
            rows.append({"date": d, "ticker": f"T{i}",
                         "pred": labels[i], "label": labels[i]})
    return pd.DataFrame(rows)


def test_per_date_ic_perfect_monotone_is_one() -> None:
    scored = _scored_frame()
    ic = oie.per_date_ic(scored)
    assert len(ic) == 12
    assert np.allclose(ic["ic"], 1.0)
    assert (ic["n_names"] == 8).all()
    assert oie.mean_ic(ic) == pytest.approx(1.0)


def test_per_date_ic_inverted_is_minus_one() -> None:
    scored = _scored_frame()
    scored["pred"] = -scored["pred"]
    assert oie.mean_ic(oie.per_date_ic(scored)) == pytest.approx(-1.0)


def test_per_date_ic_drops_thin_dates() -> None:
    scored = _scored_frame(n_dates=3, n_names=4)  # below MIN_NAMES_PER_DATE=5
    assert oie.per_date_ic(scored).empty


def test_shuffled_label_ic_near_zero() -> None:
    scored = _scored_frame(n_dates=60, n_names=40)
    assert abs(oie.shuffled_label_ic(scored)) < 0.05  # pooled shuffle kills signal


# ─── timeshift placebo ───────────────────────────────────────────────────────

def _panel(n_dates: int = 160, n_names: int = 8, seed: int = 1) -> pd.DataFrame:
    """iid-label panel: no real temporal structure, so any placebo IC is leak."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range("2024-01-01", periods=n_dates, freq="B"):
        for i in range(n_names):
            rows.append({"date": d, "ticker": f"T{i}",
                         "fwd_5d_excess": rng.normal()})
    return pd.DataFrame(rows)


def test_timeshift_placebo_clean_model_passes() -> None:
    panel = _panel()
    # An honest model: pred correlates with the SAME-date label only.
    scored = panel.rename(columns={"fwd_5d_excess": "label"}).copy()
    scored["pred"] = scored["label"] + 0.1 * np.random.default_rng(2).normal(size=len(scored))
    out = oie.timeshift_placebo(panel, scored, "fwd_5d_excess", gate_shift_days=10)
    gate = out["gate"]
    assert gate["aligned_real_ic"] > 0.8
    assert abs(gate["placebo_ic"]) < gate["threshold"]
    assert gate["passed"] is True


def test_timeshift_placebo_catches_future_label_leak() -> None:
    panel = _panel()
    shift = 10
    leaked = panel.sort_values(["ticker", "date"]).copy()
    # A leaky model: pred IS the label from `shift` trading days in the future.
    leaked["pred"] = leaked.groupby("ticker")["fwd_5d_excess"].shift(-shift)
    scored = (leaked.rename(columns={"fwd_5d_excess": "label"})
              .dropna(subset=["pred"]))
    out = oie.timeshift_placebo(panel, scored, "fwd_5d_excess", gate_shift_days=shift)
    gate = out["gate"]
    assert gate["placebo_ic"] > 0.9          # placebo correlates ~perfectly
    assert abs(gate["placebo_ic"]) >= gate["threshold"]
    assert gate["passed"] is False


def test_timeshift_placebo_fails_closed_when_unalignable() -> None:
    panel = _panel(n_dates=12)
    scored = panel.rename(columns={"fwd_5d_excess": "label"}).copy()
    scored["pred"] = scored["label"]
    out = oie.timeshift_placebo(panel, scored, "fwd_5d_excess", gate_shift_days=252)
    assert out["gate"]["passed"] is False
    assert out["gate"]["placebo_ic"] is None


# ─── battery verdict / thresholds ────────────────────────────────────────────

def test_placebo_threshold_mirrors_wf_gate() -> None:
    assert oie.placebo_ic_threshold(0.0) == 0.005
    assert oie.placebo_ic_threshold(0.10) == pytest.approx(0.05)
    assert oie.placebo_ic_threshold(-0.10) == pytest.approx(0.05)


def test_battery_verdict_requires_both_checks() -> None:
    good_gate = {"passed": True, "reason": "ok"}
    bad_gate = {"passed": False, "reason": "leak"}
    assert oie.battery_verdict(0.07, 0.001, good_gate)["passed"] is True
    assert oie.battery_verdict(0.07, 0.02, good_gate)["passed"] is False
    assert oie.battery_verdict(0.07, 0.001, bad_gate)["passed"] is False


def test_oos_contract() -> None:
    ok = oie.validate_oos_contract(pd.Timestamp("2025-02-06"), "2024-11-13", 60)
    assert ok["passed"] is True
    bad = oie.validate_oos_contract(pd.Timestamp("2024-12-01"), "2024-11-13", 60)
    assert bad["passed"] is False
    missing = oie.validate_oos_contract(pd.Timestamp("2025-02-06"), None, 60)
    assert missing["passed"] is False


# ─── end-to-end CLI smoke (tiny real checkpoint, prod .pt format) ────────────

def test_cli_end_to_end_smoke(tmp_path: Path) -> None:
    import torch
    from transformers import PatchTSTConfig

    from renquant_model_patchtst import hf_trainer as hf

    seq_len, n_feats, label = 8, 3, "fwd_5d_excess"
    rng = np.random.default_rng(7)
    rows = []
    for d in pd.date_range("2024-01-01", periods=130, freq="B"):
        for i in range(8):
            rows.append({"date": d, "ticker": f"T{i}",
                         **{f"f{k}": rng.normal() for k in range(n_feats)},
                         label: rng.normal()})
    dataset = tmp_path / "panel.parquet"
    pd.DataFrame(rows).to_parquet(dataset, index=False)

    # Discover the split's effective train cutoff so the OOS contract holds.
    panel, feat_cols = hf.load_panel_with_split(
        dataset, "all", label, preprocess=False,
        val_tail_pct=0.3, embargo_days=8)
    cutoff = panel.loc[panel["split_label"] == "train", "date"].max()

    cfg = PatchTSTConfig(num_input_channels=n_feats, context_length=seq_len,
                         patch_length=2, d_model=16, num_attention_heads=2,
                         num_hidden_layers=1)
    model = hf.HFPatchTSTRanker(cfg, use_distributional_head=False)
    ckpt_path = tmp_path / "tiny_model.pt"
    torch.save({
        "state_dict": model.state_dict(),
        "config_dict": cfg.to_dict(),
        "feature_cols": feat_cols,
        "seq_len": seq_len,
        "label_col": label,
        "lookahead_days": 5,
        "effective_train_cutoff_date": str(cutoff.date()),
        "uses_distributional_head": False,
    }, ckpt_path)
    Path(str(ckpt_path) + ".metadata.json").write_text(json.dumps({
        "training_contract": {
            "dataset": str(dataset),
            "cut": "all",
            "label_col": label,
            "hyperparameters": {"embargo_days": 8},
        },
    }))

    out_dir = tmp_path / "out"
    rc = oie.main([
        "--checkpoint", str(ckpt_path),
        "--val-tail-pct", "0.3",
        "--out-dir", str(out_dir),
    ])
    assert rc in (0, 1)  # untrained tiny model: verdict may fail, harness must not

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["kind"] == "patchtst_oos_ic_export"
    assert manifest["checkpoint"]["sha256"].startswith("sha256:")
    assert manifest["panel"]["sha256"].startswith("sha256:")
    assert manifest["oos_contract"]["passed"] is True
    assert manifest["sanity_battery"]["timeshift_placebo"]["shift_days"] == 10
    assert isinstance(manifest["metrics"]["mean_oos_ic"], float)

    # Chain-of-custody: the manifest must carry the predictions CONTENT hash
    # (not just its path), so a downstream consumer can detect a same-path
    # swap of predictions.parquet. The hash must match the bytes on disk.
    import hashlib
    ph = manifest["output_hashes"]["predictions_parquet_sha256"]
    assert ph.startswith("sha256:")
    on_disk = "sha256:" + hashlib.sha256(
        (out_dir / "predictions.parquet").read_bytes()
    ).hexdigest()
    assert ph == on_disk

    ic = pd.read_csv(out_dir / "oos_ic_daily.csv", parse_dates=["date"])
    assert {"date", "ic", "n_names"} <= set(ic.columns)
    assert len(ic) > 0
    # Every exported date must be inside the validation window (true OOS).
    val_dates = set(panel.loc[panel["split_label"] == "val", "date"])
    assert set(ic["date"]) <= val_dates
    assert (out_dir / "oos_ic_daily.parquet").exists()
    assert (out_dir / "predictions.parquet").exists()
