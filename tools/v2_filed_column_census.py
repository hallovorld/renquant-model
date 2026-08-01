#!/usr/bin/env python3
"""Which v2 column IS "the real filed date"? (Amendment 2a of the v1-v2 PIT A/B)

WHY THIS EXISTS. `tools/v1_v2_pit_ab_run.py` aborts at startup until Amendment 2a is
implemented in code. 2a says `restamp_v1()` must join v1's values to **v2's real `filed`
date per fact** instead of the retired `+60d` synthetic constant — and it leaves the
column name explicitly **TBD**:

    "column name TBD against v2's actual schema — not guessed here to avoid
     shipping a second silently-wrong implementation"

That refusal was right. `data/edgar_pit/` offers **three** date columns and they are not
interchangeable. This resolves the TBD by measuring them instead of choosing one.

WHAT IT MEASURES, and why each number matters:

  * pairwise agreement — if two candidates agreed, the choice would be moot;
  * the delta distribution — a systematic +1 day is an availability CONVENTION, not a
    filing date;
  * distinct ticker coverage — a candidate that covers fewer names than the prereg's
    common support silently SHRINKS the arm, which is the "silently-wrong
    implementation" 2a was written to avoid.

WHAT IT DOES NOT DO. It does not choose, edit the prereg, or unblock the runner. The
choice is an amendment to a frozen document and belongs in that document, argued against
these numbers.

Read-only. Reads parquet, writes only the JSON it is told to write.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

#: (file, key columns, date column) — every candidate for "v2's real filed date".
#: Declared, not discovered: a candidate silently vanishing must be a failure, not a
#: quietly shorter census.
CANDIDATES = (
    ("filing_dates.parquet", ("ticker", "period_end", "form"), "filing_date"),
    ("available_at_v2.parquet", ("ticker", "fiscal_period_end", "form"),
     "available_v2"),
    ("asfiled_period_records.parquet", ("ticker", "period_end"), "avail"),
)


def census(root: str) -> dict:
    import pandas as pd

    loaded, missing = {}, []
    for fname, keys, datecol in CANDIDATES:
        path = os.path.join(root, fname)
        if not os.path.exists(path):
            missing.append(fname)
            continue
        df = pd.read_parquet(path)
        if datecol not in df.columns:
            missing.append(f"{fname}:{datecol}")
            continue
        df = df.copy()
        df[datecol] = pd.to_datetime(df[datecol])
        for k in keys:
            if k in df.columns and "end" in k:
                df[k] = pd.to_datetime(df[k])
        loaded[fname] = {"df": df, "keys": list(keys), "datecol": datecol}

    rows = [{
        "file": f, "date_column": v["datecol"], "key_columns": v["keys"],
        "n_rows": int(len(v["df"])),
        "n_distinct_tickers": int(v["df"]["ticker"].nunique()),
        "date_min": str(v["df"][v["datecol"]].min().date()),
        "date_max": str(v["df"][v["datecol"]].max().date()),
        "n_null_dates": int(v["df"][v["datecol"]].isna().sum()),
    } for f, v in loaded.items()]

    pairs = []
    names = list(loaded)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = loaded[names[i]], loaded[names[j]]
            shared = [k for k in ("ticker", "form") if
                      k in a["df"].columns and k in b["df"].columns]
            aend = next((k for k in a["keys"] if "end" in k), None)
            bend = next((k for k in b["keys"] if "end" in k), None)
            if aend is None or bend is None:
                continue
            left = a["df"][shared + [aend, a["datecol"]]].rename(
                columns={aend: "_pe"}).drop_duplicates(shared + ["_pe"])
            right = b["df"][shared + [bend, b["datecol"]]].rename(
                columns={bend: "_pe"}).drop_duplicates(shared + ["_pe"])
            m = left.merge(right, on=shared + ["_pe"], how="inner")
            if m.empty:
                pairs.append({"a": names[i], "b": names[j], "n_joined": 0,
                              "note": "no rows join on the shared keys"})
                continue
            d = (m[a["datecol"]] - m[b["datecol"]]).dt.days
            pairs.append({
                "a": f"{names[i]}.{a['datecol']}",
                "b": f"{names[j]}.{b['datecol']}",
                "join_keys": shared + ["period_end"],
                "n_joined": int(len(m)),
                "n_identical": int((d == 0).sum()),
                "frac_identical": round(float((d == 0).mean()), 4),
                "delta_days_min": int(d.min()),
                "delta_days_median": float(d.median()),
                "delta_days_max": int(d.max()),
            })

    return {
        "root": os.path.basename(os.path.normpath(root)),
        "candidates": rows, "missing": missing, "pairwise": pairs,
        "scope_note": (
            "This resolves the TBD by MEASUREMENT; it does not choose. A candidate "
            "covering fewer distinct tickers than the prereg's common support would "
            "silently shrink the B_v1_lag arm — the 'silently-wrong implementation' "
            "Amendment 2a was written to avoid. A systematic small positive delta is an "
            "availability CONVENTION, not a filing date. Choosing is an amendment to a "
            "frozen document and belongs there, argued against these numbers."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="the v2 data/edgar_pit directory")
    ap.add_argument("--out", help="write the census JSON here")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.root):
        print(f"v2 filed-column census: {a.root} is not a directory", file=sys.stderr)
        return 2
    try:
        rep = census(a.root)
    except Exception as exc:  # noqa: BLE001
        print(f"v2 filed-column census: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not rep["candidates"]:
        print("v2 filed-column census: no candidate resolved — the census has no "
              "subjects, which is not the same as one obvious column", file=sys.stderr)
        return 2

    print(json.dumps(rep, indent=2, sort_keys=True))
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
    # Non-zero while the candidates disagree: the TBD is unresolved until someone chooses.
    return 1 if any(p.get("frac_identical", 0) < 1.0 for p in rep["pairwise"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
