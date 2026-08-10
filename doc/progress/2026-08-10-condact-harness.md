# Conditional-activation harness — the §5 freeze surface, committed pre-run

STATUS:    harness + verifier + both controls committed; NO real read has
           occurred (the §5.6 order: controls land first).

WHAT:      doc/design/frozen/2026-08-10-condact-harness.py (+ verifier +
           control JSONs). Implements the merged model#215 §5 as code:
           E-exploratory stamping; features/bootstrap params sourced from
           the v2 harness single-source; ROC20 dispersion with per-date
           exclusion counts; 252-session warm-up fail-closed; stationary
           block bootstrap (21/2000/seed 99) as committed code; hard-exit
           controls; Stage C NOT invocable in this version (constructive
           refusal — a C-capable harness is its own reviewed amendment
           once orch#939 lands and the clock guards can hold).

WHY/DIR:   §5's binding: prediction generation holds material freedom, so
           the harness must land reviewed BEFORE any real read. Controls:
           positive (condition-dependent planted signal) PASS; null
           (unconditional signal) KILL — the harness distinguishes
           "model good" from "model conditionally good".

EVIDENCE:  artifact:      both control JSONs [VERIFIED — committed
                          verifier, exit 0; positive A1 0.195 vs A0
                          0.002 PASS; null A1≈A0 KILL]
           prod or exp:   experiment tooling; nothing real read
           existing data: the merged v2 artifacts (imported constants)
           best-known?:   yes — C-refusal is constructive (the flag does
                          not exist), not a promise
           scope:         after merge: ONE Stage-E run (exploratory
                          diagnostics, no verdict authority), published
                          with stage-stamped artifacts.

TESTS:     controls under the frozen rules, hard exit codes; verifier
           enforces stage/kind/features-sha/bootstrap-params/countersign.

NEXT:      merge → Stage-E run same day (diagnostics only) → C-capable
           amendment PR after orch#939.
