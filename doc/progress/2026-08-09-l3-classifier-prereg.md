# L3 classifier prereg — relocated to the model factory, frozen before any run

STATUS:    design only. No training has been run; that is the point. The
           experiment executes only as specified or not at all.

WHAT:      doc/design/2026-08-09-l3-classifier-prereg.md — the L3 meta-label
           classifier preregistration, relocated from renquant-orchestrator
           PR #929 per its ownership review (model-experiment contracts
           belong to the model factory; the orchestrator keeps only the
           dataset-contract pointer). Frozen: logistic L2 C=1.0 (depth-2
           GBDT descriptive-only); 6 unconditional entry-time features with
           stated exclusions; regime EXCLUDED ENTIRELY (r2 producer
           verdict: live_state_snapshots is a close-of-run audit row and
           candidate_scores persists first — attribution, not availability;
           no merge-state gate exists — a future producer-stamped score-time
           field would require a NEW dated prereg); expanding
           walk-forward with 20-trading-day embargo; ALL-rows training
           declared with mandatory run_type-split metrics (live-only as a
           prereg variant); τ ∈ {0.5, 0.6}; expectancy uplift primary;
           within-date label-shuffle placebo ×200; the 64 trade_evaluations
           rows once-only; four-leg deterministic PASS/KILL; shadow-only
           stakes on PASS.

WHY/DIR:   The dataset (orch#928) is merged; the classifier experiment must
           be frozen before results exist to steer it. Two review findings
           on orch#929 drove this shape: P1 — ownership: the prereg moves
           here; P0 — no causal score-time regime source exists on any
           current surface (both the date join and the run-identity join
           fail, in opposite directions); regime is excluded, and a
           producer-stamped score-time field is a separate pipeline line
           whose adoption would be a NEW dated prereg.

EVIDENCE:  artifact:      orch#928 dataset manifest via read-only module
                          rebuild (DB mode=ro, CSV + manifest under /tmp)
                          [VERIFIED — module stdout, relocation session]:
                          7,167 rows / 523 dates / 1,275 excluded /
                          selected 135 / base win rate 0.6307 / live 2,189
                          vs sim 4,978. HISTORICAL r1 EVIDENCE ONLY (withdrawn from
                          this prereg's basis — measured on the r1
                          run-identity join before the producer verdict
                          excluded regime; kept solely as the record of why
                          the exclusion matters): 2,184 live rows carried a
                          same-run snapshot / all sim rows absent.
                          trade_evaluations = 64 [VERIFIED — sqlite ro
                          count, same session]. bull_calm-dominant days =
                          1,240 of 2,388 [VERIFIED — argmax over committed
                          orchestrator regime-posterior CSV, same session].
           prod or exp:   experiment — design doc only
           existing data: no meta-label entry classifier has ever been
                          trained in this system; the exit-side foundation
                          (meta-label-exit.json) is a different surface
           best-known?:   yes — first entry-filter prereg; anticipated
                          failure modes (sim-feature drift, regime
                          collinearity + absent/run_type collinearity,
                          base-rate drift) are in the doc so they cannot be
                          discovered as surprises
           scope:         design only; the experiment run is the next
                          deliverable and follows this document verbatim.

TESTS:     none — a prose contract; its test is that the run can be judged
           entirely from §2/§3 with zero live choices (no merge-state gate
           remains — regime is excluded unconditionally).

NEXT:      orch#929 shrinks to the dataset-contract pointer citing this doc;
           after both merge, execute the experiment exactly as frozen and
           report PASS/KILL.
