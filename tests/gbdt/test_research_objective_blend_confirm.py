"""Synthetic-data tests for the objective-blend confirmatory executor
(prereg `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md`,
script `scripts/research_objective_blend_confirm.py`).

These tests do NOT touch the panel, xgboost, or any production path — they
exercise `decide_verdict`, `block_bootstrap_ci`, and the
`serialize_result`/`deserialize_result`/`verdict_from_bundle` replay path
against hand-built series, pinning the frozen guard/decision-rule branches
and the round trip a reviewer needs to replay a persisted `--out` bundle
(model#68 review round 3 BLOCKER 1, round 4 "add focused synthetic tests
for the exact w50 guard and decision branches").
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SPEC_PATH = (Path(__file__).resolve().parents[2] / "scripts"
              / "research_objective_blend_confirm.py")
_spec = importlib.util.spec_from_file_location("research_objective_blend_confirm", _SPEC_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules["research_objective_blend_confirm"] = mod
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


# --- frozen constants are LOCKED (prereg — the whole point of a prereg) ------
def test_frozen_decision_rule_constants():
    assert mod.SEEDS == tuple(range(42, 52))
    assert len(mod.SEEDS) == 10
    assert mod.BLK == 60
    assert mod.TOP_N == 10
    assert mod.MIN_SEEDS_POSITIVE == 8


DATES = pd.bdate_range("2020-01-01", periods=300)


def _series(values, dates=DATES):
    return pd.Series(dict(zip(dates, values)))


# --- decide_verdict: the three decision branches -----------------------------
def test_decide_verdict_confirmed_needs_all_three_conditions():
    # CI lower bound > 0, >=8/10 seeds positive, winsorized guard >= 0
    assert mod.decide_verdict(ci_lo=0.001, diff_mean=0.05, n_pos=8, wins_diff=0.0) == "CONFIRMED"
    assert mod.decide_verdict(ci_lo=0.001, diff_mean=0.05, n_pos=10, wins_diff=0.02) == "CONFIRMED"


def test_decide_verdict_ci_touching_zero_is_not_confirmed():
    # lower bound exactly 0 does not satisfy "> 0"
    assert mod.decide_verdict(ci_lo=0.0, diff_mean=0.05, n_pos=10, wins_diff=0.02) != "CONFIRMED"


def test_decide_verdict_seed_instability_blocks_confirmed_even_with_positive_ci():
    out = mod.decide_verdict(ci_lo=0.01, diff_mean=0.05, n_pos=7, wins_diff=0.02)
    assert out != "CONFIRMED"
    assert out == "INCONCLUSIVE"


def test_decide_verdict_negative_winsorized_guard_blocks_confirmed():
    out = mod.decide_verdict(ci_lo=0.01, diff_mean=0.05, n_pos=10, wins_diff=-0.01)
    assert out != "CONFIRMED"
    assert out == "INCONCLUSIVE"


def test_decide_verdict_refuted_on_nonpositive_point_estimate():
    assert mod.decide_verdict(ci_lo=-0.05, diff_mean=-0.01, n_pos=3, wins_diff=-0.02) == "REFUTED"
    assert mod.decide_verdict(ci_lo=-0.05, diff_mean=0.0, n_pos=3, wins_diff=-0.02) == "REFUTED"


def test_decide_verdict_inconclusive_when_ci_spans_zero_but_point_estimate_positive():
    out = mod.decide_verdict(ci_lo=-0.01, diff_mean=0.03, n_pos=9, wins_diff=0.01)
    assert out == "INCONCLUSIVE"


# --- block_bootstrap_ci: deterministic, seed-controlled -----------------------
def test_block_bootstrap_ci_is_deterministic_for_a_fixed_seed():
    diff = _series(np.random.default_rng(0).normal(0.02, 0.05, len(DATES)))
    lo1, hi1 = mod.block_bootstrap_ci(diff, n_boot=500)
    lo2, hi2 = mod.block_bootstrap_ci(diff, n_boot=500)
    assert (lo1, hi1) == (lo2, hi2)


def test_block_bootstrap_ci_brackets_the_mean_for_a_clear_positive_signal():
    diff = _series(np.full(len(DATES), 0.05) + np.random.default_rng(1).normal(0, 0.005, len(DATES)))
    lo, hi = mod.block_bootstrap_ci(diff, n_boot=500)
    assert lo < diff.mean() < hi
    assert lo > 0  # signal swamps the noise -> CI should clear zero


def test_block_bootstrap_ci_spans_zero_for_pure_noise():
    diff = _series(np.random.default_rng(2).normal(0.0, 0.05, len(DATES)))
    lo, hi = mod.block_bootstrap_ci(diff, n_boot=500)
    assert lo < 0 < hi


# --- serialize/deserialize round trip -> verdict_from_bundle -----------------
def _make_clean_series(rng_seed=1, blend_bias=0.05, rank60_bias=0.02, noise=0.01):
    rng = np.random.default_rng(rng_seed)
    blend_by_seed, rank60_by_seed = {}, {}
    for seed in mod.SEEDS:
        blend_by_seed[seed] = _series(blend_bias + rng.normal(0, noise, len(DATES)))
        rank60_by_seed[seed] = _series(rank60_bias + rng.normal(0, noise, len(DATES)))
    blend_df = pd.DataFrame(blend_by_seed)
    rank60_df = pd.DataFrame(rank60_by_seed)
    return {
        "blend": blend_df.mean(axis=1).sort_index(),
        "rank60": rank60_df.mean(axis=1).sort_index(),
        "blend_w50": blend_df.mean(axis=1).sort_index() * 0.2,
        "rank60_w50": rank60_df.mean(axis=1).sort_index() * 0.2,
        "blend_by_seed": blend_df,
        "rank60_by_seed": rank60_df,
    }


def _direct_verdict(clean_series):
    a, b_ = clean_series["blend"], clean_series["rank60"]
    c = a.index.intersection(b_.index)
    diff = (a[c] - b_[c]).sort_index()
    aw, bw = clean_series["blend_w50"], clean_series["rank60_w50"]
    cw = aw.index.intersection(bw.index)
    wins_diff_series = (aw[cw] - bw[cw]).sort_index()
    lo, hi = mod.block_bootstrap_ci(diff)
    by_seed_a, by_seed_b = clean_series["blend_by_seed"], clean_series["rank60_by_seed"]
    seed_signs = []
    for s in mod.SEEDS:
        ca, cb = by_seed_a[s].dropna(), by_seed_b[s].dropna()
        cc = ca.index.intersection(cb.index)
        seed_signs.append(float((ca[cc] - cb[cc]).mean()))
    n_pos = sum(1 for x in seed_signs if x > 0)
    verdict = mod.decide_verdict(lo, float(diff.mean()), n_pos, float(wins_diff_series.mean()))
    return diff, wins_diff_series, {"diff_mean": float(diff.mean()), "ci90": [lo, hi],
                                     "seeds_positive": n_pos,
                                     "winsorized_w50_diff": float(wins_diff_series.mean()),
                                     "verdict": verdict}


def test_serialize_deserialize_round_trip_reproduces_verdict():
    clean_series = _make_clean_series()
    diff, wins_diff_series, expected = _direct_verdict(clean_series)

    import json as _json
    payload = _json.loads(_json.dumps(
        mod.serialize_result(clean_series, diff, wins_diff_series)))
    bundle = mod.deserialize_result(payload)
    reloaded = mod.verdict_from_bundle(bundle)

    assert reloaded["verdict"] == expected["verdict"]
    assert reloaded["seeds_positive"] == expected["seeds_positive"]
    assert reloaded["diff_mean"] == pytest.approx(expected["diff_mean"])
    assert reloaded["ci90"] == pytest.approx(expected["ci90"])
    assert reloaded["winsorized_w50_diff"] == pytest.approx(expected["winsorized_w50_diff"])


def test_serialize_deserialize_round_trip_on_a_refuted_case():
    clean_series = _make_clean_series(rng_seed=5, blend_bias=0.01, rank60_bias=0.03, noise=0.02)
    diff, wins_diff_series, expected = _direct_verdict(clean_series)
    assert expected["verdict"] in ("REFUTED", "INCONCLUSIVE")  # sanity: this fixture is not a win

    import json as _json
    payload = _json.loads(_json.dumps(
        mod.serialize_result(clean_series, diff, wins_diff_series)))
    bundle = mod.deserialize_result(payload)
    reloaded = mod.verdict_from_bundle(bundle)
    assert reloaded["verdict"] == expected["verdict"]


def test_serialized_bundle_carries_per_seed_series_not_just_the_average():
    clean_series = _make_clean_series()
    diff, wins_diff_series, _ = _direct_verdict(clean_series)
    payload = mod.serialize_result(clean_series, diff, wins_diff_series)
    assert set(payload["blend_by_seed"]) == {str(s) for s in mod.SEEDS}
    assert set(payload["rank60_by_seed"]) == {str(s) for s in mod.SEEDS}
    assert "diff_by_date" in payload
    assert "wins_diff_by_date" in payload


# --- manifest: digests + pre-run-freeze timestamps ----------------------------
def _fake_panel():
    return pd.DataFrame({"date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])})


def test_build_manifest_digests_command_and_timestamps(tmp_path):
    from renquant_model_gbdt.panel_data import PANEL_FILE

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / PANEL_FILE).write_bytes(b"fake panel bytes")

    manifest = mod.build_manifest(
        data_dir=data_dir, argv=["research_objective_blend_confirm.py", "--out", "x.json"],
        run_started_at="2026-07-25T08:00:00+00:00",
        run_finished_at="2026-07-25T09:00:00+00:00", panel=_fake_panel())

    assert manifest["data_digest"] == "sha256:" + mod._sha256_file(data_dir / PANEL_FILE)
    assert manifest["prereg_digest"] == "sha256:" + mod._sha256_file(mod.PREREG_PATH)
    assert manifest["command"] == "research_objective_blend_confirm.py --out x.json"
    assert manifest["code_revision"]  # non-empty: a real SHA inside this repo's checkout
    assert manifest["code_revision_parents"]  # non-empty: HEAD has >=1 parent in this repo
    assert manifest["prereg_commit"]  # non-empty: the prereg file is committed in this repo
    assert manifest["prereg_commit_is_ancestor_of_code_revision"] is True
    assert manifest["run_started_at"] == "2026-07-25T08:00:00+00:00"
    assert manifest["run_finished_at"] == "2026-07-25T09:00:00+00:00"
    assert manifest["row_count"] == 3
    assert manifest["date_range"] == ["2026-01-02", "2026-01-06"]
    assert manifest["producing_script"]["repo"] == "renquant-base-data"
    assert manifest["producing_script"]["path"] == mod._PANEL_BUILDER_SCRIPT


def test_build_manifest_missing_data_file_reports_none_digest_not_a_crash(tmp_path):
    manifest = mod.build_manifest(
        data_dir=tmp_path / "nope", argv=["x"],
        run_started_at="t0", run_finished_at="t1", panel=_fake_panel())
    assert manifest["data_digest"] is None
    # the prereg file itself is real (committed in this repo) -> always present
    assert manifest["prereg_digest"] is not None


def test_build_manifest_raises_when_prereg_freeze_unresolved(tmp_path, monkeypatch):
    """model#74 review round 6 BLOCKER: `_prereg_freeze` returning
    `(None, None)` (shallow clone, inconsistent history) is not itself
    fail-closed — the round-5 fix stopped there, but `build_manifest()` just
    serialized the nulls and `main()` still wrote the bundle. `build_manifest`
    must raise before any manifest is produced, so `main()` can never reach
    the `json.dump` that persists a bundle with null provenance."""
    from renquant_model_gbdt.panel_data import PANEL_FILE

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / PANEL_FILE).write_bytes(b"fake panel bytes")

    monkeypatch.setattr(mod, "_prereg_freeze", lambda *a, **k: (None, None))

    with pytest.raises(RuntimeError, match="cannot resolve the pre-run freeze"):
        mod.build_manifest(
            data_dir=data_dir, argv=["x"],
            run_started_at="t0", run_finished_at="t1", panel=_fake_panel())


# --- prereg freeze: a post-run "## RESULTS" append must NOT move the stamp ---
def _git(repo_dir, *args):
    subprocess.run(["git", *args], cwd=repo_dir, capture_output=True, text=True, check=True)


def _make_prereg_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    prereg = repo_dir / "prereg.md"
    prereg.write_text("# Frozen spec\n\nSeeds 1/2/3.\n")
    _git(repo_dir, "add", "prereg.md")
    _git(repo_dir, "commit", "-q", "-m", "freeze prereg")
    freeze_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                                capture_output=True, text=True, check=True).stdout.strip()
    return repo_dir, prereg, freeze_sha


def test_prereg_freeze_ignores_a_later_results_append():
    """model#74 review BLOCKER: `git log -1` on the whole file picked up a
    RESULTS-append commit made AFTER the run, not the actual pre-run freeze
    — defeating the manifest's pre-run-freeze guarantee. The freeze commit
    and digest must track the frozen section only, unmoved by that append."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo_dir, prereg, freeze_sha = _make_prereg_repo(Path(td))
        frozen_bytes = prereg.read_bytes()

        # Post-run amendment: append a "---" rule + RESULTS section, exactly
        # as this repo's own screen-prereg convention does (round 2: the
        # first fix attempt only tested a bare "\n## RESULTS" append with no
        # separator and missed that the "---" rule leaks into the "frozen"
        # side of a naive split).
        with open(prereg, "a") as f:
            f.write("\n\n---\n\n## RESULTS\n\nran fine\n")
        _git(repo_dir, "add", "prereg.md")
        _git(repo_dir, "commit", "-q", "-m", "amend with results")

        commit, digest = mod._prereg_freeze(repo_dir, prereg)
        assert commit == freeze_sha
        assert digest == mod.hashlib.sha256(frozen_bytes).hexdigest()
        # not the whole (now RESULTS-amended) current file
        assert digest != mod.hashlib.sha256(prereg.read_bytes()).hexdigest()


def test_prereg_freeze_matches_whole_file_when_never_amended():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo_dir, prereg, freeze_sha = _make_prereg_repo(Path(td))
        commit, digest = mod._prereg_freeze(repo_dir, prereg)
        assert commit == freeze_sha
        assert digest == mod.hashlib.sha256(prereg.read_bytes()).hexdigest()


def test_prereg_freeze_fails_closed_on_shallow_clone():
    """model#74 review round 5 P1: `actions/checkout@v4`'s default (depth 1,
    what this repo's CI actually uses) makes a shallow clone where the
    checked-out boundary commit is the ONLY commit `git log -- <path>` can
    see. Without a shallow guard, `_prereg_freeze`'s self-consistency check
    is trivially satisfied by that single commit, so it would silently
    stamp the post-run RESULTS-append commit as the "freeze" here — exactly
    the bug `test_prereg_freeze_ignores_a_later_results_append` exists to
    catch on full history. A shallow clone must fail closed instead."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo_dir, prereg, freeze_sha = _make_prereg_repo(Path(td))
        with open(prereg, "a") as f:
            f.write("\n\n---\n\n## RESULTS\n\nran fine\n")
        _git(repo_dir, "add", "prereg.md")
        _git(repo_dir, "commit", "-q", "-m", "amend with results")

        # `file://` forces the network-style transport for the clone; a bare
        # local path triggers git's local-clone hardlink optimization, which
        # ignores `--depth` and produces a full (non-shallow) clone instead.
        shallow_dir = Path(td) / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo_dir}", str(shallow_dir)],
                      capture_output=True, text=True, check=True)
        assert mod._is_shallow_repo(shallow_dir) is True

        commit, digest = mod._prereg_freeze(shallow_dir, shallow_dir / "prereg.md")
        assert commit is None
        assert digest is None


# --- manifest binding: --seeds/--prereg-path override path (model#74/#75 review) ---
def test_build_manifest_binds_to_overridden_prereg_path(tmp_path):
    """A `--prereg-path` override (a screen or fresh-seed confirmatory replay
    under a different frozen prereg) must stamp digest/commit/command against
    THAT file, not silently fall back to the default confirmatory PREREG_PATH."""
    from renquant_model_gbdt.panel_data import PANEL_FILE

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / PANEL_FILE).write_bytes(b"fake panel bytes")

    override_prereg = (mod.PREREG_PATH.parent
                        / "2026-07-25-blend-construction-screen-prereg.md")
    assert override_prereg != mod.PREREG_PATH
    assert override_prereg.exists()  # a different real committed prereg in this repo

    argv = ["research_objective_blend_confirm.py", "--seeds", "42,43,44",
            "--prereg-path", str(override_prereg), "--out", "x.json"]
    manifest = mod.build_manifest(
        data_dir=data_dir, argv=argv,
        run_started_at="2026-07-25T08:00:00+00:00",
        run_finished_at="2026-07-25T09:00:00+00:00", panel=_fake_panel(),
        prereg_path=override_prereg)

    assert manifest["prereg_path"] == str(override_prereg)
    # The contract (model#74 review round 4): the manifest must equal the
    # _prereg_freeze ground truth FOR THE OVERRIDDEN PATH — not merely differ
    # from the default's. (Asserting inequality of the two freeze commits was
    # a false assumption: two preregs can legitimately be frozen in the same
    # commit, and a shallow CI checkout can collapse their histories.)
    repo_dir = _SPEC_PATH.resolve().parents[1]
    ov_commit, ov_digest = mod._prereg_freeze(repo_dir, override_prereg)
    assert manifest["prereg_commit"] == ov_commit
    assert manifest["prereg_digest"] == (f"sha256:{ov_digest}" if ov_digest
                                         and not str(ov_digest).startswith("sha256:")
                                         else ov_digest)
    assert manifest["command"] == " ".join(argv)


def test_prereg_freeze_keys_off_the_path_argument_not_silently_ignored():
    """model#74 review round 4 P1: the equality check above compares the
    manifest to `_prereg_freeze(repo, override_prereg)` — a tautology if
    `_prereg_freeze` (or the `prereg_path` plumbing into it) silently ignored
    its argument and always resolved the default file, since both sides of
    the comparison would then drift identically. Close that gap directly: on
    a synthetic repo where two files are frozen in two DISTINCT commits,
    `_prereg_freeze` must return each file's own commit/digest, not the same
    pair for both."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo_dir = Path(td) / "repo"
        repo_dir.mkdir()
        _git(repo_dir, "init", "-q")
        _git(repo_dir, "config", "user.email", "test@example.com")
        _git(repo_dir, "config", "user.name", "Test")

        prereg_a = repo_dir / "a.md"
        prereg_a.write_text("# A\n\nSeeds 1/2/3.\n")
        _git(repo_dir, "add", "a.md")
        _git(repo_dir, "commit", "-q", "-m", "freeze a")
        commit_a = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                                  capture_output=True, text=True, check=True).stdout.strip()

        prereg_b = repo_dir / "b.md"
        prereg_b.write_text("# B\n\nSeeds 4/5/6.\n")
        _git(repo_dir, "add", "b.md")
        _git(repo_dir, "commit", "-q", "-m", "freeze b")
        commit_b = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                                  capture_output=True, text=True, check=True).stdout.strip()

        commit_from_a, digest_from_a = mod._prereg_freeze(repo_dir, prereg_a)
        commit_from_b, digest_from_b = mod._prereg_freeze(repo_dir, prereg_b)

        assert commit_from_a == commit_a
        assert commit_from_b == commit_b
        assert commit_from_a != commit_from_b
        assert digest_from_a != digest_from_b
