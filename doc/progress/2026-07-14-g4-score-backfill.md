# G4: Phase A score backfill from runs.alpaca.db

Date: 2026-07-14

## Problem

The Phase A ensemble runner (`phase_a_runner.py`, PR #53) needs per-date
JSON score files verified against an admissibility ledger. The daily pipeline
already persists candidate scores to `runs.alpaca.db` (~520 trading days,
2024-01-02 to 2026-07-13), but never exports them as per-date JSON.

Without backfilled scores, Phase A experiments cannot evaluate historical
ensemble performance — G4 L1 is data-bound.

## Solution

New script `experiments/ensemble_phase0/backfill_scores.py` that:

1. Reads candidate-role mu scores from `runs.alpaca.db` (latest run per date,
   deduped by `created_at DESC`)
2. Writes per-date JSON files with full provenance: `{date, expert, scores,
   provenance: {source_run_id, run_created_at, is_post_hoc, runs_db_digest},
   metadata}`
3. Exports forward returns CSV (`fwd_60d` from `ticker_forward_returns`)
4. Builds candidate evidence records (NOT admissibility — admission decided
   downstream by the canonical validator) with per-date provenance
5. Writes a provenance manifest with DB digest, date range, post-hoc counts,
   and classification

All output carries `EXPLORATORY_ONLY` classification. No production paths
are touched.

## Codex review r1 (2026-07-14)

Addressed all 4 blocking items from codex CHANGES_REQUESTED:

1. **Point-in-time contract**: `extract_daily_scores()` now returns
   `DateProvenance` objects with `source_run_id`, `run_created_at`, and
   `is_post_hoc` flag (true when run was created after the target date).
   Dates with post-hoc reruns are flagged, not silently treated as
   point-in-time evidence.

2. **Per-date provenance**: Every score file includes a `provenance` block
   with `source_run_id`, `run_created_at`, `is_post_hoc`, `score_column`,
   `runs_db_digest`, and `backfill_id`. Evidence records carry the same
   fields plus `score_artifact_digest`.

3. **No manufactured `admitted: true`**: Renamed `build_admissibility_records`
   → `build_evidence_records`. Output is `evidence_ledger.json` (not
   `admissibility_ledger.json`). No `admitted` field — the canonical
   admissibility validator decides admission from provenance.

4. **Score-column allowlist**: `_ALLOWED_SCORE_COLUMNS` frozenset gates
   `--score-column` to `{mu, raw_score, panel_score, rank_score, rs_score}`.
   `argparse` `choices=` enforces at CLI level; `_validate_score_column()`
   enforces at API level. Negative test confirms SQL injection is rejected.

## Tests

12 tests in `tests/test_backfill_scores.py`:
- `test_extract_daily_scores`: provenance extraction with role filtering
- `test_extract_daily_scores_date_range`: date range filtering
- `test_post_hoc_rerun_flagged`: rerun created after target date → is_post_hoc=True
- `test_extract_forward_returns`: forward returns extraction
- `test_write_score_files`: per-date JSON structure, provenance block, EXPLORATORY_ONLY
- `test_write_forward_returns_csv`: CSV format and digest
- `test_build_evidence_records_no_admitted_field`: no `admitted` key in evidence records
- `test_score_column_allowlist_rejects_arbitrary_text`: SQL injection rejected
- `test_run_backfill_e2e`: full pipeline produces all expected artifacts with provenance
- `test_score_file_digest_matches_ledger`: digest integrity verification
- `test_holdings_excluded`: only candidate role rows
- `test_post_hoc_rerun_not_silently_admitted`: post-hoc rerun flagged, evidence records lack `admitted`

## Round 2 (2026-07-14, commit 69df102): partial fix -- superseded below

A concurrent session pushed `69df102` responding to the same Codex review
(SQL-column allowlist, a `DateProvenance`/`is_post_hoc` flag, an
`evidence_ledger.json` rename dropping `admitted`). Two of the four findings
were genuinely NOT closed by that commit, proven by its own test:

- **Finding 1 (as-of / point-in-time contract) was not fixed, only labeled.**
  `extract_daily_scores`'s subquery is untouched --
  `ORDER BY p2.created_at DESC LIMIT 1` still unconditionally selects the
  LATEST run per date. `is_post_hoc` (`run_created[:10] > run_date`, a
  day-granularity string compare) is computed and attached as a flag, but
  the flagged run's score is still written out and still referenced by the
  evidence ledger -- nothing excludes it. `69df102`'s own
  `test_post_hoc_rerun_not_silently_admitted` asserts
  `rec["source_run_id"] == "run-rerun"` and
  `score_data["scores"]["AAPL"] == pytest.approx(0.12)` for a rerun
  committed 8 days after the original -- i.e. the test proves the
  look-ahead-contaminated value (0.12, not the original 0.05) is exactly
  what ships. Codex's ask was explicit: "Do not simply take `created_at
  DESC` and call it done... classify the date as unavailable and fail
  closed or exclude it" -- flagging without excluding does not meet that
  bar, and nothing downstream (`phase_a_runner.py`,
  `admissibility_ledger.py`) even reads `is_post_hoc`.
- **Finding 3 (defer admission to the canonical validator) was renamed, not
  wired.** `evidence_ledger.json`'s fields (`source_run_id`,
  `run_created_at`, `is_post_hoc`, `runs_db_digest`) are not the fields
  `admissibility_ledger.extract_metadata_from_score` reads
  (`training_cutoff`, `feature_data_cutoff`, `score_timestamp`,
  `data_watermark`, `model_content_sha256`, `has_realized_labels`,
  `label_artifact_ref`, `label_observation_end`) and
  `admissibility_ledger.build_ledger`/`validate_expert_date` is never
  called anywhere in the diff. The commit message's "canonical validator
  decides admission from provenance" was aspirational, not implemented --
  and the renamed `evidence_ledger.json` is not consumable by
  `phase_a_runner.py`'s existing `--ledger-file` path at all (it expects a
  real `admissibility_ledger.json` with `ledger_fingerprint`/
  `records[].admitted`), so this round also broke the backfill →
  Phase A integration path.
- Findings 2 (provenance) and 4 (SQL allowlist) were reasonable partial/
  full steps in the right direction and are carried forward (allowlist
  columns, the `source_run_id`/`run_created_at` idea).

## Round 3 (2026-07-14): complete fix, closing all 4 findings for real

Rewrote `backfill_scores.py` on top of `69df102` to genuinely close all four
points, verified with negative tests that check the actual *selected score
value*, not just a flag.

**1. SQL injection (`--score-column`).** `ALLOWED_SCORE_COLUMNS` = `{mu,
raw_score, panel_score, rank_score, rs_score, sigma}` (every real numeric
column on `candidate_scores`, per
`renquant-pipeline/src/renquant_pipeline/kernel/persistence.py`).
`validate_score_column()` raises `ScoreColumnNotAllowedError` before the
value ever reaches a query string, enforced at both the CLI and every
library entry point. Test: a `"mu; DROP TABLE pipeline_runs--"` payload is
rejected and the DB is proven intact afterward.

**2. As-of contract -- actually gates selection now.** New
`select_asof_runs()`: for each prediction date, only a `run_type='live'`
row whose `created_at` (SQLite `CURRENT_TIMESTAMP`, UTC) is `<=` that
date's REAL NYSE session-close cutoff (holiday/early-close aware, via
`pandas_market_calendars` -- the same primitive `admissibility_ledger.py`
already uses) is eligible for selection at all. A date with zero eligible
runs -- no live run, or every live run for it committed after its own
session closed -- is excluded with a documented reason and never appears
in the output. `_session_close_cutoff_utc()` reuses the exact formula
`admissibility_ledger._decision_ts_from_schedule` uses, so this script's
cutoff and the validator's later independent recomputation of the same
quantity are numerically identical.

Negative test `test_later_rerun_is_not_selected_look_ahead_guard` uses the
SAME shape of scenario as `69df102`'s test (an original run + a later
rerun with a changed score for the same date) and asserts the ORIGINAL
score is what `extract_daily_scores` returns -- the rerun's changed value
never surfaces. A second test,
`test_date_with_only_a_post_cutoff_run_is_excluded_not_admitted`, covers
the case where only a late rerun exists for a date: the date is excluded
entirely, not silently included with the late value.

**3. Immutable per-date provenance.** Every score file now carries, at TOP
LEVEL (the level `admissibility_ledger.extract_metadata_from_score` reads
-- `69df102`'s payload nested everything one level too deep under
`provenance`/`metadata`, so none of it was ever visible to the validator):
`as_of_date`, `data_watermark`, `score_timestamp` (= the selected run's
`created_at`), `training_cutoff`, `model_content_sha256`,
`has_realized_labels`, `label_artifact_ref`, `label_observation_end`. An
extended `metadata.provenance` block adds: source run id/type, the run's
committed timestamp, the session cutoff used, `pipeline_runs.commit_sha`
(code revision), `active_scorer`/`model_type`/`panel_ltr_artifact` (scorer
identity, read off `candidate_scores`), the NYSE calendar name/provider,
a `backfill_query_schema_version` tag, and a SHA-256 digest of the source
DB file -- durable IN the artifact, not only in a separate manifest.

`training_cutoff` and `model_content_sha256` are honestly `"MISSING"`:
`runs.alpaca.db`'s schema does not persist either field anywhere. This is
a genuine data gap, not a placeholder -- fabricating a fingerprint-shaped
value from unrelated columns would be exactly the manufactured-evidence
problem this fix exists to remove.

**4. Admission deferred to the REAL canonical validator.**
`run_backfill()` now imports and calls
`admissibility_ledger.build_ledger()` directly on the just-written
candidate evidence and persists ITS output via
`admissibility_ledger.write_ledger()` as `admissibility_ledger.json` --
the same file phase_a_runner.py already knows how to load and verify. The
backfill script no longer decides admission itself in any form. Because
`training_cutoff`/`model_content_sha256` are always `"MISSING"` given the
current `runs.alpaca.db` schema, every record is (correctly) rejected
today (`admitted=False`; reasons include "missing training cutoff date" /
"missing model fingerprint"). **This is expected, fail-closed behavior,
not a regression** -- making backfilled historical scores admissible
requires a future enhancement to persist training-cutoff/model-fingerprint
identity in `runs.alpaca.db` at write time (out of scope here; fabricating
it would recreate the exact problem being fixed).

### Tests (round 3)

`tests/test_backfill_scores.py` rewritten: 25 tests covering the allowlist
rejection, the as-of contract (including the negative rerun/look-ahead test
that checks the actual score value, and the "only a post-cutoff run
exists" exclusion case), provenance payload shape (including "never
manufactures `admitted`" and "missing fields stay honestly MISSING"), and
end-to-end `run_backfill` behavior (candidate evidence + real-validator
ledger, digest/manifest consistency, optional `--universe-file`).

Full suite: `821 passed, 2 skipped` (run via the RenQuant venv against the
sibling `renquant-common`/`renquant-base-data`/`renquant-artifacts`/
`renquant-pipeline` checkouts, matching `make test`'s CI wiring) -- no
regressions outside this module.
