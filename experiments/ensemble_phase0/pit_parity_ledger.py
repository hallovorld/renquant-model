"""PIT input-parity ledger: prod vs shadow at the same decision instant.

Design §5.1 (doc/research/2026-07-12-ensemble-combination-experiment.md)
admits the PatchTST shadow arm as an ensemble expert ONLY with evidence
that its INPUTS were point-in-time equivalent to prod's at the same
decision instant. This module produces that evidence: one fail-closed
parity verdict per session, from the two runs' persisted run bundles,
read-only.

RESEARCH-ONLY. Reads ``runs.alpaca.db`` (prod arm) and
``runs.alpaca_shadow.db`` (shadow arm) with ``mode=ro&immutable=1``;
writes ONLY under ``experiments/ensemble_phase0/output/pit_parity/``.

Compared-dimension set (verdict-bearing) — chosen from the fields the
run bundles actually persist, restricted to INPUTS (the two arms differ
in scorer artifacts BY DESIGN; scorer identity must never enter the
parity verdict):

* ``data_layer_universe`` — the shadow bundle's ``data_max_dates`` key
  set must be a subset of prod's. The data layer is the real input
  surface; the config-level ``watchlist_hash`` intentionally differs
  between arms (the shadow config swaps the panel artifact and may trail
  watchlist growth), so universe parity is defined at the data layer,
  with the config-level hash reported informationally.
* ``data_watermarks`` — per-ticker ``data_max_dates`` equality over the
  shadow∩prod intersection. Any differing ticker watermark ⇒ the arms
  did not see the same data ⇒ not parity.
* ``regime_evidence`` — the finalized regime label must match. Regime is
  a pure function of shared inputs; divergence is evidence the inputs
  (or their alignment) differed even if watermarks agree.
* ``decision_skew`` — both runs must already satisfy the as-of contract
  (committed before that session's close cutoff; enforced by
  ``backfill_scores.select_asof_runs``), and the commit-time skew between
  the two selected runs must be ≤ ``max_skew_seconds`` (default 6h:
  the daily wrapper runs the shadow arm minutes after prod within the
  same post-close window; both consume close-anchored daily bars, so
  same-session co-processing — not tick-level simultaneity — is the
  equivalence the daily-bar design actually requires).
* ``bundle_schema`` — equal ``schema_version`` on both bundles, so the
  fields being compared mean the same thing.
* Presence: a missing run on either side, an unparseable bundle, or a
  missing verdict-bearing field ⇒ ``not_parity`` with named reasons.

Excluded from the verdict (with reasons), reported informationally:

* ``artifact_hashes`` / ``config_hash`` / ``artifact_paths`` — embed the
  scorer choice, i.e. the experimental variable itself.
* ``commit_path_fingerprint`` / ``env`` — code identity, not input
  identity; informative for forensics only.
* ``pipeline_flags`` — decision OUTCOMES, not inputs.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.ensemble_phase0.admissibility_ledger import (
    US_EQUITY_CLOSE,
    DecisionSchedule,
    SessionCalendar,
    build_exchange_session_calendar,
)
from experiments.ensemble_phase0.backfill_scores import (
    RunSelection,
    select_asof_runs,
)

LEDGER_SCHEMA_VERSION = "pit_parity_ledger.v1"
DEFAULT_MAX_SKEW_SECONDS = 6 * 3600
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "pit_parity"

PROD_DB = Path("/Users/renhao/git/github/RenQuant/data/runs.alpaca.db")
SHADOW_DB = Path("/Users/renhao/git/github/RenQuant/data/runs.alpaca_shadow.db")

_VERDICT_FIELDS = ("data_max_dates", "regime_evidence", "schema_version")


@dataclass
class DimensionResult:
    dimension: str
    match: bool
    detail: str = ""


@dataclass
class ParityVerdict:
    session_date: str
    verdict: str  # "parity" | "not_parity"
    reasons: list[str] = field(default_factory=list)
    dimensions: list[DimensionResult] = field(default_factory=list)
    prod_run_id: str | None = None
    shadow_run_id: str | None = None
    informational: dict[str, Any] = field(default_factory=dict)
    ledger_schema_version: str = LEDGER_SCHEMA_VERSION

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, sort_keys=True)


def _load_bundle(db_path: Path, run_id: str) -> dict | None:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    try:
        row = conn.execute(
            "SELECT run_bundle_json FROM pipeline_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    try:
        bundle = json.loads(row[0])
    except (TypeError, ValueError):
        return None
    return bundle if isinstance(bundle, dict) else None


def _missing_fields(bundle: dict) -> list[str]:
    missing = []
    for f in _VERDICT_FIELDS:
        v = bundle.get(f)
        if v is None or (f == "data_max_dates" and not isinstance(v, dict)):
            missing.append(f)
    return missing


def _regime_label(bundle: dict) -> str | None:
    ev = bundle.get("regime_evidence")
    if not isinstance(ev, dict):
        return None
    for key in ("final_regime", "regime"):
        v = ev.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def compare_session(
    session_date: str,
    prod_sel: RunSelection | None,
    shadow_sel: RunSelection | None,
    *,
    prod_db: Path = PROD_DB,
    shadow_db: Path = SHADOW_DB,
    max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS,
) -> ParityVerdict:
    """Produce the fail-closed parity verdict for one session."""
    v = ParityVerdict(session_date=session_date, verdict="not_parity")

    if prod_sel is None or shadow_sel is None:
        side = "prod" if prod_sel is None else "shadow"
        v.reasons.append(f"missing_{side}_run: no as-of-eligible live run")
        return v
    v.prod_run_id, v.shadow_run_id = prod_sel.run_id, shadow_sel.run_id

    prod_b = _load_bundle(prod_db, prod_sel.run_id)
    shadow_b = _load_bundle(shadow_db, shadow_sel.run_id)
    if prod_b is None or shadow_b is None:
        side = "prod" if prod_b is None else "shadow"
        v.reasons.append(f"missing_{side}_bundle: run_bundle_json absent/unparseable")
        return v

    for side, b in (("prod", prod_b), ("shadow", shadow_b)):
        miss = _missing_fields(b)
        if miss:
            v.reasons.append(f"missing_{side}_fields: {','.join(miss)}")
    if v.reasons:
        return v

    # bundle_schema
    sv_p, sv_s = prod_b.get("schema_version"), shadow_b.get("schema_version")
    ok = sv_p == sv_s
    v.dimensions.append(DimensionResult(
        "bundle_schema", ok, "" if ok else f"prod={sv_p!r} shadow={sv_s!r}"))
    if not ok:
        v.reasons.append("bundle_schema_mismatch")

    # data-layer universe (shadow ⊆ prod)
    dmd_p: dict = prod_b["data_max_dates"]
    dmd_s: dict = shadow_b["data_max_dates"]
    extra_in_shadow = sorted(set(dmd_s) - set(dmd_p))
    ok = not extra_in_shadow
    v.dimensions.append(DimensionResult(
        "data_layer_universe", ok,
        "" if ok else f"shadow-only tickers: {extra_in_shadow[:10]}"
                      f"{'…' if len(extra_in_shadow) > 10 else ''}"))
    if not ok:
        v.reasons.append("shadow_universe_not_subset_of_prod")

    # per-ticker watermarks over the intersection
    inter = sorted(set(dmd_p) & set(dmd_s))
    diffs = [(t, dmd_p[t], dmd_s[t]) for t in inter if dmd_p[t] != dmd_s[t]]
    ok = not diffs
    v.dimensions.append(DimensionResult(
        "data_watermarks", ok,
        f"intersection={len(inter)}" if ok else
        f"intersection={len(inter)}, differing={diffs[:5]}"
        f"{'…' if len(diffs) > 5 else ''}"))
    if not ok:
        v.reasons.append(f"watermark_mismatch_on_{len(diffs)}_tickers")

    # regime evidence
    r_p, r_s = _regime_label(prod_b), _regime_label(shadow_b)
    ok = r_p is not None and r_p == r_s
    v.dimensions.append(DimensionResult(
        "regime_evidence", ok, "" if ok else f"prod={r_p!r} shadow={r_s!r}"))
    if not ok:
        v.reasons.append("regime_mismatch_or_missing")

    # decision skew (both already pre-cutoff via as-of selection)
    try:
        t_p = datetime.fromisoformat(prod_sel.created_at_utc)
        t_s = datetime.fromisoformat(shadow_sel.created_at_utc)
        skew = abs((t_s - t_p).total_seconds())
        ok = skew <= max_skew_seconds
        v.dimensions.append(DimensionResult(
            "decision_skew", ok,
            f"skew_seconds={int(skew)} tolerance={max_skew_seconds}"))
        if not ok:
            v.reasons.append(f"decision_skew_{int(skew)}s_exceeds_tolerance")
    except (TypeError, ValueError):
        v.dimensions.append(DimensionResult("decision_skew", False, "unparseable created_at"))
        v.reasons.append("decision_skew_unparseable")

    # informational (never verdict-bearing)
    v.informational = {
        "watchlist_hash": {"prod": prod_b.get("watchlist_hash"),
                           "shadow": shadow_b.get("watchlist_hash")},
        "watchlist_size": {"prod": prod_b.get("watchlist_size"),
                           "shadow": shadow_b.get("watchlist_size")},
        "config_hash": {"prod": prod_b.get("config_hash"),
                        "shadow": shadow_b.get("config_hash")},
        "commit_path_fingerprint_equal":
            prod_b.get("commit_path_fingerprint") == shadow_b.get("commit_path_fingerprint"),
    }

    if not v.reasons:
        v.verdict = "parity"
    return v


def build_parity_ledger(
    *,
    start_date: str,
    end_date: str,
    prod_db: Path = PROD_DB,
    shadow_db: Path = SHADOW_DB,
    calendar: SessionCalendar | None = None,
    schedule: DecisionSchedule = US_EQUITY_CLOSE,
    max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS,
) -> list[ParityVerdict]:
    calendar = calendar or build_exchange_session_calendar(start_date, end_date)
    prod_sel, prod_excl = select_asof_runs(
        prod_db, start_date=start_date, end_date=end_date,
        calendar=calendar, schedule=schedule)
    shadow_sel, shadow_excl = select_asof_runs(
        shadow_db, start_date=start_date, end_date=end_date,
        calendar=calendar, schedule=schedule)

    sessions = sorted(set(prod_sel) | set(shadow_sel)
                      | {e.run_date for e in prod_excl}
                      | {e.run_date for e in shadow_excl})
    return [
        compare_session(
            d, prod_sel.get(d), shadow_sel.get(d),
            prod_db=prod_db, shadow_db=shadow_db,
            max_skew_seconds=max_skew_seconds)
        for d in sessions
    ]


def write_parity_ledger(verdicts: list[ParityVerdict],
                        output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"pit_parity_{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(v.to_json() + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default="2026-06-22")
    ap.add_argument("--end", required=True)
    ap.add_argument("--date", help="single-date incremental mode")
    ap.add_argument("--max-skew-seconds", type=int, default=DEFAULT_MAX_SKEW_SECONDS)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = ap.parse_args(argv)

    start = args.date or args.start
    end = args.date or args.end
    verdicts = build_parity_ledger(
        start_date=start, end_date=end, max_skew_seconds=args.max_skew_seconds)
    path = write_parity_ledger(verdicts, args.output_dir)
    n_par = sum(1 for v in verdicts if v.verdict == "parity")
    print(f"pit_parity: {n_par}/{len(verdicts)} sessions parity -> {path}")
    for v in verdicts:
        if v.verdict != "parity":
            print(f"  {v.session_date}: {'; '.join(v.reasons)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
