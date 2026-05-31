"""DLinear / NLinear cross-sectional ranker unit tests.

Adapter / smoke-fixture integration is in a sibling PR. This file pins:

  * model classes instantiate at expected (n_features, seq_len) pairs
  * forward pass returns (batch,) shape
  * outputs are finite under default init (no NaN / Inf)
  * deterministic given a fixed torch seed
  * MovingAverageDecomposition satisfies x = trend + seasonal exactly
  * batched + single-sample input modes both work
  * NLinearRanker's residual structure preserves the last-value identity
    at init (the head's output is small but non-zero)

These tests run without the heavy ExperimentPipeline, no MPS, no parquet
fixtures — they're pure model + numerical contract.
"""
from __future__ import annotations

import pytest
import torch

from renquant_model_linear import (
    DLinearRanker,
    MovingAverageDecomposition,
    NLinearRanker,
)


# ---- MovingAverageDecomposition ---------------------------------------


@pytest.mark.parametrize("seq_len,n_features,kernel_size", [
    (24, 8, 5),
    (60, 32, 7),
    (16, 1, 3),
    (24, 1, 1),    # degenerate kernel; trend should equal input
])
def test_decomposition_preserves_sum(seq_len: int, n_features: int, kernel_size: int) -> None:
    """x = trend + seasonal must hold exactly (up to float precision)."""
    torch.manual_seed(42)
    decomp = MovingAverageDecomposition(kernel_size=kernel_size)
    x = torch.randn(4, seq_len, n_features)
    seasonal, trend = decomp(x)
    assert seasonal.shape == x.shape
    assert trend.shape == x.shape
    recovered = seasonal + trend
    # Float precision: should match to ~1e-6 with default float32.
    assert torch.allclose(recovered, x, atol=1e-6), (
        f"decomposition not sum-preserving: max diff = "
        f"{(recovered - x).abs().max().item():.3e}"
    )


def test_decomposition_rejects_invalid_kernel_size() -> None:
    with pytest.raises(ValueError, match="kernel_size"):
        MovingAverageDecomposition(kernel_size=0)


def test_decomposition_rejects_wrong_input_rank() -> None:
    decomp = MovingAverageDecomposition(kernel_size=5)
    with pytest.raises(ValueError, match=r"\(batch, seq_len, n_features\)"):
        decomp(torch.randn(4, 24))   # 2D — missing feature axis


# ---- DLinearRanker -----------------------------------------------------


@pytest.mark.parametrize("batch,seq_len,n_features", [
    (4, 24, 8),
    (1, 16, 1),
    (32, 60, 172),    # matches PatchTST's panel feature count
])
def test_dlinear_forward_shape(batch: int, seq_len: int, n_features: int) -> None:
    """Output is exactly (batch,) — single scalar per sample."""
    torch.manual_seed(0)
    model = DLinearRanker(n_features=n_features, seq_len=seq_len)
    x = torch.randn(batch, seq_len, n_features)
    out = model(x)
    assert out.shape == (batch,), f"expected ({batch},) got {tuple(out.shape)}"
    assert torch.isfinite(out).all(), "DLinearRanker emitted non-finite values"


def test_dlinear_deterministic_with_seed() -> None:
    """Same seed + same input → byte-identical output. No noise leakage."""
    def _run() -> torch.Tensor:
        torch.manual_seed(20260531)
        m = DLinearRanker(n_features=8, seq_len=24)
        x = torch.randn(4, 24, 8)
        return m(x)
    out_a = _run()
    out_b = _run()
    assert torch.equal(out_a, out_b), "DLinearRanker non-deterministic under seed"


def test_dlinear_parameter_count_is_small() -> None:
    """DLinear's whole selling point is parameter efficiency. Pin that
    it stays small — a parameter explosion would invalidate the
    'simple baseline' framing.

    Post-PR #14 review: per-channel temporal heads (shared mode):
      trend_head (24+1) + seasonal_head (24+1) + channel_aggregator (172)
      = 25 + 25 + 172 = 222 params.
    """
    model = DLinearRanker(n_features=172, seq_len=24, individual=False)
    n_params = sum(p.numel() for p in model.parameters())
    assert 100 < n_params < 1000, (
        f"DLinearRanker(individual=False) has {n_params} params; "
        f"expected ~222 for (n_features=172, seq_len=24). A parameter "
        f"explosion would break the 'tiny baseline vs PatchTST' framing."
    )


def test_dlinear_individual_true_uses_per_channel_weights() -> None:
    """PR #14 review M2: individual=True must actually change the model,
    not just be accepted silently. Per-channel weights → ~n_features × seq_len
    extra params + provably different output for the same input + seed."""
    torch.manual_seed(0)
    shared = DLinearRanker(n_features=8, seq_len=16, individual=False)
    torch.manual_seed(0)
    indiv = DLinearRanker(n_features=8, seq_len=16, individual=True)
    n_shared = sum(p.numel() for p in shared.parameters())
    n_indiv = sum(p.numel() for p in indiv.parameters())
    assert n_indiv > n_shared * 5, (
        f"individual=True should have substantially more params; "
        f"shared={n_shared}, individual={n_indiv} — ratio < 5x suggests "
        f"per-channel weights aren't actually allocated."
    )
    # Forward outputs must differ (different params + same init → different output)
    torch.manual_seed(42)
    x = torch.randn(4, 16, 8)
    out_shared = shared(x)
    out_indiv = indiv(x)
    assert not torch.allclose(out_shared, out_indiv, atol=1e-4), (
        "individual=True produces identical output to individual=False — "
        "the flag isn't materially changing the model."
    )


def test_dlinear_individual_true_param_count_scales() -> None:
    """For n_features=172, seq_len=24:
    individual=True ≈ 4,300 (trend) + 4,300 (seasonal) + 172 (agg) = ~8,772."""
    model = DLinearRanker(n_features=172, seq_len=24, individual=True)
    n_params = sum(p.numel() for p in model.parameters())
    assert 5000 < n_params < 15000, (
        f"DLinearRanker(individual=True) has {n_params} params; "
        f"expected ~8,772 for (172, 24). Out-of-range suggests architecture "
        f"changed unexpectedly."
    )


def test_dlinear_backward_pass_produces_gradients() -> None:
    """Training plumbing sanity: a synthetic loss should produce non-zero
    gradients on every parameter."""
    torch.manual_seed(0)
    model = DLinearRanker(n_features=8, seq_len=24)
    x = torch.randn(4, 24, 8, requires_grad=False)
    target = torch.randn(4)
    out = model(x)
    loss = ((out - target) ** 2).mean()
    loss.backward()
    for name, p in model.named_parameters():
        assert p.grad is not None, f"no gradient on {name}"
        assert p.grad.abs().sum() > 0, f"zero gradient on {name}"


def test_dlinear_individual_flag_accepted() -> None:
    """API parity with upstream LTSF-Linear's individual=True mode.
    Default False, but instantiable both ways. (Behavior pinned in
    sibling tests test_dlinear_individual_true_uses_per_channel_weights +
    test_dlinear_individual_true_param_count_scales.)"""
    DLinearRanker(n_features=8, seq_len=24, individual=False)
    DLinearRanker(n_features=8, seq_len=24, individual=True)


def test_dlinear_default_kernel_size_matches_upstream() -> None:
    """PR #14 review follow-up: default kernel_size MUST match the pinned
    upstream LTSF-Linear/DLinear value of 25 (models/DLinear.py line 47
    at SHA 0c11366). A different default would change the
    trend/seasonal split → not the same DLinear hypothesis the paper
    measures, so a poor result wouldn't actually falsify upstream DLinear."""
    model = DLinearRanker(n_features=8, seq_len=32)
    assert model.decomp.kernel_size == 25, (
        f"DLinearRanker default kernel_size = {model.decomp.kernel_size}; "
        f"expected 25 to match pinned upstream (LTSF-Linear DLinear.py:47 "
        f"at 0c11366). If this changes intentionally, update "
        f"docs/dlinear_source_note.md's deviation table + this assertion."
    )


@pytest.mark.parametrize("bad_n,bad_t", [(0, 24), (8, 0), (-1, 24)])
def test_dlinear_rejects_bad_dimensions(bad_n: int, bad_t: int) -> None:
    with pytest.raises(ValueError):
        DLinearRanker(n_features=bad_n, seq_len=bad_t)


# ---- NLinearRanker -----------------------------------------------------


@pytest.mark.parametrize("batch,seq_len,n_features", [
    (4, 24, 8),
    (1, 16, 1),
    (16, 60, 32),
])
def test_nlinear_forward_shape(batch: int, seq_len: int, n_features: int) -> None:
    torch.manual_seed(0)
    model = NLinearRanker(n_features=n_features, seq_len=seq_len)
    x = torch.randn(batch, seq_len, n_features)
    out = model(x)
    assert out.shape == (batch,)
    assert torch.isfinite(out).all()


def test_nlinear_deterministic_with_seed() -> None:
    def _run() -> torch.Tensor:
        torch.manual_seed(20260531)
        m = NLinearRanker(n_features=8, seq_len=24)
        x = torch.randn(4, 24, 8)
        return m(x)
    assert torch.equal(_run(), _run())


def test_nlinear_residual_structure_is_meaningful() -> None:
    """NLinear's signature design: subtract last-value (per channel),
    head learns deviations, add last-value back. With near-zero head
    weights, output should equal the aggregator applied to the per-
    channel last values — confirms the residual structure is wired
    correctly."""
    torch.manual_seed(0)
    model = NLinearRanker(n_features=8, seq_len=24, individual=False)
    # Zero out head weights so per-channel temporal contribution is 0
    # and the output equals the channel-aggregated last values.
    with torch.no_grad():
        model.head.weight.zero_()
        model.head.bias.zero_()
    x = torch.randn(4, 24, 8)
    out = model(x)
    # Expected: aggregator(last_values_per_channel)
    expected = model.channel_aggregator(x[:, -1, :]).squeeze(-1)
    assert torch.allclose(out, expected, atol=1e-6), (
        f"NLinear with zeroed temporal head should output ≈ aggregator("
        f"last values); got max diff {(out - expected).abs().max().item():.3e}"
    )


def test_nlinear_parameter_count_is_small() -> None:
    """Post-PR #14 review: per-channel restructure:
      head (24+1) + channel_aggregator (172) = 25 + 172 = 197 params (shared).
    """
    model = NLinearRanker(n_features=172, seq_len=24, individual=False)
    n_params = sum(p.numel() for p in model.parameters())
    assert 100 < n_params < 500, (
        f"NLinearRanker(individual=False) has {n_params} params; expected ~197"
    )


def test_nlinear_individual_true_param_count_scales() -> None:
    """individual=True ≈ 25 × 172 + 172 = ~4,472."""
    model = NLinearRanker(n_features=172, seq_len=24, individual=True)
    n_params = sum(p.numel() for p in model.parameters())
    assert 3000 < n_params < 8000, (
        f"NLinearRanker(individual=True) has {n_params} params; expected ~4,472"
    )


@pytest.mark.parametrize("bad_n,bad_t", [(0, 24), (8, 0)])
def test_nlinear_rejects_bad_dimensions(bad_n: int, bad_t: int) -> None:
    with pytest.raises(ValueError):
        NLinearRanker(n_features=bad_n, seq_len=bad_t)


# ---- Package import boundary ------------------------------------------


def test_public_api_exposes_only_documented_symbols() -> None:
    import renquant_model_linear as pkg
    # Trainer adapter symbols come from the sibling PR (linear trainer).
    # Model + decomp symbols are the focus of this PR.
    expected_model_symbols = {
        "DLinearRanker",
        "MovingAverageDecomposition",
        "NLinearRanker",
    }
    assert expected_model_symbols <= set(pkg.__all__), (
        f"missing model symbols from public API: "
        f"{expected_model_symbols - set(pkg.__all__)}"
    )


def test_falsification_framing_pins_param_ratio() -> None:
    """Document the param ratio that justifies 'linear vs PatchTST'
    falsification framing. PatchTST has ~70k params; DLinearRanker should
    be < 1% of that. If this ratio shrinks, the 'simple baseline' claim
    needs re-examining."""
    dlinear = DLinearRanker(n_features=172, seq_len=24)
    nlinear = NLinearRanker(n_features=172, seq_len=24)
    patchtst_typical_params = 70_000
    d_ratio = sum(p.numel() for p in dlinear.parameters()) / patchtst_typical_params
    n_ratio = sum(p.numel() for p in nlinear.parameters()) / patchtst_typical_params
    assert d_ratio < 0.01, (
        f"DLinearRanker / PatchTST param ratio is {d_ratio:.4f}; "
        f"expected < 0.01. Baseline is no longer 'simple enough' to "
        f"falsify the Transformer's complexity premium."
    )
    assert n_ratio < 0.01
