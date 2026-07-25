# 2026-07-25 — objective-blend confirmatory results v2 (replayable bundle)

STATUS:    results PR for the merged model#68 prereg; supersedes closed model#70;
           re-run + reclassified per model#73 review round 2 (both CHANGES_REQUESTED)
WHAT:      results memo + REPLAYABLE evidence bundle
           (`doc/research/evidence/2026-07-25-objective-blend/confirmatory-bundle.json`),
           re-run from a checkout rebased onto merged main (924ed1b) with an
           ancestry-provable manifest, and reclassified EXPLORATORY/PROVISIONAL
WHY/DIR:   model#70 was closed because its aggregate-only artifact could not replay
           the CI or guards; the merged #68 executor now emits the full
           per-date/per-seed series + freeze manifest. model#73 review found the
           first bundle's manifest.code_revision (264a322) was the unmerged head of
           model#72, stamped before 924ed1b actually merged (BLOCKER 1) — fixed by
           re-running from this checkout, now a true descendant of 924ed1b. Review
           also found the prereg's screen provenance never screened the exact
           `blend` construction, only its component arms individually (BLOCKER 2) —
           fixed by downgrading the PR's standing to EXPLORATORY/PROVISIONAL and
           withdrawing the shadow-design/ledger consequence. HIGH (durable data
           locator) fixed by adding `producing_script` git-revision + row_count +
           date_range to the manifest.
EVIDENCE:
  artifact:      evidence/2026-07-25-objective-blend/confirmatory-bundle.json
  prod or exp:   EXPERIMENT, read-only; panel digest + prereg digest stamped in the
                 bundle's freeze manifest, alongside code_revision_parents /
                 prereg_commit / prereg_commit_is_ancestor_of_code_revision
  existing data: replay verified pre-submission via deserialize_result +
                 verdict_from_bundle — recomputes CI, both guards, verdict, matching
                 the run aggregates exactly
  best-known?:   the frozen decide_verdict() rule's technical output on this run is
                 CONFIRMED; the PR's own standing is downgraded to
                 EXPLORATORY/PROVISIONAL per model#73 review (see results memo
                 Classification section) — not yet a promotable result
  scope:         "statistically CONFIRMED under the frozen rule on the survivorship
                 panel; PR standing EXPLORATORY/PROVISIONAL pending an immutable
                 blend-specific screen; no shadow-design or ledger consequence
                 authorized by this PR"
NEXT:      pre-registered screen of the exact `blend` construction (committed
           evidence) to re-earn CONFIRMED standing; only then re-freeze a
           confirmatory prereg citing that screen and consider the shadow design PR.
