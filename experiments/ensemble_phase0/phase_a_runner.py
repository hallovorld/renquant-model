"""Phase A discovery runner for the ensemble combination experiment.

Compares L1 (equal-weight combination of admitted experts) against the
frozen champion (first-listed expert used alone) on the same score-to-
portfolio mapping, using point-in-time scores that have passed the
admissibility ledger.

This is RESEARCH-ONLY tooling. It does not touch production paths,
place orders, or modify any live state.

Design reference: doc/research/2026-07-12-ensemble-combination-experiment.md
  - §3.1  L1 equal-weight combination
  - §4.4  Evaluation and statistical test
  - §4.5  Go/no-go decision tree
  - §5.2  Phase A scope

Usage::

    python -m experiments.ensemble_phase0.phase_a_runner \\
        --expert xgb --score-dir /path/to/xgb/scores \\
        --expert patchtst --score-dir /path/to/patchtst/scores \\
        --returns-file /path/to/forward_returns.csv \\
        --output-dir experiments/ensemble_phase0/output/phase_a \\
        --top-n 10
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class ExpertScores:
    """Per-date scores from one expert."""

    name: str
    dates: list[str] = field(default_factory=list)
    scores_by_date: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class PortfolioReturn:
    """Single-date portfolio return."""

    date: str
    selected_tickers: list[str]
    portfolio_return: float
    score_ic: float


@dataclass
class StrategyResult:
    """Evaluation result for one strategy (L1 or champion)."""

    name: str
    n_dates: int = 0
    mean_ic: float = float("nan")
    mean_return: float = float("nan")
    sharpe: float = float("nan")
    hit_rate: float = float("nan")
    mean_turnover: float = float("nan")
    daily_returns: list[float] = field(default_factory=list)
    daily_ics: list[float] = field(default_factory=list)


@dataclass
class PhaseAResult:
    """Complete Phase A discovery result."""

    run_id: str = ""
    timestamp: str = ""
    champion: StrategyResult = field(default_factory=lambda: StrategyResult("champion"))
    l1: StrategyResult = field(default_factory=lambda: StrategyResult("l1"))
    n_experts: int = 0
    expert_names: list[str] = field(default_factory=list)
    n_dates: int = 0
    top_n: int = 10
    delta_ic: float = float("nan")
    delta_return: float = float("nan")
    delta_sharpe: float = float("nan")
    p_value: float = float("nan")
    t_statistic: float = float("nan")
    effect_size: float = float("nan")
    verdict: str = "INCONCLUSIVE"
    verdict_detail: str = ""


# ── Score loading ────────────────────────────────────────────────────────────


def load_expert_scores(name: str, score_dir: Path) -> ExpertScores:
    """Load all date-named JSON score files from a directory.

    Each file is expected to have a ``scores`` dict mapping ticker
    symbols to numeric values. Files without ``scores`` are skipped.
    """
    expert = ExpertScores(name=name)

    if not score_dir.is_dir():
        raise FileNotFoundError(f"Score directory not found: {score_dir}")

    for path in sorted(score_dir.glob("*.json")):
        stem = path.stem
        if len(stem) != 10:
            continue
        try:
            data = json.loads(path.read_bytes())
        except (json.JSONDecodeError, OSError):
            continue

        scores = data.get("scores", {})
        if not isinstance(scores, dict) or not scores:
            continue

        clean: dict[str, float] = {}
        for ticker, val in scores.items():
            if isinstance(val, (int, float)) and math.isfinite(val):
                clean[ticker] = float(val)

        if clean:
            expert.dates.append(stem)
            expert.scores_by_date[stem] = clean

    return expert


def load_forward_returns(path: Path) -> dict[str, dict[str, float]]:
    """Load forward returns CSV: columns = date, ticker, fwd_return.

    Returns ``{date: {ticker: return}}``.
    """
    returns: dict[str, dict[str, float]] = defaultdict(dict)

    with open(path) as f:
        header = f.readline().strip().split(",")
        date_col = _find_col(header, ["date", "prediction_date"])
        ticker_col = _find_col(header, ["ticker", "symbol"])
        ret_col = _find_col(header, ["fwd_return", "forward_return", "return", "fwd_60d"])

        for line in f:
            parts = line.strip().split(",")
            if len(parts) <= max(date_col, ticker_col, ret_col):
                continue
            try:
                d = parts[date_col].strip()
                t = parts[ticker_col].strip()
                r = float(parts[ret_col].strip())
                if math.isfinite(r):
                    returns[d][t] = r
            except (ValueError, IndexError):
                continue

    return dict(returns)


def _find_col(header: list[str], candidates: list[str]) -> int:
    lower = [h.lower().strip() for h in header]
    for c in candidates:
        if c.lower() in lower:
            return lower.index(c.lower())
    raise ValueError(f"No column found matching {candidates} in {header}")


# ── Combination methods ──────────────────────────────────────────────────────


def l1_equal_weight(
    experts: list[ExpertScores],
    date: str,
) -> dict[str, float]:
    """Compute equal-weight average of expert scores for a date."""
    combined: dict[str, list[float]] = defaultdict(list)

    for expert in experts:
        scores = expert.scores_by_date.get(date, {})
        for ticker, val in scores.items():
            combined[ticker].append(val)

    return {
        ticker: sum(vals) / len(vals)
        for ticker, vals in combined.items()
        if len(vals) == len(experts)
    }


def champion_scores(
    champion_expert: ExpertScores,
    date: str,
) -> dict[str, float]:
    """Return the champion (first expert) scores for a date."""
    return dict(champion_expert.scores_by_date.get(date, {}))


# ── Portfolio mapping ────────────────────────────────────────────────────────


def top_n_selection(
    scores: dict[str, float],
    n: int,
) -> list[str]:
    """Select top-N tickers by score (highest first)."""
    if not scores:
        return []
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [t for t, _ in ranked[:n]]


# ── Evaluation ───────────────────────────────────────────────────────────────


def compute_ic(
    scores: dict[str, float],
    returns: dict[str, float],
) -> float:
    """Rank IC (Spearman) between scores and forward returns."""
    common = sorted(set(scores) & set(returns))
    if len(common) < 5:
        return float("nan")

    s = [scores[t] for t in common]
    r = [returns[t] for t in common]

    result = stats.spearmanr(s, r)
    corr = result.statistic if hasattr(result, "statistic") else result[0]
    return float(corr) if math.isfinite(corr) else float("nan")


def compute_portfolio_return(
    selected: list[str],
    returns: dict[str, float],
) -> float:
    """Equal-weight portfolio return from selected tickers."""
    if not selected:
        return 0.0
    rets = [returns.get(t, 0.0) for t in selected]
    return sum(rets) / len(rets)


def compute_turnover(
    prev_portfolio: list[str],
    curr_portfolio: list[str],
) -> float:
    """Fraction of portfolio that changed."""
    if not prev_portfolio and not curr_portfolio:
        return 0.0
    if not prev_portfolio or not curr_portfolio:
        return 1.0
    prev_set = set(prev_portfolio)
    curr_set = set(curr_portfolio)
    n = max(len(prev_set), len(curr_set))
    changed = len(prev_set.symmetric_difference(curr_set))
    return changed / (2 * n) if n > 0 else 0.0


def evaluate_strategy(
    name: str,
    score_fn,
    dates: list[str],
    forward_returns: dict[str, dict[str, float]],
    top_n: int,
) -> StrategyResult:
    """Evaluate a strategy across all dates."""
    result = StrategyResult(name=name)
    daily_rets: list[float] = []
    daily_ics: list[float] = []
    turnovers: list[float] = []
    prev_portfolio: list[str] = []

    for dt in dates:
        scores = score_fn(dt)
        if not scores:
            continue
        rets = forward_returns.get(dt, {})
        if not rets:
            continue

        ic = compute_ic(scores, rets)
        portfolio = top_n_selection(scores, top_n)
        port_ret = compute_portfolio_return(portfolio, rets)
        turnover = compute_turnover(prev_portfolio, portfolio)

        daily_rets.append(port_ret)
        daily_ics.append(ic)
        turnovers.append(turnover)
        prev_portfolio = portfolio

    result.n_dates = len(daily_rets)
    result.daily_returns = daily_rets
    result.daily_ics = daily_ics

    if daily_rets:
        valid_ics = [ic for ic in daily_ics if math.isfinite(ic)]
        result.mean_ic = np.mean(valid_ics) if valid_ics else float("nan")
        result.mean_return = float(np.mean(daily_rets))
        std = float(np.std(daily_rets, ddof=1)) if len(daily_rets) > 1 else 0.0
        result.sharpe = (result.mean_return / std) if std > 0 else float("nan")
        result.hit_rate = sum(1 for r in daily_rets if r > 0) / len(daily_rets)
        result.mean_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    return result


# ── Statistical test ─────────────────────────────────────────────────────────


def newey_west_t_test(
    x: list[float],
    y: list[float],
    max_lag: int | None = None,
) -> tuple[float, float]:
    """Paired t-test with Newey-West HAC standard errors.

    Tests H1: mean(x) > mean(y) (one-sided).
    Returns (t_statistic, p_value).
    """
    if len(x) != len(y) or len(x) < 3:
        return (float("nan"), float("nan"))

    diffs = np.array(x) - np.array(y)
    n = len(diffs)
    mean_diff = float(np.mean(diffs))

    if max_lag is None:
        max_lag = max(1, int(np.sqrt(n)))

    centered = diffs - mean_diff

    gamma_0 = float(np.dot(centered, centered) / n)
    nw_var = gamma_0

    for lag in range(1, max_lag + 1):
        weight = 1.0 - lag / (max_lag + 1.0)
        gamma_j = float(np.dot(centered[lag:], centered[:-lag]) / n)
        nw_var += 2 * weight * gamma_j

    nw_var = max(nw_var, 1e-30)
    se = np.sqrt(nw_var / n)

    if se < 1e-15:
        return (float("nan"), float("nan"))

    t_stat = mean_diff / se
    p_value = 1.0 - stats.t.cdf(t_stat, df=n - 1)

    return (float(t_stat), float(p_value))


# ── Runner ───────────────────────────────────────────────────────────────────


def run_phase_a(
    experts: list[ExpertScores],
    forward_returns: dict[str, dict[str, float]],
    top_n: int = 10,
    alpha: float = 0.05,
) -> PhaseAResult:
    """Run Phase A discovery: L1 vs champion."""
    if len(experts) < 2:
        raise ValueError("Phase A requires at least 2 experts")

    common_dates = set(experts[0].dates)
    for e in experts[1:]:
        common_dates &= set(e.dates)
    common_dates &= set(forward_returns.keys())
    dates = sorted(common_dates)

    if not dates:
        raise ValueError("No common dates between experts and returns")

    champion_expert = experts[0]

    champ_result = evaluate_strategy(
        name=f"champion ({champion_expert.name})",
        score_fn=lambda dt: champion_scores(champion_expert, dt),
        dates=dates,
        forward_returns=forward_returns,
        top_n=top_n,
    )

    l1_result = evaluate_strategy(
        name="L1 (equal-weight)",
        score_fn=lambda dt: l1_equal_weight(experts, dt),
        dates=dates,
        forward_returns=forward_returns,
        top_n=top_n,
    )

    t_stat, p_val = newey_west_t_test(
        l1_result.daily_returns,
        champ_result.daily_returns,
    )

    champ_std = float(np.std(champ_result.daily_returns, ddof=1)) if len(champ_result.daily_returns) > 1 else 1.0
    effect = (l1_result.mean_return - champ_result.mean_return) / champ_std if champ_std > 0 else 0.0

    if p_val <= alpha and l1_result.mean_return > champ_result.mean_return:
        verdict = "L1_BEATS_CHAMPION"
        detail = (
            f"L1 outperforms champion at p={p_val:.4f} < alpha={alpha}. "
            f"Proceed to L2 comparison."
        )
    elif l1_result.mean_return <= champ_result.mean_return:
        verdict = "CHAMPION_RETAINED"
        detail = (
            f"L1 does not outperform champion (delta_return={effect:.4f}). "
            f"Per §5.3: champion unchanged. Ensemble experiment stops."
        )
    else:
        verdict = "INCONCLUSIVE"
        detail = (
            f"L1 has higher return but not significant at alpha={alpha} "
            f"(p={p_val:.4f}). Champion retained per burden-of-proof rule."
        )

    run_id = hashlib.sha256(
        json.dumps({
            "experts": [e.name for e in experts],
            "dates": dates,
            "top_n": top_n,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).encode()
    ).hexdigest()[:16]

    return PhaseAResult(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        champion=champ_result,
        l1=l1_result,
        n_experts=len(experts),
        expert_names=[e.name for e in experts],
        n_dates=len(dates),
        top_n=top_n,
        delta_ic=l1_result.mean_ic - champ_result.mean_ic,
        delta_return=l1_result.mean_return - champ_result.mean_return,
        delta_sharpe=l1_result.sharpe - champ_result.sharpe,
        p_value=p_val,
        t_statistic=t_stat,
        effect_size=effect,
        verdict=verdict,
        verdict_detail=detail,
    )


# ── Output ───────────────────────────────────────────────────────────────────


def result_to_dict(result: PhaseAResult) -> dict[str, Any]:
    """Serialize PhaseAResult to a JSON-friendly dict."""
    d = asdict(result)
    for key in ("champion", "l1"):
        d[key].pop("daily_returns", None)
        d[key].pop("daily_ics", None)
    return d


def print_verdict(result: PhaseAResult) -> None:
    """Print the Phase A verdict to stdout."""
    print("=" * 60)
    print("Phase A Discovery Result")
    print("=" * 60)
    print(f"Experts: {', '.join(result.expert_names)}")
    print(f"Dates:   {result.n_dates} common evaluation dates")
    print(f"Top-N:   {result.top_n}")
    print()

    print(f"{'Metric':<20} {'Champion':>12} {'L1':>12} {'Delta':>12}")
    print("-" * 60)
    print(f"{'Mean IC':<20} {result.champion.mean_ic:>12.4f} {result.l1.mean_ic:>12.4f} {result.delta_ic:>12.4f}")
    print(f"{'Mean Return':<20} {result.champion.mean_return:>12.4f} {result.l1.mean_return:>12.4f} {result.delta_return:>12.4f}")
    print(f"{'Sharpe':<20} {result.champion.sharpe:>12.4f} {result.l1.sharpe:>12.4f} {result.delta_sharpe:>12.4f}")
    print(f"{'Hit Rate':<20} {result.champion.hit_rate:>12.4f} {result.l1.hit_rate:>12.4f} {result.l1.hit_rate - result.champion.hit_rate:>12.4f}")
    print(f"{'Turnover':<20} {result.champion.mean_turnover:>12.4f} {result.l1.mean_turnover:>12.4f} {result.l1.mean_turnover - result.champion.mean_turnover:>12.4f}")
    print()
    print(f"t-statistic: {result.t_statistic:.4f}")
    print(f"p-value:     {result.p_value:.4f}")
    print(f"Effect size: {result.effect_size:.4f}")
    print()
    print(f"VERDICT: {result.verdict}")
    print(f"  {result.verdict_detail}")
    print("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase A discovery: L1 equal-weight vs frozen champion",
    )
    parser.add_argument(
        "--expert",
        action="append",
        required=True,
        help="Expert name (repeatable, first = champion)",
    )
    parser.add_argument(
        "--score-dir",
        action="append",
        required=True,
        help="Score directory for corresponding expert (same order)",
    )
    parser.add_argument(
        "--returns-file",
        required=True,
        help="CSV with forward returns (date, ticker, fwd_return columns)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for result JSON output",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top-ranked tickers to select (default: 10)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level for the paired test (default: 0.05)",
    )
    args = parser.parse_args(argv)

    if len(args.expert) != len(args.score_dir):
        print("ERROR: --expert and --score-dir must be paired", file=sys.stderr)
        return 1

    if len(args.expert) < 2:
        print("ERROR: Phase A requires at least 2 experts", file=sys.stderr)
        return 1

    experts = []
    for name, score_dir in zip(args.expert, args.score_dir):
        print(f"Loading {name} scores from {score_dir}...")
        expert = load_expert_scores(name, Path(score_dir))
        print(f"  {len(expert.dates)} dates loaded")
        experts.append(expert)

    print(f"Loading forward returns from {args.returns_file}...")
    fwd_returns = load_forward_returns(Path(args.returns_file))
    print(f"  {len(fwd_returns)} dates loaded")

    result = run_phase_a(
        experts=experts,
        forward_returns=fwd_returns,
        top_n=args.top_n,
        alpha=args.alpha,
    )

    print_verdict(result)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"phase_a_result_{result.run_id}.json"
    output_path.write_text(
        json.dumps(result_to_dict(result), indent=2, default=str) + "\n",
    )
    print(f"\nResult saved to {output_path}")

    return 0 if result.verdict == "L1_BEATS_CHAMPION" else 1


if __name__ == "__main__":
    sys.exit(main())
