#!/usr/bin/env python3
"""How much material does the gap-separated-block construction retain? (GOAL-4)

PRIMARY OUTPUT: the count of blocks a scheme retains when blocks are spaced by at least
the label horizon. That count is a property of the series length and the spacing, and it
is the only thing here that is measured without an assumption.

Spacing removes **shared label windows** and nothing else. Predictor persistence, common
factor exposure and longer-range dependence all survive it, so spaced blocks are not shown
to be independent, no degrees of freedom follow from counting them, and this file asserts
no threshold anywhere.

SECONDARY, AND DELIBERATELY NOT A CALIBRATION `[codex on model#157]`. The optional
resampling pass draws replicates from the re-centred series and reports how often a naive
`gap = 0` block-t exceeds a given bar. It is a **sensitivity diagnostic**: it shows how the
naive statistic behaves under one resampling scheme, and nothing more. It does not
estimate how often that statistic rejects a true null, and a gap between the fraction it
reports and any nominal level says nothing about the statistic's behaviour — the
resampling scheme inherits whatever dependence the donor blocks retain, which is exactly

Because that pass is only interpretable with enough distinct donors, `--min-donors` is
**required and has no default**. This file cannot justify a minimum: the number depends on
the dependence structure the caller is willing to assume, and inventing one here would be
the same unearned assumption the rest of the module refuses. Below the caller's own
threshold the result is ``UNRESOLVED_INSUFFICIENT_DONORS`` and no fraction is emitted.

Exit codes: ``0`` measured, ``2`` usage/IO error.
"""
from __future__ import annotations
import argparse, csv, json, math, random, sys
from pathlib import Path

UNRESOLVED = "UNRESOLVED_INSUFFICIENT_DONORS"


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
    """Blocks of length b whose starts are >= b+gap apart, so no two share a label
    window. Removing that overlap is ALL this buys."""
    step = b + gap
    return [v[i:i + b] for i in range(0, len(v) - b + 1, step) if len(v[i:i + b]) == b]


def exceedance_sensitivity(v, *, b_naive, b_donor, gap, bar, n_rep, seed, min_donors):
    """Fraction of resampled replicates whose naive block-t exceeds `bar`.

    A description of one resampling scheme's behaviour, not an estimate of how often
    the statistic rejects a true null. Returns UNRESOLVED below the caller's own donor
    threshold rather than a number that would read as a calibration.
    """
    rng = random.Random(seed)
    mu = sum(v) / len(v)
    centred = [x - mu for x in v]
    donors = gap_separated_donors(centred, b_donor, gap)
    if len(donors) < min_donors:
        return {"status": UNRESOLVED, "n_donors": len(donors),
                "min_donors_required": min_donors,
                "why": (f"{len(donors)} distinct donor block(s) is below the caller's "
                        f"--min-donors {min_donors}; resampling from this few reuses the "
                        f"same blocks across replicates, so any fraction emitted would "
                        f"describe the donor set rather than the statistic")}
    k = max(2, len(centred) // b_donor)
    hits = 0
    for _ in range(n_rep):
        rep = []
        for _ in range(k):
            rep.extend(rng.choice(donors))
        t = block_t(rep, b_naive)
        if t is not None and abs(t) >= bar:
            hits += 1
    return {"status": "resampled", "n_donors": len(donors), "n_rep": n_rep,
            "exceedance_fraction": hits / n_rep}


def _student(df: int, alpha: float):
    """Illustrative only. Returns 'n/a' below df=1 rather than a number."""
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
    ap.add_argument("--block", type=int, default=60,
                    help="the NAIVE block length callers use (gap = 0)")
    ap.add_argument("--family", type=int, default=49)
    ap.add_argument("--resample", action="store_true",
                    help="also run the exceedance sensitivity pass")
    ap.add_argument("--min-donors", type=int, default=None,
                    help="REQUIRED with --resample. No default: this tool cannot justify "
                         "a minimum, so the caller states and owns one.")
    ap.add_argument("--bars", type=float, nargs="+", default=[1.96, 3.29])
    ap.add_argument("--n-rep", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json-out", type=Path, default=None)
    a = ap.parse_args(argv)

    if a.resample and a.min_donors is None:
        print("--resample requires --min-donors: the exceedance fraction is only "
              "interpretable above a donor count this tool cannot justify for you.",
              file=sys.stderr)
        return 2

    out = []
    print(f"{'series':<40}{'n':>5}{'gap-sep blocks':>16}"
          f"{'  [illustrative only] t IF independent: .05 / Bonf' + str(a.family):>52}")
    series = []
    for p in a.series:
        try:
            v = load(p, a.col)
        except (OSError, KeyError, ValueError) as exc:
            print(f"  {p.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        k = len(gap_separated_donors(v, a.horizon, a.horizon))
        df = k - 1
        print(f"{p.name[:39]:<40}{len(v):>5}{k:>16}"
              f"{'(' + str(_student(df, 0.05)) + ' / ' + str(_student(df, 0.05 / a.family)) + ')':>52}")
        series.append((p, v, k))
        out.append({"series": p.name, "n": len(v), "gap_separated_blocks": k})

    print(f"\n  The middle column is the measurement: how many blocks survive spacing at")
    print(f"  gap = h = {a.horizon}. Spacing removes shared label windows and nothing else,")
    print("  so these blocks are NOT shown to be independent. The bracketed values are")
    print("  what a Student bar WOULD be IF they were, kept only to show the order of")
    print("  magnitude; they are not applicable thresholds and nothing here asserts one.")

    if a.resample:
        print(f"\n  exceedance sensitivity (describes one resampling scheme only), "
              f"--min-donors {a.min_donors}:")
        for (p, v, _k), row in zip(series, out):
            cells = []
            for bar in a.bars:
                r = exceedance_sensitivity(
                    v, b_naive=a.block, b_donor=a.horizon, gap=a.horizon, bar=bar,
                    n_rep=a.n_rep, seed=a.seed, min_donors=a.min_donors)
                row[f"exceedance@{bar}"] = r.get("exceedance_fraction", r["status"])
                row["n_donors"] = r["n_donors"]
                cells.append(f"{r['exceedance_fraction']:.4f}"
                             if r["status"] == "resampled" else r["status"])
            print(f"    {p.name[:44]:<46}" + "  ".join(cells))
            if cells and cells[0] == UNRESOLVED:
                print(f"        {r['why']}")

    if a.json_out:
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print(f"\n  wrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
