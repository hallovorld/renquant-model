# GOAL-7 v2 verdict: UNRESOLVED-METHOD at the control gate — published verbatim

STATUS: complete (the single v2 shot is consumed and sealed; docs-only PR).
WHAT: doc/research/2026-08-02-goal7-momentum-v2-result.md + sealed
result.json/EXECUTION_CLAIM.json committed byte-verbatim (force-added past
the data/ ignore rule). Positive control 0.5590 vs frozen floor 0.80
(negative 0.0250 ≤ 0.10); H1/H2 never evaluated.
WHY/DIR: honest-negative discipline; the power arithmetic cross-check
(SE 0.01887, ncp 2.12, theoretical ≈0.55) shows the refusal is arithmetic,
not accident. Together with v1's sealed refusal the conclusion is about the
QUESTION: this panel at T=2378 cannot answer mean-IC≥0.04@h=20 under honest
inference at these standards; a third null on the same estimand would be
method-shopping and is not proposed.
EVIDENCE:
  artifact:      doc/research/doc/research/data/2026-08-02-goal7-momentum-v2-result/result.json
                 (sha256 9414edab..., byte-identical to the sealed store copy)
  prod or exp:   exp — research verdict record
  existing data: n_dates 2378, realized_block_sd 0.14496 (ddof=1), bar
                 2.00172, positive 0.5590/floor 0.80, negative 0.0250/ceil
                 0.10, MDE-would-have-passed 0.0378<0.06, placebo published
                 0.0484 `[VERIFIED — result.json, this commit]`
  best-known?:   yes — the one licensed v2 invocation's sealed output
  scope:         docs-only; three forward options laid out as operator
                 decision material without a recommendation ranking
NEXT: operator picks among the three options in the research doc (different
candidate / different question with design-time power arithmetic / stop and
bank the negatives). AC6: N/A — research docs.
