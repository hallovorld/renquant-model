"""DLinear / NLinear cross-sectional ranker — Zeng et al. AAAI 2023 adapted.

Source: ``cure-lab/LTSF-Linear`` (paper: "Are Transformers Effective for Time
Series Forecasting?", arXiv 2205.13504). Implementation Reference Policy:
see ``docs/dlinear_source_note.md`` for pinned commit, license, and
documented deviations.

Architecture
------------

Faithful to upstream's per-channel temporal pattern: the input
``(batch, seq_len, n_channels)`` is decomposed into trend + seasonal,
then a per-channel ``Linear(seq_len -> 1)`` produces a single forecast
step per channel. The ``individual`` flag controls whether each channel
gets its own weights (upstream-style, defensible per channel) or all
channels share a single weight set (faster, fewer parameters).

The only material deviation from upstream is the **output head**: we
aggregate the per-channel forecasts to a single scalar score via a
``Linear(n_channels -> 1)`` so the model fits RenQuant's
cross-sectional ranking contract. The temporal modeling path is
unchanged.

DLinearRanker:
  1. Trend/seasonal decomposition via moving-average kernel
     (kernel_size configurable; default 25, matching LTSF-Linear's
     pinned upstream value at SHA 0c11366).
  2. Per-channel temporal linear heads: trend_head + seasonal_head
     each produce a 1-step "forecast" per channel.
  3. Aggregate per-channel forecasts into a scalar ranking score.

NLinearRanker:
  1. Per-channel residual normalization (subtract last timestep).
  2. Per-channel ``Linear(seq_len -> 1)`` head.
  3. Add the last value back; aggregate to scalar.

This keeps the upstream architectural skeleton intact, so a poor result
genuinely falsifies the linear-baseline hypothesis (rather than
falsifying a degenerate compressed variant).
"""
from __future__ import annotations

import torch
import torch.nn as nn


class MovingAverageDecomposition(nn.Module):
    """Trend extraction via centered moving-average pooling.

    Faithful to LTSF-Linear's ``series_decomp.moving_avg`` — replication-
    padded average pool with even/odd kernel_size both supported. The
    returned ``seasonal`` is ``x - trend``, preserving the
    ``x = trend + seasonal`` decomposition.
    """

    def __init__(self, kernel_size: int = 5) -> None:
        super().__init__()
        if kernel_size < 1:
            raise ValueError(f"kernel_size must be ≥ 1, got {kernel_size}")
        self.kernel_size = int(kernel_size)
        self.avg = nn.AvgPool1d(
            kernel_size=self.kernel_size,
            stride=1,
            padding=0,
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (batch, seq_len, n_features) — PatchTST-style (B, T, C).
        if x.dim() != 3:
            raise ValueError(f"DLinear expects (batch, seq_len, n_features); got {x.shape}")
        # AvgPool1d expects (B, C, T). Transpose: (B, T, C) → (B, C, T).
        bct = x.transpose(1, 2)
        # Replication-pad both ends so the trend has the same length as x.
        front_pad = (self.kernel_size - 1) // 2
        back_pad = self.kernel_size - 1 - front_pad
        bct = nn.functional.pad(bct, (front_pad, back_pad), mode="replicate")
        trend_bct = self.avg(bct)
        trend = trend_bct.transpose(1, 2)  # back to (B, T, C)
        seasonal = x - trend
        return seasonal, trend


def _per_channel_temporal_linear(
    series: torch.Tensor,
    head: nn.Module,
    individual: bool,
) -> torch.Tensor:
    """Apply Linear(T -> 1) per channel.

    series : (B, T, C)
    head   : either nn.Linear(T, 1) for shared, or nn.ModuleList of n_channels
             Linear(T, 1) for individual=True.
    returns: (B, C) — single-step forecast per channel.

    Matches upstream LTSF-Linear's ``individual`` semantics:
      individual=False → one ``Linear(T, 1)`` shared across all channels
      individual=True  → ``ModuleList`` of n_channels ``Linear(T, 1)``
                          producing per-channel learned dynamics.
    """
    if individual:
        # head is ModuleList of length C.
        out_per_channel = []
        for c, layer in enumerate(head):
            # (B, T) → (B, 1) → (B,)
            out_per_channel.append(layer(series[:, :, c]).squeeze(-1))
        return torch.stack(out_per_channel, dim=-1)  # (B, C)
    # Shared head: apply Linear(T, 1) to every channel.
    # Transpose so channels are batch-like: (B, C, T), apply, squeeze.
    bct = series.transpose(1, 2)        # (B, C, T)
    out = head(bct).squeeze(-1)          # (B, C, 1) → (B, C)
    return out


class DLinearRanker(nn.Module):
    """DLinear adapted for cross-sectional scalar ranking.

    Input:  (batch, seq_len, n_features) feature sequences per sample.
    Output: (batch,)                     scalar score per sample.

    Parameters
    ----------
    n_features
        Number of feature/channel columns per timestep.
    seq_len
        Number of historical timesteps consumed.
    kernel_size
        Moving-average window size for trend extraction. Default 25
        matches the LTSF-Linear/DLinear repo at the pinned upstream
        SHA (``models/DLinear.py`` line 47 at ``0c11366``). Smaller
        kernels are acceptable for short sequences, but the default
        keeps faithful-to-upstream parity so a poor result really
        falsifies the same DLinear hypothesis the paper measures.
    individual
        If True, give each channel its own ``Linear(seq_len, 1)`` weights
        (upstream-style per-channel dynamics). If False (default), all
        channels share a single set of weights — fewer parameters,
        bigger inductive bias.
    """

    def __init__(
        self,
        n_features: int,
        seq_len: int,
        kernel_size: int = 25,
        individual: bool = False,
    ) -> None:
        super().__init__()
        if n_features < 1:
            raise ValueError(f"n_features must be ≥ 1, got {n_features}")
        if seq_len < 1:
            raise ValueError(f"seq_len must be ≥ 1, got {seq_len}")
        self.n_features = int(n_features)
        self.seq_len = int(seq_len)
        self.individual = bool(individual)

        # Trend + seasonal decomposition.
        self.decomp = MovingAverageDecomposition(kernel_size=kernel_size)

        # Per-channel temporal heads. Shared (individual=False) uses a single
        # Linear(T, 1); individual=True gives every channel its own weights —
        # matches upstream LTSF-Linear's `individual=True` mode exactly.
        if self.individual:
            self.trend_head: nn.Module = nn.ModuleList(
                [nn.Linear(self.seq_len, 1) for _ in range(self.n_features)]
            )
            self.seasonal_head: nn.Module = nn.ModuleList(
                [nn.Linear(self.seq_len, 1) for _ in range(self.n_features)]
            )
        else:
            self.trend_head = nn.Linear(self.seq_len, 1)
            self.seasonal_head = nn.Linear(self.seq_len, 1)

        # Final channel aggregation: per-channel forecasts → scalar score.
        # This is the only path-deviation from upstream forecasting; the
        # temporal modeling per channel above is faithful.
        self.channel_aggregator = nn.Linear(self.n_features, 1, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F) — decompose, per-channel temporal heads, aggregate.
        seasonal, trend = self.decomp(x)              # both (B, T, F)
        seasonal_out = _per_channel_temporal_linear(
            seasonal, self.seasonal_head, self.individual,
        )                                              # (B, F)
        trend_out = _per_channel_temporal_linear(
            trend, self.trend_head, self.individual,
        )                                              # (B, F)
        per_channel = seasonal_out + trend_out         # (B, F)
        return self.channel_aggregator(per_channel).squeeze(-1)  # (B,)


class NLinearRanker(nn.Module):
    """NLinear adapted for cross-sectional scalar ranking.

    Faithful per-channel residual structure from upstream LTSF-Linear:
    subtract the last timestep value per channel, apply Linear(T, 1) per
    channel, add the last value back. Aggregate per-channel scalars to a
    single scalar score.
    """

    def __init__(
        self,
        n_features: int,
        seq_len: int,
        individual: bool = False,
    ) -> None:
        super().__init__()
        if n_features < 1:
            raise ValueError(f"n_features must be ≥ 1, got {n_features}")
        if seq_len < 1:
            raise ValueError(f"seq_len must be ≥ 1, got {seq_len}")
        self.n_features = int(n_features)
        self.seq_len = int(seq_len)
        self.individual = bool(individual)

        if self.individual:
            self.head: nn.Module = nn.ModuleList(
                [nn.Linear(self.seq_len, 1) for _ in range(self.n_features)]
            )
        else:
            self.head = nn.Linear(self.seq_len, 1)

        self.channel_aggregator = nn.Linear(self.n_features, 1, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F)
        # Per-channel last-value subtraction.
        last = x[:, -1:, :].clone()                # (B, 1, F)
        normalized = x - last                       # (B, T, F)
        normalized_out = _per_channel_temporal_linear(
            normalized, self.head, self.individual,
        )                                           # (B, F)
        # Add back per-channel last value (broadcast back to scalar per channel).
        per_channel = normalized_out + last.squeeze(1)  # (B, F)
        return self.channel_aggregator(per_channel).squeeze(-1)  # (B,)
