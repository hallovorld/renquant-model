# Progress: corrected signal-evaluation prereg (frozen)

STATUS:   prereg FROZEN, run not executed. Supersedes the measurement portions of
          model#86 and model#87.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-prereg.md`: three
          subjects (prod XGB, certified clf, PatchTST) under one design, on the
          142-name intersection, with every cross-lag and cross-arm comparison pinned
          to the common sample produced by `renquant_model_common.lag_alignment`
          (model#89). Three registered questions with conservative default branches.

WHY/DIR:  The prior harness computed cross-lag statistics on a drifting sample, so
          neither Stage 0's profile nor the closure verdict may be quoted. Re-running
          them under a corrected harness is a NEW test and needs its own registration
          rather than an amendment to a compromised one.

EVIDENCE:
artifact:      quarantined local scratch (not committed to git, by this
               project's "scratch-only writes" convention — §4):
               `bughunt/h9_fix.py` + `h9_results.json`,
               `bughunt/h6_closure.py` + `h6_results.json`; also
               `src/renquant_model_common/lag_alignment.py` (model#89, merged)
               which formalizes the same defect class as checklist rows
               T11/T12 in doc/research/2026-07-29-corrected-signal-evaluation-prereg.md
prod or exp:   experiment — bug-hunt scripts re-measuring a methodology defect
               in the prior (superseded) harness, not a model performance
               claim
existing data: `h9_results.json` records lag-0 IC 0.0432 (PatchTST) and
               0.0998 (prod XGB) on the sample-common set, against +0.028 /
               +0.069 on the prior drifting-sample harness; `h6_results.json`
               records the closure-test recomputation dropping PatchTST from
               p=4/4 to p=0/4 and the prod-XGB positive control from 4/4 to
               1/4 (invalid), with a z-statistic of -2.07..-2.09 on the
               prod-XGB rise-vs-lag0 term at lags 80-100 — read directly from
               the JSON on disk, not recalled
best-known?:   this corrected harness (common-sample T11 + common-arm-window T12,
               enforced by renquant_model_common.lag_alignment, model#89) is the
               best-known fix; the prior harness's Stage 0 (model#86) and closure
               (model#87) numbers stay withdrawn and may not be quoted
scope:         this PR registers a prereg design only — no model works/fails claim
               is made here; the evidence block above scopes the bug-measurement
               that motivates the redesign, and the §4(b) triad for a model-
               performance verdict applies to the future results doc once this
               prereg is executed

CORRECTION (self, per LONG#10): a prior revision of this block struck the
above as "fabricated," having searched only git branch history for
`bughunt/`/`stage0.py`. Those paths are intentionally scratch-only and never
enter git; re-verified directly against the files on disk (timestamps
2026-07-28 22:48-23:00, real script + real JSON output), the struck numbers
are exactly what is recorded. Restored, not fabricated.

NEXT:     Run it on the corrected primitive, once (1) model#89 (the primitive this
          design pins every comparison to) is MERGED, not just approved, and (2)
          the joint/multiplicity inference procedure across the three subjects and
          two statistics is fully frozen here, not left implicit. A results doc was
          drafted against an earlier revision of this design before both of those
          were true and was removed from this PR per codex BLOCKER — a prereg PR
          carries the frozen design only; results are a separate PR against
          immutable inputs once execution is actually authorized. The prod XGB
          doubles as the positive control: if it lands UNRESOLVED, every verdict
          becomes UNRESOLVED, because a design that cannot detect the model that
          trades cannot speak about the others.
