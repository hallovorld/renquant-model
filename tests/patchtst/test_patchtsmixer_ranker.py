"""HFPatchTSMixerRanker contract tests.

Pins the model's shape/numerics contract so the research harness can use
it as a drop-in P1 baseline alongside DLinear/NLinear. No training loop
here — adapter/trainer wiring is sibling work.
"""
from __future__ import annotations

import pytest
import torch

from renquant_model_patchtst.patchtsmixer_ranker import (
    HFPatchTSMixerRanker,
    build_default_config,
)


# ---- Config construction -------------------------------------------------


def test_build_default_config_rejects_short_seq_len() -> None:
    """seq_len < patch_length must fail at config time, not at forward."""
    with pytest.raises(ValueError, match="seq_len"):
        build_default_config(seq_len=4, n_channels=8, patch_length=8)


def test_build_default_config_produces_valid_config() -> None:
    cfg = build_default_config(seq_len=24, n_channels=8)
    assert cfg.context_length == 24
    assert cfg.num_input_channels == 8
    assert cfg.prediction_length == 1
    assert cfg.patch_length == 8
    assert cfg.d_model == 16


# ---- Forward / shape contract --------------------------------------------


@pytest.mark.parametrize("batch,seq_len,n_channels", [
    (4, 24, 8),
    (1, 24, 1),
    (16, 32, 16),
])
def test_forward_shape_is_scalar_per_sample(
    batch: int, seq_len: int, n_channels: int,
) -> None:
    """Output is exactly (batch,) — single scalar per sample, matching
    HFPatchTSTRanker's contract so the two are A/B-swappable."""
    cfg = build_default_config(seq_len=seq_len, n_channels=n_channels)
    model = HFPatchTSMixerRanker(cfg)
    x = torch.randn(batch, seq_len, n_channels)
    out = model(past_values=x)
    assert isinstance(out, dict)
    assert "score" in out
    assert out["score"].shape == (batch,), (
        f"expected score shape ({batch},), got {tuple(out['score'].shape)}"
    )
    assert torch.isfinite(out["score"]).all()


def test_forward_accepts_harness_kwargs_silently() -> None:
    """The harness passes ``labels``, ``regime_context``, ``dates`` as
    keyword args. PatchTSMixer baseline ignores these (no FiLM, no NLL
    head) but must accept them without error so the same trial_argv works
    across model families."""
    cfg = build_default_config(seq_len=24, n_channels=4)
    model = HFPatchTSMixerRanker(cfg)
    x = torch.randn(2, 24, 4)
    out = model(
        past_values=x,
        labels=torch.zeros(2),
        regime_context=torch.zeros(2, 4),
        dates=torch.zeros(2),
    )
    assert out["score"].shape == (2,)


# ---- Backward + determinism ----------------------------------------------


def test_backward_pass_produces_gradients() -> None:
    cfg = build_default_config(seq_len=24, n_channels=8)
    model = HFPatchTSMixerRanker(cfg)
    x = torch.randn(4, 24, 8)
    target = torch.randn(4)
    out = model(past_values=x)
    loss = ((out["score"] - target) ** 2).mean()
    loss.backward()
    has_grad = sum(1 for p in model.parameters() if p.grad is not None and p.grad.abs().sum() > 0)
    n_params_with_grad_capable = sum(1 for p in model.parameters() if p.requires_grad)
    assert has_grad >= 0.5 * n_params_with_grad_capable, (
        f"only {has_grad}/{n_params_with_grad_capable} params got gradients — "
        f"likely a disconnected component in the model graph"
    )


def test_deterministic_with_seed() -> None:
    """Same seed + same input → byte-identical output."""
    def _run() -> torch.Tensor:
        torch.manual_seed(20260531)
        cfg = build_default_config(seq_len=24, n_channels=8)
        m = HFPatchTSMixerRanker(cfg)
        x = torch.randn(4, 24, 8)
        return m(past_values=x)["score"]
    out_a = _run()
    out_b = _run()
    assert torch.equal(out_a, out_b), "PatchTSMixer ranker non-deterministic"


# ---- Parameter count + falsification framing -----------------------------


def test_parameter_count_is_comparable_to_patchtst() -> None:
    """For falsification framing, PatchTSMixer should be roughly the same
    order of magnitude as PatchTST so the comparison isn't trivially
    biased by capacity. Default config (d_model=16, num_layers=2) on
    seq_len=24, n_channels=8 produces a tiny model — pin under 100k."""
    cfg = build_default_config(seq_len=24, n_channels=8)
    model = HFPatchTSMixerRanker(cfg)
    n_params = sum(p.numel() for p in model.parameters())
    assert n_params < 100_000, (
        f"HFPatchTSMixerRanker has {n_params} params; expected < 100k "
        f"with default tiny config. PatchTST typical ≈ 70k for comparable "
        f"input shape."
    )


def test_patchtsmixer_output_differs_from_patchtst() -> None:
    """Sanity: a PatchTSMixer ranker should produce different scores from
    a PatchTST ranker on the same input — confirms it's actually a
    different model, not silently calling into PatchTST."""
    from renquant_model_patchtst.hf_trainer import HFPatchTSTRanker
    from transformers import PatchTSTConfig

    torch.manual_seed(0)
    mixer_cfg = build_default_config(seq_len=24, n_channels=8)
    mixer = HFPatchTSMixerRanker(mixer_cfg)

    torch.manual_seed(0)
    patchtst_cfg = PatchTSTConfig(
        context_length=24, prediction_length=1,
        num_input_channels=8, patch_length=8, patch_stride=8,
        d_model=16, num_attention_heads=2,
        num_hidden_layers=2,
    )
    patchtst = HFPatchTSTRanker(
        patchtst_cfg,
        use_distributional_head=False,
        use_film_regime=False,
        use_cross_stock_attn=False,
    )

    x = torch.randn(4, 24, 8)
    mixer_out = mixer(past_values=x)["score"]
    patchtst_out = patchtst(past_values=x)["score"]
    assert not torch.allclose(mixer_out, patchtst_out, atol=1e-3), (
        "PatchTSMixer and PatchTST produced identical scores — one of the "
        "two model classes is silently wrong."
    )
