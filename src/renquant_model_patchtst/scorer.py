"""PatchTST runtime scorer — stateful per-ticker feature buffer over the Scorer Protocol.

Wires the sequence model into the point-in-time ``predict_rows`` interface used by
``renquant_pipeline.panel_scoring``. Each call to ``predict_rows`` appends the row to
that ticker's rolling ``seq_len`` buffer; once a buffer fills, the next call produces a
score; cold tickers (< ``seq_len`` rows seen) are omitted from the result — consumers
already treat missing scores as "no signal" and skip.

Registered via the ``renquant_common.scorers`` entry-point group as
``patchtst_panel = "renquant_model_patchtst.scorer:load"``. The runtime resolves it
through :func:`renquant_common.load_scorer` against an ``ArtifactManifest`` whose
``kind`` is ``"patchtst_panel"``.

V0 design choices:
- Cold start by default. The buffer is empty at load time; the first ``seq_len - 1``
  calls per ticker yield no score. The daily cron warms naturally over the first
  ``seq_len`` bars; a richer ``bootstrap_from_panel`` hook is sketched as a follow-up.
- No variance head exposed yet (``predict_variance`` returns ``None``). The trained
  ``mu`` / ``sigma`` head exists; surface once σ-aware Kelly is wired per-regime.
- Inference batches ALL tickers whose buffers are warm on a single ``model(...)`` call —
  matches training-time per-day batch geometry so ``cross-stock-attn`` behaves as
  trained.
"""
from __future__ import annotations

import hashlib
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import torch


class PatchTstStatefulScorer:
    """Implements ``renquant_common.contracts.Scorer`` with a rolling per-ticker buffer."""

    #: Signals to ``run_wf_gate._score_manifest_sanity`` that this scorer needs
    #: panel history (last ``seq_len`` trading days per ticker) to score a target
    #: date, rather than a single point-in-time row.
    requires_history: bool = True

    feature_cols: list[str]

    def __init__(
        self,
        model: Any,
        feature_cols: list[str],
        seq_len: int,
        *,
        device: str = "cpu",
        transform_version: str = "v1",
    ) -> None:
        self.model = model.to(device).eval()
        self.feature_cols = list(feature_cols)
        self.seq_len = int(seq_len)
        self.device = device
        self._transform_version = transform_version
        self._buffers: dict[str, deque[np.ndarray]] = {}

    # ─── Scorer Protocol ────────────────────────────────────────────────────

    def feature_fingerprint(self) -> str:
        """Stable hash of ``(feature_cols, transform_version, seq_len)``."""
        payload = "|".join(self.feature_cols) + f"||{self._transform_version}||seq={self.seq_len}"
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    @torch.no_grad()
    def predict_rows(self, rows: dict[str, dict[str, float]]) -> dict[str, float]:
        ready_tkrs: list[str] = []
        ready_windows: list[np.ndarray] = []
        for tkr, feats in rows.items():
            vec = np.fromiter(
                (float(feats.get(c, 0.0)) for c in self.feature_cols),
                dtype=np.float32, count=len(self.feature_cols),
            )
            buf = self._buffers.setdefault(tkr, deque(maxlen=self.seq_len))
            buf.append(vec)
            if len(buf) == self.seq_len:
                ready_tkrs.append(tkr)
                ready_windows.append(np.stack(buf))
        if not ready_tkrs:
            return {}
        x = torch.from_numpy(np.stack(ready_windows)).to(self.device)
        outputs = self.model(past_values=x)
        scores = outputs["score"].detach().cpu().numpy()
        return {t: float(s) for t, s in zip(ready_tkrs, scores)}

    def predict_variance(
        self, rows: dict[str, dict[str, float]]
    ) -> dict[str, float] | None:
        # V0: σ-head exists but is not surfaced until per-regime σ-aware Kelly is wired.
        return None

    # ─── History-aware scoring (consumed by run_wf_gate sanity battery) ────

    @torch.no_grad()
    def score_with_history(self, history: Any, tickers: list[str]) -> dict[str, float]:
        """Score the latest trading day for each ticker, using the prior
        ``seq_len`` rows of ``history`` as the model's input window.

        ``history`` is a pandas DataFrame with columns ``date``, ``ticker`` and
        every name in ``self.feature_cols``. Tickers with fewer than ``seq_len``
        rows are omitted (cold-start) — the caller treats a missing score as
        "no signal" (matches the Protocol's ``predict_rows`` contract).

        Independent of the rolling buffer that ``predict_rows`` maintains: each
        call to ``score_with_history`` is stateless w.r.t. previous calls, which
        is what the manifest sanity loop needs (per-date / per-ticker scoring
        against a strict cutoff window).
        """
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("score_with_history requires pandas") from exc

        out: dict[str, float] = {}
        # Group history by ticker once
        groups = history.groupby("ticker", sort=False)
        windows: list[np.ndarray] = []
        ready_tkrs: list[str] = []
        for tkr in tickers:
            try:
                rows = groups.get_group(tkr)
            except KeyError:
                continue
            rows = rows.sort_values("date")
            if len(rows) < self.seq_len:
                continue
            # Take the most recent seq_len rows; pull feature_cols in scorer order
            window = (
                rows[self.feature_cols]
                .tail(self.seq_len)
                .astype(np.float32)
                .fillna(0.0)
                .to_numpy()
            )
            if window.shape != (self.seq_len, len(self.feature_cols)):
                continue
            windows.append(window)
            ready_tkrs.append(tkr)
        if not ready_tkrs:
            return out
        x = torch.from_numpy(np.stack(windows)).to(self.device)
        outputs = self.model(past_values=x)
        scores = outputs["score"].detach().cpu().numpy()
        return {t: float(s) for t, s in zip(ready_tkrs, scores)}

    # ─── Buffer bootstrap (callers warm explicitly post-load) ──────────────

    def bootstrap_from_history(self, history: Any) -> dict[str, int]:
        """Pre-warm per-ticker buffers from historical feature rows.

        Without this, the daily cron loses ``seq_len - 1`` days of signal: the
        first ``predict_rows`` call per ticker only fills slot 1 of the buffer
        so no score is emitted. By pre-loading up to ``seq_len - 1`` historical
        rows per ticker, the very next ``predict_rows`` call appends the
        current bar and immediately produces a score.

        Parameters
        ----------
        history : pandas.DataFrame
            Must have columns ``date``, ``ticker``, plus every name in
            ``self.feature_cols``. Tickers absent from the frame are left
            cold; tickers with fewer than ``seq_len - 1`` rows are warmed with
            whatever is available (still cold until enough days accumulate).

        Returns
        -------
        dict[str, int]
            ``{ticker: rows_in_buffer_after_warm}`` for the daily run trace.
            A ticker is "ready" when ``len(buf) >= seq_len - 1``; that means
            the next ``predict_rows`` for it produces a score.
        """
        from collections import deque  # noqa: PLC0415
        target_len = max(0, self.seq_len - 1)
        state: dict[str, int] = {}
        if target_len == 0:
            return state
        for tkr, rows in history.groupby("ticker", sort=False):
            rows = rows.sort_values("date")
            warm = (
                rows[self.feature_cols]
                .tail(target_len)
                .astype(np.float32)
                .fillna(0.0)
                .to_numpy()
            )
            buf = self._buffers.setdefault(tkr, deque(maxlen=self.seq_len))
            buf.clear()
            for row in warm:
                buf.append(row)
            state[tkr] = len(buf)
        return state

    # ─── Diagnostics (not part of Protocol) ─────────────────────────────────

    def buffer_state(self) -> dict[str, int]:
        """How many rows each ticker has seen — useful for the daily run trace."""
        return {t: len(b) for t, b in self._buffers.items()}


# ─── Entry point ────────────────────────────────────────────────────────────

def load(manifest: Any) -> PatchTstStatefulScorer:
    """Build the scorer from an artifact manifest.

    Reads the ``.pt`` checkpoint pointed to by ``manifest.local_artifact_path`` (with
    ``manifest.uri`` as the canonical fallback when ``file://`` scheme), rebuilds the
    model from the embedded ``config_dict`` and feature-engineering flags, loads the
    state dict, and returns a stateful scorer. The PyTorch checkpoint format is
    produced by ``PersistModelTask`` (see ``sequence_training.PersistModelTask``).
    """
    path = _resolve_path(manifest)
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    # Lazy import — avoids loading torch/transformers when the scorer is only enumerated.
    from .hf_trainer import HFPatchTSTRanker  # noqa: PLC0415
    from transformers import PatchTSTConfig  # noqa: PLC0415
    cfg = PatchTSTConfig(**ckpt["config_dict"])
    model = HFPatchTSTRanker(
        cfg,
        use_distributional_head=bool(ckpt.get("uses_distributional_head", False)),
        use_film_regime=bool(ckpt.get("uses_film_regime", False)),
        use_cross_stock_attn=bool(ckpt.get("uses_cross_stock_attn", False)),
    )
    model.load_state_dict(ckpt["state_dict"])
    return PatchTstStatefulScorer(
        model,
        feature_cols=list(ckpt["feature_cols"]),
        seq_len=int(ckpt["seq_len"]),
    )


def _resolve_path(manifest: Any) -> Path:
    local = getattr(manifest, "local_artifact_path", None)
    if local:
        return Path(local)
    uri = getattr(manifest, "uri", None) or ""
    if uri.startswith("file://"):
        return Path(uri[len("file://"):])
    raise ValueError(
        f"PatchTST scorer cannot resolve artifact: local_artifact_path missing and "
        f"uri scheme not supported ({uri!r})"
    )
