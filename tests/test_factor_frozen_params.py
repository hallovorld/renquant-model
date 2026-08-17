"""Frozen params pins for the simple-sort factor emitters (orch#984 §5/§5b).

The house pattern (see test_params_v0_mirrors_the_sealed_v1_runner): the
frozen modules are prereg content, frozen in the build PR BEFORE any scoring
run, and these pins are what make the freeze enforceable rather than
advisory. A value change here means a NEW params version (with its own
frozen module and validator), never an edit — if one of these fails, the
frozen module is what changed and this file is right.
"""
from __future__ import annotations

import pytest

from renquant_model_factors import (params_high52w_v0, params_lowbeta_v0,
                                    params_quality_gp_v0)
from renquant_model_factors import _frozen_params_high52w_v0 as FH
from renquant_model_factors import _frozen_params_lowbeta_v0 as FL
from renquant_model_factors import _frozen_params_quality_gp_v0 as FQ
from renquant_model_momentum import _frozen_params_v0 as FM


def test_high52w_v0_pins_the_frozen_literals():
    p = params_high52w_v0()
    assert p["params_version"] == "v0"
    pins = {"window": 252, "min_obs": 200, "names_per_date_floor": 50}
    assert {k: p[k] for k in pins} == pins
    assert "orch#984" in p["params_source"]


def test_lowbeta_v0_pins_the_frozen_literals():
    p = params_lowbeta_v0()
    assert p["params_version"] == "v0"
    pins = {"beta_window": 252, "min_obs": 200, "names_per_date_floor": 50}
    assert {k: p[k] for k in pins} == pins
    assert "orch#984" in p["params_source"]


def test_quality_gp_v0_pins_the_frozen_literals():
    p = params_quality_gp_v0()
    assert p["params_version"] == "v0"
    pins = {"min_obs": 1, "max_age_days": 400, "names_per_date_floor": 50}
    assert {k: p[k] for k in pins} == pins
    # The frozen recipe names the UPSTREAM Novy-Marx column — the field
    # audit lives in the frozen module's docstring; a different column is a
    # new params version, never a silent swap.
    assert p["source_column"] == "gross_profitability"
    assert "sec_fundamentals" in p["params_source"]
    assert "orch#984" in p["params_source"]


def test_high52w_v0_shares_the_momentum_v0_clock():
    """high52w is momentum's closest sibling BY DESIGN (orch#984 §4): the
    formation window, obs floor and names floor are momentum v0's own —
    held equal here so a drifted copy fails loudly instead of silently."""
    assert FH.WINDOW == FM.WINDOW
    assert FH.MIN_OBS == FM.MIN_OBS
    assert FH.NAMES_PER_DATE_FLOOR == FM.NAMES_PER_DATE_FLOOR


def test_lowbeta_v0_shares_the_momentum_v0_clock():
    assert FL.BETA_WINDOW == FM.WINDOW
    assert FL.MIN_OBS == FM.MIN_OBS
    assert FL.NAMES_PER_DATE_FLOOR == FM.NAMES_PER_DATE_FLOOR


def test_quality_gp_v0_shares_the_names_floor():
    assert FQ.NAMES_PER_DATE_FLOOR == FM.NAMES_PER_DATE_FLOOR


def test_frozen_modules_live_inside_the_package():
    """The wheel-self-sufficiency lesson (model#196 review): the constants a
    params block reads must ship IN the package, never a repo-root path."""
    from pathlib import Path

    import renquant_model_factors as pkg

    pkg_dir = Path(pkg.__file__).resolve().parent
    for mod in (FH, FL, FQ):
        assert Path(mod.__file__).resolve().is_relative_to(pkg_dir)


@pytest.mark.parametrize("params_fn, bad_key", [
    (params_high52w_v0, "window"),
    (params_lowbeta_v0, "beta_window"),
    (params_quality_gp_v0, "max_age_days"),
])
def test_v0_domain_validators_fail_closed(params_fn, bad_key):
    from renquant_model_factors.high52w import FACTOR as H
    from renquant_model_factors.lowbeta import FACTOR as L
    from renquant_model_factors.quality_gp import FACTOR as Q

    factor = {"window": H, "beta_window": L, "max_age_days": Q}[bad_key]
    with pytest.raises(ValueError, match=bad_key):
        factor.validate_params({**params_fn(), bad_key: 0})


def test_min_obs_larger_than_window_is_unsatisfiable():
    from renquant_model_factors.high52w import FACTOR as H

    with pytest.raises(ValueError, match="can never be satisfied"):
        H.validate_params({**params_high52w_v0(), "min_obs": 253})
