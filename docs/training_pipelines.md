# Training pipelines — full parameter reference + step-by-step

This is the canonical reference for both model families in this repo. It documents
**every hyperparameter**, **every Job/Task step**, and **where each value ends up**
(artifact sidecar, `data/sim_runs.db::training_runs`, or just runtime). Keep it in
sync when a parameter is added (the model-side training pipeline is the source of
truth — code wins, this doc gets updated).

The two families share the same Task/Job/Pipeline architecture from
`renquant_common.pipeline` but live in separate packages so they can evolve their
hyperparameters and training mechanics independently.

---

## 1. GBDT (panel-LTR) — `renquant_model_gbdt`

### Pipeline shape (`panel-gbdt-training`)

```
build_training_pipeline()
  └─ DataPrepJob          : LoadPanelTask -> BuildNormalizationTask
  └─ ModelTrainingJob     : WalkForwardCVTask -> TrainBoosterTask -> BuildArtifactTask
  └─ ArtifactContractJob  : StampFingerprintTask -> AttachSmokeTask -> WriteArtifactTask
```

Driven by `renquant-orchestrator/train_gbdt.py` with optional middle insertion of
`SentimentGateTask` between `LoadPanelTask` and `BuildNormalizationTask` so the
runtime sentiment-gate behaviour is reproduced during training.

### Step-by-step

| Step | What it does | Reads from ctx | Writes to ctx |
|---|---|---|---|
| `LoadPanelTask` | reads the daily panel parquet, applies watchlist filter, drops `exclude_features` | `data_dir`, `watchlist`, `exclude_features`, `train_cutoff` | `panel`, `feat_cols` |
| `(SentimentGateTask)` | zeros sentiment features in regimes the runtime gates them in (optional, only when `--skip-sentiment-gate` is OFF) | `panel`, `feat_cols`, `sentiment_runtime_gate_contract` | `panel` (in-place) |
| `BuildNormalizationTask` | fits per-feature normalisation: chooses `global_z` / `robust_z` / `identity` per column heuristic, stores means+stds for runtime use | `panel`, `feat_cols` | `feature_means`, `feature_stds`, `feature_norm_kind` |
| `WalkForwardCVTask` | purged-walk-forward CV with `cv_embargo_days` between train and val to prevent label leakage; returns per-fold IC | `panel`, `feat_cols`, `cv_n_splits`, `cv_embargo_days`, `label_col` | `oos_per_fold_ic`, `oos_mean_ic`, `oos_std_ic`, `cv_method` |
| `TrainBoosterTask` | trains the XGBoost booster on the FULL labelled history | `panel`, `feat_cols`, `params`, `num_boost_round`, `label_col` | `booster`, `best_iter`, `train_ic` |
| `BuildArtifactTask` | assembles the panel-LTR artifact dict (schema v3) | everything above | `artifact` |
| `StampFingerprintTask` | stamps `config_fingerprint` (sha256 over watchlist + sector_map + panel-LTR settings from the strategy config), `config_fingerprint_fields`, `recipe_fingerprint` | `artifact`, `config_fingerprint_fields` | `artifact["config_fingerprint"]` |
| `AttachSmokeTask` | attaches a content-hash smoke test of the booster bytes so silent corruption is detected at load | `artifact` | `artifact["smoke_test_*"]` |
| `WriteArtifactTask` | writes the artifact JSON to `output_path` (must contain `walkforward` if `train_cutoff` is set — §5.13.13 side-config guard) | `artifact`, `output_path` | (filesystem) |

After the Pipeline returns, the **driver** (`train_gbdt.py`) writes one row to
`data/sim_runs.db::training_runs` and refreshes the README's
`<!-- LATEST_MODELS:START/END -->` block via
`scripts/refresh_readme_latest_models.py`.

### All hyperparameters

| Name | Default | Where it lives | Meaning |
|---|---|---|---|
| `objective` | `rank:pairwise` | `panel_trainer.PANEL_LTR_PARAMS` | XGBoost objective — pairwise ranking loss on per-day groups |
| `eta` | `0.05` | `PANEL_LTR_PARAMS` | learning rate |
| `max_depth` | `5` | `PANEL_LTR_PARAMS` | tree depth |
| `min_child_weight` | `50` | `PANEL_LTR_PARAMS` | min sum of instance weight per leaf — regularises against thin leaves |
| `subsample` | `0.7` | `PANEL_LTR_PARAMS` | per-tree row subsample |
| `colsample_bytree` | `0.7` | `PANEL_LTR_PARAMS` | per-tree column subsample |
| `tree_method` | `hist` (set by XGB) | `PANEL_LTR_PARAMS` | histogram-based exact splits |
| `nthread` | `8` | `PANEL_LTR_PARAMS` | threadpool (execution-only — stripped from recipe fingerprint) |
| `seed` | `42` | `train_xgb()` | RNG seed |
| `num_boost_round` | `DEFAULT_N_ROUNDS` (300) | `train_gbdt.py --num-boost-round` | total boosting iterations |
| `cv_method` | `purged_walk_forward` | hard-coded | CV scheme name stamped on artifact |
| `cv_embargo_days` | `60` | `train_gbdt.py --cv-embargo-days` | days between train end and val start — must be ≥ `lookahead_days` |
| `cv_n_splits` | `3` | `train_gbdt.py --cv-n-splits` | number of purged folds |
| `skip_cv` | `False` | `train_gbdt.py --skip-cv` | skip CV (use for manifest-builder, not for promotion candidates) |
| `label_col` | `fwd_60d_excess` | `train_gbdt.py --label` | forward-return label column (cross-sectionally demeaned) |
| `lookahead_days` | `60` | derived from `label_col` | label horizon — must be ≤ `cv_embargo_days` |
| `exclude_features` | `[]` | `train_gbdt.py --exclude-features` | feature names to drop before training (e.g. `mean_sentiment,n_articles_log,sentiment_pos_share` via `--drop-sentiment`) |
| `feature_norm_kind` | auto (per column) | `BuildNormalizationTask` heuristic | `global_z` (default) / `robust_z` (heavy tails) / `identity` (already normalised features) |
| `train_cutoff` | `None` | `train_gbdt.py --train-cutoff` | when set, training is restricted to data ≤ cutoff (for WF manifest builds); requires `--side-label` and a `walkforward` path |
| `side_label` | `None` | `train_gbdt.py --side-label` | side-config label per §5.13.13; required with `--train-cutoff` |

### Outputs

- **Artifact JSON** (`output_path`): schema v3, includes `kind`, `params`, `feature_cols`, `feature_means`, `feature_stds`, `feature_norm_kind`, `feature_source_contract`, `cv_method`, `cv_embargo_days`, `oos_mean_ic`, `oos_std_ic`, `oos_per_fold_ic`, `train_run_id`, `config_fingerprint`, `trained_date`, `effective_train_cutoff_date`, `booster_raw_json`.
- **DB row**: `training_runs` gets `run_id`, `artifact_type=panel_ltr_xgboost`, `oos_mean_ic`, `n_features`, `device`, `elapsed_sec`, `trigger`, etc.
- **README refresh**: top 8 most-recent runs auto-rendered.

---

## 2. PatchTST (sequence) — `renquant_model_patchtst`

### Pipeline shape (`patchtst-sequence-training`)

```
build_sequence_training_pipeline()
  └─ DataPrepJob         : LoadPanelTask -> ComputeRegimeLabelsTask -> BuildDatasetsTask
  └─ TrainJob            : BuildModelTask -> BuildTrainerTask -> RunTrainingTask
  └─ EvaluateJob         : EvaluateTask -> DumpValPredsTask -> BuildSummaryTask
  └─ PersistModelJob     : PersistModelTask                    (skipped unless --save-model)
  └─ RecordTrainingRunJob: RecordTrainingRunTask
```

Driven by `hf_trainer.main()` (CLI). The `orchestrator/train_patchtst.py` wrapper was removed 2026-05-30 (D7 audit confirmed zero callers — see `doc/arch/duplicates-audit.md` §A1). The research harness `renquant_model_patchtst.research` calls
`train_one(args)` in-process across cuts × seeds × configs.

### Step-by-step

| Step | What it does | Reads from ctx | Writes to ctx |
|---|---|---|---|
| `LoadPanelTask` | seeds RNGs, reads the panel parquet, assigns train/val/test split for the named cut (or `cut=all` with `val_tail_pct`), drops `exclude_features`, optionally **shuffles labels** (§5.2 placebo) | `args.seed`, `args.dataset`, `args.cut`, `args.label`, `args.exclude_features`, `args.shuffle_labels`, `args.embargo_days` | `panel`, `feat_cols` |
| `ComputeRegimeLabelsTask` | loads SPY OHLCV, runs HMM to label each calendar day as `BULL_STRONG/BULL_CALM/BULL_VOLATILE/CHOPPY/BEAR` (used by FiLM and per-regime IC) | `args.spy_path` | `hmm_labels`, `spy_path` |
| `BuildDatasetsTask` | builds `PerDayDataset` train+val: each "sample" is one day's batch of N tickers' `seq_len` × `n_features` history; ticker order preserved alphabetically; regime context broadcast when FiLM is on | `panel`, `feat_cols`, `args.label`, `args.seq_len`, `args.film_regime_cond`, `hmm_labels` | `train_ds`, `val_ds` |
| `BuildModelTask` | constructs the `PatchTSTConfig` and `HFPatchTSTRanker` model; logs param count | `feat_cols`, `args.seq_len`, `args.patch_length`, `args.d_model`, `args.n_heads`, `args.n_layers`, `args.distributional_head`, `args.film_regime_cond`, `args.cross_stock_attn` | `cfg`, `model`, `n_params` |
| `BuildTrainerTask` | wires per-regime IC callback (selection metric), early-stopping callback, `TrainingArguments` (lr, weight_decay, lr_scheduler, warmup, batch=1 by day, `load_best_model_at_end`), and the `PatchTSTRankerTrainer` | `args.lr`, `args.weight_decay`, `args.lr_scheduler`, `args.warmup_ratio`, `args.early_stopping_patience`, `args.epochs`, `args.device`, `args.nll_loss_weight`, `args.ranking_margin` | `trainer`, `metric_for_best`, `out_dir`, `total_steps`, `warmup_steps` |
| `RunTrainingTask` | `trainer.train()` — the actual HF training loop (early-stops on `eval_min_regime_ic`) | `trainer` | (model trained in-place) |
| `EvaluateTask` | final eval on val with best-model loaded; builds `training_contract` + `config_contract` (config_fingerprint, watchlist hash) | `trainer`, `feat_cols`, `panel`, `n_params`, `total_steps`, `warmup_steps`, `metric_for_best` | `final_metrics`, `best_val_ic`, `training_contract`, `config_contract` |
| `DumpValPredsTask` | runs `model.eval()` over val days, writes `hf_patchtst_<cut>_seed<seed>_val_preds.parquet` with `date, ticker, pred, label, mu, sigma` | `model`, `val_ds`, `out_dir` | (filesystem) |
| `BuildSummaryTask` | assembles `summary.json` with `arch, kind, cut, seed, best_val_ic, n_params, feature_cols, label_col, lookahead_days, params, config_fingerprint, trained_watchlist_n, training_contract, per_regime_ic` | everything above | `summary` (written to `out_dir`) |
| `PersistModelTask` (optional) | saves `.pt` checkpoint with state_dict + config + flags + training_contract, plus a `*.metadata.json` sidecar mirroring `summary` + `artifact_path, artifact_sha256, artifact_fingerprint` | `model`, `cfg`, `summary` | (filesystem) |
| `RecordTrainingRunTask` | writes a row to `data/sim_runs.db::training_runs` and runs `scripts/refresh_readme_latest_models.py` | `args`, `summary`, `best_val_ic`, `out_dir` | (DB + README) |

### All hyperparameters

| Name | Default | CLI flag | Meaning |
|---|---|---|---|
| `cut` | required | `--cut` | walk-forward cut name (`cut1_covid` … `cut5_unwind`) or `all` for full-data training |
| `seed` | `42` | `--seed` | RNG seed |
| `device` | `cpu` | `--device {cpu,mps,cuda}` | training device |
| `epochs` | `5` | `--epochs` | max training epochs; usually early-stopped at 5–6 |
| `early_stopping_patience` | `2` | `--early-stopping-patience` | stop if `eval_min_regime_ic` doesn't improve for N epochs (0 disables) |
| `lr` | `3e-4` (DOE-tuned: `1e-4`) | `--lr` | initial learning rate |
| `weight_decay` | `1e-3` (DOE-tuned: `0.3`) | `--weight-decay` | L2 — key regularizer; `0.3` is the proven DOE optimum |
| `lr_scheduler` | `cosine` | `--lr-scheduler` | HF Trainer scheduler type |
| `warmup_ratio` | `0.1` | `--warmup-ratio` | fraction of total steps used for LR warmup |
| `seq_len` | `32` (DOE-tuned: `24`) | `--seq-len` | per-ticker lookback window in trading days |
| `patch_length` | `4` | `--patch-length` | PatchTST patching length (non-overlapping by default) |
| `d_model` | `64` | `--d-model` | transformer hidden dimension |
| `n_heads` | `4` | `--n-heads` | multi-head attention heads |
| `n_layers` | `2` | `--n-layers` | encoder layers |
| `nll_loss_weight` | `0.5` | `--nll-loss-weight` | λ for `L = margin_rank + λ·student_t_nll` (distributional head only) |
| `ranking_margin` | `0.1` | `--ranking-margin` | margin in `torch.nn.functional.margin_ranking_loss` |
| `distributional_head` | `True` | `--distributional-head` / `--no-distributional-head` | predict `mu, sigma` (for σ-aware Kelly) in addition to score |
| `film_regime_cond` | `False` | `--film-regime-cond` | FiLM regime conditioning (Perez 2017); identity at init |
| `cross_stock_attn` | `False` | `--cross-stock-attn` | iTransformer-style cross-stock attention (Liu 2024); identity at init |
| `spy_path` | `data/ohlcv/SPY/1d.parquet` | `--spy-path` | OHLCV parquet for HMM regime labels |
| `label` | `fwd_60d_excess` | `--label` | forward-return label column |
| `exclude_features` | `None` | `--exclude-features` | comma list of feature cols to drop (e.g. the 3 sentiment feats for `E_drop_senti`) |
| `shuffle_labels` | `False` | `--shuffle-labels` | §5.2 placebo: globally permute labels — clean run must score IC ≈ 0 |
| `save_model` | `False` | `--save-model` | persist `.pt` checkpoint + metadata sidecar |
| `output_dir` | `artifacts/hf_patchtst` | `--output-dir` | where to write summary / val_preds / model |
| `strategy_config` | `None` | `--strategy-config` | strategy config JSON for `config_fingerprint` stamping (defaults to `renquant_104/strategy_config.shadow.json`) |
| `val_tail_pct` | `0.10` | (no CLI) | when `cut=all`, last 10% of dates → val, with `embargo_days` between |
| `embargo_days` | `60` | (no CLI) | val embargo when `cut=all` |

### DOE-tuned baseline (`B_tuned` in research harness)

`--lr 1e-4 --weight-decay 0.3 --seq-len 24 --early-stopping-patience 2` — these
values come from a Box-Behnken DOE; treat them as the baseline to beat when
exploring new levers.

### Outputs

- **`.pt` checkpoint**: torch save dict with `state_dict`, `config_dict`, all `uses_*` flags, `training_contract`, `per_regime_ic`.
- **`*.metadata.json` sidecar**: human-readable manifest containing `kind=hf_patchtst`, `config_fingerprint`, `trained_watchlist_n`, `best_val_ic`, `per_regime_ic`, `artifact_path`, `artifact_sha256`. This is what `run_wf_gate.py` / preflight `_load_artifact_payload` reads.
- **val_preds parquet**: per-day val predictions with ticker, used by `renquant_backtesting.forensics.patchtst_alpha` for the dollar-alpha-vs-SPY analysis.
- **DB row**: `training_runs` gets `artifact_type=hf_patchtst` plus notes including `cut`, `seed`, `epochs`, `cross_stock`, `film` flags.

---

## 3. Where parameter values end up

For every training run the same parameter ends up in **all four** of these places —
divergence is a bug:

```
            ┌── PT/JSON artifact (training_contract.hyperparameters)
            │
CLI ──> Pipeline ─┼── *.metadata.json sidecar (summary.params)
            │
            ├── data/sim_runs.db::training_runs (notes + config_snapshot)
            │
            └── renquant-model/README.md (Latest models block, auto-refreshed)
```

Keep this doc updated when:
1. A new hyperparameter is added to either family's Pipeline.
2. A default value changes.
3. A new Job/Task is inserted into either pipeline.
4. The DB schema gains a new column relevant to training.

---

## 4. Reference incidents

- DOE-tuned `wd=0.3` is the proven baseline against three default-config catastrophes (`+0.091 / -0.128 / -0.046` per-cut IC). See research plan `docs/patchtst_research_plan.md`.
- `--shuffle-labels` placebo (§5.2 gate) was added 2026-05-28 — runs at +0.003 IC on cut1-5 confirming the real configs' +0.066-0.070 is not selection-optimism.
- `--exclude-features mean_sentiment,n_articles_log,sentiment_pos_share` (E_drop_senti) — the GBDT lesson; PatchTST also benefits.
- `cv_embargo_days=60` matches `lookahead_days=60` and prevents the 2026-05-20 walk-forward leakage class.
