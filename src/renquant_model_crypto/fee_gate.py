"""Fee-aware net-of-cost WF evaluation + BTC baselines (crypto RFC D-C8b, M1).

Model-side, asset-SPECIFIC half of the D-C8 split (RFC §4.4 / §9.3): the
crypto taker-fee default, the BTC-baseline comparisons and the crypto
promotion DIAGNOSTIC live here; the generic cost-accounting math is the
shared ``renquant_common.cost_model`` primitive (D-C8a), soft-consumed with
an identical frozen local fallback so merge order is free (the pipeline#183
pattern). Runtime consumers must reach the SAME primitive — one number,
every consumer.

The "beat buy-and-hold BTC (and the naive BTC-timing rule) net of fees"
promotion bar (§4.4) is computed here as a **stamped diagnostic on tier-1
survivor-only evidence — NOT an enable path**. Nothing in this module (or
repo) flips a sleeve on: prospective economic enablement is owned by Stage
2.5 of the RFC's rollout ladder, gated on non-overlapping 20-day blocks of
REAL canary data, and explicitly may not consume tier-1 numbers as
thresholds (§6.1 "the exploratory survivor panel sets NONE of these
thresholds").
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("renquant_model_crypto.fee_gate")

# --- D-C8a soft-consume (merge-order free, no pin bump) ---------------------
try:  # canonical: renquant-common ships cost_model (D-C8a merged)
    from renquant_common import cost_model as _common_cost_model
except ImportError:  # identical frozen local stand-in (parity-tested)
    _common_cost_model = None

from . import _cost_model_fallback as _fallback_cost_model

USING_COMMON_COST_MODEL = _common_cost_model is not None
cost_model = _common_cost_model if USING_COMMON_COST_MODEL else _fallback_cost_model

#: Alpaca crypto tier-0 taker fee, bps per side. [GUESS: RFC §2.7 — not
#: verifiable from the SDK; the Stage-0 paper battery verifies the schedule
#: EMPIRICALLY from fill receipts and its number supersedes this default.
#: Never hardcode this into shared code (D-C8a boundary).]
CRYPTO_TAKER_FEE_BPS_DEFAULT = 25.0

#: Pre-registered naive BTC-timing rule (§4.4 secondary baseline): long BTC
#: iff the trailing N-calendar-day return is positive, else cash. FROZEN
#: here before any WF evidence; not tunable per-run (a swept baseline is no
#: baseline).
BTC_TIMING_LOOKBACK_CALENDAR_DAYS = 20

DEFAULT_BTC_SLUG = "BTC-USD"


def default_crypto_cost_spec():
    """Fee-only crypto cost spec at the taker default.

    Fee-only mirrors the RFC's own frozen fee-only convention (§6.1's
    ``RT_friction_fee_only``); spread/slippage/rounding components are
    instantiated ONCE from the Stage-0 ex-ante bounds when that battery
    reports — callers pass the instantiated spec explicitly then.
    """
    return cost_model.CostModelSpec(fee_bps=CRYPTO_TAKER_FEE_BPS_DEFAULT)


def _spec_provenance(spec: Any) -> dict:
    return {
        "fee_bps": float(spec.fee_bps),
        "spread_bps": float(spec.spread_bps),
        "slippage_bps": float(spec.slippage_bps),
        "increment_rounding_bps": float(spec.increment_rounding_bps),
        "per_side_cost_bps": float(cost_model.per_side_cost_bps(spec)),
        "round_trip_cost_bps": float(cost_model.round_trip_cost_bps(spec)),
        "fee_default_status": (
            "GUESS_stage0_verifies" if float(spec.fee_bps) == CRYPTO_TAKER_FEE_BPS_DEFAULT
            else "caller_supplied"
        ),
        "cost_model_impl": (
            "renquant_common.cost_model" if USING_COMMON_COST_MODEL
            else "renquant_model_crypto._cost_model_fallback"
        ),
    }


def _compound(returns: list[float]) -> float:
    total = 1.0
    for r in returns:
        total *= 1.0 + r
    return total - 1.0


def _close_matrix(closes: pd.DataFrame) -> pd.DataFrame:
    for col in ("date", "ticker", "close"):
        if col not in closes.columns:
            raise ValueError(f"closes frame lacks required column {col!r}")
    wide = closes.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    wide.index = pd.DatetimeIndex(pd.to_datetime(wide.index)).sort_values()
    return wide.sort_index()


# ---------------------------------------------------------------------------
# Strategy replay: top-k equal-weight, periodic rebalance, net of costs
# ---------------------------------------------------------------------------

def simulate_topk_net(
    scores: pd.DataFrame,
    closes: pd.DataFrame,
    spec,
    *,
    top_k: int = 5,
    rebalance_days: int = 20,
) -> dict:
    """Replay a top-k equal-weight strategy net of costs over scored dates.

    Frozen replay semantics (consumers/tests pin these):

    * ``scores``: long frame ``[date, ticker, score]``. Rebalances happen on
      every ``rebalance_days``-th scored date (positions on the UTC-day
      axis), starting at the first scored date.
    * A rebalance at close of day D sets weights that earn from D -> D+1
      onwards — no same-day return is ever credited to a new position.
    * Between rebalances weights DRIFT with returns (fully invested, no
      cash), so rebalance turnover is measured against drifted weights —
      realized turnover, not target-vs-target.
    * Costs: ``per_side_cost_bps x traded_fraction``, charged on the day the
      trade happens (via the shared ``apply_costs_to_period_returns``).
      Initial entry from cash is a full buy (traded fraction 1.0) — the
      replay never pretends the portfolio was free to begin with. No exit
      cost on the final mark (open positions are marked, not liquidated);
      the buy-and-hold baseline uses the same convention.
    * A held ticker missing a bar is a HARD error (fail closed) — a
      survivor-only panel with vendor gaps must be quarantined upstream,
      never silently zero-filled here.
    """
    if top_k <= 0 or rebalance_days <= 0:
        raise ValueError("top_k and rebalance_days must be positive")
    for col in ("date", "ticker", "score"):
        if col not in scores.columns:
            raise ValueError(f"scores frame lacks required column {col!r}")
    wide = _close_matrix(closes)
    scores = scores.copy()
    scores["date"] = pd.to_datetime(scores["date"])
    eval_dates = sorted(scores["date"].unique())
    if not eval_dates:
        raise ValueError("simulate_topk_net: no scored dates")
    missing_dates = [d for d in eval_dates if d not in wide.index]
    if missing_dates:
        raise ValueError(f"closes lack bars for scored dates: {missing_dates[:5]!r}")
    rebalance_set = set(eval_dates[::rebalance_days])

    weights: dict[str, float] = {}
    gross: list[float] = []
    traded: list[float] = []
    prev_date = None
    n_rebalances = 0
    for d in eval_dates:
        # 1) accrue the day's gross return on weights held since prev close
        if prev_date is None or not weights:
            gross.append(0.0)
        else:
            day_ret = 0.0
            new_weights: dict[str, float] = {}
            for tkr, w in weights.items():
                c0 = wide.at[prev_date, tkr]
                c1 = wide.at[d, tkr]
                if not (np.isfinite(c0) and np.isfinite(c1)):
                    raise ValueError(f"held ticker {tkr!r} missing close between {prev_date} and {d}")
                r = float(c1) / float(c0) - 1.0
                day_ret += w * r
                new_weights[tkr] = w * (1.0 + r)
            total = sum(new_weights.values())
            weights = {t: w / total for t, w in new_weights.items()} if total > 0 else {}
            gross.append(day_ret)
        # 2) rebalance at close of d
        if d in rebalance_set:
            day_scores = scores[scores["date"] == d].dropna(subset=["score"])
            ranked = day_scores.sort_values(["score", "ticker"], ascending=[False, True])
            chosen = ranked["ticker"].head(top_k).tolist()
            if not chosen:
                raise ValueError(f"no scored tickers at rebalance date {d}")
            target = {t: 1.0 / len(chosen) for t in chosen}
            breakdown = cost_model.turnover_breakdown(weights, target)
            traded.append(breakdown.traded_fraction)
            weights = target
            n_rebalances += 1
        else:
            traded.append(0.0)
        prev_date = d

    net = cost_model.apply_costs_to_period_returns(gross, traded, spec)
    rate = cost_model.per_side_cost_bps(spec) / 1e4
    return {
        "dates": [pd.Timestamp(d).date().isoformat() for d in eval_dates],
        "gross_returns": [float(g) for g in gross],
        "net_returns": [float(n) for n in net],
        "traded_fractions": [float(t) for t in traded],
        "gross_total_return": _compound(gross),
        "net_total_return": _compound(net),
        "total_cost_fraction": float(sum(rate * t for t in traded)),
        "n_rebalances": int(n_rebalances),
        "top_k": int(top_k),
        "rebalance_days": int(rebalance_days),
        "cost_spec": _spec_provenance(spec),
    }


# ---------------------------------------------------------------------------
# BTC baselines (§4.4) — asset-specific, never in shared code
# ---------------------------------------------------------------------------

def btc_buy_and_hold_net(btc_close: pd.Series, spec) -> dict:
    """Buy-and-hold BTC net of fees: one full entry on the first date.

    Same conventions as :func:`simulate_topk_net`: entry cost (traded 1.0)
    on day one, no exit cost on the final mark. The first period's return
    is 0 (position enters at the first close).
    """
    c = btc_close.sort_index().astype(float)
    if len(c) < 2:
        raise ValueError("btc_buy_and_hold_net: need at least 2 closes")
    gross = [0.0] + (c.to_numpy()[1:] / c.to_numpy()[:-1] - 1.0).tolist()
    traded = [1.0] + [0.0] * (len(gross) - 1)
    net = cost_model.apply_costs_to_period_returns(gross, traded, spec)
    return {
        "gross_total_return": _compound(gross),
        "net_total_return": _compound(net),
        "n_periods": len(gross),
        "cost_spec": _spec_provenance(spec),
    }


def btc_timing_rule_net(
    btc_close: pd.Series,
    spec,
    *,
    lookback_days: int = BTC_TIMING_LOOKBACK_CALENDAR_DAYS,
) -> dict:
    """Pre-registered naive BTC-timing baseline net of fees (§4.4).

    FROZEN rule: at each close D, be long BTC from D onward iff
    ``close[D] > close[D - lookback_days]`` with an EXACT calendar-day
    lookup; when the lookback bar is absent (warmup, vendor gap) the signal
    is FLAT — never a nearest-bar substitute. Position changes trade at the
    close of D (|Δw| = 1 per switch) and earn from D -> D+1; costs via the
    shared primitive. Secondary/descriptive baseline per §6.1 — Stage 2.5's
    sole primary baseline is buy-and-hold.
    """
    c = btc_close.sort_index().astype(float)
    if len(c) < 2:
        raise ValueError("btc_timing_rule_net: need at least 2 closes")
    lookback = c.reindex(c.index - pd.Timedelta(days=int(lookback_days)))
    signal = (c.to_numpy() > lookback.to_numpy()).astype(float)
    signal = np.where(np.isfinite(lookback.to_numpy()), signal, 0.0)

    gross: list[float] = [0.0]
    traded: list[float] = [abs(signal[0] - 0.0)]
    closes = c.to_numpy()
    for i in range(1, len(closes)):
        held = signal[i - 1]
        gross.append(held * (closes[i] / closes[i - 1] - 1.0))
        traded.append(abs(signal[i] - signal[i - 1]))
    net = cost_model.apply_costs_to_period_returns(gross, traded, spec)
    return {
        "rule": f"long iff trailing {int(lookback_days)}cd return > 0 (frozen)",
        "gross_total_return": _compound(gross),
        "net_total_return": _compound(net),
        "n_switches": int(sum(1 for t in traded if t > 0)),
        "cost_spec": _spec_provenance(spec),
    }


def crypto_promotion_diagnostic(
    strategy: dict,
    btc_hold: dict,
    btc_timing: Optional[dict] = None,
) -> dict:
    """§4.4 promotion bar, computed as a STAMPED DIAGNOSTIC — never an enable path.

    ``wf_promotion_bar_met`` is True iff the strategy's net-of-cost total
    return beats buy-and-hold BTC AND (when supplied) the naive timing rule,
    on the evaluated windows. It is tier-1, survivor-only evidence: Stage
    2.5 owns economic enablement and may not consume these numbers as
    thresholds (§6.1). A False here is a legitimate NO-GO signal for the
    model (§4.4: "the sleeve does not deserve a model") — also not
    auto-acted-on from this repo.
    """
    strat_net = float(strategy["net_total_return"])
    hold_net = float(btc_hold["net_total_return"])
    beats_hold = bool(strat_net > hold_net)
    out = {
        "diagnostic_only": True,
        "enable_path": False,
        "owner_of_enablement": "stage_2_5_prospective_evaluation (RFC §6/§6.1; operator + Codex gates)",
        "evidence_tier": "tier1_exploratory_survivor_only",
        "strategy_net_total_return": strat_net,
        "strategy_gross_total_return": float(strategy["gross_total_return"]),
        "btc_buy_and_hold_net_total_return": hold_net,
        "beats_btc_buy_and_hold_net": beats_hold,
    }
    if btc_timing is not None:
        timing_net = float(btc_timing["net_total_return"])
        out["btc_timing_net_total_return"] = timing_net
        out["beats_btc_timing_net"] = bool(strat_net > timing_net)
        out["wf_promotion_bar_met"] = bool(beats_hold and strat_net > timing_net)
    else:
        out["wf_promotion_bar_met"] = beats_hold
    return out


# ---------------------------------------------------------------------------
# Net-of-cost walk-forward evaluation (mirrors the gross CV's fold contract)
# ---------------------------------------------------------------------------

def net_of_cost_wf_evaluation(
    train: pd.DataFrame,
    feat_cols: list[str],
    closes: pd.DataFrame,
    *,
    normalization_builder,
    label: str,
    params: Optional[dict] = None,
    num_boost_round: int = 100,
    n_splits: int = 3,
    embargo_days: int = 20,
    spec=None,
    top_k: int = 5,
    rebalance_days: int = 20,
    btc_slug: str = DEFAULT_BTC_SLUG,
) -> dict:
    """Purged walk-forward NET-of-cost evaluation + BTC baselines (§4.4).

    Fold construction is IDENTICAL to
    :func:`renquant_model_gbdt.evaluate_walk_forward_cv` (expanding window,
    positional embargo on the sorted unique date axis — calendar days on a
    contiguous 24/7 store; per-fold train-only re-normalization via the
    injected builder). Each fold trains a booster, scores the validation
    window, replays the top-k strategy net of costs, and runs both BTC
    baselines on the SAME window. ``net = gross - cost_model(...)`` at the
    replay's realized turnover: a model that passes gross and fails net is
    a FAIL (RFC §4.4).

    Returns per-fold results plus a pooled verdict (folds compounded in
    time order) and the :func:`crypto_promotion_diagnostic` stamp.
    """
    import xgboost as xgb  # noqa: PLC0415

    from renquant_model_gbdt.panel_trainer import panel_training_matrix, train_xgb  # noqa: PLC0415

    if spec is None:
        spec = default_crypto_cost_spec()
    n_splits = max(1, int(n_splits))
    embargo_days = max(0, int(embargo_days))
    dates = np.array(sorted(pd.to_datetime(train["date"].unique())))
    if len(dates) < (n_splits + 1) * 5:
        raise ValueError(f"not enough dates for {n_splits} folds: {len(dates)}")

    wide = _close_matrix(closes)
    if btc_slug not in wide.columns:
        raise ValueError(
            f"net_of_cost_wf_evaluation: BTC baseline pair {btc_slug!r} absent from closes "
            f"(have {sorted(wide.columns.tolist())[:10]!r}...)"
        )

    fold_indices = np.array_split(np.arange(len(dates)), n_splits + 1)[1:]
    folds: list[dict] = []
    strat_returns_pooled: list[float] = []
    hold_returns_pooled: list[float] = []
    timing_returns_pooled: list[float] = []
    for fold_no, val_idx in enumerate(fold_indices, start=1):
        if len(val_idx) == 0:
            continue
        train_end_pos = int(val_idx[0]) - embargo_days
        if train_end_pos <= 0:
            log.warning("net WF fold %d skipped: embargo leaves no train dates", fold_no)
            continue
        tr_dates = set(dates[:train_end_pos])
        va_dates = dates[val_idx]
        tr = train[train["date"].isin(tr_dates)]
        va = train[train["date"].isin(set(va_dates))]
        if tr["date"].nunique() < 20 or va.empty:
            log.warning("net WF fold %d skipped: n_train_dates=%d n_val_rows=%d",
                        fold_no, tr["date"].nunique(), len(va))
            continue

        mu, sd, norm_kind, _, _ = normalization_builder(tr, feat_cols)
        booster, _ = train_xgb(
            tr, feat_cols, label=label, params=params, num_boost_round=num_boost_round,
            feature_means=mu, feature_stds=sd, feature_norm_kind=norm_kind,
        )
        Xva = panel_training_matrix(va, feat_cols, mu, sd, norm_kind)
        pred = booster.predict(xgb.DMatrix(Xva.values.astype(np.float64)))
        scored = pd.DataFrame({"date": va["date"].values, "ticker": va["ticker"].values,
                               "score": pred})

        strat = simulate_topk_net(scored, closes, spec, top_k=top_k,
                                  rebalance_days=rebalance_days)
        btc_window = wide[btc_slug].reindex(pd.DatetimeIndex(sorted(scored["date"].unique()))).dropna()
        hold = btc_buy_and_hold_net(btc_window, spec)
        # Timing rule on the same window: its first `lookback_days` are flat
        # by the frozen missing-lookback rule — conservative, no pre-window
        # information consumed inside a validation fold.
        timing = btc_timing_rule_net(btc_window, spec)
        folds.append({
            "fold": fold_no,
            "val_start": pd.Timestamp(va["date"].min()).date().isoformat(),
            "val_end": pd.Timestamp(va["date"].max()).date().isoformat(),
            "n_val_rows": int(len(va)),
            "strategy_gross_total_return": strat["gross_total_return"],
            "strategy_net_total_return": strat["net_total_return"],
            "strategy_total_cost_fraction": strat["total_cost_fraction"],
            "n_rebalances": strat["n_rebalances"],
            "btc_buy_and_hold_net_total_return": hold["net_total_return"],
            "btc_timing_net_total_return": timing["net_total_return"],
        })
        strat_returns_pooled.append(strat["net_total_return"])
        hold_returns_pooled.append(hold["net_total_return"])
        timing_returns_pooled.append(timing["net_total_return"])

    if not folds:
        raise ValueError("net-of-cost WF evaluation produced no usable folds")
    pooled_strategy = {"net_total_return": _compound(strat_returns_pooled),
                       "gross_total_return": float("nan")}
    # gross pooled: recompound fold gross totals for the diagnostic stamp
    pooled_strategy["gross_total_return"] = _compound(
        [f["strategy_gross_total_return"] for f in folds])
    pooled_hold = {"net_total_return": _compound(hold_returns_pooled)}
    pooled_timing = {"net_total_return": _compound(timing_returns_pooled)}
    diagnostic = crypto_promotion_diagnostic(pooled_strategy, pooled_hold, pooled_timing)
    result = {
        "method": "purged_walk_forward_net_of_cost",
        "n_splits": n_splits,
        "embargo_days": embargo_days,
        "embargo_axis": "utc_calendar_days (positional on the contiguous 24/7 date axis)",
        "top_k": int(top_k),
        "rebalance_days": int(rebalance_days),
        "btc_slug": btc_slug,
        "cost_spec": _spec_provenance(spec),
        "folds": folds,
        "pooled_strategy_net_total_return": pooled_strategy["net_total_return"],
        "pooled_btc_buy_and_hold_net_total_return": pooled_hold["net_total_return"],
        "pooled_btc_timing_net_total_return": pooled_timing["net_total_return"],
        "promotion_diagnostic": diagnostic,
    }
    if not math.isfinite(result["pooled_strategy_net_total_return"]):
        raise ValueError("net-of-cost WF evaluation produced a non-finite pooled return")
    return result
