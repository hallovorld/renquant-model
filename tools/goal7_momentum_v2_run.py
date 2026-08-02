#!/usr/bin/env python3
"""Runner for the FROZEN residual-momentum v2 prereg: gap-block inference. (GOAL-7)

Implements the v2 preregistration (doc/research/2026-08-02-goal7-momentum-v2-prereg.md,
backlog model#190, prereg PR model#191) in its exact §3.1 ordering. Where this runner
and that document disagree, THE DOCUMENT GOVERNS (its §5). This runner may not execute
before the prereg merges: preflight requires the prereg file present on this tree
(``v2_prereg_present``) and refuses without it.

Candidate, inputs, estimand and placebo discipline are UNCHANGED from v1 and are
REUSED from the v1 runner by import — preflight (same dataset digests, incl.
``tr_builder_importable``), Amendment-3 manifest resolution, ``assemble_day``,
``_spearman_ic``, the TR builder. Nothing of the candidate is restated here.

What v2 REPLACES is inference only (prereg §2): non-overlapping h=20 blocks separated
by discarded gaps of 20 dates over the realized scored-date sequence; one-sample t
over surviving block means against t_{0.975, df}; a lag-1-autocorrelation refusal
valve on the block means; frozen Normal controls (PCG64, seed 20260801+r) run BEFORE
H1/H2; then the §4 decision map. No HAC, no AR/MA fitting, no bootstrap anywhere in
the decision path (prereg §2.6).

Single-shot machinery is the v1 design pointed at the NEW predeclared run dir
``~/renquant-data-store/goal7-momentum-v2-prereg-run/``: O_EXCL claim before any
read, predeclared sealed result, rerun refused; every terminal outcome (including
every UNRESOLVED form) consumes the shot; only a pre-inference identity refusal
(UNRESOLVED-DATA) releases the claim, after a durable ledger entry.

Exit codes: 0 preflight clean / run completed through §4 (verdict may be KILL,
RETAIN-F1, RETAIN-S, or UNRESOLVED-POWER via the §4 MDE gate); 2 usage;
3 UNRESOLVED-DATA; 4 ALREADY-EXECUTED; 5 UNRESOLVED-METHOD (§3.1(c)/(c')
degenerate scale, §2.5 rho_1 valve, §3.1(d) control-gate violation);
6 UNRESOLVED-POWER at §3.1(b) (n_surviving below the frozen floor, pre-controls).

RUNNER-DECLARED READING (flagged for prereg reconciliation in the PR body): §4's
"mean IC(S)" is read as the mean of the SURVIVING BLOCK MEANS — the same location
parameter the §2.3 t statistic tests — and the per-date grand means are additionally
published as ``mean_ic_S_dates`` / ``mean_ic_F1_dates`` for transparency. The single
published bar uses df = n_surviving(S) − 1, the df named by §2.3/§2.4.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as _student_t

REPO = Path(__file__).resolve().parent.parent


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: The v1 runner — preflight, manifest resolution, assemble_day, _spearman_ic and the
#: TR builder are all reused FROM it (prereg §1: every carried-over object is pinned,
#: not restated). This file never modifies the v1 runner.
V1 = _load_tool("goal7_momentum_run")
#: sample_acf reused for the §2.5 rho_1 adequacy valve (same estimator v1 published
#: its realized ACF with).
INF = _load_tool("goal7_momentum_inference")

_sha = V1._sha
_utc_now = V1._utc_now

# ---- frozen by the v2 prereg; the runner only restates, never chooses ------------
FROZEN_V2 = {
    "h": 20,                     # block width = label horizon (prereg §2.1)
    "gap": 20,                   # discarded gap between blocks = h (prereg §2.1)
    "min_usable_per_block": 10,  # §2.2: thinner blocks dropped and counted
    "min_surviving_blocks": 40,  # §2.2: below -> UNRESOLVED-POWER, controls NOT run
    "rho1_ceiling": 0.25,        # §2.5: |rho_1(block means)| at/above -> METHOD
    "quantile": 0.975,           # §2.4: two-sided Student-t bar, df-aware
    "n_reps": 1000,              # §3.2: control replications
    "base_seed": 20260801,       # §3: placebo seed AND control base seed
    "placebo_perms": 5,          # §3: per-date within-date label permutations
    "placebo_ceiling": 0.01,     # §3: H1 requires placebo mean |IC| below this
    "positive_mu": 0.04,         # §3.3: = the §4 H1 threshold
    "positive_rate_min": 0.80,   # §3.3: positive-control clear-rate floor
    "negative_mu": 0.0,          # §3.4
    "negative_rate_max": 0.10,   # §3.4: negative-control clear-rate ceiling
    "mde_ceiling": 0.06,         # §4
    "h1_mean_min": 0.04,         # §4
}

# ---- single-execution guard, v1 design, NEW v2 run dir ---------------------------
#: These are the v2 study's predeclared claim/result/refusals surfaces. The v1
#: functions are hardwired to the v1 module's globals; parameterizing them would
#: modify the v1 runner (out of scope for this PR), so the guard is mirrored here
#: against these constants instead of imported.
RUN_LEDGER_DIR = Path.home() / "renquant-data-store" / "goal7-momentum-v2-prereg-run"
EXECUTION_CLAIM = RUN_LEDGER_DIR / "EXECUTION_CLAIM.json"
RESULT_PATH = RUN_LEDGER_DIR / "result.json"
REFUSALS_LOG = RUN_LEDGER_DIR / "refusals.jsonl"

V2_PREREG = REPO / "doc/research/2026-08-02-goal7-momentum-v2-prereg.md"

EXIT_ALREADY_EXECUTED = 4
EXIT_UNRESOLVED_METHOD = 5
EXIT_UNRESOLVED_POWER = 6


def _claim_execution() -> int | None:
    """Atomically take the v2 single-execution claim; exit code on refusal, else None.

    O_CREAT|O_EXCL BEFORE any data read; a second invocation — concurrent or later,
    and INCLUDING after any UNRESOLVED outcome — is refused: rerunning a frozen study
    is result selection. A claim left behind by a crash stays in force; removing it is
    a manual operator act that must leave its own durable record."""
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
            "why": ("the single-execution claim exists; a second invocation "
                    "(concurrent or later, any prior outcome) is refused — "
                    "rerunning a frozen study is result selection"),
            "claim": prior,
            "result_present": RESULT_PATH.is_file(),
            "result_path": str(RESULT_PATH),
        }, indent=2))
        return EXIT_ALREADY_EXECUTED
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"claimed_at": _utc_now(), "pid": os.getpid(),
                   "prereg_v2_sha256": (_sha(V2_PREREG) if V2_PREREG.is_file()
                                        else None),
                   "status": "in-progress"}, fh, indent=2)
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
    computed outcome, including every UNRESOLVED form, consumes the single shot."""
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


# ---- preflight -------------------------------------------------------------------
def verify_preconditions() -> dict:
    """The v1 check set (SAME dataset: identity digests, manifest resolution,
    tr_builder_importable, prereg+amendment presence) PLUS the v2 requirements.
    NOTHING loads before this passes."""
    pre = V1.verify_preconditions()

    def check(name, ok, detail=""):
        pre["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            pre["unresolved_data"].append(name)

    check("amendment_2_present", V1.AMENDMENT_2.is_file(),
          "the carried-over v1 candidate lineage includes Amendment 2")
    check("v2_prereg_present", V2_PREREG.is_file(),
          "the v2 prereg GOVERNS this runner (its §5); absent until model#191 "
          "merges — refusal by design")
    check("v1_result_present", Path(V1.RESULT_PATH).is_file(),
          "the v1 sealed result is this study's provenance (model#189): "
          f"{V1.RESULT_PATH}")
    pre["v2_prereg_sha256_at_run"] = _sha(V2_PREREG) if V2_PREREG.is_file() else None
    pre["ok"] = not pre["unresolved_data"]
    return pre


# ---- §2 gap-block machine (pure functions, no I/O) -------------------------------
def partition_blocks(T: int, h: int, gap: int) -> list[tuple[int, int]]:
    """§2.1: block k covers positions [k*(h+gap), k*(h+gap)+h) of the realized
    scored-date sequence; n_blocks = floor((T-h)/(h+gap)) + 1 for T >= h, else 0.
    At v1's realized T=2378 this is 59. Thin dates never enter the scored
    sequence, so they change T only — the partition never shifts within it."""
    if T < h:
        return []
    n = (T - h) // (h + gap) + 1
    return [(k * (h + gap), k * (h + gap) + h) for k in range(n)]


def block_stats(values: np.ndarray, h: int, gap: int, min_usable: int) -> dict:
    """§2.2: per-block mean over the block's usable (finite) dates; blocks with
    fewer than ``min_usable`` usable dates are dropped AND counted."""
    v = np.asarray(values, float)
    blocks = partition_blocks(len(v), h, gap)
    means: list[float] = []
    usable_counts: list[int] = []
    dropped = 0
    for lo, hi in blocks:
        w = v[lo:hi]
        finite = w[np.isfinite(w)]
        usable_counts.append(int(len(finite)))
        if len(finite) < min_usable:
            dropped += 1
            continue
        means.append(float(finite.mean()))
    return {"n_blocks_formed": len(blocks), "n_dropped": dropped,
            "n_surviving": len(means), "usable_counts": usable_counts,
            "means": np.asarray(means, float)}


def _block_summary(st: dict) -> dict:
    return {"n_blocks_formed": st["n_blocks_formed"], "n_dropped": st["n_dropped"],
            "n_surviving": st["n_surviving"], "usable_counts": st["usable_counts"],
            "block_means": [float(x) for x in st["means"]]}


def one_sample_t(x: np.ndarray) -> float:
    """§2.3 / §3.2: mean / (sd_ddof1 / sqrt(n)) — the ONE t formula, shared by the
    real series and the controls. Degenerate spreads are refused UPSTREAM by the
    §3.1(c') valve before this is ever evaluated on the real series."""
    x = np.asarray(x, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def t_bar(df: int) -> float:
    """§2.4: two-sided t_{0.975, df} read from Student-t (df-aware; no borrowed
    1.96). At df=58 this is 2.0017, the prereg's derived value."""
    return float(_student_t.ppf(FROZEN_V2["quantile"], df))


def run_controls(mu: float, sd: float, n: int, bar: float, *,
                 base_seed: int, n_reps: int) -> dict:
    """§3.2 FROZEN generator, exactly: rep r uses numpy.random.default_rng(
    base_seed + r) (PCG64), draws exactly n iid Normal(mu, sd) via
    rng.normal(mu, sd, n), computes the §2.3 one-sample t and applies the SAME
    comparison H1 uses (t >= bar). Rates AND per-rep clear/fail are published."""
    clears: list[bool] = []
    for r in range(n_reps):
        rng = np.random.default_rng(base_seed + r)
        draws = rng.normal(mu, sd, n)
        clears.append(bool(one_sample_t(draws) >= bar))
    n_clear = sum(clears)
    return {"mu": float(mu), "sd": float(sd), "n": int(n), "bar": float(bar),
            "base_seed": int(base_seed), "n_reps": int(n_reps),
            "n_clear": int(n_clear), "n_fail": int(n_reps - n_clear),
            "rate": n_clear / n_reps,
            "per_rep_clear": "".join("1" if c else "0" for c in clears)}


# ---- §4 decision map (pure function) ---------------------------------------------
def decide(mean_s: float, t_s: float, bar: float, placebo_mean_abs: float,
           t_delta: float, mean_f1: float, t_f1: float, mde: float) -> dict:
    """§4 EXACT comparisons: t_S >= bar and t_F1 >= bar are SIGNED (the prereg
    writes t >= bar, not |t|); only t_delta is two-sided (|t_delta| < bar)."""
    F = FROZEN_V2
    if mde > F["mde_ceiling"]:
        return {"verdict": "UNRESOLVED-POWER",
                "why": (f"realized MDE {mde:.4f} exceeds the frozen "
                        f"{F['mde_ceiling']} ceiling")}
    h1 = (mean_s >= F["h1_mean_min"]) and (t_s >= bar) \
        and (placebo_mean_abs < F["placebo_ceiling"])
    if not h1:
        return {"verdict": "KILL",
                "why": (f"H1 failed: mean IC {mean_s:.4f} (bar {F['h1_mean_min']}), "
                        f"t {t_s:.2f} (bar {bar:.4f}, signed), placebo "
                        f"{placebo_mean_abs:.4f} (bar {F['placebo_ceiling']})")}
    f1_clears = (mean_f1 >= F["h1_mean_min"]) and (t_f1 >= bar)
    if abs(t_delta) < bar and f1_clears:
        return {"verdict": "RETAIN-F1",
                "why": "composite adds nothing over F1 AND F1 independently clears"}
    return {"verdict": "RETAIN-S",
            "why": ("composite clears H1; family adds value or F1 does not "
                    "independently clear the bar")}


# ---- §3.1 ordering, end to end (pure: no filesystem writes) ----------------------
def run_inference(ic_s: np.ndarray, ic_f1: np.ndarray,
                  placebo_mean_abs: float) -> tuple[dict, int]:
    """§2–§4 in the frozen §3.1 ordering: (a) blocks formed, thin blocks dropped
    and counted; (b) surviving-block power gate — controls NOT run on refusal;
    (c)/(c') realized_block_sd (ddof=1) PUBLISHED, degenerate -> METHOD, controls
    NOT run; then the §2.5 rho_1 valve; (d) BOTH frozen controls, any violation ->
    METHOD, H1/H2 never evaluated; (e) only then the §4 map on the real series.
    Pure — execute() routes every returned terminal through _finish."""
    F = FROZEN_V2
    s = np.asarray(ic_s, float)
    f1 = np.asarray(ic_f1, float)
    bs = block_stats(s, F["h"], F["gap"], F["min_usable_per_block"])
    rep: dict = {"n_dates": int(len(s)), "blocks_S": _block_summary(bs),
                 "placebo_mean_abs": float(placebo_mean_abs)}

    # (b) power gate — BEFORE any control machinery is touched
    if bs["n_surviving"] < F["min_surviving_blocks"]:
        rep.update(status="UNRESOLVED-POWER",
                   why=(f"n_surviving {bs['n_surviving']} < frozen floor "
                        f"{F['min_surviving_blocks']} (§3.1(b)); controls NOT run"))
        return rep, EXIT_UNRESOLVED_POWER

    means = bs["means"]
    n = bs["n_surviving"]
    df = n - 1
    sd = float(np.std(means, ddof=1))
    rep["df"] = df
    rep["realized_block_sd"] = sd    # PUBLISHED even when degenerate (§3.1(c'))

    # (c)/(c') degenerate-scale valve — before rho_1, controls, and any t
    if (not np.isfinite(sd)) or sd <= 0.0:
        rep.update(status="UNRESOLVED-METHOD",
                   why=(f"realized_block_sd {sd} is degenerate (non-finite or "
                        "<= 0): the geometry produced no dispersion to test "
                        "against (§3.1(c')); controls and H1/H2 are NOT run"))
        return rep, EXIT_UNRESOLVED_METHOD

    # §2.5 adequacy valve on the machine itself
    rho1 = float(INF.sample_acf(means, 1)[0])
    rep["rho1_blocks"] = rho1
    if abs(rho1) >= F["rho1_ceiling"]:
        rep.update(status="UNRESOLVED-METHOD",
                   why=(f"|rho_1(block means)| {abs(rho1):.4f} >= frozen "
                        f"{F['rho1_ceiling']} (§2.5): the geometry failed to buy "
                        "independence; controls and H1/H2 are NOT run"))
        return rep, EXIT_UNRESOLVED_METHOD

    # (d) BOTH frozen controls, then the gate on both
    bar = t_bar(df)
    rep["bar"] = bar
    pos = run_controls(F["positive_mu"], sd, n, bar,
                       base_seed=F["base_seed"], n_reps=F["n_reps"])
    neg = run_controls(F["negative_mu"], sd, n, bar,
                       base_seed=F["base_seed"], n_reps=F["n_reps"])
    pos["ok"] = bool(pos["rate"] >= F["positive_rate_min"])
    neg["ok"] = bool(neg["rate"] <= F["negative_rate_max"])
    rep["controls"] = {"positive": pos, "negative": neg}
    if not (pos["ok"] and neg["ok"]):
        rep.update(status="UNRESOLVED-METHOD",
                   why=(f"control gate violation (§3.1(d)): positive rate "
                        f"{pos['rate']:.4f} (floor {F['positive_rate_min']}), "
                        f"negative rate {neg['rate']:.4f} (ceiling "
                        f"{F['negative_rate_max']}); H1/H2 never evaluated"))
        return rep, EXIT_UNRESOLVED_METHOD

    # (e) the real series through §4
    bf1 = block_stats(f1, F["h"], F["gap"], F["min_usable_per_block"])
    bd = block_stats(s - f1, F["h"], F["gap"], F["min_usable_per_block"])
    rep["blocks_F1"] = _block_summary(bf1)
    rep["blocks_delta"] = _block_summary(bd)
    t_s = one_sample_t(means)
    t_f1 = one_sample_t(bf1["means"]) if bf1["n_surviving"] > 1 else float("nan")
    t_d = one_sample_t(bd["means"]) if bd["n_surviving"] > 1 else float("nan")
    mean_s = float(means.mean())
    mean_f1 = float(bf1["means"].mean()) if bf1["n_surviving"] else float("nan")
    se_blocks = sd / np.sqrt(n)
    mde = float(bar * se_blocks)
    verdict = decide(mean_s, t_s, bar, float(placebo_mean_abs), t_d,
                     mean_f1, t_f1, mde)
    rep.update(status="COMPLETED", verdict=verdict,
               mean_ic_S_blocks=mean_s, t_S=float(t_s),
               mean_ic_F1_blocks=mean_f1, t_F1=float(t_f1), t_delta=float(t_d),
               se_blocks=float(se_blocks), mde=mde,
               mean_ic_S_dates=float(np.nanmean(s)),
               mean_ic_F1_dates=float(np.nanmean(f1)))
    return rep, 0


# ---- execution orchestration -----------------------------------------------------
def execute() -> int:
    code = _claim_execution()
    if code is not None:
        return code
    pre = verify_preconditions()
    if pre["unresolved_data"]:
        rep = {"status": "UNRESOLVED-DATA", "preflight": pre}
        print(json.dumps(rep, indent=2, sort_keys=True))
        _release_claim_unresolved(pre)
        return 3

    # Amendment-3 resolution, unchanged from v1: every read goes through the
    # verified snapshot root (preflight has already bound each file's sha to the
    # frozen pins; the live data/ paths are never touched). The loop restates only
    # ORCHESTRATION — assembly and IC are the imported v1 functions.
    tr_close = V1._load_tr_builder()
    root = V1._resolve_root(V1.load_snapshot_manifest())
    panel = pd.read_parquet(root / "panel.parquet",
                            columns=["ticker", "date", "fwd_20d_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    sector_of = {t: v.get("sector") for t, v in
                 json.loads((root / "ticker_sectors.json").read_text()).items()}
    tickers = sorted(panel["ticker"].unique())
    tr_returns: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    for t in tickers + ["SPY"]:
        raw = pd.read_parquet(root / f"ohlcv/{t}/1d.parquet")
        tr = tr_close(raw["close"],
                      raw.get("dividend", pd.Series(0.0, index=raw.index)))
        tr_returns[t] = tr.pct_change()
        volumes[t] = raw["volume"]
    spy_tr = tr_returns.pop("SPY")

    ic_s: list[float] = []
    ic_f1: list[float] = []
    dates_used: list[str] = []
    skipped = {"thin": 0, "infeasible": 0}
    rng_placebo = np.random.default_rng(FROZEN_V2["base_seed"])
    placebo_abs: list[float] = []
    for asof in sorted(panel["date"].unique()):
        day = panel[panel["date"] == asof]
        labels = day.set_index("ticker")["fwd_20d_excess"]
        out = V1.assemble_day(day, tr_returns, spy_tr, volumes, sector_of,
                              pd.Timestamp(asof))
        ic = V1._spearman_ic(out["scores"], labels)
        if ic is None:
            skipped["thin"] += 1
            continue
        ic1 = V1._spearman_ic(out.get("_f1", {}), labels)
        if ic1 is None:
            skipped["infeasible"] += 1
            continue
        # per-date placebo: 5 seeded within-date label permutations (v1 §4
        # discipline, seed 20260801), centring only
        pl = []
        for _ in range(FROZEN_V2["placebo_perms"]):
            perm = pd.Series(rng_placebo.permutation(labels.to_numpy()),
                             index=labels.index)
            p_ic = V1._spearman_ic(out["scores"], perm)
            if p_ic is not None:
                pl.append(abs(p_ic))
        placebo_abs.append(float(np.mean(pl)) if pl else np.nan)
        ic_s.append(ic)
        ic_f1.append(ic1)
        dates_used.append(str(pd.Timestamp(asof).date()))

    placebo_mean = float(np.nanmean(placebo_abs)) if placebo_abs else float("nan")
    rep, code = run_inference(np.asarray(ic_s), np.asarray(ic_f1), placebo_mean)
    rep["dates_skipped"] = skipped
    rep["date_range"] = ([dates_used[0], dates_used[-1]] if dates_used else None)
    rep["preflight"] = pre
    rep["prereg_v2_sha256"] = pre.get("v2_prereg_sha256_at_run")
    return _finish(rep, code)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preflight", action="store_true",
                    help="verify every precondition and print the JSON verdict")
    ap.add_argument("--execute", action="store_true",
                    help="single post-merge invocation; output committed verbatim")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args(argv)
    if a.execute:
        if a.json_out:
            print("--json-out is refused with --execute: the result destination "
                  f"is PREDECLARED ({RESULT_PATH}) so the outcome is never "
                  "caller-selectable (v1 design, codex on model#177)",
                  file=sys.stderr)
            return 2
        return execute()
    if not a.preflight:
        print("nothing to do: pass --preflight (this revision) or --execute "
              "(after model#191 merges).", file=sys.stderr)
        return 2
    rep = verify_preconditions()
    print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
