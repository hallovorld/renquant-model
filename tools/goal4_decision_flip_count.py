"""How many buy/no-buy decisions would an ensemble have CHANGED? Descriptive only.

Codex on model#129 permitted this measurement under three conditions, adopted here
as executable constraints rather than prose:

  1. explicitly ISOLATED from outcome labels,
  2. it may not report any performance of the flipped set,
  3. it may not be able to select a favourable evaluation rule.

**Isolation is enforced at the COLUMN level, and it has to be.** Measured
2026-07-30, two of the three pinned score panels carry `fwd_60d_excess` INLINE
(`oos_pick_table_recipe_v2.parquet` and `clf_wf_scores.parquet`), so choosing which
FILE to open isolates nothing. Every read below passes an explicit `columns=` list,
so a label column is never materialised at all -- not read then dropped, which
would leave it one attribute access away.

**Why the count decides something.** Option C in the design PR moves the estimand to
the decision boundary. That is only worth designing if the boundary is ever crossed.
If the ensemble flips single digits per year, C trades one power wall for another and
D becomes the honest answer. The count is the cheap discriminator, and it needs no
preregistration precisely because it touches no outcome.

    python tools/goal4_decision_flip_count.py --top-n 10
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT_LIVE = Path("/Users/renhao/git/github/RenQuant")
ROOT_BUNDLES = Path("/Users/renhao/renquant_bundles")

#: A column whose name matches this may NEVER be loaded. The list is deliberately
#: wider than the columns that exist: a new panel shipping `target_60d` must fail
#: loudly rather than sail through a name the pattern did not anticipate.
LABEL_RE = re.compile(r"fwd|label|excess|target|^y_|_ret$|return", re.I)

PANELS = {
    "prod_xgb": (ROOT_LIVE / "data/exp/oos_pick_table_recipe_v2.parquet",
                 ["date", "name", "score"], "name", "score"),
    "certified_clf": (ROOT_BUNDLES / "corrected-eval-20260729/clf-wf/clf_wf_scores.parquet",
                      ["date", "ticker", "cal"], "ticker", "cal"),
    "patchtst": (ROOT_BUNDLES / "corrected-eval-20260729/wf-eval/scores.parquet",
                 ["date", "ticker", "cal"], "ticker", "cal"),
}


def load_label_free(path: Path, columns: list[str], id_col: str, score_col: str):
    """Read ONLY `columns`. Refuses if any requested name is label-shaped."""
    bad = [c for c in columns if LABEL_RE.search(c)]
    if bad:
        raise ValueError(f"refusing to load label-shaped column(s) {bad} from {path}")
    df = pd.read_parquet(path, columns=columns)
    leaked = [c for c in df.columns if LABEL_RE.search(c)]
    if leaked:  # pragma: no cover - defence in depth against a pandas change
        raise AssertionError(f"label column(s) {leaked} materialised from {path}")
    out = df.rename(columns={id_col: "ticker", score_col: "score"})
    out["date"] = pd.to_datetime(out["date"])
    return out[["date", "ticker", "score"]]


def flip_count(panels: dict, top_n: int) -> dict:
    """Per date: top-N by prod alone vs by the mean of within-date score RANKS.

    Ranks, not raw scores: the three members are on different scales and a raw mean
    would be an unregistered weighting decision -- exactly the "favourable evaluation
    rule" the review forbids this measurement from selecting. Rank-mean is the one
    choice that needs no scale information.
    """
    base = panels["prod_xgb"]
    merged = base.rename(columns={"score": "s_prod"})
    for name in ("certified_clf", "patchtst"):
        merged = merged.merge(
            panels[name].rename(columns={"score": f"s_{name}"}),
            on=["date", "ticker"], how="inner")
    cols = [c for c in merged.columns if c.startswith("s_")]
    for c in cols:
        merged[f"r_{c}"] = merged.groupby("date")[c].rank(pct=True)
    merged["r_ens"] = merged[[f"r_{c}" for c in cols]].mean(axis=1)

    flips, dates, sizes = [], 0, []
    for day, g in merged.groupby("date"):
        if len(g) < top_n:
            continue
        a = set(g.nlargest(top_n, "s_prod")["ticker"])
        b = set(g.nlargest(top_n, "r_ens")["ticker"])
        flips.append(len(a ^ b) // 2)      # symmetric difference is 2x the swaps
        sizes.append(len(g)); dates += 1
    s = pd.Series(flips)
    return {
        "top_n": top_n,
        "common_dates": dates,
        "median_names_per_date": float(pd.Series(sizes).median()) if sizes else None,
        "flips_total": int(s.sum()),
        "flips_per_date_mean": float(s.mean()) if dates else None,
        "flips_per_date_median": float(s.median()) if dates else None,
        "dates_with_zero_flips": int((s == 0).sum()),
        "dates_with_any_flip": int((s > 0).sum()),
        "max_flips_on_a_date": int(s.max()) if dates else None,
        "REPORTS_NO_PERFORMANCE": True,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=10)
    a = ap.parse_args(argv)
    loaded = {k: load_label_free(p, c, i, s) for k, (p, c, i, s) in PANELS.items()}
    print(json.dumps(flip_count(loaded, a.top_n), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
