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
from urllib.parse import unquote, urlparse

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
        use_csranknorm_preprocessing: bool = False,
    ) -> None:
        self.model = model.to(device).eval()
        self.feature_cols = list(feature_cols)
        self.seq_len = int(seq_len)
        self.device = device
        self._transform_version = transform_version
        self._use_csranknorm_preprocessing = bool(use_csranknorm_preprocessing)
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
        current_tkrs, current_vectors = self._row_vectors(rows)
        for tkr, vec in zip(current_tkrs, current_vectors):
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
        history = self._prepare_history(history)

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
        history = self._prepare_history(history)

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

    def _row_vectors(self, rows: dict[str, dict[str, float]]) -> tuple[list[str], np.ndarray]:
        tickers = [str(tkr) for tkr in rows]
        if not tickers:
            return [], np.empty((0, len(self.feature_cols)), dtype=np.float32)
        values = np.asarray(
            [
                [float(feats.get(col, 0.0)) for col in self.feature_cols]
                for feats in rows.values()
            ],
            dtype=np.float32,
        )
        if self._use_csranknorm_preprocessing:
            try:
                import pandas as pd  # noqa: PLC0415
            except ImportError as exc:
                raise RuntimeError("PatchTST rank-normalized scoring requires pandas") from exc
            ranked = pd.DataFrame(values, columns=self.feature_cols).rank(pct=True) - 0.5
            values = ranked.fillna(0.0).to_numpy(dtype=np.float32)
        return tickers, values

    def _prepare_history(self, history: Any) -> Any:
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("score_with_history requires pandas") from exc

        required = ["date", "ticker", *self.feature_cols]
        missing = [col for col in required if col not in history.columns]
        if missing:
            raise KeyError(f"PatchTstStatefulScorer history missing columns: {missing}")
        out = history.loc[:, required].copy()
        out["date"] = pd.to_datetime(out["date"])
        out[self.feature_cols] = out[self.feature_cols].apply(pd.to_numeric, errors="coerce")
        if self._use_csranknorm_preprocessing:
            out[self.feature_cols] = (
                out.groupby("date")[self.feature_cols].rank(pct=True) - 0.5
            )
        out[self.feature_cols] = out[self.feature_cols].fillna(0.0)
        return out


# ─── Entry point ────────────────────────────────────────────────────────────

def load(manifest: Any) -> PatchTstStatefulScorer:
    """Build the scorer from an artifact manifest.

    Reads the ``.pt`` checkpoint pointed to by ``manifest.local_artifact_path`` when
    present, otherwise the standard ``ArtifactManifest.artifact_uri`` / legacy ``uri``.
    The PyTorch checkpoint format is produced by ``PersistModelTask``.
    """
    path = _resolve_path(manifest)
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    # PR #17 review BLOCKER-1: dispatch on `kind` so PatchTSMixer
    # artifacts (introduced by PR #16/#17) are loadable. Legacy
    # checkpoints without a `kind` field default to PatchTST for
    # backward compat — every artifact persisted before model_kind
    # threading landed in sequence_training was PatchTST.
    kind = str(ckpt.get("kind", "hf_patchtst"))
    if kind == "hf_patchtsmixer":
        from .patchtsmixer_ranker import HFPatchTSMixerRanker  # noqa: PLC0415
        from transformers import PatchTSMixerConfig  # noqa: PLC0415
        cfg = PatchTSMixerConfig(**ckpt["config_dict"])
        model = HFPatchTSMixerRanker(cfg)
    elif kind == "hf_patchtst":
        from .hf_trainer import HFPatchTSTRanker  # noqa: PLC0415
        from transformers import PatchTSTConfig  # noqa: PLC0415
        cfg = PatchTSTConfig(**ckpt["config_dict"])
        model = HFPatchTSTRanker(
            cfg,
            use_distributional_head=bool(ckpt.get("uses_distributional_head", False)),
            use_film_regime=bool(ckpt.get("uses_film_regime", False)),
            use_cross_stock_attn=bool(ckpt.get("uses_cross_stock_attn", False)),
        )
    else:
        raise ValueError(
            f"PatchTST scorer cannot load checkpoint kind={kind!r}; "
            f"expected one of {{'hf_patchtst', 'hf_patchtsmixer'}}")
    model.load_state_dict(ckpt["state_dict"])
    return PatchTstStatefulScorer(
        model,
        feature_cols=list(ckpt["feature_cols"]),
        seq_len=int(ckpt["seq_len"]),
        use_csranknorm_preprocessing=bool(
            ckpt.get("uses_csranknorm_preprocessing", False)
        ),
    )


def _resolve_path(manifest: Any) -> Path:
    local = _manifest_value(manifest, "local_artifact_path")
    if local:
        return Path(local)
    uri = _manifest_value(manifest, "artifact_uri", "uri") or ""
    parsed = urlparse(str(uri))
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme == "":
        return Path(str(uri))
    raise ValueError(
        f"PatchTST scorer cannot resolve artifact: local_artifact_path missing and "
        f"uri scheme not supported ({uri!r})"
    )


def _manifest_value(manifest: Any, *names: str) -> Any:
    for name in names:
        if isinstance(manifest, dict) and manifest.get(name):
            return manifest[name]
        value = getattr(manifest, name, None)
        if value:
            return value
    return None
