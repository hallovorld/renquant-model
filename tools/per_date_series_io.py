"""Shared writer for the per-date statistic series a GOAL-7 run computes.

ONE definition, imported by every runner that needs it.

WHY IT IS SHARED RATHER THAN COPIED. `renquant-pipeline` maintains a registry of
twin implementations because copies agree on the day they are written and drift
silently afterwards. A duplicated writer in the lane whose entire purpose is
making a dependence assumption CHECKABLE would be that failure at its most
ironic — the artifact meant to let a later reader reproduce the calibration
would itself be two artifacts that disagree.

MEASURED 2026-07-31 across the momentum runners: `momentum_horizon_run.py`,
`momentum_family_screen.py` and `momentum_total_return_robustness.py` each
COMPUTE per-date quantities and persist NONE, while GOAL-4's
`goal4_phase0_run.py` persists its own. That asymmetry is exactly why the GOAL-4
screen could be given a model-free dependence calibration (bootstrap its real
508-row series, no rho1 assumed) and the GOAL-7 runs could not.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_per_date_series(series_by_name: "dict[str, pd.Series]",
                          out_path: "str | Path",
                          paired: "pd.Series | None" = None,
                          provenance: "dict | None" = None) -> dict:
    """Persist the per-date statistic series this run already computed.

    WHY (GOAL-7 redesign §7, 2026-07-31). This runner COMPUTES per-date E2 via
    ``per_date_e2`` and then throws it away, keeping only summary JSON plus 10
    block means. That single omission is why the programme's own dependence
    assumption cannot be checked against its own data:

      * GOAL-4's Phase-0 screen persisted ``per_date_g_real.csv`` (508 rows), and
        that one file made a model-free, assumption-free dependence-preserving
        calibration possible — bootstrap the real series, no rho1 assumed.
      * Here the only handle is 10 block means, whose lag-1 autocorrelation has a
        standard error of 1/sqrt(10) = 0.316 — it cannot separate rho1 = 0 from
        rho1 = +0.5, i.e. it is underpowered by an order of magnitude against the
        effect it would need to detect.

    Costs one CSV (~16 KB at GOAL-4's size). Computes NOTHING new: every value
    written here is already produced by the run, so this cannot move a verdict.
    """
    import json as _json
    import pandas as _pd
    frame = _pd.DataFrame({k: v for k, v in series_by_name.items() if v is not None})

    # THE PAIRED CONTRAST IS THE ARTIFACT. Writing only `subject` and `baseline`
    # leaves the reader to re-derive `subj.index.intersection(base).- .dropna()`
    # themselves, and a different reconstruction gives a different calibration --
    # which is the whole thing this file exists to make reproducible. So the exact
    # series handed to `agg` is persisted as its own column, and the components are
    # kept beside it so the contrast can be checked rather than trusted.
    if paired is not None:
        frame = frame.join(paired.rename("paired_contrast"), how="outer")
    frame = frame.sort_index()
    frame.index.name = "date"
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out)

    meta = {
        "path": str(out),
        "columns": list(frame.columns),
        "n_rows": int(len(frame)),
        "n_paired": int(paired.notna().sum()) if paired is not None else 0,
        "first_date": str(frame.index.min()) if len(frame) else None,
        "last_date": str(frame.index.max()) if len(frame) else None,
        # Enough to interpret the CSV WITHOUT this source file. A research artifact
        # whose columns can only be decoded by reading the runner is not independent.
        # Only when the column EXISTS. A sidecar that defines `paired_contrast`
        # for a file without that column documents an object that is not there,
        # and a reader who trusts it reconstructs a contrast the run never made.
        **({"paired_contrast_definition": (
            "paired_contrast = subject - baseline on the intersection of their date "
            "indexes, NaN dropped. This is the exact series passed to agg(); do not "
            "re-derive it from the component columns."
        )} if paired is not None else {}),
        **(provenance or {}),
    }
    side = out.with_suffix(".meta.json")
    side.write_text(_json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    meta["sidecar"] = str(side)
    return meta
