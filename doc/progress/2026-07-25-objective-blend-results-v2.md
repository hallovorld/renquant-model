# 2026-07-25 — objective-blend confirmatory results v2 (replayable bundle)

STATUS:    results PR for the merged model#68 prereg; supersedes closed model#70
WHAT:      results memo + REPLAYABLE evidence bundle
           (`doc/research/evidence/2026-07-25-objective-blend/confirmatory-bundle.json`)
WHY/DIR:   model#70 was closed because its aggregate-only artifact could not replay
           the CI or guards; the merged #68 executor now emits the full
           per-date/per-seed series + freeze manifest, and this PR commits that
           bundle produced by a clean run on main.
EVIDENCE:
  artifact:      evidence/2026-07-25-objective-blend/confirmatory-bundle.json
  prod or exp:   EXPERIMENT, read-only; panel digest sha256:677939fe…, prereg digest
                 sha256:dc34fe5d… stamped in the bundle's freeze manifest
  existing data: replay verified pre-submission via deserialize_result +
                 verdict_from_bundle — recomputes CI, both guards, verdict, matching
                 the run aggregates exactly
  best-known?:   deterministic across four executions (two disclosed as
                 non-citable: pre-catch run killed unread; v1 bundle with a None
                 prereg digest from a concurrent branch switch — both in the memo)
  scope:         "CONFIRMED under the frozen rule on the survivorship panel; CI
                 lower bound +0.0018 (thin); consequence = shadow DESIGN PR only,
                 no production change; VERDICTS row re-adds only after acceptance"
NEXT:      shadow deployment design PR (readout rule frozen there); VERDICTS row
           re-add per the withdrawal note's condition.
