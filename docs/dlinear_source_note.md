# DLinear / NLinear — Source Note

Required per the merged plan's **Implementation Reference Policy**
(`patchtst_capability_research_proposal.md` §"Implementation Reference
Policy"): paper URL, repo URL, license, pinned commit/version,
deviations, and adapter-tests evidence.

## Origin

- **Paper**: "Are Transformers Effective for Time Series Forecasting?"
  (Zeng, Chen, Zhang, Xu — AAAI 2023). https://arxiv.org/abs/2205.13504
- **Official repo**: `cure-lab/LTSF-Linear` —
  https://github.com/cure-lab/LTSF-Linear
- **Pinned commit**: `0c113668a3b88c4c4ee586b8c5ec3e539c4de5a6`
  (upstream `main` at time of this PR).
- **Reference source blobs**:
  - DLinear: https://github.com/cure-lab/LTSF-Linear/blob/0c113668a3b88c4c4ee586b8c5ec3e539c4de5a6/models/DLinear.py
  - NLinear: https://github.com/cure-lab/LTSF-Linear/blob/0c113668a3b88c4c4ee586b8c5ec3e539c4de5a6/models/NLinear.py

## License

LTSF-Linear is released under the Apache License 2.0
(https://github.com/cure-lab/LTSF-Linear/blob/main/LICENSE). Our re-
implementation is also Apache-2.0 compatible. No upstream code is
vendored — the architectures are re-implemented from the paper
description + a reading of the referenced source blobs above, both
small enough that clean-room reimplementation is appropriate.

## Why these specific baselines

Per the merged research plan's P1 section:

> "DLinear/NLinear: must-try baseline. If a simple linear model beats
> PatchTST under the same splits, placebos, and per-regime gates, the
> PatchTST investment should pause."

The Zeng et al. paper's core finding is that simple linear models match
or exceed Transformer-based time-series models on most long-term
forecasting benchmarks. Whether the result transfers to **cross-
sectional ranking** is an open empirical question that RenQuant's
research plan explicitly wants answered.

## Faithfulness to upstream + the one principled deviation

The upstream DLinear / NLinear are **univariate-per-channel forecasting**
models: input is `(batch, seq_len, n_channels)`, decomposition keeps the
channel dimension, per-channel `Linear(seq_len → output_length)` heads
produce a multi-step forecast per channel, output is `(batch, output_length, n_channels)`.

We preserve **the entire temporal-modeling path** unchanged from upstream:
decomposition keeps channels, per-channel temporal linear heads operate
on individual channels (with optional per-channel weights via
`individual=True`, matching upstream semantics).

The single principled deviation is the **output head**: instead of
returning a multi-step forecast per channel, we aggregate the per-channel
forecasts via `Linear(n_channels → 1)` to produce one scalar score per
sample. This fits RenQuant's cross-sectional ranking contract (we want
ONE score per (ticker, date) sample, not a forecast time series).

| Concern | Upstream | RenQuant adaptation |
|---|---|---|
| Input shape | `(batch, seq_len, n_channels)` | `(batch, seq_len, n_features)` (same shape; "features" = "channels") |
| Decomposition | trend + seasonal via moving-average, keeps channel dim | unchanged |
| Per-channel temporal head | `Linear(seq_len → output_length)` per channel | `Linear(seq_len → 1)` per channel |
| `individual=True` semantics | per-channel separate Linear weights | unchanged (real semantics, not just an accepted flag) |
| Output | `(batch, output_length, n_channels)` forecast | scalar aggregator `Linear(n_channels → 1)` → `(batch,)` ranking score |
| Loss | MSE on forecast | Ranking loss (set by trainer; not in this module) |

### Why the channel-aggregation deviation is acceptable

The Zeng et al. paper's *result* (linear is competitive with Transformer)
depends on the **per-channel linear temporal modeling**, which we preserve
verbatim. The output dimensionality change (multi-step forecast → scalar
score) is necessary because the tasks are different — RenQuant doesn't
have a forecast horizon, it has a ranking objective. The
`channel_aggregator` `Linear(n_channels → 1)` is the minimal addition
needed to bridge between the upstream model output and our scalar score
target.

A poor result from `DLinearRanker` / `NLinearRanker` will genuinely
falsify the "linear can match Transformer" hypothesis for RenQuant's
cross-sectional ranking task — not falsify a degenerate compressed
variant, since the temporal path is faithful to upstream.

### Parameter counts (with the per-channel restructure)

For the panel's `n_features=172, seq_len=24` shape:

| Mode | Trend head | Seasonal head | Aggregator | Total |
|---|---|---|---|---|
| `DLinear individual=False` | 25 | 25 | 172 | ~222 |
| `DLinear individual=True` | 25 × 172 = 4,300 | 4,300 | 172 | ~8,772 |
| `NLinear individual=False` | 25 | — | 172 | ~197 |
| `NLinear individual=True` | 25 × 172 = 4,300 | — | 172 | ~4,472 |

Still tiny vs PatchTST (~70k). Even `individual=True` keeps the param
ratio under 15% of PatchTST, well below the "simple baseline" threshold.

## Adapter-test evidence

`tests/patchtst/test_dlinear_ranker.py` covers:

- Both models instantiate at expected `(n_features, seq_len)` pairs.
- Forward pass produces the expected `(batch,)` shape.
- All outputs are finite (no NaN / Inf in default initialization).
- Deterministic with fixed seed (`torch.manual_seed`).
- `MovingAverageDecomposition` returns components that exactly sum back
  to the input.
- Both models work in batched + single-sample modes.
- **`individual=True` actually changes the model**: distinct output from
  `individual=False` on the same input, with the expected param-count
  scaling.
- Parameter count stays small enough to preserve "simple baseline" framing.

Integration with the harness (i.e. wiring into `research_pipeline` as
an alternative `trainer_runner`) is in a sibling PR — this one ships
**model only**, not the adapter trainer.
