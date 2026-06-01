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

## Model families

| Family | Package | `--model` flag | Research config | Status |
|---|---|---|---|---|
| GBDT panel-LTR | `renquant_model_gbdt` | — | (own CLI) | production |
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
| `20260530085443-hf_patchtst-95373a` | 2026-05-30T08:54:43.713636 | hf_patchtst | -0.0814 | 169 | 142 | mps | — | manual | `dbec047` |
| `20260530083720-hf_patchtst-ea9013` | 2026-05-30T08:37:20.527692 | hf_patchtst | -0.0509 | 169 | 142 | mps | — | manual | `423cf68` |
| `20260530081449-hf_patchtst-fe31d3` | 2026-05-30T08:14:49.501296 | hf_patchtst | -0.0385 | 169 | 142 | mps | — | manual | `550c328` |
| `20260530075326-hf_patchtst-3674ad` | 2026-05-30T07:53:26.997435 | hf_patchtst | -0.1024 | 169 | 142 | mps | — | manual | `d86027a` |
| `20260530073808-hf_patchtst-bc239c` | 2026-05-30T07:38:08.060957 | hf_patchtst | +0.0304 | 169 | 142 | mps | — | manual | `1be8c8d` |
| `20260530071930-hf_patchtst-21e1c5` | 2026-05-30T07:19:30.614108 | hf_patchtst | +0.0841 | 169 | 142 | mps | — | manual | `1be8c8d` |
| `20260530070205-hf_patchtst-8b2c44` | 2026-05-30T07:02:05.152369 | hf_patchtst | -0.0366 | 169 | 142 | mps | — | manual | `6ca88db` |
| `20260530064929-hf_patchtst-759431` | 2026-05-30T06:49:29.023165 | hf_patchtst | -0.0604 | 169 | 142 | mps | — | manual | `67bf666` |

_last refreshed: 2026-05-30T18:30:43.902414Z_
<!-- LATEST_MODELS:END -->
