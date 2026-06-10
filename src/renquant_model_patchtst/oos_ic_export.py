#!/usr/bin/env python3
"""P0 clean-IC artifact exporter — IC→Sharpe RFC §7.1 / §5.5 (2026-06-10).

Produces the **placebo-clean OOS per-date cross-sectional IC series** for a
trained HF-PatchTST checkpoint, the artifact that the E1 transfer-coefficient
experiment (renquant-pipeline) consumes.

Design decisions (each one is load-bearing — see
``doc/2026-06-09-patchtst-wf-gate-eval-bug.md``):

* **Score on the model's OWN training dataset** (``training_contract.dataset``
  from the sidecar metadata), never a hardcoded panel. Root cause #1 of the
  2026-06-09 WF-gate false negative was scoring on the wrong dataset.
* **Score through the native training-eval path** (``load_panel_with_split`` +
  ``PerDayDataset`` + a plain forward pass) — the one path that demonstrably
  reproduces the model's held-out predictions. Root cause #2 of the gate bug
  was a second, divergent scorer implementation.
* **Split-pure windows.** ``PerDayDataset`` (post commit ``c5d15dc``) skips
  validation samples whose lookback crosses into embargo/train rows, closing
  the 2026-06-02 sequence-boundary purity follow-up. The first ~``seq_len``
  validation dates therefore have no samples; that is intentional.
* **OOS contract, fail closed**: ``val_start`` must be strictly after
  ``effective_train_cutoff + lookahead_days`` (business days), i.e. no training
  label window may overlap the evaluation window.
* **§5.2 eval-time sanity battery** with the SAME pass criteria as the WF gate
  (``renquant_backtesting.wf_gate.runner.run_sanity_battery``):
    - shuffled-label IC:  ``|ic| < 0.005``;
    - timeshift placebo at ``2 × label_horizon`` trading days:
      ``|placebo_ic| < max(0.005, 0.5 × |aligned_real_ic|)``;
      full shift grid retained as decay-shape diagnostics.

Outputs (under ``--out-dir``):
  ``oos_ic_daily.csv`` / ``.parquet``   (date, ic, n_names) — the P0 artifact
  ``predictions.parquet``               (date, ticker, pred, label) audit trail
  ``manifest.json``                     checkpoint sha256, dataset sha256,
                                        command, split/OOS contract, battery
                                        results, verdict

Usage (umbrella venv, repo root)::

    PYTHONPATH=../renquant-common/src:src \\
    ../RenQuant/.venv/bin/python -m renquant_model_patchtst.oos_ic_export \\
        --checkpoint ../RenQuant/artifacts/patchtst_shadow/\\
pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("oos_ic_export")

#: §5.2 gate thresholds — keep numerically identical to
#: renquant-backtesting ``wf_gate/runner.py`` (_placebo_ic_threshold / pass_shuf).
SHUFFLED_IC_MAX_ABS = 0.005
PLACEBO_RATIO_MAX = 0.5
PLACEBO_FLOOR = 0.005
SHIFT_GRID = (5, 10, 20, 40, 60, 80, 120, 180, 252)
MIN_NAMES_PER_DATE = 5


# ─── Pure metric helpers (unit-tested without torch) ─────────────────────────

def per_date_ic(scored: pd.DataFrame,
                pred_col: str = "pred",
                label_col: str = "label",
                min_names: int = MIN_NAMES_PER_DATE) -> pd.DataFrame:
    """Per-date cross-sectional Spearman IC.

    ``scored`` needs columns ``date``, ``pred_col``, ``label_col``. Dates with
    fewer than ``min_names`` rows or an undefined correlation are dropped.
    Returns a frame with columns ``date``, ``ic``, ``n_names``.
    """
    from scipy.stats import spearmanr  # noqa: PLC0415

    rows = []
    for date, g in scored.groupby("date"):
        if len(g) < min_names:
            continue
        ic = spearmanr(g[pred_col], g[label_col])[0]
        if np.isnan(ic):
            continue
        rows.append({"date": pd.Timestamp(date), "ic": float(ic),
                     "n_names": int(len(g))})
    return pd.DataFrame(rows, columns=["date", "ic", "n_names"])


def mean_ic(ic_daily: pd.DataFrame) -> float:
    return float(ic_daily["ic"].mean()) if len(ic_daily) else 0.0


def placebo_ic_threshold(aligned_real_ic: float) -> float:
    """Mirror of wf_gate ``_placebo_ic_threshold``."""
    return max(PLACEBO_FLOOR, PLACEBO_RATIO_MAX * abs(float(aligned_real_ic)))


def shuffled_label_ic(scored: pd.DataFrame, seed: int = 42) -> float:
    """Pooled-shuffle placebo: permute labels across the whole eval frame
    (same construction as the WF gate), recompute the mean per-date IC."""
    rng = np.random.default_rng(seed)
    shuf = scored.copy()
    shuf["label"] = rng.permutation(shuf["label"].to_numpy())
    return mean_ic(per_date_ic(shuf))


def timeshift_placebo(panel: pd.DataFrame, scored: pd.DataFrame,
                      label_col: str, gate_shift_days: int,
                      shift_grid: tuple[int, ...] = SHIFT_GRID) -> dict:
    """Timeshift placebo: correlate the model's scores against each ticker's
    label ``shift_days`` trading rows in the FUTURE. A leak-free model should
    show |placebo IC| well below the same-rows real IC at ``2 × horizon``.

    ``panel`` is the (preprocessed, label-NaN-dropped) training panel —
    shifts walk trading-row positions per ticker, exactly like the WF gate.
    Returns ``{"gate": {...}, "diagnostics": [...]}``.
    """
    if gate_shift_days not in shift_grid:
        shift_grid = tuple(sorted({*shift_grid, gate_shift_days}))

    panel_s = panel.sort_values(["ticker", "date"])
    scored_idx = scored.set_index(["ticker", "date"])
    diagnostics: list[dict] = []
    gate_row: dict = {
        "shift_days": gate_shift_days,
        "placebo_ic": None,
        "aligned_real_ic": None,
        "threshold": None,
        "passed": False,
        "reason": "placebo unavailable — too few aligned rows (fail closed)",
    }
    for shift_days in shift_grid:
        shifted = panel_s.groupby("ticker", sort=False)[label_col].shift(-shift_days)
        frame = pd.DataFrame({
            "ticker": panel_s["ticker"].to_numpy(),
            "date": panel_s["date"].to_numpy(),
            "y_real": panel_s[label_col].to_numpy(),
            "y_shift": shifted.to_numpy(),
        }).dropna(subset=["y_shift"]).set_index(["ticker", "date"])
        common = frame.index.intersection(scored_idx.index)
        if len(common) <= 100:
            diagnostics.append({"shift_days": shift_days, "ic": None,
                                "aligned_real_ic": None,
                                "n_rows": int(len(common)), "n_dates": 0,
                                "skipped": "too_few_aligned_rows"})
            continue
        aligned = pd.DataFrame({
            "pred": scored_idx.loc[common, "pred"].to_numpy(),
            "real": frame.loc[common, "y_real"].to_numpy(),
            "placebo": frame.loc[common, "y_shift"].to_numpy(),
            "date": [d for _, d in common],
        })
        aligned_real = mean_ic(per_date_ic(aligned, "pred", "real"))
        placebo = mean_ic(per_date_ic(aligned, "pred", "placebo"))
        diagnostics.append({
            "shift_days": shift_days,
            "ic": placebo,
            "aligned_real_ic": aligned_real,
            "n_rows": int(len(common)),
            "n_dates": int(aligned["date"].nunique()),
            "abs_ratio_to_aligned_real": (
                abs(placebo) / abs(aligned_real) if aligned_real else None),
        })
        if shift_days == gate_shift_days:
            threshold = placebo_ic_threshold(aligned_real)
            passed = abs(placebo) < threshold
            gate_row = {
                "shift_days": shift_days,
                "placebo_ic": placebo,
                "aligned_real_ic": aligned_real,
                "threshold": threshold,
                "passed": bool(passed),
                "reason": (
                    f"|placebo_ic|={abs(placebo):.4f} "
                    f"{'<' if passed else '>='} threshold={threshold:.4f} "
                    f"(max({PLACEBO_FLOOR}, {PLACEBO_RATIO_MAX}×|aligned_real_ic"
                    f"={aligned_real:+.4f}|))"
                ),
            }
    return {"gate": gate_row, "diagnostics": diagnostics}


def battery_verdict(real_ic: float, shuf_ic: float, placebo_gate: dict) -> dict:
    """Combine the §5.2 checks into a single fail-closed verdict."""
    pass_shuf = abs(shuf_ic) < SHUFFLED_IC_MAX_ABS
    pass_placebo = bool(placebo_gate.get("passed"))
    passed = pass_shuf and pass_placebo
    return {
        "passed": passed,
        "real_ic": real_ic,
        "shuffled_label": {
            "ic": shuf_ic,
            "threshold_abs": SHUFFLED_IC_MAX_ABS,
            "passed": pass_shuf,
        },
        "timeshift_placebo": placebo_gate,
        "reason": (
            f"{'PASS' if passed else 'FAIL'}: real_ic={real_ic:+.4f} "
            f"shuf_ic={shuf_ic:+.4f} (|·|<{SHUFFLED_IC_MAX_ABS}) "
            f"placebo: {placebo_gate.get('reason')}"
        ),
    }


# ─── Checkpoint / panel plumbing ─────────────────────────────────────────────

def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return "sha256:" + h.hexdigest()


def load_ranker_checkpoint(path: Path):
    """Load an ``hf_patchtst`` checkpoint into an eval-mode HFPatchTSTRanker.

    Same construction as the production scorer entry point
    (``renquant_model_patchtst.scorer.load``); kept to the native model class
    so eval predictions are bit-comparable with training-time ``val_preds``.
    Returns ``(model, ckpt_dict)``.
    """
    import torch  # noqa: PLC0415
    from transformers import PatchTSTConfig  # noqa: PLC0415

    from .hf_trainer import HFPatchTSTRanker  # noqa: PLC0415

    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    kind = str(ckpt.get("kind", "hf_patchtst"))
    if kind != "hf_patchtst":
        raise ValueError(f"oos_ic_export only supports hf_patchtst, got {kind!r}")
    cfg = PatchTSTConfig(**ckpt["config_dict"])
    model = HFPatchTSTRanker(
        cfg,
        use_distributional_head=bool(ckpt.get("uses_distributional_head", False)),
        use_film_regime=bool(ckpt.get("uses_film_regime", False)),
        use_cross_stock_attn=bool(ckpt.get("uses_cross_stock_attn", False)),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, ckpt


def validate_oos_contract(val_start: pd.Timestamp,
                          effective_train_cutoff: str | None,
                          lookahead_days: int) -> dict:
    """val_start must clear cutoff + lookahead business days — else fail closed."""
    if not effective_train_cutoff:
        return {"passed": False,
                "reason": "checkpoint missing effective_train_cutoff_date"}
    cutoff = pd.Timestamp(effective_train_cutoff)
    min_start = cutoff + pd.offsets.BDay(int(lookahead_days))
    passed = pd.Timestamp(val_start) > min_start
    return {
        "passed": bool(passed),
        "effective_train_cutoff_date": str(cutoff.date()),
        "lookahead_days": int(lookahead_days),
        "min_oos_start_exclusive": str(min_start.date()),
        "val_start": str(pd.Timestamp(val_start).date()),
        "reason": ("OOS contract satisfied" if passed else
                   f"val_start {pd.Timestamp(val_start).date()} does not clear "
                   f"cutoff+lookahead {min_start.date()} — NOT out-of-sample"),
    }


def score_val_split(model, val_ds, device: str = "cpu") -> pd.DataFrame:
    """Forward-pass every validation day; return (date, ticker, pred, label)."""
    import torch  # noqa: PLC0415

    model = model.to(device).eval()
    rows: list[pd.DataFrame] = []
    with torch.no_grad():
        for day in val_ds.days:
            x = day["past_values"].to(device)
            fwd_kwargs = {"past_values": x}
            if "regime_context" in day:
                fwd_kwargs["regime_context"] = day["regime_context"].to(device)
            outputs = model(**fwd_kwargs)
            rows.append(pd.DataFrame({
                "date": pd.to_datetime(day["dates"]),
                "ticker": day["tickers"],
                "pred": outputs["score"].detach().cpu().numpy().astype(float),
                "label": day["labels"].numpy().astype(float),
            }))
    if not rows:
        return pd.DataFrame(columns=["date", "ticker", "pred", "label"])
    return pd.concat(rows, ignore_index=True)


def crosscheck_against_val_preds(ic_daily: pd.DataFrame,
                                 val_preds_path: Path) -> dict:
    """Compare this harness's per-date IC series against the training-time
    ``val_preds.parquet`` series (no ticker column there — IC-series-level
    comparison only). High agreement on common dates validates the harness."""
    ref = pd.read_parquet(val_preds_path)
    ref_ic = per_date_ic(ref, "pred", "label")
    merged = ic_daily.merge(ref_ic, on="date", suffixes=("_export", "_trainval"))
    out = {
        "val_preds_path": str(val_preds_path),
        "trainval_mean_ic_full": mean_ic(ref_ic),
        "n_common_dates": int(len(merged)),
        "n_export_dates": int(len(ic_daily)),
        "n_trainval_dates": int(len(ref_ic)),
    }
    if len(merged) >= 10:
        out["export_mean_ic_common"] = float(merged["ic_export"].mean())
        out["trainval_mean_ic_common"] = float(merged["ic_trainval"].mean())
        out["daily_ic_corr_common"] = float(
            np.corrcoef(merged["ic_export"], merged["ic_trainval"])[0, 1])
    return out


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--checkpoint", required=True,
                   help="hf_patchtst .pt checkpoint (production scorer format)")
    p.add_argument("--metadata", default=None,
                   help="contract sidecar JSON (default: <checkpoint>.metadata.json)")
    p.add_argument("--dataset", default=None,
                   help="training panel parquet (default: training_contract.dataset "
                        "from the sidecar — scoring on any other panel is the "
                        "2026-06-09 gate bug)")
    p.add_argument("--cut", default=None,
                   help="split cut name (default: training_contract.cut)")
    p.add_argument("--val-tail-pct", type=float, default=0.10,
                   help="val tail fraction for cut=all (default 0.10, pt07 contract)")
    p.add_argument("--embargo-days", type=int, default=None,
                   help="embargo days (default: hyperparameters.embargo_days)")
    p.add_argument("--device", default="cpu",
                   help="cpu (deterministic, default) | mps | cuda")
    p.add_argument("--out-dir", default=None,
                   help="output dir (default: artifacts/diagnostics/oos_ic/"
                        "<ckpt-stem>_<UTC>)")
    p.add_argument("--max-days", type=int, default=None,
                   help="smoke mode: score only the first N validation days")
    p.add_argument("--val-preds", default=None,
                   help="optional training-time val_preds.parquet to cross-check")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    from .hf_trainer import MODEL_REPO, PerDayDataset, load_panel_with_split, resolve_runtime_path  # noqa: PLC0415

    ckpt_path = Path(args.checkpoint).expanduser().resolve()
    model, ckpt = load_ranker_checkpoint(ckpt_path)

    meta_path = Path(args.metadata) if args.metadata else Path(str(ckpt_path) + ".metadata.json")
    sidecar = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    contract = sidecar.get("training_contract") or {}
    hp = contract.get("hyperparameters") or {}

    label_col = str(ckpt.get("label_col") or contract.get("label_col") or "fwd_60d_excess")
    seq_len = int(ckpt["seq_len"])
    lookahead_days = int(ckpt.get("lookahead_days") or contract.get("lookahead_days") or 60)
    cut = str(args.cut or contract.get("cut") or "all")
    embargo_days = int(args.embargo_days if args.embargo_days is not None
                       else hp.get("embargo_days", 60))
    dataset_raw = args.dataset or contract.get("dataset")
    if not dataset_raw:
        log.error("no dataset recorded in sidecar and --dataset not given — "
                  "refusing to guess (2026-06-09 gate bug)")
        return 2
    dataset_path = resolve_runtime_path(dataset_raw)
    if not dataset_path.exists():
        log.error("dataset not found: %s", dataset_path)
        return 2

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (Path(args.out_dir) if args.out_dir else
               MODEL_REPO / "artifacts" / "diagnostics" / "oos_ic" /
               f"{ckpt_path.stem}_{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("checkpoint=%s", ckpt_path)
    log.info("dataset=%s cut=%s label=%s seq_len=%d embargo=%d val_tail=%.2f",
             dataset_path, cut, label_col, seq_len, embargo_days, args.val_tail_pct)

    panel, feat_cols = load_panel_with_split(
        dataset_path, cut, label_col,
        preprocess=True,
        val_tail_pct=args.val_tail_pct,
        embargo_days=embargo_days,
    )
    ckpt_feats = list(ckpt["feature_cols"])
    if feat_cols != ckpt_feats:
        log.error("feature column mismatch: panel has %d cols, checkpoint %d; "
                  "first diff: %s — refusing to score (OOD inputs)",
                  len(feat_cols), len(ckpt_feats),
                  next((a for a, b in zip(feat_cols, ckpt_feats) if a != b), "<length>"))
        return 2

    split_counts = panel["split_label"].value_counts().to_dict()
    expected_counts = contract.get("split_counts") or {}
    split_match = all(
        int(split_counts.get(k, 0)) == int(v) for k, v in expected_counts.items()
    ) if expected_counts else None
    if expected_counts and not split_match:
        log.warning("split counts differ from training contract: got=%s expected=%s "
                    "(recorded in manifest)", split_counts, expected_counts)

    val_dates_all = np.sort(panel.loc[panel["split_label"] == "val", "date"].unique())
    if val_dates_all.size == 0:
        log.error("no validation rows after split — nothing to evaluate")
        return 2
    oos = validate_oos_contract(
        pd.Timestamp(val_dates_all[0]),
        ckpt.get("effective_train_cutoff_date") or contract.get("effective_train_cutoff_date"),
        lookahead_days,
    )
    if not oos["passed"]:
        log.error("OOS contract FAILED: %s", oos["reason"])
        return 2
    log.info("OOS contract: %s", oos["reason"])

    val_ds = PerDayDataset(panel, feat_cols, label_col, seq_len, "val")
    if args.max_days is not None:
        val_ds.days = val_ds.days[: args.max_days]
        log.info("smoke mode: limited to %d days", len(val_ds.days))
    scored = score_val_split(model, val_ds, device=args.device)
    if scored.empty:
        log.error("no scored rows — split-pure val dataset is empty")
        return 2
    log.info("scored %d rows over %d dates (%s → %s)",
             len(scored), scored["date"].nunique(),
             scored["date"].min().date(), scored["date"].max().date())

    ic_daily = per_date_ic(scored)
    real = mean_ic(ic_daily)
    shuf = shuffled_label_ic(scored)
    horizon = lookahead_days
    placebo = timeshift_placebo(panel, scored, label_col, gate_shift_days=2 * horizon)
    verdict = battery_verdict(real, shuf, placebo["gate"])
    log.info("real_ic=%+.4f shuf_ic=%+.4f placebo@%dd=%s → %s",
             real, shuf, 2 * horizon,
             placebo["gate"].get("placebo_ic"), verdict["reason"])

    crosscheck = None
    val_preds_path = (Path(args.val_preds) if args.val_preds else
                      ckpt_path.parent / ckpt_path.name.replace("_model.pt", "_val_preds.parquet"))
    if val_preds_path.exists():
        crosscheck = crosscheck_against_val_preds(ic_daily, val_preds_path)
        log.info("cross-check vs training-time val_preds: %s", crosscheck)

    ic_daily.to_csv(out_dir / "oos_ic_daily.csv", index=False)
    ic_daily.to_parquet(out_dir / "oos_ic_daily.parquet", index=False)
    scored.to_parquet(out_dir / "predictions.parquet", index=False)

    manifest = {
        "schema_version": 1,
        "kind": "patchtst_oos_ic_export",
        "run_id": run_id,
        "command": " ".join([Path(sys.argv[0]).name, *(argv or sys.argv[1:])]),
        "checkpoint": {
            "path": str(ckpt_path),
            "sha256": sha256_file(ckpt_path),
            "label_col": label_col,
            "seq_len": seq_len,
            "lookahead_days": lookahead_days,
            "config_fingerprint": ckpt.get("config_fingerprint"),
            "trained_date": str(ckpt.get("trained_date")),
            "effective_train_cutoff_date": str(ckpt.get("effective_train_cutoff_date")),
        },
        "panel": {
            "path": str(dataset_path),
            "sha256": sha256_file(dataset_path),
            "cut": cut,
            "val_tail_pct": args.val_tail_pct,
            "embargo_days": embargo_days,
            "n_features": len(feat_cols),
            "split_counts": {k: int(v) for k, v in split_counts.items()},
            "split_counts_match_training_contract": split_match,
        },
        "oos_contract": oos,
        "split_purity": "PerDayDataset split-pure lookback windows (commit c5d15dc); "
                        "val samples whose lookback crosses embargo/train are skipped",
        "eval_window": {
            "start": str(scored["date"].min().date()),
            "end": str(scored["date"].max().date()),
            "n_dates": int(scored["date"].nunique()),
            "n_rows": int(len(scored)),
            "smoke_max_days": args.max_days,
        },
        "metrics": {
            "mean_oos_ic": real,
            "median_oos_ic": float(ic_daily["ic"].median()) if len(ic_daily) else None,
            "ic_std": float(ic_daily["ic"].std()) if len(ic_daily) else None,
            "pct_dates_positive": (
                float((ic_daily["ic"] > 0).mean()) if len(ic_daily) else None),
        },
        "sanity_battery": {**verdict,
                           "placebo_shift_diagnostics": placebo["diagnostics"]},
        "crosscheck_vs_training_val_preds": crosscheck,
        "outputs": {
            "oos_ic_daily_csv": str(out_dir / "oos_ic_daily.csv"),
            "oos_ic_daily_parquet": str(out_dir / "oos_ic_daily.parquet"),
            "predictions_parquet": str(out_dir / "predictions.parquet"),
        },
        # Content hash of the predictions artifact (NOT just its path), so a
        # downstream consumer can prove the parquet it loads is byte-identical
        # to the one this placebo-clean export produced. Without it, a
        # same-path replacement of predictions.parquet would silently pass a
        # path-only validator (renquant-pipeline validate_clean_oos_manifest).
        "output_hashes": {
            "predictions_parquet_sha256": sha256_file(out_dir / "predictions.parquet"),
            "oos_ic_daily_parquet_sha256": sha256_file(out_dir / "oos_ic_daily.parquet"),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    log.info("manifest written: %s", out_dir / "manifest.json")
    log.info("VERDICT: %s", verdict["reason"])
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
