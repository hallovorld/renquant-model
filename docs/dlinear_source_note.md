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
- **Reference commit** (pinned for this implementation): the public
  `main` branch at the time of writing (no submodule / no vendored
  source — we ported the architecture by hand below 50 LOC). The
  reference behavior is the model classes
  `models.DLinear` and `models.NLinear` in the upstream repo's `models/`
  directory.

## License

LTSF-Linear is released under the Apache License 2.0
(https://github.com/cure-lab/LTSF-Linear/blob/main/LICENSE). Our re-
implementation is also Apache-2.0 compatible (RenQuant is internal /
proprietary; this code does not redistribute LTSF-Linear's source). No
upstream code is vendored — the architectures are re-implemented from
the paper description + a reading of the upstream reference, both small
enough that clean-room reimplementation is appropriate.

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

## Deviations from upstream

The upstream DLinear / NLinear are **univariate forecasting** models:
input is a single time series, output is a multi-step forecast. RenQuant's
task is **cross-sectional ranking** on a multivariate (multi-feature)
input — we want a single scalar score per (ticker, date) sample.

Documented deviations:

| Concern | Upstream | RenQuant adaptation |
|---|---|---|
| Input shape | `(batch, seq_len)` univariate | `(batch, seq_len, n_features)` multivariate |
| Output shape | `(batch, output_length)` forecast | `(batch,)` scalar score |
| Feature handling | N/A (univariate) | `Linear(n_features → 1)` projection before the linear head |
| Decomposition head | Forecasts trend + seasonal separately | Same, but output is summed to scalar |
| Loss surface | MSE on forecast | Ranking loss (set by the trainer; not in this module) |

### Why scalar output is acceptable

The Zeng et al. paper's *result* (linear is competitive with Transformer)
does NOT depend on output dimensionality — it depends on the architectural
class (linear vs attention). A scalar ranking head preserves the
falsification-baseline property: if `DLinearRanker` matches `PatchTST` on
the same data + splits + placebos + per-regime gates, the conclusion
"Transformer overhead is unnecessary" follows even though our output is
different from the paper's.

### Why the feature projection is acceptable

Multivariate inputs reduced to univariate via a learned linear projection
is the simplest natural extension. The alternative (per-variable linear
heads, then aggregated) is also implementable via the upstream's
`individual=True` flag — we kept the per-feature projection simple here
to bound complexity. If decision-quality is borderline, we can revisit
with `individual=True` semantics.

## Adapter-test evidence

`tests/patchtst/test_dlinear_ranker.py` (this PR) covers:

- Both models instantiate at expected `(n_features, seq_len)` pairs.
- Forward pass produces the expected `(batch,)` shape.
- All outputs are finite (no NaN / Inf in default initialization).
- Deterministic with fixed seed (torch.manual_seed).
- `MovingAverageDecomposition` returns components that exactly sum back
  to the input.
- Both models work in batched + single-sample modes.

Integration with the harness (i.e. wiring into `research_pipeline` as
an alternative `trainer_runner`) is in a sibling PR — this one ships
**model only**, not the adapter trainer.
