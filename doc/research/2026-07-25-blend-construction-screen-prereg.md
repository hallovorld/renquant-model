# Prereg — SCREEN of the exact blend construction (provenance repair, disclosed)

Date: 2026-07-25
Status: SCREEN PREREG — frozen at this commit, run follows in this same PR
(evidence commit may not amend this section).
Reopening chain: this is step 1 of model#73's recorded reopening condition
("a pre-registered screen of the exact blend construction (committed
evidence), then a re-frozen confirmatory prereg citing that screen").

## Full disclosure — what this screen is and is not

The blend construction (per-date z(rank:pairwise@fwd60) + z(top-decile
classifier@fwd60)) was previously run informally and its numbers are
PUBLICLY KNOWN (session record; merged PR bodies). This screen therefore
claims NO discovery. Its sole purpose is to place COMMITTED, replayable
evidence of the exact construction into the provenance chain — the hole
the #73 downgrade correctly identified (the six-arm screen evidence
committed with #68 contained the component arms, never the blend itself).

Because the outcome is effectively known, the honest weight of the
reopening chain falls on step 2: the re-frozen confirmatory will use
**fresh seeds never used in any prior run of this line (60-69)**, making it
an independent draw rather than a replay. This screen uses the original
screen seeds (42-44) precisely because its role is to reproduce the
informal screen into the durable record.

## Frozen screen spec

- Arms: `rank60` baseline and `blend`, exactly as implemented in
  `scripts/research_objective_blend_confirm.py` (merged; guard-faithful).
- Seeds 42/43/44; the same 5 purged folds, 60d embargo, per-arm matched
  within-date shuffled-label placebos.
- Statistic: paired per-date clean top-10 spread difference; block
  bootstrap b=60, seed 20260725, 90% CI — REPORTED, not gated (screens
  carry no verdicts).
- Evidence: full replayable bundle (per-date/per-seed series + freeze
  manifest) committed under
  `doc/research/evidence/2026-07-25-blend-construction-screen/`.
- Pass bar (for proceeding to step 2 only): point estimate > 0 and ≥2/3
  seeds positive. Anything else closes the reopening chain as REFUTED.

---

## RESULTS (evidence commit — the frozen section above is unamended)

Run completed same day via the merged guard-faithful executor restricted to
the frozen screen seeds (42/43/44); full replayable bundle committed at
`doc/research/evidence/2026-07-25-blend-construction-screen/screen-bundle.json`
(freeze manifest carries data + prereg digests).

| statistic | value |
|---|---|
| blend clean top-10 spread | +0.3135/60d |
| rank60 clean top-10 spread | +0.2508/60d |
| paired diff | **+0.0627**, block-bootstrap 90% CI [+0.0027, +0.1305] |
| seeds positive | **3/3** |
| winsorized ±50% diff | +0.0096 ≥ 0 |

**Screen bar (frozen above): point estimate > 0 AND ≥2/3 seeds positive →
PASS.** (The executor also prints its 10-seed confirmatory verdict line —
INCONCLUSIVE at n=3 — which does not apply to this screen and is quoted
here only for transparency.)

Consequence per the reopening chain: step 2 proceeds — a re-frozen
confirmatory prereg citing THIS committed evidence, with fresh seeds 60-69
(an independent draw, not a replay).
