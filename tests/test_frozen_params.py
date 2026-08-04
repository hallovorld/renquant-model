

# --- v1_fast: held to the renquant-model#199 FROZEN literals (2026-08-03) ----
#
# No sealed runner exists for the fast clock; the ISSUE is the authority and
# this pin is what makes the freeze enforceable rather than advisory. A value
# change here means amending #199 FIRST.

def test_params_v1_fast_matches_the_frozen_issue():
    from renquant_model_momentum import params_v1_fast

    p = params_v1_fast()
    assert p["params_version"] == "v1_fast"
    assert p["window"] == 63            # 3-month formation (#199)
    assert p["skip"] == 5               # 1-week short-reversal skip (#199)
    assert p["min_obs"] == 50           # v0's ~79% coverage ratio on 63d (#199)
    assert p["min_features"] == 3       # identical to v0
    assert p["names_per_date_floor"] == 50  # identical to v0
    assert p["min_side_obs"] == 30      # identical to v0
    assert "renquant-model#199" in p["params_source"]


def test_v1_fast_and_v0_differ_ONLY_on_the_clock():
    """One construction, two clocks — every non-clock knob must stay equal, so
    a future 'tune' of the fast lane cannot smuggle in a different model."""
    from renquant_model_momentum import params_v0, params_v1_fast

    v0, vf = params_v0(), params_v1_fast()
    clock_keys = {"params_version", "window", "skip", "min_obs", "params_source"}
    for k in set(v0) | set(vf):
        if k in clock_keys:
            assert v0[k] != vf[k], f"{k} should differ between clocks"
        else:
            assert v0[k] == vf[k], f"{k} must be identical across clocks"
