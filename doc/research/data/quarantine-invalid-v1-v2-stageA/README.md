# QUARANTINE — v1-vs-v2 PIT A/B, Stage A execution `6c992fd`

**Status: SUPERSEDED AND VOID.** See `# STAGE A RESULT` in
`doc/research/2026-07-30-v1-v2-pit-ab-prereg.md` for the full account
(Amendments 2a/2b/2c). Summary of why:

1. Computed with the retired +60d synthetic `B_v1_lag`, not v2's real
   per-fact `filed` date (Amendment 2a).
2. Reads its verdict against a superseded bar, `|t| >= 3.24` instead of the
   corrected `|t| >= 3.29` (Amendment 2b).
3. Applied a `max |t| < 2.0` placebo rule that was not preregistered at
   execution time (Amendment 2c).

These are the raw log/JSON this execution produced, committed here **so an
invalid run is auditable rather than merely asserted** — not because any
number in them is usable. Do not cite them as evidence for a claim.

Originally referenced from `doc/research/data/2026-07-30-v1-v2-ab-stageA.log`
(+ `.json`) — those paths are `.gitignore`d (`data/`) and were never actually
committed despite that citation, so the research doc's `Verbatim: ...` line
was removed rather than left dangling. Copied here under a tracked,
quarantine-labeled path instead, so the artifact is preserved for audit and
the filename itself signals VOID rather than looking like a normal result.
