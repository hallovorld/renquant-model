# Stage-E diagnostics — no support for the daily dispersion gate

STATUS:    diagnostics only (NO verdict authority, model#215 §2b); the
           Stage-C frozen rule and clock are unchanged.

WHAT:      doc/research/2026-08-10-condact-stage-e-diagnostics.md + the
           stage-stamped artifact. A=1 signal +0.0151 vs A=0 +0.0202;
           both CIs include 0; contrast point estimate NEGATIVE; A flips
           in all 8 folds (mechanism coverage held); guards met
           (690/667 days).

WHY/DIR:   The one E-run the merged design allows. The yearly
           concentration (model#214) does not map onto daily ROC20
           dispersion — wrong variable or wrong timescale; alternatives
           are NEW preregs and may not inherit this data.

EVIDENCE:  artifact:      2026-08-10-condact-stageE-result.json
                          [VERIFIED — condact verifier exit 0;
                          stage=E-exploratory, kind=result, corpus pin
                          carried]
           prod or exp:   experiment; corpus read-only
           existing data: merged v2 constants + the frozen corpus
           best-known?:   yes — the Stage-C KILL expectation is recorded
                          BEFORE its clock matures; no gate moves
           scope:         nothing deploys; first-iteration effect surface
                          (L1/L2 shadows, serving chain) unaffected.

TESTS:     verifier green on the committed artifact; P0 sweep clean
           (only the unrelated #209).

NEXT:      Stage C on its deterministic clock (expectation: KILL);
           alternative condition variables only as NEW dated preregs.
