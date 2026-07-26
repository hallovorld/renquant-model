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
EVIDENCE:  n/a — this PR only freezes the decision rule; it makes no model/
           data claim. The step-1 screen evidence it builds on is committed
           at `doc/research/evidence/2026-07-25-blend-construction-screen/screen-bundle.json`
           (PR #74, PASS +0.0627, 3/3 seeds; provenance repaired in #74's
           fix at commit `b3a8a39` — manifest now carries a real
           code_revision/prereg_digest/prereg_commit bound to committed
           source, not the uncommitted scratchpad runner Codex flagged).
           This PR also inherits #74's `--seeds`/`--prereg-path` executor
           fix (commit `9c97907`, stacked base), which makes seeds 60-69
           and this prereg's path explicit reviewed run inputs rather than
           requiring an unreviewed executor edit at run time. The step-2
           run itself, and its evidence bundle, land in a separate results
           PR per this prereg's own "frozen on merge, run follows
           separately" rule.
NEXT:      run the executor on seeds 60-69 in a separate results PR;
           CONFIRMED unblocks the PARKED shadow design (renquant-pipeline#213)
           at its step-2 gate; REFUTED closes the line as seed-draw-fragile;
           INCONCLUSIVE authorizes exactly one extension (seeds 70-79, joint
           Bonferroni), then mandatory closure.
