"""Phase A discovery runner for the ensemble combination experiment.

Compares L1 (equal-weight combination of admitted experts) against the
frozen champion (the pre-registered ``primary_live`` expert from the
experiment manifest) on the same score-to-portfolio mapping, using
point-in-time scores that have passed the Stage 0 admissibility ledger.

This is RESEARCH-ONLY tooling. It does not touch production paths,
place orders, or modify any live state.

Design reference: doc/research/2026-07-12-ensemble-combination-experiment.md
  - §3.1    L1 equal-weight combination
  - §4.1bis Causal cross-sectional normalization + missing-expert fallback
  - §4.2    Leakage controls (non-overlapping outer blocks, not a plain t-test)
  - §4.4    Evaluation and statistical test (net-of-cost, dependence-robust)
  - §4.5    Go/no-go decision tree
  - §5.2    Phase A scope

Every input this runner consumes must be traceable to the pre-registered
experiment manifest (:mod:`experiment_manifest`) and the Stage 0
admissibility ledger (:mod:`admissibility_ledger`) -- it does not accept
arbitrary score directories or a CLI-order-determined champion (Codex
review 2026-07-13 on model#53).

Usage::

    python -m experiments.ensemble_phase0.phase_a_runner \\
        --expert xgb --score-dir /path/to/xgb/scores \\
        --expert patchtst --score-dir /path/to/patchtst/scores \\
        --returns-file /path/to/forward_returns.csv \\
        --manifest-file /path/to/experiment_manifest.json \\
        --ledger-file /path/to/admissibility_ledger.json \\
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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from experiments.ensemble_phase0.admissibility_ledger import (
    AdmissibilityLedger,
    admitted_score_digests,
    load_and_verify_ledger,
)
from experiments.ensemble_phase0.experiment_manifest import (
    ExperimentManifest,
    load_and_verify_manifest,
    resolve_champion_name,
)

#: Floor on the number of non-overlapping (block-spaced) observations
#: required before the primary pre-registered statistical test
#: ("non_overlapping_outer_blocks", §4.2/§4.4) is used. Below this, a
#: paired test's variance estimate is too unstable to mean anything --
#: this is a deliberate, documented judgment call (not a tuned production
#: threshold), matching the "explicit, not silently assumed" discipline
#: used elsewhere in this experiment (e.g. admissibility_ledger's
#: decision-schedule requirement).
MIN_NON_OVERLAPPING_OBSERVATIONS = 8

#: Test-method labels persisted in :class:`PhaseAResult` for auditability.
TEST_METHOD_NON_OVERLAPPING = "non_overlapping_outer_blocks"
TEST_METHOD_HAC_FALLBACK = "hac_on_overlapping_returns_fallback"


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
    n_dates_excluded_missing_returns: int = 0
    dates: list[str] = field(default_factory=list)
    portfolio_sizes: list[int] = field(default_factory=list)
    mean_ic: float = float("nan")
    mean_return: float = float("nan")
    mean_net_return: float = float("nan")
    sharpe: float = float("nan")
    hit_rate: float = float("nan")
    mean_turnover: float = float("nan")
    daily_returns: list[float] = field(default_factory=list)
    daily_net_returns: list[float] = field(default_factory=list)
    daily_ics: list[float] = field(default_factory=list)


@dataclass
class PhaseAResult:
    """Complete Phase A discovery result."""

    run_id: str = ""
    timestamp: str = ""
    champion: StrategyResult = field(default_factory=lambda: StrategyResult("champion"))
    l1: StrategyResult = field(default_factory=lambda: StrategyResult("l1"))
    champion_name: str = ""
    n_experts: int = 0
    expert_names: list[str] = field(default_factory=list)
    n_dates: int = 0
    dates: list[str] = field(default_factory=list)
    top_n: int = 10
    cost_bps: float = 0.0
    score_normalization_method: str = ""
    test_method: str = ""
    n_test_dates: int = 0
    block_length_days: int = 0
    manifest_fingerprint: str = ""
    ledger_fingerprint: str = ""
    returns_file_digest: str = ""
    returns_file_locator: str = ""
    expert_score_digests: dict[str, list[str]] = field(default_factory=dict)
    n_paired_test_dates: int = 0
    n_test_dates_excluded_asymmetric_or_undersized: int = 0
    minimum_effect_size_delta_ic: float = 0.0
    delta_ic: float = float("nan")
    delta_ic_test: float = float("nan")
    delta_return: float = float("nan")
    delta_sharpe: float = float("nan")
    delta_net_return_test: float = float("nan")
    p_value: float = float("nan")
    t_statistic: float = float("nan")
    effect_size: float = float("nan")
    verdict: str = "INCONCLUSIVE"
    verdict_detail: str = ""


# ── Score loading ────────────────────────────────────────────────────────────


def load_expert_scores(
    name: str,
    score_dir: Path,
    *,
    admitted_digests: dict[tuple[str, str], str],
) -> ExpertScores:
    """Load date-named JSON score files admitted by the Stage 0 ledger.

    A score file is only accepted if ``(name, date)`` is recorded as
    ``admitted=True`` in the admissibility ledger AND the file's own
    freshly-computed SHA-256 digest matches the ledger's recorded
    ``score_artifact_digest`` for that record. Neither the ledger metadata
    embedded in the JSON payload nor any other self-attested field is
    trusted -- provenance comes only from the pre-verified ledger (Codex
    review 2026-07-13, finding 1: ``load_expert_scores`` previously
    accepted arbitrary JSON and ignored the ledger's cutoffs/digests
    entirely). A date/ticker without a matching admitted ledger record is
    silently excluded, never silently included.
    """
    expert = ExpertScores(name=name)

    if not score_dir.is_dir():
        raise FileNotFoundError(f"Score directory not found: {score_dir}")

    for path in sorted(score_dir.glob("*.json")):
        stem = path.stem
        if len(stem) != 10:
            continue

        expected_digest = admitted_digests.get((name, stem))
        if not expected_digest:
            # Not admitted for this expert/date -- fail closed, not silently
            # loaded anyway.
            continue

        raw_bytes = path.read_bytes()
        actual_digest = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
        if actual_digest != expected_digest:
            # File on disk no longer matches what the ledger admitted --
            # reject rather than trust a possibly-modified file.
            continue

        try:
            data = json.loads(raw_bytes)
        except json.JSONDecodeError:
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


def verify_returns_file_digest(
    returns_path: Path, ledger: AdmissibilityLedger,
) -> tuple[str, str]:
    """Verify the forward-returns file is the SAME artifact the ledger's
    admitted records declare as their label source -- not an arbitrary or
    substituted/mutated file (Codex review 2026-07-13, finding 1: the
    ledger validates score artifacts but ``load_forward_returns`` accepted
    any path with no binding to the admitted label locator/digest).

    Every admitted record's ``label_artifact_ref`` (``sha256:<64hex>@<locator>``)
    must be IDENTICAL -- a coherent Phase A run has exactly one canonical
    label/returns artifact, referenced consistently. Checking the digest
    alone is not sufficient (Codex review 2026-07-13, round 4): a
    byte-identical file at an unrelated locator would pass a digest-only
    check but is not proof this is the file the ledger's provenance chain
    actually points at, so the locator's basename must also match the
    returns file actually supplied. Returns ``(digest, locator)`` on
    success.
    """
    raw_bytes = returns_path.read_bytes()
    actual_digest = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"

    admitted_refs = {
        record["label_artifact_ref"]
        for record in ledger.records
        if record.get("admitted") and record.get("label_artifact_ref")
    }
    if not admitted_refs:
        raise ValueError(
            "ledger has no admitted records with a label_artifact_ref -- "
            "cannot verify the forward-returns file against any declared "
            "label artifact"
        )
    if len(admitted_refs) > 1:
        raise ValueError(
            "ledger's admitted records disagree on label_artifact_ref "
            f"({sorted(admitted_refs)}) -- ambiguous which is the canonical "
            "forward-returns source"
        )
    expected_ref = next(iter(admitted_refs))
    if "@" not in expected_ref:
        raise ValueError(
            f"admitted label_artifact_ref {expected_ref!r} has no locator "
            "component (expected sha256:<digest>@<locator>)"
        )
    expected_digest, expected_locator = expected_ref.split("@", 1)
    if actual_digest != expected_digest:
        raise ValueError(
            f"forward-returns file digest {actual_digest} does not match "
            f"the ledger's admitted label_artifact_ref digest "
            f"{expected_digest} -- refusing to evaluate against a "
            "substituted or mutated returns file"
        )
    if Path(expected_locator).name != returns_path.name:
        raise ValueError(
            f"returns file name {returns_path.name!r} does not match the "
            f"ledger's declared label artifact locator {expected_locator!r} "
            f"(basename {Path(expected_locator).name!r}) -- a byte-identical "
            "file at an unrelated locator is not proof of provenance"
        )
    return actual_digest, expected_locator


# ── Combination methods ──────────────────────────────────────────────────────


def cross_sectional_zscore(scores: dict[str, float]) -> dict[str, float]:
    """Causal cross-sectional z-score of one expert's scores for one date.

    Normalizes against that date's OWN cross-section only -- no lookahead
    across dates, no information beyond what's in this date's universe.
    Per the pre-registered manifest (model PR #48 §4.1bis):
    ``score_normalization.method == "cross_sectional_zscore"``,
    ``causal: True``. A degenerate (zero cross-sectional variance)
    cross-section has no relative ranking information to normalize, so it
    maps every ticker to 0.0 rather than dividing by ~zero.
    """
    if not scores:
        return {}
    values = np.array(list(scores.values()), dtype=float)
    mean = float(values.mean())
    std = float(values.std(ddof=0))
    if std < 1e-12:
        return {ticker: 0.0 for ticker in scores}
    return {ticker: (val - mean) / std for ticker, val in scores.items()}


def l1_equal_weight(
    experts: list[ExpertScores],
    date_str: str,
) -> dict[str, float]:
    """Equal-weight combination of causally-normalized expert scores.

    Each expert's raw scores for ``date_str`` are first put on a common
    scale via :func:`cross_sectional_zscore` -- raw scores from
    heterogeneous model families (e.g. an XGB probability vs a PatchTST
    regression output) are not comparable and averaging them directly says
    nothing about relative ranking (Codex review 2026-07-13, finding 2).

    A ticker missing from one expert's scores is EXCLUDED from that
    expert's contribution and the remaining experts' normalized scores are
    averaged -- per the pre-registered missing-expert fallback policy
    (model PR #48 §4.1bis: "exclude that model from the combination for
    that specific observation... rather than dropping the whole
    observation"). A ticker is included in the combined output as long as
    at least one expert scored it that date.
    """
    combined: dict[str, list[float]] = defaultdict(list)

    for expert in experts:
        normalized = cross_sectional_zscore(expert.scores_by_date.get(date_str, {}))
        for ticker, val in normalized.items():
            combined[ticker].append(val)

    return {ticker: sum(vals) / len(vals) for ticker, vals in combined.items()}


def champion_scores(
    champion_expert: ExpertScores,
    date_str: str,
) -> dict[str, float]:
    """Return the frozen champion's raw (un-normalized) scores for a date.

    The champion is evaluated alone -- there is no cross-expert
    combination to normalize against, so its own native score scale is
    used directly, unchanged from today's production convention.
    """
    return dict(champion_expert.scores_by_date.get(date_str, {}))


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
) -> float | None:
    """Equal-weight GROSS portfolio return from selected tickers.

    Returns ``None`` -- never a silently-defaulted 0.0 -- when any
    selected ticker lacks a realized return for this date. A missing
    return is not the same as a zero return, and silently substituting
    0.0 changes the portfolio return in a way that differs (and can
    differ systematically between champion and L1, since they may select
    different tickers) depending on which names happen to be missing
    (Codex review 2026-07-13, finding 5). The caller must exclude a date
    with incomplete return coverage rather than evaluate it on a
    fabricated value.
    """
    if not selected:
        return 0.0
    missing = [t for t in selected if t not in returns]
    if missing:
        return None
    rets = [returns[t] for t in selected]
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


def select_non_overlapping_dates(dates: list[str], block_length_days: int) -> list[str]:
    """Greedily select a subsequence of ``dates`` spaced >= block_length_days
    calendar days apart.

    Per the pre-registered manifest's primary statistical-test design
    (model PR #48 §4.2/§4.4): consecutive daily observations of a
    ``label_horizon_days``-forward return share most of their observation
    window with their neighbors, inducing much stronger serial dependence
    than an ordinary HAC correction with ``max_lag ~ sqrt(n)`` accounts
    for. Subsampling to block-spaced, non-overlapping observations removes
    the induced overlap at the source rather than trying to model it away.
    """
    if not dates:
        return []
    selected = [dates[0]]
    last = date.fromisoformat(dates[0])
    for d in dates[1:]:
        cur = date.fromisoformat(d)
        if (cur - last).days >= block_length_days:
            selected.append(d)
            last = cur
    return selected


def evaluate_strategy(
    name: str,
    score_fn,
    dates: list[str],
    forward_returns: dict[str, dict[str, float]],
    top_n: int,
    *,
    cost_bps: float = 0.0,
) -> StrategyResult:
    """Evaluate a strategy across all dates.

    ``cost_bps`` is deducted from the gross return in proportion to that
    date's turnover (a full portfolio replacement costs ``cost_bps``, a
    50%-changed portfolio costs half that), per the pre-registered cost
    assumption (model PR #48 §4.4: net-of-cost is a co-primary pass
    condition, not an optional/reported-but-unused metric -- Codex review
    2026-07-13, finding 6).
    """
    result = StrategyResult(name=name)
    daily_rets: list[float] = []
    daily_net_rets: list[float] = []
    daily_ics: list[float] = []
    turnovers: list[float] = []
    used_dates: list[str] = []
    portfolio_sizes: list[int] = []
    prev_portfolio: list[str] = []
    n_excluded = 0

    for dt in dates:
        scores = score_fn(dt)
        if not scores:
            continue
        rets = forward_returns.get(dt, {})
        if not rets:
            continue

        portfolio = top_n_selection(scores, top_n)
        # Turnover reflects the actual trade that would have been made,
        # independent of whether this date's return can be evaluated --
        # excluding a return-incomplete date must not let the NEXT date's
        # turnover be measured against a stale, two-dates-ago portfolio.
        turnover = compute_turnover(prev_portfolio, portfolio)
        prev_portfolio = portfolio

        port_ret = compute_portfolio_return(portfolio, rets)
        if port_ret is None:
            n_excluded += 1
            continue

        ic = compute_ic(scores, rets)
        net_ret = port_ret - turnover * (cost_bps / 10_000.0)

        daily_rets.append(port_ret)
        daily_net_rets.append(net_ret)
        daily_ics.append(ic)
        turnovers.append(turnover)
        used_dates.append(dt)
        portfolio_sizes.append(len(portfolio))

    result.n_dates = len(daily_rets)
    result.n_dates_excluded_missing_returns = n_excluded
    result.dates = used_dates
    result.portfolio_sizes = portfolio_sizes
    result.daily_returns = daily_rets
    result.daily_net_returns = daily_net_rets
    result.daily_ics = daily_ics

    if daily_rets:
        valid_ics = [ic for ic in daily_ics if math.isfinite(ic)]
        result.mean_ic = np.mean(valid_ics) if valid_ics else float("nan")
        result.mean_return = float(np.mean(daily_rets))
        result.mean_net_return = float(np.mean(daily_net_rets))
        std = float(np.std(daily_net_rets, ddof=1)) if len(daily_net_rets) > 1 else 0.0
        result.sharpe = (result.mean_net_return / std) if std > 0 else float("nan")
        result.hit_rate = sum(1 for r in daily_net_rets if r > 0) / len(daily_net_rets)
        result.mean_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    return result


def pair_evaluations_by_date(
    champ: StrategyResult,
    l1: StrategyResult,
    top_n: int,
) -> tuple[list[str], list[float], list[float], list[float], list[float], int]:
    """Build a date-keyed paired evaluation table for the statistical test.

    ``evaluate_strategy`` independently excludes dates for incomplete
    return coverage on each strategy -- champion and L1 can therefore
    exclude DIFFERENT dates and still end up with equal-length arrays.
    Subtracting those arrays positionally (the previous behavior) can
    silently pair values from different calendar dates, and if the
    lengths happen to differ it degrades to NaN without ever surfacing
    the misalignment (Codex review 2026-07-13 round 4, finding 2).

    A date is admissible for the paired test only if BOTH strategies
    evaluated it AND both selected exactly ``top_n`` names -- an
    under-sized selection on either side breaks the "same fixed portfolio
    mapping" guarantee the whole comparison depends on (finding 3): a
    9-name champion portfolio and a 10-name L1 portfolio are not
    comparable under a claimed identical top-N mapping.

    Returns ``(dates, champ_net_returns, l1_net_returns, champ_ics,
    l1_ics, n_excluded)`` -- all list-of-N are aligned by the SAME date
    at each index. ``n_excluded`` counts dates dropped for asymmetric
    coverage or an under-sized selection on either side.
    """
    champ_by_date = {
        d: (ret, sz, ic)
        for d, ret, sz, ic in zip(
            champ.dates, champ.daily_net_returns, champ.portfolio_sizes, champ.daily_ics,
        )
    }
    l1_by_date = {
        d: (ret, sz, ic)
        for d, ret, sz, ic in zip(
            l1.dates, l1.daily_net_returns, l1.portfolio_sizes, l1.daily_ics,
        )
    }
    all_candidate_dates = sorted(set(champ_by_date) | set(l1_by_date))

    dates: list[str] = []
    champ_rets: list[float] = []
    l1_rets: list[float] = []
    champ_ics: list[float] = []
    l1_ics: list[float] = []
    n_excluded = 0

    for d in all_candidate_dates:
        c = champ_by_date.get(d)
        l = l1_by_date.get(d)
        if c is None or l is None:
            n_excluded += 1
            continue
        c_ret, c_sz, c_ic = c
        l_ret, l_sz, l_ic = l
        if c_sz != top_n or l_sz != top_n:
            n_excluded += 1
            continue
        dates.append(d)
        champ_rets.append(c_ret)
        l1_rets.append(l_ret)
        champ_ics.append(c_ic)
        l1_ics.append(l_ic)

    return dates, champ_rets, l1_rets, champ_ics, l1_ics, n_excluded


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
    *,
    champion_name: str,
    top_n: int = 10,
    alpha: float = 0.05,
    cost_bps: float = 0.0,
    block_length_days: int = 60,
    minimum_effect_size_delta_ic: float = 0.0,
    manifest_fingerprint: str = "",
    ledger_fingerprint: str = "",
    returns_file_digest: str = "",
    returns_file_locator: str = "",
    expert_score_digests: dict[str, list[str]] | None = None,
) -> PhaseAResult:
    """Run Phase A discovery: L1 vs frozen champion.

    ``champion_name`` is required with no default -- the champion must be
    an explicit, pre-registered identity (from the experiment manifest's
    ``primary_live`` expert, resolved by the caller), never inferred from
    argument order (Codex review 2026-07-13, finding 3).

    ``cost_bps``/``block_length_days``/``minimum_effect_size_delta_ic``
    should be sourced from the pre-registered experiment manifest's
    ``cost_assumptions``/``statistical_test`` sections; the defaults here
    exist only for standalone/unit-test convenience.

    The evaluation calendar (``dates``) requires every loaded expert to
    have scored a date -- per the manifest's
    ``phase_a_requires_complete_expert_coverage`` flag, Phase A's
    controlled champion-vs-L1 comparison does not evaluate a date where a
    whole expert is missing (that would let champion and L1 silently
    evaluate different calendars). The §4.1bis missing-expert
    exclude-and-renormalize policy remains fully in effect at the
    per-ticker level within any such shared date (see
    :func:`l1_equal_weight`) -- this restriction is about whole-expert
    availability, a narrower and separate concern (Codex review
    2026-07-13 round 4, finding 1).

    ``manifest_fingerprint``/``ledger_fingerprint``/``returns_file_digest``/
    ``returns_file_locator``/``expert_score_digests`` are provenance-only
    -- they do not affect the computation, but are persisted on the
    result (and folded into ``run_id``) so a favorable output can be
    independently reproduced and re-verified against the exact inputs
    that produced it.
    """
    if len(experts) < 2:
        raise ValueError("Phase A requires at least 2 experts")

    champion_candidates = [e for e in experts if e.name == champion_name]
    if len(champion_candidates) != 1:
        raise ValueError(
            f"champion_name={champion_name!r} must match exactly one loaded "
            f"expert by name; loaded experts: {[e.name for e in experts]}"
        )
    champion_expert = champion_candidates[0]

    common_dates = set(experts[0].dates)
    for e in experts[1:]:
        common_dates &= set(e.dates)
    common_dates &= set(forward_returns.keys())
    dates = sorted(common_dates)

    if not dates:
        raise ValueError("No common dates between experts and returns")

    champ_result = evaluate_strategy(
        name=f"champion ({champion_expert.name})",
        score_fn=lambda dt: champion_scores(champion_expert, dt),
        dates=dates,
        forward_returns=forward_returns,
        top_n=top_n,
        cost_bps=cost_bps,
    )

    l1_result = evaluate_strategy(
        name="L1 (equal-weight)",
        score_fn=lambda dt: l1_equal_weight(experts, dt),
        dates=dates,
        forward_returns=forward_returns,
        top_n=top_n,
        cost_bps=cost_bps,
    )

    # The go/no-go statistical test is run on a SEPARATE, block-restricted
    # evaluation, never on the full daily (overlapping-return) series
    # above (Codex review 2026-07-13, findings 4+6). champ_result/l1_result
    # remain full-sample descriptive statistics for the human-readable
    # report.
    non_overlap_dates = select_non_overlapping_dates(dates, block_length_days)
    if len(non_overlap_dates) >= MIN_NON_OVERLAPPING_OBSERVATIONS:
        test_dates = non_overlap_dates
        test_method = TEST_METHOD_NON_OVERLAPPING
    else:
        test_dates = dates
        test_method = TEST_METHOD_HAC_FALLBACK

    champ_test = evaluate_strategy(
        name=champ_result.name,
        score_fn=lambda dt: champion_scores(champion_expert, dt),
        dates=test_dates,
        forward_returns=forward_returns,
        top_n=top_n,
        cost_bps=cost_bps,
    )
    l1_test = evaluate_strategy(
        name=l1_result.name,
        score_fn=lambda dt: l1_equal_weight(experts, dt),
        dates=test_dates,
        forward_returns=forward_returns,
        top_n=top_n,
        cost_bps=cost_bps,
    )

    # Build the TRUE date-keyed paired series -- never zip the two
    # independently-filtered arrays above by position (Codex review
    # 2026-07-13 round 4, findings 2+3).
    (
        paired_dates, paired_champ_rets, paired_l1_rets,
        paired_champ_ics, paired_l1_ics, n_excluded_pairing,
    ) = pair_evaluations_by_date(champ_test, l1_test, top_n)

    # The non-overlapping-block floor must hold for the observations
    # ACTUALLY available to the paired test, not just the pre-pairing
    # candidate count -- asymmetric coverage/undersized selections can
    # shrink the usable set below the floor even when the initial block
    # selection cleared it.
    if test_method == TEST_METHOD_NON_OVERLAPPING and len(paired_dates) < MIN_NON_OVERLAPPING_OBSERVATIONS:
        test_method = TEST_METHOD_HAC_FALLBACK

    t_stat, p_val = newey_west_t_test(paired_l1_rets, paired_champ_rets)

    champ_test_std = (
        float(np.std(paired_champ_rets, ddof=1)) if len(paired_champ_rets) > 1 else 1.0
    )
    delta_net_return_test = (
        float(np.mean(paired_l1_rets)) - float(np.mean(paired_champ_rets))
        if paired_champ_rets and paired_l1_rets
        else float("nan")
    )
    effect = (
        (delta_net_return_test / champ_test_std)
        if champ_test_std > 0 and math.isfinite(delta_net_return_test)
        else 0.0
    )

    valid_champ_ics = [ic for ic in paired_champ_ics if math.isfinite(ic)]
    valid_l1_ics = [ic for ic in paired_l1_ics if math.isfinite(ic)]
    delta_ic_test = (
        float(np.mean(valid_l1_ics)) - float(np.mean(valid_champ_ics))
        if valid_champ_ics and valid_l1_ics
        else float("nan")
    )

    if test_method != TEST_METHOD_NON_OVERLAPPING:
        verdict = "EXPLORATORY_ONLY"
        detail = (
            f"Only {len(paired_dates)} paired non-overlapping "
            f"({block_length_days}d-spaced) observations available (need >= "
            f"{MIN_NON_OVERLAPPING_OBSERVATIONS} for the primary test, after "
            f"excluding {n_excluded_pairing} date(s) for asymmetric coverage "
            f"or an under-sized selection); falling back to HAC on the full "
            f"overlapping daily series is NOT the pre-registered primary "
            f"test (model PR #48 §4.2/§4.4). This verdict is EXPLORATORY_ONLY "
            f"and must not be promoted to L1_BEATS_CHAMPION / proceed-to-L2."
        )
    elif not math.isfinite(delta_net_return_test) or delta_net_return_test <= 0:
        verdict = "CHAMPION_RETAINED"
        detail = (
            f"L1 does not outperform champion net-of-cost "
            f"(delta_net_return={delta_net_return_test:.4f}) on "
            f"{len(paired_dates)} paired observations. Per §5.3: champion "
            f"unchanged. Ensemble experiment stops."
        )
    elif not (math.isfinite(p_val) and p_val <= alpha):
        verdict = "INCONCLUSIVE"
        detail = (
            f"L1 has higher net-of-cost return but not significant at "
            f"alpha={alpha} (p={p_val:.4f}) on {len(paired_dates)} paired "
            f"non-overlapping observations. Champion retained per "
            f"burden-of-proof rule."
        )
    elif not math.isfinite(delta_ic_test) or delta_ic_test < minimum_effect_size_delta_ic:
        verdict = "INCONCLUSIVE"
        detail = (
            f"L1 outperforms champion net-of-cost at p={p_val:.4f} < "
            f"alpha={alpha}, but the IC effect size (delta_ic="
            f"{delta_ic_test:.4f}) is below the pre-registered minimum "
            f"{minimum_effect_size_delta_ic} (model PR #48 §4.4: a "
            f"necessary but not sufficient statistical result is not "
            f"economically meaningful on its own). Champion retained."
        )
    else:
        verdict = "L1_BEATS_CHAMPION"
        detail = (
            f"L1 outperforms champion net-of-cost at p={p_val:.4f} < alpha={alpha} "
            f"with IC effect size delta_ic={delta_ic_test:.4f} >= "
            f"{minimum_effect_size_delta_ic} on {len(paired_dates)} paired "
            f"non-overlapping observations. Proceed to L2 comparison."
        )

    expert_score_digests = expert_score_digests or {}

    run_id = hashlib.sha256(
        json.dumps({
            "experts": [e.name for e in experts],
            "champion_name": champion_name,
            "dates": dates,
            "top_n": top_n,
            "manifest_fingerprint": manifest_fingerprint,
            "ledger_fingerprint": ledger_fingerprint,
            "returns_file_digest": returns_file_digest,
            "returns_file_locator": returns_file_locator,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).encode()
    ).hexdigest()[:16]

    return PhaseAResult(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        champion=champ_result,
        l1=l1_result,
        champion_name=champion_name,
        n_experts=len(experts),
        expert_names=[e.name for e in experts],
        n_dates=len(dates),
        dates=dates,
        top_n=top_n,
        cost_bps=cost_bps,
        score_normalization_method="cross_sectional_zscore",
        test_method=test_method,
        n_test_dates=len(test_dates),
        n_paired_test_dates=len(paired_dates),
        n_test_dates_excluded_asymmetric_or_undersized=n_excluded_pairing,
        block_length_days=block_length_days,
        minimum_effect_size_delta_ic=minimum_effect_size_delta_ic,
        manifest_fingerprint=manifest_fingerprint,
        ledger_fingerprint=ledger_fingerprint,
        returns_file_digest=returns_file_digest,
        returns_file_locator=returns_file_locator,
        expert_score_digests=expert_score_digests,
        delta_ic=l1_result.mean_ic - champ_result.mean_ic,
        delta_ic_test=delta_ic_test,
        delta_return=l1_result.mean_return - champ_result.mean_return,
        delta_sharpe=l1_result.sharpe - champ_result.sharpe,
        delta_net_return_test=delta_net_return_test,
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
        d[key].pop("daily_net_returns", None)
        d[key].pop("daily_ics", None)
    return d


def print_verdict(result: PhaseAResult) -> None:
    """Print the Phase A verdict to stdout."""
    print("=" * 60)
    print("Phase A Discovery Result")
    print("=" * 60)
    print(f"Experts:  {', '.join(result.expert_names)}")
    print(f"Champion: {result.champion_name}")
    print(f"Dates:    {result.n_dates} common evaluation dates")
    print(f"Top-N:    {result.top_n}")
    print(f"Cost:     {result.cost_bps} bps")
    print()

    print(f"{'Metric':<20} {'Champion':>12} {'L1':>12} {'Delta':>12}")
    print("-" * 60)
    print(f"{'Mean IC':<20} {result.champion.mean_ic:>12.4f} {result.l1.mean_ic:>12.4f} {result.delta_ic:>12.4f}")
    print(f"{'Mean Return':<20} {result.champion.mean_return:>12.4f} {result.l1.mean_return:>12.4f} {result.delta_return:>12.4f}")
    print(f"{'Sharpe (net)':<20} {result.champion.sharpe:>12.4f} {result.l1.sharpe:>12.4f} {result.delta_sharpe:>12.4f}")
    print(f"{'Hit Rate':<20} {result.champion.hit_rate:>12.4f} {result.l1.hit_rate:>12.4f} {result.l1.hit_rate - result.champion.hit_rate:>12.4f}")
    print(f"{'Turnover':<20} {result.champion.mean_turnover:>12.4f} {result.l1.mean_turnover:>12.4f} {result.l1.mean_turnover - result.champion.mean_turnover:>12.4f}")
    print()
    print(
        f"Test method:  {result.test_method} "
        f"({result.n_paired_test_dates} paired observations, "
        f"{result.n_test_dates_excluded_asymmetric_or_undersized} excluded "
        f"asymmetric/undersized, block={result.block_length_days}d)"
    )
    print(f"t-statistic:  {result.t_statistic:.4f}")
    print(f"p-value:      {result.p_value:.4f}")
    print(f"Effect size:  {result.effect_size:.4f}")
    print(f"Delta IC (test): {result.delta_ic_test:.4f} (minimum required: {result.minimum_effect_size_delta_ic})")
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
        help="Expert name (repeatable) -- must be declared in --manifest-file",
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
        "--manifest-file",
        required=True,
        help="Pre-registered experiment manifest JSON (experiment_manifest.py)",
    )
    parser.add_argument(
        "--ledger-file",
        required=True,
        help="Verified Stage 0 admissibility ledger JSON (admissibility_ledger.py)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for result JSON output",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help=(
            "Number of top-ranked tickers to select. Sourced from the "
            "verified manifest's portfolio_mapping.top_n by default; if "
            "supplied, must equal the manifest value (Codex review "
            "2026-07-13, finding 2: this decision-affecting parameter must "
            "not be free to change after the manifest was registered)."
        ),
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=None,
        help=(
            "Significance level for the paired test. Sourced from the "
            "verified manifest's statistical_test.alpha by default; if "
            "supplied, must equal the manifest value."
        ),
    )
    args = parser.parse_args(argv)

    if len(args.expert) != len(args.score_dir):
        print("ERROR: --expert and --score-dir must be paired", file=sys.stderr)
        return 1

    if len(args.expert) < 2:
        print("ERROR: Phase A requires at least 2 experts", file=sys.stderr)
        return 1

    manifest = load_and_verify_manifest(Path(args.manifest_file))
    manifest_expert_names = {e["name"] for e in manifest.experts}
    unknown = sorted(set(args.expert) - manifest_expert_names)
    if unknown:
        print(
            f"ERROR: experts {unknown} are not declared in the pre-registered "
            f"manifest {args.manifest_file} -- refusing to compare an "
            f"unregistered expert set",
            file=sys.stderr,
        )
        return 1
    champion_name = resolve_champion_name(manifest)
    if champion_name not in args.expert:
        print(
            f"ERROR: pre-registered champion {champion_name!r} was not passed "
            f"via --expert; got {args.expert}",
            file=sys.stderr,
        )
        return 1

    manifest_top_n = manifest.portfolio_mapping.get("top_n")
    if args.top_n is not None and args.top_n != manifest_top_n:
        print(
            f"ERROR: --top-n={args.top_n} does not match the pre-registered "
            f"manifest's portfolio_mapping.top_n={manifest_top_n!r}; a "
            "decision-affecting parameter must not diverge from the "
            "registered manifest",
            file=sys.stderr,
        )
        return 1
    top_n = manifest_top_n if args.top_n is None else args.top_n

    manifest_alpha = manifest.statistical_test.get("alpha")
    if args.alpha is not None and args.alpha != manifest_alpha:
        print(
            f"ERROR: --alpha={args.alpha} does not match the pre-registered "
            f"manifest's statistical_test.alpha={manifest_alpha!r}; a "
            "decision-affecting parameter must not diverge from the "
            "registered manifest",
            file=sys.stderr,
        )
        return 1
    alpha = manifest_alpha if args.alpha is None else args.alpha

    ledger = load_and_verify_ledger(Path(args.ledger_file))
    admitted_digests = admitted_score_digests(ledger)

    experts = []
    for name, score_dir in zip(args.expert, args.score_dir):
        print(f"Loading {name} scores from {score_dir}...")
        expert = load_expert_scores(name, Path(score_dir), admitted_digests=admitted_digests)
        print(f"  {len(expert.dates)} ledger-admitted dates loaded")
        experts.append(expert)

    if not manifest.phase_a_requires_complete_expert_coverage:
        print(
            "ERROR: manifest.phase_a_requires_complete_expert_coverage is "
            "False, but this runner's evaluation calendar always requires "
            "every loaded expert to have scored a date (it does not "
            "implement partial-expert-coverage combination) -- the "
            "manifest and runner would silently disagree about Phase A's "
            "scope",
            file=sys.stderr,
        )
        return 1

    print(f"Loading forward returns from {args.returns_file}...")
    returns_path = Path(args.returns_file)
    returns_file_digest, returns_file_locator = verify_returns_file_digest(returns_path, ledger)
    fwd_returns = load_forward_returns(returns_path)
    print(f"  {len(fwd_returns)} dates loaded (digest {returns_file_digest} verified against ledger)")

    common_dates_for_provenance = set(experts[0].dates)
    for expert in experts[1:]:
        common_dates_for_provenance &= set(expert.dates)
    common_dates_for_provenance &= set(fwd_returns.keys())
    expert_score_digests = {
        expert.name: sorted(
            admitted_digests[(expert.name, dt)]
            for dt in common_dates_for_provenance
            if (expert.name, dt) in admitted_digests
        )
        for expert in experts
    }

    cost_bps = float(manifest.cost_assumptions.get("base_cost_bps", 0.0))
    block_length_days = int(
        manifest.statistical_test.get("block_length_days", 60)
    )
    minimum_effect_size_delta_ic = float(
        manifest.statistical_test.get("minimum_effect_size_delta_ic", 0.0)
    )

    result = run_phase_a(
        experts=experts,
        forward_returns=fwd_returns,
        champion_name=champion_name,
        top_n=top_n,
        alpha=alpha,
        cost_bps=cost_bps,
        block_length_days=block_length_days,
        minimum_effect_size_delta_ic=minimum_effect_size_delta_ic,
        manifest_fingerprint=manifest.manifest_fingerprint,
        ledger_fingerprint=ledger.ledger_fingerprint,
        returns_file_digest=returns_file_digest,
        returns_file_locator=returns_file_locator,
        expert_score_digests=expert_score_digests,
    )

    print_verdict(result)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"phase_a_result_{result.run_id}.json"
    output_path.write_text(
        json.dumps(result_to_dict(result), indent=2, default=str) + "\n",
    )
    print(f"\nResult saved to {output_path}")

    # A completed run is a successful experiment regardless of which
    # verdict it reached -- CHAMPION_RETAINED/INCONCLUSIVE/EXPLORATORY_ONLY
    # are valid evidentiary outcomes, not process failures. Nonzero exit
    # is reserved for invalid inputs, failed provenance checks, or runtime
    # errors, all of which already raise/return 1 above this point (Codex
    # review 2026-07-13, finding 4: a scheduler must not conflate "L1
    # didn't win" with "this run failed").
    return 0


if __name__ == "__main__":
    sys.exit(main())
