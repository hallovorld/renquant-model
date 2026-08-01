#!/usr/bin/env python3
"""Persist GOAL-7 Stage 1's per-date series, then calibrate its bar ON THAT SERIES.

WHY THIS EXISTS. Reviewed three times `[codex on model#124, #128, #135]`, one demand each
time: the registered `t_{0.975,17} = 2.1098` bar is **not established** on 18 contiguous
60-day block means of a 120-day forward label, and the simulated size that priced it is
*conditional on an assumed* `rho1`, not measured on the real series. The remedy named in
the last review is explicit — *"a dependence-preserving, pre-registered null calibration
for the real pre-2021 series"*.

That calibration was not reconstructible, for one reason: **the frozen run persisted only
the 18 block means.** §7 of the redesign made persisting the per-date series a design
requirement precisely because of this. This tool discharges it retroactively.

WHAT MAKES THIS THE SAME RUN, AND NOT A NEW ONE. It does not re-decide anything. It
rebuilds the eval panel and the deterministic arms from the two **pinned** derived inputs,
and then **asserts every published arm statistic reproduces bit-identically against the
frozen `results.json`**. That assertion is the whole warrant: if any step of the
reconstruction diverged anywhere, `block_mean`, `block_sd` and `t` would not match to the
last representable digit. A reconstruction that reproduces is the frozen run's series; one
that does not is reported as a divergence and calibrates nothing.

THE UPSTREAM PIN NO LONGER VERIFIES, AND THAT IS A SEPARATE FACT `[本次实测]`. Re-running
`goal7_stage1_two_sided_run.py` today ABORTS: the raw OHLCV corpus fingerprint has moved
since 2026-07-30 (`48728e24…` → `0cee3698…`). The guard is right to refuse and is not
bypassed here. The two **derived** parquets this estimator actually reads are still
sha256-identical to their §2A pins, so the estimator's own inputs are unchanged while the
provenance chain above them is not. This tool therefore verifies what it reads and states
what it cannot vouch for, rather than treating a matching leaf as a verified chain.

WHAT THE CALIBRATION CAN AND CANNOT SETTLE. A circular block bootstrap of the DEMEANED
real series preserves that series' own dependence and imposes the null. Its answer depends
on the bootstrap block length `Lb`, which is a choice and not a measurement — so the output
is a **curve over Lb, not a number**. If the realised size does not stabilise as `Lb`
grows, the bar is **not identified**, which is a different and weaker statement than
"inflated by X". That distinction already cost this programme one withdrawn number
(GOAL-4's 0.1070), and it is enforced here rather than remembered.

Read-only on every corpus. Writes only under ``--out-dir``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import goal7_stage1_two_sided_run as G  # noqa: E402
from momentum_total_return_run import build_labels, per_date_z  # noqa: E402

#: Reconstructed here. The §5.1 positive control is a SEEDED SYNTHETIC arm; it is not the
#: object any critical value is applied to in anger, and rebuilding it would add a seeded
#: construction to a reproduction check whose entire value is determinism.
DETERMINISTIC_ARMS = ("treatment_u", "treatment_u_residualised", "reference_z_mom")

#: The statistics whose bit-identity proves the reconstruction IS the frozen run.
REPRO_FIELDS = ("mean_per_date", "block_mean", "block_sd", "t", "abs_t", "n_blocks")

#: Bootstrap block lengths swept. 1 is the iid baseline — NOT a candidate design, but the
#: reference the excess is measured against; 60 is the estimator's own block; 120 is the
#: label horizon; the tail probes whether the answer has stopped moving.
BOOTSTRAP_LB = (1, 5, 10, 20, 30, 60, 120, 180, 240)

SEED = 20260801
N_BOOT = 4000

#: A bootstrap resample built from fewer than this many independent block draws cannot
#: estimate a 95th percentile, in EITHER direction. Cells below the floor are reported
#: and excluded from every size claim rather than dropped silently -- a dropped cell is
#: indistinguishable from a cell that was never computed.
MIN_DRAWS = 20


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------- reconstruction --
def rebuild_arms(matrix: Path, tr_path: Path) -> tuple[G.Panel, dict, dict]:
    """Rebuild the eval panel and the deterministic arms, following `main()` step for
    step. Every constant is READ FROM THE RUN MODULE, never restated here — a restated
    `BLOCK = 60` would let this file and the frozen run drift apart silently, which is the
    exact failure the reproduction check exists to catch and would then be unable to."""
    m = pd.read_parquet(matrix)
    m["date"] = pd.to_datetime(m["date"])
    tr = pd.read_parquet(tr_path)
    tr["date"] = pd.to_datetime(tr["date"])

    w = {t_: g.set_index("date").sort_index()
         for t_, g in tr.groupby("ticker", observed=True)}
    spy = w["SPY"]
    rows = []
    for t_, d in w.items():
        c = d["tr_close"]
        b = spy["tr_close"].reindex(c.index).ffill()
        rows.append(pd.DataFrame({
            "date": d.index, "ticker": t_,
            "fwd_raw": ((c.shift(-G.H) / c - 1.0).to_numpy()
                        - (b.shift(-G.H) / b - 1.0).to_numpy())}))
    lab = pd.concat(rows, ignore_index=True)
    lab["fwd_z"] = per_date_z(lab["fwd_raw"], lab["date"])

    sib = build_labels(tr)[["date", "ticker", f"fwd_{G.H}_tr"]]
    chk = lab.merge(sib, on=["date", "ticker"], how="inner")
    both = chk["fwd_z"].notna() & chk[f"fwd_{G.H}_tr"].notna()
    dmax = float((chk.loc[both, "fwd_z"] - chk.loc[both, f"fwd_{G.H}_tr"]).abs().max())
    if not (both.sum() > 0 and dmax == 0.0):
        raise SystemExit(f"ABORT: label identity vs model#110 broken (max|diff|={dmax})")

    df = m[["date", "ticker", G.MOM_COL, G.VOL_COL]].merge(lab, on=["date", "ticker"],
                                                           how="inner")
    elig = df.dropna(subset=[G.MOM_COL, G.VOL_COL, "fwd_raw", "fwd_z"]).copy()
    cnt = elig.groupby("date").size()
    elig = elig[elig["date"].isin(cnt[cnt >= G.MIN_NAMES].index)]
    ev = elig[(elig["date"] >= G.EVAL_START) & (elig["date"] <= G.EVAL_END)].copy()

    p = G.Panel(ev)
    ev = p.df
    if p.n_dates != G.PIN_N_EVAL:
        raise SystemExit(f"ABORT: N_eval={p.n_dates} != pinned {G.PIN_N_EVAL}")
    n_blocks = p.n_dates // G.BLOCK
    if n_blocks != G.PIN_N_BLOCKS:
        raise SystemExit(f"ABORT: n_blocks={n_blocks} != pinned {G.PIN_N_BLOCKS}")

    mom = ev[G.MOM_COL].to_numpy(float)
    vol = ev[G.VOL_COL].to_numpy(float)
    labels = {"z": ev["fwd_z"].to_numpy(float), "raw": ev["fwd_raw"].to_numpy(float)}
    z_mom = p.gz(mom)
    u = np.abs(z_mom)
    u_resid = p.residualise(u, np.abs(p.gz(vol)))
    scores = {"treatment_u": u, "treatment_u_residualised": u_resid,
              "reference_z_mom": z_mom}

    series = {}
    for lb in (G.LABEL_PRIMARY, G.LABEL_SECONDARY):
        for nm in DETERMINISTIC_ARMS:
            series[(lb, nm)] = p.top_spread(scores[nm], labels[lb])
    return p, series, {"n_blocks": n_blocks}


def check_repro(series: dict, n_blocks: int, frozen: dict) -> dict:
    """Bit-identity against the frozen results.json. Not "close" — IDENTICAL."""
    out = {"fields": list(REPRO_FIELDS), "arms": {}, "all_identical": True,
           "n_compared": 0}
    for (lb, nm), g in series.items():
        st = G.block_t(g, n_blocks)
        want = frozen["arms"][lb][nm]
        diffs = {f: [want[f], st[f]] for f in REPRO_FIELDS if want[f] != st[f]}
        out["arms"][f"{lb}/{nm}"] = {"identical": not diffs, "divergent_fields": diffs}
        out["n_compared"] += 1
        if diffs:
            out["all_identical"] = False
    return out


# ------------------------------------------------------------------ calibration --
def n_blk_drawn(n: int, lb: int) -> int:
    """Independent block draws per resample at bootstrap block length `lb`."""
    return int(np.ceil(n / lb))


def block_t_stat(g: np.ndarray, n_blocks: int) -> float:
    bm = g[:n_blocks * G.BLOCK].reshape(n_blocks, G.BLOCK).mean(axis=1)
    sd = bm.std(ddof=1)
    return float("nan") if sd == 0 else float(bm.mean() / (sd / math.sqrt(n_blocks)))


def circular_block_bootstrap(e: np.ndarray, lb: int, n_boot: int,
                             rng: np.random.Generator) -> np.ndarray:
    """Resample the DEMEANED series in circular blocks of length `lb`.

    Circular, not truncated: a plain block bootstrap under-samples the first and last
    `lb - 1` observations, which biases the resampled variance downward — and a downward
    variance bias makes a bar look BETTER sized than it is, i.e. it errs in the direction
    that would flatter the design under review.
    """
    n = len(e)
    n_blk = int(np.ceil(n / lb))
    ext = np.concatenate([e, e[:lb]])
    starts = rng.integers(0, n, size=(n_boot, n_blk))
    idx = (starts[:, :, None] + np.arange(lb)[None, None, :]).reshape(n_boot, -1)[:, :n]
    return ext[idx % len(ext)]


def calibrate(g: np.ndarray, n_blocks: int, bar: float, rng: np.random.Generator) -> dict:
    """Realised two-sided size of `bar` under a dependence-preserving null, per `Lb`."""
    used = g[:n_blocks * G.BLOCK]
    e = used - used.mean()            # impose H0 while KEEPING the series' own dependence
    rows = {}
    for lb in BOOTSTRAP_LB:
        boot = circular_block_bootstrap(e, lb, N_BOOT, rng)
        bm = boot.reshape(N_BOOT, n_blocks, G.BLOCK).mean(axis=2)
        sd = bm.std(axis=1, ddof=1)
        t = np.where(sd == 0, np.nan, bm.mean(axis=1) / (sd / math.sqrt(n_blocks)))
        ok = np.isfinite(t)
        # THE NUMBER THAT EXPLAINS THE CURVE. A circular block bootstrap at length `Lb`
        # builds each resample from ceil(n / Lb) INDEPENDENT DRAWS. At Lb = 240 that is
        # FIVE. So the large-Lb end of this sweep is not "dependence preserved better" --
        # it is a bootstrap distribution estimated from a handful of draws, and its
        # apparent size is unusable in EITHER direction. Recording it is what stops the
        # low tail cell being quoted as "the bar is conservative after all".
        # A sweep in which EVERY resample is degenerate must report that, not raise:
        # `np.percentile` on an empty array throws, and a scheduled caller cannot tell a
        # thrown exception from a deliberate alarm. `None` is also not 0.0 — a size of
        # zero would read as "the bar never fires", which is the opposite of unknown.
        rows[lb] = {"realised_size": (float((np.abs(t[ok]) >= bar).mean())
                                      if ok.any() else None),
                    "n_usable": int(ok.sum()),
                    "n_degenerate": int((~ok).sum()),
                    "n_blocks_drawn_per_resample": n_blk_drawn(len(e), lb),
                    "usable_for_a_size_claim": bool(ok.any()
                                                    and n_blk_drawn(len(e), lb) >= MIN_DRAWS),
                    "p95_abs_t": (float(np.percentile(np.abs(t[ok]), 95))
                                  if ok.any() else None)}
    iid = rows[1]["realised_size"]
    usable = [lb for lb in BOOTSTRAP_LB if rows[lb]["usable_for_a_size_claim"]]
    vals = [rows[lb]["realised_size"] for lb in usable
            if rows[lb]["realised_size"] is not None]
    spread = (max(vals) - min(vals)) if vals else float("nan")
    # `Lb` must exceed the dependence length for the null to be preserved, AND leave
    # enough draws for the bootstrap to estimate a tail. On 1080 dates with a 120-day
    # label those two requirements do not overlap -- that non-overlap IS the finding.
    lb_needed = G.H
    return {"bar": bar, "n_boot": N_BOOT, "by_block_length": rows,
            "iid_baseline_size": iid,
            "usable_Lb": usable,
            "spread_over_usable_Lb": spread,
            "min_Lb_preserving_the_label_horizon": lb_needed,
            "draws_at_that_Lb": n_blk_drawn(len(e), lb_needed),
            "dependence_and_bootstrap_requirements_overlap":
                bool(n_blk_drawn(len(e), lb_needed) >= MIN_DRAWS),
            # The actionable half. Lb >= H to preserve the horizon AND ceil(n/Lb) >= 20 to
            # estimate a 5% tail together require n >= 20*H dates. This is arithmetic on
            # the two stated requirements, not an empirical finding -- so it says what a
            # design would need, and NOT that such a design would then pass.
            "dates_required_for_an_identifiable_bar": MIN_DRAWS * lb_needed,
            "dates_available": len(e),
            # The bar is IDENTIFIED only if the answer has stopped moving WHERE THE
            # BOOTSTRAP IS USABLE AT ALL. A curve still drifting there does not license
            # "inflated to X" -- it licenses "not identified", the weaker honest verdict.
            "identified": bool(vals and spread <= 0.01
                               and n_blk_drawn(len(e), lb_needed) >= MIN_DRAWS),
            "lag1_autocorr": float(np.corrcoef(e[:-1], e[1:])[0, 1])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", required=True, type=Path)
    ap.add_argument("--tr", required=True, type=Path)
    ap.add_argument("--frozen-results", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    a.out_dir.mkdir(parents=True, exist_ok=True)

    frozen = json.loads(a.frozen_results.read_text())
    R: dict = {"frozen_results": str(a.frozen_results),
               "derived_input_pins": {}, "upstream_provenance": {}}

    print("=" * 78)
    print("DERIVED INPUTS — the two files the estimator actually reads")
    print("=" * 78)
    for nm, path, pin in (("matrix", a.matrix, G.PIN_MATRIX), ("tr", a.tr, G.PIN_TR)):
        got = sha256(path)
        R["derived_input_pins"][nm] = {"sha256": got, "pin": pin, "match": got == pin}
        print(f"  {nm:<8}{got[:16]}…  {'PIN OK' if got == pin else '*** MISMATCH ***'}")
    if not all(v["match"] for v in R["derived_input_pins"].values()):
        print("\nABORT: a derived input no longer matches its §2A pin. Nothing is "
              "calibrated on inputs that are not the registered ones.")
        return 1

    # Stated, not silently omitted: what this run does NOT vouch for.
    R["upstream_provenance"] = {
        "raw_input_manifest_verifies": False,
        "note": ("`goal7_stage1_two_sided_run.py` ABORTS today because the raw OHLCV "
                 "corpus fingerprint moved since 2026-07-30. The guard is not bypassed "
                 "here; this tool never reads the raw corpus. The identity warrant is "
                 "the bit-identical reproduction below, NOT the upstream pin."),
    }

    print("\n" + "=" * 78)
    print("RECONSTRUCTION — and its only warrant: bit-identity with the frozen run")
    print("=" * 78)
    p, series, meta = rebuild_arms(a.matrix, a.tr)
    n_blocks = meta["n_blocks"]
    repro = check_repro(series, n_blocks, frozen)
    R["reproduction"] = repro
    for k, v in repro["arms"].items():
        print(f"  {k:<40}{'IDENTICAL' if v['identical'] else '*** DIVERGENT ***'}")
        for f, (want, got) in v["divergent_fields"].items():
            print(f"      {f}: frozen={want!r} rebuilt={got!r}")
    print(f"  {repro['n_compared']} arm statistics compared on "
          f"{len(REPRO_FIELDS)} fields each")
    if not repro["all_identical"]:
        print("\nSTOP: the reconstruction is not the frozen run. No series is written "
              "and nothing is calibrated — a series that cannot be shown to be THAT "
              "run's series would calibrate a bar nobody registered.")
        (a.out_dir / "calibration.json").write_text(json.dumps(R, indent=2, default=str))
        return 1

    # ------------------------------------------------------------ persist §7 --
    used_dates = [str(d.date()) for d in p.dates[:n_blocks * G.BLOCK]]
    lines = ["date,label,arm,g"]
    for (lb, nm), g in series.items():
        for d, v in zip(used_dates, g[:n_blocks * G.BLOCK]):
            # `repr(np.float64)` writes `np.float64(0.49…)` under NumPy 2, which is not
            # a number to any CSV reader -- the persisted series was unparseable by
            # `pd.read_csv(...).astype(float)` and had to be discovered by a crash.
            # `float(v)` gives full double precision without the wrapper; `repr` was only
            # ever there for precision, and it costs none.
            lines.append(f"{d},{lb},{nm},{float(v)!r}")
    (a.out_dir / "per_date_g_real.csv").write_text("\n".join(lines) + "\n")
    R["per_date_series"] = {
        "path": "per_date_g_real.csv", "n_series": len(series),
        "dates_per_series": n_blocks * G.BLOCK, "rows": len(lines) - 1,
        "first_date": used_dates[0], "last_date": used_dates[-1],
        "note": ("BLOCK-COVERED dates only: the §3 estimator drops the 2-date remainder, "
                 "so these are exactly the dates a calibration of THAT estimator may "
                 "use.")}
    print(f"\n  §7 per-date series persisted: {len(lines) - 1:,} rows "
          f"({len(series)} series × {n_blocks * G.BLOCK} dates)")

    # ------------------------------------------------------------- calibrate --
    print("\n" + "=" * 78)
    print(f"NULL CALIBRATION on the REAL series — bar = t_{{0.975,{n_blocks - 1}}} = "
          f"{G.PIN_T_STUDENT}, {N_BOOT:,} circular block bootstraps per Lb")
    print("=" * 78)
    rng = np.random.default_rng(SEED)
    R["calibration"] = {}
    print("  " + f"{'series':<40}" + "".join(f"{lb:>7}" for lb in BOOTSTRAP_LB)
          + f"{'rho1':>8}{'ident':>7}")
    print("  " + f"{'draws per resample ->':<40}"
          + "".join(f"{n_blk_drawn(n_blocks * G.BLOCK, lb):>7}" for lb in BOOTSTRAP_LB))
    for (lb_, nm), g in series.items():
        key = f"{lb_}/{nm}"
        cal = calibrate(g, n_blocks, G.PIN_T_STUDENT, rng)
        R["calibration"][key] = cal
        cells = "".join(
            (f"{cal['by_block_length'][b]['realised_size']:>7.3f}"
             if cal["by_block_length"][b]["realised_size"] is not None else f"{'n/a':>7}")
            for b in BOOTSTRAP_LB)
        print(f"  {key:<40}{cells}{cal['lag1_autocorr']:>8.3f}"
              f"{str(cal['identified']):>7}")
    any_cal = next(iter(R["calibration"].values()))
    print(f"\n  columns are bootstrap block length Lb; nominal size is 0.050; "
          f"Lb=1 is the iid baseline, not a candidate design.")
    print(f"  cells at fewer than {MIN_DRAWS} draws are NOT usable for a size claim in "
          f"either direction (usable Lb here: {any_cal['usable_Lb']}).")
    print(f"  preserving the {G.H}-day label horizon needs Lb >= {G.H}, which leaves "
          f"{any_cal['draws_at_that_Lb']} draws -> requirements overlap: "
          f"{any_cal['dependence_and_bootstrap_requirements_overlap']}")

    need = any_cal["dates_required_for_an_identifiable_bar"]
    print(f"  an identifiable bar would need >= {MIN_DRAWS} x {G.H} = {need:,} dates; "
          f"this window has {any_cal['dates_available']:,} "
          f"({need / any_cal['dates_available']:.2f}x short).")
    R["verdict"] = {
        "any_series_identified": any(c["identified"] for c in R["calibration"].values()),
        "dates_required_for_an_identifiable_bar": need,
        "dates_available": any_cal["dates_available"],
        "note": ("`identified` requires BOTH that the realised size has stopped moving "
                 "where the bootstrap is usable (spread <= 0.01) AND that an Lb "
                 "preserving the label horizon leaves >= 20 draws. A drifting or "
                 "unusable curve licenses 'not identified', never 'inflated to X'."),
    }
    (a.out_dir / "calibration.json").write_text(json.dumps(R, indent=2, default=str))
    print(f"\nwrote {a.out_dir / 'calibration.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
