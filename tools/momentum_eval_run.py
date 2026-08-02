#!/usr/bin/env python3
"""Momentum EVAL CLI — the recurring TEST harness over matured labels. (GOAL-7 slice 3)

Wires REAL readers into the pure evaluator core (design §2): per-date
cross-sectional Spearman IC of the artifact-params construction against the
matured forward label, over the ELIGIBLE window only — the caller-side half of
the causal maturity contract. The core REFUSES anything newer regardless
(belt and suspenders). READ-ONLY over the live surfaces with per-file digest
RECORDING; writes ONLY the report under --out-root and the eval ledger.

Construction reuse, never restated: the per-date scores come from the
packaged ``train_momentum_artifact`` (golden-pinned to the sealed v1
``assemble_day`` at <1e-9, PR #196); the per-date IC is the sealed v1
runner's ``_spearman_ic``, imported the way the v2 runner imports it; the
surfaces + digest-recording readers are the TRAIN CLI's ``LiveReaders``.

Exit codes: 0 ok (--dry-run, evaluated, or RECONCILED); 2 usage; 3 refused
(surfaces/artifact/label column missing, or a maturity refusal — nothing
written); 4 report for this (artifact, eval_asof, horizon) already exists AND
is already ledgered (append-only: never overwritten); 5 the ledger refused
the append (the finalized report remains on disk — never re-evaluated — and
a retry reconciles by appending its ledger row once the cause clears).

TWO-FILE PROTOCOL (mirrors the TRAIN CLI, codex review round 3 on PR #196):
the report is finalized (staging write + atomic rename) BEFORE the ledger
append is attempted, so a crash/refusal can only ever leave a valid,
content-sha-verified report with no ledger row — never a ledger row pointing
at a missing report. On startup, a finalized report with no matching ledger
row is RECONCILED rather than rejected or re-evaluated.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name,
                                                  REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: The TRAIN CLI supplies the live surfaces + the digest-recording readers
#: (reused, not copied); the sealed v1 runner supplies the per-date IC
#: definition (imported the way the v2 runner imports it).
TRAIN_CLI = _load_tool("momentum_train_run")
V1 = _load_tool("goal7_momentum_run")

from renquant_model_momentum import (train_momentum_artifact,  # noqa: E402
                                     verify_artifact_content_sha)
from renquant_model_momentum.evaluate import (EVAL_ROW_REQUIRED,  # noqa: E402
                                              STATUS_REFUSED_MATURITY,
                                              append_eval_ledger,
                                              eligible_last_date,
                                              evaluate_momentum_artifact)
from renquant_model_momentum.ledger import (LedgerIntegrityError,  # noqa: E402
                                            load_and_verify_ledger)
from renquant_model_momentum.train import content_sha256_of  # noqa: E402

PANEL_PATH = TRAIN_CLI.PANEL_PATH
SECTORS_PATH = TRAIN_CLI.SECTORS_PATH
OHLCV_ROOT = TRAIN_CLI.OHLCV_ROOT
MARKET = TRAIN_CLI.MARKET
DEFAULT_OUT_ROOT = Path.home() / "renquant-data-store" / "momentum-eval"
LEDGER_BASENAME = "momentum_eval_ledger.jsonl"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


#: How many hex chars of the artifact digest go in the filename. 12 is the repo's
#: standing abbreviation for a content sha in a human-facing identifier; the FULL
#: digest is carried inside the report and in the ledger row, so this is a
#: disambiguator, never the identity itself.
_SHA_IN_PATH = 12


def report_basename(label_horizon_bdays: int, artifact_content_sha256: str) -> str:
    """One report per `(artifact, eval_asof, horizon)` — the ledger's own key.

    Review round 1: the basename was `momentum_eval_h{h}.json`, so a SECOND artifact
    evaluated on the same `eval_asof` and horizon resolved to the FIRST one's path and
    was reconciled-or-refused against it instead of writing its own report. Every
    recurring comparison and every post-retrain re-evaluation on the same date hit that.

    `_reconcile_or_refuse`'s own docstring already said "a report already exists at this
    (artifact, eval_asof, horizon) path" — the contract was stated in the code and
    contradicted by the path.
    """
    sha = str(artifact_content_sha256 or "")
    if len(sha) < _SHA_IN_PATH:
        raise ValueError(
            f"artifact_content_sha256 {sha!r} is too short to identify a report — "
            "the path must carry artifact identity or two artifacts collide")
    return f"momentum_eval_h{int(label_horizon_bdays)}_{sha[:_SHA_IN_PATH]}.json"


def label_column(label_horizon_bdays: int) -> str:
    """horizon -> panel label column, the v2 convention (fwd_20d_excess)."""
    return f"fwd_{int(label_horizon_bdays)}d_excess"


def _panel_columns(panel_path: Path) -> list[str]:
    import pyarrow.parquet as pq
    return list(pq.read_schema(panel_path).names)


def _eligible_dates(all_dates, last_eligible: pd.Timestamp,
                    first_date=None) -> pd.DatetimeIndex:
    """Pure caller-side maturity filter: sorted unique dates <= the bound
    (and >= --first-date when given). The core still REFUSES anything newer —
    this filter is discipline, the core refusal is the guard."""
    ds = pd.DatetimeIndex(pd.unique(pd.DatetimeIndex(all_dates))).sort_values()
    ds = ds[ds <= pd.Timestamp(last_eligible)]
    if first_date is not None:
        ds = ds[ds >= pd.Timestamp(first_date)]
    return ds


class SeriesReaders:
    """EvalSeriesReaders over a prebuilt series + its recorded digests."""

    def __init__(self, series: pd.Series, digests: dict) -> None:
        self._series, self._digests = series, dict(digests)

    def per_date_candidate_series(self) -> pd.Series:
        return self._series

    def read_digests(self) -> dict:
        return dict(self._digests)


def build_per_date_series(artifact: dict, *, label_col: str,
                          last_eligible: pd.Timestamp, first_date=None
                          ) -> tuple[pd.Series, dict, dict]:
    """The per-date candidate statistic over the ELIGIBLE dates only.

    For each eligible panel date: score every panel name with the packaged
    construction under the ARTIFACT's params, then take the sealed v1
    ``_spearman_ic`` against that date's matured label column. Thin dates
    (IC undefined under the frozen names floor) are skipped AND counted —
    they never enter the scored sequence, exactly as in v2.

    Returns (series, read_digests, counts)."""
    readers = TRAIN_CLI.LiveReaders(ohlcv_root=OHLCV_ROOT,
                                    sectors_path=SECTORS_PATH)
    readers.record_digest("panel:" + PANEL_PATH.name, PANEL_PATH)
    panel = pd.read_parquet(PANEL_PATH,
                            columns=["ticker", "date", label_col])
    panel["date"] = pd.to_datetime(panel["date"])
    dates = _eligible_dates(panel["date"], last_eligible, first_date)
    params = dict(artifact["params"])
    counts = {"n_panel_dates": int(panel["date"].nunique()),
              "n_eligible_dates": int(len(dates)),
              "n_thin_dates_skipped": 0}
    out: dict[pd.Timestamp, float] = {}
    for d in dates:
        day = panel[panel["date"] == d]
        labels = day.set_index("ticker")[label_col]
        art_d = train_momentum_artifact(
            d, sorted(day["ticker"].unique()), params, readers=readers)
        scores = {t: (float("nan") if s is None else float(s))
                  for t, s in art_d["scores"].items()}
        ic = V1._spearman_ic(scores, labels)
        if ic is None:
            counts["n_thin_dates_skipped"] += 1
            continue
        out[pd.Timestamp(d)] = float(ic)
    series = pd.Series(out, dtype=float).sort_index()
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.DatetimeIndex(series.index)   # empty-dict case
    return series, readers.read_digests(), counts


def _reconcile_or_refuse(report_path: Path, ledger_path: Path,
                         expected_artifact_sha: str) -> int:
    """A report already exists at this (artifact, eval_asof, horizon) path —
    reconcile or refuse (the startup half of the two-file protocol). A
    finalized report with no ledger row is the ONE recoverable failure the
    protocol allows; reconcile by appending the row for the exact bytes on
    disk — never re-evaluate, never silently drop the report.

    Identity keys on the report's EMBEDDED artifact_content_sha256, verified
    against the artifact being evaluated — the filename's 12-hex prefix is a
    disambiguator, never trusted (codex round 1 on PR #198): a report
    embedding a DIFFERENT artifact's sha at this path is a prefix collision
    or tampering to investigate, not a reconcile candidate."""
    try:
        existing = json.loads(report_path.read_text(encoding="utf-8"))
        if existing.get("content_sha256") != content_sha256_of(existing):
            raise ValueError("report content_sha256 does not recompute")
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({
            "status": "REFUSED-REPORT-EXISTS",
            "report_path": str(report_path),
            "why": f"existing report failed content-sha verification: {exc}",
        }, indent=2))
        return 4

    embedded = existing.get("artifact_content_sha256")
    if embedded != expected_artifact_sha:
        print(json.dumps({
            "status": "REFUSED-REPORT-EXISTS",
            "report_path": str(report_path),
            "why": (f"the report at this path embeds artifact sha "
                    f"{embedded!r}, not the artifact being evaluated "
                    f"({expected_artifact_sha!r}) — identity keys on the "
                    "embedded sha, never the filename; this is a path "
                    "collision or tampering to investigate, not a "
                    "reconcile candidate"),
        }, indent=2))
        return 4

    try:
        rows = load_and_verify_ledger(ledger_path,
                                      required_fields=EVAL_ROW_REQUIRED)
    except LedgerIntegrityError as exc:
        print(json.dumps({
            "status": "REFUSED-LEDGER", "why": str(exc),
            "report_final_written": True, "retry_reconciles": False,
        }, indent=2))
        return 5

    already = any(
        r["artifact_content_sha256"] == existing["artifact_content_sha256"]
        and r["eval_asof"] == existing["eval_asof"]
        and r["label_horizon_bdays"] == existing["label_horizon_bdays"]
        for r in rows)
    if already:
        print(json.dumps({
            "status": "REFUSED-REPORT-EXISTS",
            "report_path": str(report_path),
            "why": ("append-only store: an existing ledgered evaluation is "
                    "never overwritten; a disagreeing re-run is a dispute to "
                    "investigate"),
        }, indent=2))
        return 4

    try:
        row = append_eval_ledger(existing, ledger_path)
    except LedgerIntegrityError as exc:
        print(json.dumps({
            "status": "REFUSED-LEDGER", "why": str(exc),
            "report_final_written": True, "retry_reconciles": True,
        }, indent=2))
        return 5
    print(json.dumps({
        "status": "RECONCILED",
        "why": ("report existed with no matching ledger row — a prior run "
                "crashed or was interrupted between finalize and ledger "
                "append; appended the row for the report already on disk"),
        "eval_asof": existing["eval_asof"],
        "report_path": str(report_path),
        "report_content_sha256": existing["content_sha256"],
        "ledger_row_index": row["row_index"],
        "ledger_row_sha": row["row_sha"],
    }, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", required=True,
                    help="path to the momentum artifact JSON to evaluate")
    ap.add_argument("--ledger", default=None,
                    help="eval ledger path (default <out-root>/"
                         f"{LEDGER_BASENAME})")
    ap.add_argument("--eval-asof", required=True,
                    help="evaluation as-of date YYYY-MM-DD")
    ap.add_argument("--horizon", required=True, type=int,
                    help="label_horizon_bdays; the label column is "
                         "fwd_<horizon>d_excess")
    ap.add_argument("--settle-bdays", type=int, default=1,
                    help="settle sessions after the label window (default 1, "
                         "the blend forward-ledger convention)")
    ap.add_argument("--first-date", default=None,
                    help="optional window start (default: full history up to "
                         "the maturity bound)")
    ap.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT),
                    help="report store root (NEVER a live production path)")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify surfaces + artifact, resolve the eligible "
                         "window and print the plan; write NOTHING, compute "
                         "NO statistic")
    a = ap.parse_args(argv)
    asof = pd.Timestamp(a.eval_asof)
    out_root = Path(a.out_root).expanduser()

    artifact_path = Path(a.artifact).expanduser()
    if not artifact_path.is_file():
        print(json.dumps({
            "status": "REFUSED-ARTIFACT",
            "why": f"artifact file absent: {artifact_path}",
        }, indent=2))
        return 3
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        verify_artifact_content_sha(artifact)
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({
            "status": "REFUSED-ARTIFACT",
            "why": f"artifact failed content-sha verification: {exc}",
            "artifact_path": str(artifact_path),
        }, indent=2))
        return 3

    surfaces = {
        "panel": PANEL_PATH,
        "sectors": SECTORS_PATH,
        "ohlcv_root": OHLCV_ROOT,
        "market_series": OHLCV_ROOT / MARKET / "1d.parquet",
    }
    missing = [k for k, p in surfaces.items() if not p.exists()]
    if missing:
        print(json.dumps({
            "status": "REFUSED-SURFACES-MISSING", "missing": missing,
            "surfaces": {k: str(p) for k, p in surfaces.items()},
        }, indent=2))
        return 3

    label_col = label_column(a.horizon)
    panel_cols = _panel_columns(PANEL_PATH)
    if label_col not in panel_cols:
        print(json.dumps({
            "status": "REFUSED-LABEL-COLUMN",
            "why": (f"panel carries no {label_col!r} column for horizon "
                    f"{a.horizon} — wiring a new horizon's labels is an "
                    "upstream change, never inferred here"),
        }, indent=2))
        return 3

    bound = eligible_last_date(asof, a.horizon, a.settle_bdays)
    ledger_path = (Path(a.ledger).expanduser() if a.ledger
                   else out_root / LEDGER_BASENAME)
    report_path = (out_root / str(asof.date())
                   / report_basename(a.horizon, artifact["content_sha256"]))

    if a.dry_run:
        panel_dates = pd.read_parquet(PANEL_PATH, columns=["date"])["date"]
        dates = _eligible_dates(pd.to_datetime(panel_dates), bound,
                                a.first_date)
        print(json.dumps({
            "dry_run": True,
            "eval_asof": str(asof.date()),
            "label_horizon_bdays": int(a.horizon),
            "settle_bdays": int(a.settle_bdays),
            "eligible_last_date": str(bound.date()),
            "label_column": label_col,
            "artifact_content_sha256": artifact["content_sha256"],
            "n_eligible_dates": int(len(dates)),
            "would_write": [str(report_path), str(ledger_path)],
            "statistics_computed": ("none — dry-run resolves the window and "
                                    "hashes nothing"),
        }, indent=2))
        return 0

    if report_path.exists():
        return _reconcile_or_refuse(report_path, ledger_path,
                                    artifact["content_sha256"])

    series, digests, counts = build_per_date_series(
        artifact, label_col=label_col, last_eligible=bound,
        first_date=a.first_date)
    digests["artifact:" + artifact_path.name] = _sha(artifact_path)
    report = evaluate_momentum_artifact(
        artifact, eval_asof=asof, label_horizon_bdays=a.horizon,
        readers=SeriesReaders(series, digests), settle_bdays=a.settle_bdays,
        context={"label_column": label_col, **counts})

    if report["status"] == STATUS_REFUSED_MATURITY:
        # Unreachable when _eligible_dates did its job — reaching it means the
        # caller-side filter drifted from the core contract. Nothing written.
        print(json.dumps({
            "status": STATUS_REFUSED_MATURITY, "why": report["why"],
        }, indent=2))
        return 3

    # TWO-FILE PROTOCOL: finalize the report, THEN attempt the ledger append.
    report_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = report_path.with_suffix(report_path.suffix + ".tmp")
    staging_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    staging_path.replace(report_path)
    try:
        row = append_eval_ledger(report, ledger_path)
    except LedgerIntegrityError as exc:
        print(json.dumps({
            "status": "REFUSED-LEDGER", "why": str(exc),
            "report_final_written": True, "retry_reconciles": True,
        }, indent=2))
        return 5
    print(json.dumps({
        "status": report["status"],
        "eval_asof": report["eval_asof"],
        "label_horizon_bdays": report["label_horizon_bdays"],
        "eligible_interval": report["eligible_interval"],
        "n_dates": report["n_dates"],
        "counts": counts,
        "report_path": str(report_path),
        "report_content_sha256": report["content_sha256"],
        "ledger_row_index": row["row_index"],
        "ledger_row_sha": row["row_sha"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
