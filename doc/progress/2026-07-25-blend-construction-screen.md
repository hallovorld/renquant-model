# 2026-07-25 — blend-construction screen: provenance repair, PASS

STATUS:    screen prereg frozen (commit 2175e36) then run; evidence committed;
           provenance repaired in two rounds after model#74 review: round 1
           (commit 9c97907) moved the run off an uncommitted scratchpad
           runner; round 2 (commits d8641a4, c054934) fixed the manifest's
           prereg_commit/prereg_digest, which round 1 was still stamping
           from the later in-place RESULTS append (88809c9) instead of the
           true pre-run freeze (2175e36)
WHAT:      the exact blend construction screened with committed replayable
           evidence — the hole the model#73 downgrade identified.
WHY/DIR:   model#73 downgraded the objective-blend result to EXPLORATORY/
           PROVISIONAL because the committed evidence from #68 covered only
           the blend's component arms individually, never the blend
           construction itself — so the reopening chain it set requires
           step 1, a pre-registered screen of the exact blend, with
           committed replayable evidence, before step 2 (a re-frozen
           confirmatory prereg on fresh seeds) can run. This PR is that
           step 1: the prereg was frozen at 2175e36 before the run: full
           disclosure that the blend's screen numbers were already known
           informally, so this run claims no discovery — its sole role is
           durable provenance. It PASSes the prereg's own frozen bar
           (point estimate > 0, ≥2/3 seeds positive), which unblocks step 2
           (PR model#75, fresh seeds 60-69, an independent draw).
EVIDENCE:
  artifact:      doc/research/evidence/2026-07-25-blend-construction-screen/screen-bundle.json
  prod or exp:   EXPERIMENT, read-only; committed in-repo executor
                 (scripts/research_objective_blend_confirm.py), screen seeds 42-44
                 via its --seeds/--prereg-path overrides (commit 9c97907)
  existing data: outcome previously observed informally — disclosed in the frozen
                 prereg; this run's sole role is durable provenance
  best-known?:   deterministic executor; re-run from committed source reproduced
                 byte-identical statistics to the original (uncommitted-runner)
                 pass; manifest now carries a real code_revision (c054934, parent
                 d8641a4) and prereg_digest/prereg_commit bound to the true
                 pre-run freeze commit (2175e36) via _prereg_freeze(), which
                 walks the prereg file's full history for the last commit at
                 which the text BEFORE `## RESULTS` changed, rather than
                 `git log -1` on the whole (RESULTS-amended) file; with
                 prereg_commit_is_ancestor_of_code_revision: true
  scope:         "screen-grade PASS (+0.0627, 3/3 seeds); carries NO verdict; its
                 only consequence is unlocking the step-2 confirmatory prereg with
                 fresh seeds 60-69"
NEXT:      confirmatory prereg v2 PR (fresh seeds), then the run in a results PR;
           only after that does the PARKED #213 shadow design unblock.
