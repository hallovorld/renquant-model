"""Deterministic in-repo verification of the committed Job B depth-extension
bundle (run-001; GOAL-6, tool merged in model#185).

Everything here recomputes from COMMITTED BYTES ONLY — the bundle carries the
full 82 window artifacts (30 MB, under the byte cap), so no check needs the
durable run directory or the umbrella; one OPTIONAL cross-check against the
sealed run dir loudly skips where that dir is absent (CI). The verified
claims: every artifact digest matches its manifest row; both lineage roots
recompute per the manifest's OWN root_rule (old root from the suffix, #94
append-only); the root is order-sensitive; the sealed run claim binds the
manifest bytes; every artifact honours the TYPE contract (the
stringified-norm_kind incident class — note the gbdt schema carries
feature_means/stds as LISTS aligned to feature_cols, not the clf bundle's
dicts, so the guard here is list-length alignment); the vintage seam is
complete and every new window row carries it; and the #94 causal
admissibility margin recomputes from each row's own fields.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
B = REPO / "doc/research/data/2026-08-02-jobb-gbdt-depth-extension-run001"
GOLDEN_BUNDLE = REPO / "doc/research/data/2026-08-02-jobb-gbdt-depth-extension"
RUN_DIR = Path.home() / "renquant-data-store" / "goal6-jobb-gbdt-depth" / "run-001"
VINTAGE = "2026-08-01-rebuild"
NORM_VOCAB = {"global_z", "robust_z", "identity"}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((B / "gbdt_depth_extension_manifest.json").read_text())


@pytest.fixture(scope="module")
def artifacts(manifest) -> list[tuple[dict, dict]]:
    """(manifest row, parsed committed artifact) for all 82 new windows."""
    return [(r, json.loads((B / r["artifact_path"]).read_text()))
            for r in manifest["new_windows"]]


# ── counts + ladder shape ────────────────────────────────────────────────────

def test_counts_and_backward_ladder_shape(manifest):
    new, old = manifest["new_windows"], manifest["existing_windows"]
    assert len(new) == 82 and len(old) == 43
    assert manifest["new_lineage_n_windows"] == 125
    assert manifest["old_lineage_n_windows"] == 43
    cuts = [r["cutoff_date"] for r in new]
    assert cuts == sorted(cuts) and len(set(cuts)) == len(cuts)
    assert cuts[0] == "2019-01-14" and cuts[-1] == "2023-09-11"
    # strictly BEFORE the existing ladder, on its 21-day grid
    earliest_existing = pd.Timestamp(old[0]["cutoff_date"])
    assert earliest_existing == pd.Timestamp("2023-10-02")
    for c in cuts:
        delta = (earliest_existing - pd.Timestamp(c)).days
        assert delta > 0 and delta % 21 == 0, c


# ── digests + roots (the #94 identity model) ─────────────────────────────────

def test_every_committed_artifact_digest_matches_its_manifest_row(manifest):
    for r in manifest["new_windows"]:
        p = B / r["artifact_path"]
        assert p.is_file(), r["artifact_path"]
        assert _sha(p) == r["artifact_sha256"], r["cutoff_date"]


def test_manifest_DECLARES_the_root_rule_this_file_implements(manifest):
    assert manifest["root_rule"].startswith(
        "sha256(recipe_id + LF + LF-joined ordered window artifact shas + LF)")
    assert manifest["schema"] == "gbdt-depth-extension-lineage-v1"
    assert manifest["identity_model"] == "renquant-backtesting#94"


def _root(recipe_id: str, shas: list[str]) -> str:
    return hashlib.sha256(
        (recipe_id + "\n" + "\n".join(shas) + "\n").encode("utf-8")).hexdigest()


def test_new_root_recomputes_from_committed_bytes(manifest):
    """New windows chronologically BEFORE the existing 43 (append-only
    backwards); new-window digests recomputed from the COMMITTED files, not
    trusted from their own rows."""
    shas = ([_sha(B / r["artifact_path"]) for r in manifest["new_windows"]]
            + [r["artifact_sha256"] for r in manifest["existing_windows"]])
    assert _root(manifest["recipe_id"], shas) == manifest["new_lineage_root_sha"]


def test_old_root_recomputes_from_the_suffix(manifest):
    suffix = [r["artifact_sha256"] for r in manifest["existing_windows"]]
    assert _root(manifest["recipe_id"], suffix) == manifest["old_lineage_root_sha"]
    assert manifest["old_lineage_root_sha"] != manifest["new_lineage_root_sha"]


def test_root_is_ORDER_sensitive(manifest):
    shas = ([r["artifact_sha256"] for r in manifest["new_windows"]]
            + [r["artifact_sha256"] for r in manifest["existing_windows"]])
    swapped = list(shas)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert _root(manifest["recipe_id"], swapped) != manifest["new_lineage_root_sha"]


def test_recipe_id_recomputes_from_every_committed_artifact(manifest, artifacts):
    """The manifest's recipe_id must equal the lineage lane's recipe
    fingerprint of EVERY committed window artifact — one recipe, 82 windows.
    The projection is imported from the merged tool, never restated here."""
    spec = importlib.util.spec_from_file_location(
        "wf_gbdt_depth_extension", REPO / "tools" / "wf_gbdt_depth_extension.py")
    tool = importlib.util.module_from_spec(spec)
    sys.modules["wf_gbdt_depth_extension"] = tool
    spec.loader.exec_module(tool)
    for r, art in artifacts:
        assert tool.recipe_fingerprint(art) == manifest["recipe_id"], r["cutoff_date"]


# ── the sealed run claim binds the manifest bytes ────────────────────────────

def test_run_claim_binds_the_committed_manifest(manifest):
    claim = json.loads((B / "RUN_CLAIM.json").read_text())
    assert claim["status"] == "consumed"
    assert claim["outcome"] == "extension"
    assert claim["n_new_windows"] == 82
    assert claim["new_lineage_root_sha"] == manifest["new_lineage_root_sha"]
    assert claim["manifest_sha256"] == _sha(B / "gbdt_depth_extension_manifest.json")


# ── TYPE guards (the stringified-norm_kind incident class) ───────────────────

def test_artifact_fields_have_the_TYPES_the_consumers_assume(artifacts):
    """gbdt window artifacts carry feature_means/stds as LISTS aligned to
    feature_cols (unlike the clf bundle's dicts), so the alignment guard is
    length equality; norm_kind must be a per-feature LIST, never one string."""
    for r, art in artifacts:
        n = len(art["feature_cols"])
        assert n == 172, r["cutoff_date"]
        nk = art["feature_norm_kind"]
        assert isinstance(nk, list) and not isinstance(nk, str), r["cutoff_date"]
        assert len(nk) == n, r["cutoff_date"]
        assert set(nk) <= NORM_VOCAB, sorted(set(nk) - NORM_VOCAB)
        assert isinstance(art["feature_means"], list) and len(art["feature_means"]) == n
        assert isinstance(art["feature_stds"], list) and len(art["feature_stds"]) == n
        assert isinstance(art["booster_raw_json"], str) and len(art["booster_raw_json"]) > 0


def test_no_wrong_artifact_behind_a_window(artifacts):
    """lineage_lane's structural check on the committed bytes: each artifact's
    SELF-CARRIED cutoff/embargo/effective-cutoff equal its manifest row's."""
    for r, art in artifacts:
        assert str(art["cutoff_date"])[:10] == r["cutoff_date"]
        assert int(art["cutoff_embargo_days"]) == int(r["cutoff_embargo_days"]) == 60
        assert (str(art["effective_train_cutoff_date"])[:10]
                == r["effective_train_cutoff_date"])


# ── vintage completeness (the seam must be visible everywhere) ───────────────

def test_every_new_window_row_carries_the_input_vintage(manifest):
    for r in manifest["new_windows"]:
        assert r.get("input_vintage") == VINTAGE, r["cutoff_date"]


def test_the_seam_block_is_complete_and_binds_its_evidence(manifest):
    seam = manifest["vintage_seam"]
    required = ("input_vintage", "decision", "decision_rationale",
                "evidence_golden_report", "evidence_golden_report_sha256",
                "golden_parity_max_abs_delta", "drift", "rebuilt_inputs",
                "rebuild_date_measured", "non_reproducibility")
    missing = [k for k in required if k not in seam]
    assert not missing, missing
    assert seam["input_vintage"] == VINTAGE
    assert seam["rebuild_date_measured"] == "2026-08-01"
    sha = seam["evidence_golden_report_sha256"]
    assert isinstance(sha, str) and len(sha) == 64
    for d in seam["rebuilt_inputs"]:
        assert len(d["sha256_at_read_time"]) == 64
    assert len(seam["rebuilt_inputs"]) == 3
    drift = seam["drift"]
    assert drift["feature_means_max_abs_delta"] == pytest.approx(7.131e-3, rel=1e-3)
    assert drift["feature_stds_max_abs_delta"] == pytest.approx(9.450e-3, rel=1e-3)
    assert "no longer exist on disk" in seam["non_reproducibility"]


def test_the_seam_evidence_IS_the_committed_185_golden_report(manifest):
    """The seam's content-sha binding must resolve to bytes THIS repo carries:
    the model#185 bundle's golden_report.json."""
    seam = manifest["vintage_seam"]
    p = GOLDEN_BUNDLE / "golden_report.json"
    assert p.is_file()
    assert _sha(p) == seam["evidence_golden_report_sha256"]
    report = json.loads(p.read_text())
    assert report["parity_pass"] is False
    assert (report["prediction_parity_max_abs_delta"]
            == seam["golden_parity_max_abs_delta"])


# ── #94 causal admissibility, recomputed from each row's own fields ──────────

def test_admissibility_margin_recomputes_and_is_at_least_one_bday(manifest):
    for r in manifest["new_windows"]:
        etc = pd.Timestamp(r["effective_train_cutoff_date"])
        safe = etc + pd.offsets.BDay(int(r["cutoff_embargo_days"]))
        first_oos = pd.Timestamp(r["first_oos_date"])
        assert safe < first_oos, r["cutoff_date"]
        margin = len(pd.bdate_range(safe, first_oos)) - 1
        assert margin == int(r["leakage_margin_bdays"]), r["cutoff_date"]
        assert margin >= 1, r["cutoff_date"]


# ── repo containment + optional run-dir byte parity ──────────────────────────

def test_every_path_this_verifier_READS_is_inside_this_repository(manifest):
    read = [B / "gbdt_depth_extension_manifest.json", B / "RUN_CLAIM.json",
            GOLDEN_BUNDLE / "golden_report.json",
            *(B / r["artifact_path"] for r in manifest["new_windows"])]
    assert len(read) == 85
    for p in read:
        assert p.is_file(), p
        assert p.resolve().is_relative_to(REPO), p
    for r in manifest["new_windows"]:
        assert not r["artifact_path"].startswith("/") and ".." not in r["artifact_path"]


def test_OPTIONAL_committed_bytes_equal_the_sealed_run_dir(manifest):
    """Byte parity against the durable run-001 home — loud skip where the
    run dir does not exist (CI); the digest checks above are the CI-side
    authority either way."""
    if not RUN_DIR.is_dir():
        pytest.skip(f"durable run dir absent on this machine: {RUN_DIR} — "
                    "committed-byte digest checks above remain the authority")
    assert _sha(RUN_DIR / "gbdt_depth_extension_manifest.json") == _sha(
        B / "gbdt_depth_extension_manifest.json")
    for r in manifest["new_windows"]:
        assert _sha(RUN_DIR / r["artifact_path"]) == _sha(B / r["artifact_path"]), (
            r["cutoff_date"])
