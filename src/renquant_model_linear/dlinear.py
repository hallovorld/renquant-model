"""DLinear / NLinear cross-sectional ranker — Zeng et al. AAAI 2023 adapted.

Source: ``cure-lab/LTSF-Linear`` (paper: "Are Transformers Effective for Time
Series Forecasting?", arXiv 2205.13504). Implementation Reference Policy:
see ``docs/dlinear_source_note.md`` for pinned commit, license, and
documented deviations.

The original DLinear is a univariate forecasting model that decomposes the
input into trend + seasonal series and applies separate linear projections
to each. RenQuant's task is cross-sectional ranking, not future-value
forecasting, so the architectural skeleton is preserved but the output
head is a single scalar score per (ticker, date) sample instead of a
multi-step forecast.

The point of these baselines per the merged research plan is **decision-
quality falsification**: if a model this simple matches or beats PatchTST
on the same data + splits + placebos, the PatchTST investment should
pause. The adaptation preserves the spirit (linear architecture, no
attention, no recurrence) but routes it through RenQuant's cross-
sectional contract.

Architecture
------------

DLinearRanker:
  1. Per-timestep feature projection: Linear(n_features → 1)
     Reduces multivariate input to univariate time-series per sample.
  2. Trend/seasonal decomposition via moving-average kernel
     (kernel_size configurable; default 5, matching LTSF-Linear).
  3. Separate Linear(seq_len → 1) for each component.
  4. Output: trend_out + seasonal_out → scalar score.

NLinearRanker:
  1. Per-timestep feature projection: Linear(n_features → 1)
  2. Subtract input[-1] (the most-recent step) from the series.
  3. Linear(seq_len → 1).
  4. Add input[-1] back.
  5. Output: scalar score.

Both have O(n_features × seq_len) parameters — tiny vs PatchTST (~70k).
"""
from __future__ import annotations

import torch
import torch.nn as nn


class MovingAverageDecomposition(nn.Module):
    """Trend extraction via centered moving-average pooling.

    Faithful to LTSF-Linear's ``series_decomp.moving_avg`` — reflection-
    padded average pool with even/odd kernel_size both supported. The
    returned ``seasonal`` is ``x - trend``, preserving the
    ``x = trend + seasonal`` decomposition.
    """

    def __init__(self, kernel_size: int = 5) -> None:
        super().__init__()
        if kernel_size < 1:
            raise ValueError(f"kernel_size must be ≥ 1, got {kernel_size}")
        self.kernel_size = int(kernel_size)
        # AvgPool1d's stride=1 keeps the time dimension; padding is added
        # manually below (replication) to keep the output length == input.
        self.avg = nn.AvgPool1d(
            kernel_size=self.kernel_size,
            stride=1,
            padding=0,
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (batch, seq_len, n_features) — last-dim time as in LTSF-Linear
        # would require transpose; we follow PatchTST's (B, T, C) convention.
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


class DLinearRanker(nn.Module):
    """DLinear adapted for cross-sectional scalar ranking.

    Input:  (batch, seq_len, n_features) feature sequences per sample.
    Output: (batch,)                     scalar score per sample.

    Parameters
    ----------
    n_features
        Number of feature columns per timestep.
    seq_len
        Number of historical timesteps consumed.
    kernel_size
        Moving-average window size for trend extraction. Default 5
        matches the LTSF-Linear/DLinear repo's default for non-ETT
        datasets.
    individual
        If True, give each (post-projection) channel its own linear weights
        (matches LTSF-Linear's ``individual=True`` mode). Since the
        feature projection already reduces to 1 channel, this only affects
        trend vs seasonal heads when both have multiple internal channels;
        kept here for API parity with the upstream class. Default False.
    """

    def __init__(
        self,
        n_features: int,
        seq_len: int,
        kernel_size: int = 5,
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

        # Feature → univariate projection.
        self.feature_proj = nn.Linear(self.n_features, 1, bias=False)
        # Trend + seasonal decomposition.
        self.decomp = MovingAverageDecomposition(kernel_size=kernel_size)
        # Separate linear heads — output dimension 1 (single forecast step,
        # acting as the scalar ranking score).
        self.trend_head = nn.Linear(self.seq_len, 1)
        self.seasonal_head = nn.Linear(self.seq_len, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F) → project features to 1-d → decompose → linear heads.
        proj = self.feature_proj(x)                # (B, T, 1)
        seasonal, trend = self.decomp(proj)        # both (B, T, 1)
        seasonal_in = seasonal.squeeze(-1)         # (B, T)
        trend_in = trend.squeeze(-1)               # (B, T)
        seasonal_out = self.seasonal_head(seasonal_in).squeeze(-1)  # (B,)
        trend_out = self.trend_head(trend_in).squeeze(-1)            # (B,)
        return seasonal_out + trend_out                              # (B,)


class NLinearRanker(nn.Module):
    """NLinear adapted for cross-sectional scalar ranking.

    Strictly faithful to the LTSF-Linear NLinear except for the
    cross-sectional output head (scalar instead of multi-step forecast).
    """

    def __init__(self, n_features: int, seq_len: int) -> None:
        super().__init__()
        if n_features < 1:
            raise ValueError(f"n_features must be ≥ 1, got {n_features}")
        if seq_len < 1:
            raise ValueError(f"seq_len must be ≥ 1, got {seq_len}")
        self.n_features = int(n_features)
        self.seq_len = int(seq_len)
        # Feature → univariate projection (same shape pipeline as DLinear).
        self.feature_proj = nn.Linear(self.n_features, 1, bias=False)
        # Single linear head over time dimension.
        self.head = nn.Linear(self.seq_len, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        proj = self.feature_proj(x).squeeze(-1)    # (B, T)
        # NLinear normalization: subtract last timestep value (per sample).
        last = proj[:, -1:].clone()                # (B, 1)
        normalized = proj - last
        out = self.head(normalized).squeeze(-1)    # (B,)
        # Add the last-value scalar back so the head learns deviations
        # rather than absolute level.
        return out + last.squeeze(-1)
