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
          `[VERIFIED - hf_trainer.py:337 signature + driver grep]`. What remains is a
          PANEL-level pattern: per-date IC RISES with label lag for BOTH subjects
          `[VERIFIED - goal6-stage0/results.json, wf-eval/diagnostics.log]` - PatchTST
          0d +0.028 -> 100d +0.078 (t=3.21); prod XGB 0d +0.069 -> 40d +0.088 -> 160d
          +0.089, still rising at the last measured lag.

EVIDENCE: the design's decisive addition is trap T10, a turnover-matched control: the
          same test on a 60-day rolling mean of the prod XGB score, which manufactures
          persistence WITHOUT changing the underlying signal. If smoothing alone
          reproduces the long-horizon profile, the effect is persistence (the artefact
          that closed PatchTST at 60d, model#87) rather than horizon. No IC/Sharpe
          claim is made by this PR, so the §4(b) triad applies to the results doc.

NEXT:     Run the frozen grid, then a results doc applying §3 mechanically. RELOCATE
          authorises only a shadow lane at the winning horizon through the standard
          gate chain - never a production switch.
