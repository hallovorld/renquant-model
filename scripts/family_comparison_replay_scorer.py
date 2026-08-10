"""Family-comparison fold-8 replay scorer -- the MODEL-SIDE half of the
family-comparison runner (relocation of renquant-orchestrator PR #953's
P0: model training internals belong in renquant-model).

This script is EXACTLY the training+scoring half of the orchestrator
runner (branch research/family-comparison-run,
doc/research/data/2026-08-10-family-comparison-runner.py), preserved
verbatim: harness constants ast-read (FEATS/CUTS/PARAMS/SEEDS/
CORPUS_SHA256), corpus sha assertion against the harness pin, fold-8
selection CUTS[7], per-row purge via the corpus's own 60-session
endpoint map, fillna(0) + train-stat z-normalization clipped to [-5, 5],
per-date rank:pairwise groups, 100 rounds, seeds (42, 43, 44), replay
score = mean of the three boosters' predictions.

It publishes a hash-pinned PREDICTION artifact only. Labels, live-run
data, joining, outcomes, bootstrap, and any verdict stay in the
orchestrator (design doc doc/design/2026-08-09-family-comparison-freeze.md,
orch#951): the output carries no labels and reads no runs DB.

Usage:
  python family_comparison_replay_scorer.py <harness.py> \
      <frozen_corpus.parquet> <ext_fund.parquet> <W0> <W1> <out_csv>

Outputs <out_csv> with columns date,ticker,replay_score for the window
rows [W0, W1], plus <out_csv>.manifest.json recording the sha256 of both
input parquets, the harness path + sha256, fold8_train_rows, the purged
count, the seeds, and the sha256 of the output CSV itself.
"""
import ast, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb

if len(sys.argv) != 7:
    sys.exit("usage: family_comparison_replay_scorer.py <harness.py> "
             "<frozen_corpus.parquet> <ext_fund.parquet> <W0> <W1> <out_csv>")
HARNESS, FROZEN, EXT, W0, W1, OUT = sys.argv[1:7]
OUT = Path(OUT)
LABEL60 = "fwd_60d_excess"
LABEL_SESSIONS = 60                        # harness constant (60d label)


def harness_constants():
    tree = ast.parse(Path(HARNESS).read_text())
    out = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in ("FEATS", "CUTS", "PARAMS", "SEEDS",
                                           "CORPUS_SHA256")):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    need = {"FEATS", "CUTS", "PARAMS", "SEEDS", "CORPUS_SHA256"}
    assert set(out) == need, f"harness constants missing: {need - set(out)}"
    return out


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


H = harness_constants()
FEATS, CUTS, PARAMS, SEEDS = H["FEATS"], H["CUTS"], H["PARAMS"], H["SEEDS"]
# doc s2 frozen identities, asserted (not assumed): the seed tuple and the
# fold-8 trait (train <= 2025-12-31, the last fold) named by the doc
assert tuple(SEEDS) == (42, 43, 44), f"seed tuple {SEEDS} != doc s2 (42,43,44)"
assert len(CUTS) == 8 and CUTS[7][1] == "2025-12-31", (
    f"CUTS[7] {CUTS[7]!r} is not fold-8 (train <= 2025-12-31)")
frozen_sha = file_sha256(FROZEN)
assert frozen_sha == H["CORPUS_SHA256"], (
    f"frozen corpus sha {frozen_sha[:12]} != harness pin")

# ── fold-8 training, the harness's own recipe (doc s2) ──────────────────
fz = pd.read_parquet(FROZEN, columns=["date", "ticker", LABEL60] + FEATS)
fz["date"] = fz["date"].astype(str).str[:10]
tr_s, tr_e, te_s, _ = CUTS[7]
tr = fz[(fz.date >= tr_s) & (fz.date <= tr_e)].dropna(subset=[LABEL60])
# per-row purge on the corpus's own calendar (harness _endpoint_map)
dates = sorted(fz.date.unique())
idx = {d: i for i, d in enumerate(dates)}
ep = {d: (dates[i + LABEL_SESSIONS] if i + LABEL_SESSIONS < len(dates) else None)
      for d, i in idx.items()}
n0 = len(tr)
tr = tr[tr.date.map(lambda d: ep.get(d) is not None and ep[d] < te_s)]
Xtr = tr[FEATS].fillna(0).values.astype(np.float64)
ytr = tr[LABEL60].clip(-5, 5).values.astype(np.float64)
mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-9
Xtr = ((Xtr - mu) / sd).clip(-5, 5)
si = np.argsort(tr["date"].values)
_, gsz = np.unique(tr["date"].values[si], return_counts=True)
dtr = xgb.DMatrix(Xtr[si], label=ytr[si]); dtr.set_group(gsz)
boosters = [xgb.train({**PARAMS, "seed": s}, dtr, num_boost_round=100)
            for s in SEEDS]
print(f"fold-8 trained: rows {len(tr)} (purged {n0 - len(tr)}), "
      f"seeds {SEEDS}", flush=True)

# ── extension window scoring (model-side only; no labels, no live data,
#    no joining -- those stay in the orchestrator) ───────────────────────
exp = pd.read_parquet(EXT, columns=["date", "ticker"] + FEATS)
exp["date"] = exp["date"].astype(str).str[:10]
exp = exp[(exp.date >= W0) & (exp.date <= W1)]
Xe = ((exp[FEATS].fillna(0).values.astype(np.float64) - mu) / sd).clip(-5, 5)
de = xgb.DMatrix(Xe)
exp = exp.assign(replay_score=np.mean([b.predict(de) for b in boosters], axis=0))

out_df = exp[["date", "ticker", "replay_score"]]
out_df.to_csv(OUT, index=False)

manifest = {
    "frozen_corpus_sha256": frozen_sha,
    "ext_parquet_sha256": file_sha256(EXT),
    "harness_path": HARNESS,
    "harness_sha256": file_sha256(HARNESS),
    "window": [W0, W1],
    "fold8_train_rows": int(len(tr)),
    "fold8_purged": int(n0 - len(tr)),
    "seeds": list(SEEDS),
    "n_rows": int(len(out_df)),
    "output_csv_sha256": file_sha256(OUT),
}
Path(str(OUT) + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
