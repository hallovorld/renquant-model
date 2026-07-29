# Progress: horizon-relocation prereg (frozen)

STATUS:   prereg FROZEN, run NOT executed. Docs only.

WHAT:     Adds `doc/research/2026-07-28-horizon-relocation-prereg.md`: does this
          panel's signal live at a longer horizon than the 60d we train and trade?
          Frozen horizon grid (20/60/100/120/160 trading days), two subjects on the
          142-name intersection, per-arm nulls, block length set to each arm's OWN
          horizon, mandatory turnover/cost arithmetic, and a frozen
          RELOCATE / STAY / INCONCLUSIVE rule with ties resolving to STAY.

WHY/DIR:  Operator question about the persistence finding ("是不是哪里不对? 有 alpha
          的话能不能 streamline?"). The most likely mechanical bug was checked and
          REFUTED: the `.shift(-60)` in the PatchTST trainer is a placebo-only
          parameter, default 0, and the WF driver never passes it
          `[VERIFIED - hf_trainer.py:337 signature + driver grep]`. The IC-vs-lag
          table that originally motivated this prereg (`goal6-stage0/results.json`)
          is NOT cited here as verified evidence: model#86 (Stage 0) carries open
          CHANGES_REQUESTED findings and has no approved/merged result, and
          model#87's closure verdict was retracted with no confirmatory run merged
          either. This PR is a pre-run design only; §1/§2 of the research doc state
          the operator's question as motivation, not as a premise the run is handed.

EVIDENCE:
artifact:      src/renquant_model_patchtst/hf_trainer.py:337 (this repo, current
               main); doc/research/2026-07-28-horizon-relocation-prereg.md (this
               PR's own frozen design)
prod or exp:   experiment — refuting one candidate mechanical-bug hypothesis
               (`label_shift_days`), not a model performance claim
existing data: `hf_trainer.py:337`'s `label_shift_days` signature default is 0
               and is placebo-only; grepping the WF driver invocation confirms it
               is never passed a non-zero value — this candidate bug is ruled out
best-known?:   n/a — this is a negative/refutation check on one hypothesis, not a
               model comparison
scope:         claim is scoped to `label_shift_days` being inert in the current WF
               driver invocation; it does not establish or refute whether IC
               actually rises with label lag — that question is registered in §1-3
               of the research doc and answered only by executing this prereg, not
               by this progress doc. No IC/Sharpe claim is made by this PR, so the
               §4(b) triad for a model verdict applies to the future results doc.

NEXT:     Run the frozen grid, then a results doc applying §3 mechanically. RELOCATE
          authorises only a shadow lane at the winning horizon through the standard
          gate chain - never a production switch.
