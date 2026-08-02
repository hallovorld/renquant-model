# GOAL-7: momentum design dossier committed (operator directive: preserve docs + references)

STATUS: complete (docs-only).
WHAT: `doc/research/2026-08-01-goal7-momentum-design-dossier.md` — the single
committed index of the momentum line: the frozen v1 chain (design #161/#162,
prereg #164, amendments 1/2/4 merged + 3-re in review, runner #177, base-data#60
manifest, durable store 294/294 verified read-only), the measured-negatives
table that shaped the design, and the external literature each choice leans on
(residual momentum, momentum crashes, vol-managed momentum, factor momentum).
WHY/DIR: operator 2026-08-01: "保留设计文档和reference"; the references existed
only in memory/PR threads, not as a committed artifact. Non-normative by
construction — preregs govern on any disagreement.
EVIDENCE:
  artifact:      doc/research/2026-08-01-goal7-momentum-design-dossier.md
  prod or exp:   exp — documentation index, no runtime surface
  existing data: every internal row points at an already-merged doc/PR/data
                 bundle in this repo or base-data#60; no new measurements are
                 claimed `[早前实测 pointers only]`
  best-known?:   yes — first committed consolidation; previously scattered
                 across 9 research docs + 4 data bundles + PR threads
  scope:         docs-only; no code, no data, no frozen text edited
NEXT: update by PR as the chain gains/closes documents; v1 verdict flows per
the frozen rules (RETAIN → shadow-only design PR; KILL → v-next directions
kept in §2). AC6 gate-design rule: N/A — docs-only.
