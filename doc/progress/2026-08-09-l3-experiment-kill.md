# L3 meta-label experiment — prereg execution attempt, re-scoped: NO ADMISSIBLE VERDICT

STATUS:    delivered — as exploratory diagnostics only. The 2026-08-09 run
           is INADMISSIBLE as the frozen prereg's one execution (codex
           review, PR #210): no PASS/KILL verdict is recorded, the L3
           hypothesis remains untested, and model#209 remains an execution
           block.

WHAT:      doc/research/2026-08-09-l3-meta-label-experiment.md + committed
           artifacts under doc/research/data/ (run script, folds/placebo/
           external/pooled-predictions CSVs, summary JSON, leg verifier).
           One execution of the v1 prereg (model#207) as amended by v2
           (model#208) was attempted; the record now documents why it
           cannot carry the prereg verdict and preserves its outputs as
           diagnostics.

WHY/DIR:   Two admissibility defects (research record §0): (1) leg 3
           scored raw mixed-horizon/mixed-action trade_evaluations
           fwd_return — buy {1d:12, 5d:10, 10d:10} + sell {1d:2} — against
           a prereg target frozen as candidate-level fwd_20d>0, buy-side
           only (the model#209 label mismatch); (2) the runner's
           fold-defining guards (min_train=300, min_test=50,
           min_pre_dates=60, min_selected=10, quarterly grid from
           2024-07-01) were never frozen in v1/v2. The prior "one
           execution, zero deviations, verdict KILL" claim is retracted in
           a visible corrections section.

EVIDENCE:  artifact:      2026-08-09-l3-exp-summary.json [VERIFIED —
                          verifier recomputed all four leg numbers from
                          committed CSVs, exit 0]: median uplift@0.5
                          +0.0017, share 6/9, placebo p95 0.0000 (165/200
                          seeds exactly zero — degenerate bar, stated),
                          cal slope −0.0008, external −0.0454 (4/34
                          selected); 9 folds, 7,027 complete-case rows
                          (140 dropped, matching v2's expected 140); AUC
                          0.41–0.62, GBDT probe no better. Live-only
                          variant: ZERO folds under the runner's guards.
           prod or exp:   experiment — read-only over committed frozen
                          inputs + one mode=ro DB read for the once-only
                          external outcomes; no production surface touched
           existing data: the merged v1+v2 preregs and frozen artifacts
           best-known?:   n/a — these are diagnostics, not a model-quality
                          claim; no admissible verdict exists for L3
           scope:         diagnostic numbers over the frozen dataset with
                          unfrozen fold guards and a target-misaligned
                          external leg — NOT admissible prereg evidence;
                          the L3 slot stays EMPTY (severable by design,
                          orch#918 §3) because no admissible PASS exists.

TESTS:     data/2026-08-09-l3-exp-verify.py — recomputes the four leg
           numbers from committed artifacts, exits 1 on drift vs the
           summary OR if the summary ever records an admissible verdict
           (the summary stores as_run_gate_arithmetic="KILL" with
           admissible_verdict=null) [VERIFIED — run after the
           machine-surface relabel, exit 0; it prints the as-run gate
           arithmetic KILL explicitly marked INADMISSIBLE as a prereg
           verdict — record §0].

NEXT:      MoE/allocation-machine line continues on L1 (shadow row lands
           2026-08-10 15:30; sigma* decision with the operator) and L2
           (shadow job installation awaiting a machine grant). Any L3
           attempt = a NEW dated prereg that freezes, BEFORE execution: a
           target-aligned external test (candidate-level fwd_20d holdout
           or prospective), the exact fold calendar, all guards and the
           undefined-selection rule, τ set relative to the base rate, and
           features from a repaired producer stamp (orch#931).
