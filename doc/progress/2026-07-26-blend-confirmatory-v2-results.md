# 2026-07-26 — blend confirmatory v2 results: CONFIRMED (independent draw)

STATUS:    results PR for the merged #75 prereg; run via its verbatim frozen command
WHAT:      results memo + replayable bundle (evidence/2026-07-25-blend-confirmatory-v2/)
EVIDENCE:
  artifact:      confirmatory-bundle.json — per-date/per-seed series + freeze manifest
                 (prereg_commit 4a040a9, frozen-section digest, ancestor True)
  prod or exp:   EXPERIMENT, read-only
  existing data: replay verified pre-submission (deserialize_result + verdict_from_bundle
                 recompute CONFIRMED / +0.0687 / [+0.0156,+0.1269] / 9/10 / +0.0117)
  best-known?:   independent draw (seeds 60-69, disjoint from all prior runs 42-51);
                 two draws now agree in direction and magnitude (+0.055 / +0.069)
  scope:         "CONFIRMED under the frozen v2 rule on the survivorship panel;
                 consequence = #213 shadow design unblocks at its gate; NO production
                 change; VERDICTS row after acceptance"
NEXT:      on acceptance -> orchestrator VERDICTS row PR + #213 rollout step PRs
           (model artifact, pipeline shadow slot, orchestrator readout; machine
           landing keeps the operator grant).
