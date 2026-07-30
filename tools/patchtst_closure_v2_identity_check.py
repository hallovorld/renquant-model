#!/usr/bin/env python3
"""§0.1 abort-gate evidence collection for the FROZEN prereg
doc/research/2026-07-30-patchtst-closure-prereg-v2.md ("model#113").

READ-ONLY over /Users/renhao/git/github/RenQuant (no writes, no git calls).
Writes only under doc/research/data/2026-07-30-patchtst-closure-v2/ (this
repo, this branch).

This script re-derives, in one place, exactly the facts the results doc
cites for the §0.1 VOID finding:

  1. The live shadow path's served PatchTST checkpoint identity, from
     execution-emitted metadata (shadow_scorer_health.jsonl) plus an
     independent re-hash of the resolved artifact file.
  2. Whether that digest appears ANYWHERE in the only span-adequate
     historical score corpus available (the 43-fold walk-forward research
     corpus backing doc/research/data's PatchTST scores in the prior
     model#90 corrected-eval line).
  3. Whether any GENUINELY execution-identity-linked historical score
     table (runs.alpaca_shadow.db) has enough span for the frozen §3
     estimator at L=60 (needs an admissible-date span on the order of
     120+ trading days).

Run once; outputs feed the sealed §0.2 bundle and are not modified after.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "doc/research/data/2026-07-30-patchtst-closure-v2"

LIVE_CKPT = Path("/Users/renhao/git/github/RenQuant/artifacts/patchtst_shadow/"
                  "pt07_strict_trainfit_embargo60_20260522/seed_44/"
                  "hf_patchtst_all_seed44_model.pt")
LIVE_SIDECAR = Path(str(LIVE_CKPT) + ".metadata.json")
HEALTH_JSONL = Path("/Users/renhao/git/github/RenQuant/backtesting/renquant_104/"
                     "logs/shadow_scorer_health.jsonl")
WF_CORPUS_ROOT = Path("/Users/renhao/renquant_bundles/patchtst-wf-corpus-b4e47e2c")
SHADOW_DB = Path("/Users/renhao/git/github/RenQuant/data/runs.alpaca_shadow.db")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log_lines = []

    def log(m):
        print(m)
        log_lines.append(m)

    # ---- 1. live checkpoint identity, established by execution -----------
    live_sha = sha256_file(LIVE_CKPT)
    sidecar = json.loads(LIVE_SIDECAR.read_text())
    health_records = []
    with open(HEALTH_JSONL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("kind") == "hf_patchtst":
                health_records.append(d)

    log(f"LIVE checkpoint path: {LIVE_CKPT}")
    log(f"LIVE checkpoint sha256 (full, computed here): {live_sha}")
    log(f"shadow_scorer_health.jsonl hf_patchtst records: {len(health_records)}")
    for r in health_records:
        log(f"  run_date={r['run_date']} content_sha256={r['content_sha256']} "
            f"config_fingerprint={r['config_fingerprint']} "
            f"staleness_days={r['staleness_days']} status={r['status']} "
            f"state={r['state']} reasons={r['reasons']}")
    truncated_prefixes = {r["content_sha256"] for r in health_records}
    log(f"distinct truncated content_sha256 values across all hf_patchtst "
        f"health records: {truncated_prefixes}")
    match = all(live_sha.startswith(p.split(":")[1]) for p in truncated_prefixes)
    log(f"full re-hash matches the (16-char-truncated) served digest in EVERY "
        f"health record: {match}")
    log(f"sidecar trained_date={sidecar.get('trained_date')} "
        f"effective_train_cutoff_date={sidecar.get('effective_train_cutoff_date')} "
        f"feature_count={sidecar.get('feature_count')} "
        f"config_fingerprint={sidecar.get('config_fingerprint')}")

    identity = dict(
        artifact_path=str(LIVE_CKPT),
        content_sha256_full=live_sha,
        content_sha256_truncated_from_health_jsonl=sorted(truncated_prefixes),
        trained_date=sidecar.get("trained_date"),
        effective_train_cutoff_date=sidecar.get("effective_train_cutoff_date"),
        feature_count=sidecar.get("feature_count"),
        config_fingerprint=sidecar.get("config_fingerprint"),
        n_health_records=len(health_records),
        health_record_run_dates=[r["run_date"] for r in health_records],
        staleness_days_last=health_records[-1]["staleness_days"] if health_records else None,
        status_last=health_records[-1]["status"] if health_records else None,
    )

    # ---- 2. does this digest appear in the 43-fold WF research corpus? ---
    scan_rows = []
    hit = False
    for ckpt in sorted(WF_CORPUS_ROOT.glob("*/hf_patchtst_all_seed44_model.pt")):
        fold_date = ckpt.parent.name
        sha = sha256_file(ckpt)
        is_match = (sha == live_sha)
        hit = hit or is_match
        scan_rows.append((fold_date, str(ckpt), sha, is_match))
    log(f"\n43-fold WF research corpus scan: {len(scan_rows)} checkpoints hashed "
        f"from {WF_CORPUS_ROOT}")
    log(f"any fold's checkpoint sha256 == live served sha256? {hit}")

    # ---- 3. genuinely identity-linked live score history: how long? ------
    con = sqlite3.connect(f"file:{SHADOW_DB}?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    cur.execute("""
        SELECT pr.run_date, pr.model_content_sha256, COUNT(*)
        FROM candidate_scores cs JOIN pipeline_runs pr ON cs.run_id = pr.run_id
        WHERE cs.model_type = 'hf_patchtst'
        GROUP BY pr.run_date, pr.model_content_sha256
        ORDER BY pr.run_date
    """)
    db_rows = cur.fetchall()
    verified_dates = [r[0] for r in db_rows
                      if r[1] and live_sha.startswith(r[1].split(":")[1])]
    log(f"\nruns.alpaca_shadow.db: hf_patchtst candidate_scores present on "
        f"{len(db_rows)} distinct (date, model_content_sha256) groups, span "
        f"{db_rows[0][0]}..{db_rows[-1][0]}" if db_rows else "no hf_patchtst rows at all")
    log(f"of those, dates where model_content_sha256 is a verified prefix-match "
        f"of the LIVE digest: {verified_dates}")
    log(f"n execution-identity-VERIFIED hf_patchtst score dates: {len(verified_dates)}")
    log("frozen §3 estimator at L=60,h=60 needs an admissible-date span of "
        "at least 120 consecutive trading days on ONE identity-verified score "
        "series before even n_blocks=1 exists; §7 expects roughly ~500 "
        "admissible dates (n_blocks~8) for a powered result.")

    # ---- write outputs -----------------------------------------------
    (OUT / "identity_evidence.json").write_text(json.dumps(identity, indent=2))
    with open(OUT / "checkpoint_sha256_scan.csv", "w") as f:
        f.write("fold_date,checkpoint_path,sha256,matches_live_digest\n")
        for row in scan_rows:
            f.write(f"{row[0]},{row[1]},{row[2]},{row[3]}\n")
    with open(OUT / "candidate_scores_identity_scan.csv", "w") as f:
        f.write("run_date,model_content_sha256,n_rows,verified_match_live\n")
        for r in db_rows:
            vm = bool(r[1] and live_sha.startswith(r[1].split(":")[1]))
            f.write(f"{r[0]},{r[1]},{r[2]},{vm}\n")
    with open(OUT / "shadow_scorer_health_hf_patchtst.jsonl", "w") as f:
        for r in health_records:
            f.write(json.dumps(r) + "\n")
    (OUT / "run.log").write_text("\n".join(log_lines) + "\n")
    print(f"\nwrote outputs to {OUT}")


if __name__ == "__main__":
    main()
