"""Backward depth-extension of the production gbdt walk-forward lineage
(GOAL-6 Job B, model#180; consumes the renquant-backtesting#94 identity model).

WHAT THIS BUILDS
----------------
The production WF manifest carries 43 per-cutoff retrains (2023-10-02 ..
2026-03-02). This driver extends that lineage BACKWARDS in time: same recipe,
same 60-business-day embargo, same cadence, new cutoffs strictly BEFORE the
earliest existing one, down to ``--target-earliest`` (default 2019-01-02).
Per new window it trains the prod recipe snapshot, persists an artifact whose
field set mirrors the existing window artifacts KEY-FOR-KEY (types included),
and finally writes an extension lineage manifest under the #94 append-only
rule: the extended lineage is a NEW ordered sha list (new windows in
chronological position BEFORE the existing 43) with a NEW
``lineage_root_sha``; both the old root (over the existing 43) and the new
root are recorded, and the old root stays recomputable from the suffix.

CADENCE CONVENTION — MEASURED FROM THE LADDER, NOT INVENTED
-----------------------------------------------------------
Measured on the live manifest (walkforward_manifest_gbdt_prod_recipe_v2
.calibrated.json, 43 retrains):
  * all 42 consecutive cutoff gaps are EXACTLY 21 CALENDAR days;
  * every cutoff is a Monday (weekday set == {0});
  * 2023-12-25 — Christmas, an NYSE holiday with no trading session — IS a
    ladder cutoff.
So the existing convention is a pure 21-calendar-day arithmetic grid with NO
NYSE-holiday adjustment; NYSE alignment happens downstream, where a window's
OOS range is the PANEL's trading dates in (cutoff, next_cutoff]. The backward
extension therefore continues the same arithmetic grid:
``new_cutoff_k = earliest_existing - k * 21 days`` (Mondays preserved by
construction, no holiday shifting), and leakage/embargo checks are made
against actual panel trading dates.

RECIPE + PARAMS SOURCE
----------------------
The recipe is imported LIVE from the committed training primitives the
daily/WF path uses (``renquant_model_gbdt``: ``load_panel`` cutoff contract
via ``LoadPanelTask``, ``build_normalization`` via ``BuildNormalizationTask``,
``panel_training_matrix``/``train_xgb`` via ``TrainBoosterTask``, artifact
assembly via ``BuildArtifactTask``). Params are taken from the EXISTING
window artifacts themselves (the earliest window's self-carried ``params``
— 8 keys incl. seed=42, no nthread — and ``best_iter`` as num_boost_round),
then cross-asserted equal to the committed package constants
(``panel_trainer.PANEL_LTR_PARAMS`` / ``DEFAULT_N_ROUNDS``); a divergence
refuses the run rather than guessing which source is right. The manifest's
own ``trainer`` field names ``renquant_orchestrator.train_gbdt`` with options
``{drop_sentiment: false, skip_cv: true}``; this driver mirrors that task
sequence exactly (LoadPanel -> sentiment gate -> BuildNormalization ->
TrainBooster -> BuildArtifact -> fingerprint -> smoke), including the
per-regime sentiment TRAINING gate, whose functions are imported read-only
from the umbrella's ``scripts/train_production_model.py`` (the same functions
``train_gbdt.SentimentGateTask`` bridges to).

CONFIG SOURCE (measured, 2026-08-02)
------------------------------------
The gate/fingerprint config is pinned to the strategy-104 SUBREPO config
(``renquant-strategy-104/configs/strategy_config.json``) — the same source
the June build passed via ``--strategy-config`` — because it reproduces the
existing artifacts' ``config_fingerprint`` (sha256:f8fb2259b2bf1537) and
``config_fingerprint_fields`` byte-exactly, while the umbrella copy has since
drifted (fingerprints sha256:14586756d4f67691 today). Every regime key the
replay tasks consume (hurst/cusum/vol/bear thresholds, gmm_artifact) was
measured EQUAL in both configs, and the effective sentiment policy from both
matches the artifact-carried policy; the tool still hard-asserts the produced
gate contract against the reference artifact's at run time.

SAFETY
------
READ-ONLY over /Users/renhao/git/github/RenQuant (sys.dont_write_bytecode is
set before any umbrella import so no __pycache__ is ever written there);
refuses any output root that resolves inside the umbrella. Every input is
digest-recorded at read time.

ATOMIC PREDECLARED RUN DIRECTORIES (tools/goal7_momentum_run.py pattern)
------------------------------------------------------------------------
Every writing invocation (--golden or the batch) runs inside its OWN
``run-<NNN>`` subdir of the durable ``--out-root`` (default
``~/renquant-data-store/goal6-jobb-gbdt-depth/``), claimed ATOMICALLY
(fresh mkdir + O_CREAT|O_EXCL ``RUN_CLAIM.json``) BEFORE any training or
output write, and sealed read-only (0444, claim included) at finish — so a
rerun can never overwrite the failed golden evidence or a completed corpus;
it must claim a NEW run id. An existing run dir — claimed, completed, or
crashed — is REFUSED. A claim left behind by a crash stays IN FORCE
(refuse-and-investigate beats silent rerun); removing a stale run dir is a
manual operator act that MUST leave its own durable record (a progress-doc
or memory entry naming what was removed and why).

MODES
-----
  --plan-only   compute + PRINT the backward ladder; no training, no writes;
  --golden      (requires --run-id) reproduce the EARLIEST EXISTING window
                (2023-10-02) from scratch and compare booster prediction
                parity on its OOS dates vs the committed artifact's booster
                (target max|delta| < 1e-6); the ONLY training this mode runs
                is that single fit. The report — pass or FAIL — is sealed in
                the claimed run dir (a failed report is the seam's evidence);
  (default)     (requires --run-id + --evidence-golden) full backward batch:
                train every new window, persist artifacts + the extension
                lineage manifest into the claimed run dir. REFUSES unless
                the golden evidence PASSED (mixed-vintage lineages must not
                acquire a root silently) OR the operator declares the seam
                explicitly (next flag);
  --accept-vintage-seam
                batch admission over a FAILED golden: the operator DECISION
                (2026-08-02) to extend on the current input vintage with the
                June-vs-Aug drift recorded first-class instead of silent.
                REQUIRES the FAILED golden report as the seam's measured
                evidence, BOUND to the pending batch: every lineage-relevant
                input digest the report recorded must equal the batch's
                freshly-computed digest (a stale or substituted report is
                refused with the diverging digest NAMED), and the exact
                evidence bytes are pinned into the seam block by content
                sha256 (``evidence_golden_report_sha256``). REFUSES if the
                golden PASSED (a passed golden means no seam exists — the
                flag would then document a lie). Writes a ``vintage_seam``
                block into the extension manifest and stamps every new
                window row ``input_vintage`` so no consumer can pool across
                the seam without seeing it.

GOLDEN VERDICT (measured 2026-08-02): parity FAILED, max|delta| = 0.649 over
4380 OOS rows / 15 dates. Localization (measured, not assumed): panel slice
shape, sentiment-gate mask (366713 zeroed rows), effective train cutoff and
config fingerprint all reproduce EXACTLY; the 158 global_z normalization
constants match today's stats file to 1.8e-9; the divergence is the 5 fund
columns' robust-z refit — data/sec_fundamentals_daily.parquet was rebuilt
2026-08-01 with revised historical values (gross_profitability median drift
7.13e-3 == the observed feature_means max delta; book_to_price scale drift
9.45e-3 == the feature_stds max delta). The June-vintage input bytes no
longer exist on disk, so the existing 43 windows cannot be byte-reproduced
from current inputs.

VINTAGE-SEAM DECISION (operator, 2026-08-02): DOCUMENT THE SEAM — do NOT
regenerate the 43-window ladder. The production lineage stamps bind the
ACTUAL artifacts in the WF manifest; regenerating them on the Aug vintage
would break that tie and create a third parallel corpus. The whole ladder is
already retrospective (built June-July 2026 for 2023-2026 cutoffs), so
extending on the current vintage with the seam recorded is methodologically
the same object — the seam makes the June-vs-Aug input drift first-class
instead of silent. ``--accept-vintage-seam`` implements exactly that and
nothing more; without it the golden-pass gate is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

# ── constants (paths are provenance anchors; RenQuant is READ-ONLY) ──────────
RQ = Path("/Users/renhao/git/github/RenQuant")
GITHUB = RQ.parent
DATA = RQ / "data"
STRATEGY_DIR = RQ / "backtesting" / "renquant_104"
WF_MANIFEST = (STRATEGY_DIR / "artifacts" / "sim" /
               "walkforward_manifest_gbdt_prod_recipe_v2.calibrated.json")
STRATEGY_CONFIG = GITHUB / "renquant-strategy-104" / "configs" / "strategy_config.json"
# Durable predeclared output root (NOT a session scratch path): every writing
# invocation claims its own run-<NNN> subdir atomically and seals it at finish,
# so a rerun can never overwrite the failed golden evidence or a completed
# corpus (same pattern as tools/goal7_momentum_run.py's execution claim).
DEFAULT_OUT_ROOT = Path.home() / "renquant-data-store" / "goal6-jobb-gbdt-depth"
DEFAULT_TARGET_EARLIEST = "2019-01-02"
SIDE_LABEL = "wf_depth_ext_jobb"
GOLDEN_PARITY_TARGET = 1e-6

#: recipe_match.py execution-only params (mirrored byte-exactly from
#: renquant-backtesting src/renquant_backtesting/wf_gate/recipe_match.py so the
#: recipe identity computed here equals the one the lineage lane stamps).
EXECUTION_ONLY_PARAM_KEYS: frozenset[str] = frozenset({
    "nthread", "n_jobs", "num_threads", "total_steps", "warmup_steps",
    "verbosity", "verbose", "silent", "epochs", "early_stopping_patience",
    "device",
})


# ── pure helpers (unit-tested; no heavy imports, no I/O beyond the arg) ──────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_ladder(cutoffs: list[str]) -> list[str]:
    """Structural ladder integrity — the same refusals as backtesting's
    ``lineage_lane.build_gbdt_lineage_view``: duplicates refuse, out-of-order
    refuses. Returns the (already-ordered) YYYY-MM-DD list."""
    cuts = [str(c)[:10] for c in cutoffs]
    if not cuts:
        raise ValueError("WF manifest has no retrains")
    if len(set(cuts)) != len(cuts):
        raise ValueError("WF manifest cutoff ladder has duplicates")
    if cuts != sorted(cuts):
        raise ValueError("WF manifest cutoff ladder is not chronologically ordered")
    return cuts


def derive_cadence_days(cutoffs: list[str]) -> int:
    """The ladder's own cadence in CALENDAR days; refuses a non-uniform grid
    (a mixed-cadence ladder has no single convention to extend)."""
    cuts = validate_ladder(cutoffs)
    if len(cuts) < 2:
        raise ValueError("need >= 2 cutoffs to derive a cadence")
    diffs = {(pd.Timestamp(b) - pd.Timestamp(a)).days for a, b in zip(cuts, cuts[1:])}
    if len(diffs) != 1:
        raise ValueError(f"ladder cadence is not uniform: gaps {sorted(diffs)} days")
    return diffs.pop()


def backward_extension(cutoffs: list[str], target_earliest: str) -> list[str]:
    """Continue the ladder's arithmetic grid backwards from its earliest
    cutoff down to ``target_earliest`` (inclusive). Chronological ascending
    order; every new cutoff is exactly ``k * cadence`` days before the
    earliest existing cutoff (grid-aligned by construction)."""
    cuts = validate_ladder(cutoffs)
    cadence = derive_cadence_days(cuts)
    earliest = pd.Timestamp(cuts[0])
    target = pd.Timestamp(target_earliest)
    if target >= earliest:
        raise ValueError(
            f"--target-earliest {target.date()} is not before the earliest "
            f"existing cutoff {earliest.date()}")
    out: list[str] = []
    k = 1
    while True:
        c = earliest - pd.Timedelta(days=cadence * k)
        if c < target:
            break
        out.append(str(c.date()))
        k += 1
    out.reverse()
    # invariants the tests pin: unique, ordered, grid-aligned, all before earliest
    assert len(set(out)) == len(out) and out == sorted(out)
    assert all((earliest - pd.Timestamp(c)).days % cadence == 0 for c in out)
    assert all(pd.Timestamp(c) < earliest for c in out)
    return out


def lineage_root(recipe_id: str, ordered_shas: list[str]) -> str:
    """The #94 identity rule, exactly (renquant-backtesting
    ``lineage_admissibility.lineage_root_sha``):
    sha256(recipe_id + LF + LF-joined ordered artifact shas + LF)."""
    payload = recipe_id + "\n" + "\n".join(ordered_shas) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_out_dir(raw: str | Path) -> Path:
    """Resolve the output dir and REFUSE anything inside the umbrella."""
    out = Path(raw).expanduser().resolve()
    rq = RQ.resolve()
    if out == rq or rq in out.parents:
        raise ValueError(
            f"--out-root {out} resolves inside the read-only umbrella {rq}; refusing")
    return out


# ── atomic predeclared run directories (tools/goal7_momentum_run.py pattern) ─
# Every writing invocation (--golden or the batch) runs inside its own
# ``run-<NNN>`` subdir of the durable out-root. The dir is claimed ATOMICALLY
# (mkdir with no exist_ok + O_CREAT|O_EXCL RUN_CLAIM.json) BEFORE any training
# or output write; completed outputs are sealed read-only (0444) at finish. A
# claim left behind by a crash stays IN FORCE: the next invocation refuses the
# run id (refuse-and-investigate beats silent rerun), and removing a stale
# claim/run dir is a manual operator act that MUST leave its own durable
# record (a progress-doc or memory entry naming what was removed and why).

def _utc_now() -> str:
    import datetime as _dt  # noqa: PLC0415
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def claim_run_dir(out_root: Path, run_id: str, mode: str) -> Path:
    """Atomically claim ``<out_root>/run-<run_id>``; refuse if it exists at all
    (claimed, completed, or crashed). This is the ONLY function that may create
    a run directory, and it runs BEFORE any training or output write."""
    run_dir = resolve_out_dir(Path(out_root) / f"run-{run_id}")
    if run_dir.exists():
        claim = run_dir / "RUN_CLAIM.json"
        state = "no claim file (unknown writer)"
        if claim.is_file():
            try:
                state = json.loads(claim.read_text()).get("status", "unreadable")
            except (OSError, json.JSONDecodeError):
                state = "unreadable claim"
        raise ValueError(
            f"run dir {run_dir} already exists (claim status: {state}) — "
            "refusing to overwrite a claimed/completed/crashed run; pick a new "
            "run id, or investigate. Manual removal of a stale run dir must "
            "leave a durable record.")
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir()  # atomic; races fail here with FileExistsError
    fd = os.open(run_dir / "RUN_CLAIM.json",
                 os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"claimed_at": _utc_now(), "pid": os.getpid(), "mode": mode,
                   "status": "in-progress"}, fh, indent=2)
    return run_dir


def assert_claimed(run_dir: Path) -> None:
    """Writers may only run inside an in-progress claimed run dir — this is the
    runtime tripwire behind 'no write happens before the claim'."""
    claim = Path(run_dir) / "RUN_CLAIM.json"
    if not claim.is_file():
        raise ValueError(
            f"run dir {run_dir} carries no RUN_CLAIM.json — outputs may only "
            "be written inside an atomically claimed run dir (claim_run_dir)")
    status = json.loads(claim.read_text()).get("status")
    if status != "in-progress":
        raise ValueError(
            f"run claim in {run_dir} has status {status!r} (not in-progress) — "
            "a completed run is sealed and never rewritten")


def seal_run(run_dir: Path, summary: dict) -> None:
    """Finish a claimed run: stamp the claim consumed, then seal EVERY file in
    the run dir read-only (0444) — golden reports, window artifacts, manifests
    and the claim itself. A sealed run can only be superseded by a NEW run id,
    never edited."""
    run_dir = Path(run_dir)
    claim_path = run_dir / "RUN_CLAIM.json"
    claim = json.loads(claim_path.read_text())
    claim.update(status="consumed", finished_at=_utc_now(), **summary)
    claim_path.write_text(json.dumps(claim, indent=2))
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            os.chmod(p, 0o444)


def require_golden_pass(report_path: Path) -> dict:
    """The batch gate: training the backward windows is only meaningful if the
    golden reproduction of the earliest EXISTING window passed prediction
    parity — otherwise the new windows are trained on a DIFFERENT input
    vintage than the lineage they claim to extend, and the extended root
    would certify a mixed-vintage lineage. Measured 2026-08-02: parity FAILED
    (max|delta|=0.649) because data/sec_fundamentals_daily.parquet was rebuilt
    on 2026-08-01 with revised historical values (fund robust-z drift up to
    9.45e-3), so this gate REFUSES the batch until parity passes or the
    vintage seam is declared explicitly (``--accept-vintage-seam``)."""
    report_path = Path(report_path)
    if not report_path.is_file():
        raise ValueError(
            f"no golden report at {report_path} — run --golden first; the "
            "batch refuses to train windows without a parity-verified recipe path")
    report = json.loads(report_path.read_text())
    if not report.get("parity_pass"):
        raise ValueError(
            "golden parity FAILED (max|delta|="
            f"{report.get('prediction_parity_max_abs_delta')}); refusing the "
            "batch — a backward extension trained on a different input vintage "
            "than the existing lineage would certify mixed-vintage evidence")
    return report


#: The declared input vintage of every NEW window trained under the seam —
#: the three lineage-relevant inputs were measured rebuilt on 2026-08-01
#: (mtimes recorded per file at read time in the seam block).
VINTAGE_SEAM_TAG = "2026-08-01-rebuild"

#: The operator decision + rationale, recorded verbatim in the seam block.
VINTAGE_SEAM_DECISION = (
    "DOCUMENT THE VINTAGE SEAM — do NOT regenerate the 43-window ladder")
VINTAGE_SEAM_RATIONALE = (
    "The production lineage stamps bind the ACTUAL artifacts in the WF "
    "manifest; regenerating them on the Aug vintage would break that tie and "
    "create a third parallel corpus. The whole ladder is already "
    "retrospective (built June-July 2026 for 2023-2026 cutoffs), so extending "
    "on the current vintage with the seam recorded is methodologically the "
    "same object — the seam makes the June-vs-Aug input drift first-class "
    "instead of silent. (Operator decision, 2026-08-02.)")


def resolve_vintage_seam(evidence_path: Path, accept_vintage_seam: bool,
                         current_input_digests: dict) -> tuple[dict, str] | None:
    """Batch admission. Two lawful states, nothing in between:

    * no flag  -> the golden at ``evidence_path`` must have PASSED
      (``require_golden_pass``);
    * the flag -> the golden must exist, have FAILED, and be BOUND to the
      pending batch: EVERY lineage-relevant input digest the report recorded
      (the ``*_sha256`` set golden mode writes) must equal the batch's
      freshly-computed digest for the same input. A stale report (inputs
      rebuilt since the golden ran) or a substituted report (recorded against
      different bytes) is refused with the diverging digest NAMED — a failed
      golden admits ONLY the vintage it actually measured.

    Returns ``(report, report_file_sha256)`` in seam mode (the sha binds the
    exact evidence bytes into the seam block), else None."""
    evidence_path = Path(evidence_path)
    if not accept_vintage_seam:
        require_golden_pass(evidence_path)
        return None
    if not evidence_path.is_file():
        raise ValueError(
            f"--accept-vintage-seam without a golden report at {evidence_path} "
            "— the seam's evidence IS the failed golden; run --golden first")
    raw = evidence_path.read_bytes()
    report_sha = hashlib.sha256(raw).hexdigest()
    report = json.loads(raw)
    if report.get("parity_pass"):
        raise ValueError(
            "--accept-vintage-seam over a PASSED golden (max|delta|="
            f"{report.get('prediction_parity_max_abs_delta')}) — a passed "
            "golden means no seam exists; the flag would document a seam that "
            "is not there. Refusing.")
    evidence_digests = report.get("input_digests") or {}
    ev_keys = {k for k in evidence_digests if k.endswith("_sha256")}
    cur_keys = {k for k in (current_input_digests or {}) if k.endswith("_sha256")}
    if not ev_keys:
        raise ValueError(
            "seam evidence unusable: the golden report carries no input "
            "digests — it cannot be bound to the pending batch's inputs")
    for k in sorted(ev_keys | cur_keys):
        if k not in ev_keys:
            raise ValueError(
                f"seam evidence unbound: the golden report lacks input digest "
                f"{k!r} that the pending batch recorded — refusing")
        if k not in cur_keys:
            raise ValueError(
                f"seam evidence unbound: the pending batch recorded no input "
                f"digest {k!r} that the golden report carries — refusing")
        if evidence_digests[k] != current_input_digests[k]:
            raise ValueError(
                f"seam evidence STALE: input digest {k!r} diverged between the "
                f"golden report ({str(evidence_digests[k])[:16]}…) and the "
                f"pending batch ({str(current_input_digests[k])[:16]}…) — the "
                "inputs changed since the golden ran; re-run --golden on the "
                "current vintage before declaring the seam")
    return report, report_sha


def build_vintage_seam(report: dict, rebuilt_inputs: list[dict],
                       evidence_path: str = "golden_report.json",
                       evidence_sha256: str | None = None) -> dict:
    """The ``vintage_seam`` manifest block: every number carried FROM the
    failed golden report (the measurement), never restated by hand; the exact
    evidence bytes bound by content sha256."""
    required = ("prediction_parity_max_abs_delta",
                "feature_means_max_abs_delta", "feature_stds_max_abs_delta")
    missing = [k for k in required if k not in report]
    if missing:
        raise ValueError(f"golden report lacks seam-evidence fields: {missing}")
    return {
        "input_vintage": VINTAGE_SEAM_TAG,
        "decision": VINTAGE_SEAM_DECISION,
        "decision_rationale": VINTAGE_SEAM_RATIONALE,
        "evidence_golden_report": str(evidence_path),
        "evidence_golden_report_sha256": evidence_sha256,
        "golden_parity_max_abs_delta": float(report["prediction_parity_max_abs_delta"]),
        "drift": {
            "feature_means_max_abs_delta": float(report["feature_means_max_abs_delta"]),
            "feature_means_max_abs_delta_column":
                "gross_profitability (fund robust-z median)",
            "feature_stds_max_abs_delta": float(report["feature_stds_max_abs_delta"]),
            "feature_stds_max_abs_delta_column":
                "book_to_price (fund robust-z scale, 1.4826*MAD)",
            "global_z_max_drift_vs_current_stats": 1.8e-9,
            "localization_note": (
                "slice shape, sentiment-gate mask, effective train cutoff and "
                "config fingerprint reproduce EXACTLY; the drift is confined "
                "to the 5 fund columns' robust-z refit (+1 alpha raw-clip "
                "bound). Measured 2026-08-02; see golden_report.json and "
                "doc/progress/2026-08-02-jobb-gbdt-depth-extension-tool.md."),
        },
        "rebuilt_inputs": list(rebuilt_inputs),
        "rebuild_date_measured": "2026-08-01",
        "non_reproducibility": (
            "The June-2026 vintage input bytes no longer exist on disk; the "
            "existing 43 windows are NOT byte-reproducible from current "
            "inputs."),
    }


def semantic_params(params: dict) -> dict:
    """recipe_match.py mirror: drop execution-only keys."""
    if not isinstance(params, dict):
        return {}
    return {k: v for k, v in params.items() if str(k) not in EXECUTION_ONLY_PARAM_KEYS}


def feature_source_contract_keys(artifact: dict) -> list[str]:
    contract = artifact.get("feature_source_contract")
    if not isinstance(contract, dict):
        return []
    return sorted(str(k) for k in contract.keys())


def recipe_projection(artifact: dict) -> dict:
    """recipe_match.py mirror: the model-recipe fields a WF manifest must match."""
    return {
        "kind": artifact.get("kind"),
        "feature_cols": list(artifact.get("feature_cols") or []),
        "feature_norm_kind": list(artifact.get("feature_norm_kind") or []),
        "feature_source_contract_keys": feature_source_contract_keys(artifact),
        "label_col": artifact.get("label_col"),
        "lookahead_days": int(artifact.get("lookahead_days") or 0),
        "params": semantic_params(artifact.get("params") or {}),
    }


def recipe_fingerprint(artifact: dict) -> str:
    """recipe_match.py mirror: sha256:<16-hex> over the recipe projection —
    the identity the lineage lane uses as ``recipe_id``."""
    payload = json.dumps(recipe_projection(artifact), sort_keys=True,
                         separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def check_artifact_field_parity(new: dict, ref: dict) -> list[str]:
    """Key-for-key + TYPE-for-type parity of a new window artifact against an
    existing one. Values legitimately differ per window; the KEY SET and each
    field's exact python type must not (the stringified-norm_kind incident:
    ``str(norm_kind)`` collapsed a 172-element list into one string and every
    digest check still passed). Returns a list of problems; empty == parity."""
    problems: list[str] = []
    missing = sorted(set(ref) - set(new))
    extra = sorted(set(new) - set(ref))
    if missing:
        problems.append(f"missing keys vs reference: {missing}")
    if extra:
        problems.append(f"extra keys vs reference: {extra}")
    for k in sorted(set(ref) & set(new)):
        if type(new[k]) is not type(ref[k]):  # noqa: E721 — exact type, bool!=int
            problems.append(
                f"type mismatch at {k!r}: {type(new[k]).__name__} != "
                f"{type(ref[k]).__name__}")
    # the incident guard, explicitly (never trust the generic loop alone)
    nk = new.get("feature_norm_kind")
    if not isinstance(nk, list) or isinstance(nk, str):
        problems.append(
            f"feature_norm_kind must be a list, got {type(nk).__name__}")
    elif "feature_cols" in new and isinstance(new["feature_cols"], list) \
            and len(nk) != len(new["feature_cols"]):
        problems.append(
            f"feature_norm_kind length {len(nk)} != feature_cols "
            f"{len(new['feature_cols'])}")
    # metadata sub-key parity (both carry dicts per the generic loop)
    if isinstance(new.get("metadata"), dict) and isinstance(ref.get("metadata"), dict):
        md_missing = sorted(set(ref["metadata"]) - set(new["metadata"]))
        md_extra = sorted(set(new["metadata"]) - set(ref["metadata"]))
        if md_missing:
            problems.append(f"metadata missing sub-keys: {md_missing}")
        if md_extra:
            problems.append(f"metadata extra sub-keys: {md_extra}")
    return problems


# ── heavy path (imports deferred; every umbrella import is read-only) ────────

def _bootstrap_heavy() -> None:
    """sys.path for the committed primitives + the umbrella gate functions.

    ``sys.dont_write_bytecode`` is set FIRST: importing umbrella modules must
    not write __pycache__ under the read-only RenQuant tree."""
    sys.dont_write_bytecode = True
    repo_src = Path(__file__).resolve().parent.parent / "src"
    pins = [repo_src,
            GITHUB / "renquant-common" / "src",
            GITHUB / "renquant-base-data" / "src",
            GITHUB / "renquant-artifacts" / "src"]
    for p in pins:
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    # umbrella LAST so pins win name clashes; needed ONLY for the sentiment
    # gate bridge (scripts.train_production_model + kernel + training_panel).
    for p in (STRATEGY_DIR, RQ):
        if str(p) not in sys.path:
            sys.path.append(str(p))


def _load_ref_artifact(manifest: dict) -> tuple[dict, Path, str]:
    """The earliest existing window's artifact (the parity/type reference),
    with the lineage_lane cross-check: self-carried cutoff == manifest cutoff."""
    row = manifest["retrains"][0]
    path = STRATEGY_DIR / str(row["artifact_uri"])
    if not path.is_file():
        raise FileNotFoundError(f"window artifact missing: {path}")
    sha = sha256_file(path)
    art = json.loads(path.read_text())
    art_cut = str(art.get("cutoff_date", ""))[:10]
    man_cut = str(row["cutoff_date"])[:10]
    if art_cut != man_cut:
        raise ValueError(
            f"artifact cutoff {art_cut!r} != manifest retrain cutoff {man_cut!r} "
            f"at {row['artifact_uri']} — wrong artifact behind this window")
    return art, path, sha


def _existing_window_rows(manifest: dict) -> list[dict]:
    """Digest + cross-check EVERY existing window (lineage_lane structural
    checks), returning manifest rows for the extension lineage."""
    rows = []
    for r in manifest["retrains"]:
        p = STRATEGY_DIR / str(r["artifact_uri"])
        if not p.is_file():
            raise FileNotFoundError(f"window artifact missing: {p}")
        art = json.loads(p.read_text())
        man_cut = str(r["cutoff_date"])[:10]
        art_cut = str(art.get("cutoff_date", ""))[:10]
        if art_cut != man_cut:
            raise ValueError(
                f"artifact cutoff {art_cut!r} != manifest cutoff {man_cut!r} "
                f"at {r['artifact_uri']}")
        rows.append({
            "cutoff_date": man_cut,
            "artifact_path": str(p),
            "artifact_sha256": sha256_file(p),
            "effective_train_cutoff_date":
                str(art.get("effective_train_cutoff_date", ""))[:10],
            "cutoff_embargo_days": int(art.get("cutoff_embargo_days", -1)),
            "provenance": "existing_prod_wf_manifest",
        })
    return rows


def _production_fingerprint(label: str, feat_cols: list[str]) -> tuple[str, dict, dict]:
    """The production config fingerprint from the strategy-104 subrepo config
    (measured to reproduce the existing artifacts' stamp byte-exactly)."""
    from renquant_common.config_consistency import (  # noqa: PLC0415
        _model_relevant_fields, fingerprint_config)
    from scripts.train_production_model import build_fingerprint_config  # noqa: PLC0415
    cfg = build_fingerprint_config(
        fingerprint_config_path=str(STRATEGY_CONFIG), watchlist_file=None,
        label_used=label, feat_cols=feat_cols)
    return fingerprint_config(cfg), _model_relevant_fields(cfg), cfg


def _train_window(cutoff: pd.Timestamp, *, ref: dict, first_oos: pd.Timestamp,
                  golden: bool = False) -> tuple[dict, dict]:
    """Train ONE per-window snapshot exactly the way the existing windows were
    trained (manifest trainer = renquant_orchestrator.train_gbdt with
    skip_cv + the sentiment training gate); returns (artifact, timings)."""
    from renquant_model_gbdt.panel_data import (  # noqa: PLC0415
        AttachSmokeTask, BuildNormalizationTask, LoadPanelTask,
        StampFingerprintTask)
    from renquant_model_gbdt.panel_trainer import (  # noqa: PLC0415
        DEFAULT_N_ROUNDS, PANEL_LTR_PARAMS)
    from renquant_model_gbdt.pipeline import (  # noqa: PLC0415
        BuildArtifactTask, GbdtTrainingContext, TrainBoosterTask)
    from scripts.train_production_model import (  # noqa: PLC0415
        apply_sentiment_training_gate, build_sentiment_training_regime_map)

    # params: ARTIFACT-CARRIED, cross-asserted against the committed constants.
    params = dict(ref["params"])
    n_rounds = int(ref["best_iter"])
    if params != dict(PANEL_LTR_PARAMS):
        raise AssertionError(
            f"artifact-carried params {params} != committed PANEL_LTR_PARAMS "
            f"{PANEL_LTR_PARAMS}; refusing to guess which recipe is right")
    if n_rounds != int(DEFAULT_N_ROUNDS):
        raise AssertionError(
            f"artifact-carried best_iter {n_rounds} != DEFAULT_N_ROUNDS "
            f"{DEFAULT_N_ROUNDS}")

    t = {"t_start": time.time()}
    ctx = GbdtTrainingContext(
        label=str(ref["label_col"]), params=params, num_boost_round=n_rounds,
        skip_cv=True, data_dir=str(DATA), cutoff_date=pd.Timestamp(cutoff),
        side_label=("wf_depth_ext_golden" if golden else SIDE_LABEL),
        output_path=None, train_run_id=str(uuid.uuid4())[:8],
        training_notes=str(ref["training_notes"]),
    )
    LoadPanelTask().run(ctx)
    t["load_panel_s"] = round(time.time() - t["t_start"], 1)
    if list(ctx.feat_cols) != list(ref["feature_cols"]):
        raise AssertionError(
            "panel feature columns diverge from the reference recipe "
            f"(n={len(ctx.feat_cols)} vs {len(ref['feature_cols'])}); the "
            "recipe is frozen — refusing")

    # sentiment TRAINING gate (mirrors train_gbdt.SentimentGateTask; config
    # pinned to the strategy-104 subrepo copy — see module docstring).
    fp, fp_fields, fp_cfg = _production_fingerprint(ctx.label, ctx.feat_cols)
    ctx.config_fingerprint, ctx.config_fingerprint_fields = fp, fp_fields
    t0 = time.time()
    regime_map = build_sentiment_training_regime_map(ctx.train["date"].unique(), fp_cfg)
    ctx.train, contract = apply_sentiment_training_gate(
        ctx.train, ctx.feat_cols, fp_cfg, regime_map)
    t["regime_gate_s"] = round(time.time() - t0, 1)
    if not contract:
        raise AssertionError(
            "sentiment training gate reported not-required, but every existing "
            "window artifact carries an active gate contract — recipe divergence")
    for k in ("sentiment_runtime_gate_feature_cols",
              "sentiment_runtime_gate_disabled_regimes",
              "sentiment_runtime_gate_policy"):
        if contract[k] != ref[k]:
            raise AssertionError(
                f"gate contract field {k} diverges from the reference window: "
                f"{contract[k]} != {ref[k]} — training would not be the frozen "
                "recipe; refusing")
    ctx.extra_artifact_fields.update(contract)

    BuildNormalizationTask().run(ctx)
    t0 = time.time()
    TrainBoosterTask().run(ctx)
    t["fit_s"] = round(time.time() - t0, 1)
    BuildArtifactTask().run(ctx)
    StampFingerprintTask().run(ctx)
    AttachSmokeTask().run(ctx)
    # umbrella stamp_fingerprint()'s provenance record (the reference windows
    # carry it; StampFingerprintTask does not write it).
    ctx.artifact.setdefault("metadata", {})["config_fingerprint_source"] = {
        "fingerprint_config_path": str(STRATEGY_CONFIG),
        "watchlist_file": None,
        "label_used": ctx.label,
        "feature_count": len(ctx.feat_cols),
    }

    # ── contracts, hard (a violation refuses the window, never warns) ──
    art = ctx.artifact
    rid_new, rid_ref = recipe_fingerprint(art), recipe_fingerprint(ref)
    if rid_new != rid_ref:
        raise AssertionError(
            f"recipe fingerprint diverged: new {rid_new} != existing {rid_ref}")
    problems = check_artifact_field_parity(art, ref)
    if problems:
        raise AssertionError(f"artifact field parity vs reference failed: {problems}")
    # leakage/embargo (#94 check_window form, vs the CALLER's grid):
    # nominal effective cutoff + embargo BDays < first OOS trading date; the
    # honest post-dropna max training date only ever tightens this.
    etc = pd.Timestamp(str(art["effective_train_cutoff_date"]))
    embargo = int(art["cutoff_embargo_days"])
    safe_after = etc + pd.offsets.BDay(embargo)
    if not safe_after < first_oos:
        raise AssertionError(
            f"LEAKAGE cutoff={pd.Timestamp(cutoff).date()}: nominal effective "
            f"train cutoff {etc.date()} + {embargo} BDay = {safe_after.date()} "
            f">= first OOS date {first_oos.date()}")
    honest = pd.Timestamp(ctx.train["date"].max())
    if not honest + pd.offsets.BDay(embargo) < first_oos:
        raise AssertionError(
            f"LEAKAGE cutoff={pd.Timestamp(cutoff).date()}: honest train max "
            f"{honest.date()} + {embargo} BDay >= first OOS {first_oos.date()}")
    t["leakage_margin_bdays"] = int(len(pd.bdate_range(safe_after, first_oos)) - 1)
    t["honest_train_max_date"] = str(honest.date())
    t["n_train_rows"] = int(len(ctx.train))
    t["n_train_dates"] = int(ctx.train["date"].nunique())
    t["zeroed_rows"] = int(contract["sentiment_runtime_gate_zeroed_rows"])
    t["total_s"] = round(time.time() - t["t_start"], 1)
    del t["t_start"]
    return art, t


def _panel_dates() -> np.ndarray:
    """All panel trading dates (read-only; date column only)."""
    dates = pd.read_parquet(DATA / "alpha158_291_fundamental_dataset.parquet",
                            columns=["date"])["date"]
    return np.sort(pd.to_datetime(dates).unique())


def _first_oos_after(all_dates: np.ndarray, cutoff: pd.Timestamp) -> pd.Timestamp:
    after = all_dates[all_dates > np.datetime64(pd.Timestamp(cutoff))]
    if len(after) == 0:
        raise ValueError(f"no panel trading date after cutoff {cutoff}")
    return pd.Timestamp(after[0])


def _score_with_artifact(art: dict, frame: pd.DataFrame) -> np.ndarray:
    """Score rows using ONLY an artifact's self-carried contract."""
    import xgboost as xgb  # noqa: PLC0415
    from renquant_model_gbdt.panel_trainer import panel_training_matrix  # noqa: PLC0415
    feat_cols = list(art["feature_cols"])
    mu = np.asarray(art["feature_means"], dtype=float)
    sd = np.asarray(art["feature_stds"], dtype=float)
    booster = xgb.Booster()
    booster.load_model(bytearray(art["booster_raw_json"].encode("utf-8")))
    X = panel_training_matrix(frame, feat_cols, mu, sd, list(art["feature_norm_kind"]))
    return booster.predict(xgb.DMatrix(X.values.astype(np.float64)))


def run_golden(out_dir: Path, manifest: dict, input_digests: dict) -> int:
    """Reproduce the EARLIEST EXISTING window from scratch; compare booster
    prediction parity on that window's OOS dates vs the committed artifact.
    Runs ONLY inside an atomically claimed run dir; the report — pass or fail
    (a failed report is the seam's evidence) — is sealed read-only at finish."""
    assert_claimed(out_dir)
    ref, ref_path, ref_sha = _load_ref_artifact(manifest)
    cuts = validate_ladder([r["cutoff_date"] for r in manifest["retrains"]])
    cut, nxt = pd.Timestamp(cuts[0]), pd.Timestamp(cuts[1])
    all_dates = _panel_dates()
    first_oos = _first_oos_after(all_dates, cut)

    art, timings = _train_window(cut, ref=ref, first_oos=first_oos, golden=True)

    # OOS window = the ladder rule the corpus builders use: (cut, next_cut].
    window = [d for d in all_dates if cut < pd.Timestamp(d) <= nxt]
    panel = pd.read_parquet(DATA / "alpha158_291_fundamental_dataset.parquet")
    panel["date"] = pd.to_datetime(panel["date"])
    oos = panel[panel["date"].isin(set(window))]

    pred_ref = _score_with_artifact(ref, oos)
    pred_new = _score_with_artifact(art, oos)
    max_delta = float(np.max(np.abs(pred_ref - pred_new))) if len(oos) else float("nan")

    mu_delta = float(np.max(np.abs(
        np.asarray(art["feature_means"], dtype=float)
        - np.asarray(ref["feature_means"], dtype=float))))
    sd_delta = float(np.max(np.abs(
        np.asarray(art["feature_stds"], dtype=float)
        - np.asarray(ref["feature_stds"], dtype=float))))
    report = {
        "mode": "golden",
        "reproduced_cutoff": str(cut.date()),
        "reference_artifact": str(ref_path),
        "reference_artifact_sha256": ref_sha,
        "oos_window": [str(pd.Timestamp(window[0]).date()),
                       str(pd.Timestamp(window[-1]).date())],
        "n_oos_rows": int(len(oos)),
        "n_oos_dates": int(len(window)),
        "prediction_parity_max_abs_delta": max_delta,
        "parity_target": GOLDEN_PARITY_TARGET,
        "parity_pass": bool(max_delta < GOLDEN_PARITY_TARGET),
        "booster_bytes_identical": bool(
            art["booster_raw_json"] == ref["booster_raw_json"]),
        "feature_means_max_abs_delta": mu_delta,
        "feature_stds_max_abs_delta": sd_delta,
        "effective_train_cutoff_match": bool(
            art["effective_train_cutoff_date"] == ref["effective_train_cutoff_date"]),
        "config_fingerprint_match": bool(
            art["config_fingerprint"] == ref["config_fingerprint"]),
        "sentiment_zeroed_rows": {
            "new": int(art["sentiment_runtime_gate_zeroed_rows"]),
            "ref": int(ref["sentiment_runtime_gate_zeroed_rows"])},
        "panel_shape": {"new": art["panel_shape"], "ref": ref["panel_shape"]},
        "timings": timings,
        "input_digests": input_digests,
    }
    report_path = out_dir / "golden_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    seal_run(out_dir, {"outcome": "golden",
                       "parity_pass": report["parity_pass"],
                       "golden_report_sha256": sha256_file(report_path)})
    print(json.dumps(report, indent=2), flush=True)
    if not report["parity_pass"]:
        print(f"[GOLDEN FAIL] max|delta|={max_delta} >= {GOLDEN_PARITY_TARGET} "
              "— NOT rationalizing; stopping. Evidence sealed at "
              f"{report_path}", flush=True)
        return 1
    print(f"[GOLDEN OK] max|delta|={max_delta} over {len(oos)} rows / "
          f"{len(window)} dates; fit {timings['fit_s']}s", flush=True)
    return 0


def _rebuilt_inputs(input_digests: dict) -> list[dict]:
    """The three lineage-relevant rebuilt inputs, each with its CURRENT
    read-time sha256 (from the digests recorded in main()) and its measured
    on-disk mtime date — the seam block's file evidence."""
    import datetime  # noqa: PLC0415
    rows = []
    for name_key, sha_key in (("fundamentals", "fundamentals_sha256"),
                              ("panel", "panel_sha256"),
                              ("alpha_stats", "alpha_stats_sha256")):
        p = Path(input_digests[name_key])
        rows.append({
            "file": str(p),
            "sha256_at_read_time": input_digests[sha_key],
            "mtime_date_measured":
                datetime.date.fromtimestamp(p.stat().st_mtime).isoformat(),
        })
    return rows


def run_extension(out_dir: Path, manifest: dict, target_earliest: str,
                  min_train_dates: int, input_digests: dict,
                  plan_only: bool, accept_vintage_seam: bool = False,
                  evidence_golden: Path | None = None) -> int:
    """Plan (read-only, prints) or train the backward batch. The batch runs
    ONLY inside an atomically claimed run dir (``assert_claimed`` first, before
    anything else), admits only via the golden evidence at ``evidence_golden``
    (PASS without the seam flag; digest-bound FAIL with it), and is sealed
    read-only at finish."""
    if not plan_only:
        assert_claimed(out_dir)
    t_start = time.time()
    ref, ref_path, _ = _load_ref_artifact(manifest)
    cuts = validate_ladder([r["cutoff_date"] for r in manifest["retrains"]])
    cadence = derive_cadence_days(cuts)
    new_cuts = backward_extension(cuts, target_earliest)
    all_dates = _panel_dates()
    panel_min = pd.Timestamp(all_dates[0])

    # feasibility: refuse windows whose training slice is too thin. The panel
    # starts at panel_min; a cutoff needs >= min_train_dates panel dates
    # strictly before (cutoff - embargo BDays).
    embargo = int(ref["cutoff_embargo_days"])
    feasible, truncated = [], []
    for c in new_cuts:
        eff = pd.Timestamp(c) - pd.offsets.BDay(embargo)
        n = int((all_dates < np.datetime64(eff)).sum())
        (feasible if n >= min_train_dates else truncated).append(
            {"cutoff_date": c, "n_train_dates_available": n})
    plan = {
        "cadence_days": cadence,
        "cadence_measurement": {
            "consecutive_gap_days_set": [cadence],
            "cutoff_weekday_set": sorted({pd.Timestamp(c).dayofweek for c in cuts}),
            "nyse_holiday_cutoff_evidence": "2023-12-25" if "2023-12-25" in cuts else None,
            "convention": "pure N-calendar-day arithmetic grid, no NYSE-holiday "
                          "adjustment; OOS windows use panel trading dates",
        },
        "existing_n": len(cuts),
        "existing_earliest": cuts[0], "existing_latest": cuts[-1],
        "target_earliest": target_earliest,
        "panel_min_date": str(panel_min.date()),
        "min_train_dates": min_train_dates,
        "n_new_windows": len(feasible),
        "new_earliest": feasible[0]["cutoff_date"] if feasible else None,
        "new_latest": feasible[-1]["cutoff_date"] if feasible else None,
        "truncated_infeasible": truncated,
    }
    if plan_only:
        # read-only preview: PRINTS the plan, writes nothing (files exist only
        # inside claimed, sealed run dirs).
        print(json.dumps(plan, indent=2), flush=True)
        return 0

    # batch admission: golden PASS, or an explicitly declared seam over a
    # digest-BOUND golden FAIL — nothing in between (resolve_vintage_seam
    # refuses the rest, naming any diverging input digest).
    if evidence_golden is None:
        raise ValueError(
            "no golden evidence declared — pass --evidence-golden "
            "<run-dir>/golden_report.json from a sealed --golden run")
    bound = resolve_vintage_seam(evidence_golden, accept_vintage_seam,
                                 input_digests)
    seam = None
    if bound is not None:
        seam_report, seam_report_sha = bound
        seam = build_vintage_seam(seam_report, _rebuilt_inputs(input_digests),
                                  evidence_path=str(evidence_golden),
                                  evidence_sha256=seam_report_sha)
    existing_rows = _existing_window_rows(manifest)
    recipe_id = recipe_fingerprint(ref)
    old_root = lineage_root(recipe_id, [r["artifact_sha256"] for r in existing_rows])

    # extended ladder for the OOS grid: each new window's OOS ends at the NEXT
    # cutoff (the newest new window hands over to the earliest existing one).
    ladder = [f["cutoff_date"] for f in feasible] + cuts
    new_rows: list[dict] = []
    order_executed: list[str] = []
    # newest-first execution (largest fit first surfaces cost early); manifest
    # rows are emitted in chronological order regardless.
    for c in reversed([f["cutoff_date"] for f in feasible]):
        cut = pd.Timestamp(c)
        first_oos = _first_oos_after(all_dates, cut)
        art, timings = _train_window(cut, ref=ref, first_oos=first_oos)
        wdir = out_dir / "window_artifacts" / c
        wdir.mkdir(parents=True, exist_ok=True)
        wpath = wdir / "panel-ltr.json"
        wpath.write_text(json.dumps(art))  # the production writer's format
        idx = ladder.index(c)
        nxt = ladder[idx + 1]
        new_rows.append({
            "cutoff_date": c,
            "artifact_path": str(wpath.relative_to(out_dir)),
            "artifact_sha256": sha256_file(wpath),
            "effective_train_cutoff_date":
                str(art["effective_train_cutoff_date"])[:10],
            "cutoff_embargo_days": int(art["cutoff_embargo_days"]),
            "oos_window_rule": f"({c}, {nxt}] over panel trading dates",
            "first_oos_date": str(first_oos.date()),
            "leakage_margin_bdays": timings["leakage_margin_bdays"],
            "n_train_rows": timings["n_train_rows"],
            "n_train_dates": timings["n_train_dates"],
            "sentiment_zeroed_rows": timings["zeroed_rows"],
            "fit_seconds": timings["fit_s"],
            "provenance": "jobb_depth_extension",
            **({"input_vintage": VINTAGE_SEAM_TAG} if seam is not None else {}),
        })
        order_executed.append(c)
        print(f"[window {c}] train_rows={timings['n_train_rows']:,} "
              f"fit={timings['fit_s']}s total={timings['total_s']}s "
              f"margin={timings['leakage_margin_bdays']}bd", flush=True)
    new_rows.sort(key=lambda r: r["cutoff_date"])

    ordered_shas = ([r["artifact_sha256"] for r in new_rows]
                    + [r["artifact_sha256"] for r in existing_rows])
    new_root = lineage_root(recipe_id, ordered_shas)
    ext = {
        "schema": "gbdt-depth-extension-lineage-v1",
        "identity_model": "renquant-backtesting#94",
        "root_rule": "sha256(recipe_id + LF + LF-joined ordered window artifact "
                     "shas + LF); ordered = chronological cutoff order, new "
                     "windows BEFORE the existing ladder (append-only backwards)",
        "recipe_id": recipe_id,
        "recipe_id_rule": "recipe_match.recipe_fingerprint over the window "
                          "artifact's recipe projection",
        "old_lineage_root_sha": old_root,
        "old_lineage_n_windows": len(existing_rows),
        "new_lineage_root_sha": new_root,
        "new_lineage_n_windows": len(ordered_shas),
        "plan": plan,
        **({"vintage_seam": seam} if seam is not None else {}),
        "execution_order": order_executed,
        "new_windows": new_rows,
        "existing_windows": existing_rows,
        "inputs": input_digests,
        "reference_artifact": str(ref_path),
        "wall_seconds": round(time.time() - t_start, 1),
    }
    manifest_path = out_dir / "gbdt_depth_extension_manifest.json"
    manifest_path.write_text(json.dumps(ext, indent=2))
    seal_run(out_dir, {"outcome": "extension",
                       "n_new_windows": len(new_rows),
                       "new_lineage_root_sha": new_root,
                       "manifest_sha256": sha256_file(manifest_path)})
    print(json.dumps({"old_lineage_root_sha": old_root,
                      "new_lineage_root_sha": new_root,
                      "n_new_windows": len(new_rows)}, indent=2), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT),
                    help="durable run-dir root; each writing invocation claims "
                         "its own run-<NNN> subdir and seals it at finish")
    ap.add_argument("--run-id", default=None,
                    help="predeclared run id NNN (required for --golden and "
                         "the batch; refused if run-<NNN> already exists)")
    ap.add_argument("--target-earliest", default=DEFAULT_TARGET_EARLIEST)
    ap.add_argument("--min-train-dates", type=int, default=250,
                    help="refuse windows with fewer panel dates before their "
                         "effective cutoff (a year of trading days by default)")
    ap.add_argument("--golden", action="store_true",
                    help="reproduce the earliest EXISTING window and report "
                         "prediction parity; the only training this mode runs")
    ap.add_argument("--plan-only", action="store_true",
                    help="compute + PRINT the backward ladder; no training, "
                         "no writes")
    ap.add_argument("--accept-vintage-seam", action="store_true",
                    help="batch admission over a FAILED golden: record the "
                         "documented input-vintage seam (operator decision "
                         "2026-08-02) instead of requiring parity; refuses "
                         "if the golden PASSED, is absent, or its recorded "
                         "input digests diverge from the pending batch's")
    ap.add_argument("--evidence-golden", default=None,
                    help="path to the sealed golden_report.json from a prior "
                         "--golden run; the batch's admission evidence "
                         "(required for the batch)")
    args = ap.parse_args(argv)

    out_root = resolve_out_dir(args.out_root)  # refuses anything inside RenQuant
    _bootstrap_heavy()

    # input digests, recorded AT READ TIME (before any load that uses them)
    input_digests = {
        "wf_manifest": str(WF_MANIFEST),
        "wf_manifest_sha256": sha256_file(WF_MANIFEST),
        "panel": str(DATA / "alpha158_291_fundamental_dataset.parquet"),
        "panel_sha256": sha256_file(DATA / "alpha158_291_fundamental_dataset.parquet"),
        "alpha_stats": str(DATA / "alpha158_qlib_dataset.stats.json"),
        "alpha_stats_sha256": sha256_file(DATA / "alpha158_qlib_dataset.stats.json"),
        "fundamentals": str(DATA / "sec_fundamentals_daily.parquet"),
        "fundamentals_sha256": sha256_file(DATA / "sec_fundamentals_daily.parquet"),
        "strategy_config": str(STRATEGY_CONFIG),
        "strategy_config_sha256": sha256_file(STRATEGY_CONFIG),
        "spy_ohlcv": str(DATA / "ohlcv" / "SPY" / "1d.parquet"),
        "spy_ohlcv_sha256": sha256_file(DATA / "ohlcv" / "SPY" / "1d.parquet"),
        "gmm_artifact": str(STRATEGY_DIR / "artifacts" / "prod" / "spy-gmm-regime.json"),
        "gmm_artifact_sha256": sha256_file(
            STRATEGY_DIR / "artifacts" / "prod" / "spy-gmm-regime.json"),
    }
    manifest = json.loads(WF_MANIFEST.read_text())

    if args.plan_only:
        # read-only: no run dir, no claim, no writes.
        return run_extension(out_root, manifest, args.target_earliest,
                             args.min_train_dates, input_digests, True)

    # every writing mode claims its predeclared run dir BEFORE any training
    # or output write; the claim is the first and only dir creation.
    if not args.run_id:
        raise SystemExit("--run-id NNN is required for --golden and the batch "
                         "(each run gets its own claimed, sealed run dir)")
    mode = "golden" if args.golden else "extension"
    run_dir = claim_run_dir(out_root, args.run_id, mode)

    if args.golden:
        return run_golden(run_dir, manifest, input_digests)
    return run_extension(run_dir, manifest, args.target_earliest,
                         args.min_train_dates, input_digests, False,
                         accept_vintage_seam=args.accept_vintage_seam,
                         evidence_golden=(Path(args.evidence_golden)
                                          if args.evidence_golden else None))


if __name__ == "__main__":
    sys.exit(main())
