# GOAL-7: the single --execute crashed at IMPORT — root-caused, fixed, claim removal recorded

STATUS: complete (fix + regression tests); re-execution follows this PR's merge.
WHAT: `total_return_close` moved VERBATIM to its package home
(`renquant_model_common/total_return.py`); the build script imports it from
there and keeps its own guards; the runner imports the package (no script
execution); preflight gains `tr_builder_importable` (BaseException-caught,
incl. SystemExit) so any future import-time failure is a pre-inference
UNRESOLVED-DATA that RELEASES the claim. The concurrent session's
forgetful-test is updated from "the real store must not exist" (false after
any real execution) to a before/after no-leak comparison.
WHY/DIR: the first granted --execute (claim 11:02:30Z) died at
`_load_tr_builder`: importing `build_total_return_series.py` executes the
JULY study's module-level raw-corpus pin guard + build loop, and that pin no
longer matches the refreshed live raw layer — a guard validating the WRONG
object for this runner (its inputs are the frozen digest-verified store;
preflight was 12/12 PASS). SystemExit bypassed the never-raises Exception
handler; my launch command's `| tail` masked the real exit code (the known
pipe-exit trap).
EVIDENCE:
  artifact:      src/renquant_model_common/total_return.py (verbatim body),
                 tools/build_total_return_series.py (import swap),
                 tools/goal7_momentum_run.py (package import + preflight
                 check), tests/test_goal7_momentum_runner.py (+3 regressions:
                 import-no-side-effects; hand-checked dividend arithmetic pin;
                 SystemExit → preflight refusal)
  prod or exp:   exp — research runner + build tooling; no serving surface
  existing data: the ABORT text + stranded claim (status in-progress, pid
                 94867, claimed_at 2026-08-02T11:02:30Z) `[VERIFIED — read
                 before removal]`; ZERO estimand computed (death at code
                 import, before any panel/OHLCV read)
  best-known?:   yes — the function's one importable home replaces a script
                 import that executed a study
  scope:         18/18 runner tests (15 prior + 3 regressions; the
                 forgetful-test updated in place); make test 1393 passed
                 `[VERIFIED — pytest 2026-08-02, both counts measured]`
NEXT: codex review → merge → re-execute the single --execute (legitimate:
zero statistics were computed by the crashed attempt; the claim's own
docstring names manual removal WITH a durable record — THIS DOC is that
record, and the refusals ledger gains the entry at re-execution preflight).
AC6: N/A — research tooling.
