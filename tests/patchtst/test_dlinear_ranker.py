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
    'simple baseline' framing."""
    model = DLinearRanker(n_features=172, seq_len=24)
    n_params = sum(p.numel() for p in model.parameters())
    # Expected: feature_proj (172) + trend_head (24+1) + seasonal_head (24+1)
    # = 172 + 25 + 25 = 222 params. Pin under 1k to catch refactor explosions.
    assert n_params < 1000, (
        f"DLinearRanker has {n_params} params; expected ~222 for "
        f"(n_features=172, seq_len=24). A parameter explosion would "
        f"break the 'tiny baseline vs PatchTST' framing."
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
    Default False, but instantiable both ways."""
    DLinearRanker(n_features=8, seq_len=24, individual=False)
    DLinearRanker(n_features=8, seq_len=24, individual=True)


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
    """NLinear's signature design: subtract last-value, head learns
    deviations, add last-value back. With near-zero head weights, output
    should be close to the projected last value of the input — confirms
    the residual structure is wired correctly."""
    torch.manual_seed(0)
    model = NLinearRanker(n_features=8, seq_len=24)
    # Zero out head weights so output ≈ residual baseline.
    with torch.no_grad():
        model.head.weight.zero_()
        model.head.bias.zero_()
    x = torch.randn(4, 24, 8)
    out = model(x)
    expected_last = model.feature_proj(x[:, -1, :]).squeeze(-1)
    assert torch.allclose(out, expected_last, atol=1e-6), (
        f"NLinear with zeroed head should output ≈ projected last value; "
        f"got max diff {(out - expected_last).abs().max().item():.3e}"
    )


def test_nlinear_parameter_count_is_small() -> None:
    model = NLinearRanker(n_features=172, seq_len=24)
    n_params = sum(p.numel() for p in model.parameters())
    # Expected: feature_proj (172) + head (24+1) = 197 params.
    assert n_params < 500, f"NLinearRanker has {n_params} params; expected ~197"


@pytest.mark.parametrize("bad_n,bad_t", [(0, 24), (8, 0)])
def test_nlinear_rejects_bad_dimensions(bad_n: int, bad_t: int) -> None:
    with pytest.raises(ValueError):
        NLinearRanker(n_features=bad_n, seq_len=bad_t)


# ---- Package import boundary ------------------------------------------


def test_public_api_exposes_only_documented_symbols() -> None:
    import renquant_model_linear as pkg
    assert set(pkg.__all__) == {
        "DLinearRanker",
        "MovingAverageDecomposition",
        "NLinearRanker",
    }


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
