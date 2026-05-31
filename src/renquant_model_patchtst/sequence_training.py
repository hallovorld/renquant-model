"""PatchTST single-run training, decomposed into the Task/Job/Pipeline model.

``hf_trainer.train_one`` was a ~200-line monolith. This module splits that exact
flow into single-responsibility Tasks grouped into four Jobs:

    DataPrepJob   : LoadPanel → ComputeRegimeLabels → BuildDatasets
    TrainJob      : BuildModel → BuildTrainer → RunTraining
    EvaluateJob   : Evaluate → DumpValPreds → BuildSummary
    PersistModelJob (skipped unless --save-model) : PersistModel

Behaviour is identical to the former ``train_one``; the heavy lifting (model,
trainer, datasets, contracts) still lives in ``hf_trainer`` and is referenced
through ``hf.*`` so default hyperparameters stay single-sourced. ``train_one``
now just builds a context and runs ``build_sequence_training_pipeline()``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from renquant_common import Job, Pipeline, Task, record_training_run

from . import hf_trainer as hf


@dataclass
class SequenceTrainingContext:
    """Mutable state threaded through the sequence-training Pipeline."""

    args: argparse.Namespace
    panel: Any = None
    feat_cols: list[str] | None = None
    hmm_labels: Any = None
    spy_path: Any = None
    train_ds: Any = None
    val_ds: Any = None
    cfg: Any = None
    model: Any = None
    n_params: int | None = None
    out_dir: Any = None
    total_steps: int | None = None
    warmup_steps: int | None = None
    metric_for_best: str | None = None
    trainer: Any = None
    final_metrics: dict | None = None
    best_val_ic: float | None = None
    training_contract: dict | None = None
    config_contract: dict | None = None
    summary: dict | None = None


# ─── DataPrepJob ─────────────────────────────────────────────────────────────

class LoadPanelTask(Task):
    """Seed RNGs + load the panel with its walk-forward split and feature cols."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        torch.manual_seed(a.seed)
        np.random.seed(a.seed)
        ctx.panel, ctx.feat_cols = hf.load_panel_with_split(
            Path(a.dataset), a.cut, a.label,
            val_tail_pct=getattr(a, "val_tail_pct", 0.10),
            embargo_days=getattr(a, "embargo_days", 60),
            train_cutoff=getattr(a, "train_cutoff", None),
            data_end=getattr(a, "data_end", None),
            exclude_features=([s.strip() for s in a.exclude_features.split(",") if s.strip()]
                              if getattr(a, "exclude_features", None) else None),
            shuffle_labels=getattr(a, "shuffle_labels", False),
            label_shift_days=getattr(a, "label_shift_days", 0))
        return True


class ComputeRegimeLabelsTask(Task):
    """Compute HMM regime labels once (reused by FiLM injection + per-regime IC)."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        ctx.spy_path = hf.REPO / a.spy_path
        if ctx.spy_path.exists():
            from renquant_common.hmm_regime_labels import compute_hmm_regime_labels  # noqa: PLC0415
            ctx.hmm_labels = compute_hmm_regime_labels(ctx.spy_path)
        elif a.film_regime_cond:
            raise FileNotFoundError(
                f"FiLM regime conditioning requires SPY parquet at {ctx.spy_path}")
        return True


class BuildDatasetsTask(Task):
    """Build per-day train/val datasets (regime context injected only when FiLM ON)."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        ds_hmm = ctx.hmm_labels if a.film_regime_cond else None
        ctx.train_ds = hf.PerDayDataset(ctx.panel, ctx.feat_cols, a.label, a.seq_len,
                                        "train", hmm_labels=ds_hmm)
        ctx.val_ds = hf.PerDayDataset(ctx.panel, ctx.feat_cols, a.label, a.seq_len,
                                      "val", hmm_labels=ds_hmm)
        hf.log.info("days train=%d val=%d", len(ctx.train_ds), len(ctx.val_ds))
        return True


# ─── TrainJob ────────────────────────────────────────────────────────────────

class BuildModelTask(Task):
    """Construct the PatchTST config + ranker model."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        ctx.cfg = hf.PatchTSTConfig(
            num_input_channels=len(ctx.feat_cols),
            context_length=a.seq_len,
            patch_length=a.patch_length,
            patch_stride=a.patch_length,  # non-overlapping
            d_model=a.d_model,
            num_attention_heads=a.n_heads,
            num_hidden_layers=a.n_layers,
            ffn_dim=a.d_model * 2,
        )
        ctx.model = hf.HFPatchTSTRanker(ctx.cfg, use_distributional_head=a.distributional_head,
                                        use_film_regime=a.film_regime_cond,
                                        use_cross_stock_attn=a.cross_stock_attn)
        ctx.n_params = sum(p.numel() for p in ctx.model.parameters())
        hf.log.info("HFPatchTSTRanker n_params=%.2fM dist_head=%s film=%s cross_stock=%s",
                    ctx.n_params / 1e6, a.distributional_head, a.film_regime_cond,
                    a.cross_stock_attn)
        return True


class BuildTrainerTask(Task):
    """Wire callbacks + selection metric + TrainingArguments + the Trainer."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        callbacks: list = []
        metric_for_best = None
        greater_is_better = True
        if ctx.hmm_labels is not None:
            callbacks.append(hf.PerRegimeICCallback(ctx.val_ds, ctx.hmm_labels))
            metric_for_best = "eval_min_regime_ic"
            hf.log.info("PerRegimeICCallback wired | n_labels=%d", len(ctx.hmm_labels))
            if a.early_stopping_patience > 0:
                callbacks.append(hf.EarlyStoppingCallback(
                    early_stopping_patience=a.early_stopping_patience,
                    early_stopping_threshold=0.0001,
                ))
                hf.log.info("EarlyStoppingCallback wired (patience=%d)",
                            a.early_stopping_patience)
        else:
            hf.log.warning("SPY parquet missing at %s — falling back to eval_loss "
                           "for best-model selection (PRIME DIRECTIVE degraded)", ctx.spy_path)
            metric_for_best = "eval_loss"
            greater_is_better = False
        ctx.metric_for_best = metric_for_best
        ctx.out_dir = Path(a.output_dir)
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        ctx.total_steps = a.epochs * max(1, len(ctx.train_ds))
        ctx.warmup_steps = int(a.warmup_ratio * ctx.total_steps)
        training_args = hf.TrainingArguments(
            output_dir=str(ctx.out_dir / "_hf_trainer"),
            num_train_epochs=a.epochs,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            learning_rate=a.lr,
            weight_decay=a.weight_decay,
            lr_scheduler_type=a.lr_scheduler,
            warmup_steps=ctx.warmup_steps,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model=metric_for_best,
            greater_is_better=greater_is_better,
            seed=a.seed,
            report_to=[],
            logging_steps=200,
            dataloader_num_workers=0,
            remove_unused_columns=False,
            use_cpu=(a.device == "cpu"),
        )
        ctx.trainer = hf.PatchTSTRankerTrainer(
            model=ctx.model, args=training_args,
            train_dataset=ctx.train_ds, eval_dataset=ctx.val_ds,
            data_collator=hf.identity_collator, callbacks=callbacks,
            nll_loss_weight=a.nll_loss_weight,
            ranking_margin=a.ranking_margin,
        )
        return True


class RunTrainingTask(Task):
    """Run the HF training loop."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        ctx.trainer.train()
        return True


# ─── EvaluateJob ─────────────────────────────────────────────────────────────

class EvaluateTask(Task):
    """Final eval (best model loaded) + build training/config contracts."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        ctx.final_metrics = ctx.trainer.evaluate()
        ctx.best_val_ic = float(ctx.final_metrics.get("eval_min_regime_ic", float("nan")))
        hf.log.info("FINAL eval %s", {k: f"{v:+.4f}" if isinstance(v, float) else v
                                       for k, v in ctx.final_metrics.items()})
        ctx.training_contract = hf.build_training_contract(
            a, ctx.feat_cols, ctx.panel, ctx.n_params, ctx.total_steps, ctx.warmup_steps,
            ctx.metric_for_best, ctx.final_metrics)
        ctx.config_contract = hf.build_config_contract(a)
        ctx.training_contract["config_contract"] = ctx.config_contract
        return True


class DumpValPredsTask(Task):
    """Predict over val days + dump predictions parquet for regime-stratified IC."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        device = next(ctx.model.parameters()).device
        ctx.model.eval()
        rows: list[dict] = []
        with torch.no_grad():
            for day in ctx.val_ds.days:
                x = day["past_values"].to(device)
                fwd_kwargs = {"past_values": x}
                if "regime_context" in day:
                    fwd_kwargs["regime_context"] = day["regime_context"].to(device)
                outputs = ctx.model(**fwd_kwargs)
                tickers = day.get("tickers")
                for i, d in enumerate(day["dates"]):
                    row = {"date": pd.Timestamp(d),
                           "ticker": (str(tickers[i]) if tickers is not None else None),
                           "pred": float(outputs["score"][i].cpu()),
                           "label": float(day["labels"][i])}
                    if "loc" in outputs:
                        row["mu"] = float(outputs["loc"][i].cpu())
                        row["sigma"] = float(outputs["scale"][i].cpu())
                    rows.append(row)
        preds_df = pd.DataFrame(rows)
        dump = ctx.out_dir / f"hf_patchtst_{a.cut}_seed{a.seed}_val_preds.parquet"
        preds_df.to_parquet(dump, index=False)
        hf.log.info("preds dumped: %s (%d rows)", dump.name, len(preds_df))
        return True


class BuildSummaryTask(Task):
    """Assemble the run summary + write summary.json."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        tc, cc = ctx.training_contract, ctx.config_contract
        ctx.summary = {
            "arch": "hf_patchtst", "kind": "hf_patchtst",
            "cut": a.cut, "seed": a.seed,
            "best_val_ic": ctx.best_val_ic, "n_params": ctx.n_params,
            "feature_cols": ctx.feat_cols,
            "label_col": a.label,
            "lookahead_days": tc.get("lookahead_days"),
            "params": tc.get("hyperparameters", {}),
            "n_features": len(ctx.feat_cols), "uses_distributional_head": a.distributional_head,
            "config_fingerprint": cc["config_fingerprint"],
            "config_fingerprint_fields": cc["config_fingerprint_fields"],
            "config_path": cc["config_path"],
            "trained_watchlist_n": cc["trained_watchlist_n"],
            "training_contract": tc,
            "per_regime_ic": {k.removeprefix("eval_ic_"): v
                              for k, v in ctx.final_metrics.items()
                              if k.startswith("eval_ic_")},
        }
        (ctx.out_dir / f"hf_patchtst_{a.cut}_seed{a.seed}_summary.json").write_text(
            json.dumps(ctx.summary, indent=2, default=str))
        return True


# ─── PersistModelJob ─────────────────────────────────────────────────────────

class PersistModelTask(Task):
    """Save the model checkpoint + metadata sidecar (when --save-model)."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        a = ctx.args
        tc, cc = ctx.training_contract, ctx.config_contract
        model_path = ctx.out_dir / f"hf_patchtst_{a.cut}_seed{a.seed}_model.pt"
        torch.save({
            "state_dict": ctx.model.state_dict(),
            "config_dict": ctx.cfg.to_dict(),
            "feature_cols": ctx.feat_cols,
            "seq_len": a.seq_len,
            "label_col": a.label,
            "trained_date": tc.get("trained_date"),
            "effective_train_cutoff_date": tc.get("effective_train_cutoff_date"),
            "lookahead_days": tc.get("lookahead_days"),
            "best_val_ic": ctx.best_val_ic,
            "config_fingerprint": cc["config_fingerprint"],
            "config_fingerprint_fields": cc["config_fingerprint_fields"],
            "config_path": cc["config_path"],
            "trained_watchlist_n": cc["trained_watchlist_n"],
            "uses_distributional_head": a.distributional_head,
            "uses_film_regime": a.film_regime_cond,
            "uses_cross_stock_attn": a.cross_stock_attn,
            "uses_csranknorm_preprocessing": True,
            "uses_winsorize_label_preprocessing": True,
            "training_contract": tc,
            "per_regime_ic": ctx.summary["per_regime_ic"],
        }, model_path)
        model_fp = "sha256:" + hashlib.sha256(model_path.read_bytes()).hexdigest()
        sidecar = dict(ctx.summary)
        sidecar.update({
            "artifact_path": str(model_path),
            "artifact_sha256": model_fp,
            "artifact_fingerprint": model_fp,
        })
        (model_path.with_name(model_path.name + ".metadata.json")).write_text(
            json.dumps(sidecar, indent=2, default=str))
        hf.log.info("model saved: %s", model_path)
        return True


# ─── Jobs + Pipeline ─────────────────────────────────────────────────────────

class DataPrepJob(Job):
    """Load panel + regime labels + build per-day datasets."""

    @property
    def tasks(self) -> list[Task]:
        return [LoadPanelTask(), ComputeRegimeLabelsTask(), BuildDatasetsTask()]


class TrainJob(Job):
    """Build the model + trainer and run the training loop."""

    @property
    def tasks(self) -> list[Task]:
        return [BuildModelTask(), BuildTrainerTask(), RunTrainingTask()]


class EvaluateJob(Job):
    """Final eval, dump val predictions, assemble the summary."""

    @property
    def tasks(self) -> list[Task]:
        return [EvaluateTask(), DumpValPredsTask(), BuildSummaryTask()]


class PersistModelJob(Job):
    """Persist the checkpoint; skipped unless --save-model."""

    def should_skip(self, ctx: SequenceTrainingContext) -> bool:
        return not ctx.args.save_model

    @property
    def tasks(self) -> list[Task]:
        return [PersistModelTask()]


class RecordTrainingRunTask(Task):
    """Write a row to ``data/sim_runs.db::training_runs`` + refresh renquant-model
    README's Latest-Models block. Best-effort (warnings only, never fatal)."""

    def run(self, ctx: SequenceTrainingContext) -> bool | None:
        import os  # noqa: PLC0415
        import sqlite3  # noqa: PLC0415
        import subprocess  # noqa: PLC0415
        import sys  # noqa: PLC0415
        from pathlib import Path as _Path  # noqa: PLC0415
        # Derive DB path from RENQUANT_STRATEGY_DIR when set (preferred over a
        # machine-specific hardcode); env var still wins.
        strat = os.environ.get("RENQUANT_STRATEGY_DIR")
        default_db = (_Path(strat).resolve().parent.parent / "data" / "sim_runs.db"
                      if strat else _Path("data") / "sim_runs.db")
        db = _Path(os.environ.get("RENQUANT_TRAINING_DB", str(default_db)))
        if not db.exists():
            return True
        a = ctx.args
        s = ctx.summary or {}
        repo = _Path(__file__).resolve().parents[3]
        try:
            conn = sqlite3.connect(str(db))
            try:
                feature_cols = list(ctx.feat_cols or s.get("feature_cols") or [])
                n_rows = s.get("n_rows")
                if n_rows is None and ctx.panel is not None:
                    try:
                        n_rows = int(len(ctx.panel))
                    except TypeError:
                        n_rows = None
                n_dates = s.get("n_dates")
                if n_dates is None and ctx.panel is not None and hasattr(ctx.panel, "columns"):
                    try:
                        if "date" in ctx.panel.columns:
                            n_dates = int(ctx.panel["date"].nunique())
                    except Exception:  # noqa: BLE001
                        n_dates = None
                train_ic = s.get("train_ic")
                if train_ic is None:
                    train_ic = (ctx.final_metrics or {}).get("train_ic")
                record_training_run(
                    conn,
                    strategy=os.environ.get("RENQUANT_STRATEGY_NAME", "renquant_104"),
                    artifact_type="hf_patchtst",
                    config_snapshot=ctx.config_contract or {},
                    oos_mean_ic=ctx.best_val_ic,
                    train_ic=train_ic,
                    n_rows=n_rows,
                    feature_cols=feature_cols or None,
                    artifact_path=str(ctx.out_dir) if ctx.out_dir else None,
                    elapsed_sec=None,
                    trigger=os.environ.get("RENQUANT_TRAIN_TRIGGER", "manual"),
                    n_tickers=s.get("trained_watchlist_n"),
                    n_dates=n_dates,
                    n_features=s.get("n_features", len(feature_cols)),
                    device=getattr(a, "device", "n/a"),
                    deterministic=False,
                    training_window_years=getattr(a, "training_window_years", None),
                    notes=(f"cut={a.cut} seed={a.seed} epochs={a.epochs} "
                           f"cross_stock={getattr(a,'cross_stock_attn',False)} "
                           f"film={getattr(a,'film_regime_cond',False)}"),
                    also_log_jsonl=False,
                    repo_dir=repo,
                )
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            hf.log.warning("record_training_run skipped: %s", exc)
        # Refresh README
        readme_refresh = repo / "scripts" / "refresh_readme_latest_models.py"
        readme = repo / "README.md"
        if readme_refresh.exists() and readme.exists():
            try:
                subprocess.run(
                    [sys.executable, str(readme_refresh),
                     "--db", str(db), "--readme", str(readme)],
                    check=False, timeout=30,
                )
            except Exception as exc:  # noqa: BLE001
                hf.log.warning("README refresh skipped: %s", exc)
        return True


class RecordTrainingRunJob(Job):
    """Persist training_runs DB row + auto-refresh README; non-fatal."""

    @property
    def tasks(self) -> list[Task]:
        return [RecordTrainingRunTask()]


def build_sequence_training_pipeline() -> Pipeline:
    """The full single-run PatchTST training Pipeline (data → model → eval → persist → record)."""
    return Pipeline(
        [DataPrepJob(), TrainJob(), EvaluateJob(), PersistModelJob(),
         RecordTrainingRunJob()],
        name="patchtst-sequence-training",
    )


def run_sequence_training(args: argparse.Namespace) -> dict:
    """Build a context, run the pipeline, return the run summary."""
    ctx = SequenceTrainingContext(args=args)
    build_sequence_training_pipeline().run(ctx)
    return ctx.summary
