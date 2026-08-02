#!/usr/bin/env python3
"""Runner for the FROZEN residual-momentum prereg (model#164 + Amendments 1-2). (GOAL-7)

COMPLETE runner: precondition verification, data assembly, and the full inference
stage (calibration, §4.4 rate gates, H1/H2 decision). `--execute` performs the real
study — it is guarded by the §7 execution gate, not by a missing implementation.

Execution gate (§7 of the prereg): may execute only after (a) the prereg merged
unmodified, (b) Amendments 1 and 2 merged (F1 alpha-t form; bootstrap adequacy rule —
this runner REFUSES to run on a tree where either amendment is absent), (c) this
runner PR merged, (d) single invocation with verbatim-committed JSON output.

Frozen inputs verified against the prereg's pinned digests BEFORE anything loads;
any mismatch → UNRESOLVED-DATA and nothing else happens.

RUNNER-DECLARED CONSTANT (reviewed here, since the prereg left it to the runner):
``MIN_SIDE_OBS = 30`` for F5's per-side beta floor. Justification `[本次实测
2026-08-01]`: the minimum down-day count in ANY rolling 252-day SPY window since 2016
is 97 (1st percentile 99; minimum up-day count 108), so 30 is a pure OLS-validity
floor that no realized calendar window approaches — it can bind only for names with
substantial missing data, where a nan into the ≥3-of-5 composite rule is the designed
outcome.

Exit codes: 0 preflight clean / run complete; 2 usage; 3 UNRESOLVED-DATA;
4 ALREADY-EXECUTED (the single-execution claim exists);
5 UNRESOLVED-METHOD (a validation gate failed; the report says which).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import os
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
AMENDMENT_3 = REPO / "doc/research/2026-08-01-goal7-momentum-prereg-amendment-3.md"
AMENDMENT_4 = REPO / "doc/research/2026-08-01-goal7-momentum-prereg-amendment-4.md"
PREREG = REPO / "doc/research/2026-08-01-goal7-residual-momentum-prereg.md"
HAC_SE = RQ / ".subrepo_runtime/repos/renquant-common/src/renquant_common/metrics/hac_se.py"
#: Amendment 3: §2 inputs resolve THROUGH the base-data fingerprint manifest
#: (renquant-base-data#59) — verify-then-read, and NO fallback to the live data/
#: paths under any condition (they refresh daily; the frozen digests stopped
#: resolving there within 24h of the freeze). Resolution prefers the PINNED runtime
#: copy (what deploys actually consume) over the developer checkout; the chosen
#: source is recorded in the preflight output, and the manifest_identity check binds
#: whichever copy is read to the frozen §2 digests, so a stale or divergent copy
#: cannot substitute a different dataset.
MANIFEST_CANDIDATES = (
    RQ / ".subrepo_runtime/repos/renquant-base-data/manifests/"
         "momentum-prereg-inputs-20260801.json",
    Path("/Users/renhao/git/github/renquant-base-data/manifests/"
         "momentum-prereg-inputs-20260801.json"),
)


# ---- §7 single-execution guard (codex review on #177) ---------------------------
#: The claim is taken ATOMICALLY (O_CREAT|O_EXCL) BEFORE any data read; the result
#: destination is PREDECLARED (never caller-selectable); claim and result are sealed
#: read-only at the end. A second invocation — concurrent or later, and INCLUDING
#: after an UNRESOLVED-METHOD/POWER outcome — is refused: rerunning a frozen study
#: is result selection. The ONLY release is the pre-inference identity refusal
#: (UNRESOLVED-DATA from the initial preflight): no estimand has been computed on
#: that path, so re-invocation cannot choose among results — and every such refusal
#: is appended to a durable ledger BEFORE the claim is released. A claim left behind
#: by a crash stays in force (refuse-and-investigate beats silent rerun); removing
#: it is a manual operator act that must leave its own durable record.
RUN_LEDGER_DIR = Path.home() / "renquant-data-store" / "goal7-momentum-prereg-run"
EXECUTION_CLAIM = RUN_LEDGER_DIR / "EXECUTION_CLAIM.json"
RESULT_PATH = RUN_LEDGER_DIR / "result.json"
REFUSALS_LOG = RUN_LEDGER_DIR / "refusals.jsonl"
EXIT_ALREADY_EXECUTED = 4


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _claim_execution() -> int | None:
    """Atomically take the single-execution claim; exit code on refusal, else None."""
    RUN_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(EXECUTION_CLAIM, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            prior = EXECUTION_CLAIM.read_text(encoding="utf-8")[:2000]
        except OSError:
            prior = "(claim unreadable)"
        print(json.dumps({
            "status": "ALREADY-EXECUTED",
            "why": ("the §7 single-execution claim exists; a second invocation "
                    "(concurrent or later, any prior outcome) is refused — "
                    "rerunning a frozen study is result selection"),
            "claim": prior,
            "result_present": RESULT_PATH.is_file(),
            "result_path": str(RESULT_PATH),
        }, indent=2))
        return EXIT_ALREADY_EXECUTED
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"claimed_at": _utc_now(), "pid": os.getpid(),
                   "prereg_sha256": _sha(PREREG), "status": "in-progress"},
                  fh, indent=2)
    return None


def _release_claim_unresolved(pre: dict) -> None:
    """Pre-inference identity refusal: durably ledger it, THEN release the claim."""
    with open(REFUSALS_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _utc_now(), "status": "UNRESOLVED-DATA",
                             "unresolved": pre.get("unresolved_data")}) + "\n")
    EXECUTION_CLAIM.unlink()


def _finish(rep: dict, code: int) -> int:
    """Every post-preflight terminal outcome: print, persist to the PREDECLARED
    path, seal result + claim read-only. The claim is never released here — any
    computed outcome, including UNRESOLVED-METHOD, consumes the single shot."""
    txt = json.dumps(rep, indent=2, sort_keys=True, default=str)
    print(txt)
    RESULT_PATH.write_text(txt + "\n", encoding="utf-8")
    claim = json.loads(EXECUTION_CLAIM.read_text(encoding="utf-8"))
    claim["status"] = "consumed"
    claim["finished_at"] = _utc_now()
    claim["exit_code"] = code
    claim["result_sha256"] = hashlib.sha256((txt + "\n").encode()).hexdigest()
    EXECUTION_CLAIM.write_text(json.dumps(claim, indent=2), encoding="utf-8")
    os.chmod(RESULT_PATH, 0o444)
    os.chmod(EXECUTION_CLAIM, 0o444)
    return code


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_snapshot_manifest() -> dict | None:
    """The Amendment-3 resolution manifest, or None (= UNRESOLVED-DATA, no fallback).

    The winning candidate's path is recorded under the non-identity key
    ``_manifest_source`` for the preflight report."""
    for cand in MANIFEST_CANDIDATES:
        if not cand.is_file():
            continue
        man = json.loads(cand.read_text())
        if man.get("dataset_id") != "momentum-prereg-inputs-20260801":
            continue
        man["_manifest_source"] = str(cand)
        return man
    return None


def _resolve_root(man: dict) -> Path | None:
    """content-addressed-v1 resolution: identity lives ENTIRELY in the manifest's
    digest set; a candidate root is only a cache hint. Selection is by existence
    (first root carrying panel.parquet); VALIDITY is decided by the digest checks
    that follow, and a digest failure there is a finding — never grounds to try
    the next root silently."""
    for cand in man.get("resolver", {}).get("candidate_roots", []):
        root = Path(cand["path"])
        if (root / "panel.parquet").is_file():
            return root
    return None


def _load_tr_builder():
    """The VALIDATED total-return construction, imported — never restated.

    Imports the PACKAGE home (renquant_model_common.total_return), not the
    build script: the script's top level executes the July study's raw-corpus
    guard and build loop, which crashed this runner's single --execute on
    2026-08-02 (SystemExit at import, before any data read — a guard
    validating the WRONG object for this runner, whose inputs are the frozen
    digest-verified store)."""
    from renquant_model_common.total_return import total_return_close
    return total_return_close


def verify_preconditions() -> dict:
    """Every §7 / §2 precondition, verified. NOTHING loads before this passes."""
    out: dict = {"checks": {}, "unresolved_data": []}

    def check(name, ok, detail=""):
        out["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            out["unresolved_data"].append(name)

    try:
        _load_tr_builder()
        _tr_ok, _tr_detail = True, "renquant_model_common.total_return imports cleanly"
    except BaseException as exc:  # noqa: BLE001 - incl. SystemExit: an import-time
        # guard in a dependency must become a pre-inference refusal (claim
        # releases), never a mid-execute crash that strands the claim (2026-08-02).
        _tr_ok, _tr_detail = False, f"{type(exc).__name__}: {exc}"
    check("tr_builder_importable", _tr_ok, _tr_detail)
    check("prereg_present", PREREG.is_file(), str(PREREG))
    check("amendment_1_present", AMENDMENT_1.is_file(),
          "runner implements the AMENDED F1; refuses on a pre-amendment tree")
    check("amendment_3_present", AMENDMENT_3.is_file(),
          "resolution-through-manifest IS Amendment-3 semantics; refuses without it")
    check("amendment_4_present", AMENDMENT_4.is_file(),
          "the gates implement Amendment-4 definitions; refuses without it")
    man = load_snapshot_manifest()
    check("snapshot_manifest_present", man is not None,
          f"candidates {[str(c) for c in MANIFEST_CANDIDATES]} — "
          "no live-path fallback exists by design")
    if man is not None:
        out["manifest_source"] = man.get("_manifest_source")
    check("hac_se_digest", HAC_SE.is_file() and _sha(HAC_SE) == FROZEN["hac_se_sha256"])
    if man is not None:
        check("manifest_identity",
              man["files"]["panel.parquet"]["sha256"] == FROZEN["panel_sha256"]
              and man["files"]["ticker_sectors.json"]["sha256"] == FROZEN["sector_sha256"]
              and man["combined_ohlcv_digest"]["value"] == FROZEN["ohlcv_combined_sha256"],
              "manifest headline digests must equal the frozen §2 pins byte-for-byte")
        root = _resolve_root(man)
        check("snapshot_root_resolves", root is not None,
              "no candidate root carries panel.parquet — refuse; no live-path fallback")
    if man is not None and root is not None:
        panel = root / "panel.parquet"
        check("panel_digest", panel.is_file() and _sha(panel) == FROZEN["panel_sha256"])
        sect = root / "ticker_sectors.json"
        check("sector_digest", sect.is_file() and _sha(sect) == FROZEN["sector_sha256"])
        if panel.is_file():
            tickers = sorted(pd.read_parquet(panel, columns=["ticker"])["ticker"].unique())
            h = hashlib.sha256()
            missing, per_file_mismatch = [], []
            for t in tickers:
                f = root / f"ohlcv/{t}/1d.parquet"
                if not f.is_file():
                    missing.append(t)
                    continue
                d = _sha(f)
                h.update(f"{t}:{d}\n".encode())
                entry = man["files"].get(f"ohlcv/{t}/1d.parquet")
                if entry is None or entry["sha256"] != d:
                    per_file_mismatch.append(t)
            check("ohlcv_combined_digest",
                  not missing and h.hexdigest() == FROZEN["ohlcv_combined_sha256"],
                  f"missing={missing[:5]}" if missing else "")
            check("ohlcv_per_file_vs_manifest", not per_file_mismatch,
                  f"mismatch={per_file_mismatch[:5]}" if per_file_mismatch
                  else "every file read verified against its manifest sha256")
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
    return {"scores": scores, "n_used": n_used, "_f1": dict(feats["f1"]),
            "n_scored": sum(1 for s in scores.values() if np.isfinite(s)),
            "n_names": int(len(day_panel))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preflight", action="store_true",
                    help="verify every precondition and print the JSON verdict")
    ap.add_argument("--execute", action="store_true",
                    help="§7 gate: single post-merge invocation; output committed verbatim")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)
    if a.execute:
        if a.json_out:
            print("--json-out is refused with --execute: the result destination "
                  f"is PREDECLARED ({RESULT_PATH}) so the outcome is never "
                  "caller-selectable (codex on #177)", file=sys.stderr)
            return 2
        return execute()
    if not a.preflight:
        print("nothing to do: pass --preflight (this revision) or --execute (later).",
              file=sys.stderr)
        return 2
    rep = verify_preconditions()
    print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep["ok"] else 3




# ===================================================================== stage B ====
# Execution orchestration. Frozen decisions only; every constant restated from the
# prereg + amendments, none invented here.

AMENDMENT_2 = REPO / "doc/research/2026-08-01-goal7-momentum-prereg-amendment-2.md"


def _spearman_ic(scores: dict[str, float], labels: pd.Series) -> float | None:
    """Per-date cross-sectional Spearman IC over names scored AND labelled."""
    common = [t for t, s in scores.items()
              if np.isfinite(s) and t in labels.index and np.isfinite(labels[t])]
    if len(common) < FROZEN["names_per_date_floor"]:
        return None
    a = pd.Series({t: scores[t] for t in common}).rank()
    b = labels[common].rank()
    return float(np.corrcoef(a, b)[0, 1])


def decide(h1_ic_mean: float, h1_t: float, t_star: float, placebo_mean_abs: float,
           d_ic_t: float, f1_ic_mean: float, f1_t: float,
           mde: float) -> dict:
    """The frozen decision map (§4.5 + Amendment-1-consistent H2). Pure function."""
    if mde > 0.06:
        return {"verdict": "UNRESOLVED-POWER",
                "why": f"realized MDE {mde:.4f} exceeds the frozen 0.06 ceiling"}
    h1_pass = (h1_ic_mean >= 0.04) and (abs(h1_t) >= t_star) and (placebo_mean_abs < 0.01)
    if not h1_pass:
        return {"verdict": "KILL",
                "why": (f"H1 failed: mean IC {h1_ic_mean:.4f} (bar 0.04), |t| "
                        f"{abs(h1_t):.2f} (bar {t_star:.2f}), placebo "
                        f"{placebo_mean_abs:.4f} (bar 0.01)")}
    f1_pass = (f1_ic_mean >= 0.04) and (abs(f1_t) >= t_star)
    if abs(d_ic_t) < t_star and f1_pass:
        return {"verdict": "RETAIN-F1",
                "why": "composite adds nothing over F1 AND F1 independently clears H1"}
    return {"verdict": "RETAIN-S",
            "why": ("composite clears H1; family adds value or F1 does not "
                    "independently clear the bar")}


def execute() -> int:
    import importlib.util as _ilu

    code = _claim_execution()
    if code is not None:
        return code
    pre = verify_preconditions()
    for extra, path in (("amendment_2_present", AMENDMENT_2),):
        pre["checks"][extra] = {"ok": path.is_file(), "detail": str(path)}
        if not path.is_file():
            pre["unresolved_data"].append(extra)
    if pre["unresolved_data"]:
        rep = {"status": "UNRESOLVED-DATA", "preflight": pre}
        print(json.dumps(rep, indent=2, sort_keys=True))
        _release_claim_unresolved(pre)
        return 3

    spec = _ilu.spec_from_file_location(
        "goal7_momentum_inference", REPO / "tools" / "goal7_momentum_inference.py")
    INF = _ilu.module_from_spec(spec)
    spec.loader.exec_module(INF)
    tr_close = _load_tr_builder()

    # Amendment 3: every read goes through the verified snapshot root (preflight has
    # already verified each file's sha against the manifest; the live data/ paths are
    # never touched).
    root = _resolve_root(load_snapshot_manifest())
    panel = pd.read_parquet(root / "panel.parquet",
                            columns=["ticker", "date", "fwd_20d_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    sector_of = {t: v.get("sector") for t, v in
                 json.loads((root / "ticker_sectors.json").read_text()).items()}

    tickers = sorted(panel["ticker"].unique())
    tr_returns, volumes = {}, {}
    for t in tickers + ["SPY"]:
        f = root / f"ohlcv/{t}/1d.parquet"
        raw = pd.read_parquet(f)
        tr = tr_close(raw["close"], raw.get("dividend",
                                            pd.Series(0.0, index=raw.index)))
        r = tr.pct_change()
        (tr_returns if True else None)[t] = r
        volumes[t] = raw["volume"]
    spy_tr = tr_returns.pop("SPY")

    ic_s, ic_f1, dates_used, skipped = [], [], [], {"thin": 0, "infeasible": 0}
    rng_placebo = np.random.default_rng(FROZEN["seed"])
    placebo_abs = []
    all_dates = sorted(panel["date"].unique())
    for asof in all_dates:
        day = panel[panel["date"] == asof]
        labels = day.set_index("ticker")["fwd_20d_excess"]
        out = assemble_day(day, tr_returns, spy_tr, volumes, sector_of,
                           pd.Timestamp(asof))
        ic = _spearman_ic(out["scores"], labels)
        if ic is None:
            skipped["thin"] += 1
            continue
        f1_scores = {t: v for t, v in out.get("_f1", {}).items()}
        ic1 = _spearman_ic(f1_scores, labels) if f1_scores else None
        if ic1 is None:
            skipped["infeasible"] += 1
            continue
        # placebo: 5 seeded within-date label permutations, centring only
        pl = []
        for _ in range(5):
            perm = pd.Series(rng_placebo.permutation(labels.to_numpy()),
                             index=labels.index)
            p_ic = _spearman_ic(out["scores"], perm)
            if p_ic is not None:
                pl.append(abs(p_ic))
        placebo_abs.append(float(np.mean(pl)) if pl else np.nan)
        ic_s.append(ic); ic_f1.append(ic1); dates_used.append(str(pd.Timestamp(asof).date()))

    s = np.array(ic_s); f1 = np.array(ic_f1)
    d_ic = s - f1
    cfg = dict(INF.FROZEN_INFERENCE)
    cfg["envelope_rule"] = "bootstrap_max"

    # HAC mirror cross-check against the PINNED implementation
    sys.path.insert(0, str(HAC_SE.parent.parent.parent))
    from renquant_common.metrics.hac_se import newey_west_se
    t_mine = INF.bartlett_hac_t(s, cfg["L"])
    t_pinned = float(s.mean()) / newey_west_se(s, lag=cfg["L"])
    if not np.isclose(t_mine, t_pinned, rtol=1e-9):
        return _finish({"status": "UNRESOLVED-DATA",
                        "why": f"HAC mirror mismatch: {t_mine} vs pinned {t_pinned}"},
                       3)

    realized_acf = [float(a) for a in INF.sample_acf(s, cfg["acf_envelope_lags"])]
    cal = INF.calibrate_bar(s, cfg)
    if cal["status"] != "calibrated":
        # §4.4: bars and the realized ACF are published regardless of outcome.
        return _finish({"status": "UNRESOLVED-METHOD", "calibration": cal,
                        "realized_acf": realized_acf,
                        "n_dates": len(s), "dates_skipped": skipped}, 5)

    # gates (§4.4) — both are 5,000-rep RATE checks against the frozen band, not
    # single-statistic comparisons. The positive-control fixture is DEDICATED and
    # content-pinned (no more borrowing an unrelated clf-bundle CSV).
    pc_path = Path(__file__).resolve().parent / "data/goal7_positive_control_noise.csv"
    pc_sha = hashlib.sha256(pc_path.read_bytes()).hexdigest()
    if pc_sha != cfg["positive_control_sha256"]:
        return _finish({"status": "UNRESOLVED-DATA",
                        "why": f"positive-control fixture digest mismatch: {pc_sha} "
                               f"!= pinned {cfg['positive_control_sha256']}"}, 3)
    noise = pd.read_csv(pc_path, float_precision="round_trip")["x"].to_numpy()
    pc = INF.positive_control(noise, cfg)
    mach = INF.machinery_self_check(s, cal, cfg)
    se_hac = float(s.mean()) / t_mine if t_mine else float("nan")
    mde = cal["t_star"] * abs(se_hac)
    if not (pc["ok"] and mach["ok"]):
        return _finish({"status": "UNRESOLVED-METHOD",
                        "positive_control": pc,
                        "machinery": mach,
                        "calibration": cal, "realized_acf": realized_acf}, 5)

    verdict = decide(float(s.mean()), t_mine, cal["t_star"],
                     float(np.nanmean(placebo_abs)),
                     INF.bartlett_hac_t(d_ic, cfg["L"]),
                     float(f1.mean()), INF.bartlett_hac_t(f1, cfg["L"]), mde)
    rep = {"status": "COMPLETED", "verdict": verdict,
           "n_dates": len(s), "dates_skipped": skipped,
           "mean_ic_S": float(s.mean()), "t_S": t_mine, "t_star": cal["t_star"],
           "mean_ic_F1": float(f1.mean()), "t_F1": INF.bartlett_hac_t(f1, cfg["L"]),
           "t_delta": INF.bartlett_hac_t(d_ic, cfg["L"]),
           "placebo_mean_abs": float(np.nanmean(placebo_abs)),
           "mde": mde, "calibration": cal,
           "positive_control": pc, "machinery": mach,
           "realized_acf": realized_acf,
           "preflight": pre}
    return _finish(rep, 0)


if __name__ == "__main__":
    raise SystemExit(main())
