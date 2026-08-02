# Momentum graduates to a standing vertical: train/test/trade architecture fixed

STATUS: proposal (design-only; no behavior change).
WHAT: doc/design/2026-08-02-momentum-pipeline-architecture.md — three
pipelines with repo ownership and contracts: TRAIN (renquant_model_momentum
package; weekly gate-compatible artifacts carrying the #94 admissibility
fields + input-digest records), TEST (the v2 gap-block machinery refactored
into a recurring evaluator appending to an evidence ledger — no gate, no
verdicts; promotion stays on the WF lineage path), TRADE (shadow-only
s104 shadow_models entry inheriting the whole GOAL-1 guard stack; data
collection, no claim). Build order in 5 reviewed slices; the machine landing
is ONE operator grant at the end.
WHY/DIR: operator directive 2026-08-02 ("模型有了，但是要有自己的训练，测试，
交易 pipeline") + what the two sealed studies proved structurally: history
is out of independent observations for the fine question `[VERIFIED — prior
work, model#189/#193]`; the remedies (forward evidence, recurring honest
evaluation, gate-compatible artifacts) ARE a pipeline.
EVIDENCE:
  artifact:      doc/design/2026-08-02-momentum-pipeline-architecture.md
  prod or exp:   exp — design only
  existing data: v2 power numbers and the #190 h=60 arithmetic cited from
                 their sealed/published homes; no new measurement
  best-known?:   yes — first standing-pipeline design for this line; the
                 alternative (a third one-shot study) was ruled out as
                 method-shopping in model#193
  scope:         docs-only; slices 2-4 are separate reviewed PRs; slice 5
                 (launchd + pins) is operator-gated
NEXT: codex review → merge → slice 2 (TRAIN package) dispatched. AC6: N/A —
design doc; the eventual shadow lane adds no capital-admission gate (shadow
is read-only) and the promotion path explicitly defers to the existing gates.
