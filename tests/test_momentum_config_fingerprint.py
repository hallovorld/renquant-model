"""The producer must stamp the identity the ADMISSION CHECK reads, in the form
the CONSUMER recomputes.

s104#95, measured 2026-08-07: the fast momentum artifact carried no top-level
`config_fingerprint`, so `model_admission._check_config_fingerprint` rejected
both fast blend legs with `missing_config_fingerprint` — one step BEFORE the
lane config's `expected_config_fingerprint` is compared. Backfilling the lane
configs, which is what s104#95 originally proposed, could not have fixed it.
"""
from __future__ import annotations

import json
import pytest

from renquant_model_momentum.train import params_config_fingerprint

PARAMS = {"window": 126, "skip": 5, "min_obs": 60, "min_side_obs": 10,
          "min_features": 2, "names_per_date_floor": 20,
          "params_source": "v1_fast", "params_version": "v1_fast"}


def test_config_fingerprint_matches_the_consumer_recipe():
    """THE contract. The consumer's copy lives in
    `renquant_pipeline.momentum_identity`, which exists so the umbrella's
    stdlib-only pinned-path CI can validate this string without importing
    pandas. Two copies are acceptable ONLY while a test pins them equal — this
    is that test. If it is ever skipped in CI, the equality is unenforced.
    """
    momentum_identity = pytest.importorskip(
        "renquant_pipeline.momentum_identity",
        reason="consumer copy unavailable — equality is UNENFORCED in this run")
    assert params_config_fingerprint(PARAMS) == \
        momentum_identity.params_fingerprint(PARAMS)


def test_the_form_is_momentum_version_digest():
    fp = params_config_fingerprint(PARAMS)
    head, ver, digest = fp.split("-", 2)
    assert head == "momentum"
    assert ver == "v1_fast", "params_version is read from INSIDE params"
    assert len(digest) == 16 and all(c in "0123456789abcdef" for c in digest)


def test_params_version_comes_from_inside_params_not_top_level():
    """I reported this key as absent by checking the wrong depth (s104#95).
    The ledger and `artifact_kind_for` both read it from inside `params`."""
    assert params_config_fingerprint({**PARAMS, "params_version": "v0"}) \
        .startswith("momentum-v0-")


def test_a_changed_param_changes_the_fingerprint():
    """Anti-vacuity: an identity that does not move with its inputs is not one."""
    assert params_config_fingerprint(PARAMS) != \
        params_config_fingerprint({**PARAMS, "window": 127})


def test_key_order_does_not_change_it():
    shuffled = dict(reversed(list(PARAMS.items())))
    assert params_config_fingerprint(shuffled) == params_config_fingerprint(PARAMS)


def test_the_emitted_artifact_carries_it_at_TOP_level():
    """`model_admission` reads `artifact.get("config_fingerprint")` — top level.
    A value nested under `params` would satisfy no consumer."""
    import inspect
    from renquant_model_momentum import train
    src = inspect.getsource(train)
    assert '"config_fingerprint": params_config_fingerprint(p),' in src, \
        "the artifact dict must stamp it as a TOP-LEVEL key"
