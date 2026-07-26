# 2026-07-25 — CONFIRMATORY prereg v2: blend objective, fresh seeds 60-69 (reopening step 2)

STATUS:    prereg frozen on merge; run and results land in a separate PR that
           may not amend this document.
WHAT:      `doc/research/2026-07-25-blend-confirmatory-v2-prereg.md` — the
           frozen decision rule for step 2 of the model#73 reopening chain,
           stacked on #74 (step 1, the blend-construction screen, PASS).
WHY/DIR:   model#73 downgraded the objective-blend result to EXPLORATORY/
           PROVISIONAL and set a two-step reopening condition: (1) a
           pre-registered screen of the exact blend construction with
           committed evidence — PASS'd in #74 — then (2) a re-frozen
           confirmatory prereg citing that screen, run on an independent
           draw. This PR is step 2: every prior run of this line (informal
           screens, the withdrawn #70/#73 sequence, the #74 screen) used
           seeds 42-51; this prereg pins fresh seeds 60-69, never used
           anywhere in this line, so a future PASS is a genuine out-of-draw
           confirmation rather than a replay. The decision rule (CONFIRMED /
           REFUTED / INCONCLUSIVE with one pre-authorized extension) is
           frozen here, before the run, per the standing prereg discipline
           (`AGENT-RETROSPECTIVE.md` §4b / promotion-methodology triad).
EVIDENCE:  n/a for this PR's own change (it only freezes the decision rule;
           it makes no model/data claim of its own). It does cite step-1
           (#74) as a supporting prerequisite, so that citation carries its
           own §4(b) block rather than free-form prose:
  artifact:      doc/research/evidence/2026-07-25-blend-construction-screen/screen-bundle.json
  prod or exp:   experiment (screen-grade; carries no verdict of its own)
  existing data: PASS +0.0627/60d, 3/3 seeds positive against the screen's
                 own frozen bar (point estimate > 0, ≥2/3 seeds positive)
  best-known?:   step-1 screen only — its sole role is unblocking step 2
                 (this PR); it is not itself the confirmatory read
  scope:         "this is #74's screen-bundle.json, EXPERIMENT; provenance
                 is bound to the true pre-run freeze commit `2175e36` (not
                 the post-run RESULTS-append commit `88809c9` an earlier
                 repair round mistakenly stamped) via #74's fix (commits
                 `d8641a4`, `c054934`, `5a65f3c` — `code_revision=c054934`,
                 `prereg_commit_is_ancestor_of_code_revision=true`)"
           This PR also inherits #74's `--seeds`/`--prereg-path` executor
           override (commit `9c97907`, stacked base), which makes seeds
           60-69 and this prereg's path explicit reviewed run inputs rather
           than requiring an unreviewed executor edit at run time. The
           step-2 run itself, and its evidence bundle, land in a separate
           results PR per this prereg's own "frozen on merge, run follows
           separately" rule.
NEXT:      run the executor on seeds 60-69 in a separate results PR;
           CONFIRMED unblocks the PARKED shadow design (renquant-pipeline#213)
           at its step-2 gate; REFUTED closes the line as seed-draw-fragile;
           INCONCLUSIVE authorizes exactly one extension (seeds 70-79, joint
           Bonferroni), then mandatory closure.
