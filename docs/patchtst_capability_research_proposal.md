# PatchTST Capability Research Proposal

## Purpose

This document proposes the next research cycle for improving the PatchTST
sequence model used by RenQuant. The goal is not to add one more experiment
knob. The goal is to make PatchTST, or a better sequence/panel model, pass a
strict scientific process: explicit hypotheses, leak-safe data, reproducible
trial matrices, placebo gates, robust cross-cut analysis, and clear promotion
criteria.

## Current State

The current dataset is `data/transformer_v4_wl200_clean.parquet`: 346,022 rows,
142 tickers, 2,541 trading dates from 2016-01-04 through 2026-02-10, and labels
`fwd_5d_excess`, `fwd_20d_excess`, and `fwd_60d_excess`.

Recent mainline fixes matter for this proposal:

- PR #9 fixed the time-shift placebo cross-split label leak.
- PR #10 fixed raw regime string use inside the research pipeline.
- `ExperimentPipeline` now records trial matrix, placebos, aggregation, analysis,
  and verdict artifacts.

The local training ledger gives a useful but incomplete signal. On `cut1_covid`,
`cross_stock_attn=True` averaged about +0.146 pooled IC versus about +0.048 for
the tuned baseline. That is promising, but it is not yet a model result:
`cut2_fed` tuned baseline is still unstable/negative, and all-cut runs remain
noisy. The next cycle should confirm whether cross-stock attention generalizes
across all cuts and placebos before adding larger data or new architectures.

## Research Read

PatchTST is a strong starting point because patching reduces attention cost and
keeps local temporal semantics. Its main design is also the main RenQuant risk:
channel independence means each variable is modeled as a univariate sequence
with shared weights. That is efficient, but a cross-sectional stock ranker needs
stock-to-stock, sector-to-market, and market-to-stock interactions.

The strongest literature fit for RenQuant is therefore cross-variate and
cross-stock modeling:

- iTransformer embeds individual series as variate tokens and uses attention to
  capture multivariate correlations.
- Crossformer explicitly models cross-time and cross-dimension dependency.
- StockMixer is finance-specific and mixes indicator, time, and stock dimensions
  with explicit stock-to-market and market-to-stock influence. It is also likely
  cheaper to train than another Transformer.
- MASTER is finance-specific and alternates intra-stock and inter-stock
  aggregation with market-guided feature selection.
- TSMixer supports the same direction with efficient time and feature MLP mixing.

Foundation models such as TimesFM, Chronos, and Moirai are interesting, but they
are not first-priority production candidates for RenQuant. Their native task is
mostly forecasting future time-series values, while RenQuant needs
point-in-time, exogenous-feature, cross-sectional excess-return ranking. They
are better evaluated as frozen feature generators or sanity baselines.

## P0: Debug And Measurement Fixes

Before expanding experiments, fix the remaining measurement risks.

1. Align training selection with research judgement. The trainer still selects
   the best epoch on `eval_min_regime_ic`, while the research report judges
   configs on pooled per-date Spearman IC. Sparse regime days can make
   `min_regime_ic` too noisy for checkpoint selection. Add a controlled
   selection ablation: `min_regime_ic`, `pooled_ic`, and a robust composite
   such as `pooled_ic - lambda * negative_non_defensive_regime_penalty`.

2. Remove implicit umbrella path assumptions from the trainer. `research.py`
   accepts explicit `--dataset`, `--spy-path`, and `--strategy-config`, but
   `hf_trainer.py` still has fallback logic around `RENQUANT_STRATEGY_DIR` and
   default strategy paths. The model repo should require explicit paths or read
   installed contract packages. It should not infer a checkout layout.

3. Improve ledger structure. Current `training_runs` stores important fields
   such as cut, seed, cross-stock, and FiLM mainly in `notes`; some `commit_sha`
   values are null. Persist these as structured metadata so cross-repo dashboards
   do not have to parse strings.

4. Add label-lineage audits. For each trial, persist label column, lookahead,
   label-shift policy, split source row checks, winsor bounds fitted on train
   only, and row counts after placebo mutation.

## P1: PatchTST Capability Improvements

The first model-improvement wave should stay close to the existing PatchTST
codepath so results are attributable.

- Confirm `C_xstock`: run all five cuts and at least two seeds after the placebo
  fix. Tune only if it beats `B_tuned` by at least one standard error and has no
  negative non-defensive regime evidence.
- Add a market/factor token variant: aggregate same-day market, sector, and
  style context into explicit tokens before the rank head. This is the smallest
  MASTER/StockMixer-style addition to current PatchTST.
- Re-test FiLM only after the regime detector contract passes. FiLM should help
  only if regime labels are stable enough to condition on.
- Add multi-horizon heads for `fwd_5d_excess`, `fwd_20d_excess`, and
  `fwd_60d_excess`. Keep a single primary selection label, but use auxiliary
  heads to improve temporal representation.
- Add masked-patch pretraining on the same point-in-time panel, then fine-tune
  on ranking. PatchTST literature explicitly reports self-supervised transfer
  benefits, and RenQuant has more unlabeled temporal structure than clean labels.

## P2: Data Expansion

Increasing data can help, but only if the data contract is stricter than the
model ambition.

- Expand the universe through `renquant-base-data` with point-in-time membership
  snapshots, not current constituents backfilled into history.
- Extend history before 2016 only for features that are point-in-time and
  consistently available. More dates are valuable mainly because they add more
  bear, inflation, unwind, and low-volatility regimes.
- Add features through gated ablations, not bulk ingestion. Candidate groups:
  sector-relative returns, macro/ETF state, options IV, fundamental revisions,
  and cleaned sentiment. Current evidence says raw sentiment can dilute signal,
  so sentiment should be transformed or excluded by default.
- Persist dataset fingerprints and feature group manifests for every run.

## P3: New Model Experiments

Recommended candidates:

1. `StockMixerLite`: highest priority alternative. It matches the RenQuant panel
   shape directly, should be faster than attention-heavy models, and tests
   whether indicator/time/stock mixing beats PatchTST.
2. `MASTERLite`: market-guided Transformer with explicit intra-stock and
   inter-stock aggregation. This is closest to the domain problem but more
   complex than StockMixer.
3. `TSMixer` or `DLinear`: cheap baselines. If these match PatchTST, the neural
   sequence stack is overcomplicated.
4. `iTransformer` or `Crossformer`: second-wave Transformer variants if
   cross-stock attention consistently wins.
5. `TimesFM`, `Chronos`, `Moirai`: frozen feature or benchmark only, unless a
   later experiment proves they can handle RenQuant's exogenous cross-sectional
   ranking target.

## Implementation Reference Policy

Implementation should use mature libraries or official open-source projects
wherever they fit the RenQuant contract. Write custom code only for the
RenQuant-specific parts: point-in-time panel loading, cross-sectional rank loss,
walk-forward splits, placebos, artifact contracts, and model adapters.

Reference priority:

1. Packaged, maintained libraries already compatible with PyTorch/HF workflows.
   Current examples: Hugging Face `transformers.PatchTSTModel` and
   `PatchTSMixerModel`.
2. Official paper repositories with compatible license and clear reproduction
   scripts. Pin a commit, record the license, and port only the minimal model
   block needed for RenQuant if the repo is not package-quality.
3. Widely used benchmark libraries such as THUML Time-Series-Library or
   NeuralForecast for sanity checks and baseline parity.
4. From-scratch implementation only when no reference exists or the reference
   cannot support RenQuant's ranking/panel contract.

Reference shortlist:

| Model | Preferred source | Use in RenQuant |
|---|---|---|
| PatchTST | Hugging Face `transformers` | Keep using packaged backbone. |
| PatchTSMixer / TSMixer | Hugging Face `transformers`, NeuralForecast | First MLP-mixer baseline before custom StockMixer. |
| StockMixer | Official SJTU-DMTai repo | Port architecture if license/deps pass review. |
| MASTER | Official SJTU-DMTai repo | Reference for market-guided stock/market tokens. |
| iTransformer | Official THUML repo or Time-Series-Library | Reference if cross-stock attention wins. |
| Crossformer | Official Thinklab-SJTU repo | Second-wave cross-dimension Transformer. |
| DLinear | Official LTSF-Linear/DLinear repo | Cheap sanity baseline. |
| TimesFM | Google Research repo | Frozen feature or benchmark only. |
| Chronos | Amazon Science repo | Frozen feature or benchmark only. |
| Moirai | Salesforce `uni2ts` repo | Frozen feature or benchmark only. |

Every implementation PR should include a source note with paper URL, repo URL,
license, pinned commit/version, deviations from the reference, and adapter tests
showing expected tensor shapes and deterministic smoke behavior.

## Proposed Experiment Matrix

All experiments should run through `renquant_model_patchtst.research` and
`ExperimentPipeline`. Use `renquant_common.run_parallel` only for independent
cut/seed jobs when the scheduler chooses parallel execution. On MPS, keep one
training job at a time; on CPU or multi-GPU, cap per-worker threads and persist
the execution plan.

Phase A, corrected baseline:

```bash
python -m renquant_model_patchtst.research \
  --phase range_find \
  --configs B_tuned,C_xstock,D_film,E_drop_senti,F_fwd20d \
  --cuts cut1_covid,cut2_fed,cut3_inflpk,cut4_svb,cut5_unwind \
  --seeds 42,43 \
  --epochs 4 \
  --device mps
```

Phase B, selection metric ablation: add trainer support for
`--selection-metric min_regime_ic|pooled_ic|robust_composite`, then repeat the
winner from Phase A.

Phase C, data expansion: rerun the Phase B winner on larger point-in-time
universes and longer history, changing only one data dimension per run.

Phase D, candidate models: compare `StockMixerLite`, `MASTERLite`, and one cheap
baseline against the confirmed PatchTST winner on the same cuts, seeds, and
placebos.

Phase E, confirmation:

```bash
python -m renquant_model_patchtst.research \
  --phase confirm \
  --configs <winner> \
  --seeds 42,43,44,45,46 \
  --epochs 8 \
  --device mps
```

## Promotion Criteria

A candidate can move beyond research only if it satisfies all of these:

- Mean pooled IC beats the current XGB baseline and `B_tuned` PatchTST baseline.
- Shuffle-label and time-shift placebo ICs are near zero and below gate
  thresholds.
- No negative non-defensive regime evidence.
- Worst cut IC is positive.
- DSR is above threshold and PBO is acceptable.
- All artifacts include matrix hash, git head, dataset fingerprint, config
  fingerprint, scheduler plan, and complete trial results.

## Recommended Order

1. Implement P0 measurement fixes.
2. Rerun Phase A with the corrected pipeline.
3. If `C_xstock` survives, tune cross-stock plus market/factor token variants.
4. Implement `StockMixerLite` as the first non-PatchTST candidate.
5. Expand data only after a stable model and metric surface exists.

## References

- PatchTST, "A Time Series is Worth 64 Words": https://arxiv.org/abs/2211.14730
- Hugging Face PatchTST docs: https://huggingface.co/docs/transformers/model_doc/patchtst
- Hugging Face PatchTSMixer docs: https://huggingface.co/docs/transformers/main/model_doc/patchtsmixer
- iTransformer, ICLR 2024: https://openreview.net/forum?id=JePfAI8fah
- iTransformer official repo: https://github.com/thuml/iTransformer
- Crossformer, ICLR 2023: https://openreview.net/forum?id=vSVLM2j9eie
- Crossformer official repo: https://github.com/Thinklab-SJTU/Crossformer
- StockMixer, AAAI 2024: https://mlanthology.org/aaai/2024/fan2024aaai-stockmixer/
- StockMixer official repo: https://github.com/SJTU-DMTai/StockMixer
- MASTER: https://arxiv.org/abs/2312.15235
- MASTER official repo: https://github.com/SJTU-DMTai/MASTER
- TSMixer: https://research.google/pubs/tsmixer-an-all-mlp-architecture-for-time-series-forecasting/
- NeuralForecast TSMixer docs: https://nixtlaverse.nixtla.io/neuralforecast/models.tsmixer.html
- DLinear/LTSF-Linear: https://arxiv.org/abs/2205.13504
- Time-Series-Library: https://github.com/thuml/Time-Series-Library
- TS2Vec: https://ojs.aaai.org/index.php/AAAI/article/view/20881
- TimesFM: https://research.google/blog/a-decoder-only-foundation-model-for-time-series-forecasting/
- TimesFM official repo: https://github.com/google-research/timesfm
- Chronos: https://www.amazon.science/blog/adapting-language-model-architectures-for-time-series-forecasting/
- Chronos official repo: https://github.com/amazon-science/chronos-forecasting
- Moirai: https://arxiv.org/abs/2402.02592
- Moirai official repo: https://github.com/SalesforceAIResearch/uni2ts
