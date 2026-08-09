# L3 prereg v2 — the v1 feature set is infeasible on the measured data

STATUS:    design amendment only. Execution STOPPED before any outcome; no
           uplift/placebo/calibration/external number exists anywhere.

WHAT:      doc/design/2026-08-09-l3-classifier-prereg-v2.md — amends exactly
           one clause of the merged v1 prereg (model#207): the feature set,
           6 → 4 (drop expected_return and sigma), plus the missing-data
           policy v1 never froze (complete-case, drop-and-count, no
           imputation). Everything else inherited verbatim.

WHY/DIR:   First execution attempt found the v1 six-feature complete-case
           sample is 631 live rows / 26 dates — the frozen expanding
           quarterly walk-forward from 2024 cannot run, and the ALL-rows arm
           holds zero sim rows. v1 froze no missing-data clause and demands
           zero live choices, so improvising one mid-run was not an option;
           v1's own instrument for this is "a new attempt is a new dated
           prereg".

EVIDENCE:  artifact:      NaN audit + complete-case matrix over the merged
                          l3_candidate_dataset.v2 export (7,167 rows)
                          [VERIFIED — pandas audit, this session]:
                          expected_return missing 5,008 (ALL sim + 30 live;
                          present only on live rows from 2026-04-27);
                          sigma missing 1,528 (live only, 2026-05-12..
                          2026-07-10); mu missing 140 (live, 2026-05-12..
                          05-15). Subset feasibility: v1-S6 = 631 rows /
                          26 dates (live only); v2-S4 = 7,027 rows /
                          519 dates / 2,049 live, span 2024-01-02..
                          2026-07-10.
           prod or exp:   experiment — design doc only; no production
                          surface touched
           existing data: the merged v1 prereg + the merged dataset export;
                          the aborted run's stdout (row counts only — the
                          fold table was empty, crash preceded any metric)
           best-known?:   yes — the alternative sigma-keeping S5 (5,639
                          rows) was measured and rejected IN THE DOC: it
                          erases the 25 most recent live dates, gutting the
                          live-only variant (2,189 → 661)
           scope:         the amendment + the serving-drift finding
                          (candidate_scores stamping drift, filed to the
                          orchestrator G-F lane); producer fix out of scope.

TESTS:     none — prose contract; its test is unchanged from v1: the run
           judged entirely from the frozen tables with zero live choices.

NEXT:      after this merges, execute ONCE under v2 (4 features, 7,027
           rows) with committed CSV + verifier + hash-pinned manifest at
           the #913/#926 standard; report the four legs and PASS/KILL.
