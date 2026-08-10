# Family-comparison fold-8 replay scorer + hash-pinned predictions

STATUS:    executed once; predictions artifact + manifest committed on
           this branch. Relocation of orchestrator PR #953's model-side
           half after its P0 review (the orchestrator runner trained and
           scored XGBoost inside renquant-orchestrator, violating "model
           training internals belong in renquant-model").

WHAT:      scripts/family_comparison_replay_scorer.py — EXACTLY the
           training+scoring half of the orchestrator runner (branch
           research/family-comparison-run, doc/research/data/
           2026-08-10-family-comparison-runner.py), logic preserved
           verbatim: harness constants ast-read (FEATS/CUTS/PARAMS/
           SEEDS/CORPUS_SHA256), corpus sha asserted against the
           harness pin, fold-8 = CUTS[7], per-row purge via the corpus's
           own 60-session endpoint map, fillna(0) + train-stat
           z-normalization clipped to [-5, 5], per-date rank:pairwise
           groups, 100 rounds, seeds (42, 43, 44), replay score = mean
           of the three boosters. Startup assertions: tuple(SEEDS) ==
           (42, 43, 44) and CUTS[7][1] == "2025-12-31". Output is a
           label-free prediction CSV (date,ticker,replay_score) plus a
           sibling manifest pinning both input parquets, the harness,
           and the output CSV by sha256. Labels, live-run data, joining,
           bootstrap, and any verdict stay in the orchestrator (design
           doc 2026-08-09-family-comparison-freeze.md, orch#951): this
           artifact is the consumption surface for the orchestrator's
           join-only runner.

           doc/design/frozen/2026-08-10-family-comparison-replay-
           predictions.csv (+ .manifest.json) — ONE real execution over
           the frozen window 2026-05-20..2026-07-31.

WHY/DIR:   orch#953 P0: the repo boundary is the review surface. Moving
           the trained half here and publishing a hash-pinned artifact
           lets the orchestrator keep only joining/reporting, with the
           handoff auditable by sha256 instead of by trust.

EVIDENCE:  artifact:      doc/design/frozen/2026-08-10-family-comparison-
                          replay-predictions.csv — 7592 prediction rows
                          [VERIFIED — wc -l = 7593 incl. header], sha256
                          b549940e0c70... [VERIFIED — shasum -a 256
                          recomputed independently of the manifest,
                          2026-08-09; equals the manifest's
                          output_csv_sha256]. fold8_train_rows=708723,
                          purged=0 [VERIFIED — scorer stdout + manifest,
                          matching the orchestrator runner's rehearsed
                          expectation exactly; a mismatch was a
                          stop-and-report condition]. Inputs pinned:
                          frozen corpus 870f68ebad5d... [VERIFIED —
                          runtime assert against the harness
                          CORPUS_SHA256 pin], extension parquet
                          7da2f2797c1f..., harness 7ca9e48f3be9...
                          [VERIFIED — hashed at run time into the
                          manifest].
           prod or exp:   experiment. All inputs read-only (frozen
                          corpus, extension parquet, frozen harness); no
                          production path written; run executed in an
                          isolated worktree.
           existing data: the orchestrator runner (research/family-
                          comparison-run) as the verbatim source; the
                          frozen v2 harness doc/design/frozen/
                          2026-08-09-xgbmom-v2-harness.py as the
                          constants authority; the orchestrator
                          rehearsal fixture mechanics as the test
                          template. No new modeling choices were made
                          here — every constant is the harness's or the
                          frozen design's.
           best-known?:   yes — the training recipe is the harness's own
                          (not a re-implementation choice), and the
                          56-line training stretch was diffed
                          byte-identical against the orchestrator source
                          before running [VERIFIED — content-anchored
                          diff, 2026-08-09]. The only deltas are the CLI
                          (W0/W1/out_csv replace runs.db/out_prefix),
                          dropping the label column from the extension
                          read, and the replay->replay_score column
                          name.
           scope:         one new script, one committed prediction
                          artifact + manifest, one new test file, this
                          progress doc. No src/ package changes, no
                          orchestrator changes (the join-only runner is
                          orch#953's follow-up), no live surface
                          touched, no gate or config moved.

TESTS:     tests/test_family_comparison_replay_scorer.py — synthetic
           corpus/extension pair built in tmp_path with a fixture
           harness whose CORPUS_SHA256 is the TRUE fixture-corpus sha
           (the pin assert is exercised, not bypassed). Controls:
           (a) planted-signal ordering recovered in replay_score
           (per-date Spearman vs the planted column, mean > 0.5);
           (b) two end-to-end runs byte-identical; (c) manifest output
           sha matches the file, input pins recomputed independently;
           plus a drifted-corpus fail-closed control. 2 passed in 3.48s
           [VERIFIED — pytest, 2026-08-09]. Full suite: 1563 passed,
           3 skipped in 66s [VERIFIED — make test with the sibling-repo
           PYTHONPATH and ../RenQuant/.venv python, 2026-08-09].

NEXT:      merge this PR → orch#953 rebases to a join-only runner that
           consumes this CSV by its manifest sha (no xgboost import in
           the orchestrator) → the orchestrator-side comparison re-runs
           against the pinned artifact.
