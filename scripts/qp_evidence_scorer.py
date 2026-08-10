#!/usr/bin/env python3
"""qp evidence scorer — nested per-fold gate-fit/validation/test replay.

The MODEL-SIDE half of the qp re-enable evidence prereg (renquant-
orchestrator doc/design/2026-08-10-qp-reenable-evidence-prereg.md,
MERGED as orch#955; doc sha256 d2392a…, pinned in the manifest). This
script implements freeze §4 (arms and machinery) and the model-side
duties of §7; the orchestrator's PR-B runner consumes the hash-pinned
artifacts and stays join-only (labels, statistic, bootstrap, verdict all
live THERE — none of them exists here).

Per fold f of the v2 CUTS (ast-read from the frozen harness; corpus sha
asserted against the harness pin):

  boundaries   train_end = last corpus session <= CUTS[f][1];
               validation_start = train_end - 251 sessions (a 252-session
               validation segment, corpus calendar); gate_fit_end = the
               session immediately before validation_start. All three
               recorded per fold.
  gate-fit     panel leg: renquant_model_gbdt.panel_trainer.train_xgb
               (PANEL_LTR_PARAMS verbatim, 100 rounds, the production
               artifact's 172-column feature contract — feature_cols
               read from the prod artifact JSON, its booster NEVER
               loaded) on rows with date <= gate_fit_end AND per-row
               60-session label endpoint strictly before
               validation_start (endpoint map on the corpus's own
               calendar). momentum leg: train_momentum_artifact with
               params_v0() at the latest weekly cutoff (last trading
               day <= a Saturday, corpus calendar) <= validation_start;
               golden checks per the module (content sha, frozen params
               fingerprint momentum-v0-fd65161a…, composite golden
               reproduction, names floor) — a failing cutoff DROPS the
               leg for the fold and records a degradation flag
               (composite degrades to z(panel) alone, freeze §4).
               Serving one artifact per arm is EQUIVALENT to per-day
               live-cadence serving under the arm's cutoff bound: every
               scored day is >= the bound, so the latest admissible
               weekly cutoff is the ledger tail for all of them.
  validation   the gate-fit models score the validation segment OUT-OF-
               SAMPLE: blend z+z per validation day (z cross-sectional,
               ddof=0, NaN propagates — blend_scorer.py semantics),
               top-5 entered per day, held 5 sessions, exits capped at
               train_end (freeze: every gate input ends by the fold's
               train end), pnl_pct = raw 5d ticker close return minus
               SPY (OHLCV 1d closes), entry_regime from the production
               regime constructor build_regime_series (the WF gate's
               own, called run_wf_gate.py:2701-style). Stamps via the
               production scripts/trade_monotonicity.py
               evaluate_trade_monotonicity, VERBATIM defaults
               (min_n_per_regime 30, min_spearman 0.02, positive
               spread). Per-fold per-regime {eligible, passed} FROZEN
               into the stamps JSON.
  full-train   panel leg: train <= train_end with per-row purge against
               the fold's test start (harness convention); momentum
               leg: latest weekly cutoff <= train_end, same golden
               checks. These score the TEST fold days only; emitted as
               fold,date,ticker,recipe_score,regime (regime from
               build_regime_series for the test dates, so PR B stays
               join-only; an undetermined regime is recorded UNKNOWN —
               fail-closed downstream, coverage-recorded here).

Outputs (committed, hash-pinned): the test-day scores CSV, the stamps
JSON, and a manifest recording every input sha, per-fold boundaries,
OOS validation day counts, momentum degradation flags, seeds/params
fingerprints, and the sha256 of both output files. NO labels are read
beyond fwd_60d_excess for training; fwd_5d_excess is never touched.

Usage:
  python qp_evidence_scorer.py --harness <frozen_harness.py> \
      --corpus <frozen_corpus.parquet> --prod-artifact <panel-ltr.json> \
      --renquant-root <RenQuant checkout> --out-dir <dir>
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from renquant_model_common.momentum_features import composite_scores  # noqa: E402
from renquant_model_common.total_return import total_return_close  # noqa: E402
from renquant_model_gbdt.panel_trainer import (  # noqa: E402
    DEFAULT_N_ROUNDS,
    PANEL_LTR_PARAMS,
    train_xgb,
)
from renquant_model_momentum.train import (  # noqa: E402
    params_config_fingerprint,
    params_v0,
    train_momentum_artifact,
    verify_artifact_content_sha,
)

LABEL = "fwd_60d_excess"
LABEL_SESSIONS = 60          # label horizon in corpus sessions (harness)
HOLD_SESSIONS = 5            # frozen validation-trade hold (freeze §4)
TOP_K = 5                    # frozen top-k per validation day (freeze §4)
VALIDATION_SESSIONS = 252    # validation_start = train_end - 251 sessions
FROZEN_CORPUS_SHA256 = (
    "870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e")
FROZEN_MOMENTUM_FP = "momentum-v0-fd65161a20b29314"  # freeze §4 fingerprint
FROZEN_TEST_DAY_COUNTS = (191, 191, 191, 189, 188, 191, 190, 26)  # freeze §5
EXPECTED_N_FEATURES = 172    # the production artifact's feature contract
SCORES_BASENAME = "2026-08-10-qp-evidence-scores.csv"
STAMPS_BASENAME = "2026-08-10-qp-evidence-stamps.json"
MANIFEST_BASENAME = "2026-08-10-qp-evidence-manifest.json"
DESIGN_DOC_SHA256 = (
    "d2392aa19fc74873688ead412d4e8fdb3a559ba4365c90af59c249b879aa4326")
_GOLDEN_ATOL = 1e-9          # pipeline loader's reconstruction bar


# ── input identity ──────────────────────────────────────────────────────

def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def harness_constants(harness_path: str | Path) -> dict:
    """ast-read the frozen harness constants (never import/execute it)."""
    tree = ast.parse(Path(harness_path).read_text())
    out = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in ("CUTS", "CORPUS_SHA256")):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    need = {"CUTS", "CORPUS_SHA256"}
    if set(out) != need:
        raise ValueError(f"harness constants missing: {need - set(out)}")
    return out


# ── corpus calendar machinery ───────────────────────────────────────────

def endpoint_map(sessions: list[str]) -> dict:
    """date -> the 60th corpus session AFTER it (harness _endpoint_map:
    per-row purge on the corpus's OWN calendar; beyond-corpus -> None)."""
    idx = {d: i for i, d in enumerate(sessions)}
    return {d: (sessions[i + LABEL_SESSIONS]
                if i + LABEL_SESSIONS < len(sessions) else None)
            for d, i in idx.items()}


def fold_boundaries(sessions: list[str], idx: dict, cut: tuple) -> dict:
    """All frozen boundaries for one CUTS row (freeze §4 gate bullet)."""
    tr_s, tr_e, te_s, te_e = cut
    train_end = max(d for d in sessions if d <= tr_e)
    it = idx[train_end]
    if it < VALIDATION_SESSIONS:
        raise ValueError(
            f"corpus too short for a {VALIDATION_SESSIONS}-session "
            f"validation segment before {train_end}")
    validation_start = sessions[it - (VALIDATION_SESSIONS - 1)]
    gate_fit_end = sessions[it - VALIDATION_SESSIONS]
    return {
        "train_start": tr_s,
        "train_end": train_end,
        "validation_start": validation_start,
        "gate_fit_end": gate_fit_end,
        "test_start": te_s,
        "test_end": te_e,
    }


def weekly_cutoff_grid(sessions: list[str]) -> list[str]:
    """Last trading day <= each Saturday, on the corpus calendar (the
    live weekly publish cadence, freeze §4 / build-spec resolution)."""
    first = pd.Timestamp(sessions[0])
    last = pd.Timestamp(sessions[-1])
    sat = first + pd.Timedelta(days=(5 - first.weekday()) % 7)
    arr = np.array(sessions)
    cutoffs: list[str] = []
    while sat <= last + pd.Timedelta(days=7):
        s = sat.strftime("%Y-%m-%d")
        pos = np.searchsorted(arr, s, side="right") - 1
        if pos >= 0:
            c = str(arr[pos])
            if not cutoffs or c != cutoffs[-1]:
                cutoffs.append(c)
        sat += pd.Timedelta(days=7)
    return cutoffs


def serving_cutoff(grid: list[str], bound: str) -> str:
    """Latest weekly cutoff <= bound — the ledger tail an arm would
    serve on every scored day (all scored days are >= bound)."""
    ok = [c for c in grid if c <= bound]
    if not ok:
        raise ValueError(f"no weekly cutoff <= {bound}")
    return ok[-1]


# ── panel leg (production trainer, verbatim) ────────────────────────────

def train_panel_arm(corpus: pd.DataFrame, feat_cols: list[str],
                    ep: dict, *, train_start: str, max_date: str,
                    endpoint_before: str, params: dict | None = None,
                    num_boost_round: int = DEFAULT_N_ROUNDS):
    """One panel-leg training: rows in [train_start, max_date] with a
    non-null label AND per-row 60-session endpoint strictly before
    ``endpoint_before`` (harness per-row purge convention). Trains via
    the production trainer's own default path (reindex + fillna(0), raw
    prebuilt-panel feature space, PANEL_LTR_PARAMS, date-sorted
    rank:pairwise groups)."""
    tr = corpus[(corpus.date >= train_start) & (corpus.date <= max_date)]
    tr = tr.dropna(subset=[LABEL])
    n0 = len(tr)
    keep = tr.date.map(lambda d: ep.get(d) is not None and ep[d] < endpoint_before)
    tr = tr[keep]
    if tr.empty:
        raise ValueError(
            f"panel arm has no training rows (<= {max_date}, "
            f"endpoint < {endpoint_before})")
    booster, train_ic = train_xgb(
        tr, feat_cols, label=LABEL,
        params=dict(PANEL_LTR_PARAMS if params is None else params),
        num_boost_round=num_boost_round)
    return booster, {"n_train_rows": int(len(tr)),
                     "n_purged": int(n0 - len(tr)),
                     "train_ic_insample": float(train_ic)}


def score_panel(booster, frame: pd.DataFrame, feat_cols: list[str]) -> np.ndarray:
    """Score rows with the SAME feature builder train_xgb's default path
    used (reindex to the contract, fillna(0)) — no other transform."""
    import xgboost as xgb  # noqa: PLC0415
    x = (frame.reindex(columns=feat_cols, fill_value=0).fillna(0)
         .values.astype(np.float64))
    return booster.predict(xgb.DMatrix(x))


# ── blend construction (blend_scorer.py semantics) ──────────────────────

def _zvec(vals: np.ndarray) -> np.ndarray | None:
    """Cross-sectional z, ddof=0, over the finite universe; None when the
    leg is degenerate (<2 finite or sd<=0) — it then contributes 0
    (BlendPanelScorer.score, verbatim semantics)."""
    finite = np.isfinite(vals)
    if int(finite.sum()) < 2:
        return None
    mu = float(vals[finite].mean())
    sd = float(vals[finite].std())  # ddof=0 (numpy default)
    if not np.isfinite(sd) or sd <= 0.0:
        return None
    z = np.full(len(vals), np.nan)
    z[finite] = (vals[finite] - mu) / sd
    return z


def composite_over_frame(scored: pd.DataFrame,
                         mom_scores: dict | None) -> tuple[np.ndarray, dict]:
    """Per-day blend z(panel) + z(momentum) over a frame with columns
    date, ticker, panel_raw (RangeIndex). NaN propagates for names a
    healthy leg could not score; a degenerate leg contributes 0 and is
    reason-recorded; a DROPPED momentum leg (mom_scores None) degrades
    the composite to z(panel) alone (freeze §4 fallback)."""
    comp = np.full(len(scored), np.nan)
    reasons: dict[str, list[str]] = {}
    for d, g in scored.groupby("date", sort=True):
        pos = g.index.to_numpy()
        total = np.zeros(len(g))
        z_p = _zvec(g["panel_raw"].to_numpy(dtype=float))
        if z_p is None:
            reasons.setdefault(str(d), []).append("panel_degenerate")
        else:
            total = total + z_p
        if mom_scores is not None:
            mv = np.array([mom_scores.get(t, np.nan) for t in g["ticker"]],
                          dtype=float)
            z_m = _zvec(mv)
            if z_m is None:
                reasons.setdefault(str(d), []).append("momentum_degenerate")
            else:
                total = total + z_m
        comp[pos] = total
    return comp, reasons


# ── momentum leg (frozen recipe replay + golden checks) ─────────────────

def momentum_golden_checks(artifact: dict) -> list[str]:
    """The module's golden checks (freeze §7 'golden checks' duty): the
    self-carried content sha recomputes; the params fingerprint IS the
    frozen recipe momentum-v0-fd65161a…; the composite reproduces from
    the stored features (the pipeline loader's golden-reproduction bar,
    <1e-9); the names floor is met. ANY failure -> the leg is dropped
    for the fold and a degradation flag recorded."""
    fails: list[str] = []
    try:
        verify_artifact_content_sha(artifact)
    except ValueError as exc:
        fails.append(f"content_sha_mismatch:{exc}")
    stamped = artifact.get("config_fingerprint")
    if stamped != FROZEN_MOMENTUM_FP:
        fails.append(f"config_fingerprint_not_frozen:{stamped}")
    recomputed = params_config_fingerprint(artifact.get("params", {}))
    if recomputed != FROZEN_MOMENTUM_FP:
        fails.append(f"params_fingerprint_recompute:{recomputed}")
    feats: dict[str, dict[str, float]] = {f: {} for f in
                                          ("f1", "f2", "f3", "f4", "f5")}
    for t, row in (artifact.get("features") or {}).items():
        for f in feats:
            v = row.get(f)
            feats[f][t] = float("nan") if v is None else float(v)
    try:
        min_features = int(artifact["params"]["min_features"])
        golden, _ = composite_scores(feats, min_features=min_features)
        for t, s in (artifact.get("scores") or {}).items():
            a = float("nan") if s is None else float(s)
            b = golden.get(t, float("nan"))
            same = (np.isnan(a) and np.isnan(b)) or (
                np.isfinite(a) and np.isfinite(b) and abs(a - b) <= _GOLDEN_ATOL)
            if not same:
                fails.append(f"scores_reconstruction_mismatch:{t}")
                break
    except (KeyError, TypeError, ValueError) as exc:
        fails.append(f"scores_reconstruction_unrunnable:{exc}")
    if not artifact.get("names_floor_ok"):
        fails.append(f"names_floor:n_scored={artifact.get('n_scored')}")
    return fails


class OhlcvStore:
    """Cached read-only OHLCV frames (data/ohlcv/<T>/1d.parquet) with
    per-file digest recording — serves both the momentum readers and the
    validation-trade pnl closes from ONE read per file."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._frames: dict[str, pd.DataFrame | None] = {}
        self.digests: dict[str, str] = {}

    def frame(self, ticker: str) -> pd.DataFrame | None:
        if ticker not in self._frames:
            f = self.root / ticker / "1d.parquet"
            if not f.is_file():
                self._frames[ticker] = None
            else:
                self.digests[f"ohlcv/{ticker}/1d.parquet"] = file_sha256(f)
                self._frames[ticker] = pd.read_parquet(f)
        return self._frames[ticker]

    def close(self, ticker: str) -> pd.Series | None:
        raw = self.frame(ticker)
        return None if raw is None else raw["close"]

    def tr_returns(self, ticker: str) -> pd.Series | None:
        """Total-return daily returns — tools/momentum_train_run.py
        LiveReaders recipe, verbatim."""
        raw = self.frame(ticker)
        if raw is None:
            return None
        tr = total_return_close(
            raw["close"],
            raw["dividend"] if "dividend" in raw.columns
            else pd.Series(0.0, index=raw.index))
        return tr.pct_change()

    def volume(self, ticker: str) -> pd.Series | None:
        raw = self.frame(ticker)
        return None if raw is None else raw["volume"]


class CorpusMomentumReaders:
    """MomentumReaders over the shared OhlcvStore + ticker_sectors.json
    (the production LiveReaders shape; digests recorded at read)."""

    def __init__(self, store: OhlcvStore, sectors_path: str | Path,
                 market: str = "SPY"):
        self._store = store
        self._sectors_path = Path(sectors_path)
        self._market = market
        self._sectors: dict[str, str | None] | None = None

    def tr_returns(self, ticker: str) -> pd.Series | None:
        return self._store.tr_returns(ticker)

    def volume(self, ticker: str) -> pd.Series | None:
        return self._store.volume(ticker)

    def market_tr_returns(self) -> pd.Series:
        r = self._store.tr_returns(self._market)
        if r is None:
            raise FileNotFoundError(
                f"market series {self._market} absent under {self._store.root}")
        return r

    def sector_of(self) -> dict[str, str | None]:
        if self._sectors is None:
            self._store.digests["ticker_sectors.json"] = file_sha256(
                self._sectors_path)
            raw = json.loads(self._sectors_path.read_text())
            self._sectors = {t: v.get("sector") for t, v in raw.items()}
        return self._sectors

    def read_digests(self) -> dict[str, str]:
        return dict(self._store.digests)


def make_real_momentum_arm(readers: CorpusMomentumReaders,
                           corpus_days: pd.DataFrame):
    """momentum_arm(cutoff, universe_bound) -> (scores|None, info).
    Universe = tickers on the latest corpus date <= cutoff (the
    production resolve_universe rule against the FROZEN corpus).
    Golden-check failure -> (None, info with dropped=True)."""
    def arm(cutoff: str) -> tuple[dict | None, dict]:
        eligible = corpus_days[corpus_days.date <= cutoff]
        if eligible.empty:
            raise ValueError(f"corpus has no dates <= {cutoff}")
        day = eligible.date.max()
        universe = sorted(eligible.loc[eligible.date == day, "ticker"].unique())
        artifact = train_momentum_artifact(
            pd.Timestamp(cutoff), universe, params_v0(), readers=readers)
        fails = momentum_golden_checks(artifact)
        info = {
            "cutoff": cutoff,
            "universe_date": str(day),
            "n_names": int(artifact["n_names"]),
            "n_scored": int(artifact["n_scored"]),
            "n_missing_series": int(artifact["n_missing_series"]),
            "names_floor_ok": bool(artifact["names_floor_ok"]),
            "effective_train_cutoff_date":
                artifact["effective_train_cutoff_date"],
            "content_sha256": artifact["content_sha256"],
            "config_fingerprint": artifact["config_fingerprint"],
            "golden_failures": fails,
            "dropped": bool(fails),
        }
        if fails:
            return None, info
        scores = {t: float(s) for t, s in artifact["scores"].items()
                  if s is not None and np.isfinite(s)}
        return scores, info
    return arm


# ── validation trades + frozen stamps ───────────────────────────────────

def _ret_between(close: pd.Series | None, d0: str, d1: str) -> float:
    if close is None:
        return float("nan")
    try:
        p0 = float(close.loc[pd.Timestamp(d0)])
        p1 = float(close.loc[pd.Timestamp(d1)])
    except KeyError:
        return float("nan")
    if not (np.isfinite(p0) and np.isfinite(p1)) or p0 <= 0:
        return float("nan")
    return p1 / p0 - 1.0


def simulate_validation_trades(comp_frame: pd.DataFrame, entry_days: list[str],
                               sessions: list[str], idx: dict, *,
                               close_of, spy_close: pd.Series,
                               regime_of) -> pd.DataFrame:
    """Frozen simulated-trade convention (freeze §4): top-5 by composite
    per entry day (ties broken by ticker, deterministic), held exactly
    HOLD_SESSIONS corpus sessions, pnl_pct = raw ticker close return
    minus SPY over the hold, entry_regime from the production regime
    series. Trades whose prices are unreadable keep a NaN pnl_pct — the
    production evaluator's cleaner drops them (counted upstream)."""
    rows = []
    for d in entry_days:
        g = comp_frame[comp_frame.date == d]
        fin = g[np.isfinite(g["composite"].to_numpy(dtype=float))]
        if fin.empty:
            continue
        sel = fin.sort_values(["composite", "ticker"],
                              ascending=[False, True]).head(TOP_K)
        exit_d = sessions[idx[d] + HOLD_SESSIONS]
        spy_ret = _ret_between(spy_close, d, exit_d)
        for _, r in sel.iterrows():
            tick_ret = _ret_between(close_of(r["ticker"]), d, exit_d)
            rows.append({
                "entry_date": d,
                "exit_date": exit_d,
                "ticker": r["ticker"],
                "entry_rank_score": float(r["composite"]),
                "pnl_pct": tick_ret - spy_ret,
                "entry_regime": regime_of(d),
            })
    return pd.DataFrame(rows, columns=["entry_date", "exit_date", "ticker",
                                       "entry_rank_score", "pnl_pct",
                                       "entry_regime"])


def load_monotonicity_evaluator(renquant_root: str | Path):
    """The production stamp authority, loaded VERBATIM from the RenQuant
    checkout's scripts/trade_monotonicity.py (never re-implemented)."""
    import importlib.util  # noqa: PLC0415
    path = Path(renquant_root) / "scripts" / "trade_monotonicity.py"
    name = "qp_evidence_trade_monotonicity"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclass InitVar resolution needs the entry
    spec.loader.exec_module(mod)
    return mod.evaluate_trade_monotonicity


def compute_stamps(trades: pd.DataFrame, evaluator) -> dict:
    """evaluate_trade_monotonicity with VERBATIM defaults; the per-regime
    {eligible, passed} pairs are the FROZEN gate stamps."""
    report = evaluator(trades)
    regimes = {}
    for row in report.regimes:
        regimes[str(row["regime"])] = {
            "eligible": bool(row["eligible"]),
            "passed": bool(row["passed"]),
            "n": int(row["n"]),
            "spearman": (None if row.get("spearman") is None
                         else float(row["spearman"])),
            "top_bottom_return_spread":
                (None if row.get("top_bottom_return_spread") is None
                 else float(row["top_bottom_return_spread"])),
        }
    return {"passed": bool(report.passed), "reason": str(report.reason),
            "regimes": regimes}


# ── per-fold nested replay ──────────────────────────────────────────────

def run_fold(corpus: pd.DataFrame, feat_cols: list[str], sessions: list[str],
             idx: dict, ep: dict, cut: tuple, fold_no: int, *,
             close_of, spy_close: pd.Series, regime_of, momentum_arm,
             evaluator, weekly_grid: list[str] | None = None,
             params: dict | None = None,
             num_boost_round: int = DEFAULT_N_ROUNDS) -> dict:
    """One fold's full nested replay (freeze §4 gate bullet, splits
    i/ii/iii). Returns test scores + frozen stamps + per-fold metadata;
    NOTHING here reads labels beyond training fwd_60d_excess."""
    b = fold_boundaries(sessions, idx, cut)
    it = idx[b["train_end"]]
    grid = weekly_grid if weekly_grid is not None else weekly_cutoff_grid(sessions)

    # (i) GATE-FIT models — see NOTHING from the validation segment.
    gate_booster, gate_meta = train_panel_arm(
        corpus, feat_cols, ep, train_start=b["train_start"],
        max_date=b["gate_fit_end"], endpoint_before=b["validation_start"],
        params=params, num_boost_round=num_boost_round)
    gate_cutoff = serving_cutoff(grid, b["validation_start"])
    gate_mom_scores, gate_mom_info = momentum_arm(gate_cutoff)

    # (ii) VALIDATION segment — OOS scoring by the gate-fit models; entry
    # days capped so every exit lands on/before train_end (freeze: every
    # gate input ends by the fold's train end).
    segment = sessions[it - (VALIDATION_SESSIONS - 1): it + 1]
    entry_days = [d for d in segment if idx[d] + HOLD_SESSIONS <= it]
    val_rows = corpus[corpus.date.isin(entry_days)][["date", "ticker"]].copy()
    val_rows = val_rows.sort_values(["date", "ticker"]).reset_index(drop=True)
    val_rows["panel_raw"] = score_panel(
        gate_booster, corpus.loc[
            corpus.date.isin(entry_days)].sort_values(["date", "ticker"]),
        feat_cols)
    val_comp, val_reasons = composite_over_frame(val_rows, gate_mom_scores)
    val_rows["composite"] = val_comp
    trades = simulate_validation_trades(
        val_rows, entry_days, sessions, idx,
        close_of=close_of, spy_close=spy_close, regime_of=regime_of)
    if len(trades) and trades["exit_date"].max() > b["train_end"]:
        raise AssertionError(
            f"fold {fold_no}: a validation trade exits after train_end "
            f"({trades['exit_date'].max()} > {b['train_end']})")
    stamps = compute_stamps(trades, evaluator)

    # (iii) TEST fold — FULL-TRAIN models, retrained only after the gate
    # stamps above are frozen; the stamps never touch these scores here
    # (PR B applies them unchanged).
    full_booster, full_meta = train_panel_arm(
        corpus, feat_cols, ep, train_start=b["train_start"],
        max_date=b["train_end"], endpoint_before=b["test_start"],
        params=params, num_boost_round=num_boost_round)
    full_cutoff = serving_cutoff(grid, b["train_end"])
    full_mom_scores, full_mom_info = momentum_arm(full_cutoff)

    test_days = [d for d in sessions if b["test_start"] <= d <= b["test_end"]]
    test_rows = corpus[corpus.date.isin(test_days)][["date", "ticker"]].copy()
    test_rows = test_rows.sort_values(["date", "ticker"]).reset_index(drop=True)
    test_rows["panel_raw"] = score_panel(
        full_booster, corpus.loc[
            corpus.date.isin(test_days)].sort_values(["date", "ticker"]),
        feat_cols)
    test_comp, test_reasons = composite_over_frame(test_rows, full_mom_scores)
    scores_df = pd.DataFrame({
        "fold": fold_no,
        "date": test_rows["date"],
        "ticker": test_rows["ticker"],
        "recipe_score": test_comp,
        "regime": [regime_of(d) for d in test_rows["date"]],
    })

    n_trades = int(len(trades))
    n_trades_scored = int(np.isfinite(
        trades["pnl_pct"].to_numpy(dtype=float)).sum()) if n_trades else 0
    meta = {
        "fold": fold_no,
        "boundaries": b,
        "validation": {
            "n_segment_days": len(segment),
            "n_entry_days": len(entry_days),
            "n_trades": n_trades,
            "n_trades_with_pnl": n_trades_scored,
            "n_regime_unknown_entry_days": int(sum(
                1 for d in entry_days if regime_of(d) == "UNKNOWN")),
            "panel": gate_meta,
            "momentum": gate_mom_info,
            "degenerate_leg_days": {k: v for k, v in val_reasons.items()},
        },
        "test": {
            "n_days": len(test_days),
            "n_rows": int(len(scores_df)),
            "n_regime_unknown_days": int(sum(
                1 for d in test_days if regime_of(d) == "UNKNOWN")),
            "panel": full_meta,
            "momentum": full_mom_info,
            "degenerate_leg_days": {k: v for k, v in test_reasons.items()},
        },
        "momentum_degraded": bool(gate_mom_info.get("dropped")
                                  or full_mom_info.get("dropped")),
    }
    return {"scores": scores_df, "stamps": stamps, "meta": meta,
            "trades": trades}


# ── guards + outputs ────────────────────────────────────────────────────

def assert_no_validation_leak(scores_df: pd.DataFrame,
                              boundaries_by_fold: dict) -> None:
    """FAIL LOUDLY if any emitted test-score row sits outside its fold's
    test interval — in particular a validation/train day leaking in."""
    for fold, b in boundaries_by_fold.items():
        sub = scores_df[scores_df["fold"] == fold]
        bad = sub[(sub["date"] <= b["train_end"])
                  | (sub["date"] < b["test_start"])
                  | (sub["date"] > b["test_end"])]
        if len(bad):
            raise AssertionError(
                f"validation/test boundary violated: fold {fold} emits "
                f"{len(bad)} row(s) outside ({b['test_start']}.."
                f"{b['test_end']}] & > train_end {b['train_end']}; "
                f"first offending date {sorted(bad['date'])[0]}")


def expected_schedule(sessions: list[str],
                      boundaries_by_fold: dict) -> dict[str, list[str]]:
    """orch#956 codex P0: {fold (str) -> every expected test date}, from
    the SAME corpus calendar the scorer scores on (v2 CUTS test
    intervals intersected with corpus sessions). The orchestrator runner
    asserts exact score coverage against this — any missing (fold, date)
    is a fail-closed coverage failure."""
    return {str(fold): [d for d in sessions
                        if b["test_start"] <= d <= b["test_end"]]
            for fold, b in boundaries_by_fold.items()}


def assert_scores_contract(scores_df: pd.DataFrame,
                           schedule: dict[str, list[str]]) -> None:
    """Emitted-artifact invariants the orchestrator asserts (orch#956):
    (1) coverage — every scheduled (fold, date) has rows and no
    unscheduled (fold, date) appears; (2) exactly ONE regime value per
    (fold, date) group; (3) rows sorted by (fold, date, ticker)."""
    got = {(str(f), d) for f, d in
           scores_df[["fold", "date"]].drop_duplicates().itertuples(index=False)}
    want = {(f, d) for f, dates in schedule.items() for d in dates}
    if got != want:
        missing = sorted(want - got)[:3]
        extra = sorted(got - want)[:3]
        raise AssertionError(
            f"score coverage != expected schedule: {len(want - got)} "
            f"missing (e.g. {missing}), {len(got - want)} extra "
            f"(e.g. {extra})")
    n_regimes = scores_df.groupby(["fold", "date"])["regime"].nunique()
    if int(n_regimes.max()) != 1 or int(n_regimes.min()) != 1:
        bad = n_regimes[n_regimes != 1].index.tolist()[:3]
        raise AssertionError(
            f"(fold, date) groups without exactly one regime value: {bad}")
    key = scores_df[["fold", "date", "ticker"]].apply(tuple, axis=1).tolist()
    if key != sorted(key):
        raise AssertionError(
            "scores rows are not sorted by (fold, date, ticker)")


def write_outputs(out_dir: str | Path, scores_df: pd.DataFrame,
                  stamps: dict) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scores_path = out / SCORES_BASENAME
    stamps_path = out / STAMPS_BASENAME
    scores_df.to_csv(scores_path, index=False)
    stamps_path.write_text(
        json.dumps(stamps, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    return {
        "scores_csv": {"path": str(scores_path),
                       "sha256": file_sha256(scores_path),
                       "n_rows": int(len(scores_df))},
        "stamps_json": {"path": str(stamps_path),
                        "sha256": file_sha256(stamps_path)},
    }


def verify_output_shas(manifest: dict, out_dir: str | Path) -> None:
    """Recompute both output digests from disk against the manifest —
    manifest sha integrity is a hard check, not an assertion in prose."""
    out = Path(out_dir)
    for key, basename in (("scores_csv", SCORES_BASENAME),
                          ("stamps_json", STAMPS_BASENAME)):
        want = manifest["outputs"][key]["sha256"]
        got = file_sha256(out / basename)
        if want != got:
            raise AssertionError(
                f"manifest sha mismatch for {basename}: manifest {want[:12]}… "
                f"!= on-disk {got[:12]}…")


def find_renquant_root(repo: Path = _REPO) -> Path | None:
    """Sibling RenQuant discovery via the repo's committed data symlink
    (data -> ../RenQuant/data), falling back to a plain sibling dir."""
    for cand in ((repo / "data"), None):
        if cand is not None and cand.exists():
            root = cand.resolve().parent
            if (root / "scripts" / "trade_monotonicity.py").is_file():
                return root
    sib = repo.parent / "RenQuant"
    if (sib / "scripts" / "trade_monotonicity.py").is_file():
        return sib
    return None


# ── real-run driver ─────────────────────────────────────────────────────

def _git_revision(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--prod-artifact", required=True)
    ap.add_argument("--renquant-root", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    rq = Path(a.renquant_root)

    h = harness_constants(a.harness)
    cuts = h["CUTS"]
    assert len(cuts) == 8 and cuts[7][1] == "2025-12-31", (
        f"harness CUTS is not the v2 8-fold table: {cuts!r}")
    corpus_sha = file_sha256(a.corpus)
    assert corpus_sha == h["CORPUS_SHA256"] == FROZEN_CORPUS_SHA256, (
        f"frozen corpus sha {corpus_sha[:12]}… != harness/prereg pin")

    prod = json.loads(Path(a.prod_artifact).read_text())
    feat_cols = list(prod["feature_cols"])  # features ONLY — booster unread
    assert len(feat_cols) == EXPECTED_N_FEATURES, (
        f"prod artifact feature contract is {len(feat_cols)} cols, "
        f"expected {EXPECTED_N_FEATURES}")
    del prod

    corpus = pd.read_parquet(a.corpus,
                             columns=["date", "ticker", LABEL] + feat_cols)
    corpus["date"] = corpus["date"].astype(str).str[:10]
    missing = [c for c in feat_cols if c not in corpus.columns]
    assert not missing, f"corpus lacks contract features: {missing[:5]}"
    sessions = sorted(corpus.date.unique())
    idx = {d: i for i, d in enumerate(sessions)}
    ep = endpoint_map(sessions)
    grid = weekly_cutoff_grid(sessions)

    boundaries_by_fold = {f + 1: fold_boundaries(sessions, idx, cut)
                          for f, cut in enumerate(cuts)}
    test_day_counts = tuple(
        sum(1 for d in sessions if b["test_start"] <= d <= b["test_end"])
        for b in boundaries_by_fold.values())
    assert test_day_counts == FROZEN_TEST_DAY_COUNTS, (
        f"corpus test-day counts {test_day_counts} != frozen §5 table "
        f"{FROZEN_TEST_DAY_COUNTS}")

    # Production regime series — the WF gate's own constructor, called the
    # run_wf_gate.py:2701 way; ONE call over every date we stamp or emit.
    if str(rq) not in sys.path:
        sys.path.insert(0, str(rq))
    from scripts.analyze_manifest_sanity_placebo import (  # noqa: PLC0415
        STRATEGY_DIR,
        build_regime_series,
    )
    all_dates: set[str] = set()
    for fold, b in boundaries_by_fold.items():
        it = idx[b["train_end"]]
        segment = sessions[it - (VALIDATION_SESSIONS - 1): it + 1]
        all_dates.update(d for d in segment if idx[d] + HOLD_SESSIONS <= it)
        all_dates.update(d for d in sessions
                         if b["test_start"] <= d <= b["test_end"])
    print(f"building production regime series for {len(all_dates)} dates…",
          flush=True)
    regimes_df = build_regime_series(sorted(all_dates),
                                     strategy_dir=STRATEGY_DIR)
    regime_map = {
        pd.Timestamp(r["date"]).strftime("%Y-%m-%d"):
            (str(r["regime"]) if r["regime"] else "UNKNOWN")
        for _, r in regimes_df.iterrows()}

    def regime_of(d: str) -> str:
        return regime_map.get(d, "UNKNOWN")

    store = OhlcvStore(rq / "data" / "ohlcv")
    readers = CorpusMomentumReaders(store, rq / "data" / "ticker_sectors.json")
    momentum_arm = make_real_momentum_arm(
        readers, corpus[["date", "ticker"]])
    spy_close = store.close("SPY")
    assert spy_close is not None, "SPY OHLCV missing"
    evaluator = load_monotonicity_evaluator(rq)

    all_scores, stamps, fold_meta = [], {}, []
    for fold, cut in enumerate(cuts, start=1):
        print(f"fold {fold}: nested replay starting "
              f"({boundaries_by_fold[fold]})", flush=True)
        res = run_fold(corpus, feat_cols, sessions, idx, ep, cut, fold,
                       close_of=store.close, spy_close=spy_close,
                       regime_of=regime_of, momentum_arm=momentum_arm,
                       evaluator=evaluator, weekly_grid=grid)
        all_scores.append(res["scores"])
        stamps[f"fold_{fold}"] = {
            "boundaries": res["meta"]["boundaries"],
            **res["stamps"],
        }
        fold_meta.append(res["meta"])
        print(f"fold {fold}: {res['meta']['validation']['n_trades']} "
              f"validation trades, stamps passed={res['stamps']['passed']} "
              f"({res['stamps']['reason']}); "
              f"{res['meta']['test']['n_rows']} test rows", flush=True)

    scores_df = pd.concat(all_scores, ignore_index=True)
    assert_no_validation_leak(scores_df, boundaries_by_fold)
    schedule = expected_schedule(sessions, boundaries_by_fold)
    assert_scores_contract(scores_df, schedule)
    outputs = write_outputs(a.out_dir, scores_df, stamps)

    manifest = {
        "design": {
            "doc": ("renquant-orchestrator doc/design/"
                    "2026-08-10-qp-reenable-evidence-prereg.md"),
            "merged_pr": "orch#955",
            "doc_sha256": DESIGN_DOC_SHA256,
        },
        "inputs": {
            "harness": {"path": str(a.harness),
                        "sha256": file_sha256(a.harness)},
            "frozen_corpus": {"path": str(a.corpus), "sha256": corpus_sha,
                              "rows": int(len(corpus)),
                              "sessions": len(sessions)},
            "prod_panel_artifact": {
                "path": str(a.prod_artifact),
                "sha256": file_sha256(a.prod_artifact),
                "n_feature_cols": len(feat_cols),
                "feature_cols_sha256": hashlib.sha256(
                    json.dumps(feat_cols).encode()).hexdigest(),
                "read": "feature_cols only; the booster was never loaded",
            },
            "trade_monotonicity_module": {
                "path": str(rq / "scripts" / "trade_monotonicity.py"),
                "sha256": file_sha256(rq / "scripts" / "trade_monotonicity.py"),
                "thresholds": "verbatim defaults (min_n_per_regime 30, "
                              "min_spearman 0.02, positive spread)",
            },
            "regime_constructor": {
                "module": "scripts/analyze_manifest_sanity_placebo.py",
                "path": str(rq / "scripts" /
                            "analyze_manifest_sanity_placebo.py"),
                "sha256": file_sha256(
                    rq / "scripts" / "analyze_manifest_sanity_placebo.py"),
                "strategy_dir": str(STRATEGY_DIR),
                "strategy_config_sha256": file_sha256(
                    Path(STRATEGY_DIR) / "strategy_config.json"),
                "called_as": ("build_regime_series(dates, strategy_dir="
                              "STRATEGY_DIR) — the run_wf_gate.py:2701 shape"),
            },
            "ohlcv_read_digests": readers.read_digests(),
        },
        "panel_trainer": {
            "module": "renquant_model_gbdt.panel_trainer",
            "file_sha256": file_sha256(
                _REPO / "src" / "renquant_model_gbdt" / "panel_trainer.py"),
            "git_revision": _git_revision(_REPO),
            "params": dict(PANEL_LTR_PARAMS),
            "params_sha256": hashlib.sha256(json.dumps(
                PANEL_LTR_PARAMS, sort_keys=True).encode()).hexdigest(),
            "num_boost_round": DEFAULT_N_ROUNDS,
            "label": LABEL,
            "feature_space": ("raw prebuilt-panel values, reindex to the "
                              "contract + fillna(0) — train_xgb's default "
                              "path; identical builder at scoring time"),
        },
        "momentum": {
            "params": params_v0(),
            "config_fingerprint": FROZEN_MOMENTUM_FP,
            "weekly_cutoff_rule": (
                "last trading day <= each Saturday on the corpus calendar; "
                "each arm serves its latest cutoff <= the arm's bound "
                "(gate-fit: validation_start; full-train: train_end) — "
                "equivalent to per-day live-cadence serving because every "
                "scored day is >= the bound"),
            "golden_checks": ["content_sha_recomputes",
                             "params_fingerprint_is_frozen",
                             "composite_golden_reproduction_1e-9",
                             "names_floor_ok"],
        },
        "conventions": {
            "boundaries": ("train_end = last corpus session <= CUTS[f][1]; "
                           "validation_start = train_end - 251 sessions; "
                           "gate_fit_end = the session before "
                           "validation_start"),
            "purge": ("per-row 60-session label endpoint on the corpus "
                      "calendar: gate-fit endpoint < validation_start; "
                      "full-train endpoint < test_start (harness "
                      "convention)"),
            "blend": ("z(panel) + z(momentum) per day, z ddof=0 over each "
                      "leg's finite universe, NaN propagates (intersection "
                      "semantics); degenerate leg contributes 0, recorded; "
                      "dropped momentum leg -> z(panel) alone (freeze §4 "
                      "fallback)"),
            "validation_trades": (f"top-{TOP_K} per entry day, held "
                                  f"{HOLD_SESSIONS} sessions, entries capped "
                                  "so exits land on/before train_end; "
                                  "pnl_pct = raw close return minus SPY "
                                  "(fractional units)"),
            "regime_fail_closed": ("a date the detector cannot stamp is "
                                   "recorded UNKNOWN and counted; UNKNOWN "
                                   "is not an admitted regime downstream"),
        },
        "expected_schedule": schedule,
        "folds": fold_meta,
        "outputs": outputs,
        "run": {
            "executed_at_utc": _dt.datetime.now(
                _dt.timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0],
            "xgboost": __import__("xgboost").__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    manifest_path = Path(a.out_dir) / MANIFEST_BASENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    verify_output_shas(manifest, a.out_dir)

    print(json.dumps({
        "status": "DONE",
        "scores_csv_sha256": outputs["scores_csv"]["sha256"],
        "scores_rows": outputs["scores_csv"]["n_rows"],
        "stamps_json_sha256": outputs["stamps_json"]["sha256"],
        "manifest": str(manifest_path),
        "momentum_degraded_folds": [m["fold"] for m in fold_meta
                                    if m["momentum_degraded"]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
