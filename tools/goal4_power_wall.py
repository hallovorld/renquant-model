"""Re-derive GOAL-4's §2 power table from the committed probe. No new data.

Every number in `doc/design/2026-07-30-goal4-power-wall-and-options.md` §2 comes
from here, so the design PR's arithmetic is reproducible rather than transcribed.
Reads only `control_power_probe.json`, which is already committed and digest-pinned
by the Phase-0 manifest.

The block-count solver is a plain INTEGER SCAN, deliberately. The first version was
a fixed-point iteration that diverged and produced a non-monotone table (g=0.098
appeared to need more blocks than g=0.020). `--self-check` asserts monotonicity, so
that class of bug cannot ship silently again.

    python tools/goal4_power_wall.py --self-check
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scipy import stats

PROBE = (Path(__file__).resolve().parent.parent / "doc" / "research" / "data"
         / "2026-07-30-goal4-phase0-ensemble-gain" / "control_power_probe.json")

#: Gains the design document tabulates. Not thresholds — the whole point of the
#: design PR is that nobody has yet chosen which of these is worth deploying.
TARGET_GAINS = (0.0257, 0.0200, 0.0100, 0.0050, 0.0020, 0.0008)


def block_se(main_arm: dict) -> float:
    """s.e. of the block mean, recovered from the arm's own mean and t.

    The probe reports mean and t but not the standard error; |mean|/|t| is exact
    for a one-sample t, so this is a rearrangement rather than an estimate.
    """
    return abs(main_arm["mean"]) / abs(main_arm["t"])


def blocks_needed(gain: float, se_ref: float, n_ref: int, cap: int = 2_000_000) -> int:
    """Smallest n with `gain >= t(0.975, n-1) * se_ref * sqrt(n_ref / n)`.

    s.e. shrinks as 1/sqrt(n) while the Student critical value *also* falls with n,
    so both sides move; scanning avoids having to linearise either.
    """
    for n in range(2, cap):
        if gain >= stats.t.ppf(0.975, n - 1) * se_ref * math.sqrt(n_ref / n):
            return n
    raise ValueError(f"no n below {cap} detects {gain}")


def build(probe: dict) -> dict:
    arm = probe["independent_main_arm"]
    se, nb, ne = block_se(arm), arm["n_blocks"], arm["n_eval"]
    t_crit = probe["t_crit_student_leg"]
    rows = []
    for g in TARGET_GAINS:
        n = blocks_needed(g, se, nb)
        rows.append({"gain": g, "blocks": n, "eval_dates": round(n * ne / nb),
                     "years": round(n * ne / nb / 252, 1), "vs_today": round(n / nb, 1)})
    return {
        "n_eval": ne, "n_blocks": nb, "dates_per_block": round(ne / nb, 1),
        "observed_gain": arm["mean"], "observed_t": arm["t"],
        "block_se": se, "t_crit": t_crit,
        "minimum_detectable_gain": t_crit * se,
        "benchmark_mean_ic": probe["benchmark_mean_ic"],
        "rows": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(PROBE))
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)

    out = build(json.loads(Path(a.probe).read_text()))

    if a.self_check:
        rows = out["rows"]
        # Sorted by DECREASING gain, so blocks must be strictly increasing. This is
        # the exact invariant the discarded solver violated.
        assert all(r["gain"] > s["gain"] for r, s in zip(rows, rows[1:])), "gains unsorted"
        assert all(r["blocks"] < s["blocks"] for r, s in zip(rows, rows[1:])), \
            f"NON-MONOTONE: {[(r['gain'], r['blocks']) for r in rows]}"
        # The tabulated MDE must be the gain that needs exactly the realised block
        # count -- otherwise the table and the headline describe different screens.
        assert blocks_needed(out["minimum_detectable_gain"], out["block_se"],
                             out["n_blocks"]) <= out["n_blocks"] + 1

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
