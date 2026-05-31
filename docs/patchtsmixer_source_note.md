# PatchTSMixer (HF transformers) — Source Note

Required per the merged plan's **Implementation Reference Policy**.

## Origin

- **Paper**: "TSMixer: An All-MLP Architecture for Time Series
  Forecasting" (Chen, Li, Yoder, Arik, Pfister — Google Research).
  https://research.google/pubs/tsmixer-an-all-mlp-architecture-for-time-series-forecasting/
- **PatchTSMixer**: the patched-input variant integrated into Hugging
  Face transformers as a first-class model.
- **HF docs**: https://huggingface.co/docs/transformers/main/model_doc/patchtsmixer
- **Source**: `transformers.PatchTSMixerModel` (package source, not
  vendored). Version pinned by the renquant-model worktree's installed
  `transformers` — currently `5.8.1`. The exact version is recorded at
  test-time via `transformers.__version__` for evidence-registry
  attribution.

## License

HF transformers is Apache-2.0. We do not vendor any source; the
implementation uses the package's public API (`PatchTSMixerConfig` +
`PatchTSMixerModel`). Our wrapper code is also Apache-2.0 compatible.

## Why this baseline

Per the merged research plan's P1 section:

> "PatchTSMixer / TSMixer is a P1 MLP-mixer baseline. First MLP-mixer
> baseline before custom StockMixer."

This is the **second falsification axis** alongside DLinear/NLinear:
- Linear baselines (DLinear/NLinear) test "does attention add value over
  plain linear?"
- MLP-mixer baselines (PatchTSMixer/TSMixer) test "does attention add
  value over channel-mixed MLPs?"

If either baseline matches or beats PatchTST on RenQuant's cross-
sectional ranking task under the same data + splits + placebos + per-
regime gates, the attention premium has to justify itself.

## Adaptation deviations

Same shape as the DLinear adaptation (`docs/dlinear_source_note.md`):
the **only** principled deviation from upstream is the **output head**.

| Concern | Upstream PatchTSMixer | RenQuant adaptation |
|---|---|---|
| Input shape | `(batch, seq_len, n_channels)` | unchanged |
| Backbone | `PatchTSMixerModel` — channel + patch mixing MLPs | unchanged (HF public API) |
| Pool | `last_hidden_state` shape `(B, C, n_patches, d_model)` | `mean(dim=(1, 2))` → `(B, d_model)` |
| Output | multi-step forecast | `Linear(d_model → 1)` → scalar score `(B,)` |
| FiLM regime conditioning | not in upstream | not implemented here (PatchTST-specific extension) |
| Cross-stock attention | not in upstream | not implemented here (PatchTST-specific extension) |

Pooling matches the `HFPatchTSTRanker` pattern (mean over channels +
patches) exactly, so the only thing differing between a PatchTST run
and a PatchTSMixer run is the backbone architecture between input and
pooled representation. Fair-comparison framing per the merged plan.

## Tests

`tests/patchtst/test_patchtsmixer_ranker.py` covers:

- Config construction (default config + invalid input rejection)
- Forward shape: `(B, T, C)` → `(B,)` for several `(batch, seq_len, n_channels)` combos
- Harness kwargs accepted-but-ignored (labels, regime_context, dates)
- Backward pass produces gradients on most params
- Deterministic with seed
- Parameter count under 100k with default tiny config (comparable to PatchTST)
- Output differs from PatchTST on the same input (not silently calling into PatchTST)

Harness integration (`--model patchtsmixer` in `hf_trainer.py` CLI,
adapter trainer wrapping the model in the same training loop) is sibling
work — this PR ships the model wrapper + tests only.
