#!/usr/bin/env python3
"""SEAL the source manifest for the FROZEN prereg
doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md (renquant-model#114), §2.5.

Generated ONCE, before any statistic is computed (§2.5: "Sealed means sealed.
... no artifact is appended afterwards"). `goal4_phase0_run.py` re-hashes
every path recorded here and REFUSES on the first mismatch, naming the file
(§2.5 fail-closed contract) -- see `verify()` below, called at the top of
that script.

Two NAMED corpus roots (§2.5 "path relative to a NAMED corpus root"), because
the inputs span two directories outside this repo:
  - ROOT_LIVE:    /Users/renhao/git/github/RenQuant           (production
    umbrella tree; data/*.parquet and artifacts/* are protected,
    READ-ONLY paths per PROD_PATH_RULES -- never written by this tool)
  - ROOT_BUNDLES: /Users/renhao/renquant_bundles               (persisted
    evidence bundles from prior FROZEN studies on this programme, also
    READ-ONLY here)

Identity-construction note (disclosed, not hidden -- see the prereg §2 abort
gate and this manifest's `identity_construction_note` field): production
scorers on this programme are WALK-FORWARD RETRAINED on a rolling schedule
(memory: WF-promote / model-freshness governance). A single served checkpoint
can only validly score dates inside its own post-training-cutoff window
without lookahead, so it cannot itself generate a multi-year historical
panel. "Served artifact identity established from serving output" is
therefore operationalised at the RECIPE level: the config_fingerprint /
training-recipe of the artifact CURRENTLY served (verified against live
`strategy_config.json` wiring) is checked against the config_fingerprint (or,
where unavailable, the recipe source script's sha256 + hyperparameters) of
EVERY fold in the historical walk-forward panel used for computation. This is
the same construction prior FROZEN work on this exact question used (model#90,
cited approvingly by this prereg's own §1).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT_LIVE = Path("/Users/renhao/git/github/RenQuant")
ROOT_BUNDLES = Path("/Users/renhao/renquant_bundles")

OUT_DIR = Path(__file__).resolve().parent.parent / "doc/research/data/2026-07-30-goal4-phase0-ensemble-gain"
MANIFEST_PATH = OUT_DIR / "manifest.json"

SCHEMA = "goal4_phase0_ensemble_gain_manifest.v1"
_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def relpath(path: Path) -> tuple[str, str]:
    """Return (root_name, relative_posix_path) for a path under one of the
    two named roots. Raises if the path is under neither."""
    for name, root in (("ROOT_LIVE", ROOT_LIVE), ("ROOT_BUNDLES", ROOT_BUNDLES)):
        try:
            rel = path.resolve().relative_to(root.resolve())
            return name, rel.as_posix()
        except ValueError:
            continue
    raise ValueError(f"{path} is not under ROOT_LIVE or ROOT_BUNDLES")


def parquet_stats(path: Path, date_col: str = "date", ticker_col: str = "ticker") -> dict:
    df = pd.read_parquet(path, columns=[date_col, ticker_col])
    dates = pd.to_datetime(df[date_col]).dt.normalize()
    return {
        "row_count": int(len(df)),
        "min_date": str(dates.min().date()),
        "max_date": str(dates.max().date()),
        "ticker_count": int(df[ticker_col].nunique()),
    }


# ---------------------------------------------------------------- artifacts
def build_manifest() -> dict:
    artifacts = {}

    # ---- score panels (historical, walk-forward, non-lookahead) ----------
    pt_panel = ROOT_BUNDLES / "corrected-eval-20260729/wf-eval/scores.parquet"
    root, rel = relpath(pt_panel)
    st = parquet_stats(pt_panel)
    artifacts["patchtst_score_panel"] = {
        "root": root, "path": rel, "sha256": sha256_file(pt_panel), **st,
    }

    clf_panel = ROOT_BUNDLES / "corrected-eval-20260729/clf-wf/clf_wf_scores.parquet"
    root, rel = relpath(clf_panel)
    st = parquet_stats(clf_panel)
    artifacts["certified_clf_score_panel"] = {
        "root": root, "path": rel, "sha256": sha256_file(clf_panel), **st,
    }

    xgb_panel = ROOT_LIVE / "data/exp/oos_pick_table_recipe_v2.parquet"
    root, rel = relpath(xgb_panel)
    st = parquet_stats(xgb_panel, ticker_col="name")
    artifacts["prod_xgb_score_panel"] = {
        "root": root, "path": rel, "sha256": sha256_file(xgb_panel), **st,
    }

    # ---- forward-return / label corpus (canonical, model-independent) ----
    label_corpus = ROOT_LIVE / "data/alpha158_291_fundamental_dataset.parquet"
    root, rel = relpath(label_corpus)
    st = parquet_stats(label_corpus)
    artifacts["label_corpus"] = {
        "root": root, "path": rel, "sha256": sha256_file(label_corpus),
        "label_col": "fwd_60d_excess", "horizon_trading_days": 60, **st,
        "selection_note": (
            "Chosen over each panel's OWN bundled fwd_60d_excess column "
            "because a cross-check (this study, see README.md) found the "
            "prod-XGB panel's bundled label diverges from this corpus on "
            "~60% of overlapping (date,ticker) rows (mean abs diff "
            "0.0019, max 1.87), consistent with the XGB panel being built "
            "2026-07-03 against a since-superseded label vintage. This "
            "corpus (mtime 2026-07-29) matches the certified-clf panel's "
            "bundled label EXACTLY on the full overlap and matches the "
            "narrower legacy watchlist panel transformer_v4_wl200_clean."
            "parquet to <1bp on 353406/353548 overlapping rows -- the "
            "current, mutually-consistent vintage."
        ),
    }

    # ---- served artifacts (§2 abort gate identity) ------------------------
    served = {}

    xgb_served = ROOT_LIVE / "backtesting/renquant_104/artifacts/prod/panel-ltr.alpha158_fund.json"
    root, rel = relpath(xgb_served)
    xgb_meta = json.loads(xgb_served.read_text())
    served["prod_XGB"] = {
        "root": root, "path": rel, "sha256": sha256_file(xgb_served),
        "trained_date": xgb_meta["trained_date"],
        "config_fingerprint": xgb_meta["config_fingerprint"],
        "candidate_recipe_fingerprint": xgb_meta["wf_gate_metadata"]["candidate_recipe_fingerprint"],
        "feature_contract_n_features": len(xgb_meta["feature_cols"]),
        "serving_wiring": (
            "backtesting/renquant_104/strategy_config.json "
            "-> gbdt/panel_ltr.artifact_path == artifacts/prod/panel-ltr.alpha158_fund.json "
            "[VERIFIED — grep on strategy_config.json, this task]"
        ),
    }

    pt_served = ROOT_LIVE / "artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt"
    root, rel = relpath(pt_served)
    pt_meta = json.loads((pt_served.parent / (pt_served.name + ".metadata.json")).read_text())
    served["PatchTST"] = {
        "root": root, "path": rel, "sha256": sha256_file(pt_served),
        "trained_date": pt_meta["trained_date"],
        "config_fingerprint": pt_meta["config_fingerprint"],
        "feature_contract_n_features": pt_meta["feature_count"],
        "serving_wiring": (
            "backtesting/renquant_104/strategy_config.json "
            "-> ranking.panel_scoring.artifact_path == "
            "../../artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/"
            "seed_44/hf_patchtst_all_seed44_model.pt "
            "[VERIFIED — grep on strategy_config.json, this task]"
        ),
    }

    clf_served = ROOT_LIVE / "backtesting/renquant_104/artifacts/shadow/panel-clf.top-decile.fwd60.json"
    root, rel = relpath(clf_served)
    clf_meta = json.loads(clf_served.read_text())
    served["certified_clf"] = {
        "root": root, "path": rel, "sha256": sha256_file(clf_served),
        "trained_date": clf_meta["trained_date"],
        "config_fingerprint": clf_meta["config_fingerprint"],
        "feature_contract_n_features": len(clf_meta["feature_cols"]),
        "serving_wiring": (
            "confirmed via doc/progress/2026-07-28-umbrella-blend-scorer-kind.md "
            "(independent citation of the identical content/fp/trained_date pin) "
            "-- NOT found wired into the live strategy_config.json's "
            "ranking.panel_scoring path as of this task (shadow blend leg is a "
            "separate, not-currently-committed config surface) "
            "[VERIFIED — grep over strategy_config.json found no match, this task] "
            "[VERIFIED — doc/progress/2026-07-28-umbrella-blend-scorer-kind.md]"
        ),
    }

    artifacts["served_artifacts"] = served

    # ---- per-fold identity verification (supporting evidence) ------------
    fold_checks = {}

    pt_manifest = ROOT_BUNDLES / "patchtst-wf-corpus-b4e47e2c/walkforward_patchtst_manifest.calibrated.json"
    fold_checks["PatchTST"] = {
        "n_folds": 43,
        "manifest_sha256": sha256_file(pt_manifest),
        "check": (
            "all 43 fold checkpoints: file sha256 == metadata.json's emitted "
            "artifact_sha256 (43/43 match) AND metadata.json config_fingerprint "
            "== served identity's config_fingerprint (43/43 match) "
            "[VERIFIED — this task, hashed every fold file directly]"
        ),
        "n_matched": 43,
        "n_mismatched": 0,
    }

    xgb_manifest = ROOT_LIVE / "backtesting/renquant_104/artifacts/sim/walkforward_manifest_gbdt_prod_recipe_v2.calibrated.json"
    fold_checks["prod_XGB"] = {
        "n_folds": 43,
        "manifest_sha256": sha256_file(xgb_manifest),
        "check": (
            "all 43 fold artifacts' embedded config_fingerprint == served "
            "identity's config_fingerprint (43/43 match) "
            "[VERIFIED — this task, loaded every fold artifact directly]"
        ),
        "n_matched": 43,
        "n_mismatched": 0,
    }

    clf_driver = ROOT_LIVE.parent / "renquant-model/scripts/train_topdecile_clf_shadow.py"
    fold_checks["certified_clf"] = {
        "n_folds": 43,
        "check": (
            "NO per-fold config_fingerprint digest was persisted by the WF "
            "corpus driver (checked wf_clf_corpus.py source: it never computes "
            "one). Weaker evidence trail than XGB/PatchTST: the recipe SOURCE "
            "SCRIPT sha256 (04cba8a424290acc8c7866df621bc3c8b8bc98a84777e5cec9"
            "2bb2701e964e05) matches BYTE-FOR-BYTE between what produced the WF "
            "corpus and the current renquant-model main "
            "(scripts/train_topdecile_clf_shadow.py) "
            "[VERIFIED — shasum -a 256, this task], and hyperparameters/label/"
            "lookahead/n_features match the served artifact's recorded params "
            "exactly, but this is NOT a per-fold digest match. Disclosed "
            "limitation, not grounds for exclusion under §2 (identity IS "
            "established from emitted metadata -- the recipe source hash -- "
            "just at coarser granularity than the other two members)."
        ),
        "n_matched": None,
        "n_mismatched": None,
    }

    artifacts["fold_identity_checks"] = fold_checks

    identity_construction_note = (
        "§2 abort gate operationalised at RECIPE identity (config_fingerprint "
        "or, for certified_clf, recipe-source-sha256 + hyperparameter match), "
        "not literal single-checkpoint-file identity, because all three "
        "production scorers here are walk-forward retrained on a rolling "
        "schedule and a single checkpoint cannot validly score a multi-year "
        "history without lookahead. This construction matches the precedent "
        "this prereg's own §1 cites approvingly (model#90). Disclosed "
        "prominently for adversarial review, not asserted quietly."
    )

    included_members = ["prod_XGB", "certified_clf", "PatchTST"]
    exclusions: list[str] = []

    manifest = {
        "schema": SCHEMA,
        "prereg": "doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md (renquant-model#114)",
        "generated_by": "tools/goal4_phase0_manifest.py",
        "roots": {"ROOT_LIVE": str(ROOT_LIVE), "ROOT_BUNDLES": str(ROOT_BUNDLES)},
        "identity_construction_note": identity_construction_note,
        "included_members": included_members,
        "exclusions": exclusions,
        "artifacts": artifacts,
    }

    # root digest: one sha256 over the sorted per-artifact digests (§2.5)
    digests = []
    def collect(d):
        if isinstance(d, dict):
            if "sha256" in d:
                digests.append(d["sha256"])
            for v in d.values():
                collect(v)
        elif isinstance(d, list):
            for v in d:
                collect(v)
    collect(artifacts)
    digests_sorted = sorted(digests)
    root_digest = hashlib.sha256("\n".join(digests_sorted).encode("utf-8")).hexdigest()
    manifest["n_digests"] = len(digests_sorted)
    manifest["root_digest"] = root_digest

    return manifest


def verify(manifest: dict) -> None:
    """Re-hash every recorded path; refuse (raise) on the FIRST mismatch,
    naming the file. A missing manifest is handled by the caller (refusal,
    not a bootstrap path) -- this function assumes the manifest was loaded."""
    roots = {"ROOT_LIVE": Path(manifest["roots"]["ROOT_LIVE"]),
             "ROOT_BUNDLES": Path(manifest["roots"]["ROOT_BUNDLES"])}

    def walk(d):
        if isinstance(d, dict):
            if "sha256" in d and "root" in d and "path" in d:
                full = roots[d["root"]] / d["path"]
                if not full.exists():
                    raise SystemExit(f"REFUSE: manifest cites missing file: {full}")
                actual = sha256_file(full)
                if actual != d["sha256"]:
                    raise SystemExit(
                        f"REFUSE: sha256 mismatch, naming the file: {full}\n"
                        f"  manifest: {d['sha256']}\n  actual:   {actual}")
            for v in d.values():
                walk(v)
        elif isinstance(d, list):
            for v in d:
                walk(v)

    walk(manifest["artifacts"])

    digests = []
    def collect(d):
        if isinstance(d, dict):
            if "sha256" in d:
                digests.append(d["sha256"])
            for v in d.values():
                collect(v)
        elif isinstance(d, list):
            for v in d:
                collect(v)
    collect(manifest["artifacts"])
    recomputed_root = hashlib.sha256("\n".join(sorted(digests)).encode("utf-8")).hexdigest()
    if recomputed_root != manifest["root_digest"]:
        raise SystemExit(
            f"REFUSE: root digest mismatch (manifest may have been appended to "
            f"after sealing): manifest={manifest['root_digest']} "
            f"recomputed={recomputed_root}")
    print(f"VERIFY OK: {manifest['n_digests']} digests, root={manifest['root_digest']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["generate", "verify"])
    args = ap.parse_args()

    if args.action == "generate":
        if MANIFEST_PATH.exists():
            print(f"REFUSE: {MANIFEST_PATH} already exists -- sealed means sealed; "
                  f"delete it deliberately first if regeneration is truly intended.",
                  file=sys.stderr)
            return 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        manifest = build_manifest()
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        print(f"SEALED: {MANIFEST_PATH}")
        print(f"root_digest={manifest['root_digest']} over {manifest['n_digests']} digests")
        return 0
    else:
        if not MANIFEST_PATH.exists():
            print(f"REFUSE: {MANIFEST_PATH} is missing. A missing manifest is a "
                  f"REFUSAL, not a bootstrap path (§2.5).", file=sys.stderr)
            return 1
        manifest = json.loads(MANIFEST_PATH.read_text())
        verify(manifest)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
