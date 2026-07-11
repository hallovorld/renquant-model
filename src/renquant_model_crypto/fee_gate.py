"""Fee-aware net-of-cost WF evaluation + BTC baselines (crypto RFC D-C8b, M1).

Model-side, asset-SPECIFIC half of the D-C8 split (RFC §4.4 / §9.3): the
crypto taker-fee default, the BTC-baseline comparisons and the crypto
promotion DIAGNOSTIC live here; the generic cost-accounting math is the
shared ``renquant_common.cost_model`` primitive (D-C8a).

HARD dependency, no fallback (Codex review, model#43 r2): the r1 local
fallback copy is REMOVED. This module requires renquant-common>=0.12.0
(the release shipping ``cost_model``) and fails closed at import when it is
absent — a net-of-cost verdict must come from the ONE shared primitive, or
the WF gate and runtime accounting could silently drift.

Measured-cost requirement (Codex review, model#43 r2): the gate emits a
NET verdict ONLY with a stamped, attested, Stage-0-MEASURED cost spec
(:func:`validate_cost_attestation`). The 25 bps taker default below is a
[GUESS] research constant — the gate refuses to turn it (or any other
unattested number) into a net verdict; without attestation it emits
GROSS-ONLY diagnostics, explicitly labeled. Every emitted spec is stamped
with its canonical content identity
(``cost_model_content_sha256`` + schema version) so any net figure is
traceable to the exact cost identity that produced it.

Execution convention (Codex review, model#43 r2 — THE lookahead fix):
scores at bar D consume information up to and including bar D's close;
that close is only observable at ``D+1 00:00 UTC``. A replay that fills at
bar D's own close therefore trades at a price inside its information set.
The frozen feasible convention here: a decision made from bar D fills at
the close of bar ``D + execution_delay_bars`` (default 1 — the next
observable daily mark), the delay period's return accrues to the PRE-fill
book, and turnover costs are charged on the fill bar. The regression test
(``tests/crypto/test_fee_gate.py::TestExecutionDelay``) pins that changing
a decision bar's close cannot alter the replay's fill accounting.

The "beat buy-and-hold BTC (and the naive BTC-timing rule) net of fees"
promotion bar (§4.4) is computed as a **stamped diagnostic on tier-1
survivor-only evidence — NOT an enable path**, and is additionally marked
``decision_grade: false`` until a Stage-0-calibrated spec AND prospective
evaluation (Stage 1/2/2.5) exist. Nothing in this repo flips a sleeve on.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("renquant_model_crypto.fee_gate")

# --- D-C8a HARD dependency (fail closed; no fallback by design) -------------
try:
    from renquant_common import cost_model
except ImportError as exc:  # pragma: no cover - exercised only in stale envs
    raise ImportError(
        "renquant_model_crypto requires renquant_common.cost_model (crypto RFC "
        "D-C8a, renquant-common>=0.12.0 — common#28). No local fallback exists "
        "by design (Codex review, model#43 r2): net-of-cost math must be the "
        "ONE shared primitive or WF-gate replay and runtime accounting could "
        "silently drift. Sync/upgrade the renquant-common checkout/install."
    ) from exc

#: Alpaca crypto tier-0 taker fee, bps per side. [GUESS: RFC §2.7 — not
#: verifiable from the SDK. RESEARCH CONSTANT ONLY: the gate REFUSES to emit
#: a net verdict from this (or any) unattested number; the Stage-0 paper
#: battery measures the real schedule from fill receipts and its stamped,
#: attested spec is the only net-verdict input. Never hardcode this into
#: shared code (D-C8a boundary).]
CRYPTO_TAKER_FEE_BPS_DEFAULT = 25.0

#: Pre-registered naive BTC-timing rule (§4.4 secondary baseline): long BTC
#: iff the trailing N-calendar-day return is positive, else cash. FROZEN
#: here before any WF evidence; not tunable per-run (a swept baseline is no
#: baseline).
BTC_TIMING_LOOKBACK_CALENDAR_DAYS = 20

DEFAULT_BTC_SLUG = "BTC-USD"

#: Frozen feasible execution convention: decisions fill at the NEXT
#: observable daily mark. 0 is rejected everywhere — it re-introduces the
#: same-bar-fill lookahead this convention exists to kill.
DEFAULT_EXECUTION_DELAY_BARS = 1

#: Attestation sources the gate accepts as MEASURED (RFC §4.4 calibration
#: source split: paper-battery fill receipts, then realized live-canary
#: fills under the frozen monotone update rule).
MEASURED_COST_SOURCES = ("stage0_battery", "live_canary")

NET_VERDICT_EMITTED = "emitted"
NET_VERDICT_WITHHELD = "withheld_unmeasured_cost_spec"


def default_crypto_cost_spec():
    """Fee-only crypto cost spec at the [GUESS] taker default — RESEARCH ONLY.

    The net-of-cost gate will NOT accept this as a measured input: without a
    valid :func:`validate_cost_attestation` payload the gate emits
    gross-only diagnostics. Fee-only mirrors the RFC's frozen fee-only
    convention (§6.1's ``RT_friction_fee_only``); the real spec is
    instantiated ONCE from the Stage-0 battery.
    """
    return cost_model.CostModelSpec(fee_bps=CRYPTO_TAKER_FEE_BPS_DEFAULT)


def validate_cost_attestation(attestation: Mapping[str, Any]) -> dict:
    """Validate a measured-cost attestation; return its canonical dict.

    Required shape: ``{"source": <one of MEASURED_COST_SOURCES>,
    "measured_at": <ISO date>, "evidence_ref": <non-empty str>}`` — the
    Stage-0 battery report (or live-canary re-estimate memo) the numbers
    came from. Malformed attestations are a HARD error (fail closed), never
    downgraded to gross-only: a caller who *tried* to attest and got the
    shape wrong must find out, not silently lose the net verdict.
    """
    if not isinstance(attestation, Mapping):
        raise ValueError(
            f"cost attestation must be a mapping, got {type(attestation).__name__!r}"
        )
    source = attestation.get("source")
    if source not in MEASURED_COST_SOURCES:
        raise ValueError(
            f"cost attestation source must be one of {list(MEASURED_COST_SOURCES)}, "
            f"got {source!r}"
        )
    measured_at = attestation.get("measured_at")
    try:
        measured_ts = pd.Timestamp(measured_at)
        if pd.isna(measured_ts):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(
            f"cost attestation measured_at must be an ISO date, got {measured_at!r}"
        ) from None
    evidence_ref = attestation.get("evidence_ref")
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise ValueError(
            "cost attestation evidence_ref must be a non-empty string naming the "
            f"battery report / memo, got {evidence_ref!r}"
        )
    extras = sorted(set(attestation) - {"source", "measured_at", "evidence_ref"})
    if extras:
        raise ValueError(f"cost attestation has unknown field(s): {extras}")
    return {
        "source": str(source),
        "measured_at": measured_ts.date().isoformat(),
        "evidence_ref": evidence_ref.strip(),
    }


def _spec_provenance(spec: Any, attestation: Optional[dict]) -> dict:
    """Canonical cost-spec identity stamp (Codex review: stamped everywhere).

    Carries the spec's full serialized components, its
    ``cost_model_content_sha256`` identity + schema version (verifier flow:
    ``cost_model_content_sha256(cost_model_spec_from_dict(cost_spec))``),
    the attestation (or its absence), and whether the fee equals the
    [GUESS] research default.
    """
    return {
        "cost_spec": spec.to_dict(),
        "cost_spec_sha256": cost_model.cost_model_content_sha256(spec),
        "cost_model_fingerprint_schema_version": (
            cost_model.COST_MODEL_FINGERPRINT_SCHEMA_VERSION),
        "per_side_cost_bps": float(cost_model.per_side_cost_bps(spec)),
        "round_trip_cost_bps": float(cost_model.round_trip_cost_bps(spec)),
        "fee_default_status": (
            "GUESS_stage0_verifies" if float(spec.fee_bps) == CRYPTO_TAKER_FEE_BPS_DEFAULT
            else "caller_supplied"
        ),
        "attestation": dict(attestation) if attestation else None,
        "cost_model_impl": "renquant_common.cost_model",
    }


def _compound(returns: list[float]) -> float:
    total = 1.0
    for r in returns:
        total *= 1.0 + r
    return total - 1.0


def _return_stats(returns: list[float]) -> dict:
    arr = np.asarray(returns, dtype=float)
    return {
        "n_periods": int(arr.size),
        "mean_daily_return": float(arr.mean()) if arr.size else float("nan"),
        "std_daily_return": float(arr.std(ddof=1)) if arr.size > 1 else float("nan"),
    }


def _close_matrix(closes: pd.DataFrame) -> pd.DataFrame:
    for col in ("date", "ticker", "close"):
        if col not in closes.columns:
            raise ValueError(f"closes frame lacks required column {col!r}")
    wide = closes.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    wide.index = pd.DatetimeIndex(pd.to_datetime(wide.index)).sort_values()
    return wide.sort_index()


def _execution_convention(delay: int) -> dict:
    return {
        "observable_cutoff": (
            "scores at bar D consume bars <= D close, observable at D+1 00:00 UTC "
            "(RFC §3.5 watermark)"
        ),
        "fill": (
            f"close of bar D+{delay} — the next observable daily mark; the delay "
            "period's return accrues to the PRE-fill book; turnover costs are "
            "charged on the fill bar"
        ),
        "execution_delay_bars": int(delay),
        "lookahead_regression_test": (
            "tests/crypto/test_fee_gate.py::TestExecutionDelay"
        ),
    }


# ---------------------------------------------------------------------------
# Strategy replay: top-k equal-weight, periodic rebalance, delayed fills
# ---------------------------------------------------------------------------

def simulate_topk_net(
    scores: pd.DataFrame,
    closes: pd.DataFrame,
    spec,
    *,
    top_k: int = 5,
    rebalance_days: int = 20,
    execution_delay_bars: int = DEFAULT_EXECUTION_DELAY_BARS,
) -> dict:
    """Replay a top-k equal-weight strategy with FEASIBLE delayed fills.

    Frozen replay semantics (consumers/tests pin these):

    * ``scores``: long frame ``[date, ticker, score]``. Decisions happen on
      every ``rebalance_days``-th scored date, starting at the first.
    * **Execution delay (lookahead fix, r2)**: a decision made from bar D's
      scores fills at the close of bar ``D + execution_delay_bars``
      (default 1). The delay period's return accrues to the PRE-fill book;
      a decision whose fill bar lies beyond the window EXPIRES unexecuted
      (zero cost, zero position change, counted). ``execution_delay_bars``
      must be >= 1 — a same-bar fill would trade at a price inside the
      decision's information set.
    * Between fills weights DRIFT with returns (fully invested, no cash);
      fill turnover is measured against drifted weights — realized
      turnover, not target-vs-target.
    * Costs: ``per_side_cost_bps x traded_fraction``, charged on the fill
      bar (via the shared ``apply_costs_to_period_returns``). The initial
      entry from cash is a full buy (traded fraction 1.0). No exit cost on
      the final mark (open positions are marked, not liquidated); the
      buy-and-hold baseline uses the same convention.
    * A held ticker missing a bar is a HARD error (fail closed) — a
      survivor-only panel with vendor gaps must be quarantined upstream,
      never silently zero-filled here.
    """
    if top_k <= 0 or rebalance_days <= 0:
        raise ValueError("top_k and rebalance_days must be positive")
    delay = int(execution_delay_bars)
    if delay < 1:
        raise ValueError(
            "execution_delay_bars must be >= 1: a same-bar fill trades at a price "
            "inside the decision's information set (Codex review, model#43 r2)"
        )
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
    decision_indices = set(range(0, len(eval_dates), rebalance_days))

    weights: dict[str, float] = {}
    pending: dict[int, dict[str, float]] = {}  # fill index -> target weights
    gross: list[float] = []
    traded: list[float] = []
    fill_dates: list[str] = []
    prev_date = None
    n_decisions = 0
    n_fills = 0
    for j, d in enumerate(eval_dates):
        # 1) accrue the period's gross return on the pre-fill book
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
        # 2) execute any fill scheduled for this bar (against drifted weights)
        if j in pending:
            target = pending.pop(j)
            breakdown = cost_model.turnover_breakdown(weights, target)
            traded.append(breakdown.traded_fraction)
            weights = target
            n_fills += 1
            fill_dates.append(pd.Timestamp(d).date().isoformat())
        else:
            traded.append(0.0)
        # 3) record a new decision from THIS bar's scores (fills at j+delay;
        #    delay >= 1 means a decision can never fill at its own bar)
        if j in decision_indices:
            day_scores = scores[scores["date"] == d].dropna(subset=["score"])
            ranked = day_scores.sort_values(["score", "ticker"], ascending=[False, True])
            chosen = ranked["ticker"].head(top_k).tolist()
            if not chosen:
                raise ValueError(f"no scored tickers at decision date {d}")
            n_decisions += 1
            if j + delay < len(eval_dates):
                pending[j + delay] = {t: 1.0 / len(chosen) for t in chosen}
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
        "n_decisions": int(n_decisions),
        "n_rebalances": int(n_fills),
        "n_expired_decisions": int(n_decisions - n_fills),
        "fill_dates": fill_dates,
        "top_k": int(top_k),
        "rebalance_days": int(rebalance_days),
        "execution_convention": _execution_convention(delay),
    }


# ---------------------------------------------------------------------------
# BTC baselines (§4.4) — asset-specific, never in shared code
# ---------------------------------------------------------------------------

def btc_buy_and_hold_net(btc_close: pd.Series, spec) -> dict:
    """Buy-and-hold BTC net of fees: one full entry on the first date.

    No execution delay: buy-and-hold conditions on NOTHING (no bar's close
    enters any decision), so entering at the first close consumes no
    information. This also leaves the baseline fully invested from bar 0
    while the delayed-fill strategy starts at bar 1+ — conservative AGAINST
    the strategy. Same no-exit-cost-on-final-mark convention as the replay.
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
    }


def btc_timing_rule_net(
    btc_close: pd.Series,
    spec,
    *,
    lookback_days: int = BTC_TIMING_LOOKBACK_CALENDAR_DAYS,
    execution_delay_bars: int = DEFAULT_EXECUTION_DELAY_BARS,
) -> dict:
    """Pre-registered naive BTC-timing baseline net of fees (§4.4).

    FROZEN rule: the signal at close D is long iff
    ``close[D] > close[D - lookback_days]`` (EXACT calendar-day lookup;
    missing lookback bar ⇒ flat — never a nearest-bar substitute). The
    signal CONDITIONS on close D, so it takes the SAME feasible execution
    delay as the strategy replay (r2 lookahead fix): the position decided
    at close D fills at close ``D + execution_delay_bars`` and earns from
    the following period; switch turnover (|Δw| = 1) is charged on the fill
    bar. Secondary/descriptive baseline per §6.1 — Stage 2.5's sole primary
    baseline is buy-and-hold.
    """
    delay = int(execution_delay_bars)
    if delay < 1:
        raise ValueError(
            "execution_delay_bars must be >= 1 (same feasibility rule as the "
            "strategy replay — the signal conditions on the decision bar's close)"
        )
    c = btc_close.sort_index().astype(float)
    if len(c) < 2:
        raise ValueError("btc_timing_rule_net: need at least 2 closes")
    lookback = c.reindex(c.index - pd.Timedelta(days=int(lookback_days)))
    signal = (c.to_numpy() > lookback.to_numpy()).astype(float)
    signal = np.where(np.isfinite(lookback.to_numpy()), signal, 0.0)

    n = len(c)
    # position effective as of close i = the signal decided `delay` bars ago
    position = np.zeros(n)
    for i in range(n):
        position[i] = signal[i - delay] if i - delay >= 0 else 0.0
    gross: list[float] = [0.0]
    traded: list[float] = [abs(position[0] - 0.0)]
    closes = c.to_numpy()
    for i in range(1, n):
        held = position[i - 1]  # book set at the previous close
        gross.append(held * (closes[i] / closes[i - 1] - 1.0))
        traded.append(abs(position[i] - position[i - 1]))
    net = cost_model.apply_costs_to_period_returns(gross, traded, spec)
    return {
        "rule": f"long iff trailing {int(lookback_days)}cd return > 0 (frozen)",
        "gross_total_return": _compound(gross),
        "net_total_return": _compound(net),
        "n_switches": int(sum(1 for t in traded if t > 0)),
        "execution_convention": _execution_convention(delay),
    }


def crypto_promotion_diagnostic(
    strategy: dict,
    btc_hold: dict,
    btc_timing: Optional[dict] = None,
) -> dict:
    """§4.4 promotion bar, computed as a STAMPED DIAGNOSTIC — never an enable path.

    ``wf_promotion_bar_met`` is True iff the strategy's net-of-cost total
    return beats buy-and-hold BTC AND (when supplied) the naive timing rule,
    on the evaluated windows. It is tier-1, survivor-only evidence and
    explicitly ``decision_grade: false``: Stage 2.5 owns economic
    enablement and may not consume these numbers as thresholds (§6.1). A
    False here is a legitimate NO-GO signal for the model (§4.4) — also not
    auto-acted-on from this repo.
    """
    strat_net = float(strategy["net_total_return"])
    hold_net = float(btc_hold["net_total_return"])
    beats_hold = bool(strat_net > hold_net)
    out = {
        "diagnostic_only": True,
        "enable_path": False,
        "decision_grade": False,
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
    cost_attestation: Optional[Mapping[str, Any]] = None,
    top_k: int = 5,
    rebalance_days: int = 20,
    execution_delay_bars: int = DEFAULT_EXECUTION_DELAY_BARS,
    btc_slug: str = DEFAULT_BTC_SLUG,
) -> dict:
    """Purged walk-forward net-of-cost (or gross-only) evaluation (§4.4).

    Fold construction is IDENTICAL to
    :func:`renquant_model_gbdt.evaluate_walk_forward_cv` (expanding window,
    positional embargo on the sorted unique date axis — calendar days on a
    contiguous 24/7 store; per-fold train-only re-normalization via the
    injected builder). Each fold trains a booster, scores the validation
    window, replays the top-k strategy with the frozen delayed-fill
    convention, and runs both BTC baselines on the SAME window.

    **Net-verdict gating (r2)**: a NET verdict is emitted ONLY when
    ``cost_attestation`` validates as a MEASURED source
    (:func:`validate_cost_attestation`) and ``spec`` is the attested,
    caller-supplied spec. Without an attestation the evaluation runs
    GROSS-ONLY (zero-cost replay; turnover still reported), the result is
    labeled ``net_verdict_status: withheld_unmeasured_cost_spec`` and NO
    promotion verdict is computed — a [GUESS] fee default can never become
    a net number (Codex review, model#43 r2). A malformed attestation is a
    hard error, never a silent downgrade; an unattested spec is likewise a
    hard error (the caller must choose: attest it or drop it).

    Every result is stamped ``decision_grade: false`` with explicit
    reasons: tier-1 survivor-only panel, and (until Stage 0/1/2/2.5) no
    calibrated friction bounds + no prospective evidence.
    """
    import xgboost as xgb  # noqa: PLC0415

    from renquant_model_gbdt.panel_trainer import panel_training_matrix, train_xgb  # noqa: PLC0415

    attestation: Optional[dict] = None
    if cost_attestation is not None:
        attestation = validate_cost_attestation(cost_attestation)
        if spec is None:
            raise ValueError(
                "net_of_cost_wf_evaluation: a cost attestation was supplied without "
                "the attested spec — pass the measured CostModelSpec explicitly"
            )
        net_verdict_status = NET_VERDICT_EMITTED
        replay_spec = spec
    else:
        if spec is not None:
            raise ValueError(
                "net_of_cost_wf_evaluation: a cost spec without a measured attestation "
                "cannot produce a net verdict (Codex review, model#43 r2). Either "
                "attest the spec (validate_cost_attestation shape) or omit it for a "
                "labeled gross-only evaluation."
            )
        net_verdict_status = NET_VERDICT_WITHHELD
        replay_spec = cost_model.CostModelSpec()  # zero-cost: gross-only replay

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
    strat_totals: list[float] = []
    strat_gross_totals: list[float] = []
    hold_totals: list[float] = []
    timing_totals: list[float] = []
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

        strat = simulate_topk_net(scored, closes, replay_spec, top_k=top_k,
                                  rebalance_days=rebalance_days,
                                  execution_delay_bars=execution_delay_bars)
        btc_window = wide[btc_slug].reindex(pd.DatetimeIndex(sorted(scored["date"].unique()))).dropna()
        hold = btc_buy_and_hold_net(btc_window, replay_spec)
        # Timing rule on the same window: warmup is flat by the frozen
        # missing-lookback rule — no pre-window information enters a fold.
        timing = btc_timing_rule_net(btc_window, replay_spec,
                                     execution_delay_bars=execution_delay_bars)
        active_returns = (strat["net_returns"] if net_verdict_status == NET_VERDICT_EMITTED
                          else strat["gross_returns"])
        fold_record = {
            "fold": fold_no,
            "val_start": pd.Timestamp(va["date"].min()).date().isoformat(),
            "val_end": pd.Timestamp(va["date"].max()).date().isoformat(),
            "n_val_rows": int(len(va)),
            "n_val_dates": int(va["date"].nunique()),
            "n_decisions": strat["n_decisions"],
            "n_rebalances": strat["n_rebalances"],
            "n_expired_decisions": strat["n_expired_decisions"],
            "strategy_gross_total_return": strat["gross_total_return"],
            "btc_buy_and_hold_gross_total_return": hold["gross_total_return"],
            "btc_timing_gross_total_return": timing["gross_total_return"],
            "return_stats": _return_stats(active_returns),
        }
        if net_verdict_status == NET_VERDICT_EMITTED:
            fold_record.update({
                "strategy_net_total_return": strat["net_total_return"],
                "strategy_total_cost_fraction": strat["total_cost_fraction"],
                "btc_buy_and_hold_net_total_return": hold["net_total_return"],
                "btc_timing_net_total_return": timing["net_total_return"],
            })
            strat_totals.append(strat["net_total_return"])
            hold_totals.append(hold["net_total_return"])
            timing_totals.append(timing["net_total_return"])
        else:
            strat_totals.append(strat["gross_total_return"])
            hold_totals.append(hold["gross_total_return"])
            timing_totals.append(timing["gross_total_return"])
        strat_gross_totals.append(strat["gross_total_return"])
        folds.append(fold_record)

    if not folds:
        raise ValueError("net-of-cost WF evaluation produced no usable folds")

    def _dispersion(values: list[float]) -> float:
        return float(np.std(values, ddof=1)) if len(values) > 1 else float("nan")

    decision_grade_reasons = [
        "tier1_exploratory_survivor_only_panel (RFC §4.6 — historical WF evidence "
        "is survivor-biased by construction; tier-2 prospective evidence is the "
        "decision-grade path)",
        "no_prospective_evaluation_yet (Stage 1 shadow / Stage 2 canary / Stage 2.5 "
        "block evaluation pending)",
    ]
    if net_verdict_status == NET_VERDICT_WITHHELD:
        decision_grade_reasons.insert(
            0, "unmeasured_cost_spec (Stage-0 battery has not produced an attested spec)")
    else:
        decision_grade_reasons.insert(
            1, "cost_spec_covers_measured_components_only (ex-ante spread/slippage/"
               "gap bounds per RFC §4.4 land with the full Stage-0 report)")

    result = {
        "method": "purged_walk_forward_net_of_cost",
        "grade": ("net_of_cost" if net_verdict_status == NET_VERDICT_EMITTED
                  else "gross_only_diagnostic"),
        "net_verdict_status": net_verdict_status,
        "decision_grade": False,
        "decision_grade_reasons": decision_grade_reasons,
        "n_splits": n_splits,
        "n_folds_evaluated": len(folds),
        "embargo_days": embargo_days,
        "embargo_axis": "utc_calendar_days (positional on the contiguous 24/7 date axis)",
        "top_k": int(top_k),
        "rebalance_days": int(rebalance_days),
        "execution_convention": _execution_convention(int(execution_delay_bars)),
        "btc_slug": btc_slug,
        "folds": folds,
        "fold_total_return_dispersion": _dispersion(strat_totals),
        "pooled_strategy_gross_total_return": _compound(strat_gross_totals),
    }
    if net_verdict_status == NET_VERDICT_EMITTED:
        pooled_strategy = {
            "net_total_return": _compound(strat_totals),
            "gross_total_return": _compound(strat_gross_totals),
        }
        pooled_hold = {"net_total_return": _compound(hold_totals)}
        pooled_timing = {"net_total_return": _compound(timing_totals)}
        result.update({
            "cost_spec_provenance": _spec_provenance(replay_spec, attestation),
            "pooled_strategy_net_total_return": pooled_strategy["net_total_return"],
            "pooled_btc_buy_and_hold_net_total_return": pooled_hold["net_total_return"],
            "pooled_btc_timing_net_total_return": pooled_timing["net_total_return"],
            "promotion_diagnostic": crypto_promotion_diagnostic(
                pooled_strategy, pooled_hold, pooled_timing),
        })
        if not math.isfinite(result["pooled_strategy_net_total_return"]):
            raise ValueError("net-of-cost WF evaluation produced a non-finite pooled return")
    else:
        result.update({
            "cost_spec_provenance": None,
            "pooled_btc_buy_and_hold_gross_total_return": _compound(hold_totals),
            "pooled_btc_timing_gross_total_return": _compound(timing_totals),
            "promotion_diagnostic": {
                "status": NET_VERDICT_WITHHELD,
                "diagnostic_only": True,
                "enable_path": False,
                "decision_grade": False,
                "note": (
                    "no net verdict without a Stage-0-measured, attested cost spec "
                    "(Codex review, model#43 r2); gross-only figures above are "
                    "labeled diagnostics, not a promotion input"
                ),
            },
        })
    return result
