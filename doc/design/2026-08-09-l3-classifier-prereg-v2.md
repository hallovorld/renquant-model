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
stamping turned INTERMITTENT from 2026-05-12 — every missing-sigma row is
dated 2026-05-12..2026-07-10, but 443 live rows inside that window still
carry sigma `[VERIFIED — committed verifier, §5]`. Their intersection — rows carrying all
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
guts the live slice the live-only VARIANT exists to check: live rows fall
2,189 → 661 (30.2% retained), 10 of the 40 live dates lose every row, and
post-2026-05-12 coverage turns partial — 20 of the 29 post-cutoff live
dates retain at least one row, 443 rows in total `[VERIFIED — committed
verifier, §5]`. S4 keeps 7,027 rows / 519 dates / 2,049 live rows spanning
2024-01-02..2026-07-10 `[VERIFIED — committed verifier, §5]`. Availability
of the four retained features, stated exactly: POOLED, each is ≥98%
available (mu 7,027/7,167 = 98.05%; the other three 100%). Per run_type,
panel_score / rank_score / n_candidates_that_date are 100% on both; mu is
100% on sim but 93.60% on live (2,049/2,189 — the 140 missing live rows
are exactly the four dates 2026-05-12..15, which S4 drops-and-counts)
`[VERIFIED — committed verifier, §5]`. Dropping a feature that does not
exist in the data is a feasibility repair, not a tuning move; no outcome
influenced it.

Consequential restatement (numbers only; rules unchanged from v1):
training rows ALL = 7,027 expected; live-only variant = 2,049 expected;
everything else — logistic L2 C=1.0, depth-2 GBDT descriptive-only,
expanding quarterly WF + 20-trading-day embargo, τ ∈ {0.5, 0.6}, expectancy
uplift primary, within-date shuffle ×200, the 64 `trade_evaluations` rows
once-only, four-leg PASS/KILL — inherited verbatim from v1 §2–§3.

The external test inherits the same feature set by necessity, and its
population is FROZEN here, before execution. Join rule (deterministic):
each of the 64 `trade_evaluations` rows takes features from the frozen
dataset itself, keyed (run_date(run_id), ticker) — the canonical
widest-run row, the SAME construction as every training row. Measured
funnel `[VERIFIED — committed verifier, §5]`: 64 rows → 46 match a dataset
row (18 unmatched — chiefly sells of held names that were not candidates
that date) → 34 are S4-feature-complete (12 dropped on missing mu). The
frozen external denominator is therefore **34 rows** (32 buy / 2 sell; 14
distinct (run_id, ticker, action) trades over 3 run dates,
2026-05-08..2026-05-20), identifier list committed at
`doc/design/frozen/2026-08-09-l3-prereg-v2-external-eligible.txt` (sha256
`1e1bff4d…`). Insufficient-data KILL rule `[ASSUMED — frozen here]`: leg 3
runs on exactly the frozen 34-row list; if the recomputed eligible set
drifts from that list, or had the list held fewer than 30 rows or 10
distinct trades, leg 3 is not evaluable and the run records KILL — PASS
requires all four legs, so an unevaluable leg fails closed. With 34
correlated rows over 3 dates the leg remains a sign check and is stated as
such (v1 already scoped it so at n=64).

## 3 · The serving-drift finding (separate lane, recorded here first)

That `candidate_scores` silently changed WHICH features it stamps — sigma
turning intermittent from 2026-05-12, expected_return appearing 2026-04-27
— is a
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

## 5 · Frozen feasibility artifacts (review r2 — independently auditable)

The feasibility record is committed, hash-pinned, and re-derivable without
this session:

* `doc/design/frozen/2026-08-09-l3-candidate-dataset-v2.csv` — the exact
  `l3_candidate_dataset.v2` export this amendment is judged on (sha256
  `eecfd050…`), with the builder's manifest beside it (sha256 `79f5d9f5…`).
* `doc/design/frozen/l3_prereg_v2_feasibility.py` — read-only verifier:
  re-checks both hashes, recomputes the availability table and the S6/S5/S4
  complete-case counts and date spans from the CSV, recomputes the external
  funnel from a `mode=ro` DB open, and EXITS NON-ZERO on any drift from its
  frozen constants. It reads no outcome value: dataset outcome columns are
  used for non-emptiness only, and the `trade_evaluations` query selects
  identifier columns only.
* `doc/design/frozen/2026-08-09-l3-prereg-v2-external-eligible.txt` — the
  frozen 34-row external population (sha256 `1e1bff4d…`).
* `tests/test_l3_prereg_v2_feasibility.py` — regression guard: pins the
  hashes and counts, proves outcome-invariance (permuting/negating every
  outcome value in the dataset leaves the report identical), and pins the
  external join rule on synthetic rows.

Execution (the NEXT step) consumes the committed CSV — a rebuild that
hash-drifts means the DB moved past the freeze, never that the freeze
moves. (The directory is `doc/design/frozen/`, not `…/data/`, because this
repo's .gitignore excludes any `data/` directory.)

## 6 · Corrections (review r2, 2026-08-09 — visible per LONG row 10)

Three r1 claims were wrong or overstated; each is corrected in place above,
and the committed verifier pins the corrected values:

1. §2 formerly claimed S5 "erases the 25 most recent live dates". Measured:
   S5 fully erases 10 of the 40 live dates; 20 of the 29 post-2026-05-12
   live dates retain at least one row (443 rows). The S5 rejection stands
   on the corrected ground: ~70% of live rows and a quarter of the live
   dates still vanish from the slice the live-only VARIANT exists to check.
2. §2 formerly claimed every retained feature is "≥98% available on BOTH
   run_types". Measured: ≥98% holds POOLED; on the live slice mu is 93.60%
   (2,049/2,189). The sentence now states pooled and per-run_type
   availability exactly.
3. §1/§3 formerly described sigma as having "stopped being stamped" on
   2026-05-12. Measured: stamping turned intermittent — every missing-sigma
   row falls in 2026-05-12..2026-07-10, yet 443 live rows in that window
   still carry sigma.
