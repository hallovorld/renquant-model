"""TEST core: the recurring evaluator over the v2 gap-block machine. (GOAL-7 slice 3)

Implements §2 (TEST) of the momentum pipeline architecture
(doc/design/2026-08-02-momentum-pipeline-architecture.md): the validated v2
machinery (model#192/#193) as a REUSABLE, RECURRING evaluator — same block
geometry, same degenerate-sd and rho_1 valves, same positive/negative controls
with published per-rep counts — parameterized over the evaluation window and
the label horizon. The machine's pure pieces are the byte-verbatim packaged
mirror ``_v2_machine`` (see its docstring for why a mirror); this module never
re-states a formula.

NO GATE, NO VERDICT (design §2): the report carries the raw gates' outputs
only (power-adequacy, controls, block-t/bar/MDE). Statuses mirror the v2
runner's vocabulary — ``UNRESOLVED-POWER`` / ``UNRESOLVED-METHOD`` /
``COMPLETED`` — plus the maturity refusal below; there is deliberately no
decision map and no verdict wording anywhere. Capital promotion is NOT on
this path.

MANDATORY CAUSAL MATURITY CONTRACT (design §2, review round 1 HIGH): an
evaluation run at ``eval_asof`` may score ONLY dates whose forward label has
fully matured by that cutoff — the last eligible observation date is
``eval_asof − (label_horizon_bdays + settle_bdays)`` business days (weekday
calendar, pandas ``BDay``; the settle default of 1 mirrors the blend
forward-ledger's ``MATURITY_TDAYS = horizon + 1 session settle`` discipline
in ops/renquant104/rq104_blend_readout.py). A caller passing ANY scored date
newer than that bound gets a ``REFUSED-MATURITY`` report naming the boundary
— never a silent truncation, so the eligible set of an already-written ledger
row can never re-shape as labels fill in. Every report persists ``eval_asof``,
``label_horizon_bdays``, ``settle_bdays``, the eligible interval
``[first_date, last_date]``, the artifact content sha and the per-input read
digests, so any row is independently recomputable.

The evaluation ledger reuses the TRAIN ledger's digest chain via the SHARED
``append_chained_row`` (one chain implementation, never duplicated).
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Mapping, Protocol

import numpy as np
import pandas as pd

from renquant_model_momentum._v2_machine import (FROZEN_V2, _block_summary,
                                                 block_stats, one_sample_t,
                                                 run_controls, sample_acf,
                                                 t_bar)
from renquant_model_momentum.ledger import (LedgerIntegrityError,
                                            append_chained_row,
                                            load_and_verify_ledger)
from renquant_model_momentum.train import (_jsonable, content_sha256_of,
                                           verify_artifact_content_sha)

__all__ = ["EVAL_KIND", "EVAL_ROW_REQUIRED", "EVAL_SCHEMA_VERSION",
           "EvalSeriesReaders", "STATUS_COMPLETED", "STATUS_METHOD",
           "STATUS_POWER", "STATUS_REFUSED_MATURITY", "append_eval_ledger",
           "eligible_last_date", "evaluate_momentum_artifact"]

EVAL_KIND = "momentum_eval_v0"
EVAL_SCHEMA_VERSION = 1

#: Status vocabulary: the v2 runner's terminal statuses, verbatim, plus the
#: slice-3 maturity refusal. There is NO verdict vocabulary by design.
STATUS_REFUSED_MATURITY = "REFUSED-MATURITY"
STATUS_POWER = "UNRESOLVED-POWER"
STATUS_METHOD = "UNRESOLVED-METHOD"
STATUS_COMPLETED = "COMPLETED"

#: Fields every EVAL-ledger row must carry (the chain fields + the eval key).
EVAL_ROW_REQUIRED = ("row_index", "prev_row_sha", "appended_at_utc", "kind",
                     "eval_asof", "label_horizon_bdays", "settle_bdays",
                     "status", "artifact_content_sha256",
                     "report_content_sha256", "report", "row_sha")


class EvalSeriesReaders(Protocol):
    """Injected input surface — the core never touches disk itself.

    ``per_date_candidate_series`` returns the per-date candidate statistic
    (in the standing construction: the per-date cross-sectional Spearman IC of
    the artifact-params construction against the MATURED forward label),
    indexed by the scored dates, sorted ascending, unique. NaN values are
    allowed (they count against a block's usable floor, exactly as in v2);
    dates the caller skipped entirely (thin dates) simply do not appear —
    they change the sequence length only, never the partition within it.

    ``read_digests`` must return {input_name -> sha256 hex} for every input
    actually read to produce the series: recorded-at-read, not pinned
    (design §1/§2 — the digest record is what makes any later dispute
    answerable)."""

    def per_date_candidate_series(self) -> pd.Series: ...

    def read_digests(self) -> Mapping[str, str]: ...


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def eligible_last_date(eval_asof: Any, label_horizon_bdays: int,
                       settle_bdays: int) -> pd.Timestamp:
    """The causal maturity bound: the LAST scored date whose forward label has
    fully matured by ``eval_asof`` — ``eval_asof − (label_horizon_bdays +
    settle_bdays)`` business days (design §2). A scored date d carries a label
    over the h business days after d plus a settle session; only d at or
    before this bound may enter an evaluation."""
    return (pd.Timestamp(eval_asof)
            - pd.tseries.offsets.BDay(int(label_horizon_bdays)
                                      + int(settle_bdays)))


def _require_int(name: str, value: Any, minimum: int) -> int:
    if not isinstance(value, (int, np.integer)) or isinstance(value, bool):
        raise ValueError(f"{name} must be an int, got {type(value).__name__}")
    v = int(value)
    if v < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {v}")
    return v


def _validated_series(readers: EvalSeriesReaders) -> pd.Series:
    series = readers.per_date_candidate_series()
    if not isinstance(series, pd.Series):
        raise ValueError("per_date_candidate_series() must return a "
                         f"pd.Series, got {type(series).__name__}")
    idx = series.index
    if not isinstance(idx, pd.DatetimeIndex):
        raise ValueError("the per-date series must be indexed by dates "
                         f"(DatetimeIndex), got {type(idx).__name__}")
    if idx.has_duplicates:
        raise ValueError("the per-date series carries duplicate dates — one "
                         "scored date, one observation")
    if len(idx) and not idx.is_monotonic_increasing:
        raise ValueError("the per-date series must be sorted ascending by "
                         "date — the block partition is positional over the "
                         "scored-date sequence")
    return series


def evaluate_momentum_artifact(artifact: Mapping[str, Any], *, eval_asof: Any,
                               label_horizon_bdays: int,
                               readers: EvalSeriesReaders,
                               settle_bdays: int = 1,
                               context: Mapping[str, Any] | None = None
                               ) -> dict:
    """One recurring evaluation = one report (design §2).

    The v2 §3.1 ordering, exactly, on the caller-supplied per-date candidate
    series: (a) gap-blocks formed (width = gap = the label horizon), thin
    blocks dropped AND counted; (b) surviving-block power gate — controls NOT
    run on refusal; (c)/(c') realized_block_sd (ddof=1) PUBLISHED, degenerate
    -> METHOD; the §2.5 rho_1 valve; (d) BOTH frozen controls (PCG64,
    base_seed 20260801 + r, per-rep counts published) BEFORE any candidate
    statistic; (e) only then the block-t, the df-aware bar and the MDE. No
    decision map follows (e) — raw gate outputs only.

    Pure over ``readers``: no disk, no clock beyond the evaluated_at stamp.
    ``context`` (optional) is recorded verbatim as ``caller_context`` — for
    counts the caller measured while building the series (thin dates etc.).
    """
    verify_artifact_content_sha(artifact)   # never evaluate unverified bytes
    h = _require_int("label_horizon_bdays", label_horizon_bdays, 1)
    settle = _require_int("settle_bdays", settle_bdays, 0)
    asof = pd.Timestamp(eval_asof)
    if pd.isna(asof):
        raise ValueError("eval_asof is not a date")
    series = _validated_series(readers)
    bound = eligible_last_date(asof, h, settle)

    F = FROZEN_V2
    rep: dict[str, Any] = {
        "kind": EVAL_KIND,
        "eval_schema_version": EVAL_SCHEMA_VERSION,
        "evaluated_at_utc": _utc_now(),
        "eval_asof": str(asof.date()),
        "label_horizon_bdays": h,
        "settle_bdays": settle,
        "eligible_last_date": str(bound.date()),
        "maturity_rule": (
            "eligible scored dates end at eval_asof - (label_horizon_bdays + "
            "settle_bdays) business days (weekday calendar, pandas BDay): a "
            "scored date d carries a label over the h business days after d "
            "plus a settle session, so only d at or before the bound has a "
            "fully matured label at eval_asof — mirrors the blend "
            "forward-ledger's MATURITY_TDAYS discipline (design §2, review "
            "round 1 HIGH); newer dates are REFUSED, never silently "
            "truncated"),
        "eligible_interval": (
            {"first_date": str(series.index.min().date()),
             "last_date": str(series.index.max().date())}
            if len(series) else None),
        "n_dates": int(len(series)),
        "artifact_content_sha256": artifact["content_sha256"],
        "artifact_kind": artifact.get("kind"),
        "artifact_cutoff_date": artifact.get("cutoff_date"),
        "inputs": {
            "read_digests": dict(readers.read_digests()),
            "digest_policy": ("recorded-at-read, not pinned — recurring "
                              "evaluation over live surfaces (design §2)"),
        },
        "frozen": {
            "h": h, "gap": h,
            "geometry_rule": ("block width = label horizon, discarded gap = "
                              "h, positional over the eligible scored-date "
                              "sequence (v2 §2.1; the gap >= h is what buys "
                              "block independence)"),
            "min_usable_per_block": F["min_usable_per_block"],
            "min_surviving_blocks": F["min_surviving_blocks"],
            "rho1_ceiling": F["rho1_ceiling"],
            "quantile": F["quantile"],
            "n_reps": F["n_reps"],
            "base_seed": F["base_seed"],
            "positive_mu": F["positive_mu"],
            "positive_rate_min": F["positive_rate_min"],
            "negative_mu": F["negative_mu"],
            "negative_rate_max": F["negative_rate_max"],
        },
        "interpretation_rule": (
            "no gate, no verdict: this report carries raw gate outputs only; "
            "capital promotion is NOT on this path — promotion, if ever "
            "proposed, goes through the WF lineage gate with these artifacts "
            "(design §2)"),
    }
    if context is not None:
        rep["caller_context"] = dict(context)

    # -- the causal maturity contract, mechanical -----------------------------
    immature = series.index[series.index > bound]
    if len(immature):
        rep.update(
            status=STATUS_REFUSED_MATURITY,
            why=(f"{len(immature)} scored date(s) newer than the eligible "
                 f"end {bound.date()} (eval_asof {asof.date()} - "
                 f"({h} label_horizon_bdays + {settle} settle_bdays) business "
                 f"days); latest offending date {immature.max().date()}. "
                 "Labels there cannot have fully matured by eval_asof — "
                 "REFUSED, never silently truncated (append-only rows must "
                 "never re-shape as labels fill in)"),
            n_immature_dates=int(len(immature)),
            first_immature_date=str(immature.min().date()),
            last_immature_date=str(immature.max().date()),
        )
        return _finalize(rep)

    # -- the v2 machine, in the frozen §3.1 ordering --------------------------
    values = series.to_numpy(dtype=float)
    bs = block_stats(values, h, h, F["min_usable_per_block"])
    rep["blocks"] = _block_summary(bs)

    # (b) power gate — BEFORE any control machinery is touched
    if bs["n_surviving"] < F["min_surviving_blocks"]:
        rep.update(status=STATUS_POWER,
                   why=(f"n_surviving {bs['n_surviving']} < frozen floor "
                        f"{F['min_surviving_blocks']} (v2 §3.1(b)); controls "
                        "NOT run"))
        return _finalize(rep)

    means = bs["means"]
    n = bs["n_surviving"]
    df = n - 1
    sd = float(np.std(means, ddof=1))
    rep["df"] = df
    rep["realized_block_sd"] = sd   # PUBLISHED even when degenerate (§3.1(c'))

    # (c)/(c') degenerate-scale valve — before rho_1, controls, and any t
    if (not np.isfinite(sd)) or sd <= 0.0:
        rep.update(status=STATUS_METHOD,
                   why=(f"realized_block_sd {sd} is degenerate (non-finite or "
                        "<= 0): the geometry produced no dispersion to test "
                        "against (v2 §3.1(c')); controls and the candidate "
                        "statistic are NOT run"))
        return _finalize(rep)

    # §2.5 adequacy valve on the machine itself
    rho1 = float(sample_acf(means, 1)[0])
    rep["rho1_blocks"] = rho1
    if abs(rho1) >= F["rho1_ceiling"]:
        rep.update(status=STATUS_METHOD,
                   why=(f"|rho_1(block means)| {abs(rho1):.4f} >= frozen "
                        f"{F['rho1_ceiling']} (v2 §2.5): the geometry failed "
                        "to buy independence; controls and the candidate "
                        "statistic are NOT run"))
        return _finalize(rep)

    # (d) BOTH frozen controls, BEFORE any candidate statistic
    bar = t_bar(df)
    rep["bar"] = bar
    pos = run_controls(F["positive_mu"], sd, n, bar,
                       base_seed=F["base_seed"], n_reps=F["n_reps"])
    neg = run_controls(F["negative_mu"], sd, n, bar,
                       base_seed=F["base_seed"], n_reps=F["n_reps"])
    pos["ok"] = bool(pos["rate"] >= F["positive_rate_min"])
    neg["ok"] = bool(neg["rate"] <= F["negative_rate_max"])
    rep["controls"] = {"positive": pos, "negative": neg}
    if not (pos["ok"] and neg["ok"]):
        rep.update(status=STATUS_METHOD,
                   why=(f"control gate violation (v2 §3.1(d)): positive rate "
                        f"{pos['rate']:.4f} (floor {F['positive_rate_min']}), "
                        f"negative rate {neg['rate']:.4f} (ceiling "
                        f"{F['negative_rate_max']}); the candidate statistic "
                        "is never evaluated"))
        return _finalize(rep)

    # (e) the candidate statistic — raw outputs only, no decision map
    t_stat = one_sample_t(means)
    se_blocks = sd / np.sqrt(n)
    rep.update(status=STATUS_COMPLETED,
               t_stat=float(t_stat),
               mean_blocks=float(means.mean()),
               se_blocks=float(se_blocks),
               mde=float(bar * se_blocks),
               mean_dates=float(np.nanmean(values)))
    return _finalize(rep)


def _finalize(rep: dict) -> dict:
    """Strict-JSON projection + the self-carried content sha (artifact idiom)."""
    rep = _jsonable(rep)
    rep["content_sha256"] = content_sha256_of(rep)
    return rep


def append_eval_ledger(report: Mapping[str, Any],
                       ledger_path: Any) -> dict:
    """Append ONE evaluation report's row; returns the appended row.

    Same chain idiom as the TRAIN artifact ledger via the SHARED
    ``append_chained_row`` (never duplicated). Refusals (all
    ``LedgerIntegrityError``):
    - a report whose self-carried content_sha256 does not recompute;
    - a ``REFUSED-MATURITY`` report — that is a caller defect, not evidence;
      appending it would consume the (artifact, eval_asof, horizon) key and
      block the corrected re-evaluation forever;
    - a second row for the same (artifact_content_sha256, eval_asof,
      label_horizon_bdays) — one evaluation per artifact per as-of per
      horizon; a re-run that disagrees is a dispute to investigate, never a
      row to overwrite;
    - a ledger whose existing rows fail chain/self-digest checks."""
    claimed = report.get("content_sha256")
    actual = content_sha256_of(report)
    if claimed != actual:
        raise LedgerIntegrityError(
            f"refusing to ledger the report: content_sha256 mismatch "
            f"(carried {claimed!r}, recomputed {actual})")
    for key in ("kind", "status", "eval_asof", "label_horizon_bdays",
                "settle_bdays", "artifact_content_sha256"):
        if key not in report:
            raise LedgerIntegrityError(f"report missing {key!r}")
    if report["kind"] != EVAL_KIND:
        raise LedgerIntegrityError(
            f"not an evaluation report: kind {report['kind']!r} != "
            f"{EVAL_KIND!r}")
    if report["status"] == STATUS_REFUSED_MATURITY:
        raise LedgerIntegrityError(
            "refusing to ledger a REFUSED-MATURITY report: a maturity "
            "refusal is a caller defect (immature labels passed in), not "
            "evidence — appending it would consume the (artifact, eval_asof, "
            "horizon) key and permanently block the corrected re-evaluation; "
            "fix the input window and evaluate again")

    rows = load_and_verify_ledger(ledger_path,
                                  required_fields=EVAL_ROW_REQUIRED)
    for r in rows:
        if (r["artifact_content_sha256"] == report["artifact_content_sha256"]
                and r["eval_asof"] == report["eval_asof"]
                and r["label_horizon_bdays"]
                == report["label_horizon_bdays"]):
            raise LedgerIntegrityError(
                f"a row for artifact "
                f"{report['artifact_content_sha256'][:12]}… "
                f"eval_asof={report['eval_asof']} "
                f"label_horizon_bdays={report['label_horizon_bdays']} "
                f"already exists (row {r['row_index']}) — append-only means "
                "this run is a dispute to investigate, never a rewrite")

    return append_chained_row({
        "kind": EVAL_KIND,
        "eval_asof": report["eval_asof"],
        "label_horizon_bdays": report["label_horizon_bdays"],
        "settle_bdays": report["settle_bdays"],
        "status": report["status"],
        "artifact_content_sha256": report["artifact_content_sha256"],
        "report_content_sha256": report["content_sha256"],
        "eligible_interval": report.get("eligible_interval"),
        "report": dict(report),
    }, ledger_path, required_fields=EVAL_ROW_REQUIRED)
