# renquant-model

Single repository for all RenQuant model families. Merges the former
`renquant-model-gbdt` and `renquant-model-patchtst` repos (RFC §"Backfill
Plan" P3) so they share CV primitives, feature-assembly utilities, the
training-ledger writer, and a single Scorer-registration surface.

## Layout

```
src/
  renquant_model_gbdt/            # GBDT panel-LTR family (production)
  renquant_model_alpha158_linear/ # alpha158 linear side-strategy family
  renquant_model_patchtst/        # PatchTST / sequence family (candidate)
  renquant_model_common/          # cross-family scaffolding
tests/
  gbdt/                     # GBDT family tests
  alpha158_linear/          # alpha158 linear tests
  patchtst/                 # sequence family tests
```

> Namespace note: the RFC sketched a `renquant_model.{gbdt,patchtst}`
> nested namespace. To preserve the working Scorer entry points and
> consumer wiring established in P1, this repo keeps the two top-level
> packages (`renquant_model_gbdt`, `renquant_model_patchtst`)
> co-located rather than deep-renaming. The consolidation goal (one
> repo, shared code, one management point) is met; the nested namespace
> can be revisited later as a non-breaking internal refactor.

## Install

```bash
pip install -e .[gbdt]            # XGBoost backend
pip install -e .[alpha158-linear] # Alpha158 linear backend
pip install -e .[patchtst]        # torch + transformers backend
```

## Model families

| Family | Package | `--model` flag | Research config | Status |
|---|---|---|---|---|
| GBDT panel-LTR | `renquant_model_gbdt` | — | (own CLI) | production |
| Alpha158 linear | `renquant_model_alpha158_linear` | — | side-strategy retrain | production side-strategy |
| PatchTST | `renquant_model_patchtst` | `patchtst` (default) | `B_tuned` / `C_xstock` / `D_film` / `E_drop_senti` / `F_fwd20d` | candidate |
| PatchTSMixer | `renquant_model_patchtst` | `patchtsmixer` | `G_patchtsmixer` | W1 baseline |
| DLinear | `renquant_model_linear` | `dlinear` | `L_dlinear` (kernel=25) / `L_dlinear_k5` / `L_dlinear_k3` | W1 baseline |
| NLinear | `renquant_model_linear` | `nlinear` | `L_nlinear` | W1 baseline |

All sequence families (PatchTST, PatchTSMixer, DLinear, NLinear) share the
same research harness (`renquant_model_patchtst.research_pipeline`), the
same data preprocessing (`load_panel_with_split` + `csrank_norm` +
`train-fit Winsorize`), and the same evaluation surface (per-regime IC,
placebo gates, DSR/PBO/promotion tiers) — so cross-family comparisons are
apples-to-apples.

Invocation:

```bash
# PatchTST research
python -m renquant_model_patchtst.research --configs B_tuned --cuts all ...

# PatchTSMixer (same CLI, just switch the config)
python -m renquant_model_patchtst.research --configs G_patchtsmixer --cuts all ...

# Linear baselines (separate CLI, mirrors the PatchTST shape)
python -m renquant_model_linear.research --configs L_dlinear --cuts all ...
```

Phase A.0 smoke runners (small synthetic fixture, < 5 min):

```bash
./scripts/run_phase_a0_smoke.sh          # PatchTST family
./scripts/run_phase_a0_smoke_linear.sh   # DLinear / NLinear family
```

## Scorer registration

Both families register loaders under the `renquant_common.scorers`
entry-point group. Consumers (`renquant-pipeline`, `renquant-backtesting`)
resolve them exclusively through `renquant_common.load_scorer` — they
never import this package directly.

## Dependency rule

Depends on `renquant-common`, `renquant-base-data`, `renquant-artifacts`.
Must not import `renquant-pipeline`, `renquant-execution`, or
`renquant-backtesting`.

<!-- LATEST_MODELS:START -->
## Latest trained models

_Auto-generated from `data/sim_runs.db::training_runs` by `scripts/refresh_readme_latest_models.py`._

| run_id | when | family | OOS IC | features | tickers | device | took | trigger | commit |
|---|---|---|---|---|---|---|---|---|---|
| `20260723213615-hf_patchtst-6567bb` | 2026-07-23T21:36:15.281886 | hf_patchtst | -0.0569 | 172 | 145 | mps | — | manual | `e10b02e` |
| `20260723210654-hf_patchtst-b88395` | 2026-07-23T21:06:54.180992 | hf_patchtst | -0.0439 | 172 | 145 | mps | — | manual | `e10b02e` |
| `20260723202258-hf_patchtst-6a6f34` | 2026-07-23T20:22:58.624333 | hf_patchtst | +0.0143 | 172 | 145 | mps | — | manual | `e10b02e` |
| `20260723182427-hf_patchtst-9a8a1c` | 2026-07-23T18:24:27.235924 | hf_patchtst | +0.1994 | 172 | 145 | mps | — | manual | `e10b02e` |
| `20260723180816-hf_patchtst-bfed54` | 2026-07-23T18:08:16.045060 | hf_patchtst | +0.1454 | 172 | 145 | mps | — | manual | `e10b02e` |
| `20260723175216-hf_patchtst-9309ad` | 2026-07-23T17:52:16.201190 | hf_patchtst | +0.0465 | 172 | 145 | mps | — | manual | `e10b02e` |
| `20260722053029-hf_patchtst-d1af71` | 2026-07-22T05:30:29.523244 | hf_patchtst | -0.0024 | 172 | 145 | cpu | — | manual | `5ef1c2d` |
| `20260722052754-hf_patchtst-64cd5d` | 2026-07-22T05:27:54.719251 | hf_patchtst | -0.0192 | 172 | 145 | cpu | — | manual | `5ef1c2d` |

_last refreshed: 2026-07-23T21:36:15.414428Z_
<!-- LATEST_MODELS:END -->
