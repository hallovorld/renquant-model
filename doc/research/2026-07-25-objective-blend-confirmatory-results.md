# Results — tail-aware blend objective vs production rank:pairwise: CONFIRMED

Date: 2026-07-25
Prereg (FROZEN, merged): `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md` (model#68)
Evidence (REPLAYABLE): `doc/research/evidence/2026-07-25-objective-blend/confirmatory-bundle.json`
Supersedes: model#70 (closed unmerged — its aggregate-only evidence could not
replay the CI or guards; this PR is the accepted-results path the VERDICTS
withdrawal note requires)

## Verdict — CONFIRMED [VERIFIED, replayable]

| condition | frozen requirement | measured |
|---|---|---|
| primary | block-bootstrap 90% CI lower bound > 0 | **+0.0018** (diff +0.0552/60d, CI [+0.0018, +0.1085]) |
| guard (a) | ≥8/10 seed signs positive | **10/10** |
| guard (b) | winsorized-±50% diff ≥ 0 | **+0.0095** |

blend clean top-10 spread **+0.2873/60d** vs production **+0.2321/60d** —
**+24% relative on the harvest statistic**, positive in all 10 seeds.

**Replay path (verified before submission):**
`deserialize_result(bundle["series"])` → `verdict_from_bundle(...)`
recomputes diff_mean, the CI, both guards, and the CONFIRMED verdict from
the committed per-date/per-seed series, matching the run's aggregates
exactly. The freeze manifest carries both digests
(`data_digest sha256:677939fe…`, `prereg_digest sha256:dc34fe5d…`).

## Determinism — four identical executions

The statistic set (+0.0552 / [+0.0018,+0.1085] / 10/10 / +0.0095) is
byte-identical across: (1) the pre-catch run (killed unread — guard wiring,
not numbers), (2) the fixed-executor run, (3) the first replayable-bundle
run (incomplete prereg digest — my concurrent branch switch during the run;
disclosed), (4) this clean run on main. Seeded end-to-end as designed.

## Consequence (frozen, conditioned per the model#70 round-3 finding)

CONFIRMED with a replayable bundle ⇒ the shadow deployment design PR may
now be drafted. **Nothing here authorizes a production change**; the shadow
readout rule gets frozen in that design PR, and shadow-forward evidence
remains decisive. The VERDICTS row re-adds in the orchestrator ledger only
after THIS PR is accepted (the withdrawal note's recorded condition).

## Boundaries

CI lower bound is thin (+0.0018) — a just-clears confirmation, ~±20%
relative uncertainty on a +24% relative effect. Survivorship panel (levels
inflated; the paired diff is the robust read). One model family, fwd_60d
label; the factorial (model#72) found no H×F×R interactions that would
bound this claim, at ~±0.01-0.02 resolution.
