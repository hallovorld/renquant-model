# L3 meta-label experiment executed as frozen — KILL

STATUS:    completed outcome. One execution, zero deviations, verdict KILL.

WHAT:      doc/research/2026-08-09-l3-meta-label-experiment.md + committed
           artifacts under doc/research/data/ (run script, folds/placebo/
           external/pooled-predictions CSVs, summary JSON, leg verifier).
           The single execution of the v1 prereg (model#207) as amended by
           v2 (model#208), consuming the committed frozen CSV (hash
           re-checked at start) and the frozen 34-row external list.

WHY/DIR:   The prereg existed to make this run judgeable with zero live
           choices. It was: legs 3 (external, −4.5pp on the 4/34 selected)
           and 4 (calibration slope −0.0008) fail outright; legs 1–2 pass
           marginally/vacuously and are annotated as such in the record.

EVIDENCE:  artifact:      2026-08-09-l3-exp-summary.json [VERIFIED —
                          verifier recomputed all four legs from committed
                          CSVs, exit 0]: median uplift@0.5 +0.0017, share
                          6/9, placebo p95 0.0000 (165/200 seeds exactly
                          zero — degenerate bar, stated), cal slope
                          −0.0008, external −0.0454 (4/34 selected);
                          9 folds, 7,027 complete-case rows (140 dropped,
                          matching v2's expected 140); AUC 0.41–0.62,
                          GBDT probe no better. Live-only variant: ZERO
                          folds under frozen guards — reported unevaluable.
           prod or exp:   experiment — read-only over committed frozen
                          inputs + one mode=ro DB read for the once-only
                          external outcomes; no production surface touched
           existing data: the merged v1+v2 preregs and frozen artifacts
           best-known?:   yes — the record annotates WHY each passing leg
                          is weak (τ=0.5 vs base 0.63 selects 80–100%,
                          placebo degenerates to exactly 0) so the next
                          prereg can fix the bars, not the outcome
           scope:         L3 slot stays EMPTY (severable by design,
                          orch#918 §3); any retry = new dated prereg.

TESTS:     data/2026-08-09-l3-exp-verify.py — recomputes legs 1–4 from
           committed artifacts, exits 1 on drift vs the summary [VERIFIED —
           run, exit 0, "verdict KILL"].

NEXT:      MoE/allocation-machine line continues on L1 (shadow row lands
           2026-08-10 15:30; sigma* decision with the operator) and L2
           (shadow job installation awaiting a machine grant). L3 retry
           preconditions, if ever: tau set relative to base rate, features
           from a repaired producer stamp (orch#931), live-only-feasible
           fold scheme — each a NEW dated prereg.
