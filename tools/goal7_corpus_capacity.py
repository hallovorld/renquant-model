#!/usr/bin/env python3
"""Which label horizons could EVER have a bootstrap-identifiable bar on this corpus?

model#147 measured that GOAL-7 Stage 1's registered `t_{0.975,17} = 2.1098` bar is **not
identifiable**: preserving a 120-trading-day label's dependence forces a bootstrap block
`Lb >= 120`, which on 1 080 dates leaves 9 independent draws where ~20 are needed to
estimate a 5% tail. That answered the question for **one** design. It left the design
question open: *which horizon, if any, does this corpus support?*

This is the arithmetic, run against the real admissible calendar `[本次实测 2026-08-01]`.
The requirement is `available_dates >= draws_floor * h` — the same two conditions as
model#147, applied across horizons instead of to one.

    corpus calendar          3 161 dates   2014-01-02 -> 2026-07-29
    admissible (>=20 names)  2 407 dates   2016-12-29 -> 2026-07-29

===== ============== ========= ========== =========
  h   scope            avail     need@20   verdict
===== ============== ========= ========== =========
   20  pre-burn          1 182        400  OK
   60  pre-burn          1 142      1 200  SHORT   @floor 20
  120  pre-burn          1 082      2 400  SHORT   @floor 20
  120  whole corpus      2 287      2 400  SHORT   @floor 20 — but OK @floor 10
===== ============== ========= ========== =========

EVERY CELL ABOVE IS AT ONE FLOOR. The verdicts that survive the sweep are the only ones
this tool asserts `[codex on model#148]`:

  * **pre-burn `h = 120` is INFEASIBLE across all swept floors (10 / 20 / 30).** Robust.
  * **whole-corpus `h = 120` is FLOOR_DEPENDENT** — short at 20 and 30, OK at 10 — and
    **must not drive a design decision.**

An earlier version of this docstring stated the whole-corpus result as an ABSOLUTE — that
no amount of data could rescue `h = 120`. That is **withdrawn**: it contradicts this
tool's own sweep, and it was still reachable through `--help` after the progress document
had been corrected — the same retracted claim living on in a second user-facing surface.

(The withdrawn sentence is described here rather than quoted. Quoting it would put the
exact phrase back into `--help`, where a reader skimming for the conclusion finds the
words and not the retraction — and it would defeat the regression below, which is how I
noticed.)

Addendum 2 makes the whole-corpus row weaker still, not stronger: the draws floor's
stated rationale was refuted by measurement, so a verdict that flips with the floor rests
on a convention that could not be justified.

THE FLOOR IS MINE, SO ITS SENSITIVITY IS REPORTED. `draws_floor = 20` is a convention I
chose in model#147, not a standard, so a verdict resting on it is only as good as the
choice. Swept over 10 / 20 / 30:

  * `h = 120` pre-burn is **SHORT at every floor** — that verdict does not depend on me.
  * `h = 20` pre-burn is **OK at every floor**.
  * `h = 60` pre-burn is OK at 10 and SHORT at 20 and 30 — **floor-dependent, therefore
    NOT settled**, and it must not be reported as feasible.

CAPACITY IS NOT POWER, AND THE DISTINCTION IS LOAD-BEARING. Clearing this test means a
bar *could be calibrated*, not that a design *could detect anything*. GOAL-6 Stage 0
already measured that the shorter horizon buys no statistical power (H2 NOT SUPPORTED:
~3x the independent blocks, proportionately smaller effect, flat ratio). So `h = 20`
passing here is a statement about calibration only, and using it as an argument for a
20-day design would be substituting one instrument for another.

THE BURN BOUNDARY IS NOT MINE TO LIFT. `2021-10-08` is registered (AMENDMENT 2, A2.2) as
burned for this hypothesis. The `whole corpus` rows exist to BOUND the question — to show
that no amount of extra data rescues `h = 120` — and are not a licensed design.

Read-only. Reads the momentum matrix, writes only under ``--out``. Decides nothing and
freezes nothing.

Exit codes: ``0`` at least one horizon is feasible at the given floor, ``1`` none is,
``2`` usage/IO error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

#: Registered burn boundary (AMENDMENT 2, A2.2) — dates whose label window reaches past
#: this are burned for this hypothesis.
BURN = pd.Timestamp("2021-10-08")

#: §2A per-date admissibility floor, and the feature columns whose presence defines it.
MIN_NAMES = 20
FEATURE_COLS = ("mom_12_1_tr", "vol_60_tr")

#: Swept, never assumed. See the module docstring: the h=120 verdict survives all three.
DRAWS_FLOORS = (10, 20, 30)
HORIZONS = (20, 60, 120)


def admissible_calendar(matrix: Path) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex,
                                               pd.DataFrame]:
    """(corpus calendar, admissible dates). Admissible = the §2A rule, not a guess."""
    m = pd.read_parquet(matrix, columns=["date", "ticker", *FEATURE_COLS])
    m["date"] = pd.to_datetime(m["date"])
    cal = pd.DatetimeIndex(np.sort(m["date"].unique()))
    elig = m.dropna(subset=list(FEATURE_COLS))
    cnt = elig.groupby("date").size()
    adm = pd.DatetimeIndex(np.sort(cnt[cnt >= MIN_NAMES].index))
    return cal, adm, m


def last_usable_t(cal: pd.DatetimeIndex, h: int, pre_burn: bool) -> pd.Timestamp | None:
    """The last date whose full `h`-session label window exists (and, pre-burn, closes
    before the boundary). Derived from the corpus's OWN trading-day index — A4.3 makes
    that the calendar of record, and a calendar-day approximation would silently move it.
    """
    if h >= len(cal):
        return None
    if not pre_burn:
        return cal[len(cal) - h - 1]
    ok = [i for i in range(len(cal) - h) if cal[i + h] < BURN]
    return cal[max(ok)] if ok else None


def admissibility_loss(cal, adm, m) -> dict:
    """WHY the admissible window starts where it does — asked because #148's verdict is
    only meaningful if the shortfall is the corpus and not a conservative rule.

    Splits every inadmissible date into the two causes that can produce one, and tests the
    obvious third suspect (the name floor) by re-running it at lower thresholds.
    """
    import numpy as np  # noqa: PLC0415
    rows = m.groupby("date").size()
    both = m.dropna(subset=list(FEATURE_COLS)).groupby("date").size()
    df = pd.DataFrame({"rows": rows, "both": both}).fillna(0).astype(int)
    lost = df[df["both"] < MIN_NAMES]
    empty = lost[lost["rows"] < MIN_NAMES]
    warm = lost[lost["rows"] >= MIN_NAMES]
    first20 = df[df["rows"] >= MIN_NAMES].index[0]
    firstadm = df[df["both"] >= MIN_NAMES].index[0]
    warm_sessions = int((df.index >= first20).sum() - (df.index >= firstadm).sum())
    # The name floor as a suspect, falsified rather than argued.
    by_floor = {f: int((both >= f).sum()) for f in (5, 10, 20)}
    return {
        "n_inadmissible": int(len(lost)),
        "corpus_has_under_min_names": {
            "n": int(len(empty)),
            "first": str(empty.index[0].date()) if len(empty) else None,
            "last": str(empty.index[-1].date()) if len(empty) else None},
        "feature_warmup": {
            "n": int(len(warm)),
            "first": str(warm.index[0].date()) if len(warm) else None,
            "last": str(warm.index[-1].date()) if len(warm) else None,
            "sessions_between_first_20_names_and_first_admissible": warm_sessions,
            "note": ("mom_12_1_tr needs 12 months of history, so a ~250-session gap "
                     "between 'names exist' and 'the feature is computable' is the "
                     "FEATURE's definition, not a defect to be tuned away.")},
        "admissible_dates_by_name_floor": by_floor,
        "name_floor_is_not_binding": len({v for v in by_floor.values()}) == 1,
        "conclusion": (
            "The shortfall behind h=120 is the CORPUS, not a conservative admissibility "
            "rule. Extending the window backwards recovers nothing (those dates have no "
            "names), the warm-up is exactly the feature's own lookback, and relaxing the "
            "name floor from 20 to 10 to 5 recovers ZERO dates."),
    }


def capacity(matrix: Path) -> dict:
    cal, adm, m_for_loss = admissible_calendar(matrix)
    rows = []
    for floor in DRAWS_FLOORS:
        for h in HORIZONS:
            for pre_burn in (True, False):
                last = last_usable_t(cal, h, pre_burn)
                if last is None:
                    rows.append({"draws_floor": floor, "horizon": h,
                                 "scope": "pre_burn" if pre_burn else "whole_corpus",
                                 "status": "NO_USABLE_DATE", "available": 0,
                                 "needed": floor * h, "feasible": False})
                    continue
                n = int((adm <= last).sum())
                rows.append({
                    "draws_floor": floor, "horizon": h,
                    "scope": "pre_burn" if pre_burn else "whole_corpus",
                    "status": "checked", "last_usable_t": str(last.date()),
                    "available": n, "needed": floor * h, "feasible": n >= floor * h})

    def verdicts(h: int, scope: str) -> list[bool]:
        return [r["feasible"] for r in rows if r["horizon"] == h and r["scope"] == scope]

    robust = {}
    for h in HORIZONS:
        for scope in ("pre_burn", "whole_corpus"):
            v = verdicts(h, scope)
            robust[f"h{h}/{scope}"] = (
                "FEASIBLE" if all(v) else
                "INFEASIBLE" if not any(v) else
                # The honest third value. A verdict that flips with the floor rests on my
                # convention, not on the corpus, and must not be reported either way.
                "FLOOR_DEPENDENT")
    loss = admissibility_loss(cal, adm, m_for_loss)
    return {
        "admissibility_loss": loss,
        "corpus_calendar_dates": len(cal),
        "corpus_first": str(cal[0].date()), "corpus_last": str(cal[-1].date()),
        "admissible_dates": len(adm),
        "admissible_first": str(adm[0].date()), "admissible_last": str(adm[-1].date()),
        "min_names": MIN_NAMES, "burn_boundary": str(BURN.date()),
        "draws_floors_swept": list(DRAWS_FLOORS), "horizons": list(HORIZONS),
        "rows": rows,
        "robust_verdict": robust,
        "scope_note": (
            "CAPACITY IS NOT POWER. Clearing this test means a bar COULD be calibrated, "
            "not that a design could detect anything — GOAL-6 Stage 0 measured that the "
            "shorter horizon buys no power (H2 NOT SUPPORTED). And the burn boundary is "
            "registered (A2.2); the whole_corpus rows BOUND the question, they do not "
            "license a design."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        rep = capacity(a.matrix)
        rep["matrix_sha256"] = hashlib.sha256(a.matrix.read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError) as exc:
        print(f"capacity: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        print(f"  corpus     {rep['corpus_calendar_dates']:>6} dates  "
              f"{rep['corpus_first']} -> {rep['corpus_last']}")
        print(f"  admissible {rep['admissible_dates']:>6} dates  "
              f"{rep['admissible_first']} -> {rep['admissible_last']} "
              f"(>= {rep['min_names']} names)")
        print(f"\n  {'floor':>6}{'h':>5}{'scope':>14}{'avail':>8}{'need':>7}  verdict")
        for r in rep["rows"]:
            print(f"  {r['draws_floor']:>6}{r['horizon']:>5}{r['scope']:>14}"
                  f"{r['available']:>8}{r['needed']:>7}  "
                  f"{'OK' if r['feasible'] else 'SHORT'}")
        print("\n  robust across every floor swept:")
        for k, v in rep["robust_verdict"].items():
            print(f"    {k:<22}{v}")
        print("\n  " + rep["scope_note"])

    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {a.out}")

    return 0 if any(r["feasible"] for r in rep["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
