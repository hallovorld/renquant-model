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
    NESTED_WF_HARNESS_APPLIED,
    NESTED_WF_HARNESS_NOT_BUILT,
    ExperimentManifest,
    load_and_verify_manifest,
    resolve_champion_name,
)

#: Floor on the number of non-overlapping (block-spaced) observations
#: required before the primary pre-registered statistical test
#: ("non_overlapping_outer_blocks", §4.2/§4.4) is used. Below this, a
#: paired test's variance estimate is too unstable to mean anything.
#:
#: **Power justification (round 6, item 5):** for a paired t-test at
#: alpha=0.05 (one-sided) and power=0.80, a Cohen's d of ~1.0 (large
#: effect in non-overlapping block returns) requires n >= 7. We round
#: up to 8 as a margin. This is a MINIMUM for exploratory-but-testable
#: verdicts. Below ``MIN_CONFIRMATORY_OBSERVATIONS`` (20), a passing
#: test is still EXPLORATORY_ONLY — insufficient power to distinguish a
#: real effect from a large-variance lucky draw at the effect sizes
#: expected in this domain (~0.3-0.5 Sharpe difference expressed as
#: non-overlapping block Cohen's d). 20 blocks gives ~80% power at d=0.65.
MIN_NON_OVERLAPPING_OBSERVATIONS = 8

#: Below this, a verdict of L1_BEATS_CHAMPION is not justified — the
#: test may pass but cannot be considered confirmatory. The result is
#: capped at EXPLORATORY_ONLY with a note explaining the power limitation.
MIN_CONFIRMATORY_OBSERVATIONS = 20

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
    embargo_sessions: int = 0
    block_spacing_unit: str = "session_index"
    estimand_policy: str = "block_rebalance_paired"
    champion_production_policy: str = "daily"
    manifest_fingerprint: str = ""
    ledger_fingerprint: str = ""
    returns_file_digest: str = ""
    returns_file_locator: str = ""
    expert_score_digests: dict[str, list[str]] = field(default_factory=dict)
    n_paired_test_dates: int = 0
    n_test_dates_excluded_asymmetric_or_undersized: int = 0
    n_paired_ic_dates: int = 0
    minimum_effect_size_delta_ic: float = 0.0
    min_non_overlapping_observations: int = MIN_NON_OVERLAPPING_OBSERVATIONS
    nested_wf_harness_status: str = ""
    min_confirmatory_observations: int = MIN_CONFIRMATORY_OBSERVATIONS
    session_calendar_digest: str = ""
    session_calendar_verified: bool = False
    selected_block_indices: list[int] = field(default_factory=list)
    experiment_version: str = ""
    champion_policy_artifact_digest: str = ""
    embargo_justification: str = ""
    score_coverage: dict[str, Any] = field(default_factory=dict)
    label_observation_end: str = ""
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
    admitted records declare as their label source.

    **Artifact identity contract (option 1):** identity is the SHA-256
    content digest alone. The locator portion of ``label_artifact_ref``
    (the ``@<path>`` suffix in ``sha256:<64hex>@<path>``) is an
    informational audit trail — it records where the artifact was when
    the ledger was built, but is NOT part of identity comparison. Two
    files with the same SHA-256 digest ARE the same artifact regardless
    of where they reside on disk.

    This contract was chosen over locator-based identity (option 2)
    because: (a) ``Path.parts`` suffix matching is not a canonical
    locator binding — any ancestor directory is unconstrained, so a
    copied byte-identical file can pass; (b) SHA-256 collision is
    computationally infeasible for an adversary at this scale; (c) the
    digest is already computed and validated for score artifacts via
    ``admitted_score_digests()``.

    All admitted records must agree on the same content digest. The
    locator, if present, is persisted for audit recovery but not
    asserted against the supplied file path.

    Returns ``(digest, locator)`` where locator is the informational
    audit-trail string (empty if the ref has no ``@`` component).
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

    # Extract digests from all admitted refs — identity is the digest,
    # so refs that differ only in the locator portion are still the same
    # artifact.
    admitted_digests = set()
    audit_locator = ""
    for ref in admitted_refs:
        if "@" in ref:
            d, loc = ref.split("@", 1)
            audit_locator = loc
        else:
            d = ref
        admitted_digests.add(d)

    if len(admitted_digests) > 1:
        raise ValueError(
            "ledger's admitted records disagree on label artifact digest "
            f"({sorted(admitted_digests)}) -- ambiguous which content is "
            "the canonical forward-returns source"
        )
    expected_digest = next(iter(admitted_digests))
    if actual_digest != expected_digest:
        raise ValueError(
            f"forward-returns file digest {actual_digest} does not match "
            f"the ledger's admitted label artifact digest "
            f"{expected_digest} -- refusing to evaluate against a "
            "substituted or mutated returns file"
        )

    # Round 6, item 4: validate label_observation_end consistency across
    # admitted records. All admitted records must declare the same
    # label_observation_end — divergent values mean the ledger was built
    # against forward-return data with inconsistent horizons.
    admitted_label_ends = {
        record.get("label_observation_end")
        for record in ledger.records
        if record.get("admitted") and record.get("label_observation_end")
        and record["label_observation_end"] != "MISSING"
    }
    if len(admitted_label_ends) > 1:
        raise ValueError(
            f"ledger's admitted records disagree on label_observation_end "
            f"({sorted(admitted_label_ends)}) -- ambiguous return-horizon "
            f"semantics"
        )

    # Validate the label horizon is consistent with the ledger's declared
    # label_horizon_days: if the ledger declares a horizon, the actual
    # observation window must span at least that many days from the
    # earliest admitted prediction date.
    #
    # Round 6, finding 2 (Codex review 2026-07-13T17:00:21Z): the previous
    # version wrapped BOTH the date parsing AND the actual_span validation
    # raise in the same `try`, so the `except (ValueError, TypeError): pass`
    # meant to swallow unparseable dates also silently swallowed the
    # validation failure it just raised -- a label window shorter than the
    # declared horizon was accepted instead of rejected. The `try` is now
    # restricted to parsing only; the comparison and its `raise` happen in
    # the `else` clause, outside the `try`, so a real validation failure
    # always propagates.
    if admitted_label_ends and ledger.label_horizon_days:
        label_end_str = next(iter(admitted_label_ends))
        earliest_pred = min(
            record["prediction_date"]
            for record in ledger.records
            if record.get("admitted")
        )
        try:
            label_end_date = date.fromisoformat(label_end_str)
            earliest_pred_date = date.fromisoformat(earliest_pred)
        except (ValueError, TypeError):
            pass  # unparseable dates — already caught by ledger validation
        else:
            actual_span = (label_end_date - earliest_pred_date).days
            if actual_span < ledger.label_horizon_days:
                raise ValueError(
                    f"label_observation_end {label_end_str} is only "
                    f"{actual_span}d after earliest prediction date "
                    f"{earliest_pred} (ledger declares "
                    f"label_horizon_days={ledger.label_horizon_days})"
                )

    return actual_digest, audit_locator


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


def select_non_overlapping_dates(
    dates: list[str],
    min_spacing: int,
    *,
    embargo: int = 0,
    session_calendar: list[str] | None = None,
) -> tuple[list[str], list[int]]:
    """Greedily select a subsequence of ``dates`` spaced >= ``min_spacing +
    embargo`` positions apart.

    When ``session_calendar`` is provided (the frozen, manifest-bound
    list of ALL expected trading sessions), spacing is measured in
    **calendar-index positions** -- each date's position is looked up in
    the full calendar, so gaps from missing sessions are preserved as
    index distance rather than compressed away (Codex review round 11,
    2026-07-14T02:02:08Z, finding 1). Without a calendar, spacing falls
    back to input-list index positions (round 10 behavior, suitable only
    for unit tests where the input IS the complete calendar).

    Returns ``(selected_dates, selected_calendar_indices)`` -- the
    calendar indices are persisted on the result for auditability.

    ``embargo`` adds extra positions beyond ``min_spacing`` to skip,
    ensuring a buffer between the end of one block's label horizon and the
    start of the next evaluation point (§4.1 embargo requirement).
    """
    if not dates:
        return [], []
    total_gap = min_spacing + embargo

    if session_calendar is not None:
        cal_index = {d: i for i, d in enumerate(session_calendar)}
        unknown = [d for d in dates if d not in cal_index]
        if unknown:
            raise ValueError(
                f"{len(unknown)} evaluation date(s) are absent from the "
                f"session calendar (first 5: {unknown[:5]}). This is a "
                f"hard failure: silently dropping unknown dates mutates "
                f"the sample, which can change both which names get "
                f"selected and the significance of the resulting test."
            )
        indexed = [(cal_index[d], d) for d in dates]
        if not indexed:
            return [], []
        indexed.sort()
        selected = [indexed[0][1]]
        selected_indices = [indexed[0][0]]
        last_cal_idx = indexed[0][0]
        for cal_idx, d in indexed[1:]:
            if cal_idx - last_cal_idx >= total_gap:
                selected.append(d)
                selected_indices.append(cal_idx)
                last_cal_idx = cal_idx
        return selected, selected_indices

    selected = [dates[0]]
    selected_indices = [0]
    last_idx = 0
    for i, d in enumerate(dates[1:], start=1):
        if i - last_idx >= total_gap:
            selected.append(d)
            selected_indices.append(i)
            last_idx = i
    return selected, selected_indices


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
    embargo_sessions: int = 0,
    champion_production_policy: str = "daily",
    minimum_effect_size_delta_ic: float = 0.0,
    min_non_overlapping_observations: int = MIN_NON_OVERLAPPING_OBSERVATIONS,
    nested_wf_harness_status: str = NESTED_WF_HARNESS_NOT_BUILT,
    session_calendar: list[str] | None = None,
    session_calendar_digest: str = "",
    experiment_version: str = "",
    champion_policy_artifact_digest: str = "",
    embargo_justification: str = "",
    manifest_fingerprint: str = "",
    ledger_fingerprint: str = "",
    returns_file_digest: str = "",
    returns_file_locator: str = "",
    expert_score_digests: dict[str, list[str]] | None = None,
    score_coverage: dict[str, Any] | None = None,
    label_observation_end: str = "",
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

    ``nested_wf_harness_status`` is accepted, persisted on the result, and
    kept as a versioned, checkable manifest fact -- but it is NOT used to
    gate promotability. Every Phase A verdict is unconditionally capped at
    ``EXPLORATORY_ONLY`` (Codex review 2026-07-13T17:00:21Z, round 6,
    finding 1): ``nested_wf_harness_status == NESTED_WF_HARNESS_APPLIED``
    is a self-attested manifest string -- a caller can build and fingerprint
    a manifest with that value with no nested-WF/purging harness having
    actually generated an outer-fold evaluation calendar. There is no
    typed, immutable WF-evidence reference in this codebase, generated by
    a harness and independently verified by this runner, for the field to
    be checked against -- and design doc §5.1 lists the harness itself as
    "Not built -- Blocks discovery". Inventing a verification scheme for a
    harness that does not exist would manufacture false confidence, which
    is worse than the honest current gap. Until a real harness AND a real
    verifier exist, no run -- regardless of what the manifest claims --
    may produce a promotable verdict. A future PR that builds the harness
    would add an actual verifier function here and change this cap to
    check that verifier's result, not the raw manifest string.
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

    # Evaluation calendar: block-rebalance policy (Codex review round 9).
    # The runner evaluates ONE policy matching the manifest's
    # rebalance_cadence="block_rebalance": select a portfolio every
    # block_length_days, hold between rebalances, charge turnover/cost
    # only at rebalance points. There is no separate daily evaluation —
    # all reported metrics (delta_ic, delta_return, delta_sharpe, and the
    # primary test's delta_net_return_test) come from the same
    # block-rebalance evaluation, so the estimand is unambiguous.
    non_overlap_dates, selected_block_indices = select_non_overlapping_dates(
        dates, block_length_days, embargo=embargo_sessions,
        session_calendar=session_calendar,
    )
    if len(non_overlap_dates) >= min_non_overlapping_observations:
        eval_dates = non_overlap_dates
        test_method = TEST_METHOD_NON_OVERLAPPING
    else:
        eval_dates = dates
        test_method = TEST_METHOD_HAC_FALLBACK

    champ_result = evaluate_strategy(
        name=f"champion ({champion_expert.name})",
        score_fn=lambda dt: champion_scores(champion_expert, dt),
        dates=eval_dates,
        forward_returns=forward_returns,
        top_n=top_n,
        cost_bps=cost_bps,
    )

    l1_result = evaluate_strategy(
        name="L1 (equal-weight)",
        score_fn=lambda dt: l1_equal_weight(experts, dt),
        dates=eval_dates,
        forward_returns=forward_returns,
        top_n=top_n,
        cost_bps=cost_bps,
    )

    (
        paired_dates, paired_champ_rets, paired_l1_rets,
        paired_champ_ics, paired_l1_ics, n_excluded_pairing,
    ) = pair_evaluations_by_date(champ_result, l1_result, top_n)

    # The non-overlapping-block floor must hold for the observations
    # ACTUALLY available to the paired test, not just the pre-pairing
    # candidate count -- asymmetric coverage/undersized selections can
    # shrink the usable set below the floor even when the initial block
    # selection cleared it.
    if test_method == TEST_METHOD_NON_OVERLAPPING and len(paired_dates) < min_non_overlapping_observations:
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

    # delta_ic_test must be PAIRED: compute only on dates where BOTH
    # arms have finite IC (Codex round 5, finding 4).
    paired_ic_dates = [
        (c_ic, l_ic) for c_ic, l_ic in zip(paired_champ_ics, paired_l1_ics)
        if math.isfinite(c_ic) and math.isfinite(l_ic)
    ]
    n_paired_ic_dates = len(paired_ic_dates)
    # Below the same minimum-observations floor used for the return
    # series, a handful of paired IC dates is too unstable to trust --
    # treat as insufficient (NaN) rather than a numerically-finite-but-
    # meaningless point estimate ("make insufficient IC observations
    # non-promotable").
    if n_paired_ic_dates >= min_non_overlapping_observations:
        delta_ic_test = (
            float(np.mean([l for _, l in paired_ic_dates]))
            - float(np.mean([c for c, _ in paired_ic_dates]))
        )
    else:
        delta_ic_test = float("nan")

    if test_method != TEST_METHOD_NON_OVERLAPPING:
        verdict = "EXPLORATORY_ONLY"
        detail = (
            f"Only {len(paired_dates)} paired non-overlapping "
            f"({block_length_days}d-spaced) observations available (need >= "
            f"{min_non_overlapping_observations} for the primary test, after "
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
        # Round 6, item 5: a passing test on fewer than
        # MIN_CONFIRMATORY_OBSERVATIONS non-overlapping blocks lacks the
        # power to distinguish a real effect from a lucky draw — cap at
        # EXPLORATORY_ONLY until more data is available.
        if len(paired_dates) < MIN_CONFIRMATORY_OBSERVATIONS:
            verdict = "EXPLORATORY_ONLY"
            detail = (
                f"L1 outperforms champion net-of-cost at p={p_val:.4f} < "
                f"alpha={alpha} with delta_ic={delta_ic_test:.4f} >= "
                f"{minimum_effect_size_delta_ic}, but only "
                f"{len(paired_dates)} paired non-overlapping observations "
                f"are available (need >= {MIN_CONFIRMATORY_OBSERVATIONS} for "
                f"a confirmatory verdict — see power justification in "
                f"MIN_CONFIRMATORY_OBSERVATIONS). This result is promising "
                f"but exploratory; it must not be promoted to "
                f"L1_BEATS_CHAMPION until the observation count clears the "
                f"confirmatory floor."
            )
        else:
            verdict = "L1_BEATS_CHAMPION"
            detail = (
                f"L1 outperforms champion net-of-cost at p={p_val:.4f} < alpha={alpha} "
                f"with IC effect size delta_ic={delta_ic_test:.4f} >= "
                f"{minimum_effect_size_delta_ic} on {len(paired_dates)} paired "
                f"non-overlapping observations (>= {MIN_CONFIRMATORY_OBSERVATIONS} "
                f"confirmatory floor). Proceed to L2 comparison."
            )

    # Round 6, finding 1 (Codex review 2026-07-13T17:00:21Z): the previous
    # version only capped when nested_wf_harness_status != APPLIED, which
    # meant a caller could build and fingerprint a manifest that simply
    # SETS nested_wf_harness_status to NESTED_WF_HARNESS_APPLIED and the
    # runner would emit a promotable verdict -- with no actual harness
    # having generated an outer-fold calendar, and nothing here verifying
    # that claim against anything. A manifest field proves who wrote the
    # claim, not that the prerequisite ran. No typed, immutable,
    # harness-generated WF-evidence artifact exists yet in this codebase
    # (design doc §5.1: "Nested WF + purging harness | Not built | Blocks
    # discovery"), so there is nothing to verify nested_wf_harness_status
    # against. Building a fake verification scheme for a harness that does
    # not exist would be worse than doing nothing (false confidence).
    #
    # The correct, honest, minimal fix: cap EVERY Phase A verdict at
    # EXPLORATORY_ONLY, UNCONDITIONALLY, regardless of
    # nested_wf_harness_status's value. The field/constants/manifest
    # wiring are kept as versioned, checkable scaffolding for when a real
    # harness + verifier eventually exists -- a future PR would add an
    # actual verifier function and change the condition below to check
    # its result, not the raw manifest string.
    if verdict != "EXPLORATORY_ONLY":
        underlying_verdict, underlying_detail = verdict, detail
        verdict = "EXPLORATORY_ONLY"
        detail = (
            f"No verified nested-WF/purging harness evidence exists for this "
            f"run -- nested_wf_harness_status={nested_wf_harness_status!r} is "
            f"a self-attested manifest field, not verifiable evidence, and "
            f"design doc §5.1 lists the harness itself as not built. Every "
            f"Phase A verdict is capped at EXPLORATORY_ONLY, unconditionally, "
            f"until a typed, harness-generated, runner-verified WF-evidence "
            f"reference exists and is checked here (not merely attested in "
            f"the manifest). Underlying (non-binding) result: "
            f"{underlying_verdict} -- {underlying_detail}"
        )

    if champion_production_policy != "block_rebalance":
        detail += (
            f" NOTE: this result compares L1 and champion under a "
            f"block-rebalance evaluation policy; the production champion "
            f"uses {champion_production_policy!r} rebalancing. The result "
            f"applies to the block-rebalance estimand and must not be "
            f"directly interpreted as improvement over the production "
            f"{champion_production_policy}-rebalance champion without a "
            f"separate {champion_production_policy}-policy validation."
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
        n_test_dates=len(eval_dates),
        n_paired_test_dates=len(paired_dates),
        n_test_dates_excluded_asymmetric_or_undersized=n_excluded_pairing,
        n_paired_ic_dates=n_paired_ic_dates,
        block_length_days=block_length_days,
        embargo_sessions=embargo_sessions,
        block_spacing_unit="session_index",
        estimand_policy="block_rebalance_paired",
        champion_production_policy=champion_production_policy,
        minimum_effect_size_delta_ic=minimum_effect_size_delta_ic,
        min_non_overlapping_observations=min_non_overlapping_observations,
        nested_wf_harness_status=nested_wf_harness_status,
        session_calendar_digest=session_calendar_digest,
        session_calendar_verified=session_calendar is not None,
        selected_block_indices=selected_block_indices,
        experiment_version=experiment_version,
        champion_policy_artifact_digest=champion_policy_artifact_digest,
        embargo_justification=embargo_justification,
        score_coverage=score_coverage or {},
        label_observation_end=label_observation_end,
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
    print(f"Delta IC (test): {result.delta_ic_test:.4f} (minimum required: {result.minimum_effect_size_delta_ic}, on {result.n_paired_ic_dates} paired-IC dates)")
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
    parser.add_argument(
        "--session-calendar",
        required=True,
        help=(
            "JSON file listing every expected trading session (a JSON "
            "array of ISO date strings). The calendar's SHA-256 digest "
            "must match manifest.session_calendar_digest. Spacing between "
            "non-overlapping blocks is measured against this calendar, not "
            "the (potentially compressed) intersection of loaded data."
        ),
    )
    parser.add_argument(
        "--champion-policy-artifact",
        required=True,
        help=(
            "Path to the champion's frozen policy artifact file. Its "
            "SHA-256 digest must match "
            "manifest.champion_policy_artifact_digest — fail closed on "
            "absence/mismatch. Binds the comparison to a specific, "
            "digested champion policy."
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

    # Bind manifest to ledger — reject if the manifest was registered
    # against a different ledger. An EMPTY fingerprint is also rejected
    # (fail-closed, not fail-open): allowing an unbound manifest through
    # would let a caller pair it with any arbitrary ledger.
    if not manifest.admissibility_ledger_fingerprint:
        print(
            "ERROR: manifest.admissibility_ledger_fingerprint is empty -- "
            "the manifest does not declare which ledger it is bound to",
            file=sys.stderr,
        )
        return 1
    if manifest.admissibility_ledger_fingerprint != ledger.ledger_fingerprint:
        print(
            f"ERROR: manifest's admissibility_ledger_fingerprint "
            f"({manifest.admissibility_ledger_fingerprint}) does not "
            f"match the supplied ledger's fingerprint "
            f"({ledger.ledger_fingerprint}) -- the manifest was "
            f"registered against a different ledger",
            file=sys.stderr,
        )
        return 1

    # Validate expert set matches a pre-registered expert_sets entry.
    supplied_experts = sorted(args.expert)
    matched_set = False
    for es in manifest.expert_sets:
        if sorted(es.get("experts", [])) == supplied_experts:
            matched_set = True
            break
    if not matched_set:
        print(
            f"ERROR: supplied experts {supplied_experts} do not match any "
            f"pre-registered expert_sets entry in the manifest: "
            f"{[es.get('experts') for es in manifest.expert_sets]}",
            file=sys.stderr,
        )
        return 1

    admitted_digests = admitted_score_digests(ledger)

    # Build expected (expert, date) set from ledger — any admitted record
    # that we can't load is a coverage gap to report (round 5, finding 2).
    expected_by_expert: dict[str, set[str]] = defaultdict(set)
    for record in ledger.records:
        if record.get("admitted") and record.get("expert_name") in args.expert:
            expected_by_expert[record["expert_name"]].add(
                record.get("prediction_date", "")
            )

    experts = []
    score_coverage: dict[str, Any] = {}
    for name, score_dir in zip(args.expert, args.score_dir):
        print(f"Loading {name} scores from {score_dir}...")
        expert = load_expert_scores(name, Path(score_dir), admitted_digests=admitted_digests)
        expected = expected_by_expert.get(name, set())
        loaded = set(expert.dates)
        missing = sorted(expected - loaded)
        if missing:
            # Round 6, finding 3 (Codex review 2026-07-13T17:00:21Z): a
            # warning-and-continue here turns an immutable admitted
            # calendar into a post-hoc subset chosen by whichever files
            # happen to be present/digest-valid, which can change both
            # which names get selected and the significance of the
            # resulting test. Require complete coverage of every
            # ledger-admitted record for every selected expert; fail
            # closed rather than silently evaluate a shrunk calendar.
            print(
                f"ERROR: {len(missing)} ledger-admitted dates could not "
                f"be loaded for {name} (digest mismatch or missing file): "
                f"{missing[:5]}{'...' if len(missing) > 5 else ''} -- Phase A "
                "requires complete coverage of every admitted record for "
                "every selected expert; a warn-and-continue here would let "
                "the evaluated calendar be silently determined by which "
                "score files happen to be present, not by the pre-registered "
                "ledger",
                file=sys.stderr,
            )
            return 1
        coverage_rate = len(loaded) / len(expected) if expected else 0.0
        score_coverage[name] = {
            "expected": len(expected),
            "loaded": len(loaded),
            "missing": len(missing),
            "coverage_rate": round(coverage_rate, 4),
            "missing_dates_sample": missing[:10],
        }
        print(f"  {len(expert.dates)}/{len(expected)} ledger-admitted dates loaded ({coverage_rate:.1%})")
        experts.append(expert)

    # Resolve label_observation_end from ledger for provenance persistence.
    admitted_label_ends = {
        record.get("label_observation_end")
        for record in ledger.records
        if record.get("admitted") and record.get("label_observation_end")
        and record["label_observation_end"] != "MISSING"
    }
    label_observation_end = (
        next(iter(admitted_label_ends)) if len(admitted_label_ends) == 1 else ""
    )

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

    # Load statistical config from manifest BEFORE any check that
    # references these values (round 6, item 1: block_length_days was
    # used at the label-horizon check before being assigned here).
    cost_bps = float(manifest.cost_assumptions.get("base_cost_bps", 0.0))
    block_length_days = int(
        manifest.statistical_test.get("block_length_days", 60)
    )
    minimum_effect_size_delta_ic = float(
        manifest.statistical_test.get("minimum_effect_size_delta_ic", 0.0)
    )
    min_non_overlapping_observations = int(
        manifest.statistical_test.get(
            "min_non_overlapping_observations",
            MIN_NON_OVERLAPPING_OBSERVATIONS,
        )
    )
    embargo_sessions = int(
        manifest.statistical_test.get("embargo_sessions", 0)
    )
    if embargo_sessions <= 0:
        print(
            f"ERROR: manifest.statistical_test.embargo_sessions="
            f"{embargo_sessions} -- the design (§4.1/§4.2) requires blocks "
            f"at least label_horizon PLUS embargo; a zero or absent embargo "
            f"does not implement 'plus embargo' and is rejected. Set a "
            f"positive embargo tied to the training/label contract.",
            file=sys.stderr,
        )
        return 1
    champion_production_policy = manifest.champion_production_policy or "daily"

    if not manifest.experiment_version:
        print(
            "ERROR: manifest.experiment_version is empty -- the "
            "block-rebalance evaluation is a distinct research arm (not a "
            "repair to the daily champion comparison) and requires a named, "
            "versioned experiment design",
            file=sys.stderr,
        )
        return 1

    # Session calendar: load, digest-verify, and pass to the runner for
    # calendar-indexed spacing (Codex review round 11/12).
    if not manifest.session_calendar_digest:
        print(
            "ERROR: manifest.session_calendar_digest is empty -- the "
            "manifest must declare the expected calendar digest before "
            "the run, not learn it at runtime (post-hoc calendar problem)",
            file=sys.stderr,
        )
        return 1
    session_calendar_digest = manifest.session_calendar_digest

    cal_path = Path(args.session_calendar)
    cal_bytes = cal_path.read_bytes()
    actual_cal_digest = f"sha256:{hashlib.sha256(cal_bytes).hexdigest()}"
    session_calendar: list[str] = json.loads(cal_bytes)
    if not isinstance(session_calendar, list) or not all(
        isinstance(d, str) for d in session_calendar
    ):
        print(
            "ERROR: --session-calendar must be a JSON array of ISO date "
            "strings",
            file=sys.stderr,
        )
        return 1
    if not session_calendar:
        print("ERROR: session calendar is empty", file=sys.stderr)
        return 1
    if session_calendar != sorted(set(session_calendar)):
        print(
            "ERROR: session calendar must be sorted and contain unique "
            "sessions",
            file=sys.stderr,
        )
        return 1
    if actual_cal_digest != session_calendar_digest:
        print(
            f"ERROR: session calendar digest {actual_cal_digest} does not "
            f"match manifest.session_calendar_digest "
            f"{session_calendar_digest}",
            file=sys.stderr,
        )
        return 1
    print(f"  Session calendar: {len(session_calendar)} sessions (digest {session_calendar_digest})")

    # Champion policy artifact: load, digest-verify (Codex review round 12).
    if not manifest.champion_policy_artifact_digest:
        print(
            "ERROR: manifest.champion_policy_artifact_digest is empty -- "
            "the experiment cannot claim 'L1 vs frozen champion' without "
            "a digested, verifiable champion policy artifact",
            file=sys.stderr,
        )
        return 1
    policy_path = Path(args.champion_policy_artifact)
    if not policy_path.exists():
        print(
            f"ERROR: --champion-policy-artifact {policy_path} does not "
            f"exist",
            file=sys.stderr,
        )
        return 1
    policy_bytes = policy_path.read_bytes()
    actual_policy_digest = f"sha256:{hashlib.sha256(policy_bytes).hexdigest()}"
    if actual_policy_digest != manifest.champion_policy_artifact_digest:
        print(
            f"ERROR: champion policy artifact digest "
            f"{actual_policy_digest} does not match "
            f"manifest.champion_policy_artifact_digest "
            f"{manifest.champion_policy_artifact_digest}",
            file=sys.stderr,
        )
        return 1
    print(f"  Champion policy artifact verified (digest {actual_policy_digest})")

    if manifest.rebalance_cadence != "block_rebalance":
        print(
            f"ERROR: manifest.rebalance_cadence={manifest.rebalance_cadence!r} "
            f"-- the primary test evaluates a block-rebalance policy (portfolio "
            f"held for block_length_days={block_length_days} between rebalances, "
            f"costs charged only at rebalance points); the manifest must "
            f"declare 'block_rebalance' to match the implemented estimand",
            file=sys.stderr,
        )
        return 1

    manifest_one_sided = manifest.statistical_test.get("one_sided")
    if manifest_one_sided is not True:
        print(
            f"ERROR: manifest.statistical_test.one_sided="
            f"{manifest_one_sided!r} -- the implemented Newey-West paired "
            f"t-test is one-sided (H1: mean(L1) > mean(champion)); a "
            f"pre-registered field that disagrees with or is absent from "
            f"the implementation is not a frozen statistical contract",
            file=sys.stderr,
        )
        return 1

    print(f"Loading forward returns from {args.returns_file}...")
    returns_path = Path(args.returns_file)
    returns_file_digest, returns_file_locator = verify_returns_file_digest(returns_path, ledger)
    fwd_returns = load_forward_returns(returns_path)
    print(f"  {len(fwd_returns)} dates loaded (digest {returns_file_digest} verified against ledger)")

    # Label-horizon consistency: the block length must be >= the label
    # horizon to ensure non-overlapping blocks produce truly non-overlapping
    # forward returns (round 6, item 1: a block shorter than the label
    # horizon is an invalid primary test, not a "weaker" one).
    total_block_spacing = block_length_days + embargo_sessions
    if ledger.label_horizon_days and total_block_spacing < ledger.label_horizon_days:
        print(
            f"ERROR: block_length_days + embargo_sessions = "
            f"{block_length_days} + {embargo_sessions} = {total_block_spacing} < "
            f"ledger.label_horizon_days={ledger.label_horizon_days}; "
            f"non-overlapping blocks would still have overlapping forward "
            f"returns, invalidating the primary statistical test. Increase "
            f"block_length_days + embargo_sessions in the manifest to >= "
            f"label_horizon_days.",
            file=sys.stderr,
        )
        return 1

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

    result = run_phase_a(
        experts=experts,
        forward_returns=fwd_returns,
        champion_name=champion_name,
        top_n=top_n,
        alpha=alpha,
        cost_bps=cost_bps,
        block_length_days=block_length_days,
        embargo_sessions=embargo_sessions,
        champion_production_policy=champion_production_policy,
        minimum_effect_size_delta_ic=minimum_effect_size_delta_ic,
        min_non_overlapping_observations=min_non_overlapping_observations,
        nested_wf_harness_status=manifest.nested_wf_harness_status,
        session_calendar=session_calendar,
        session_calendar_digest=session_calendar_digest,
        experiment_version=manifest.experiment_version,
        champion_policy_artifact_digest=manifest.champion_policy_artifact_digest,
        embargo_justification=manifest.embargo_justification,
        manifest_fingerprint=manifest.manifest_fingerprint,
        ledger_fingerprint=ledger.ledger_fingerprint,
        returns_file_digest=returns_file_digest,
        returns_file_locator=returns_file_locator,
        expert_score_digests=expert_score_digests,
        score_coverage=score_coverage,
        label_observation_end=label_observation_end,
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
