# GOAL-7 pipeline slice 3: the recurring TEST evaluator (`evaluate.py`)

STATUS: planned — built + fully tested; recurring runs begin only after
review + merge, and nothing schedules them (machine landing is slice 5,
operator-gated; merged-but-dark by design). Implements §2 (TEST) of the
MERGED architecture design
(doc/design/2026-08-02-momentum-pipeline-architecture.md), including the
MANDATORY causal maturity contract from its review round 1 (HIGH).

WHAT: design §2 as code —
- `src/renquant_model_momentum/_v2_machine.py`: the sealed v2 gap-block
  machine's pure pieces (`FROZEN_V2`, `partition_blocks`, `block_stats`,
  `one_sample_t`, `t_bar`, `run_controls`; `sample_acf` from the inference
  module) as a BYTE-VERBATIM packaged mirror — the `_frozen_params_v0`
  precedent, not the `total_return` move: the v2 runner is the provenance of
  a SEALED published result and its bytes stay untouched; the wheel must be
  self-sufficient (`tools/` never ships — the review-round-1 lesson of PR
  #196). Mirror fidelity is held by `inspect.getsource` byte-equality tests
  plus the output-parity golden.
- `src/renquant_model_momentum/evaluate.py`:
  `evaluate_momentum_artifact(artifact, *, eval_asof, label_horizon_bdays,
  readers, settle_bdays=1) -> report` — the v2 §3.1 ordering, recurring:
  gap-block geometry (width = gap = the label horizon, positional over the
  ELIGIBLE scored-date sequence), <10-usable blocks dropped AND counted,
  n_surviving < 40 → UNRESOLVED-POWER (controls NOT run), realized_block_sd
  (ddof=1) PUBLISHED with the degenerate publish+refuse, the |rho1| >= 0.25
  valve, BOTH PCG64 base_seed-20260801+r controls (floors 0.80 / 0.10,
  per-rep clear strings published) BEFORE any candidate statistic, then the
  block-t + df-aware bar + MDE. Statuses mirror v2's vocabulary
  (UNRESOLVED-POWER / UNRESOLVED-METHOD / COMPLETED) plus REFUSED-MATURITY;
  NO decision map, NO verdict wording anywhere — raw gate outputs only, and
  the report carries the design's standing interpretation rule (capital
  promotion is NOT on this path).
- The causal maturity contract, mechanical: eligible dates end at
  `eval_asof − (label_horizon_bdays + settle_bdays)` business days (pandas
  BDay; settle default 1 mirrors the blend forward-ledger's
  `MATURITY_TDAYS = horizon + 1 session settle` in
  ops/renquant104/rq104_blend_readout.py). ANY newer scored date →
  REFUSED-MATURITY naming the boundary — never silent truncation, so a
  written row's eligible set can never re-shape as labels fill in. Every
  report carries eval_asof / label_horizon_bdays / settle_bdays / the
  eligible interval [first_date, last_date] / the artifact content sha /
  per-input read digests, so any row is independently recomputable.
  A REFUSED-MATURITY report is NOT ledgerable (it is a caller defect;
  appending it would consume the (artifact, eval_asof, horizon) key and
  block the corrected re-evaluation forever).
- `append_eval_ledger(report, ledger_path)`: append-only JSONL with the SAME
  prev_row_sha/row_sha chain as the TRAIN artifact ledger via a SHARED
  `append_chained_row` extracted into `ledger.py` (one chain implementation;
  `append_to_artifact_ledger` now routes through it — behavior unchanged,
  regression-tested). Duplicate (artifact_content_sha256, eval_asof,
  label_horizon_bdays) refused; tampered reports/histories refused.
- `tools/momentum_eval_run.py`: CLI (`--artifact/--ledger/--eval-asof/
  --horizon` + `--settle-bdays/--first-date/--out-root/--dry-run`) wiring
  REAL readers with digest recording — per-date scores from the packaged
  `train_momentum_artifact` (golden-pinned to the sealed `assemble_day`),
  per-date IC via the sealed v1 `_spearman_ic`, label column
  `fwd_<h>d_excess` (refused if unwired). Caller-side maturity truncation
  (`_eligible_dates`) is the discipline; the core refusal is the guard. The
  TRAIN CLI's TWO-FILE protocol is mirrored exactly: report finalized
  (staging + atomic rename) BEFORE the ledger append; startup reconciles a
  finalized-but-unledgered report; exit 4 already-ledgered, exit 5 ledger
  refusal with reconciliation on retry.

WHY/DIR: v1/v2 closed the one-shot question honestly (underpowered at the
frozen target); the design's remedy is recurring honest evaluation that LOGS
evidence instead of issuing verdicts. This slice turns the validated v2
machine into that standing harness without re-adjudicating the sealed shots,
and makes the maturity discipline mechanical so forward evidence can never
leak partially-filled labels into a row.

EVIDENCE:
  artifact:      src/renquant_model_momentum/{_v2_machine,evaluate}.py,
                 src/renquant_model_momentum/{__init__,ledger}.py (chain
                 helper shared), tools/momentum_eval_run.py,
                 tests/test_momentum_evaluator.py
  prod or exp:   exp — new evaluator + CLI; nothing schedules it, nothing
                 consumes its ledger yet (slices 4–5); zero serving surfaces
                 touched; no production path written
  existing data: the sealed v2 runner (tools/goal7_momentum_v2_run.py,
                 model#192) is the reference machine. The parity golden runs
                 ITS `run_inference` and the evaluator on the same synthetic
                 2378-date series (PCG64 seed 20260801, N(0.005, 0.05)) and
                 asserts EXACT equality — block means, usable counts, df=58,
                 realized_block_sd, rho1, bar, both control rates including
                 the 1000-char per-rep clear strings, t, se, MDE — bitwise
                 (`==`, no tolerance needed: both sides execute the
                 byte-verbatim machine) `[VERIFIED — pytest 2026-08-02]`;
                 fixture measured: 59 surviving blocks, rho1 0.1281, control
                 rates 1.000/0.025 `[VERIFIED — measured 2026-08-02]`; the
                 maturity boundary literals are hand-pinned then measured
                 (2026-06-30 − 21 bd = 2026-06-01; − 22 bd = 2026-05-29)
                 `[VERIFIED — measured 2026-08-02]`
  best-known?:   yes — the only implementation of design §2 TEST; the sealed
                 v2 runner remains the authority the mirror is held to
                 (getsource byte-equality + output parity)
  scope:         a PORT-IDENTITY claim only (evaluator == sealed v2 machine
                 on the same input), never a new IC/edge number; NO statistic
                 was computed on real data anywhere in this slice — every
                 fixture is synthetic, and the single live-surface test is an
                 env-skipped --dry-run smoke that resolves the window from
                 the panel's date/schema and computes nothing; CLI writes
                 only under --out-root
  tests:         new file 45 passed `[VERIFIED — pytest -q
                 tests/test_momentum_evaluator.py, 2.64s]`; full suite 1514
                 passed, 0 failed `[VERIFIED — make test 2026-08-02,
                 64.13s]`; pre-slice baseline 1469 `[VERIFIED — pytest
                 --collect-only ignoring the new file]` (1469 + 45 = 1514,
                 zero regressions)

NEXT: codex review → merge (merged-but-dark: no scheduler). Then slice 4
  (strategy-104 shadow_models config, its repo) and slice 5 (machine
  landing, ONE operator grant with reverts per the containment protocol).
  The h=60 horizon rides this same evaluator once its evaluation is invoked
  with --horizon 60 — the panel already carries fwd_60d_excess
  `[VERIFIED — schema read 2026-08-02]` — as a second ledger key, evidence
  accumulation only.
AC6: N/A — research/evaluation tooling; no run-surface change.

## Review round 1: the report path did not carry the identity the ledger keys on

Ledger identity is `(artifact_content_sha256, eval_asof, label_horizon_bdays)`, but the
report basename was `momentum_eval_h{h}.json`. A SECOND artifact evaluated on the same
`eval_asof` and horizon therefore resolved to the FIRST one's path and was
reconciled-or-refused against it instead of writing its own report — which is every
recurring comparison and every post-retrain re-evaluation on the same date, i.e. the two
things a recurring evaluator exists to do.

`_reconcile_or_refuse`'s own docstring already read *"a report already exists at this
(artifact, eval_asof, horizon) path"*. The contract was stated in the code and
contradicted by the path.

Fixed: `report_basename(horizon, artifact_content_sha256)` →
`momentum_eval_h{h}_{sha[:12]}.json`. The abbreviation is a disambiguator only — the full
digest stays in the report body and the ledger row — and a digest too short to identify
anything is REFUSED rather than truncated, so the collision cannot come back through a
stub value.

| claim | value | provenance |
|---|---|---|
| module tests | 47 passed | [VERIFIED — `pytest -q tests/test_momentum_evaluator.py`] |
| model suite | 1514 passed, 2 skipped | [VERIFIED — `pytest -q`] |
| both new tests are load-bearing | restoring the pre-fix `momentum_eval_run.py` fails both | [VERIFIED — `git show HEAD:…` over the fix, re-run] |

The three existing CLI tests pinned the old basename as a literal; they now DERIVE it
through the CLI's own rule, so a future change to the naming cannot leave a test asserting
a path the tool no longer writes.

### Round 1, second half: reconcile must verify the embedded sha, not the filename

Landed by the concurrent session in a separate commit on this branch (the path
fix above); this commit contributes the remaining half of the reviewed
contract: `_reconcile_or_refuse` now takes the sha of the artifact being
evaluated and verifies it against the report's EMBEDDED
`artifact_content_sha256` before anything else. The filename's 12-hex prefix
routes; it is never believed: a content-sha-valid report embedding a
DIFFERENT artifact's sha at this path (prefix collision or tampering) is
refused (exit 4, naming the embedded sha it found) — never reconciled, never
ledgered, planted bytes untouched.

| claim | value | provenance |
|---|---|---|
| wrong-artifact report planted at the path | exit 4 naming the embedded sha; no ledger created; planted bytes unchanged | [VERIFIED — `test_cli_reconcile_refuses_wrong_artifact_at_the_path`] |
| same triple twice | still the append-only duplicate refusal (wording asserted), 1 ledger row | [VERIFIED — `test_cli_second_run_refuses_ledgered_report`, extended] |
| module tests | 48 passed | [VERIFIED — `pytest -q tests/test_momentum_evaluator.py`, 2.78s] |
| model suite | 1517 passed, 0 failed | [VERIFIED — `make test 2026-08-02`, 63.09s] |

## Review round 2: settle joins the identity; the requested window reaches the core

Two release-blocking contract gaps (codex, reproduced by them):

**1. `--settle-bdays` changed the maturity boundary but not the identity.**
Settle moves `eligible_last_date`, i.e. it changes the causal sample — yet
the report path and the ledger duplicate key carried only (artifact,
eval_asof, horizon). Settle 1 then settle 2 on one artifact/asof/horizon:
the second run died REFUSED-REPORT-EXISTS and its maturity contract could
never be recorded. Fixed by making the durable identity the 4-tuple
(artifact_content_sha256, eval_asof, label_horizon_bdays, settle_bdays) in
ALL THREE surfaces: the filename
(`momentum_eval_h<h>_s<settle>_<sha12>.json`), the reconcile check (the
report's EMBEDDED artifact sha AND settle must equal the requested ones —
the filename routes, it is never believed), and
`evaluate.append_eval_ledger`'s duplicate key. Default settle stays 1 (the
blend forward-ledger convention).

**2. The CLI pre-filtered immature dates, making the core's mandatory
refusal unreachable on the only real-reader path.** The old
`_eligible_dates` silently truncated at the bound before the core ever saw
the series — a silent filter standing in front of the contract it fed. Now
the CLI passes the FULL requested window to the core: `_window_dates` is
maturity-BLIND (declared [first_date, last_date] only, default last =
the bound as an explicit, persisted request), `--last-date` beyond the
bound flows through and is REFUSED by the core (exit 3, nothing written),
and the report's caller_context records the requested window plus the
no-silent-exclusion invariant `n_window_dates == n_dates +
n_thin_dates_skipped`. The maturity gate lives in the core ONLY.

| claim | value | provenance |
|---|---|---|
| settle 1 then settle 2, same artifact/asof/horizon | two reports (`_s1_`/`_s2_`), two ledger rows, bounds 2026-06-01 / 2026-05-29; same 4-tuple again -> duplicate refusal, still 2 rows | [VERIFIED — `test_cli_TWO_SETTLES_same_artifact_asof_horizon_both_record`] |
| settle=0 row does not block settle=1 at the API | 2 rows, quadruple dup refused | [VERIFIED — `test_eval_ledger_settle_is_part_of_the_identity`] |
| wrong-settle report planted at the path | exit 4 naming the embedded settle; never ledgered | [VERIFIED — `test_cli_reconcile_refuses_wrong_settle_at_the_path`] |
| core refusal REACHABLE on the real path | honest builder + `--last-date` past the bound -> exit 3 REFUSED-MATURITY, nothing written; same builder at the default window -> exit 0 | [VERIFIED — `test_cli_last_date_beyond_the_bound_REACHES_the_core_refusal`] |
| `_window_dates` is maturity-blind | no-bounds call returns dates past the bound verbatim | [VERIFIED — `test_window_dates_realizes_the_requested_window_verbatim`] |
| module tests | 52 passed | [VERIFIED — `pytest -q tests/test_momentum_evaluator.py`, 3.64s] |
| model suite | 1521 passed, 0 failed (baseline 1469 + 52) | [VERIFIED — `make test 2026-08-02`, 75.07s] |
