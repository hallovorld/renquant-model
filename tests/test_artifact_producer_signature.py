"""Which of three trainers produced this artifact — R3, made mechanical.

R3's cost line: *"I pointed a delegated retrain at the wrong twin TWICE before this was
settled; its metadata came out non-production-shaped (nthread: 14)."* It was settled by
reading two signatures by hand; this makes that read runnable so a third mis-pointing is
caught by running something rather than by remembering.

The verdict vocabulary is deliberately weak: `consistent_with`, never `produced_by`. A
signature is evidence about the SHAPE of the output, not a record of which process ran.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import artifact_producer_signature as P  # noqa: E402

ORCH = "orchestrator/train_gbdt.py"
UMB = "RenQuant/scripts/train_production_model.py"
NOTES = "alpha158 + SEC fund panel-LTR, self-contained subrepo training"
BASE_PARAMS = {"colsample_bytree": 0.7, "eta": 0.05, "max_depth": 5,
               "min_child_weight": 50, "objective": "rank:pairwise", "seed": 42,
               "subsample": 0.7, "verbosity": 0}


# ------------------------------------------------------------ the measured shape --
def test_the_served_shape_is_consistent_with_the_ORCHESTRATOR_trainer_only():
    r = P.classify({"training_notes": NOTES, "params": dict(BASE_PARAMS)})
    assert r["verdict"] == "consistent_with_exactly_one"
    assert r["consistent_with"] == [ORCH]
    assert UMB in r["ruled_out"]


def test_nthread_PRESENT_rules_the_orchestrator_shape_back_IN_not_out():
    """`train_gbdt.py` adds nthread only when `--nthread` is passed, so its presence does
    NOT rule the orchestrator out — it merely stops ruling the umbrella trainer out. Both
    then match, and the honest answer is undecidable."""
    r = P.classify({"training_notes": NOTES,
                    "params": dict(BASE_PARAMS, nthread=14)})
    assert ORCH in r["consistent_with"]
    assert r["verdict"] == "undecidable"


def test_matching_SEVERAL_profiles_is_UNDECIDABLE_not_a_pick():
    r = P.classify({"training_notes": NOTES, "params": dict(BASE_PARAMS, nthread=14)})
    assert len(r["consistent_with"]) > 1 and r["verdict"] == "undecidable"


def test_matching_NONE_is_UNDECIDABLE_not_produced_by_none():
    """An artifact matching no profile has not been attributed — it has not been shown to
    come from outside the three."""
    r = P.classify({"training_notes": "something else", "params": {}})
    assert r["consistent_with"] == []
    assert r["verdict"] == "undecidable"


def test_a_DIFFERENT_notes_string_rules_the_orchestrator_out():
    r = P.classify({"training_notes": "other", "params": dict(BASE_PARAMS)})
    assert ORCH in r["ruled_out"]
    assert any("training_notes" in w for w in r["ruled_out"][ORCH])


# --------------------------------------------------------------------- robustness --
def test_MALFORMED_params_is_undecidable_not_a_crash():
    r = P.classify({"training_notes": NOTES, "params": "n/a"})
    assert r["verdict"] == "undecidable" and "not an object" in r["why"]


def test_absent_training_notes_does_not_raise():
    r = P.classify({"params": dict(BASE_PARAMS)})
    assert r["verdict"] in ("undecidable", "consistent_with_exactly_one")


def test_the_verdict_vocabulary_never_says_PRODUCED_BY():
    """The claim this tool is allowed to make is bounded, and the bound lives in the
    output rather than in a docstring nobody re-reads."""
    src = (TOOLS / "artifact_producer_signature.py").read_text()
    assert "produced_by" not in src
    r = P.classify({"training_notes": NOTES, "params": dict(BASE_PARAMS)})
    assert "consistent_with" in r and "never reports" in r["note"]


def test_each_profile_cites_its_source_line():
    """R3's registry citation had already drifted (228 -> 354). Citations that are not
    checkable rot silently, so each profile carries one."""
    for name, prof in P.PROFILES.items():
        assert prof["cited"] and ":" in prof["cited"], name


def test_exit_1_when_undecidable(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"training_notes": "x", "params": {}}))
    assert P.main(["--artifact", str(p)]) == 1


def test_exit_2_on_an_unreadable_artifact(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope")
    assert P.main(["--artifact", str(p)]) == 2
