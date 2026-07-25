# Results — tail-aware blend objective vs production rank:pairwise: EXPLORATORY / PROVISIONAL

Date: 2026-07-25
Prereg (FROZEN, merged): `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md` (model#68)
Evidence (REPLAYABLE): `doc/research/evidence/2026-07-25-objective-blend/confirmatory-bundle.json`
Supersedes: model#70 (closed unmerged — its aggregate-only evidence could not
replay the CI or guards; this PR is the accepted-results path the VERDICTS
withdrawal note requires)

**Classification downgraded per model#73 review (BLOCKER 2):** the frozen
decision rule's own output on this run is the technical label `CONFIRMED`
(below) — that computation is not in question. But the prereg's "screen
provenance" section cites `doc/research/evidence/2026-07-25-objective-blend/screen-six-arm-result.json`,
which covers `rank_pairwise`, `top_decile_clf`, `big_run_clf`, `rank_on_20d`
as four *separate* arms. None of those rows is the `blend` construction
under test here (per-date z(rank60) + z(top_decile_clf)) — the blend itself
was never screened before being frozen into the confirmatory prereg; its
case rests on the mechanism argument alone. Per review, that gap means this
result **cannot stand as a promotable "CONFIRMED"** result until an
immutable prior screen record exists for the exact blend construction — so
this memo reports the run's technical verdict but classifies the PR's
standing as **EXPLORATORY / PROVISIONAL**, and withdraws the shadow-design
and ledger-verdict authorization below (see Consequence).

## Run's technical verdict — CONFIRMED under the frozen rule [VERIFIED, replayable]

| condition | frozen requirement | measured |
|---|---|---|
| primary | block-bootstrap 90% CI lower bound > 0 | **+0.0116** (diff +0.0602/60d, CI [+0.0116, +0.1155]) |
| guard (a) | ≥8/10 seed signs positive | **9/10** |
| guard (b) | winsorized-±50% diff ≥ 0 | **+0.0125** |

blend clean top-10 spread **+0.2837/60d** vs production **+0.2235/60d** —
**+27% relative on the harvest statistic**, positive in 9 of 10 seeds.

**Replay path (verified before submission):**
`deserialize_result(bundle["series"])` → `verdict_from_bundle(...)`
recomputes diff_mean, the CI, both guards, and the CONFIRMED verdict from
the committed per-date/per-seed series, matching the run's aggregates
exactly. The freeze manifest carries both digests
(`data_digest sha256:67dab241…`, `prereg_digest sha256:dc34fe5d…`).

## Determinism — retracted per model#73 review round 3 (BLOCKER)

The prior claim of four byte-identical executions
(+0.0552 / [+0.0018,+0.1085] / 10/10 / +0.0095) is **retracted**: it was
stale prose left over from the earlier, non-citable runs and did not match
this PR's committed bundle. Round-3 review found the committed
`confirmatory-bundle.json` — and an independent replay via
`deserialize_result(bundle["series"])` → `verdict_from_bundle(...)` —
reproduce **+0.0602 / [+0.0116, +0.1155] / 9/10 / +0.0125**, the numbers now
in the table above. The three earlier runs ((1) pre-catch, killed unread;
(2) the fixed-executor run; (3) the first replayable-bundle run) are not
part of the committed evidence and their statistic set cannot be verified
against this artifact, so no determinism claim across those runs is made
here — only this run's committed bundle is evidentiary.

## Consequence — WITHDRAWN pending an immutable blend-specific screen (model#73 review BLOCKER 2)

The original consequence ("shadow deployment design PR may now be drafted")
is **withdrawn**: the frozen prereg's screen provenance never screened the
exact `blend` construction (see Classification above), so this replayable
run — however clean its own execution — cannot authorize the shadow-design
PR or the orchestrator ledger's VERDICTS row re-add. **Nothing here
authorizes a production change.** To re-earn CONFIRMED standing: run a
short, pre-registered screen of the exact `blend` construction itself
(committed evidence, not the mechanism argument alone), then re-freeze a
confirmatory prereg citing that screen.

## Boundaries

CI lower bound is thin (+0.0116) — a just-clears confirmation, ~±20%
relative uncertainty on a +27% relative effect. Survivorship panel (levels
inflated; the paired diff is the robust read). One model family, fwd_60d
label; the factorial (model#72) found no H×F×R interactions that would
bound this claim, at ~±0.01-0.02 resolution. Classification: EXPLORATORY /
PROVISIONAL (see above) — not a standing confirmed result.
