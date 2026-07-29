# Progress: corrected-evaluation results, with auditable provenance

STATUS:   delivered. Restores the results document that was removed from model#90 for
          citing an unauditable path — the objection is answered, not argued with.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-results.md`: the Q1
          decision statistic recomputed with the merged three-view estimator, the raw-IC
          contrast, and an explicit statement of what is NOT established.

WHY/DIR:  model#90 froze the design and merged; its numbers had been stripped because
          they pointed at session scratch. The artifacts are now retained and
          content-addressed, so the same numbers are quotable on different grounds:
          they are falsifiable by recomputation rather than taken on trust.

EVIDENCE:
artifact:      /Users/renhao/renquant_bundles/corrected-eval-20260729/ (44 files, root
               digest f6b6ef6d5055600df190da9d56c32453e31b71c54ff5beeda88e12caac0df38a,
               re-verifiable with `tools/corpus_index.py verify`, model#91)
prod or exp:   experiment — signal-evaluation research artifact, not a production/live
               path
existing data: model#90's Q1 result was stripped for citing an unauditable
               session-scratch path; this PR recomputes the SAME statistic
               (`d = REAL - persistence` on per-date rank IC, block_length 60, 1500
               bootstrap resamples, via `dependence_aware_mean`, model#89) against the
               retained, content-addressed bundle above — same numbers, now falsifiable
               by recomputation `[VERIFIED - recomputed 2026-07-29]`
best-known?:   yes for the paired-difference view: all three subjects RESOLVE across
               block-t, bootstrap CI and leave-one-block-out (prod XGB +0.0359 t +1.23
               CI [+0.0218, +0.0787]; certified clf +0.0113 t +1.31 CI [+0.0049,
               +0.0275]; PatchTST -0.0488 t -2.31 CI [-0.0772, -0.0050]). For raw-IC
               LEVELS only prod XGB resolves; certified clf's absolute IC (largest
               block t of the three, +1.52) still crosses zero [-0.0287, +0.1749] and
               must NOT be quoted as established
scope:         "this is /Users/renhao/renquant_bundles/corrected-eval-20260729/,
               experiment, Q1 paired-difference vs each subject's own 60-day-lagged
               persistence baseline — vs raw-IC levels where only prod XGB resolves."
               No Sharpe or return claim is made.

NEXT:     The clf's ABSOLUTE IC must not be quoted as established anywhere; its
          paired result may. PatchTST's closure still needs its own registered kill
          rule — model#87 is retracted and may not be reused as-is.
