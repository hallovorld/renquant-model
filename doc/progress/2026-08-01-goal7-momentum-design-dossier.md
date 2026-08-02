# GOAL-7: momentum design dossier committed (operator directive: preserve docs + references)

STATUS: complete (docs-only).
WHAT: `doc/research/2026-08-01-goal7-momentum-design-dossier.md` — the single
committed index of the momentum line: the frozen v1 chain (design #161/#162,
prereg #164, amendments 1/2/4 merged + Amendment 3 re-proposal, runner #177,
base-data#60 manifest, durable store — 294/294 digests verified at publication
`[VERIFIED — publication log 2026-08-01]` — read-only), the measured-negatives
table that shaped the design, and the external literature each choice leans on
(residual momentum, momentum crashes, vol-managed momentum, factor momentum).
WHY/DIR: operator directive 2026-08-01 (in English: preserve the design
documents and references); the references existed only in memory/PR threads,
not as a committed artifact. Non-normative by
construction — preregs govern on any disagreement.
EVIDENCE:
  artifact:      doc/research/2026-08-01-goal7-momentum-design-dossier.md
  prod or exp:   exp — documentation index, no runtime surface
  existing data: every internal row points at an already-merged doc/PR/data
                 bundle in this repo or base-data#60; no new measurements are
                 claimed — each number in the dossier carries a [VERIFIED — 
                 <source>] tag naming the artifact that measured it
  best-known?:   yes — first committed consolidation; previously scattered across the research docs and data
                 bundles this index enumerates (count them there, not here)
  scope:         docs-only; no code, no data, no frozen text edited
NEXT: update by PR as the chain gains/closes documents; v1 verdict flows per
the frozen rules (RETAIN → shadow-only design PR; KILL → v-next directions
kept in §2). AC6 gate-design rule: N/A — docs-only.
