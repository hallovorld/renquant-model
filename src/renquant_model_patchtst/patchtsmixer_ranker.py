"""PatchTSMixer cross-sectional ranker — HF transformers MLP-mixer baseline.

Per the merged research plan §"P1 Low-Cost Decision Baselines": "PatchTSMixer
/ TSMixer is a P1 MLP-mixer baseline. First MLP-mixer baseline before custom
StockMixer." A second falsification axis alongside DLinear/NLinear: if a
mixer architecture matches or beats the attention-based PatchTST on the
same data, the attention premium needs justification.

Source per Implementation Reference Policy
------------------------------------------

- **Paper**: "TSMixer: An All-MLP Architecture for Time Series Forecasting"
  (Chen et al. — Google Research). PatchTSMixer is the patched-input
  variant integrated into Hugging Face transformers.
- **HF docs**: https://huggingface.co/docs/transformers/main/model_doc/patchtsmixer
- **Package source**: ``transformers.PatchTSMixerModel`` (the
  ``transformers`` package this venv has installed; version stamped at
  import time in tests).
- **License**: HF transformers is Apache-2.0; we vendor nothing — only
  use the package's public API.

The ranker is a thin wrapper around HF's ``PatchTSMixerModel`` adding a
single ``Linear(d_model → 1)`` ranking head. Pooling matches the
HFPatchTSTRanker pattern (mean over channels + patches) so the two
models can be A/B compared on identical pre/post processing surfaces —
the only thing that differs is the architecture between input and pooled
representation.

Architecture
------------

  past_values: (batch, seq_len, n_channels)
  ↓ PatchTSMixerModel
  last_hidden_state: (batch, n_channels, n_patches, d_model)
  ↓ mean(dim=(1, 2))           ← pool over channels + patches
  pooled: (batch, d_model)
  ↓ Linear(d_model → 1).squeeze
  score: (batch,)               ← scalar ranking score per sample
"""
from __future__ import annotations

import torch
import torch.nn as nn
from transformers import PatchTSMixerConfig, PatchTSMixerModel


class HFPatchTSMixerRanker(nn.Module):
    """HF PatchTSMixer backbone + ranking head.

    Mirrors HFPatchTSTRanker's contract surface so the harness can swap
    between the two with a ``--model`` flag:

      * Input:  ``past_values`` (batch, seq_len, n_channels)
      * Output: ``dict`` with key ``"score"`` → (batch,) scalar score

    PatchTSMixer is channel-mixed (no per-channel-independent backbone),
    so cross-stock-attention and FiLM regime conditioning aren't wired
    here. Those PatchTST-specific extensions can be added later if the
    base MLP-mixer baseline shows competitive numbers.
    """

    def __init__(self, cfg: PatchTSMixerConfig) -> None:
        super().__init__()
        self.backbone = PatchTSMixerModel(cfg)
        self.rank_head = nn.Linear(cfg.d_model, 1)

    def forward(
        self,
        past_values: torch.Tensor,
        labels: torch.Tensor | None = None,        # noqa: ARG002 — harness contract
        regime_context: torch.Tensor | None = None,  # noqa: ARG002 — accepted-but-ignored
        dates=None,                                  # noqa: ARG002 — accepted-but-ignored
    ) -> dict[str, torch.Tensor]:
        # past_values: (B, T, C) → backbone returns (B, C, n_patches, d_model)
        out = self.backbone(past_values=past_values)
        h = out.last_hidden_state.mean(dim=(1, 2))   # → (B, d_model)
        return {"score": self.rank_head(h).squeeze(-1)}


def build_default_config(
    seq_len: int,
    n_channels: int,
    patch_length: int = 8,
    patch_stride: int = 8,
    d_model: int = 16,
    num_layers: int = 2,
    expansion_factor: int = 2,
    dropout: float = 0.1,
) -> PatchTSMixerConfig:
    """Build a small PatchTSMixerConfig matching the surface PatchTST uses.

    Defaults pinned to keep parameter count comparable to a small PatchTST
    (small d_model, 2 layers). Production sweep should tune these via the
    research harness's config_args, same pattern as PatchTST's TUNED
    config list.

    ``patch_length`` and ``patch_stride`` default to 8 so ``seq_len=24``
    produces exactly 3 non-overlapping patches (24 / 8 = 3). For shorter
    ``seq_len``, caller must pass ``patch_length`` that divides cleanly
    or PatchTSMixer drops the trailing remainder.
    """
    if seq_len < patch_length:
        raise ValueError(
            f"seq_len ({seq_len}) must be ≥ patch_length ({patch_length})"
        )
    return PatchTSMixerConfig(
        context_length=int(seq_len),
        prediction_length=1,
        num_input_channels=int(n_channels),
        patch_length=int(patch_length),
        patch_stride=int(patch_stride),
        d_model=int(d_model),
        num_layers=int(num_layers),
        expansion_factor=int(expansion_factor),
        dropout=float(dropout),
    )
