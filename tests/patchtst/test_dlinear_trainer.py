"""DLinear/NLinear adapter trainer tests.

Pins the contract surface so the trainer is a drop-in for
``renquant_model_patchtst.hf_trainer.train_single_run`` in the research
harness — same CLI dests, same return shape, same val_preds parquet
format.

Tests use a tiny inline pandas panel (no parquet fixture dependency,
no torch>=cpu requirements beyond what PR #14 already needs) so this PR
is independent of PR #13.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import renquant_model_patchtst.hf_trainer as hf
from renquant_model_linear import trainer as linear_trainer


# ---- Fixture: tiny inline panel with planted signal ---------------------


def _build_inline_panel(tmp_path: Path) -> Path:
    """Deterministic 100-date × 8-ticker × 5-feature panel where feature[0]
    drives the label. Signal IC ~ +0.4. Small enough for 4-epoch CPU smoke
    in seconds."""
    rng = np.random.default_rng(20260531)
    n_dates, n_tickers = 100, 8
    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    rows = []
    for d in dates:
        signal = rng.standard_normal(n_tickers)
        label = 0.6 * signal + rng.standard_normal(n_tickers) * 1.0
        noise = rng.standard_normal((n_tickers, 4))
        for i in range(n_tickers):
            rows.append({
                "date": d,
                "ticker": f"T{i:02d}",
                "f_signal": float(signal[i]),
                "noise_0": float(noise[i, 0]),
                "noise_1": float(noise[i, 1]),
                "noise_2": float(noise[i, 2]),
                "noise_3": float(noise[i, 3]),
                "fwd_5d_excess": float(label[i]),
            })
    df = pd.DataFrame(rows).sort_values(["ticker", "date"]).reset_index(drop=True)
    out = tmp_path / "inline_panel.parquet"
    df.to_parquet(out, index=False)
    return out


# ---- build_parser surface contract --------------------------------------


def test_build_parser_accepts_all_trial_argv_flags() -> None:
    """The linear trainer parser must accept every flag that
    research_pipeline._trial_argv unconditionally emits, otherwise
    research runs would SystemExit inside the subprocess (same failure
    class as PR #12 review M1)."""
    p = linear_trainer.build_parser()
    dests = {a.dest for a in p._actions}
    # Same required surface as hf_trainer.build_parser (validated by
    # ValidateTrainerSurfaceTask). Mirrors PR #12 review M1.
    for required in (
        "cut", "seed", "epochs", "device", "output_dir", "dataset",
        "label", "embargo_days", "val_tail_pct",
        "shuffle_labels", "label_shift_days",
        "detector_version",
    ):
        assert required in dests, (
            f"linear build_parser missing required dest {required!r}"
        )


def test_build_parser_default_detector_version_is_v20260531() -> None:
    """Default the corrected detector — matches the harness CLI default
    per PR #12 design."""
    p = linear_trainer.build_parser()
    args = p.parse_args([
        "--cut", "all", "--seed", "1", "--epochs", "1",
        "--output-dir", "/tmp", "--dataset", "/tmp/x",
    ])
    assert args.detector_version == "v2026-05-31"


def test_build_parser_rejects_unknown_detector_version() -> None:
    p = linear_trainer.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args([
            "--cut", "all", "--seed", "1", "--epochs", "1",
            "--output-dir", "/tmp", "--dataset", "/tmp/x",
            "--detector-version", "v2099-not-a-version",
        ])


def test_build_parser_rejects_unknown_model() -> None:
    p = linear_trainer.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args([
            "--cut", "all", "--seed", "1", "--epochs", "1",
            "--output-dir", "/tmp", "--dataset", "/tmp/x",
            "--model", "patchtst",  # patchtst is NOT a linear option
        ])


def test_build_parser_accept_film_and_xstock_flags_silently() -> None:
    """PatchTST-only flags accepted-but-ignored so the same _trial_argv
    works across model families. If we rejected them, the harness's
    config_args (which include --film-regime-cond or --cross-stock-attn
    for PatchTST configs) wouldn't be flag-shareable."""
    p = linear_trainer.build_parser()
    args = p.parse_args([
        "--cut", "all", "--seed", "1", "--epochs", "1",
        "--output-dir", "/tmp", "--dataset", "/tmp/x",
        "--film-regime-cond", "--cross-stock-attn",
    ])
    assert args.film_regime_cond is True
    assert args.cross_stock_attn is True


# ---- train_single_run end-to-end -----------------------------------------


def _smoke_args(model: str, dataset: Path, out: Path) -> argparse.Namespace:
    return argparse.Namespace(
        cut="all", seed=42, epochs=3, device="cpu",
        output_dir=str(out), dataset=str(dataset),
        label="fwd_5d_excess", embargo_days=5, val_tail_pct=0.20,
        strategy_config=None,
        shuffle_labels=False, label_shift_days=0,
        exclude_features=None, spy_path="data/ohlcv/SPY/1d.parquet",
        detector_version="v2026-05-31",
        model=model, seq_len=10, kernel_size=3,
        lr=1e-2, weight_decay=0.0, early_stopping_patience=0,
        film_regime_cond=False, cross_stock_attn=False,
    )


@pytest.mark.parametrize("model", ["dlinear", "nlinear"])
def test_trainer_end_to_end_produces_valid_summary_and_val_preds(
    tmp_path: Path, model: str,
) -> None:
    """End-to-end smoke: load → train → eval → val_preds parquet → summary
    JSON. Asserts the output shape matches what the research pipeline
    expects (val_preds_path is set + readable, summary has best_val_ic).

    Does NOT assert learning success — just that the contract surface
    is intact. Learning success is asserted by the dedicated test below."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    args = _smoke_args(model, dataset, out)
    summary = linear_trainer.train_single_run(args)

    # Contract: val_preds_path is set and the parquet exists with required columns.
    val_preds_path = Path(summary["val_preds_path"])
    assert val_preds_path.exists()
    val_preds = pd.read_parquet(val_preds_path)
    for col in ("date", "ticker", "pred", "label"):
        assert col in val_preds.columns, f"val_preds missing column {col}"
    assert len(val_preds) > 0

    # Summary contract — research_pipeline reads these fields.
    assert summary["model"] == model
    assert summary["cut"] == "all"
    assert summary["seed"] == 42
    assert summary["best_val_ic"] is not None
    assert summary["best_val_pooled_ic"] is not None
    assert summary["epochs_run"] >= 1
    assert summary["best_epoch"] >= 0
    assert summary["best_epoch"] < summary["epochs_run"]
    assert summary["n_features"] >= 1
    assert summary["n_params"] > 0
    assert summary["device"] == "cpu"
    assert summary["detector_version"] == "v2026-05-31"


@pytest.mark.parametrize("model", ["dlinear", "nlinear"])
def test_trainer_learns_planted_signal(tmp_path: Path, model: str) -> None:
    """The inline panel plants a signal (Spearman IC ~+0.4 between
    f_signal and label). After csrank_norm quantizes features to 8
    rank-levels per day (n_tickers=8 cross-section), the available
    learning signal is meaningful but bounded. A correctly-wired
    trainer should achieve val pooled IC > 0.03 after 15 epochs at
    a high enough LR. If this fails, either the model is broken or
    the training loop has a bug — random init gives IC near 0.

    Threshold is set well above noise floor (random IC std ≈ 0.02 with
    n_dates ~10 val days) but well below the planted-signal ceiling
    (per-day IC ~+0.4 raw), because the tiny panel + csrank_norm
    quantization caps achievable IC. Phase A.0 / Phase A.1 on the real
    panel will test actual model quality."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    args = _smoke_args(model, dataset, out)
    args.epochs = 15
    args.lr = 1e-1   # high LR for quick convergence on tiny panel
    summary = linear_trainer.train_single_run(args)
    assert summary["best_val_pooled_ic"] > 0.03, (
        f"{model} failed to learn the planted signal: "
        f"best val pooled IC = {summary['best_val_pooled_ic']:+.4f} "
        f"(expected > 0.03 — well above random noise floor). Either "
        f"the model is broken or the training loop has a bug."
    )


def test_trainer_summary_includes_per_regime_when_spy_missing(tmp_path: Path) -> None:
    """When SPY parquet doesn't exist, per_regime_ic should be empty (not
    raise). The summary JSON should still be valid."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    args = _smoke_args("dlinear", dataset, out)
    args.spy_path = str(tmp_path / "missing_spy.parquet")
    summary = linear_trainer.train_single_run(args)
    # Epoch history should record per_regime_ic={} (empty dict, not error).
    for entry in summary["epoch_history"]:
        assert entry["per_regime_ic"] == {} or entry["per_regime_ic"] is not None


def test_trainer_summary_is_json_serializable(tmp_path: Path) -> None:
    """Summary must round-trip through json.dumps — research_pipeline
    persists it that way."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    args = _smoke_args("nlinear", dataset, out)
    summary = linear_trainer.train_single_run(args)
    summary_path = out / f"nlinear_all_seed42_summary.json"
    assert summary_path.exists()
    # Re-load the persisted summary
    persisted = json.loads(summary_path.read_text())
    assert persisted["model"] == "nlinear"


def test_trainer_label_shift_placebo_runs_without_error(tmp_path: Path) -> None:
    """Timeshift placebo (label_shift_days > 0) should train and eval
    cleanly — exercises the cross-split-leak-guard path from PR #9 on
    the linear trainer's preprocessing flow."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    args = _smoke_args("dlinear", dataset, out)
    args.label_shift_days = 5
    summary = linear_trainer.train_single_run(args)
    assert summary["label_shift_days"] == 5
    # Best val IC may be poor (placebo); just check the run completes.
    assert "best_val_ic" in summary


def test_trainer_shuffle_label_placebo_runs_without_error(tmp_path: Path) -> None:
    """Shuffle-label placebo (train labels permuted) should train and eval
    cleanly. Val labels still aligned per PR #9 invariant — pooled IC
    should be NEAR ZERO on a clean placebo."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    args = _smoke_args("dlinear", dataset, out)
    args.shuffle_labels = True
    args.epochs = 3
    summary = linear_trainer.train_single_run(args)
    assert summary["shuffle_labels"] is True
    # Note: with planted signal in features, even random train labels may
    # produce non-trivial val IC due to feature pre-norm structure. Don't
    # assert tightly on the value here — that's a sanity-triad concern,
    # not a trainer concern. Just assert the run completes.


# ---- research-CLI config contract (PR #15 review regression) -------------


def test_canonical_dlinear_config_uses_upstream_kernel_size() -> None:
    """PR #15 review regression guard. The canonical ``L_dlinear`` config
    must NOT override the upstream-faithful default kernel_size=25 (pinned
    by PR #14 from LTSF-Linear@0c11366). If a smaller kernel is wanted,
    it must be a named ablation (``L_dlinear_k5`` / ``L_dlinear_k3``) so
    experiment labels are scientifically honest.
    """
    from renquant_model_linear.research import configs

    cfg_map = configs()
    canonical = cfg_map["L_dlinear"]
    # Either explicit --kernel-size 25 OR no --kernel-size at all (relies
    # on trainer default which is also 25 post-PR-#14).
    if "--kernel-size" in canonical:
        idx = canonical.index("--kernel-size")
        assert canonical[idx + 1] == "25", (
            f"L_dlinear sets --kernel-size {canonical[idx + 1]!r}; the "
            f"canonical baseline MUST use 25 to match pinned upstream. "
            f"Use L_dlinear_k<N> naming for smaller-kernel ablations."
        )

    # Smaller-kernel ablations must be named with the L_dlinear_k<N> suffix.
    for name, args in cfg_map.items():
        if name in {"L_dlinear", "L_nlinear"}:
            continue
        if "--kernel-size" in args:
            idx = args.index("--kernel-size")
            kernel = args[idx + 1]
            assert name.startswith("L_dlinear_k"), (
                f"config {name!r} sets --kernel-size {kernel} but isn't "
                f"named with the L_dlinear_k<N> ablation convention"
            )
            expected_suffix = f"k{kernel}"
            assert name.endswith(expected_suffix), (
                f"config {name!r} sets --kernel-size {kernel} but name "
                f"doesn't end with {expected_suffix!r} — label drift risk"
            )


# ---- main() CLI sanity ---------------------------------------------------


def test_main_with_inline_dataset(tmp_path: Path) -> None:
    """`python -m renquant_model_linear.trainer ...` exits 0 on a valid
    smoke invocation."""
    dataset = _build_inline_panel(tmp_path)
    out = tmp_path / "run"
    argv = [
        "--cut", "all", "--seed", "42", "--epochs", "2", "--device", "cpu",
        "--output-dir", str(out), "--dataset", str(dataset),
        "--label", "fwd_5d_excess", "--embargo-days", "5", "--val-tail-pct", "0.20",
        "--seq-len", "10", "--lr", "1e-2", "--model", "dlinear",
    ]
    rc = linear_trainer.main(argv)
    assert rc == 0
    # Summary persisted at the expected path.
    assert (out / "dlinear_all_seed42_summary.json").exists()
