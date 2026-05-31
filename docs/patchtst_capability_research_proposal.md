# PatchTST Capability Research Proposal

## Purpose

This document proposes the next research cycle for improving the PatchTST
sequence model used by RenQuant. The goal is to find a validated ranking model,
not to add knobs. Every proposal below must pass a strict process: explicit
hypothesis, point-in-time data, leak-safe splits, placebo gates, per-regime
analysis, reproducible artifacts, and kill criteria before expensive compute.

## Current State

The current dataset is `data/transformer_v4_wl200_clean.parquet`: 346,022 rows,
142 tickers, 2,541 trading dates from 2016-01-04 through 2026-02-10, and labels
`fwd_5d_excess`, `fwd_20d_excess`, and `fwd_60d_excess`.

Recent mainline fixes changed the evidence surface:

- PR #9 fixed the time-shift placebo cross-split label leak.
- PR #10 fixed raw regime string use inside the research pipeline.
- `ExperimentPipeline` records trial matrix, placebos, aggregation, analysis,
  and verdict artifacts.

All PatchTST IC numbers measured before PR #9 are presumed suspect until
revalidated with the corrected placebo gate. The historical Phase 2 artifacts
`../RenQuant/artifacts/patchtst_phase2/B_tuned_cut1_covid_s42..s46` report
`best_val_ic = +0.1198 +/- 0.0121` across five seeds, but those runs predate the
placebo fix and are not decision evidence. The earlier `+0.146 vs +0.048`
comparison is removed because it did not match the ledger and mixed
non-comparable runs.

The current conclusion is therefore conservative: PatchTST is not maxed out,
but no PatchTST variant is validated. The next step is to prove the corrected
gate works, then rerun only the cheapest experiments that can change the
decision.

## Project Read

Internal project evidence is as important as external papers:

- `memory/project_patchtst_btuned_leakage_2026-05-31.md`: B_tuned Tier-3 was
  `invalid_experiment`; timeshift placebo IC `+0.0687` exceeded real IC
  `+0.0437`. Treat pre-fix PatchTST results as leak-contaminated.
- `memory/project_strategy_local_optimum_2026-05-14.md`: ten strategy knob
  sweeps produced zero promotable candidates. The next improvement likely needs
  structural change: signal, universe, model, or regime dispatch.
- `memory/project_longshort_clean_verdict_2026-05-14.md` and
  `memory/feedback_regime_conditional_strategy.md`: pooled metrics can bury
  actionable regime behavior. Report per-regime first and pooled second.
- `renquant-common` now exposes `detector_version="v2026-05-31"` for
  `compute_hmm_regime_labels`, but the model harness still defaults to legacy
  calls unless it explicitly wires the version.

## Research Read

PatchTST is a strong starting point because patching reduces attention cost and
keeps local temporal semantics. Its main design is also the main RenQuant risk:
channel independence is efficient, but a cross-sectional stock ranker needs
stock-to-stock, sector-to-market, and market-to-stock interactions.

The strongest literature fit is cross-variate and cross-stock modeling:

- iTransformer embeds individual series as variate tokens and uses attention to
  capture multivariate correlations.
- Crossformer explicitly models cross-time and cross-dimension dependency.
- StockMixer is finance-specific and mixes indicator, time, and stock dimensions
  with explicit stock-to-market and market-to-stock influence.
- MASTER is finance-specific and alternates intra-stock and inter-stock
  aggregation with market-guided feature selection.
- TSMixer/PatchTSMixer provides efficient time and feature MLP mixing.
- DLinear/NLinear must be tried early: Zeng et al. show simple linear baselines
  beat many Transformer time-series models on long-term forecasting benchmarks.

Foundation models such as TimesFM, Chronos, and Moirai are interesting, but they
are not first-priority production rankers. Their native task is future
time-series value forecasting, while RenQuant needs point-in-time,
exogenous-feature, cross-sectional excess-return ranking. Use them first as
frozen feature generators or sanity benchmarks.

## P0: Debug And Measurement Fixes

Do these before spending overnight compute.

1. Add a placebo-gate smoke fixture. Phase A.0 must prove the corrected
   shuffled-label and time-shift placebos go near zero on a known clean setup.
   If the gate fails, stop model research and debug the gate.

2. Wire detector version explicitly. Add `--detector-version v2026-05-31` to
   `ExperimentSpec`, `RegimeDetectorContractTask`, `ComputeRegimeLabelsTask`,
   and `PerRegimeICCallback`, then call
   `compute_hmm_regime_labels(..., detector_version=args.detector_version)`.
   Decision runs must not use `--no-regime-contract`; that bypass is only for
   smoke or detector-debug runs.

3. Align checkpoint selection with research judgement. The trainer currently
   selects the best epoch on `eval_min_regime_ic`, while the research verdict
   uses pooled per-date Spearman IC plus regime gates. Run a temporary ablation:
   `min_regime_ic`, `pooled_ic`, and `robust_composite`. After the ablation,
   delete the two losing metric paths and keep one canonical selection metric.

4. Remove implicit umbrella path assumptions from the trainer. `research.py`
   accepts explicit `--dataset`, `--spy-path`, and `--strategy-config`, but
   `hf_trainer.py` still has fallback logic around `RENQUANT_STRATEGY_DIR` and
   default strategy paths. The model repo should require explicit paths or
   installed contract packages.

5. Improve ledger structure. Persist cut, seed, config, cross-stock, FiLM,
   detector version, trial kind, matrix hash, and commit SHA as structured
   fields, not only in `notes`.

6. Add label-lineage audits. Persist label column, lookahead, label-shift
   policy, shifted-source split checks, train-fitted winsor bounds, and row
   counts after placebo mutation.

## Evidence Registry Requirements

The current inconsistency came from fragmented evidence, not from the raw
dataset: SQLite ledger rows, JSON summaries, artifact directories, and memory
notes all describe experiments, but none is the canonical index. Fix this before
using any result in a decision.

Required canonical fields for every trial:

- `experiment_id`, `matrix_hash`, `trial_id`, `trial_kind`, `config_name`,
  `cut`, `seed`, `epochs`, `device`, and scheduler plan.
- `repo`, `git_head`, dirty flag, package versions, detector version, strategy
  config fingerprint, dataset fingerprint, and feature manifest fingerprint.
- Metric definitions with namespaced fields: `selection_min_regime_ic`,
  `selection_pooled_ic`, `verdict_pooled_ic`, `per_regime_ic`,
  `placebo_shuffle_ic`, and `placebo_timeshift_ic`.
- Evidence status: `valid`, `screen_only`, `suspect`, or `invalid`, plus
  `invalidation_reason`. All pre-PR #9 PatchTST artifacts should be imported
  only as `suspect_pre_pr9_placebo_bug`.
- Source paths for every artifact used in a report.

Rules:

- Reports must read from `ExperimentPipeline` artifacts or an explicitly
  imported legacy artifact index. They must not infer evidence from directory
  names or parse `training_runs.notes`.
- Any result missing detector version, placebo verdict, dataset fingerprint, or
  metric definition is `screen_only` at best.
- A doc may cite historical numbers only with artifact path, metric name, seed
  count, and validity status.

## P1: Low-Cost Decision Baselines

Before more PatchTST architecture work, run the cheapest models that can falsify
the Transformer path.

1. `DLinear` / `NLinear`: must-try baseline. If a simple linear model beats
   PatchTST under the same splits, placebos, and per-regime gates, the PatchTST
   investment should pause.
2. `PatchTSMixer` / `TSMixer`: packaged or benchmark-library MLP-mixer baseline.
   This tests time/feature mixing without full attention cost.
3. `B_tuned` revalidation: only as the corrected PatchTST control, not as a
   trusted historical baseline.
4. `C_xstock` revalidation: test only after A.0 passes. Cross-stock attention
   remains plausible, but its historical lift is not validated.

## P2: PatchTST Capability Improvements

These are second after P0 and P1.

- Add a market/factor token variant: aggregate same-day market, sector, and
  style context into explicit tokens before the rank head. This is the smallest
  MASTER/StockMixer-style addition to current PatchTST.
- Re-test FiLM only after `detector_version="v2026-05-31"` is wired through the
  entire harness and regime contract passes.
- Add multi-horizon heads for `fwd_5d_excess`, `fwd_20d_excess`, and
  `fwd_60d_excess`. Keep one primary selection label, but use auxiliary heads
  to improve representation.
- Treat within-dataset masked pretraining as a regularization/warm-start
  hypothesis, not as proven self-supervised transfer. Design a compute-equivalent
  A/B: random init for N total steps versus masked pretrain plus fine-tune for
  the same N total steps. Cross-dataset transfer is a separate experiment.

## P3: Data Expansion And Alternative Models

Increase data only after the measurement surface is stable.

- Expand the universe through `renquant-base-data` with point-in-time membership
  snapshots, not current constituents backfilled into history.
- Extend history before 2016 only for point-in-time features with consistent
  availability. More dates are useful mainly if they add more bear, inflation,
  unwind, and low-volatility regimes.
- Add feature groups through gated ablations: sector-relative returns,
  macro/ETF state, options IV, fundamental revisions, and cleaned sentiment.
  Raw sentiment should not be bulk-added because prior evidence says it can
  dilute signal.
- Test `StockMixerLite` after DLinear/TSMixer. It best matches the RenQuant
  panel shape and should be cheaper than attention-heavy models.
- Test `MASTERLite` after StockMixerLite. It is closer to the finance problem
  but more complex.
- Test iTransformer/Crossformer only if cross-stock attention or mixer baselines
  prove that cross-variate modeling is the winning axis.

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
| DLinear/NLinear | Official LTSF-Linear/DLinear repo, Time-Series-Library | P1 must-try baseline. |
| PatchTSMixer / TSMixer | Hugging Face `transformers`, NeuralForecast | P1 MLP-mixer baseline. |
| StockMixer | Official SJTU-DMTai repo | Port architecture if license/deps pass review. |
| MASTER | Official SJTU-DMTai repo | Reference for market-guided stock/market tokens. |
| iTransformer | Official THUML repo or Time-Series-Library | Reference if cross-stock attention wins. |
| Crossformer | Official Thinklab-SJTU repo | Second-wave cross-dimension Transformer. |
| TimesFM | Google Research repo | Frozen feature or benchmark only. |
| Chronos | Amazon Science repo | Frozen feature or benchmark only. |
| Moirai | Salesforce `uni2ts` repo | Frozen feature or benchmark only. |

Every implementation PR should include a source note with paper URL, repo URL,
license, pinned commit/version, deviations from the reference, and adapter tests
showing expected tensor shapes and deterministic smoke behavior.

## Proposed Experiment Matrix

All experiments should run through `renquant_model_patchtst.research` or the
same `ExperimentPipeline` contract for alternative models. Use
`renquant_common.run_parallel` only for independent cut/seed jobs when the
scheduler chooses parallel execution. On MPS, keep one training job at a time;
on CPU or multi-GPU, cap per-worker threads and persist the execution plan.

### Phase A.0: Gate Smoke

Target wallclock: about 30 minutes on MPS.

```bash
python -m renquant_model_patchtst.research \
  --phase range_find \
  --configs B_tuned \
  --cuts cut1_covid \
  --seeds 42 \
  --epochs 4 \
  --device mps \
  --detector-version v2026-05-31
```

Kill criteria: stop if detector contract fails, if shuffled-label placebo is not
near zero, if time-shift placebo is not near zero, or if placebo IC exceeds the
real IC fraction gate.

### Phase A.1: Cheap Cross-Stock Screen

Run only after A.0 passes. Target wallclock: about 6 hours sequential on MPS.

```bash
python -m renquant_model_patchtst.research \
  --phase range_find \
  --configs B_tuned,C_xstock \
  --cuts cut1_covid,cut2_fed,cut3_inflpk,cut4_svb,cut5_unwind \
  --seeds 42 \
  --epochs 4 \
  --device mps \
  --detector-version v2026-05-31
```

Kill criteria: stop if placebos fail, if `C_xstock` does not beat `B_tuned` on
mean pooled IC, if any non-defensive regime IC is negative, or if worst-cut IC
is negative.

### Phase A.2: Overnight Confirmation Sweep

Run only for candidates surviving A.1. Use five seeds and all five cuts. Do not
run every speculative config; the full 5 config x 5 cut x 5 seed matrix is too
expensive unless A.1 proves the axis is worth it.

### Phase B: Selection Metric Ablation

Add temporary trainer support for
`--selection-metric min_regime_ic|pooled_ic|robust_composite`, run it only on
the A.1 survivor, then delete the two losing metric implementations.

### Phase C: P1 Alternative Baselines

Wire DLinear/NLinear and PatchTSMixer/TSMixer into the same pipeline contract:
same data, same splits, same placebos, same per-regime report, same artifact
fields. If a P1 baseline wins, pause PatchTST architecture work.

### Phase D: Data And Model Expansion

Only after P0/P1/P2 produce a stable winner: rerun the winner on larger
point-in-time universes and longer history, changing one data dimension per run.
Then compare StockMixerLite and MASTERLite.

## Promotion Tiers

- REJECT: any placebo failure, missing detector contract, negative
  non-defensive regime evidence, negative worst-cut IC, or no lift over the
  control.
- SCREEN: gates pass and mean pooled IC improves, but evidence is insufficient
  for live use because standard error, DSR, PBO, or seed count is weak.
- LIVE: confirm phase passes all placebos, beats XGB and current model controls,
  has no negative non-defensive regime evidence, worst-cut IC is positive, DSR
  passes threshold, and PBO is acceptable.

## Expected-Impact Triage

| Item | Expected information per compute | Cost | Priority |
|---|---|---:|---|
| A.0 placebo smoke | Highest: validates or blocks all PatchTST results | Low | P0 |
| Detector-version wiring | Highest: required for regime gates | Low/medium | P0 |
| DLinear/NLinear | High: can falsify Transformer need | Low | P1 |
| PatchTSMixer/TSMixer | High: cheap non-attention baseline | Low/medium | P1 |
| C_xstock revalidation | Medium/high if A.0 passes | Medium | P1 |
| Market/factor token | Medium: tests finance-specific context | Medium | P2 |
| StockMixerLite | Medium/high after P1 | Medium | P3 |
| MASTERLite | Medium but more implementation risk | High | P3 |
| Foundation models | Low for primary ranking; useful as features | Medium/high | Later |

## Recommended Order

1. Implement P0 detector-version, placebo-smoke, ledger, and audit fixes.
2. Run Phase A.0 and stop if the gate fails.
3. Wire DLinear/NLinear and PatchTSMixer/TSMixer baselines.
4. Run Phase A.1 for B_tuned versus C_xstock only if A.0 passes.
5. Run Phase A.2 or Phase B only for survivors.
6. Expand data and test StockMixerLite/MASTERLite after the measurement surface
   is stable.

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
