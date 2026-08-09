# L3 meta-label classifier — prereg v2 (feature-availability amendment)

STATUS: frozen before any outcome. This document amends ONE clause of
`doc/design/2026-08-09-l3-classifier-prereg.md` (v1, merged in model#207):
the frozen feature set. Every other element of v1 — model class, split,
embargo, thresholds, primary metric, placebo, external test, the four
PASS/KILL legs — is inherited verbatim and is NOT restated as changeable.
v1 itself prescribes this instrument: "No feature additions, no threshold
moves, no model upgrades inside this prereg. A new attempt is a new dated
prereg."

## 1 · Why v2 exists — the v1 design is infeasible on the measured data

The first execution attempt (2026-08-09, same session as this document)
loaded the merged `l3_candidate_dataset.v2` export and found the v1
six-feature set structurally unavailable:

| feature | rows missing | where `[VERIFIED — NaN audit on the v2 CSV, this session]` |
|---|---|---|
| expected_return | 5,008 | ALL 4,978 sim rows + 30 live; present only on live rows from 2026-04-27 |
| sigma | 1,528 | live rows only, ALL dated 2026-05-12..2026-07-10 |
| mu | 140 | live rows only, dated 2026-05-12..2026-05-15 |
| panel_score, rank_score, n_candidates_that_date | 0 | complete |

The two large holes are COMPLEMENTARY serving-side drifts: `expected_return`
began being stamped into `candidate_scores` around 2026-04-27, and `sigma`
stopped being stamped on 2026-05-12. Their intersection — rows carrying all
six v1 features — is 631 live rows over 26 dates (2026-04-27..2026-07-10)
`[VERIFIED — complete-case count, this session]`. That cannot support the
frozen expanding quarterly walk-forward from 2024, and it voids the ALL-rows
arm entirely (zero sim rows qualify).

v1 froze no missing-data clause, and its self-test is "the run can be judged
entirely from §2/§3 with zero live choices". Inventing a drop/impute policy
mid-run would be exactly such a live choice. Execution therefore STOPPED
before any outcome was computed.

**Contamination statement**: the aborted attempt produced NO uplift, placebo,
calibration, or external-test number — the fold table was empty and the run
crashed before the first metric line. The only quantities observed were
input-side: row counts, NaN counts, date spans. Feature availability is a
property of the design matrix, not of the labels; selecting features on
availability does not condition on outcomes.

## 2 · The amended clause (the ONLY change)

| element | v1 (infeasible) | **v2 (frozen here)** |
|---|---|---|
| features — base (unconditional) | panel_score, mu, sigma, expected_return, rank_score, n_candidates_that_date | **panel_score, mu, rank_score, n_candidates_that_date — 4 features** `[DERIVED — count of this list]` |
| missing-data policy | none frozen | **complete-case: any row missing a frozen feature or fwd_20d is dropped AND counted; the report states the count. No imputation.** Expected drop: 140 rows (2.0%) `[VERIFIED — mu NaN count, this session]` |

Why S4 and not a sigma-keeping S5: keeping sigma preserves 5,639 rows but
erases the 25 most recent live dates (live sample 2,189 → 661) — the
live-only prereg VARIANT would lose the very regime it exists to check.
S4 keeps 7,027 rows / 519 dates / 2,049 live rows spanning
2024-01-02..2026-07-10 `[VERIFIED — complete-case count, this session]` —
every retained feature is ≥98% available on BOTH run_types across the full
calendar. Dropping a feature that does not exist in the data is a
feasibility repair, not a tuning move; no outcome influenced it.

Consequential restatement (numbers only; rules unchanged from v1):
training rows ALL = 7,027 expected; live-only variant = 2,049 expected;
everything else — logistic L2 C=1.0, depth-2 GBDT descriptive-only,
expanding quarterly WF + 20-trading-day embargo, τ ∈ {0.5, 0.6}, expectancy
uplift primary, within-date shuffle ×200, the 64 `trade_evaluations` rows
once-only, four-leg PASS/KILL — inherited verbatim from v1 §2–§3.

The external test inherits the same feature set by necessity: the 64
evaluation rows join to `candidate_scores` for features, so they carry S4
availability like every other row; rows unmatched or feature-incomplete are
excluded and counted, and the sign check runs on what remains (stated in the
report).

## 3 · The serving-drift finding (separate lane, recorded here first)

That `candidate_scores` silently changed WHICH features it stamps — sigma
vanishing 2026-05-12, expected_return appearing 2026-04-27 — is a
producer-contract drift on the live serving surface, invisible to every
schema check that only validates column EXISTENCE. It is what made v1
infeasible, and it caps every future entry-time feature set. Filed as an
observability issue in the orchestrator repo (G-F lane) with these measured
dates; fixing the producer is out of scope for this prereg.

## 4 · What v2 does not do

* No threshold, τ, placebo, embargo, fold, metric, or model change.
* No peeked outcome motivates any choice above — the contamination statement
  in §1 is the record.
* No readmission of regime (v1's producer verdict stands) and no readmission
  of sigma/expected_return — if the producer later stamps them reliably,
  that is a NEW dated prereg, not an amendment to this one.
