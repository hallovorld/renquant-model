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
