"""Simple-sort factor emitters (G-I MoE impl step 1, orch#984 §4–5).

Synthetic frames ONLY — every number a test asserts is computable by hand
from the fixture's construction. All ledger tests run in tmp dirs; nothing
touches RenQuant or any production path.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from renquant_model_factors import (append_to_artifact_ledger,
                                    build_high52w_artifact,
                                    build_lowbeta_artifact,
                                    build_quality_gp_artifact,
                                    factor_config_fingerprint,
                                    load_and_verify_ledger,
                                    params_high52w_v0, params_lowbeta_v0,
                                    params_quality_gp_v0,
                                    verify_artifact_content_sha)
from renquant_model_momentum.ledger import LedgerIntegrityError

N_DAYS = 300
DATES = pd.bdate_range("2025-06-02", periods=N_DAYS)
CUTOFF = DATES[-1]

# SPY: deterministic alternating returns (+1% / -0.5%) — the OLS slope of a
# ticker whose returns are EXACTLY k × SPY's is exactly k, by construction.
_SPY_RETS = np.where(np.arange(N_DAYS - 1) % 2 == 0, 0.01, -0.005)
_SPY = pd.Series(100.0 * np.concatenate([[1.0], np.cumprod(1.0 + _SPY_RETS)]),
                 index=DATES)


def _geometric(start: float, k: float) -> pd.Series:
    """Close series whose daily returns are exactly k × SPY's."""
    return pd.Series(
        start * np.concatenate([[1.0], np.cumprod(1.0 + k * _SPY_RETS)]),
        index=DATES)


class Readers:
    """Stub FactorReaders over hand-constructed frames (synthetic only)."""

    def __init__(self, closes=None, fundamentals=None):
        self._closes = closes or {}
        self._fundamentals = fundamentals or {}

    def close(self, ticker):
        return self._closes.get(ticker)

    def market_close(self):
        return _SPY

    def fundamental(self, ticker):
        return self._fundamentals.get(ticker)

    def read_digests(self):
        return {"synthetic": "0" * 64}


# ------------------------------------------------------------------ high52w --
@pytest.fixture()
def high52w_world():
    # AAA: flat 100 with a single spike to 125 inside the 252-day window
    # (index 100 -> window is DATES[48:]) => score = 100 / 125 = 0.8.
    aaa = pd.Series(100.0, index=DATES)
    aaa.iloc[100] = 125.0
    # BBB: strictly increasing => the cutoff close IS the max => score 1.0.
    bbb = pd.Series(np.linspace(50.0, 100.0, N_DAYS), index=DATES)
    # CCC: only 150 observations < min_obs=200 => NaN (fail-closed).
    ccc = pd.Series(80.0, index=DATES[-150:])
    return Readers(closes={"AAA": aaa, "BBB": bbb, "CCC": ccc})


@pytest.fixture()
def high52w_artifact(high52w_world):
    return build_high52w_artifact(CUTOFF, ["AAA", "BBB", "CCC", "DDD"],
                                  params_high52w_v0(), readers=high52w_world)


def test_high52w_scores_by_hand(high52w_artifact):
    s = high52w_artifact["scores"]
    assert abs(s["AAA"] - 0.8) < 1e-12          # RAW ratio, not a z-score
    assert abs(s["BBB"] - 1.0) < 1e-12
    assert s["CCC"] is None                     # NaN -> explicit null
    assert "DDD" not in s                       # missing series != NaN score


def test_high52w_min_obs_fails_closed(high52w_artifact):
    assert high52w_artifact["scores"]["CCC"] is None
    assert high52w_artifact["n_obs"]["CCC"] == 150
    assert high52w_artifact["n_missing_series"] == 1
    assert high52w_artifact["n_scored"] == 2


def test_high52w_artifact_contract(high52w_artifact):
    a = high52w_artifact
    assert a["kind"] == "factor_high52w_v0"
    assert a["cutoff_date"] == str(CUTOFF.date())
    assert a["cutoff_embargo_days"] == 0
    # MEASURED, not asserted: the newest close actually consumed.
    assert a["effective_train_cutoff_date"] == str(CUTOFF.date())
    assert a["config_fingerprint"].startswith("factor_high52w-v0-")
    assert a["params"] == params_high52w_v0()
    # 2 scored < the frozen floor of 50: the artifact SAYS so, still carries
    # the full construction — refusal belongs to the consumers.
    assert a["names_floor_ok"] is False
    assert a["universe"] == ["AAA", "BBB", "CCC", "DDD"]


def test_high52w_ignores_non_positive_closes(high52w_world):
    # A corrupt (negative) close inside the window is not an observation:
    # it neither enters the max nor counts toward min_obs.
    aaa = high52w_world._closes["AAA"].copy()
    aaa.iloc[200] = -1.0
    art = build_high52w_artifact(
        CUTOFF, ["AAA"], params_high52w_v0(),
        readers=Readers(closes={"AAA": aaa}))
    assert abs(art["scores"]["AAA"] - 0.8) < 1e-12
    assert art["n_obs"]["AAA"] == 251


# ------------------------------------------------------------------ lowbeta --
@pytest.fixture()
def lowbeta_world():
    return Readers(closes={
        "DDD": _geometric(50.0, 2.0),    # beta exactly 2   => score -2
        "EEE": _geometric(30.0, -0.5),   # beta exactly -0.5 => score +0.5
        "FFF": _geometric(10.0, 1.0).iloc[-100:],  # 99 pairs < 200 => NaN
    })


@pytest.fixture()
def lowbeta_artifact(lowbeta_world):
    return build_lowbeta_artifact(CUTOFF, ["DDD", "EEE", "FFF", "GGG"],
                                  params_lowbeta_v0(), readers=lowbeta_world)


def test_lowbeta_scores_by_hand(lowbeta_artifact):
    s = lowbeta_artifact["scores"]
    assert abs(s["DDD"] - (-2.0)) < 1e-9        # -beta_hat, RAW
    assert abs(s["EEE"] - 0.5) < 1e-9
    assert s["FFF"] is None


def test_lowbeta_min_obs_fails_closed(lowbeta_artifact):
    assert lowbeta_artifact["n_obs"]["FFF"] == 99
    assert lowbeta_artifact["scores"]["FFF"] is None
    assert lowbeta_artifact["n_missing_series"] == 1  # GGG has no series
    assert lowbeta_artifact["n_scored"] == 2


def test_lowbeta_uses_the_trailing_window_only(lowbeta_artifact):
    # 299 paired returns exist; the OLS must see exactly beta_window=252.
    assert lowbeta_artifact["n_obs"]["DDD"] == 252
    assert lowbeta_artifact["kind"] == "factor_lowbeta_v0"


def test_lowbeta_degenerate_market_fails_closed():
    """A flat SPY window cannot identify a slope — NaN, never a 0-beta."""
    flat = pd.Series(100.0, index=DATES)

    class FlatMarket(Readers):
        def market_close(self):
            return flat

    art = build_lowbeta_artifact(
        CUTOFF, ["DDD"], params_lowbeta_v0(),
        readers=FlatMarket(closes={"DDD": _geometric(50.0, 2.0)}))
    assert art["scores"]["DDD"] is None
    assert art["n_scored"] == 0


# --------------------------------------------------------------- quality_gp --
@pytest.fixture()
def quality_gp_world():
    return Readers(fundamentals={
        # Quarterly snapshots; newest (0.42) is 44 calendar days before the
        # cutoff (2026-08-14) — fresh, so score = 0.42 verbatim.
        "GGG": pd.Series([0.30, 0.35, 0.42],
                         index=pd.to_datetime(["2026-01-05", "2026-04-06",
                                               "2026-07-01"])),
        # Single snapshot ~2.6 years old > max_age_days=400 => NaN.
        "HHH": pd.Series([0.55], index=pd.to_datetime(["2024-01-05"])),
        # Snapshots exist but every value is NaN => zero observations => NaN.
        "KKK": pd.Series([np.nan, np.nan],
                         index=pd.to_datetime(["2026-01-05", "2026-07-01"])),
    })


@pytest.fixture()
def quality_gp_artifact(quality_gp_world):
    return build_quality_gp_artifact(CUTOFF, ["GGG", "HHH", "III", "KKK"],
                                     params_quality_gp_v0(),
                                     readers=quality_gp_world)


def test_quality_gp_serves_the_upstream_ratio_verbatim(quality_gp_artifact):
    # The score IS the upstream Novy-Marx column value — never recomputed,
    # never proxied (see _frozen_params_quality_gp_v0 for the field audit).
    assert abs(quality_gp_artifact["scores"]["GGG"] - 0.42) < 1e-12
    assert quality_gp_artifact["params"]["source_column"] == "gross_profitability"


def test_quality_gp_staleness_and_min_obs_fail_closed(quality_gp_artifact):
    a = quality_gp_artifact
    assert a["scores"]["HHH"] is None      # stale beyond 400 calendar days
    assert a["n_obs"]["HHH"] == 1
    assert a["scores"]["KKK"] is None      # all-NaN series: 0 observations
    assert a["n_obs"]["KKK"] == 0
    assert a["n_missing_series"] == 1      # III has no series at all
    assert a["n_scored"] == 1


def test_quality_gp_measures_the_snapshot_date(quality_gp_artifact):
    # last_read is the newest QUALIFYING snapshot — for annual/quarterly
    # filers it legitimately trails the cutoff; it is measured, not asserted.
    a = quality_gp_artifact
    assert a["kind"] == "factor_quality_gp_v0"
    assert a["effective_train_cutoff_date"] == "2026-07-01"


# ------------------------------------------------- identity + shared machine --
def test_config_fingerprint_is_stable_and_param_sensitive():
    p = params_high52w_v0()
    fp = factor_config_fingerprint("high52w", p)
    # Stable across calls and key order (canonical JSON).
    assert fp == factor_config_fingerprint("high52w", dict(reversed(list(p.items()))))
    # Any param change is a NEW recipe.
    assert fp != factor_config_fingerprint("high52w", {**p, "window": 251})
    # ...and the factor name is part of the identity.
    assert fp != factor_config_fingerprint("lowbeta", p)
    assert fp.startswith("factor_high52w-v0-")
    assert len(fp.rsplit("-", 1)[1]) == 16


def test_content_sha_round_trip_and_tamper(high52w_artifact):
    verify_artifact_content_sha(high52w_artifact)
    tampered = json.loads(json.dumps(high52w_artifact))
    tampered["n_scored"] += 1
    with pytest.raises(ValueError, match="content_sha256 mismatch"):
        verify_artifact_content_sha(tampered)


def test_unsupported_params_version_fails_closed(high52w_world):
    with pytest.raises(ValueError, match="unsupported params_version"):
        build_high52w_artifact(
            CUTOFF, ["AAA"], {**params_high52w_v0(), "params_version": "v9"},
            readers=high52w_world)


def test_params_version_is_required(high52w_world):
    p = params_high52w_v0()
    del p["params_version"]
    with pytest.raises(ValueError, match="params_version"):
        build_high52w_artifact(CUTOFF, ["AAA"], p, readers=high52w_world)


def test_empty_universe_is_refused(high52w_world):
    with pytest.raises(ValueError, match="universe is empty"):
        build_high52w_artifact(CUTOFF, [], params_high52w_v0(),
                               readers=high52w_world)


def test_bool_is_not_an_int_param(high52w_world):
    with pytest.raises(ValueError, match="must be an int"):
        build_high52w_artifact(
            CUTOFF, ["AAA"], {**params_high52w_v0(), "window": True},
            readers=high52w_world)


# ------------------------------------------------------------------- ledger --
def _weekly(world, cutoff):
    return build_high52w_artifact(cutoff, ["AAA", "BBB"], params_high52w_v0(),
                                  readers=world)


def test_ledger_append_and_chain_verify(tmp_path, high52w_world):
    """The imported momentum ledger, driving a factor lane end-to-end."""
    ledger = tmp_path / "factor_high52w" / "ledger.jsonl"
    a1 = _weekly(high52w_world, DATES[-6])
    a2 = _weekly(high52w_world, CUTOFF)
    append_to_artifact_ledger(a1, ledger)
    append_to_artifact_ledger(a2, ledger)

    rows = load_and_verify_ledger(ledger)
    assert [r["row_index"] for r in rows] == [0, 1]
    assert rows[0]["prev_row_sha"] is None
    assert rows[1]["prev_row_sha"] == rows[0]["row_sha"]
    assert rows[0]["kind"] == "factor_high52w_v0"
    assert rows[0]["artifact_content_sha256"] == a1["content_sha256"]
    assert rows[1]["read_digests"] == {"synthetic": "0" * 64}


def test_ledger_refuses_duplicate_cutoff(tmp_path, high52w_world):
    ledger = tmp_path / "factor_high52w" / "ledger.jsonl"
    append_to_artifact_ledger(_weekly(high52w_world, CUTOFF), ledger)
    with pytest.raises(LedgerIntegrityError, match="already exists"):
        append_to_artifact_ledger(_weekly(high52w_world, CUTOFF), ledger)


def test_ledger_refuses_after_history_rewrite(tmp_path, high52w_world):
    ledger = tmp_path / "factor_high52w" / "ledger.jsonl"
    append_to_artifact_ledger(_weekly(high52w_world, DATES[-6]), ledger)
    append_to_artifact_ledger(_weekly(high52w_world, CUTOFF), ledger)
    lines = ledger.read_text().splitlines()
    row0 = json.loads(lines[0])
    row0["n_scored"] = 99  # rewrite history
    ledger.write_text("\n".join([json.dumps(row0, sort_keys=True,
                                            separators=(",", ":"))] +
                                lines[1:]) + "\n")
    with pytest.raises(LedgerIntegrityError):
        load_and_verify_ledger(ledger)


def test_one_kind_per_ledger_file(tmp_path, high52w_world, lowbeta_world):
    """The (cutoff_date, params_version) uniqueness key assumes a
    single-kind lane per file (like momentum vs momentum_fast) — a
    cross-kind append into the same file REFUSES rather than interleaving
    two factors' histories."""
    ledger = tmp_path / "factor_high52w" / "ledger.jsonl"
    append_to_artifact_ledger(_weekly(high52w_world, CUTOFF), ledger)
    stray = build_lowbeta_artifact(CUTOFF, ["DDD"], params_lowbeta_v0(),
                                   readers=lowbeta_world)
    with pytest.raises(LedgerIntegrityError, match="already exists"):
        append_to_artifact_ledger(stray, ledger)


def test_ledger_refuses_tampered_artifact(tmp_path, high52w_world):
    ledger = tmp_path / "factor_high52w" / "ledger.jsonl"
    art = _weekly(high52w_world, CUTOFF)
    art["n_scored"] += 1
    with pytest.raises(LedgerIntegrityError, match="refusing to ledger"):
        append_to_artifact_ledger(art, ledger)
    assert not ledger.exists()
