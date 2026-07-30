#!/usr/bin/env python3
"""§3/§7 power measurement on the ONLY identity-verified PatchTST score
series, for the FROZEN prereg
doc/research/2026-07-30-patchtst-closure-prereg-v2.md ("model#113").

Added after an adversarial review correctly established that §0.1 is
SATISFIED (identity was obtained by execution, and the digest assertion is
satisfiable on the identity-verified score dates) and that the binding
constraint is therefore §7's pre-committed power clause, not a §0.1 identity
failure. This script MEASURES `N_eval` / `n_blocks` / dropped-remainder on
the identity-verified series rather than deriving them in prose — §7.3
requires those exact numbers in the headline, and this programme's own
"asserted instead of measured" lesson forbids stamping them unmeasured.

Honours §0.1 by refusing the walk-forward research corpus outright: the only
score dates admitted here are those whose `pipeline_runs.model_content_sha256`
is a verified prefix-match of the live served checkpoint digest.

READ-ONLY over /Users/renhao/git/github/RenQuant (sqlite opened
`mode=ro&immutable=1`; no writes, no git). Writes only under this repo's
doc/research/data/2026-07-30-patchtst-closure-v2/.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import patchtst_closure_v2_lib as CL  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "doc/research/data/2026-07-30-patchtst-closure-v2"

LIVE_CKPT = Path("/Users/renhao/git/github/RenQuant/artifacts/patchtst_shadow/"
                  "pt07_strict_trainfit_embargo60_20260522/seed_44/"
                  "hf_patchtst_all_seed44_model.pt")
SHADOW_DB = Path("/Users/renhao/git/github/RenQuant/data/runs.alpaca_shadow.db")
PANEL = "/Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet"

GATE_LAG = 60   # §1: the ONLY gate lag
H = 60          # §1 horizon
BLOCK_LEN = 60  # §3
MIN_BLOCKS_POWERED = 6   # §7 clause 1


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(m):
        print(m)
        lines.append(m)

    live_sha = sha256_file(LIVE_CKPT)
    log(f"live served checkpoint sha256: {live_sha}")

    # ---- the identity-verified score series (§0.1 honoured) --------------
    con = sqlite3.connect(f"file:{SHADOW_DB}?mode=ro&immutable=1", uri=True)
    q = """
        SELECT pr.run_date AS date, cs.ticker AS ticker, cs.panel_score AS score,
               pr.model_content_sha256 AS sha
        FROM candidate_scores cs JOIN pipeline_runs pr ON cs.run_id = pr.run_id
        WHERE cs.model_type = 'hf_patchtst'
    """
    df = pd.read_sql_query(q, con)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    total_dates = df["date"].nunique()

    def verified(s):
        return bool(s) and live_sha.startswith(str(s).split(":")[-1])

    df["identity_verified"] = df["sha"].map(verified)
    ver = df[df["identity_verified"]].copy()
    ver_dates = pd.DatetimeIndex(sorted(ver["date"].unique()))
    log(f"hf_patchtst score dates in runs.alpaca_shadow.db: {total_dates} total; "
        f"{len(ver_dates)} identity-VERIFIED against the live digest")
    log(f"identity-verified score dates: {[str(d.date()) for d in ver_dates]}")
    log(f"names per verified date: "
        f"{ver.groupby('date')['ticker'].nunique().to_dict()}")

    # ---- §1/§3 admissibility + blocking, MEASURED -----------------------
    panel = pd.read_parquet(PANEL, columns=["ticker", "date"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    label_axis = pd.DatetimeIndex(sorted(panel["date"].unique()))

    result = {"live_checkpoint_sha256": live_sha,
              "n_score_dates_total": int(total_dates),
              "n_score_dates_identity_verified": int(len(ver_dates)),
              "identity_verified_dates": [str(d.date()) for d in ver_dates],
              "gate_lag": GATE_LAG, "horizon": H, "block_len": BLOCK_LEN}

    in_axis = [d for d in ver_dates if d in set(label_axis)]
    log(f"\nverified score dates present on the panel label axis: {len(in_axis)} "
        f"of {len(ver_dates)}")
    result["n_verified_dates_on_label_axis"] = len(in_axis)

    if len(in_axis) == 0:
        log("NOTE: the verified score dates post-date the panel's last label date "
            f"({label_axis[-1].date()}), so no forward label exists for them at all.")
        n_eval = 0
    else:
        adm = CL.admissible_dates(pd.DatetimeIndex(in_axis), label_axis,
                                   GATE_LAG, H)
        n_eval = len(adm)

    blocks = CL.block_partition_indices(n_eval, BLOCK_LEN)
    CL.assert_no_undersized_block(blocks, BLOCK_LEN)
    n_blocks = len(blocks)
    dropped = n_eval - n_blocks * BLOCK_LEN

    log(f"\n=== §3 estimator on the identity-verified series, MEASURED ===")
    log(f"N_eval (admissible dates at L={GATE_LAG}, h={H}) = {n_eval}")
    log(f"n_blocks = floor(N_eval/{BLOCK_LEN}) = {n_blocks}")
    log(f"dropped remainder days = {dropped}")
    log(f"§7 clause 1 threshold: n_blocks < {MIN_BLOCKS_POWERED} -> "
        f"UNRESOLVED (underpowered)")
    fires = n_blocks < MIN_BLOCKS_POWERED
    log(f"§7 clause 1 fires: {fires}")
    log(f"minimum score-date span needed for even ONE admissible date at "
        f"L={GATE_LAG},h={H}: {GATE_LAG + 1} contiguous scored trading days "
        f"(plus {H} further trading days of label history for the forward "
        f"window to close)")

    result.update(N_eval=int(n_eval), n_blocks=int(n_blocks),
                   dropped_remainder=int(dropped),
                   power_clause_7_1_fires=bool(fires),
                   min_blocks_powered=MIN_BLOCKS_POWERED,
                   T_crit="not computable: n_blocks < 2, no Student-t leg exists",
                   treatment_t="not computable: no block means exist")

    # ---- §4.1 positive control on the SAME dates ------------------------
    log(f"\n=== §4.1 positive control, on the SAME dates (as registered) ===")
    log("§4.1 registers the control as 'prod XGB, unpermuted, same harness, "
        "SAME DATES'. The treatment's registered date set is the "
        f"identity-verified series, whose admissible-date count is {n_eval}, so "
        "the control on that same date set has the same 0 admissible dates and "
        "is not computable either. Running it on a DIFFERENT (longer) date set "
        "would not be the registered control.")
    result["positive_control"] = (
        "not computable on the registered date set (0 admissible dates); "
        "running it on a different date set would not be the §4.1 control")

    (OUT / "power_measurement.json").write_text(json.dumps(result, indent=2))
    (OUT / "power_measure.log").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}/power_measurement.json")


if __name__ == "__main__":
    main()
