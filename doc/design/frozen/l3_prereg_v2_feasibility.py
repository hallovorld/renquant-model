"""L3 prereg v2 feasibility verifier — availability ONLY, no outcome metric.

Committed for review r2 on model#208: the v2 amendment's legitimacy rests on
"availability-only, no outcome observed", so the feasibility numbers must be
independently reproducible from committed artifacts, and the once-only
external population must be frozen BEFORE execution. This module

* pins the exact ``l3_candidate_dataset.v2`` input by SHA-256 (CSV + builder
  manifest, committed next to this file);
* recomputes the per-feature availability table and the S6 (v1) / S5
  (sigma-keeping) / S4 (v2) complete-case counts and date spans from the CSV,
  and FAILS (exit 1) on any drift from the FROZEN constants below;
* freezes the S4-eligible external-test denominator: the 64
  ``trade_evaluations`` rows keyed ``(run_date(run_id), ticker)`` into the
  frozen dataset (the canonical widest-run row — the SAME construction as
  every training row), rows unmatched or S4-feature-incomplete excluded and
  counted. The surviving identifiers are committed in
  ``2026-08-09-l3-prereg-v2-external-eligible.txt`` and hash-pinned here.

CONTAMINATION GUARANTEE: no outcome value is read into any computation.
Dataset outcome columns (``fwd_20d``/``fwd_60d``/``win``) are used ONLY for
non-emptiness (complete-case membership); ``trade_evaluations`` is queried
for identifier columns ONLY (run_id, ticker, action, horizon_days) — the
outcome columns are never selected. The report contains counts, date spans
and hashes exclusively. Pinned by the outcome-invariance test in
``tests/test_l3_prereg_v2_feasibility.py``.

Usage (from the repo root; DB access is read-only and optional):

    python doc/design/frozen/l3_prereg_v2_feasibility.py \
        [--csv <path>] [--db data/runs.alpaca.db]

Pointing ``--csv`` at a freshly rebuilt export that hash-drifts from the
frozen CSV is a FAILURE by design: the prereg dataset is the committed bytes;
a drifted rebuild means the DB moved past the freeze, never that the freeze
moves.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "2026-08-09-l3-candidate-dataset-v2.csv"
MANIFEST_PATH = HERE / "2026-08-09-l3-candidate-dataset-v2.manifest.json"
EXTERNAL_IDS_PATH = HERE / "2026-08-09-l3-prereg-v2-external-eligible.txt"

LABEL = "fwd_20d"
SIGMA_CUTOFF = "2026-05-12"          # sigma stamping turns intermittent here
V1_FEATURES = ("panel_score", "mu", "sigma", "expected_return",
               "rank_score", "n_candidates_that_date")
S5_FEATURES = ("panel_score", "mu", "sigma", "rank_score",
               "n_candidates_that_date")
V2_FEATURES = ("panel_score", "mu", "rank_score", "n_candidates_that_date")

# Every count below was measured this session from the committed CSV and a
# mode=ro open of the runs DB; the reviewer's independent rebuild (model#208
# review r1/r2) reproduced the same values.
FROZEN = {
    "csv_sha256":
        "eecfd050a52fab53f9a5f366ac4d5a69e560d426dfe6c5fa3485ed0ebec45405",
    "manifest_sha256":
        "79f5d9f5f8bf77c766e326bed21d0c3e8d7e297d7ef08a951b2d022cc452ad64",
    "manifest": {
        "schema": "l3_candidate_dataset.v2",
        "n_rows": 7167,
        "n_dates": 523,
        "n_candidates_without_forward_row_excluded": 1275,
        "n_selected": 135,
        "rows_by_run_type": {"live": 2189, "sim": 4978},
    },
    # non-null counts: {feature: (pooled, live, sim)} of 7167 / 2189 / 4978
    "availability": {
        "panel_score": (7167, 2189, 4978),
        "mu": (7027, 2049, 4978),               # live 2049/2189 = 93.60%
        "sigma": (5639, 661, 4978),             # live 661/2189 = 30.20%
        "expected_return": (2159, 2159, 0),     # sim 0/4978
        "rank_score": (7167, 2189, 4978),
        "n_candidates_that_date": (7167, 2189, 4978),
    },
    "subsets": {
        "s6_v1": {
            "n_rows": 631, "n_dates": 26,
            "span": ["2026-04-27", "2026-07-10"],
            "n_live_rows": 631, "n_live_dates": 26, "n_live_dates_total": 40,
            "n_live_dates_lost": 14,
            "post_cutoff_live_dates_retained": 20,
            "post_cutoff_live_dates_total": 29,
            "post_cutoff_live_rows": 443,
        },
        "s5_keep_sigma": {
            "n_rows": 5639, "n_dates": 513,
            "span": ["2024-01-02", "2026-07-10"],
            "n_live_rows": 661, "n_live_dates": 30, "n_live_dates_total": 40,
            "n_live_dates_lost": 10,
            "post_cutoff_live_dates_retained": 20,
            "post_cutoff_live_dates_total": 29,
            "post_cutoff_live_rows": 443,
        },
        "s4_v2": {
            "n_rows": 7027, "n_dates": 519,
            "span": ["2024-01-02", "2026-07-10"],
            "n_live_rows": 2049, "n_live_dates": 36, "n_live_dates_total": 40,
            "n_live_dates_lost": 4,
            "post_cutoff_live_dates_retained": 26,
            "post_cutoff_live_dates_total": 29,
            "post_cutoff_live_rows": 1831,
        },
    },
    "external": {
        "n_te_rows": 64,
        "n_matched": 46,
        "n_unmatched": 18,
        "n_feature_incomplete": 12,
        "n_eligible": 34,
        "by_action": {"buy": 32, "sell": 2},
        "n_distinct_trades": 14,        # distinct (run_id, ticker, action)
        "n_run_dates": 3,
        "span": ["2026-05-08", "2026-05-20"],
        "ids_sha256":
            "1e1bff4de95fec570c8f7ff4e84f2e870301a526660cc201e36e61c797d16e09",
        # insufficient-data KILL floors [ASSUMED — frozen in the v2 doc]
        "min_rows": 30,
        "min_distinct_trades": 10,
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _present(row: dict, col: str) -> bool:
    """Non-null in CSV terms. Presence only — the VALUE is never parsed."""
    return row.get(col, "") not in ("", "None")


def availability(rows: list[dict]) -> dict:
    live = [r for r in rows if r["run_type"] == "live"]
    sim = [r for r in rows if r["run_type"] == "sim"]
    return {f: (sum(_present(r, f) for r in rows),
                sum(_present(r, f) for r in live),
                sum(_present(r, f) for r in sim))
            for f in V1_FEATURES}


def subset_stats(rows: list[dict], feats: tuple[str, ...]) -> dict:
    cc = [r for r in rows
          if all(_present(r, f) for f in feats) and _present(r, LABEL)]
    dates = sorted({r["run_date"] for r in cc})
    live = [r for r in cc if r["run_type"] == "live"]
    live_dates = {r["run_date"] for r in live}
    all_live_dates = {r["run_date"] for r in rows if r["run_type"] == "live"}
    post_total = {d for d in all_live_dates if d > SIGMA_CUTOFF}
    post_rows = [r for r in live if r["run_date"] > SIGMA_CUTOFF]
    return {
        "n_rows": len(cc), "n_dates": len(dates),
        "span": [dates[0], dates[-1]] if dates else None,
        "n_live_rows": len(live),
        "n_live_dates": len(live_dates),
        "n_live_dates_total": len(all_live_dates),
        "n_live_dates_lost": len(all_live_dates) - len(live_dates),
        "post_cutoff_live_dates_retained":
            len({r["run_date"] for r in post_rows}),
        "post_cutoff_live_dates_total": len(post_total),
        "post_cutoff_live_rows": len(post_rows),
    }


def load_trade_eval_ids(db_path: Path) -> list[tuple]:
    """(run_id, ticker, action, horizon_days, run_date) — identifiers ONLY.

    The SELECT names no outcome column; fwd_return / relative_return /
    is_winner are never read.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        run_date = dict(con.execute(
            "SELECT run_id, run_date FROM pipeline_runs"))
        return [(rid, t, a, h, run_date.get(rid)) for rid, t, a, h
                in con.execute(
                    "SELECT run_id, ticker, action, horizon_days "
                    "FROM trade_evaluations "
                    "ORDER BY run_id, ticker, action, horizon_days")]
    finally:
        con.close()


def external_funnel(te_ids: list[tuple], rows: list[dict]) -> dict:
    """S4 eligibility of the trade_evaluations population, frozen join rule:
    (run_date(run_id), ticker) into the dataset's canonical widest-run row —
    the same feature construction as every training row."""
    idx = {(r["run_date"], r["ticker"]): r for r in rows}
    eligible, unmatched, incomplete, eligible_dates = [], [], [], set()
    for rid, t, a, h, rdate in te_ids:
        row = idx.get((rdate, t))
        if row is None:
            unmatched.append((rid, t, a, h))
        elif all(_present(row, f) for f in V2_FEATURES):
            eligible.append((rid, t, a, h))
            eligible_dates.add(rdate)
        else:
            incomplete.append((rid, t, a, h))
    ids = [f"{rid}|{t}|{a}|{h}" for rid, t, a, h in eligible]
    run_dates = sorted(eligible_dates)
    return {
        "n_te_rows": len(te_ids),
        "n_matched": len(eligible) + len(incomplete),
        "n_unmatched": len(unmatched),
        "n_feature_incomplete": len(incomplete),
        "n_eligible": len(eligible),
        "by_action": {a: sum(1 for e in eligible if e[2] == a)
                      for a in sorted({e[2] for e in eligible})},
        "n_distinct_trades": len({e[:3] for e in eligible}),
        "n_run_dates": len(run_dates),
        "span": [run_dates[0], run_dates[-1]] if run_dates else None,
        "ids": ids,
        "ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
    }


def read_frozen_external_ids(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def verify(csv_path: Path = CSV_PATH,
           manifest_path: Path = MANIFEST_PATH,
           ids_path: Path = EXTERNAL_IDS_PATH,
           db_path: Path | None = None,
           frozen: dict = FROZEN) -> tuple[dict, list[str]]:
    """Recompute everything; return (report, drifts). drifts == [] is PASS."""
    drifts: list[str] = []

    def check(name: str, got, want):
        if got != want:
            drifts.append(f"{name}: got {got!r} != frozen {want!r}")

    report: dict = {"csv": str(csv_path)}
    check("csv_sha256", sha256_file(csv_path), frozen["csv_sha256"])
    check("manifest_sha256", sha256_file(manifest_path),
          frozen["manifest_sha256"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for k, want in frozen["manifest"].items():
        check(f"manifest.{k}", manifest.get(k), want)

    rows = load_rows(csv_path)
    report["availability"] = availability(rows)
    for f, want in frozen["availability"].items():
        check(f"availability.{f}", report["availability"][f], want)

    report["subsets"] = {
        "s6_v1": subset_stats(rows, V1_FEATURES),
        "s5_keep_sigma": subset_stats(rows, S5_FEATURES),
        "s4_v2": subset_stats(rows, V2_FEATURES),
    }
    for name, want in frozen["subsets"].items():
        check(f"subsets.{name}", report["subsets"][name], want)

    frozen_ids = read_frozen_external_ids(ids_path)
    ids_hash = hashlib.sha256("\n".join(frozen_ids).encode()).hexdigest()
    ext = frozen["external"]
    report["external_frozen"] = {"n_ids": len(frozen_ids),
                                 "ids_sha256": ids_hash}
    check("external.ids_file.n", len(frozen_ids), ext["n_eligible"])
    check("external.ids_file.sha256", ids_hash, ext["ids_sha256"])
    check("external.floor.rows_ok",
          len(frozen_ids) >= ext["min_rows"], True)

    if db_path is not None:
        funnel = external_funnel(load_trade_eval_ids(db_path), rows)
        ids = funnel.pop("ids")
        report["external_recomputed"] = funnel
        for k, want in ext.items():
            if k in funnel:
                check(f"external.{k}", funnel[k], want)
        check("external.ids_match_frozen_file", ids, frozen_ids)
        check("external.floor.distinct_trades_ok",
              funnel["n_distinct_trades"] >= ext["min_distinct_trades"], True)
    else:
        report["external_recomputed"] = "SKIPPED — no --db given"

    return report, drifts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=CSV_PATH)
    ap.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    ap.add_argument("--ids", type=Path, default=EXTERNAL_IDS_PATH)
    ap.add_argument("--db", type=Path, default=None,
                    help="runs DB (opened mode=ro) to recompute the external "
                         "funnel; omit to verify committed artifacts only")
    args = ap.parse_args(argv)
    report, drifts = verify(args.csv, args.manifest, args.ids, args.db)
    print(json.dumps(report, indent=2, default=str))
    if drifts:
        print("\nDRIFT — feasibility record does NOT match frozen constants:")
        for d in drifts:
            print(f"  {d}")
        return 1
    print("\nFEASIBILITY VERIFIED — all frozen counts reproduced; "
          "no outcome value was read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
