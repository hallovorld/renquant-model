#!/usr/bin/env python3
"""How badly is the gap=0 block-t miscalibrated on THESE series? Measured, not assumed.

`dependence_aware_mean` builds contiguous blocks with **gap = 0** and says so in its own
docstring: it "must not present the comparison as inference". model#154 showed the frozen
v1-vs-v2 Stage-A gate uses it anyway, at |t| >= 3.29.

This measures the damage instead of asserting it, and does so WITHOUT touching any
alternative hypothesis: every replicate is drawn from a series re-centred to mean zero, so
what is measured is the procedure's SIZE under H0 and nothing else. Calibrating size is
not looking at the effect.

Method. Given a per-date statistic series:
  * re-centre to mean 0                       -> H0 holds by construction
  * resample GAP-SEPARATED blocks of length b, discarding `gap` observations between
    donor blocks, so adjacent resampled blocks never share a label window
  * for each replicate compute the naive gap=0 block-t the callers actually use
  * empirical size = fraction of replicates with |t| >= bar

A correct procedure returns size ~= nominal. Anything materially above it is
anticonservative by exactly that amount.

Exit codes: 0 measured, 2 usage/IO error.
"""
from __future__ import annotations
import argparse, csv, json, math, random, sys
from pathlib import Path


def blocks_no_gap(v, b):
    """Exactly what `dependence_aware_mean._blocks` does: contiguous, stride = b."""
    return [sum(v[i:i + b]) / len(v[i:i + b]) for i in range(0, len(v), b)]


def block_t(v, b):
    m = blocks_no_gap(v, b)
    if len(m) < 2:
        return None
    mu = sum(m) / len(m)
    var = sum((x - mu) ** 2 for x in m) / (len(m) - 1)
    se = math.sqrt(var / len(m))
    return None if se == 0 else mu / se


def gap_separated_donors(v, b, gap):
    """Donor blocks of length b whose starts are >= b+gap apart, so no two donors share
    a label window. This is the sampling unit a gap-0 scheme does not have."""
    step = b + gap
    return [v[i:i + b] for i in range(0, len(v) - b + 1, step) if len(v[i:i + b]) == b]


def size_under_h0(v, *, b_naive, b_donor, gap, bar, n_rep, seed):
    rng = random.Random(seed)
    mu = sum(v) / len(v)
    centred = [x - mu for x in v]                      # H0 by construction
    donors = gap_separated_donors(centred, b_donor, gap)
    if len(donors) < 2:
        return {"status": "too_few_donors", "n_donors": len(donors)}
    k = max(2, len(centred) // b_donor)
    rejects = 0
    for _ in range(n_rep):
        rep = []
        for _ in range(k):
            rep.extend(rng.choice(donors))
        t = block_t(rep, b_naive)
        if t is not None and abs(t) >= bar:
            rejects += 1
    return {"status": "measured", "n_donors": len(donors), "n_rep": n_rep,
            "size": rejects / n_rep}


def _student(df: int, alpha: float):
    """Two-sided Student critical value. Returns the string 'n/a' rather than a number
    when df < 1 -- an unavailable bar must not be printed as if it were large-sample."""
    if df < 1:
        return "n/a"
    try:
        from scipy import stats  # noqa: PLC0415
    except ImportError:
        return "no-scipy"
    return f"{float(stats.t.ppf(1 - alpha / 2, df)):.2f}"


def load(path: Path, col: str):
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [float(r[col]) for r in rows if r.get(col) not in (None, "", "nan")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", required=True, type=Path, nargs="+")
    ap.add_argument("--col", default="ic")
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--block", type=int, default=60, help="the NAIVE block length used by callers")
    ap.add_argument("--bars", type=float, nargs="+", default=[1.96, 3.29])
    ap.add_argument("--n-rep", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--family", type=int, default=49,
                    help="joint family size for the Bonferroni column (v1-v2 prereg: 49)")
    ap.add_argument("--json-out", type=Path, default=None)
    a = ap.parse_args(argv)

    out = []
    print(f"{'series':<40}{'n':>5}{'gap-sep blocks':>16}"
          f"{'[illustrative only] t if independent, .05 / Bonf'+str(a.family):>50}")
    for p in a.series:
        try:
            v = load(p, a.col)
        except (OSError, KeyError, ValueError) as exc:
            print(f"  {p.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        k = len(gap_separated_donors([x for x in v], a.horizon, a.horizon))
        df = k - 1
        t05 = _student(df, 0.05)
        tbf = _student(df, 0.05 / a.family)
        print(f"{p.name[:39]:<40}{len(v):>5}{k:>16}{'('+str(t05)+' / '+str(tbf)+')':>50}")
    print(f"\n  FEASIBILITY DIAGNOSTIC, NOT A TEST. The middle column is the count of")
    print(f"  gap-separated blocks at gap = h = {a.horizon}: how much material a scheme that")
    print("  removes direct label overlap would have to work with. That is all it is.")
    print("\n  The bracketed values are what a Student bar WOULD be IF those blocks were")
    print("  independent. They are ILLUSTRATIVE ONLY and are not applicable thresholds:")
    print("  gap >= h removes shared label windows and nothing else. Predictor persistence,")
    print("  common factor exposure and longer-range dependence all survive it, so the")
    print("  retained blocks are not shown to be independent and no df follows from the")
    print("  count. A valid bar requires a justified or calibrated null, which this tool")
    print("  does not supply.\n")
    print(f"{'series':<44}{'n':>5}{'donors':>8}" + "".join(f"{'size@'+str(b):>11}" for b in a.bars))
    for p in a.series:
        try:
            v = load(p, a.col)
        except (OSError, KeyError, ValueError) as exc:
            print(f"  {p.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        row = {"series": p.name, "n": len(v)}
        cells = []
        for bar in a.bars:
            r = size_under_h0(v, b_naive=a.block, b_donor=a.horizon, gap=a.horizon,
                              bar=bar, n_rep=a.n_rep, seed=a.seed)
            row[f"size@{bar}"] = r.get("size")
            row["n_donors"] = r.get("n_donors")
            cells.append(f"{r['size']:.4f}" if r["status"] == "measured" else r["status"])
        print(f"{p.name[:43]:<44}{len(v):>5}{row.get('n_donors',0):>8}" + "".join(f"{c:>11}" for c in cells))
        out.append(row)
    print("\n  Nominal size for |t|>=1.96 is 0.05. Replicates are drawn from the re-centred")
    print("  series, so H0 holds by construction and any excess is the procedure's own.")
    if a.json_out:
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print(f"  wrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
