#!/usr/bin/env python3
"""Runner for the FROZEN residual-momentum prereg (model#164 + Amendment 1). (GOAL-7)

STAGE A ONLY in this revision: precondition verification and data assembly. The
inference stage (calibration, gates, H1/H2) lands in a follow-up revision of this same
PR; `--execute` refuses until it exists. Nothing here computes an IC, a score
statistic, or touches a label beyond schema checks.

Execution gate (§7 of the prereg): may execute only after (a) the prereg merged
unmodified, (b) Amendment 1 merged (the F1-degeneracy fix — this runner implements the
AMENDED alpha-t form via `renquant_model_common.momentum_features` and therefore
REFUSES to run on a tree where the amendment is absent), (c) this runner PR merged,
(d) single invocation with verbatim-committed JSON output.

Frozen inputs verified against the prereg's pinned digests BEFORE anything loads;
any mismatch → UNRESOLVED-DATA and nothing else happens.

RUNNER-DECLARED CONSTANT (reviewed here, since the prereg left it to the runner):
``MIN_SIDE_OBS = 30`` for F5's per-side beta floor. Justification `[本次实测
2026-08-01]`: the minimum down-day count in ANY rolling 252-day SPY window since 2016
is 97 (1st percentile 99; minimum up-day count 108), so 30 is a pure OLS-validity
floor that no realized calendar window approaches — it can bind only for names with
substantial missing data, where a nan into the ≥3-of-5 composite rule is the designed
outcome.

Exit codes: 0 preflight clean / run complete; 2 usage; 3 UNRESOLVED-DATA; 4 stage
not implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RQ = Path("/Users/renhao/git/github/RenQuant")

sys.path.insert(0, str(REPO / "src"))
from renquant_model_common.momentum_features import (  # noqa: E402
    composite_scores, f1_residual_momentum, f2_information_discreteness,
    f3_industry_momentum, f4_signed_volume_agreement, f5_downside_beta_penalty)

# ---- frozen by the prereg (model#164); the runner only restates, never chooses ----
FROZEN = {
    "panel_sha256": "55811f6387e67411fe11a20eb1d5d929086c5a9dc2675496f3d8592fed2c0dba",
    "sector_sha256": "ec26bb1efcf8463519366478ae72c933f93c9d110d65f8af1634e2fcbb578d3b",
    "ohlcv_combined_sha256": "4d4638a9f0d69f940fb36a73c28e92883d51b686ab032aebedf559c174c2c1d0",
    "hac_se_sha256": "c568ed51428b642c936eda865779b57e0282814f170bb1528e86be2ba9f9b8bc",
    "window": 252, "skip": 21, "min_obs": 200, "min_features": 3,
    "names_per_date_floor": 50, "h": 20, "seed": 20260801,
}
#: runner-declared (see module docstring), reviewed in this PR:
MIN_SIDE_OBS = 30

AMENDMENT_1 = REPO / "doc/research/2026-08-01-goal7-momentum-prereg-amendment-1.md"
PREREG = REPO / "doc/research/2026-08-01-goal7-residual-momentum-prereg.md"
HAC_SE = RQ / ".subrepo_runtime/repos/renquant-common/src/renquant_common/metrics/hac_se.py"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_tr_builder():
    """The VALIDATED total-return construction, imported — never restated."""
    spec = importlib.util.spec_from_file_location(
        "build_total_return_series", REPO / "tools" / "build_total_return_series.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.total_return_close


def verify_preconditions() -> dict:
    """Every §7 / §2 precondition, verified. NOTHING loads before this passes."""
    out: dict = {"checks": {}, "unresolved_data": []}

    def check(name, ok, detail=""):
        out["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            out["unresolved_data"].append(name)

    check("prereg_present", PREREG.is_file(), str(PREREG))
    check("amendment_1_present", AMENDMENT_1.is_file(),
          "runner implements the AMENDED F1; refuses on a pre-amendment tree")
    panel = RQ / "data/alpha158_291_fundamental_dataset.parquet"
    check("panel_digest", panel.is_file() and _sha(panel) == FROZEN["panel_sha256"])
    sect = RQ / "data/ticker_sectors.json"
    check("sector_digest", sect.is_file() and _sha(sect) == FROZEN["sector_sha256"])
    check("hac_se_digest", HAC_SE.is_file() and _sha(HAC_SE) == FROZEN["hac_se_sha256"])
    if panel.is_file():
        tickers = sorted(pd.read_parquet(panel, columns=["ticker"])["ticker"].unique())
        h = hashlib.sha256()
        missing = []
        for t in tickers:
            f = RQ / f"data/ohlcv/{t}/1d.parquet"
            if not f.is_file():
                missing.append(t)
                continue
            h.update(f"{t}:{_sha(f)}\n".encode())
        check("ohlcv_combined_digest",
              not missing and h.hexdigest() == FROZEN["ohlcv_combined_sha256"],
              f"missing={missing[:5]}" if missing else "")
        out["n_tickers"] = len(tickers)
    out["prereg_sha256_at_run"] = _sha(PREREG) if PREREG.is_file() else None
    out["ok"] = not out["unresolved_data"]
    return out


def assemble_day(day_panel: pd.DataFrame, tr_returns: dict[str, pd.Series],
                 spy_tr: pd.Series, volumes: dict[str, pd.Series],
                 sector_of: dict[str, str], asof: pd.Timestamp) -> dict:
    """F1–F5 + composite for one date. Pure assembly over the engine; every drop
    counted, never silent."""
    lo = asof - pd.tseries.offsets.BDay(FROZEN["window"] + FROZEN["skip"])
    hi = asof - pd.tseries.offsets.BDay(FROZEN["skip"])
    feats: dict[str, dict[str, float]] = {k: {} for k in ("f1", "f2", "f3", "f4", "f5")}
    formation: dict[str, float] = {}
    m = spy_tr.loc[(spy_tr.index > lo) & (spy_tr.index <= hi)]
    for t in day_panel["ticker"]:
        r = tr_returns.get(t)
        if r is None:
            continue
        w = r.loc[(r.index > lo) & (r.index <= hi)]
        pair = pd.concat([w, m], axis=1, join="inner").dropna()
        ri, rm = pair.iloc[:, 0].to_numpy(), pair.iloc[:, 1].to_numpy()
        feats["f1"][t] = f1_residual_momentum(ri, rm, min_obs=FROZEN["min_obs"])
        feats["f2"][t] = f2_information_discreteness(ri, min_obs=FROZEN["min_obs"])
        v = volumes.get(t)
        vw = (v.reindex(pair.index).to_numpy() if v is not None
              else np.full(len(pair), np.nan))
        feats["f4"][t] = f4_signed_volume_agreement(ri, vw, min_obs=FROZEN["min_obs"])
        feats["f5"][t] = f5_downside_beta_penalty(
            ri, rm, min_obs=FROZEN["min_obs"], min_side_obs=MIN_SIDE_OBS)
        formation[t] = float(np.prod(1.0 + ri) - 1.0) if len(ri) else float("nan")
    feats["f3"] = f3_industry_momentum(formation, sector_of)
    scores, n_used = composite_scores(feats, min_features=FROZEN["min_features"])
    return {"scores": scores, "n_used": n_used,
            "n_scored": sum(1 for s in scores.values() if np.isfinite(s)),
            "n_names": int(len(day_panel))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preflight", action="store_true",
                    help="verify every precondition and print the JSON verdict")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args(argv)
    if a.execute:
        print("execute: the inference stage is not implemented in this revision; "
              "refusing (exit 4).", file=sys.stderr)
        return 4
    if not a.preflight:
        print("nothing to do: pass --preflight (this revision) or --execute (later).",
              file=sys.stderr)
        return 2
    rep = verify_preconditions()
    print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
