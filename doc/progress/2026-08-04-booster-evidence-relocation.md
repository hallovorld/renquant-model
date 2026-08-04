# 2026-08-04 — booster divergence + consensus evidence relocated here per orch#712's ruling

STATUS:    relocation of two stranded measurements; doc/evidence only
WHAT:      orch PR #712 was closed OUT-OF-SCOPE with an explicit ruling:
           same-recipe booster divergence measurement belongs in
           renquant-model, source/provenance and non-performance claims
           carried across. Both it and its sibling measurement were found
           2026-08-04 stranded on orchestrator branches, on NO main
           anywhere. Relocated byte-verbatim into doc/evidence/:
           - 2026-08-01-booster-real-panel-divergence/ — 12 same-recipe
             boosters, real panel, 20 sessions: median top-decile
             disagreement 35.7% (corrects the ~60% synthetic figure).
           - 2026-08-01-booster-consensus-structure/ — same corpus:
             66.9% of traded slots carry a >=7/12 majority; the churn is
             a fringe, not the core.
           Each dir carries a RELOCATION.md with the ruling, the claims
           summary, and the machine-local-runner caveat; evaluators and
           guard tests are preserved INSIDE the evidence dirs, not under
           tests/ — this repo's CI must not measure a disk it lacks.
WHY/DIR:   "Relocate, don't just close" + the #778 verbatim-archive
           precedent. These two numbers are the quantified premise of the
           GOAL-8 ensemble ladder; leaving them recoverable only from
           local branches is one `git branch -D` away from erasure.
EVIDENCE:  all files byte-identical to the source branches (git show
           extraction); source branches named in the RELOCATION docs and
           deleted only after this merges.
NEXT:      after merge: delete the three orchestrator branches
           (o712-wt twin included); GOAL-8 S3 design may cite these as
           preregistered inputs.
