# renquant-model

Single repository for all RenQuant model families. Merges the former
`renquant-model-gbdt` and `renquant-model-patchtst` repos (RFC §"Backfill
Plan" P3) so they share CV primitives, feature-assembly utilities, the
training-ledger writer, and a single Scorer-registration surface.

## Layout

```
src/
  renquant_model_gbdt/      # GBDT panel-LTR family (production)
  renquant_model_patchtst/  # PatchTST / sequence family (candidate)
  renquant_model_common/    # cross-family scaffolding
tests/
  gbdt/                     # GBDT family tests
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
pip install -e .[gbdt]       # XGBoost backend
pip install -e .[patchtst]   # torch + transformers backend
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
| `5770ccc3` | 2026-05-29T16:35:00Z | hf_patchtst | +0.0182 | 169 | 142 | mps | 34.0m | manual | `b863da9b` |
| `a1bd9d1d` | 2026-05-29T16:02:37Z | panel_ltr_xgboost | +0.0456 | 169 | — | cpu | 1.1m | manual | `b863da9b` |

_last refreshed: 2026-05-30T05:47:36.754838Z_
<!-- LATEST_MODELS:END -->
