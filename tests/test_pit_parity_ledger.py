"""Tests for the PIT input-parity ledger (fail-closed, per-dimension)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from experiments.ensemble_phase0.backfill_scores import RunSelection
from experiments.ensemble_phase0.pit_parity_ledger import (
    DEFAULT_MAX_SKEW_SECONDS,
    compare_session,
)

SESSION = "2026-07-15"


def _mk_db(tmp_path: Path, name: str, run_id: str, bundle: dict | None,
           raw_json: str | None = None) -> Path:
    db = tmp_path / name
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE pipeline_runs (run_id TEXT, run_bundle_json TEXT)")
    payload = raw_json if raw_json is not None else (
        json.dumps(bundle) if bundle is not None else None)
    conn.execute("INSERT INTO pipeline_runs VALUES (?, ?)", (run_id, payload))
    conn.commit()
    conn.close()
    return db


def _bundle(**over) -> dict:
    base = {
        "schema_version": "v3",
        "data_max_dates": {"AAPL": "2026-07-15", "MSFT": "2026-07-15"},
        "regime_evidence": {"final_regime": "BULL_CALM"},
        "watchlist_hash": "wh", "watchlist_size": 2, "config_hash": "ch",
        "commit_path_fingerprint": "cpf",
    }
    base.update(over)
    return base


def _sel(run_id: str, created: str = "2026-07-15T19:00:00+00:00") -> RunSelection:
    return RunSelection(run_id=run_id, run_date=SESSION, created_at_utc=created)


_DB_SEQ = iter(range(10_000))


def _verdict(tmp_path, prod_bundle, shadow_bundle, *, prod_raw=None,
             shadow_raw=None, prod_sel=True, shadow_sel=True,
             shadow_created="2026-07-15T19:30:00+00:00", skew=DEFAULT_MAX_SKEW_SECONDS):
    seq = next(_DB_SEQ)  # unique filenames — a test may build several pairs
    prod_db = _mk_db(tmp_path, f"p{seq}.db", "p1", prod_bundle, prod_raw)
    shadow_db = _mk_db(tmp_path, f"s{seq}.db", "s1", shadow_bundle, shadow_raw)
    return compare_session(
        SESSION,
        _sel("p1") if prod_sel else None,
        _sel("s1", shadow_created) if shadow_sel else None,
        prod_db=prod_db, shadow_db=shadow_db, max_skew_seconds=skew,
    )


class TestParityVerdicts:

    def test_full_match_is_parity(self, tmp_path):
        v = _verdict(tmp_path, _bundle(), _bundle())
        assert v.verdict == "parity" and not v.reasons

    def test_missing_shadow_run_fails_closed(self, tmp_path):
        v = _verdict(tmp_path, _bundle(), _bundle(), shadow_sel=False)
        assert v.verdict == "not_parity"
        assert any("missing_shadow_run" in r for r in v.reasons)

    def test_unparseable_bundle_fails_closed(self, tmp_path):
        v = _verdict(tmp_path, _bundle(), None, shadow_raw="{not json")
        assert v.verdict == "not_parity"
        assert any("missing_shadow_bundle" in r for r in v.reasons)

    def test_missing_field_fails_closed(self, tmp_path):
        b = _bundle(); del b["regime_evidence"]
        v = _verdict(tmp_path, _bundle(), b)
        assert v.verdict == "not_parity"
        assert any("missing_shadow_fields" in r and "regime_evidence" in r
                   for r in v.reasons)

    def test_watermark_mismatch(self, tmp_path):
        v = _verdict(tmp_path, _bundle(),
                     _bundle(data_max_dates={"AAPL": "2026-07-14",
                                             "MSFT": "2026-07-15"}))
        assert v.verdict == "not_parity"
        assert any("watermark_mismatch_on_1_tickers" in r for r in v.reasons)

    def test_shadow_extra_ticker_breaks_subset(self, tmp_path):
        v = _verdict(tmp_path, _bundle(),
                     _bundle(data_max_dates={"AAPL": "2026-07-15",
                                             "MSFT": "2026-07-15",
                                             "ZZZ": "2026-07-15"}))
        assert v.verdict == "not_parity"
        assert "shadow_universe_not_subset_of_prod" in v.reasons

    def test_shadow_subset_is_ok(self, tmp_path):
        v = _verdict(tmp_path, _bundle(),
                     _bundle(data_max_dates={"AAPL": "2026-07-15"}))
        assert v.verdict == "parity"

    def test_regime_mismatch(self, tmp_path):
        v = _verdict(tmp_path, _bundle(),
                     _bundle(regime_evidence={"final_regime": "BEAR"}))
        assert v.verdict == "not_parity"
        assert "regime_mismatch_or_missing" in v.reasons

    def test_schema_version_mismatch(self, tmp_path):
        v = _verdict(tmp_path, _bundle(), _bundle(schema_version="v2"))
        assert v.verdict == "not_parity"
        assert "bundle_schema_mismatch" in v.reasons

    def test_skew_tolerance_boundary(self, tmp_path):
        # exactly at tolerance passes; one second over fails
        at = _verdict(tmp_path, _bundle(), _bundle(),
                      shadow_created="2026-07-15T20:00:00+00:00", skew=3600)
        assert at.verdict == "parity"
        over = _verdict(tmp_path, _bundle(), _bundle(),
                        shadow_created="2026-07-15T20:00:01+00:00", skew=3600)
        assert over.verdict == "not_parity"
        assert any("decision_skew" in r for r in over.reasons)

    def test_scorer_difference_never_enters_verdict(self, tmp_path):
        # config_hash / watchlist_hash / commit fingerprint differ (the
        # experimental variable) — parity must still hold.
        v = _verdict(tmp_path, _bundle(),
                     _bundle(config_hash="OTHER", watchlist_hash="OTHER",
                             commit_path_fingerprint="OTHER"))
        assert v.verdict == "parity"
        assert v.informational["config_hash"]["shadow"] == "OTHER"
