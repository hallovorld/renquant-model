# L3 prereg v2 — the v1 feature set is infeasible on the measured data

STATUS:    design amendment only. Execution STOPPED before any outcome; no
           uplift/placebo/calibration/external number exists anywhere.

WHAT:      doc/design/2026-08-09-l3-classifier-prereg-v2.md — amends exactly
           one clause of the merged v1 prereg (model#207): the feature set,
           6 → 4 (drop expected_return and sigma), plus the missing-data
           policy v1 never froze (complete-case, drop-and-count, no
           imputation). Everything else inherited verbatim. Review r2 added
           the committed feasibility record: the frozen dataset CSV +
           manifest, a read-only drift-failing verifier, the frozen 34-row
           external-test population, and a regression-guard test
           (doc/design/frozen/ + tests/test_l3_prereg_v2_feasibility.py).

WHY/DIR:   First execution attempt found the v1 six-feature complete-case
           sample is 631 live rows / 26 dates — the frozen expanding
           quarterly walk-forward from 2024 cannot run, and the ALL-rows arm
           holds zero sim rows. v1 froze no missing-data clause and demands
           zero live choices, so improvising one mid-run was not an option;
           v1's own instrument for this is "a new attempt is a new dated
           prereg".

EVIDENCE:  artifact:      doc/design/frozen/ — the exact
                          l3_candidate_dataset.v2 export (CSV sha256
                          eecfd050…, manifest sha256 79f5d9f5…, 7,167 rows)
                          + l3_prereg_v2_feasibility.py, a read-only
                          verifier that recomputes every count below and
                          exits non-zero on drift
                          [VERIFIED — verifier run with --db, this session;
                          all frozen counts reproduced]:
                          expected_return missing 5,008 (ALL sim + 30 live;
                          present only on live rows from 2026-04-27);
                          sigma missing 1,528 (live only, all dated
                          2026-05-12..2026-07-10, stamping intermittent —
                          443 live rows in that window still carry it);
                          mu missing 140 (live, the four dates 2026-05-12..
                          05-15; live availability 2,049/2,189 = 93.60%,
                          pooled 7,027/7,167 = 98.05%). Subset feasibility:
                          v1-S6 = 631 rows / 26 dates (live only); v2-S4 =
                          7,027 rows / 519 dates / 2,049 live, span
                          2024-01-02..2026-07-10. External population,
                          frozen before execution: 64 trade_evaluations
                          rows → 46 match a dataset row → 34 S4-complete
                          (32 buy / 2 sell, 14 distinct trades, 3 run
                          dates); id list committed, sha256 1e1bff4d….
           prod or exp:   experiment — design doc + committed frozen
                          artifacts; no production surface touched (DB
                          opened mode=ro only)
           existing data: the merged v1 prereg + the merged dataset export;
                          the aborted run's stdout (row counts only — the
                          fold table was empty, crash preceded any metric)
           best-known?:   yes — the alternative sigma-keeping S5 (5,639
                          rows) was measured and rejected IN THE DOC: live
                          rows fall 2,189 → 661 (30.2% retained), 10 of 40
                          live dates lose every row, 20 of 29
                          post-2026-05-12 live dates keep ≥1 row (443 rows)
           scope:         the amendment + the frozen feasibility record +
                          the serving-drift finding (candidate_scores
                          stamping drift, filed to the orchestrator G-F
                          lane); producer fix out of scope.

TESTS:     tests/test_l3_prereg_v2_feasibility.py — 7 passed (0.19s):
           frozen hashes + counts pinned, injected drift detected,
           outcome-invariance proven (permuting/negating every outcome
           value leaves the report identical), external join rule pinned
           on synthetic rows. Verifier CLI run with --db (mode=ro):
           FEASIBILITY VERIFIED, exit 0.

CORRECTIONS (review r2, visible per LONG row 10): r1 of this doc claimed S5
           "erases the 25 most recent live dates" and that every retained
           feature is "≥98% available on BOTH run_types". Measured: S5
           fully erases 10 of 40 live dates (20 of 29 post-cutoff dates
           keep 443 rows), and ≥98% holds POOLED only — mu is 93.60% on
           live. Corrected here and in the design doc §6; the S5 rejection
           and the amendment stand on the corrected numbers.

NEXT:      after this merges, execute ONCE under v2 (4 features, 7,027
           rows) consuming the committed frozen CSV (hash re-checked by the
           verifier at run start); report the four legs and PASS/KILL on
           the frozen 34-row external denominator.
