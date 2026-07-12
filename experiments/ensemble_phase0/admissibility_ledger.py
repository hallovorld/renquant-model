"""Stage 0 admissibility ledger builder for ensemble combination experiments.

Per §3.0 of the ensemble combination experiment design (model PR #48):
every proposed expert must pass an admissibility ledger for every historical
prediction date BEFORE any L1-L3 comparison may start.

The ledger records per-expert, per-prediction-date:
  - model/content fingerprint
  - training cutoff (last training date)
  - feature/data cutoff (as-of date for inference inputs)
  - score timestamp (when the score was generated)
  - universe coverage (how many tickers scored)
  - missingness (fraction of universe with missing scores)
  - score orientation (higher = more bullish? sign convention)
  - realized label availability (whether fwd_60d labels exist for evaluation)

Usage:
    python experiments/ensemble_phase0/admissibility_ledger.py \
        --expert xgb --score-dir /path/to/xgb/scores \
        --expert patchtst --score-dir /path/to/patchtst/scores \
        --universe-file /path/to/universe.csv \
        --output-dir experiments/ensemble_phase0/output
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExpertAdmissibilityRecord:
    """Single-date admissibility record for one expert."""

    expert_name: str
    prediction_date: str
    model_fingerprint: str
    training_cutoff: str
    feature_data_cutoff: str
    score_timestamp: str
    universe_size: int
    scored_count: int
    missing_count: int
    missingness_rate: float
    score_orientation: str
    has_realized_labels: bool
    admitted: bool
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class ExpertSpec:
    """Specification for one expert to be audited."""

    name: str
    score_dir: Path
    orientation: str = "higher_is_bullish"
    model_metadata_key: str = "model_content_sha256"


@dataclass
class AdmissibilityLedger:
    """Complete admissibility ledger for an ensemble experiment."""

    created_at: str = ""
    experts: list[str] = field(default_factory=list)
    universe_size: int = 0
    date_range: tuple[str, str] = ("", "")
    records: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    ledger_fingerprint: str = ""

    def compute_fingerprint(self) -> str:
        content = json.dumps(self.records, sort_keys=True).encode()
        return f"sha256:{hashlib.sha256(content).hexdigest()}"


SUPPORTED_SCORE_FORMATS = {".json"}


def load_score_file(path: Path) -> dict[str, Any] | None:
    """Load a single score file. Only JSON is supported.

    Parquet is rejected: it cannot carry the same provenance metadata
    (fingerprint, training cutoff, score timestamp, etc.) inline.
    A versioned parquet+sidecar schema may be added later.
    """
    if path.suffix == ".json":
        return json.loads(path.read_text())
    return None


def extract_metadata_from_score(
    score_data: dict[str, Any],
    expert: ExpertSpec,
) -> dict[str, Any]:
    """Extract admissibility-relevant metadata from a score payload."""
    meta: dict[str, Any] = {}

    meta["model_fingerprint"] = score_data.get(
        expert.model_metadata_key,
        score_data.get("fingerprint", "MISSING"),
    )
    meta["training_cutoff"] = score_data.get(
        "training_cutoff",
        score_data.get("train_end_date", "MISSING"),
    )
    meta["feature_data_cutoff"] = score_data.get(
        "as_of_date",
        score_data.get("feature_cutoff", "MISSING"),
    )
    meta["score_timestamp"] = score_data.get(
        "score_timestamp",
        score_data.get("created_at", "MISSING"),
    )

    meta["has_realized_labels"] = bool(
        score_data.get("has_realized_labels", False)
    )

    scores = score_data.get("scores", {})
    if isinstance(scores, dict):
        meta["score_keys"] = list(scores.keys())
        meta["scores"] = scores
    else:
        meta["score_keys"] = []
        meta["scores"] = {}

    return meta


def validate_expert_date(
    expert: ExpertSpec,
    prediction_date: str,
    score_meta: dict[str, Any],
    universe_tickers: list[str],
    *,
    decision_timestamp_max: str | None = None,
) -> ExpertAdmissibilityRecord:
    """Validate one expert on one prediction date against Stage 0 requirements.

    Args:
        decision_timestamp_max: upper bound for score_timestamp (ISO-8601 date
            prefix). If provided, scores generated AFTER this date are rejected
            as potential look-ahead. If absent, defaults to prediction_date
            (same-day cap).
    """
    reasons: list[str] = []

    fingerprint = score_meta.get("model_fingerprint", "MISSING")
    if fingerprint == "MISSING":
        reasons.append("missing model fingerprint")

    training_cutoff = score_meta.get("training_cutoff", "MISSING")
    if training_cutoff == "MISSING":
        reasons.append("missing training cutoff date")
    elif training_cutoff != "MISSING" and training_cutoff >= prediction_date:
        reasons.append(
            f"training cutoff {training_cutoff} >= prediction date "
            f"{prediction_date} (lookahead)"
        )

    feature_cutoff = score_meta.get("feature_data_cutoff", "MISSING")
    if feature_cutoff == "MISSING":
        reasons.append("missing feature/data cutoff")
    elif feature_cutoff != "MISSING" and feature_cutoff > prediction_date:
        reasons.append(
            f"feature cutoff {feature_cutoff} > prediction date "
            f"{prediction_date} (lookahead)"
        )

    score_ts = score_meta.get("score_timestamp", "MISSING")
    ts_upper = decision_timestamp_max or prediction_date
    if score_ts == "MISSING":
        reasons.append("missing score timestamp")
    elif score_ts != "MISSING":
        try:
            ts_date = score_ts[:10]
            if ts_date < prediction_date:
                reasons.append(
                    f"score_timestamp date {ts_date} < prediction date "
                    f"{prediction_date} (score generated before prediction date)"
                )
            if ts_date > ts_upper:
                reasons.append(
                    f"score_timestamp date {ts_date} > decision cutoff "
                    f"{ts_upper} (late score — potential look-ahead)"
                )
        except (TypeError, IndexError):
            reasons.append(f"score_timestamp unparseable: {score_ts!r}")

    # Universe coverage: intersect scored keys with expected universe.
    score_keys = score_meta.get("score_keys", [])
    universe_set = set(universe_tickers)
    scored_set = set(score_keys)
    unknown_keys = scored_set - universe_set
    if unknown_keys:
        reasons.append(
            f"{len(unknown_keys)} unknown ticker(s) not in universe: "
            f"{sorted(unknown_keys)[:5]}"
        )
    duplicate_keys = len(score_keys) - len(scored_set)
    if duplicate_keys > 0:
        reasons.append(f"{duplicate_keys} duplicate score key(s)")

    scored_expected = universe_set & scored_set
    universe_size = len(universe_tickers)
    scored = len(scored_expected)
    missing = universe_size - scored
    missingness = missing / universe_size if universe_size > 0 else 1.0

    if missingness > 0.20:
        reasons.append(
            f"missingness {missingness:.1%} exceeds 20% threshold"
        )

    has_labels = bool(score_meta.get("has_realized_labels", False))

    return ExpertAdmissibilityRecord(
        expert_name=expert.name,
        prediction_date=prediction_date,
        model_fingerprint=fingerprint,
        training_cutoff=training_cutoff,
        feature_data_cutoff=feature_cutoff,
        score_timestamp=score_meta.get("score_timestamp", "MISSING"),
        universe_size=universe_size,
        scored_count=scored,
        missing_count=missing,
        missingness_rate=missingness,
        score_orientation=expert.orientation,
        has_realized_labels=has_labels,
        admitted=len(reasons) == 0,
        rejection_reasons=reasons,
    )


def build_complementarity_report(
    expert_scores: dict[str, dict[str, dict[str, float]]],
    prediction_dates: list[str],
    universe_tickers: list[str],
) -> dict[str, Any]:
    """Build the complementarity diagnostics required by §3.0.

    Reports cross-sectional score correlation, rank correlation,
    and disagreement coverage between experts.
    """
    try:
        import numpy as np
        from scipy import stats
    except ImportError:
        return {"error": "numpy/scipy required for complementarity analysis"}

    expert_names = sorted(expert_scores.keys())
    if len(expert_names) < 2:
        return {"error": "need at least 2 experts for complementarity"}

    correlations: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []

    for dt in prediction_dates:
        for i, e1 in enumerate(expert_names):
            for e2 in expert_names[i + 1 :]:
                s1 = expert_scores.get(e1, {}).get(dt, {})
                s2 = expert_scores.get(e2, {}).get(dt, {})
                common = sorted(set(s1.keys()) & set(s2.keys()))
                if len(common) < 10:
                    continue
                v1 = np.array([s1[t] for t in common])
                v2 = np.array([s2[t] for t in common])
                r_pearson = float(np.corrcoef(v1, v2)[0, 1])
                r_spearman = float(stats.spearmanr(v1, v2).statistic)
                correlations.append(
                    {
                        "date": dt,
                        "experts": [e1, e2],
                        "pearson": round(r_pearson, 4),
                        "spearman": round(r_spearman, 4),
                        "n_common": len(common),
                    }
                )

                rank1 = np.argsort(np.argsort(-v1))
                rank2 = np.argsort(np.argsort(-v2))
                rank_diff = np.abs(rank1.astype(int) - rank2.astype(int))
                n_disagree = int(np.sum(rank_diff >= 5))
                disagreements.append(
                    {
                        "date": dt,
                        "experts": [e1, e2],
                        "n_rank_disagree_ge5": n_disagree,
                        "disagree_frac": round(n_disagree / len(common), 4),
                    }
                )

    avg_pearson = (
        sum(c["pearson"] for c in correlations) / len(correlations)
        if correlations
        else None
    )
    avg_spearman = (
        sum(c["spearman"] for c in correlations) / len(correlations)
        if correlations
        else None
    )
    avg_disagree = (
        sum(d["disagree_frac"] for d in disagreements) / len(disagreements)
        if disagreements
        else None
    )

    return {
        "expert_pairs": [
            {"pair": [e1, e2]}
            for i, e1 in enumerate(expert_names)
            for e2 in expert_names[i + 1 :]
        ],
        "n_dates_evaluated": len(prediction_dates),
        "avg_pearson_correlation": avg_pearson,
        "avg_spearman_correlation": avg_spearman,
        "avg_rank_disagreement_fraction": avg_disagree,
        "per_date_correlations": correlations[:20],
        "complementarity_assessment": _assess_complementarity(
            avg_pearson, avg_spearman, avg_disagree
        ),
    }


def _assess_complementarity(
    avg_pearson: float | None,
    avg_spearman: float | None,
    avg_disagree: float | None,
) -> str:
    """Produce a falsifiable complementarity assessment per §3.0."""
    if avg_pearson is None or avg_spearman is None:
        return "INSUFFICIENT_DATA"
    if abs(avg_pearson) > 0.95 and abs(avg_spearman) > 0.95:
        return "NEAR_DUPLICATE — experts produce near-identical scores"
    if avg_disagree is not None and avg_disagree < 0.05:
        return "LOW_DISAGREEMENT — experts rarely alter each other's rankings"
    return "PLAUSIBLE — experts show sufficient score diversity for combination"


def build_ledger(
    experts: list[ExpertSpec],
    prediction_dates: list[str],
    universe_tickers: list[str],
    score_loader: Any = None,
    *,
    complementarity_assessment: str | None = None,
) -> AdmissibilityLedger:
    """Build the complete admissibility ledger.

    This is the main entry point. In production use, pass a score_loader
    callable that returns score metadata for (expert, date) pairs.
    For testing, the ledger can be built from pre-extracted metadata.

    Args:
        complementarity_assessment: result string from
            build_complementarity_report. Must be "PLAUSIBLE" for
            all_experts_fully_admitted to be True. None = not yet
            evaluated (fail-closed).
    """
    ledger = AdmissibilityLedger(
        created_at=datetime.utcnow().isoformat() + "Z",
        experts=[e.name for e in experts],
        universe_size=len(universe_tickers),
        date_range=(
            (prediction_dates[0], prediction_dates[-1])
            if prediction_dates
            else ("", "")
        ),
    )

    per_expert_stats: dict[str, dict[str, int]] = {}
    for expert in experts:
        admitted = 0
        rejected = 0
        for dt in prediction_dates:
            if score_loader is not None:
                score_meta = score_loader(expert, dt)
            else:
                score_meta = {
                    "model_fingerprint": "MISSING",
                    "training_cutoff": "MISSING",
                    "feature_data_cutoff": "MISSING",
                    "score_timestamp": "MISSING",
                    "score_keys": [],
                }

            record = validate_expert_date(
                expert, dt, score_meta, universe_tickers
            )
            ledger.records.append(asdict(record))
            if record.admitted:
                admitted += 1
            else:
                rejected += 1

        per_expert_stats[expert.name] = {
            "admitted": admitted,
            "rejected": rejected,
            "total": admitted + rejected,
            "admission_rate": (
                round(admitted / (admitted + rejected), 4)
                if (admitted + rejected) > 0
                else 0
            ),
        }

    total_records = len(ledger.records)
    per_expert_ok = (
        total_records > 0
        and all(
            s["admitted"] > 0 and s["rejected"] == 0
            for s in per_expert_stats.values()
        )
    )
    complementarity_ok = complementarity_assessment == "PLAUSIBLE"

    ledger.summary = {
        "total_records": total_records,
        "per_expert": per_expert_stats,
        "complementarity_assessment": complementarity_assessment or "NOT_EVALUATED",
        "complementarity_ok": complementarity_ok,
        "all_experts_fully_admitted": per_expert_ok and complementarity_ok,
    }
    ledger.ledger_fingerprint = ledger.compute_fingerprint()

    return ledger


def write_ledger(ledger: AdmissibilityLedger, output_dir: Path) -> Path:
    """Write the ledger to disk as a JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "admissibility_ledger.json"
    payload = {
        "created_at": ledger.created_at,
        "experts": ledger.experts,
        "universe_size": ledger.universe_size,
        "date_range": ledger.date_range,
        "summary": ledger.summary,
        "ledger_fingerprint": ledger.ledger_fingerprint,
        "records": ledger.records,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    return output_path


def _discover_prediction_dates(experts: list[ExpertSpec]) -> list[str]:
    """Discover prediction dates from score files in expert score directories.

    Scans each expert's score_dir for files named YYYY-MM-DD.{json,parquet}
    and returns the sorted union of all dates found.
    """
    import re

    suffixes = "|".join(s.lstrip(".") for s in SUPPORTED_SCORE_FORMATS)
    date_re = re.compile(rf"^(\d{{4}}-\d{{2}}-\d{{2}})\.({suffixes})$")
    dates: set[str] = set()
    for expert in experts:
        if expert.score_dir.is_dir():
            for f in expert.score_dir.iterdir():
                m = date_re.match(f.name)
                if m:
                    dates.add(m.group(1))
    return sorted(dates)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Stage 0 admissibility ledger for ensemble experiments"
    )
    parser.add_argument(
        "--expert",
        action="append",
        required=True,
        help="Expert name (repeat for each expert)",
    )
    parser.add_argument(
        "--score-dir",
        action="append",
        required=True,
        help="Score directory for each expert (same order as --expert)",
    )
    parser.add_argument(
        "--universe-file",
        required=True,
        help="Path to universe ticker list (one ticker per line or CSV)",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/ensemble_phase0/output",
        help="Output directory for ledger files",
    )
    args = parser.parse_args()

    if len(args.expert) != len(args.score_dir):
        print("ERROR: --expert and --score-dir counts must match", file=sys.stderr)
        sys.exit(1)

    universe_path = Path(args.universe_file)
    if not universe_path.exists():
        print(f"ERROR: universe file not found: {universe_path}", file=sys.stderr)
        sys.exit(1)

    universe_tickers = [
        line.strip()
        for line in universe_path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    experts = [
        ExpertSpec(name=name, score_dir=Path(sd))
        for name, sd in zip(args.expert, args.score_dir)
    ]

    # Discover prediction dates from score directories.
    prediction_dates = _discover_prediction_dates(experts)
    if not prediction_dates:
        print(
            "ERROR: no prediction dates discovered from score directories — "
            "cannot build a ledger with zero dates (fail-closed)",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Building admissibility ledger for {len(experts)} experts")
    print(f"Universe: {len(universe_tickers)} tickers")
    print(f"Prediction dates: {len(prediction_dates)} ({prediction_dates[0]} .. {prediction_dates[-1]})")

    def _file_score_loader(expert: ExpertSpec, dt: str) -> dict[str, Any]:
        """Load score metadata from the expert's score directory."""
        for suffix in SUPPORTED_SCORE_FORMATS:
            candidate = expert.score_dir / f"{dt}{suffix}"
            if candidate.exists():
                data = load_score_file(candidate)
                if data is not None:
                    return extract_metadata_from_score(data, expert)
        return {
            "model_fingerprint": "MISSING",
            "training_cutoff": "MISSING",
            "feature_data_cutoff": "MISSING",
            "score_timestamp": "MISSING",
            "scored_count": 0,
        }

    # First pass: build ledger without complementarity to collect scores.
    ledger_pass1 = build_ledger(
        experts, prediction_dates, universe_tickers,
        score_loader=_file_score_loader,
    )

    # Compute complementarity report (§3.0) — required for admission.
    expert_scores: dict[str, dict[str, dict[str, float]]] = {}
    for record in ledger_pass1.records:
        name = record["expert_name"]
        dt = record["prediction_date"]
        if name not in expert_scores:
            expert_scores[name] = {}
        for exp in experts:
            if exp.name == name:
                meta = _file_score_loader(exp, dt)
                scores = meta.get("scores", {})
                if scores:
                    expert_scores[name][dt] = {
                        k: float(v) for k, v in scores.items()
                        if isinstance(v, (int, float))
                    }
                break

    comp_assessment: str | None = None
    if len(expert_scores) >= 2:
        comp = build_complementarity_report(
            expert_scores, prediction_dates, universe_tickers
        )
        comp_assessment = comp.get("complementarity_assessment")
        comp_path = Path(args.output_dir) / "complementarity_report.json"
        comp_path.parent.mkdir(parents=True, exist_ok=True)
        comp_path.write_text(json.dumps(comp, indent=2) + "\n")
        print(f"Complementarity report written to {comp_path}")
        print(f"  Assessment: {comp_assessment}")

    # Rebuild ledger with complementarity result bound in.
    ledger = build_ledger(
        experts, prediction_dates, universe_tickers,
        score_loader=_file_score_loader,
        complementarity_assessment=comp_assessment,
    )
    output_path = write_ledger(ledger, Path(args.output_dir))
    print(f"Ledger written to {output_path}")
    print(f"Fingerprint: {ledger.ledger_fingerprint}")

    # Fail-closed verdict.
    if ledger.summary.get("all_experts_fully_admitted"):
        print("RESULT: All experts fully admitted — Phase A may proceed")
    else:
        print("RESULT: FAIL — not all experts fully admitted", file=sys.stderr)
        for name, stats in ledger.summary.get("per_expert", {}).items():
            if stats["rejected"] > 0:
                print(f"  {name}: {stats['rejected']}/{stats['total']} rejected")
        if not ledger.summary.get("complementarity_ok"):
            print(
                f"  complementarity: {ledger.summary.get('complementarity_assessment')} "
                f"(must be PLAUSIBLE)",
                file=sys.stderr,
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
