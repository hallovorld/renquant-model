# Results — tail-aware blend objective vs production rank:pairwise: CONFIRMED

Date: 2026-07-25
Prereg (FROZEN): `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md`
Evidence: `doc/research/evidence/2026-07-25-objective-blend/confirmatory-result.json`
Executor: `scripts/research_objective_blend_confirm.py` (guard (b) verbatim)

## Verdict — CONFIRMED [VERIFIED: recomputed from the printed run output;
NOT independently replayable from the committed bundle — see the
"Disclosed reproducibility gap" section of this PR's progress doc,
`doc/progress/2026-07-25-objective-blend-confirmatory-results.md`. model#68's
round-3/4 fix (bundle + manifest) landed after this run completed.]

All three frozen conditions met:

| condition | frozen requirement | measured |
|---|---|---|
| primary | block-bootstrap 90% CI lower bound > 0 | **+0.0018** (diff +0.0552/60d, CI [+0.0018, +0.1085]) |
| guard (a) | ≥8/10 seed signs positive | **10/10** |
| guard (b) | winsorized-±50% diff ≥ 0 | **+0.0095** |

blend clean top-10 spread **+0.2873/60d** vs production rank:pairwise
**+0.2321/60d** — **+24% relative on the harvest statistic**, positive in
every one of 10 seeds (blend range +0.2271…+0.3533; rank60 range
+0.1903…+0.2969; no overlap of seed means in the wrong direction).

## Run-integrity timeline (disclosed in full)

1. Decision rule frozen (orchestrator commit `ede9e76c`, 2026-07-25,
   pre-run; identical text relocated here as model#68).
2. First run launched; review round-1 (model#68) correctly found the
   executor implemented guard (b) as a trimmed-mean surrogate rather than
   the frozen winsorized statistic. The run was **killed before any
   arm-vs-arm contrast was computed or read** (only baseline per-seed level
   lines had printed).
3. Executor fixed to the frozen guard verbatim; full rerun produced the
   numbers above. No decision-rule text changed at any point.

## Pre-committed consequence (from the frozen prereg)

**CONFIRMED → a SHADOW deployment design PR follows. Nothing in this result
authorizes a production config change.** The shadow design will route the
blend scorer through the existing shadow-scorer infrastructure
(renquant-pipeline #211 health-record line) with a forward clean-spread
readout rule frozen in that design PR. The historical corpus supplied the
hypothesis and this confirmation; **the decisive evidence for any
production change is shadow-forward**, exactly as the prereg's own
INCONCLUSIVE branch already stipulated.

## Boundaries

- **The CI lower bound is thin (+0.0018).** This is a just-clears
  confirmation, not an overwhelming one; sized honestly it is a ~+24%
  relative improvement measured with ~±20% relative uncertainty.
- Survivorship panel: LEVELS are inflated; the paired arm-vs-arm difference
  is the robust statistic.
- One model family, one universe, one label (fwd_60d). The factorial
  (model#67, running) covers horizon/features/regime interactions this
  design deliberately held fixed.
- The verdict registers in the orchestrator `VERDICTS.md` ledger
  (cross-repo row, PROVISIONAL pending S-REL adversarial verification per
  house R1 default).
