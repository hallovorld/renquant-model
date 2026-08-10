"""v2 machine-surface verifier (model#213 duty): recompute the gate
arithmetic from a result JSON and enforce every integrity field. Exit 1 on
any drift. Usage: python …-v2-verify.py <result.json>"""
import hashlib, json, sys
import numpy as np
import importlib.util
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "h", HERE / "2026-08-09-xgbmom-v2-harness.py")
h = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(h)          # imports xgb; only constants needed
except Exception:                        # noqa: BLE001 — fall back to parsing
    import re
    src = (HERE / "2026-08-09-xgbmom-v2-harness.py").read_text()
    FEATS = json.loads(re.search(r"FEATS = (\[.*?\])", src, re.S).group(1))
    CUTS = eval(re.search(r"CUTS = (\[.*?\])", src, re.S).group(1))  # noqa: S307 — literal list from the committed file
else:
    FEATS, CUTS = h.FEATS, h.CUTS

r = json.load(open(sys.argv[1]))
bad = []
if r.get("features_sha256") != hashlib.sha256(json.dumps(FEATS).encode()).hexdigest():
    bad.append("features_sha256")
if [tuple(x) for x in r.get("fold_table", [])] != [tuple(c) for c in CUTS]:
    bad.append("fold_table")
if r.get("admissible_verdict") is not None and not r.get("countersigned_by_review"):
    bad.append("admissible_verdict set WITHOUT countersignature")
if "purge_per_fold" not in r:
    bad.append("purge_per_fold missing")
rs = np.array(r["real_signal_per_fold"], dtype=float)
legs = [bool(np.nanmean(rs) > 0),
        bool(int(np.nansum(rs > 0)) >= 6),        # strict 6-of-the-fixed-8
        bool(r["aa_seed_std"] <= 0.01),
        bool(r["legs"][3])]                        # recency leg as recorded
if legs[:3] != r["legs"][:3]:
    bad.append(f"leg arithmetic {legs[:3]} vs {r['legs'][:3]}")
ga = "PASS" if all(r["legs"]) else "KILL"
if ga != r["gate_arithmetic"]:
    bad.append("gate_arithmetic")
if bad:
    print("DRIFT:", bad); sys.exit(1)
print(f"VERIFIED — machine surface enforced: gate arithmetic {ga}, "
      f"admissible_verdict={r.get('admissible_verdict')}, "
      f"purged per fold {[p['n_purged'] for p in r['purge_per_fold']]}")
