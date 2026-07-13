# Ensemble Phase 0: admissibility ledger and experiment manifest (v2)

**Date:** 2026-07-12
**PR:** model feat/ensemble-phase0-ledger-v2 (supersedes #50)
**Design:** model PR #48 (merged), §3.0 and §4.5A

## What

Phase 0 prerequisite tooling for the ensemble experiment: admissibility ledger
and immutable experiment manifest. This v2 PR strips the L1 experiment runner
code that was out of scope and fixes review issues from Codex.

### Components

1. **Admissibility ledger builder** (`experiments/ensemble_phase0/admissibility_ledger.py`)
   - Per-expert, per-date validation: fingerprint, training cutoff, feature/data
     cutoff, score timestamp, universe coverage, missingness, score orientation
   - Lookahead detection (training cutoff >= prediction date)
   - Score timestamp validation: lower bound (prediction date) AND upper bound
     (decision cutoff, defaults to same-day cap)
   - Universe coverage: intersection-based scoring, unknown/duplicate ticker
     rejection, missingness derived from expected universe only
   - `has_realized_labels` extracted from score artifact (fail-closed default)
   - Parquet rejected — JSON only (no provenance parity for parquet)
   - Complementarity report: required prerequisite for admission (must be
     "PLAUSIBLE" or all_experts_fully_admitted = False)
   - Deterministic SHA-256 fingerprinted ledger output
   - CLI discovers dates from score directories and runs complementarity analysis

2. **Experiment manifest builder** (`experiments/ensemble_phase0/experiment_manifest.py`)
   - Immutable pre-registered manifest encoding the full §4.5A contract
   - 3 experts, 2 expert sets, 6-hypothesis family, hierarchical gatekeeping
   - Tamper detection via fingerprint verification

### Fixes from Codex review (CHANGES_REQUESTED on #50 and #51)

Round 1 fixes (a6b4bd8 and earlier):

1. **`extract_metadata_from_score` extracts `has_realized_labels`** — previously
   never copied from the score artifact; now explicitly extracted with
   fail-closed False default.

2. **Score timestamp upper bound enforced** — `decision_timestamp_max` parameter
   caps how late a score can be generated. Defaults to prediction_date (same-day
   cap). Late scores rejected as potential look-ahead.

3. **Universe coverage via intersection** — `scored_count` now measures
   `universe ∩ score_keys` (not raw `len(scores)`). Unknown tickers outside the
   universe are rejected. Duplicate keys are rejected. Missingness derived only
   from expected universe names.

4. **Parquet explicitly rejected** — `load_score_file` only supports JSON.
   Parquet cannot carry inline provenance metadata; a versioned parquet+sidecar
   schema may be added later. `SUPPORTED_SCORE_FORMATS` constant controls this.

5. **Complementarity is a prerequisite** — `build_ledger` accepts
   `complementarity_assessment` parameter. `all_experts_fully_admitted` requires
   both per-expert admission AND complementarity = "PLAUSIBLE". INSUFFICIENT_DATA,
   NEAR_DUPLICATE, LOW_DISAGREEMENT, or NOT_EVALUATED all block Phase A.

### Round 2 fixes (Codex re-review on a6b4bd8)

6. **Timing causally re-specified** — Replaced date-prefix string comparison
   with proper timezone-aware ISO-8601 timestamp parsing (`_parse_timestamp`
   helper). Removed the incorrect `score_timestamp < prediction_date` rejection
   (D-1 overnight scoring is valid). Added `decision_timestamp` parameter
   (replaces `decision_timestamp_max`), wired through CLI `--decision-timestamp`
   flag and `build_ledger`. Added `data_watermark` field to metadata contract
   and `ExpertAdmissibilityRecord`. Enforced causal chain:
   `training_cutoff < data_watermark <= prediction_date`,
   `score_timestamp <= decision_timestamp`.

7. **`has_realized_labels` now contributes to rejection** — Added
   `require_realized_labels` parameter (default True for historical evaluation).
   When True, `has_realized_labels=False` produces rejection reason
   "no realized labels for evaluation". Pass False for live/prospective scoring.

8. **Complementarity rejects NaN/non-finite** — `_assess_complementarity` now
   explicitly checks `math.isfinite()` on Pearson, Spearman, and disagreement
   averages. Non-finite values produce `NON_FINITE_CORRELATION` assessment
   (blocks admission). `build_complementarity_report` flags degenerate
   (constant/NaN) correlation entries and excludes them from averages.
   `MIN_COMMON_NAMES` constant (10) replaces hardcoded threshold.

9. **Fingerprint SHA-256 digest syntax validation** — Added `FINGERPRINT_RE`
   regex (`^sha256:[0-9a-f]{64}$`). Fingerprints that are present but
   syntactically invalid are rejected. Tests cover: too-short, uppercase hex,
   wrong prefix, valid format.

## Why

Per §5.1, the Stage 0 admissibility ledger and immutable manifest BLOCK every
L1-L3 comparison. Without them, any experiment result is not credible.

## Status

- 62/62 tests pass (55 ledger + 7 manifest).
- New test coverage: D-1 overnight scoring, timezone-aware timestamps, absent
  realized labels, NaN/constant-score complementarity, fingerprint syntax
  validation, fingerprint mutation/tamper detection, causal chain violations.
- These are experiment-side tools, not production code changes.
- Next: run the ledger against actual XGB + PatchTST score histories to produce
  the first admissibility audit.

## Revision note (2026-07-13, round 8 — real exchange calendar closes the item-2 gap)

A concurrent session's `3448fab8` addressed 4 fresh Codex findings (schedule
persistence + fingerprint binding, required `decision_timestamp`, label
horizon, digest+locator label references) solidly -- verified independently,
114/114 pass. But its item-2 fix (`SessionCalendar`) was hand-populated
(`valid_dates`/`early_close_times` supplied entirely by the caller, no
connection to a real exchange calendar), and the production CLI still
defaulted to the fixed `US_EQUITY_CLOSE` clock with `session_calendar=None`
-- the stderr warning told users to pass `--session-calendar`, but that flag
did not exist anywhere in the argparse setup. This directly contradicted the
original finding: "A fixed US_EQUITY_CLOSE must not be the production CLI
default."

This round closes that gap on top of `3448fab8` (keeping its schedule
persistence, required-kwarg, and label-horizon/locator work intact):

1. Added `pandas_market_calendars>=4` as a real dependency (`pyproject.toml`)
   -- the same exchange-calendar primitive `renquant-execution`'s
   `preopen_cancel_gate.py` and `renquant-orchestrator` already use.
2. New `build_exchange_session_calendar(start, end, *, calendar_name="NYSE", ...)`
   constructs a `SessionCalendar` from the REAL NYSE schedule: `valid_dates`
   from actual trading sessions, `early_close_times` derived by comparing each
   session's real `market_close` (converted to the declared session timezone)
   against the nominal full-session close -- no hand-typed date lists.
3. The CLI's `main()` now ALWAYS constructs a real calendar (padded ±7 days
   around the discovered prediction-date range, so a range whose exact
   boundary falls on a holiday doesn't itself come back empty and crash) and
   passes it into both `build_ledger()` calls. This is the default, not an
   opt-in flag -- removed the phantom `--session-calendar` reference.
4. Verified with real historical NYSE data: 2025-11-27 (Thanksgiving) has no
   session; 2025-11-28 (day after) has a real 13:00 ET early close, not
   16:00 ET -- a score at 13:30 ET is correctly rejected as post-decision,
   one at 12:30 ET is correctly admitted. A single-day query that itself
   falls on a holiday raises fail-closed rather than silently returning an
   always-rejecting empty calendar.

6 new tests (`TestRealExchangeCalendar`): Thanksgiving non-session, real
early-close time detection, regular-session has no override, end-to-end
early-close rejection/admission using real calendar data, empty-range
fail-closed.

### Verification

- `pytest tests/test_admissibility_ledger.py -v`: 120/120 pass (114 + 6 new)
  `[VERIFIED]`
- Full suite (excluding `tests/patchtst`/`tests/gbdt`/`tests/crypto`, which
  fail to collect even on an unmodified checkout due to an unrelated
  `_SixMetaPathImporter` environment issue): 148 passed, 1 skipped, 1
  pre-existing unrelated failure (`ModuleNotFoundError: sklearn`)
  `[VERIFIED]`
- CLI smoke-tested end-to-end: a single Thanksgiving-dated score file is
  correctly rejected ("not a real NYSE trading session") without crashing;
  a valid session date runs the full pipeline `[VERIFIED]`
