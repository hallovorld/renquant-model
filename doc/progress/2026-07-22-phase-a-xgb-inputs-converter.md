# GOAL-4 Phase A — walk-forward-sim -> Phase A inputs converter (XGB expert)   (PR #65)

STATUS:    in-progress
WHAT:      `experiments/ensemble_phase0/build_phase_a_inputs.py` — a
           scorer-agnostic CLI converter: reads a walk-forward-sim DB's
           per-date `score_distribution` for ONE scorer + the WF manifest
           (`retrains[]`), and emits the Phase-A score-dir (one
           `YYYY-MM-DD.json` per date in the exact schema
           `admissibility_ledger.load_score_file` /
           `extract_metadata_from_score` read) + a shared `returns.csv`.
           Admission is deferred to the CANONICAL validator
           (`admissibility_ledger.build_ledger`) — the converter never
           self-attests `admitted: true`. PIT vintage selection: a sim
           date `D`'s vintage is the LATEST walk-forward fold whose
           `cutoff_date + BDay(lookahead_days)` is strictly before `D`
           (business-day offset, matching
           `effective_train_cutoff_date` / `WalkForwardModelLoader.entry_as_of`);
           `training_cutoff` is stamped as that fold's real `cutoff_date`
           (never `"MISSING"`); model fingerprint = SHA-256 of the fold's
           resolved `artifact_uri` when readable, falling back to a
           clearly-flagged `provenance_bound:` digest
           (`is_real_content_digest=False`) only when the artifact cannot
           be resolved. Every emitted record carries
           `classification: EXPLORATORY_ONLY`. XGB expert inputs produced
           for window 2025-08-25 -> 2026-03-27: 149 dates written, 116
           ADMITTED by the canonical validator (33 rejected, all legitimate
           coverage/label reasons, zero schema/causal-chain rejects), 12
           distinct WF folds, all with real artifact content digests.
           `tests/test_build_phase_a_inputs.py` — 10 tests (BDay boundary,
           latest-eligible-fold pick, real `training_cutoff` stamping,
           date-before-coverage exclusion, score-column SQL guard,
           artifact-digest real-vs-fallback, end-to-end synthetic build the
           canonical validator ADMITS).
WHY/DIR:   GOAL-4 Phase A ensemble evaluation is BLOCKED on evidence volume
           (`doc/research/2026-07-16-g4-phase-a-data-audit.md`); the
           actionable path is a pseudo-OOS historical reconstruction from
           archived WF model vintages + walk-forward-sim scores. This PR
           builds that reconstruction's reusable tooling and produces the
           XGB expert's inputs so the 2-expert Phase A can run once the
           fresh PatchTST WF-sim corpus lands. Also addresses model#64's
           PIT-correctness feedback (real `training_cutoff` vs the retired
           `backfill_scores`' honest `"MISSING"`).
EVIDENCE:  n/a (experiment tooling + unit tests, no model/data performance
           claim; output is explicitly `EXPLORATORY_ONLY`, never fed into a
           champion/L1 promotion decision).
           `python -m pytest tests/test_build_phase_a_inputs.py` -> 10
           passed. Real-data run: 149 dates -> 116 admitted (see WHAT).
NEXT:      **Codex's CHANGES_REQUESTED finding on this PR is NOT resolved
           here** — surfaced explicitly, not silently skipped: the
           converter still reconstructs fold/artifact identity AFTER the
           fact from `score_distribution` + the manifest rather than
           consuming provenance the sim persisted AT GENERATION TIME (fold
           cutoff, artifact content digest, manifest/lock digest, input
           watermark, actual score timestamp), so it cannot rule out a
           score having been produced by a different fold/manifest/code
           revision than the one it certifies, and the `provenance_bound:`
           fallback is a syntactically-valid-but-unverified surrogate.
           Fixing this requires changing the WF SIM (a different
           component/repo than this converter) to persist those fields at
           generation time, then reworking this converter to require and
           cross-check them, then re-running both the XGB and PatchTST
           sims and re-verifying admission — out of scope for a mechanical
           control-contract fix pass; needs its own PR. Until that lands,
           this PR's output stays labeled `EXPLORATORY_ONLY`
           (already true today) and must NOT be cited as Phase-A evidence
           for a champion/L1 decision. This also keeps #64 and the stacked
           #66 blocked per Codex's review.
