#!/usr/bin/env python3
"""Which of the three trainers produced this artifact? (twin-registry R3)

R3 records three trainers for one model — `RenQuant/scripts/train_production_model.py`,
`renquant-model/src/renquant_model_gbdt/panel_trainer.py`, and the pinned
`renquant-orchestrator/src/renquant_orchestrator/train_gbdt.py` — and says the last one is
what actually runs. Its cost line is the reason this exists: *"I pointed a delegated
retrain at the wrong twin TWICE before this was settled; its metadata came out
non-production-shaped (`nthread: 14`)."*

That was settled by reading two signatures by hand. This makes the same read mechanical, so
a third mis-pointing is caught by running something rather than by remembering.

THE TWO SIGNATURES, re-measured 2026-08-01 on the served
`prod/panel-ltr.alpha158_fund.json` `[本次实测]`:

  * **`training_notes`** is exactly `alpha158 + SEC fund panel-LTR, self-contained subrepo
    training` — the string literal at `train_gbdt.py:354`.
  * **`params` omits `nthread`** (8 keys: colsample_bytree, eta, max_depth,
    min_child_weight, objective, seed, subsample, verbosity). `train_gbdt.py` adds
    `nthread` ONLY when `--nthread` is passed (`:327`), whereas
    `train_production_model.py:58` hardcodes `"nthread": _XGB_NTHREAD` in the param dict
    itself — so its output cannot lack the key.

**R3 still holds.** And the registry's own citation has drifted: it cites
`train_gbdt.py:228` for the notes string, which is now at **:354**. A registry whose value
is that its citations are checkable should be corrected there — noted, not done here,
because the registry lives in `renquant-orchestrator`.

WHAT THIS IS NOT. Not a proof of authorship: two trainers could converge on the same
signature, and a signature is evidence about the SHAPE of the output, not a record of which
process ran. It reports `consistent_with` / `inconsistent_with` / `undecidable`, never
"produced by". `undecidable` is a real answer — an artifact matching several profiles, or
none, has not been attributed.

Read-only. Opens the artifact, writes nothing.

Exit codes: ``0`` exactly one profile is consistent, ``1`` zero or several are,
``2`` usage/IO error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: Signatures cited from source on 2026-08-01, not asserted from memory. `notes` is the
#: exact literal; `forbids_params` are keys whose PRESENCE rules the profile out;
#: `requires_params` are keys whose ABSENCE rules it out.
PROFILES = {
    "orchestrator/train_gbdt.py": {
        "notes": "alpha158 + SEC fund panel-LTR, self-contained subrepo training",
        "forbids_params": (),           # adds nthread only when --nthread is passed
        "requires_params": (),
        "cited": "train_gbdt.py:354 (notes), :327 (nthread is opt-in)",
    },
    "RenQuant/scripts/train_production_model.py": {
        "notes": None,                  # different/absent notes string
        "forbids_params": (),
        "requires_params": ("nthread",),  # hardcoded in the param dict at :58
        "cited": "train_production_model.py:58",
    },
}


def classify(artifact: dict) -> dict:
    notes = artifact.get("training_notes")
    params = artifact.get("params") or {}
    if not isinstance(params, dict):
        return {"verdict": "undecidable",
                "why": f"`params` is {type(params).__name__}, not an object"}

    consistent, ruled_out = [], {}
    for name, prof in PROFILES.items():
        reasons = []
        if prof["notes"] is not None and notes != prof["notes"]:
            reasons.append("training_notes does not match this trainer's literal")
        for k in prof["requires_params"]:
            if k not in params:
                reasons.append(f"params lack {k!r}, which this trainer always sets")
        for k in prof["forbids_params"]:
            if k in params:
                reasons.append(f"params carry {k!r}, which this trainer never sets")
        if reasons:
            ruled_out[name] = reasons
        else:
            consistent.append(name)

    if len(consistent) == 1:
        verdict = "consistent_with_exactly_one"
    elif not consistent:
        verdict = "undecidable"          # matches nothing — NOT "produced by none"
    else:
        verdict = "undecidable"          # matches several — a signature is not a proof
    return {
        "verdict": verdict,
        "consistent_with": consistent,
        "ruled_out": ruled_out,
        "training_notes": notes,
        "param_keys": sorted(params),
        "note": ("A signature is evidence about the SHAPE of the output, not a record of "
                 "which process ran. Two trainers could converge; this never reports "
                 "'produced by'."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", required=True, type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        art = json.loads(a.artifact.read_text())
    except (OSError, ValueError) as exc:
        print(f"producer-signature: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(art, dict):
        print("producer-signature: artifact top level is not an object", file=sys.stderr)
        return 2

    rep = classify(art)
    rep["artifact"] = str(a.artifact)
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        print(f"  {a.artifact.name}")
        print(f"    verdict: {rep['verdict']}")
        for c in rep["consistent_with"]:
            print(f"      consistent with  {c}   [{PROFILES[c]['cited']}]")
        for name, why in rep["ruled_out"].items():
            print(f"      ruled out        {name}")
            for w in why:
                print(f"          - {w}")
        print(f"\n  {rep['note']}")
    return 0 if rep["verdict"] == "consistent_with_exactly_one" else 1


if __name__ == "__main__":
    raise SystemExit(main())
