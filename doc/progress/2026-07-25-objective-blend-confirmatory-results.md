# 2026-07-25 — Confirmatory results: tail-aware blend objective vs production rank:pairwise

STATUS:    results committed; CONFIRMED per the frozen numeric rule, but PROVISIONAL
           as a decision — NOT yet independently replayable (disclosed gap below),
           restacked on the fixed #68 executor but not re-run against it. The
           shadow-deployment next step (below) is GATED on a replayable re-run, not
           authorized by this evidence alone.
WHAT:      `doc/research/2026-07-25-objective-blend-confirmatory-results.md` (results
           memo) + `doc/research/evidence/2026-07-25-objective-blend/confirmatory-result.json`
           (aggregate result of the 10-seed run against `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md`).
WHY/DIR:   Reads the frozen decision rule from model#68 against the completed 10-seed
           confirmatory run. CONFIRMED under the frozen rule authorizes exactly one
           next step: a shadow-deployment design PR (renquant-pipeline shadow-scorer
           line) — no production config change from this result.
EVIDENCE:
  artifact:      doc/research/evidence/2026-07-25-objective-blend/confirmatory-result.json
  prod or exp:   EXPERIMENT — research harness on `alpha158_291_fundamental_dataset.parquet`
                 via renquant_model_gbdt public API; read-only; no prod artifact touched
  existing data: prereg frozen pre-run at model#68's original head (`3da6d01e`); this
                 run predates model#68's round-3/4 bundle-replayability fix (`ceac403`)
  best-known?:   first confirmatory read of the objective-blend screen (model#68)
  scope:         "paired diff +0.0552/60d, block-bootstrap 90% CI [+0.0018,+0.1085]
                 (lower bound thin but > 0), seed signs 10/10 positive, winsorized
                 ±50% guard +0.0095 ≥ 0 -> CONFIRMED per the frozen rule. Consequence:
                 shadow deployment design PR next; NOTHING here authorizes a
                 production change. CI lower bound is thin (~±20% relative
                 uncertainty) — a just-clears confirmation, not a decisive one."
NEXT:      GATED — shadow deployment design PR (renquant-pipeline shadow-scorer line)
           does not open until a replayable re-run against the bundle-capable
           executor (model#68 `ceac403`+) confirms this result; see "Disclosed
           reproducibility gap" below for the two paths. Verdict registers in
           orchestrator VERDICTS.md as PROVISIONAL — now for two independent
           reasons: the pre-existing R1-default pending-S-REL-verification reason,
           and this PR's non-replayable evidence — see renquant-orchestrator#576.

## Disclosed reproducibility gap (model#70 review rounds 1-2)

Both review rounds are correct that `confirmatory-result.json` serializes only
aggregate means/CI/guards/verdict, not the per-date/per-seed series a reviewer needs
to recompute the CI and both guards independently. model#68's round 3-4 fix
(`ceac403`, landed after this run) adds exactly that bundle format
(`serialize_result`/`deserialize_result`/`verdict_from_bundle`, pinned by a synthetic
round-trip test) — but it lands AFTER this specific run completed, so this PR's
committed `confirmatory-result.json` predates the fix and is not itself replayable.

This fix cycle does not re-run the 10-seed panel experiment (a multi-hour compute
job; out of scope for a bounded review-finding fix). Two honest paths forward,
left for reviewer/operator triage rather than picked unilaterally here:

1. **Re-run** the confirmatory experiment against the now-bundle-capable executor
   (`scripts/research_objective_blend_confirm.py` @ `ceac403` or later) and replace
   this PR's evidence with the new replayable bundle. Given all randomness in the
   executor is seeded (xgboost `seed=seed` per training call, bootstrap
   `BOOT_SEED=20260725`), a re-run against unchanged data should reproduce this
   run's aggregates near-exactly, which would itself be useful A/A-style
   confirmation of run-to-run stability.
2. **Downgrade** this PR's verdict from CONFIRMED to a disclosed-provisional read
   until a replayable re-run exists, and gate the shadow-deployment follow-up PR on
   that re-run rather than on this evidence alone.

Not resolving this gap by fabricating the missing per-date/per-seed series from the
aggregate numbers already committed — that would misrepresent unverified
reconstruction as the original run's actual data.

### Round 3 review finding addressed

MED — the result/next-step language was stronger than the committed (non-replayable)
evidence could support: the results-memo title and "Pre-committed consequence"
section stated a plain CONFIRMED and said the shadow-deployment design PR
"follows," without conditioning that on the reproducibility gap disclosed two
sections below it. Took the review's second offered path (downgrade, not
re-run — the 10-seed panel is a multi-hour job out of scope for this fix cycle):
retitled the results memo `CONFIRMED (PROVISIONAL — non-replayable evidence)`,
reworded its "Pre-committed consequence" section to gate the shadow-deployment
design PR on a replayable re-run rather than authorizing it now, and updated
this doc's STATUS/NEXT fields to match. The frozen numeric verdict (CI lower
bound > 0, both guards pass) is unchanged — only the decision/authorization
language is downgraded.

## Run-integrity timeline (unchanged from the original PR body)

The first run was killed **unread** after round-1 review on model#68 correctly
caught the executor's guard-(b) surrogate (trimmed-mean approximation instead of
the frozen winsorized-±50% clean-spread difference). The rerun used the frozen
guard verbatim; no decision-rule text changed between the prereg freeze and this
run. This is an assertion, not an auditable artifact — model#68's round-3 HIGH
finding on the pre-run freeze boundary (manifest `prereg_digest` +
`run_started_at`) also postdates this run for the same reason as the bundle gap
above.
