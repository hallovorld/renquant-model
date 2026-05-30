"""Structural tests for the stateful PatchTST scorer.

The scorer is the wiring that lets the runtime panel-scoring pipeline ever load
PatchTST — there was no PatchTST scorer registered before this. These tests pin:

* Scorer Protocol compliance (so ``load_scorer`` will accept it),
* the stateful per-ticker rolling buffer (cold start → warm at seq_len),
* per-ticker independence (one ticker's warmup doesn't bleed into another).

Behavioural correctness against the actual trained model is covered by the
research harness's pooled-IC + the val-preds → dollar-alpha backtest; here we
only verify the scorer plumbing.
"""
from __future__ import annotations

from typing import Any

import torch

from renquant_common.contracts import Scorer
from renquant_model_patchtst.scorer import PatchTstStatefulScorer


class _MockModel(torch.nn.Module):
    """Minimal stand-in for HFPatchTSTRanker — returns a per-ticker mean score."""

    def to(self, *a: Any, **k: Any) -> "_MockModel":  # noqa: D401
        return self

    def eval(self) -> "_MockModel":  # noqa: D401
        return self

    def forward(self, past_values: torch.Tensor, **_: Any) -> dict[str, torch.Tensor]:
        # past_values: (N_tickers, seq_len, n_features) → mean over time+feature
        return {"score": past_values.mean(dim=(1, 2))}


def _make(seq_len: int = 3, feats: list[str] | None = None) -> PatchTstStatefulScorer:
    return PatchTstStatefulScorer(_MockModel(), feats or ["a", "b"], seq_len=seq_len)


def test_protocol_compliance() -> None:
    s = _make()
    assert isinstance(s, Scorer)
    fp = s.feature_fingerprint()
    assert isinstance(fp, str) and fp.startswith("sha256:")
    assert s.predict_variance({"AAPL": {"a": 1.0, "b": 2.0}}) is None


def test_cold_start_omits_until_seq_len_rows_seen() -> None:
    s = _make(seq_len=3)
    # First two calls per ticker: buffer not yet full → no score returned
    assert s.predict_rows({"AAPL": {"a": 1.0, "b": 2.0}}) == {}
    assert s.predict_rows({"AAPL": {"a": 3.0, "b": 4.0}}) == {}
    # Third call: buffer is full → score emitted
    out = s.predict_rows({"AAPL": {"a": 5.0, "b": 6.0}})
    assert set(out) == {"AAPL"}
    # Fourth call: still warm
    assert "AAPL" in s.predict_rows({"AAPL": {"a": 7.0, "b": 8.0}})


def test_per_ticker_buffer_independence() -> None:
    s = _make(seq_len=2, feats=["a"])
    s.predict_rows({"AAPL": {"a": 1.0}})  # AAPL buffer: 1
    out = s.predict_rows({"AAPL": {"a": 2.0}, "MSFT": {"a": 99.0}})
    # AAPL warmed (2 rows), MSFT still cold (1 row)
    assert "AAPL" in out and "MSFT" not in out


def test_buffer_state_diagnostic() -> None:
    s = _make(seq_len=4, feats=["a"])
    s.predict_rows({"AAPL": {"a": 1.0}})
    s.predict_rows({"AAPL": {"a": 2.0}, "MSFT": {"a": 5.0}})
    state = s.buffer_state()
    assert state == {"AAPL": 2, "MSFT": 1}


def test_feature_fingerprint_changes_with_seq_len() -> None:
    a = _make(seq_len=8, feats=["x", "y"]).feature_fingerprint()
    b = _make(seq_len=16, feats=["x", "y"]).feature_fingerprint()
    assert a != b


def test_requires_history_advertised() -> None:
    # The WF gate's _score_manifest_sanity dispatches on this attribute.
    assert PatchTstStatefulScorer.requires_history is True


def test_score_with_history_returns_one_score_per_ready_ticker() -> None:
    import pandas as pd
    s = _make(seq_len=3, feats=["a", "b"])
    # AAPL has 3 days of history (== seq_len → ready); MSFT only has 2 (cold)
    history = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "AAPL", "a": 0.1, "b": 0.2},
        {"date": "2024-01-02", "ticker": "AAPL", "a": 0.3, "b": 0.4},
        {"date": "2024-01-03", "ticker": "AAPL", "a": 0.5, "b": 0.6},
        {"date": "2024-01-02", "ticker": "MSFT", "a": 1.1, "b": 1.2},
        {"date": "2024-01-03", "ticker": "MSFT", "a": 1.3, "b": 1.4},
    ])
    out = s.score_with_history(history, ["AAPL", "MSFT"])
    assert set(out) == {"AAPL"}
    assert isinstance(out["AAPL"], float)


def test_score_with_history_independent_of_predict_rows_buffer() -> None:
    """The history path must not consume / mutate the rolling buffer state."""
    import pandas as pd
    s = _make(seq_len=2, feats=["a"])
    s.predict_rows({"AAPL": {"a": 1.0}})  # warms predict_rows buffer to 1
    history = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "AAPL", "a": 5.0},
        {"date": "2024-01-02", "ticker": "AAPL", "a": 6.0},
    ])
    s.score_with_history(history, ["AAPL"])
    # buffer should still be at 1 (history call is stateless w.r.t. buffer)
    assert s.buffer_state()["AAPL"] == 1
