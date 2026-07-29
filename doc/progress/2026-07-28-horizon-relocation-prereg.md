# Progress: horizon-relocation prereg (frozen)

STATUS:   prereg FROZEN, run NOT executed. Docs only.
          CORRECTION (visible, per long-term-agreements.md entry 10): an earlier
          version of this doc and the research doc stated an "IC rises with label
          lag" table tagged `[VERIFIED - goal6-stage0/results.json,
          wf-eval/diagnostics.log]` and said PatchTST "is CLOSED at 60d (model#87)".
          Neither has a real source: GOAL-6 Stage 0 (model#86) has no
          approved/executed result (5 unresolved CHANGES_REQUESTED findings as of
          2026-07-29), and model#87's results commit was dropped after the corpus it
          depended on was found not to exist. Retracted, not restated - see the
          research doc's own CORRECTION section for the full record.

WHAT:     Adds `doc/research/2026-07-28-horizon-relocation-prereg.md`: does this
          panel's signal live at a longer horizon than the 60d we train and trade?
          Frozen horizon grid (20/60/100/120/160 trading days), two subjects on the
          142-name intersection, an explicit source contract (score panels must be
          named by a checked-in path + commit/run-id, not asserted), per-arm nulls,
          block length set to each arm's OWN horizon, a Bonferroni-corrected
          multiplicity rule across the 5-horizon selection, mandatory turnover/cost
          arithmetic against the production `renquant_common.cost_model`, and a
          frozen RELOCATE / STAY / INCONCLUSIVE rule with ties resolving to STAY.

WHY/DIR:  Operator question about a persistence finding that has not itself been
          confirmed ("是不是哪里不对? 有 alpha 的话能不能 streamline?"). The most
          likely mechanical bug was checked and REFUTED: the `.shift(-60)` in the
          PatchTST trainer is a placebo-only parameter, default 0, and the WF driver
          never passes it `[VERIFIED - hf_trainer.py:337 signature + driver grep]`.
          Nothing else is asserted as a finding here - whether IC actually rises
          with label lag is the question this run answers, not a premise it starts
          from (see correction above).

EVIDENCE: artifact:      `doc/research/2026-07-28-horizon-relocation-prereg.md`
          (design only) `[VERIFIED - this PR's diff]`.
           prod or exp:   design/experiment - no run executed, no production
          artifact touched.
           existing data: `hf_trainer.py:337`'s `label_shift_days` signature and its
          zero default `[VERIFIED - direct file read, this session]`. No other
          numeric claim is made; the previously-cited `goal6-stage0/results.json`
          and `wf-eval/diagnostics.log` do not exist as executed artifacts and are
          removed from the doc.
           best-known?:   n/a - pre-run design, no result to rank.
           scope:         "this is a frozen pre-run prereg, not a result - the
          §4(b) sanity triad applies once a results doc is written against this
          design, not to this PR."

NEXT:     Run the frozen grid against the §2 source contract, then a results doc
          applying §3 mechanically. RELOCATE authorises only a shadow lane at the
          winning horizon through the standard gate chain - never a production
          switch.
