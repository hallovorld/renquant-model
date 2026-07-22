# G4: multi-expert output isolation in the Phase A inputs converter   (PR #66)

STATUS:    in-progress
WHAT:      In `build_phase_a_inputs.run_build`, co-locates the per-expert
           admissibility ledger and its calendar evidence under
           `output_dir/<expert_name>/` (the same dir that already holds
           that expert's score files and `universe.txt`):
           `write_calendar_evidence(cal_evidence, output_dir / expert_name)`,
           `ledger_path = write_ledger(ledger, output_dir / expert_name)`.
           The ledger's calendar-evidence locator is a bare filename, so
           co-location keeps it valid. `BuildManifest` gains a
           `ledger_path` field (default `""`, backward compatible). The
           shared forward-returns CSV stays at the `output_dir` root by
           design (expert-independent label data). No admission semantics,
           loader cutoff logic, or ledger content changed — pure
           output-path isolation.
WHY/DIR:   The GOAL-4 Phase A evidence producer writes, per expert, a
           per-date score dir + admissibility ledger + calendar-evidence
           record + a shared forward-returns CSV + a build manifest. A
           second expert built into the SAME `output_dir` must not
           clobber the first expert's evidence — this is the exact defect
           that broadly affected the retired `backfill_scores.py` (PR #54,
           removed by #63). The live successor
           `build_phase_a_inputs.py` (PR #65) had already isolated scores
           + `universe.txt` per expert, but still wrote the admissibility
           ledger + calendar evidence to the shared root, so a second
           expert's build still clobbered the first expert's ledger.
EVIDENCE:  n/a (output-path isolation fix + unit tests, no model/data
           performance claim). New regression test
           `test_second_expert_build_does_not_clobber_first_experts_root_artifacts`
           builds xgb then patchtst into one `output_dir`, asserts xgb's
           ledger + calendar evidence survive byte-for-byte, both experts
           get isolated evidence, and no expert-specific evidence lands at
           the shared root; fails on the pre-fix source, passes with the
           fix. Full ensemble suite:
           `tests/test_build_phase_a_inputs.py tests/test_phase_a_runner.py
           tests/test_admissibility_ledger.py` -> 293 passed.
NEXT:      **Codex's CHANGES_REQUESTED finding on this PR is NOT resolved
           here** — surfaced explicitly, not silently skipped: this fix is
           correctly scoped (output-path isolation only) but it stacks on
           #65, whose Phase-A evidence contract is itself under
           CHANGES_REQUESTED for reconstructing fold/artifact provenance
           post-hoc instead of consuming sim-time-persisted facts (see
           #65's progress doc `NEXT:`). Per Codex: this PR cannot merge
           atop a producer with that open provenance gap; rebase again
           after #65 is redesigned to consume simulation-time-persisted
           fold/artifact/manifest-digest/watermark/timestamp facts, and
           update this isolation test to the resulting required evidence
           schema. Until then, no Phase-A output from this stack (#65+#66)
           is admissible as ensemble evidence — output stays
           `EXPLORATORY_ONLY`.
