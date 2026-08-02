"""Slice-3 TEST evaluator tests: mirror fidelity + v2-machine parity golden,
the mandatory causal maturity contract, every refusal path (power/degenerate/
rho1/controls), the chained eval ledger (shared chain helper, duplicate
refusal), report completeness with types, and the CLI two-file protocol.

Synthetic fixtures ONLY — no IC/statistic is computed on real data anywhere
in this file; the single live-surface test is a LOUD env-skip and computes
NO statistic (dry-run resolves the window and hashes nothing).
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import pathlib
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_momentum import _v2_machine as M
from renquant_model_momentum.evaluate import (EVAL_KIND, EVAL_ROW_REQUIRED,
                                              append_eval_ledger,
                                              eligible_last_date,
                                              evaluate_momentum_artifact)
from renquant_model_momentum.ledger import (LedgerIntegrityError,
                                            append_chained_row,
                                            append_to_artifact_ledger,
                                            load_and_verify_ledger,
                                            row_sha256_of)
from renquant_model_momentum.train import content_sha256_of, params_v0

REPO = Path(__file__).resolve().parent.parent


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name,
                                                  REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V2 = _load_tool("goal7_momentum_v2_run")       # the sealed v2 runner
CLI = _load_tool("momentum_eval_run")          # the slice-3 CLI

LIVE = (CLI.PANEL_PATH.is_file() and CLI.SECTORS_PATH.is_file()
        and (CLI.OHLCV_ROOT / CLI.MARKET / "1d.parquet").is_file())
OFF_MACHINE = ("live RenQuant data surfaces absent (off-machine) — this test "
               "reads the live panel READ-ONLY (dates only, NO statistic) "
               "and cannot run in CI")

SHA_HEX = re.compile(r"^[0-9a-f]{64}$")

# Hand-pinned calendar facts (weekday arithmetic verified by hand, then
# measured once 2026-08-02): 2026-06-30 is a Tuesday; 21 business days back
# is Monday 2026-06-01; 22 back is Friday 2026-05-29.
ASOF = "2026-06-30"
BOUND_H20_S1 = "2026-06-01"
BOUND_H20_S2 = "2026-05-29"


# ---------------------------------------------------------------- fixtures --
def _mini_artifact(**overrides) -> dict:
    """A minimal, content-sha-valid momentum artifact for the evaluator."""
    art = {"kind": "momentum_residual_v0", "artifact_schema_version": 1,
           "cutoff_date": "2026-06-30", "params": params_v0(),
           "universe": ["AAA", "BBB"], "n_scored": 2,
           "inputs": {"read_digests": {}}}
    art.update(overrides)
    art["content_sha256"] = content_sha256_of(art)
    return art


def _dated(values, end: str = BOUND_H20_S1) -> pd.Series:
    """values -> a per-date series on a business-day calendar ENDING exactly
    at the h=20/settle=1 eligibility bound for eval_asof 2026-06-30."""
    vals = np.asarray(values, float)
    idx = pd.bdate_range(end=end, periods=len(vals))
    return pd.Series(vals, index=idx)


def _readers(series: pd.Series, digests: dict | None = None):
    if digests is None:
        h = hashlib.sha256()
        h.update(np.ascontiguousarray(series.to_numpy(float)).tobytes())
        h.update(",".join(str(i) for i in series.index).encode())
        digests = {"synthetic/per_date_series": h.hexdigest()}
    return CLI.SeriesReaders(series, digests)


def _eval(series, *, asof=ASOF, h=20, settle=1, artifact=None, **kw):
    return evaluate_momentum_artifact(
        artifact if artifact is not None else _mini_artifact(),
        eval_asof=asof, label_horizon_bdays=h,
        readers=_readers(series), settle_bdays=settle, **kw)


#: The parity fixture (seed measured 2026-08-02): 59 surviving blocks,
#: rho1 0.128 (< 0.25), positive rate 1.000, negative 0.025 — every valve
#: passes, so the full machine runs end to end.
def _parity_values() -> np.ndarray:
    return np.random.default_rng(20260801).normal(0.005, 0.05, 2378)


@pytest.fixture(scope="module")
def artifact():
    return _mini_artifact()


@pytest.fixture(scope="module")
def completed_report(artifact):
    return evaluate_momentum_artifact(
        artifact, eval_asof=ASOF, label_horizon_bdays=20,
        readers=_readers(_dated(_parity_values())), settle_bdays=1)


# ------------------------------------------------------- mirror fidelity ----
def test_mirror_is_byte_verbatim_against_the_sealed_v2_runner():
    """THE pin on the port: every mirrored pure piece must equal the sealed
    v2 runner's own source byte for byte (`_frozen_params_v0` precedent —
    the sealed runner stays the authority; if this fails, the mirror is what
    changed and the sealed runner is right)."""
    for name in ("partition_blocks", "block_stats", "_block_summary",
                 "one_sample_t", "t_bar", "run_controls"):
        assert inspect.getsource(getattr(M, name)) == \
            inspect.getsource(getattr(V2, name)), name
    assert inspect.getsource(M.sample_acf) == \
        inspect.getsource(V2.INF.sample_acf)
    assert M.FROZEN_V2 == V2.FROZEN_V2


def test_mirror_needs_nothing_outside_the_installed_package():
    """The wheel-sufficiency lesson (review round 1 on #196), applied to the
    evaluator: the whole package — evaluate included — must import and run
    from a tree with no tools/ anywhere above it."""
    import shutil
    import tempfile

    import renquant_model_momentum as pkg
    pkg_dir = Path(pkg.__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(pkg_dir, Path(tmp) / pkg_dir.name)
        out = subprocess.run(
            [sys.executable, "-c",
             "import numpy as np, pandas as pd\n"
             "from renquant_model_momentum.evaluate import "
             "evaluate_momentum_artifact, eligible_last_date\n"
             "from renquant_model_momentum._v2_machine import FROZEN_V2\n"
             "print(FROZEN_V2['base_seed'], "
             "eligible_last_date('2026-06-30', 20, 1).date())"],
            cwd=tmp, env={"PYTHONPATH": tmp, "PATH": "/usr/bin:/bin"},
            capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-600:]
        assert out.stdout.split() == ["20260801", "2026-06-01"], out.stdout


# --------------------------------------------------- v2-machine parity ------
def test_v2_machine_parity_golden(completed_report):
    """THE golden: on the same synthetic series, the evaluator's block means,
    df, sd, rho1, bar, control rates (per-rep string included), t, se and MDE
    EQUAL the sealed v2 runner's run_inference outputs — bitwise, since both
    sides execute the byte-verbatim machine on the same array."""
    vals = _parity_values()
    rep = completed_report
    v2rep, code = V2.run_inference(vals, vals.copy(), 0.0)
    assert code == 0 and v2rep["status"] == "COMPLETED"
    assert rep["status"] == "COMPLETED"

    for key in ("n_blocks_formed", "n_dropped", "n_surviving",
                "usable_counts", "block_means"):
        assert rep["blocks"][key] == v2rep["blocks_S"][key], key
    assert rep["df"] == v2rep["df"] == 58
    assert rep["realized_block_sd"] == v2rep["realized_block_sd"]
    assert rep["rho1_blocks"] == v2rep["rho1_blocks"]
    assert rep["bar"] == v2rep["bar"]
    for side in ("positive", "negative"):
        mine, theirs = rep["controls"][side], v2rep["controls"][side]
        for key in ("mu", "sd", "n", "bar", "base_seed", "n_reps", "n_clear",
                    "n_fail", "rate", "per_rep_clear", "ok"):
            assert mine[key] == theirs[key], f"{side}.{key}"
    assert rep["t_stat"] == v2rep["t_S"]
    assert rep["mean_blocks"] == v2rep["mean_ic_S_blocks"]
    assert rep["se_blocks"] == v2rep["se_blocks"]
    assert rep["mde"] == v2rep["mde"]
    assert rep["mean_dates"] == v2rep["mean_ic_S_dates"]


def test_parity_fixture_actually_exercises_the_full_machine(completed_report):
    """Positive control on the golden's fixture: every stage genuinely ran."""
    rep = completed_report
    assert rep["blocks"]["n_surviving"] == 59
    assert rep["controls"]["positive"]["ok"] is True
    assert rep["controls"]["negative"]["ok"] is True
    assert len(rep["controls"]["positive"]["per_rep_clear"]) == 1000
    assert rep["controls"]["positive"]["n_clear"] \
        + rep["controls"]["positive"]["n_fail"] == 1000
    assert abs(rep["rho1_blocks"]) < 0.25


def test_no_verdict_anywhere(completed_report):
    """Design §2: no gate, no verdict — raw gate outputs only. No report key
    carries a verdict and no v2 decision word appears anywhere."""
    def keys_of(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from keys_of(v)
    assert all("verdict" not in k for k in keys_of(completed_report))
    text = json.dumps(completed_report)
    for word in ("KILL", "RETAIN-F1", "RETAIN-S", "decision"):
        assert word not in text
    assert "capital promotion is NOT on this path" \
        in completed_report["interpretation_rule"]


# ------------------------------------------------- causal maturity contract -
def test_eligible_last_date_math_includes_settle():
    assert eligible_last_date(ASOF, 20, 1) == pd.Timestamp(BOUND_H20_S1)
    assert eligible_last_date(ASOF, 20, 2) == pd.Timestamp(BOUND_H20_S2)
    assert eligible_last_date(ASOF, 20, 0) == \
        pd.Timestamp(ASOF) - pd.tseries.offsets.BDay(20)


def test_maturity_refusal_names_the_boundary():
    """One date past the bound -> REFUSED-MATURITY naming the boundary; no
    statistic of any kind is computed."""
    series = _dated(np.full(200, 0.01), end="2026-06-02")  # 1 bday too new
    rep = _eval(series)
    assert rep["status"] == "REFUSED-MATURITY"
    assert BOUND_H20_S1 in rep["why"]
    assert rep["eligible_last_date"] == BOUND_H20_S1
    assert rep["n_immature_dates"] == 1
    assert rep["first_immature_date"] == "2026-06-02"
    for key in ("blocks", "t_stat", "controls", "df", "realized_block_sd"):
        assert key not in rep, f"{key} computed on refused input"


def test_maturity_bound_is_settle_aware():
    """The SAME series is eligible at settle=1 and refused at settle=2 —
    the settle term is live in the boundary, not decoration."""
    series = _dated(np.full(120, 0.01), end=BOUND_H20_S1)
    assert _eval(series, settle=1)["status"] != "REFUSED-MATURITY"
    rep2 = _eval(series, settle=2)
    assert rep2["status"] == "REFUSED-MATURITY"
    assert rep2["eligible_last_date"] == BOUND_H20_S2
    assert BOUND_H20_S2 in rep2["why"]


def test_report_carries_the_realized_eligible_interval(completed_report):
    series = _dated(_parity_values())
    assert completed_report["eligible_interval"] == {
        "first_date": str(series.index.min().date()),
        "last_date": str(series.index.max().date())}
    assert completed_report["eligible_interval"]["last_date"] == BOUND_H20_S1
    assert completed_report["n_dates"] == 2378


def test_maturity_refusal_is_not_ledgerable(tmp_path):
    series = _dated(np.full(50, 0.01), end="2026-06-15")
    rep = _eval(series)
    assert rep["status"] == "REFUSED-MATURITY"
    ledger = tmp_path / "eval_ledger.jsonl"
    with pytest.raises(LedgerIntegrityError, match="maturity"):
        append_eval_ledger(rep, ledger)
    assert not ledger.exists()


def test_unverified_artifact_is_refused_before_anything():
    bad = _mini_artifact()
    bad["n_scored"] = 99                        # sha NOT recomputed
    with pytest.raises(ValueError, match="content_sha256 mismatch"):
        _eval(_dated(np.full(50, 0.01)), artifact=bad)


@pytest.mark.parametrize("kwargs,match", [
    ({"h": 0}, "label_horizon_bdays"),
    ({"h": 20.0}, "label_horizon_bdays"),
    ({"settle": -1}, "settle_bdays"),
    ({"settle": True}, "settle_bdays"),
])
def test_bad_horizon_or_settle_refused(kwargs, match):
    with pytest.raises(ValueError, match=match):
        _eval(_dated(np.full(50, 0.01)), **kwargs)


def test_unsorted_or_duplicate_dates_refused():
    good = _dated(np.full(50, 0.01))
    shuffled = good.iloc[::-1]
    with pytest.raises(ValueError, match="sorted ascending"):
        _eval(shuffled)
    duped = pd.concat([good, good.iloc[[0]]]).sort_index()
    with pytest.raises(ValueError, match="duplicate dates"):
        _eval(duped)
    with pytest.raises(ValueError, match="DatetimeIndex"):
        _eval(pd.Series(np.full(50, 0.01)))


# ------------------------------------------------------- machine paths ------
def test_power_refusal_below_the_block_floor():
    """300 dates -> 8 blocks < the frozen 40 floor: POWER, controls NOT run,
    nothing downstream computed."""
    rep = _eval(_dated(np.random.default_rng(2).normal(0, 0.05, 300)))
    assert rep["status"] == "UNRESOLVED-POWER"
    assert rep["blocks"]["n_blocks_formed"] == 8
    assert "40" in rep["why"]
    for key in ("controls", "df", "realized_block_sd", "rho1_blocks", "bar",
                "t_stat", "mde"):
        assert key not in rep, f"{key} computed past the power gate"


def test_thin_blocks_dropped_and_counted():
    """v2 §2.2 verbatim behaviour: a block with <10 usable dates is dropped
    AND counted; the partition itself never shifts."""
    vals = _parity_values()
    vals[120:131] = np.nan            # block 3 keeps 9 usable dates (< 10)
    rep = _eval(_dated(vals))
    assert rep["blocks"]["n_blocks_formed"] == 59
    assert rep["blocks"]["n_dropped"] == 1
    assert rep["blocks"]["n_surviving"] == 58
    assert rep["blocks"]["usable_counts"][3] == 9
    assert len(rep["blocks"]["block_means"]) == 58


def test_degenerate_block_sd_published_and_refused():
    rep = _eval(_dated(np.full(2378, 0.01)))
    assert rep["status"] == "UNRESOLVED-METHOD"
    assert rep["realized_block_sd"] == 0.0      # PUBLISHED even when degenerate
    assert "degenerate" in rep["why"]
    for key in ("rho1_blocks", "controls", "t_stat"):
        assert key not in rep


def test_rho1_valve_refuses_dependent_blocks():
    """Block-level sine (measured rho1 0.696 >= 0.25): the geometry failed to
    buy independence -> METHOD; controls and the candidate t are NOT run."""
    vals = np.sin(2 * np.pi * (np.arange(2378) // 40) / 8.0) * 0.05 + 0.001
    rep = _eval(_dated(vals))
    assert rep["status"] == "UNRESOLVED-METHOD"
    assert abs(rep["rho1_blocks"]) >= 0.25
    assert "independence" in rep["why"]
    for key in ("controls", "t_stat", "bar"):
        assert key not in rep


def test_control_gate_violation_blocks_the_candidate_statistic():
    """Huge block dispersion (seed measured: positive rate 0.147 < 0.80):
    both controls are published WITH per-rep counts, and the candidate t is
    never evaluated — controls come BEFORE any candidate statistic."""
    rep = _eval(_dated(np.random.default_rng(3).normal(0.0, 1.5, 2378)))
    assert rep["status"] == "UNRESOLVED-METHOD"
    pos, neg = rep["controls"]["positive"], rep["controls"]["negative"]
    assert pos["ok"] is False and pos["rate"] < 0.80
    assert len(pos["per_rep_clear"]) == 1000 == len(neg["per_rep_clear"])
    assert pos["n_clear"] == pos["per_rep_clear"].count("1")
    assert neg["n_clear"] == neg["per_rep_clear"].count("1")
    for key in ("t_stat", "mean_blocks", "mde"):
        assert key not in rep, f"{key} computed despite the control violation"


def test_controls_are_the_frozen_pcg64_generator(completed_report):
    """The frozen generator, re-derived independently here: rep r =
    default_rng(20260801 + r).normal(mu, sd, n) through the one t formula."""
    ctl = completed_report["controls"]["positive"]
    sd, n, bar = ctl["sd"], ctl["n"], ctl["bar"]
    assert ctl["base_seed"] == 20260801
    for r in (0, 1, 999):
        draws = np.random.default_rng(20260801 + r).normal(0.04, sd, n)
        t = float(draws.mean() / (draws.std(ddof=1) / np.sqrt(n)))
        assert ctl["per_rep_clear"][r] == ("1" if t >= bar else "0"), r


# ------------------------------------------------------ report contract -----
REQUIRED_FIELDS = {
    "kind": str, "eval_schema_version": int, "evaluated_at_utc": str,
    "eval_asof": str, "label_horizon_bdays": int, "settle_bdays": int,
    "eligible_last_date": str, "maturity_rule": str, "eligible_interval": dict,
    "n_dates": int, "artifact_content_sha256": str, "artifact_kind": str,
    "artifact_cutoff_date": str, "inputs": dict, "frozen": dict,
    "interpretation_rule": str, "blocks": dict, "df": int,
    "realized_block_sd": float, "rho1_blocks": float, "bar": float,
    "controls": dict, "status": str, "t_stat": float, "mean_blocks": float,
    "se_blocks": float, "mde": float, "mean_dates": float,
    "content_sha256": str,
}


def test_report_field_completeness_and_types(completed_report):
    for field, typ in REQUIRED_FIELDS.items():
        assert field in completed_report, f"missing {field}"
        assert isinstance(completed_report[field], typ), \
            f"{field}: {type(completed_report[field]).__name__} != {typ.__name__}"
    assert completed_report["kind"] == EVAL_KIND
    assert SHA_HEX.match(completed_report["content_sha256"])
    assert SHA_HEX.match(completed_report["artifact_content_sha256"])
    for name, sha in completed_report["inputs"]["read_digests"].items():
        assert isinstance(name, str) and SHA_HEX.match(sha)
    frozen = completed_report["frozen"]
    assert frozen["h"] == frozen["gap"] == 20
    assert frozen["min_surviving_blocks"] == 40
    assert frozen["base_seed"] == 20260801
    assert "mde_ceiling" not in frozen      # decision-map constant: NOT used
    assert "h1_mean_min" not in frozen


def test_report_strict_json_round_trip(completed_report):
    text = json.dumps(completed_report, allow_nan=False)  # raises on NaN/Inf
    back = json.loads(text)
    assert back == completed_report
    assert isinstance(back["blocks"]["block_means"], list)
    assert isinstance(back["blocks"]["usable_counts"], list)


def test_report_content_sha_verifies_and_detects_tamper(completed_report):
    body = {k: v for k, v in completed_report.items() if k != "content_sha256"}
    assert content_sha256_of(body) == completed_report["content_sha256"]
    tampered = json.loads(json.dumps(completed_report))
    tampered["t_stat"] += 1.0
    assert content_sha256_of(tampered) != tampered["content_sha256"]


def test_caller_context_is_carried_verbatim(artifact):
    rep = _eval(_dated(np.full(60, 0.01)),
                context={"label_column": "fwd_20d_excess",
                         "n_thin_dates_skipped": 3})
    assert rep["caller_context"] == {"label_column": "fwd_20d_excess",
                                    "n_thin_dates_skipped": 3}


# ------------------------------------------------------------- eval ledger --
def test_eval_ledger_chain_appends_and_verifies(tmp_path, artifact,
                                                completed_report):
    ledger = tmp_path / "eval_ledger.jsonl"
    r0 = append_eval_ledger(completed_report, ledger)
    later = evaluate_momentum_artifact(
        artifact, eval_asof=pd.Timestamp(ASOF) + pd.tseries.offsets.BDay(1),
        label_horizon_bdays=20,
        readers=_readers(_dated(_parity_values())), settle_bdays=1)
    r1 = append_eval_ledger(later, ledger)
    rows = load_and_verify_ledger(ledger, required_fields=EVAL_ROW_REQUIRED)
    assert [r["row_index"] for r in rows] == [0, 1]
    assert rows[0]["prev_row_sha"] is None
    assert rows[1]["prev_row_sha"] == rows[0]["row_sha"]
    assert rows[0]["row_sha"] == row_sha256_of(rows[0]) == r0["row_sha"]
    assert rows[1]["row_sha"] == r1["row_sha"]
    assert rows[0]["report"] == completed_report
    assert rows[0]["report_content_sha256"] \
        == completed_report["content_sha256"]
    assert rows[0]["status"] == "COMPLETED"


def test_eval_ledger_refuses_duplicate_key(tmp_path, completed_report):
    """One evaluation per (artifact_sha, eval_asof, horizon) — a re-run is a
    dispute to investigate, never a rewrite."""
    ledger = tmp_path / "eval_ledger.jsonl"
    append_eval_ledger(completed_report, ledger)
    with pytest.raises(LedgerIntegrityError, match="already exists"):
        append_eval_ledger(completed_report, ledger)
    assert len(ledger.read_text().splitlines()) == 1


def test_eval_ledger_admits_same_key_at_a_different_horizon(tmp_path,
                                                            artifact):
    """The horizon is part of the key: h=60 on the same artifact + as-of
    appends fine (and a POWER refusal IS ledgerable evidence — 2378 dates
    give 20 blocks at h=60, under the 40 floor)."""
    ledger = tmp_path / "eval_ledger.jsonl"
    series = _dated(_parity_values())
    asof60 = series.index[-1] + pd.tseries.offsets.BDay(61)
    rep20 = evaluate_momentum_artifact(
        artifact, eval_asof=asof60, label_horizon_bdays=20,
        readers=_readers(series), settle_bdays=1)
    append_eval_ledger(rep20, ledger)
    rep60 = evaluate_momentum_artifact(
        artifact, eval_asof=asof60, label_horizon_bdays=60,
        readers=_readers(series), settle_bdays=1)
    assert rep60["status"] == "UNRESOLVED-POWER"
    row = append_eval_ledger(rep60, ledger)     # same artifact + asof, h=60
    assert row["row_index"] == 1
    assert row["label_horizon_bdays"] == 60
    assert row["status"] == "UNRESOLVED-POWER"


def test_eval_ledger_refuses_rewritten_history(tmp_path, completed_report):
    ledger = tmp_path / "eval_ledger.jsonl"
    append_eval_ledger(completed_report, ledger)
    row = json.loads(ledger.read_text())
    row["status"] = "COMPLETED-BETTER"          # rewrite an existing row
    ledger.write_text(json.dumps(row, sort_keys=True,
                                 separators=(",", ":")) + "\n")
    with pytest.raises(LedgerIntegrityError, match="edited after"):
        load_and_verify_ledger(ledger, required_fields=EVAL_ROW_REQUIRED)


def test_eval_ledger_refuses_tampered_report(tmp_path, completed_report):
    bad = json.loads(json.dumps(completed_report))
    bad["t_stat"] += 1.0                        # sha NOT recomputed
    with pytest.raises(LedgerIntegrityError, match="content_sha256"):
        append_eval_ledger(bad, tmp_path / "eval_ledger.jsonl")
    assert not (tmp_path / "eval_ledger.jsonl").exists()


def test_chain_helper_is_shared_not_duplicated():
    """Slice-3 contract: ONE chain implementation. Both ledgers' appends bind
    the same function object, and the eval module defines no chain of its
    own."""
    import renquant_model_momentum.evaluate as E
    import renquant_model_momentum.ledger as L
    assert E.append_chained_row is L.append_chained_row
    assert E.load_and_verify_ledger is L.load_and_verify_ledger
    src = inspect.getsource(E)
    for token in ("row_sha256_of", '"row_index":', '"prev_row_sha":'):
        assert token not in src, \
            f"evaluate.py re-implements chain mechanics ({token})"


def test_train_ledger_still_chains_through_the_shared_helper(tmp_path,
                                                             monkeypatch):
    """Regression for the slice-2 ledger refactor: the artifact ledger routes
    through append_chained_row and its rows verify unchanged."""
    import renquant_model_momentum.ledger as L
    calls = []
    real = L.append_chained_row

    def _spy(body, path, **kw):
        calls.append(dict(body))
        return real(body, path, **kw)
    monkeypatch.setattr(L, "append_chained_row", _spy)
    art = _mini_artifact()
    ledger = tmp_path / "artifact_ledger.jsonl"
    row = append_to_artifact_ledger(art, ledger)
    assert len(calls) == 1
    assert calls[0]["artifact_content_sha256"] == art["content_sha256"]
    assert load_and_verify_ledger(ledger)[0]["row_sha"] == row["row_sha"]


def test_chain_helper_refuses_forged_chain_fields(tmp_path):
    with pytest.raises(LedgerIntegrityError, match="chain-stamped"):
        append_chained_row({"kind": "x", "row_index": 7},
                           tmp_path / "l.jsonl",
                           required_fields=("row_index", "row_sha", "kind"))
    assert not (tmp_path / "l.jsonl").exists()


# --------------------------------------------------------------------- CLI --
def _fake_surfaces(monkeypatch, tmp_path, label_cols=("fwd_20d_excess",)):
    """Point the CLI at tmp-path surface stubs; the series builder is
    monkeypatched per-test (the real one computes IC — synthetic only)."""
    ohlcv_market_dir = tmp_path / "ohlcv" / CLI.MARKET
    ohlcv_market_dir.mkdir(parents=True)
    (ohlcv_market_dir / "1d.parquet").touch()
    sectors_path = tmp_path / "sectors.json"
    sectors_path.write_text("{}")
    panel_path = tmp_path / "panel.parquet"
    panel_path.touch()
    monkeypatch.setattr(CLI, "PANEL_PATH", panel_path)
    monkeypatch.setattr(CLI, "SECTORS_PATH", sectors_path)
    monkeypatch.setattr(CLI, "OHLCV_ROOT", tmp_path / "ohlcv")
    monkeypatch.setattr(CLI, "_panel_columns",
                        lambda p: ["ticker", "date", *label_cols])
    return tmp_path / "out"


def _synthetic_builder(series, digests=None, counts=None):
    def _build(artifact, *, label_col, last_eligible, first_date=None):
        eligible = series[series.index <= pd.Timestamp(last_eligible)] \
            if getattr(_build, "truncate", True) else series
        return (eligible,
                digests or {"synthetic/per_date_series": "ab" * 32},
                counts or {"n_panel_dates": len(series),
                           "n_eligible_dates": len(eligible),
                           "n_thin_dates_skipped": 0})
    return _build


def _write_artifact(tmp_path) -> Path:
    p = tmp_path / "artifact.json"
    p.write_text(json.dumps(_mini_artifact(), sort_keys=True))
    return p


def _report_name(art_path, horizon: int = 20) -> str:
    """The CLI's own basename rule, derived rather than restated (round 1: the path
    now carries artifact identity, so a hardcoded name would pin one artifact)."""
    art = json.loads(pathlib.Path(art_path).read_text(encoding="utf-8"))
    return CLI.report_basename(horizon, art["content_sha256"])


def _cli_args(tmp_path, out_root, art_path, **over):
    args = {"--artifact": str(art_path), "--eval-asof": ASOF,
            "--horizon": "20", "--out-root": str(out_root)}
    args.update(over)
    return [x for kv in args.items() for x in kv]


def test_cli_refuses_missing_artifact(tmp_path, capsys):
    rc = CLI.main(["--artifact", str(tmp_path / "absent.json"),
                   "--eval-asof", ASOF, "--horizon", "20",
                   "--out-root", str(tmp_path / "out")])
    assert rc == 3
    assert "REFUSED-ARTIFACT" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_cli_refuses_tampered_artifact(tmp_path, capsys):
    art = _mini_artifact()
    art["n_scored"] = 99                        # sha NOT recomputed
    p = tmp_path / "artifact.json"
    p.write_text(json.dumps(art))
    rc = CLI.main(["--artifact", str(p), "--eval-asof", ASOF,
                   "--horizon", "20", "--out-root", str(tmp_path / "out")])
    assert rc == 3
    assert "content-sha" in capsys.readouterr().out


def test_cli_refuses_when_surfaces_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(CLI, "PANEL_PATH", tmp_path / "absent.parquet")
    rc = CLI.main(["--artifact", str(_write_artifact(tmp_path)),
                   "--eval-asof", ASOF, "--horizon", "20",
                   "--out-root", str(tmp_path / "out")])
    assert rc == 3
    assert "REFUSED-SURFACES-MISSING" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_cli_refuses_unwired_label_column(monkeypatch, capsys, tmp_path):
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    rc = CLI.main(_cli_args(tmp_path, out_root, _write_artifact(tmp_path),
                            **{"--horizon": "60"}))
    assert rc == 3
    out = capsys.readouterr().out
    assert "REFUSED-LABEL-COLUMN" in out
    assert "fwd_60d_excess" in out
    assert not out_root.exists()


def test_eligible_dates_truncates_at_the_bound_and_first_date():
    dates = pd.bdate_range("2026-05-20", "2026-06-10")
    got = CLI._eligible_dates(dates, pd.Timestamp(BOUND_H20_S1))
    assert got.max() == pd.Timestamp(BOUND_H20_S1)
    assert (got <= pd.Timestamp(BOUND_H20_S1)).all()
    got2 = CLI._eligible_dates(dates, pd.Timestamp(BOUND_H20_S1),
                               first_date="2026-05-27")
    assert got2.min() == pd.Timestamp("2026-05-27")
    # unsorted + duplicated input comes out sorted-unique
    messy = list(dates[::-1]) + [dates[0]]
    got3 = CLI._eligible_dates(messy, pd.Timestamp(BOUND_H20_S1))
    assert got3.is_monotonic_increasing and not got3.has_duplicates


def test_cli_end_to_end_two_file_protocol(monkeypatch, capsys, tmp_path):
    """Synthetic e2e: report finalized + ledger row appended; the report on
    disk verifies and the printed summary carries the ledger row."""
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    art_path = _write_artifact(tmp_path)
    series = _dated(_parity_values())
    monkeypatch.setattr(CLI, "build_per_date_series",
                        _synthetic_builder(series))
    rc = CLI.main(_cli_args(tmp_path, out_root, art_path))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "COMPLETED"
    report_path = out_root / ASOF / _report_name(art_path)
    assert report_path.is_file()
    report = json.loads(report_path.read_text())
    assert content_sha256_of(report) == report["content_sha256"]
    assert report["caller_context"]["label_column"] == "fwd_20d_excess"
    rows = load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME,
                                  required_fields=EVAL_ROW_REQUIRED)
    assert len(rows) == 1
    assert rows[0]["report_content_sha256"] == report["content_sha256"]
    assert not any((out_root / ASOF).glob("*.tmp"))


def test_cli_finalizes_report_before_ledger_append(monkeypatch, tmp_path):
    """Two-file protocol invariant (TRAIN CLI's #196 round-3 order): by the
    time append_eval_ledger is called, the final-named report already exists
    and no staging file remains."""
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    art_path = _write_artifact(tmp_path)
    monkeypatch.setattr(CLI, "build_per_date_series",
                        _synthetic_builder(_dated(_parity_values())))
    report_path = out_root / ASOF / _report_name(art_path)
    real_append = CLI.append_eval_ledger
    seen = {}

    def _spy(report, ledger_path):
        seen["report_exists_at_append_time"] = report_path.is_file()
        seen["no_tmp_at_append_time"] = \
            not any(report_path.parent.glob("*.tmp"))
        return real_append(report, ledger_path)
    monkeypatch.setattr(CLI, "append_eval_ledger", _spy)
    assert CLI.main(_cli_args(tmp_path, out_root, art_path)) == 0
    assert seen["report_exists_at_append_time"] is True
    assert seen["no_tmp_at_append_time"] is True


def test_cli_second_run_refuses_ledgered_report(monkeypatch, capsys,
                                                tmp_path):
    """The inverse guard on the round-1 identity fix: the SAME triple twice
    is still the append-only duplicate refusal — the embedded-sha identity
    check passes (same artifact), then the ledgered-duplicate refusal
    fires."""
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    art_path = _write_artifact(tmp_path)
    monkeypatch.setattr(CLI, "build_per_date_series",
                        _synthetic_builder(_dated(_parity_values())))
    assert CLI.main(_cli_args(tmp_path, out_root, art_path)) == 0
    capsys.readouterr()
    rc = CLI.main(_cli_args(tmp_path, out_root, art_path))
    out = capsys.readouterr().out
    assert rc == 4
    assert "REFUSED-REPORT-EXISTS" in out
    assert "append-only" in out, \
        "same-triple rerun must hit the duplicate refusal, not the " \
        "artifact-mismatch refusal"
    assert len(load_and_verify_ledger(
        out_root / CLI.LEDGER_BASENAME,
        required_fields=EVAL_ROW_REQUIRED)) == 1


def test_cli_ledger_refusal_leaves_a_reconcilable_report(monkeypatch, capsys,
                                                         tmp_path):
    """A ledger refusal after finalize leaves the report on disk; the retry
    RECONCILES (appends the row for the exact bytes on disk) — never
    re-evaluates."""
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    art_path = _write_artifact(tmp_path)
    monkeypatch.setattr(CLI, "build_per_date_series",
                        _synthetic_builder(_dated(_parity_values())))
    real_append = CLI.append_eval_ledger
    calls = {"n": 0}

    def _flaky(report, ledger_path):
        if calls["n"] == 0:
            calls["n"] += 1
            raise LedgerIntegrityError("transient: simulated tampered ledger")
        return real_append(report, ledger_path)
    monkeypatch.setattr(CLI, "append_eval_ledger", _flaky)

    rc = CLI.main(_cli_args(tmp_path, out_root, art_path))
    assert rc == 5
    assert "REFUSED-LEDGER" in capsys.readouterr().out
    report_path = out_root / ASOF / _report_name(art_path)
    assert report_path.is_file()
    original_sha = json.loads(report_path.read_text())["content_sha256"]
    assert load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME,
                                  required_fields=EVAL_ROW_REQUIRED) == []

    rc = CLI.main(_cli_args(tmp_path, out_root, art_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert "RECONCILED" in out
    assert json.loads(report_path.read_text())["content_sha256"] \
        == original_sha, "reconciliation must not re-evaluate"
    rows = load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME,
                                  required_fields=EVAL_ROW_REQUIRED)
    assert len(rows) == 1 and rows[0]["report_content_sha256"] == original_sha


def test_cli_maturity_refusal_writes_nothing(monkeypatch, capsys, tmp_path):
    """A builder that drifts past the bound (simulated) hits the CORE's
    refusal: exit 3, no report file, no ledger row — the belt failed and the
    suspenders held."""
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    art_path = _write_artifact(tmp_path)
    immature = _dated(np.full(100, 0.01), end="2026-06-05")
    builder = _synthetic_builder(immature)
    builder.truncate = False                    # simulate the drifted filter
    monkeypatch.setattr(CLI, "build_per_date_series", builder)
    rc = CLI.main(_cli_args(tmp_path, out_root, art_path))
    out = capsys.readouterr().out
    assert rc == 3
    assert "REFUSED-MATURITY" in out
    assert BOUND_H20_S1 in out
    assert not (out_root / ASOF).exists()
    assert not (out_root / CLI.LEDGER_BASENAME).exists()


@pytest.mark.skipif(not LIVE, reason=OFF_MACHINE)
def test_cli_dry_run_smoke_on_live_surfaces(tmp_path):
    """READ-ONLY smoke, NO statistic: --dry-run resolves the eligible window
    against the live panel (dates + schema only) and writes NOTHING."""
    art_path = _write_artifact(tmp_path)
    out_root = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "momentum_eval_run.py"),
         "--artifact", str(art_path), "--eval-asof", ASOF,
         "--horizon", "20", "--dry-run", "--out-root", str(out_root)],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    rep = json.loads(proc.stdout)
    assert rep["dry_run"] is True
    assert rep["eligible_last_date"] == BOUND_H20_S1
    assert rep["label_column"] == "fwd_20d_excess"
    assert rep["n_eligible_dates"] > 0
    assert "none" in rep["statistics_computed"]
    assert not out_root.exists(), "--dry-run wrote something"


# --- review round 1: identity is (artifact, eval_asof, horizon) ----------------------

def test_TWO_ARTIFACTS_same_asof_and_horizon_get_SEPARATE_reports(
        monkeypatch, tmp_path, capsys):
    """The regression the review asked for.

    Ledger identity is `(artifact_content_sha256, eval_asof, label_horizon_bdays)`, but
    the report basename was `momentum_eval_h{h}.json` — no artifact in it. So a second
    artifact evaluated on the same date and horizon resolved to the FIRST one's path and
    was reconciled-or-refused against it instead of writing its own report. That is every
    recurring comparison and every post-retrain re-evaluation on the same date.

    Both artifacts here are content-sha-valid and genuinely distinct (different
    `cutoff_date`), and both must land — separate files, two ledger rows, append-only
    intact.
    """
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    a1 = tmp_path / "artifact_a.json"
    a1.write_text(json.dumps(_mini_artifact(), sort_keys=True))
    a2 = tmp_path / "artifact_b.json"
    a2.write_text(json.dumps(_mini_artifact(cutoff_date="2026-05-29"), sort_keys=True))

    sha1 = json.loads(a1.read_text())["content_sha256"]
    sha2 = json.loads(a2.read_text())["content_sha256"]
    assert sha1 != sha2, "the fixture artifacts are not distinct"

    series = _dated(_parity_values())
    monkeypatch.setattr(CLI, "build_per_date_series", _synthetic_builder(series))

    for art in (a1, a2):
        rc = CLI.main(_cli_args(tmp_path, out_root, art))
        out = json.loads(capsys.readouterr().out)
        assert rc == 0, out
        assert out["status"] == "COMPLETED", out

    p1 = out_root / ASOF / _report_name(a1)
    p2 = out_root / ASOF / _report_name(a2)
    assert p1 != p2, "both artifacts still resolve to one report path"
    assert p1.is_file() and p2.is_file()

    r1, r2 = (json.loads(p.read_text()) for p in (p1, p2))
    assert r1["artifact_content_sha256"] == sha1
    assert r2["artifact_content_sha256"] == sha2
    assert content_sha256_of(r1) == r1["content_sha256"]
    assert content_sha256_of(r2) == r2["content_sha256"]

    rows = load_and_verify_ledger(out_root / CLI.LEDGER_BASENAME,
                                  required_fields=EVAL_ROW_REQUIRED)
    shas = [r["artifact_content_sha256"] for r in rows]
    assert sorted(shas) == sorted([sha1, sha2]), shas


def test_the_basename_REFUSES_an_unusable_artifact_digest():
    """Fail-closed on the disambiguator itself: a missing or stub digest cannot be
    allowed to produce a path, or two artifacts silently share one again."""
    for bad in ("", None, "abc123"):
        with pytest.raises(ValueError, match="too short to identify"):
            CLI.report_basename(20, bad)
    good = CLI.report_basename(20, "a" * 64)
    assert good == "momentum_eval_h20_" + "a" * 12 + ".json"


def test_cli_reconcile_refuses_wrong_artifact_at_the_path(monkeypatch,
                                                          capsys, tmp_path):
    """Round 1, the reconcile half: identity keys on the report's EMBEDDED
    artifact_content_sha256 verified against the artifact being evaluated —
    the filename's 12-hex prefix is never trusted. A content-sha-valid
    report embedding a DIFFERENT artifact's sha planted at this artifact's
    path (prefix collision or tampering) is refused, never reconciled and
    never ledgered."""
    out_root = _fake_surfaces(monkeypatch, tmp_path)
    art_path = _write_artifact(tmp_path)
    monkeypatch.setattr(CLI, "build_per_date_series",
                        _synthetic_builder(_dated(_parity_values())))

    # A report genuinely evaluated for a DIFFERENT artifact, planted at THIS
    # artifact's path with a VALID self-sha — only the embedded identity is
    # wrong; the filename would happily lie.
    other = _mini_artifact(cutoff_date="2026-06-23")
    forged = evaluate_momentum_artifact(
        other, eval_asof=ASOF, label_horizon_bdays=20,
        readers=_readers(_dated(_parity_values())), settle_bdays=1)
    report_path = out_root / ASOF / _report_name(art_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(forged, sort_keys=True))

    rc = CLI.main(_cli_args(tmp_path, out_root, art_path))
    out = capsys.readouterr().out
    assert rc == 4
    assert "REFUSED-REPORT-EXISTS" in out
    assert "embeds artifact sha" in out
    assert other["content_sha256"] in out, \
        "the refusal must name the embedded sha it found"
    assert not (out_root / CLI.LEDGER_BASENAME).exists(), \
        "the wrong artifact's report must never be ledgered"
    assert json.loads(report_path.read_text()) == forged, \
        "the planted report must not be overwritten"
