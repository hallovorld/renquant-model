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

from datetime import datetime, timezone
from typing import Any

import pytest
import torch

from renquant_common import ArtifactManifest, OOSEvidence
from renquant_common.contracts import Scorer
from renquant_model_patchtst.scorer import PatchTstStatefulScorer, _resolve_path


class _MockModel(torch.nn.Module):
    """Minimal stand-in for HFPatchTSTRanker — returns a per-ticker mean score."""

    def to(self, *a: Any, **k: Any) -> "_MockModel":  # noqa: D401
        return self

    def eval(self) -> "_MockModel":  # noqa: D401
        return self

    def forward(self, past_values: torch.Tensor, **_: Any) -> dict[str, torch.Tensor]:
        # past_values: (N_tickers, seq_len, n_features) → mean over time+feature
        return {"score": past_values.mean(dim=(1, 2))}


def _make(
    seq_len: int = 3,
    feats: list[str] | None = None,
    *,
    use_csranknorm_preprocessing: bool = False,
) -> PatchTstStatefulScorer:
    return PatchTstStatefulScorer(
        _MockModel(),
        feats or ["a", "b"],
        seq_len=seq_len,
        use_csranknorm_preprocessing=use_csranknorm_preprocessing,
    )


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


def test_resolve_path_accepts_standard_artifact_manifest_uri(tmp_path) -> None:
    path = tmp_path / "hf_patchtst.pt"
    path.write_bytes(b"checkpoint")
    manifest = ArtifactManifest(
        kind="hf_patchtst",
        family="patchtst",
        artifact_uri=f"file://{path}",
        feature_fingerprint="sha256:feature",
        config_fingerprint="sha256:config",
        training_data_fingerprint="sha256:data",
        trained_at=datetime.now(timezone.utc),
        lookahead_days=60,
        oos_evidence=OOSEvidence(
            mean_ic=0.01,
            std_ic=0.0,
            per_fold_ic=(),
            cv_method="purged-walk-forward",
            embargo_days=60,
        ),
        owner_repo="renquant-model",
    )

    assert _resolve_path(manifest) == path


def test_resolve_path_accepts_legacy_uri_dict(tmp_path) -> None:
    path = tmp_path / "legacy.pt"
    path.write_bytes(b"checkpoint")

    assert _resolve_path({"uri": f"file://{path}"}) == path


def test_predict_rows_applies_csranknorm_when_checkpoint_declares_it() -> None:
    s = _make(seq_len=1, feats=["a"], use_csranknorm_preprocessing=True)

    out = s.predict_rows({"LOW": {"a": 10.0}, "HIGH": {"a": 20.0}})

    assert out["LOW"] == pytest.approx(0.0)
    assert out["HIGH"] == pytest.approx(0.5)


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


# ─── bootstrap_from_history (D5) ───────────────────────────────────────────

def test_bootstrap_from_history_warms_buffer_to_seq_len_minus_one() -> None:
    """After bootstrap, next predict_rows call produces a score immediately."""
    import pandas as pd
    s = _make(seq_len=5, feats=["a", "b"])
    history = pd.DataFrame([
        {"date": f"2024-01-{i:02d}", "ticker": "AAPL", "a": 0.1 * i, "b": 0.2 * i}
        for i in range(1, 11)
    ])
    state = s.bootstrap_from_history(history)
    # Warmed with seq_len - 1 = 4 rows (the most recent)
    assert state["AAPL"] == 4
    assert s.buffer_state()["AAPL"] == 4
    # Next predict_rows call produces a score (cold-start eliminated)
    out = s.predict_rows({"AAPL": {"a": 1.1, "b": 2.2}})
    assert "AAPL" in out


def test_bootstrap_with_insufficient_history_stays_cold() -> None:
    """A ticker with fewer than seq_len - 1 history rows remains cold."""
    import pandas as pd
    s = _make(seq_len=5, feats=["a"])
    history = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "AAPL", "a": 1.0},
        {"date": "2024-01-02", "ticker": "AAPL", "a": 2.0},
    ])
    state = s.bootstrap_from_history(history)
    assert state["AAPL"] == 2
    # Next predict_rows: buffer goes 2 -> 3, still not seq_len (5)
    out = s.predict_rows({"AAPL": {"a": 3.0}})
    assert "AAPL" not in out


def test_bootstrap_only_warms_tickers_present_in_history() -> None:
    import pandas as pd
    s = _make(seq_len=3, feats=["a"])
    history = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "AAPL", "a": 1.0},
        {"date": "2024-01-02", "ticker": "AAPL", "a": 2.0},
    ])
    state = s.bootstrap_from_history(history)
    assert set(state) == {"AAPL"}
    # MSFT was absent from history → no buffer entry
    assert "MSFT" not in s.buffer_state()


def test_bootstrap_uses_most_recent_rows() -> None:
    """Out-of-order history rows must be sorted by date before warming."""
    import pandas as pd
    s = _make(seq_len=3, feats=["a"])
    history = pd.DataFrame([
        {"date": "2024-01-03", "ticker": "AAPL", "a": 30.0},
        {"date": "2024-01-01", "ticker": "AAPL", "a": 10.0},  # oldest, should be dropped
        {"date": "2024-01-02", "ticker": "AAPL", "a": 20.0},
        {"date": "2024-01-04", "ticker": "AAPL", "a": 40.0},  # newest
    ])
    s.bootstrap_from_history(history)
    # Buffer is seq_len - 1 = 2 rows; should contain the 2 NEWEST
    buf_list = list(s._buffers["AAPL"])
    assert buf_list[-1][0] == pytest.approx(40.0)
    assert buf_list[-2][0] == pytest.approx(30.0)


def test_bootstrap_clears_existing_buffer() -> None:
    """Pre-existing predict_rows state is overwritten by bootstrap."""
    import pandas as pd
    s = _make(seq_len=3, feats=["a"])
    s.predict_rows({"AAPL": {"a": 999.0}})  # noise: 1 row in buffer
    history = pd.DataFrame([
        {"date": "2024-01-01", "ticker": "AAPL", "a": 1.0},
        {"date": "2024-01-02", "ticker": "AAPL", "a": 2.0},
    ])
    s.bootstrap_from_history(history)
    buf_list = list(s._buffers["AAPL"])
    assert len(buf_list) == 2
    # Should NOT contain 999.0 (cleared first)
    assert all(row[0] != pytest.approx(999.0) for row in buf_list)
