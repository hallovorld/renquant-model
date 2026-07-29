# Progress: corrected-evaluation results — EXPLORATORY only (not yet confirmatory)

STATUS:   in-progress. Restores the results document that was removed from model#90 for
          citing an unauditable path, but review (PR #92, two CHANGES_REQUESTED passes)
          caught that the restored bundle is itself defective in two ways this doc must
          not paper over — downgraded to exploratory per the fix below.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-results.md`: the Q1
          decision statistic recomputed with the merged three-view estimator, the raw-IC
          contrast, and an explicit statement of what is NOT established. The document
          now leads with an EXPLORATORY caveat (not confirmatory) instead of presenting
          the numbers as a settled post-prereg verdict.

WHY/DIR:  model#90 froze the design and merged; its numbers had been stripped because
          they pointed at session scratch. The artifacts are now retained and
          content-addressed over their OUTPUT files, so the same numbers are quotable as
          exploratory findings — but two defects block treating them as confirmatory:
          (1) the retained bundle (`harness.py`/`results.json`/`verdict.json`) is
          timestamped 2026-07-28 23:34-23:35 PDT, ~3h BEFORE model#90 merged at
          2026-07-29 02:19:34 PDT `[VERIFIED - git log -1 8579fa7; ls -la on the
          bundle]` — it cannot be "recomputed against the merged prereg" when it
          predates the merge; (2) the harness reads mutable inputs from
          `/Users/renhao/git/github/RenQuant/data/...` and session-scratch parquet
          outside the bundle, and imports from `/private/tmp/renquant-model-pr89-review
          /src` — the root digest covers only outputs, so a verifier cannot reproduce
          these numbers from the bundle alone.

EVIDENCE:
artifact:      /Users/renhao/renquant_bundles/corrected-eval-20260729/ (44 files, root
               digest f6b6ef6d5055600df190da9d56c32453e31b71c54ff5beeda88e12caac0df38a
               over OUTPUT files only, re-verifiable with `tools/corpus_index.py
               verify`, model#91 — does NOT cover inputs, see WHY/DIR)
prod or exp:   experiment — signal-evaluation research artifact, not a production/live
               path
existing data: model#90's Q1 result was stripped for citing an unauditable
               session-scratch path; this PR recomputes the SAME statistic
               (`d = REAL - persistence` on per-date rank IC, block_length 60, 1500
               bootstrap resamples, via `dependence_aware_mean`, model#89) against the
               retained bundle above, but the bundle predates model#90's merge by ~3h
               and reads unhashed mutable inputs, so it is exploratory, not a
               falsifiable post-freeze confirmatory record
               `[VERIFIED - recomputed 2026-07-29, ordering defect found on review]`
best-known?:   not confirmatory — see STATUS. The paired-difference numbers (prod XGB
               +0.0359 t +1.23 CI [+0.0218, +0.0787]; certified clf +0.0113 t +1.31 CI
               [+0.0049, +0.0275]; PatchTST -0.0488 t -2.31 CI [-0.0772, -0.0050]) and
               the raw-IC contrast (only prod XGB resolves; certified clf's absolute IC,
               largest block t of the three at +1.52, still crosses zero
               [-0.0287, +0.1749]) are exploratory only until re-run per NEXT
scope:         "this is /Users/renhao/renquant_bundles/corrected-eval-20260729/,
               experiment, EXPLORATORY (not confirmatory — predates model#90's merge,
               unhashed inputs) Q1 paired-difference vs each subject's own 60-day-lagged
               persistence baseline — vs raw-IC levels where only prod XGB resolves."
               No Sharpe or return claim is made.

NEXT:     Re-run the harness strictly AFTER model#90's merge (8579fa7), with the exact
          input parquet files (panel, prod-XGB scores, clf/PatchTST WF scores) and the
          code revision pinned and content-hashed INTO the bundle itself — not read from
          mutable RenQuant/scratch paths — before any confirmatory claim is made. Until
          then this stays exploratory. The clf's ABSOLUTE IC must not be quoted as
          established anywhere regardless of that re-run; its paired result may.
          PatchTST's closure still needs its own registered kill rule — model#87 is
          retracted and may not be reused as-is.
