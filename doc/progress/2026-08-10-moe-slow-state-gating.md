# MoE slow-state gating — prereg + Stage-E diagnostics (the monthly axis is null AND unpowerable)

STATUS:    design proposal + committed exploratory freeze surface (orch#966).
           Stage E is diagnostics only — NO verdict authority (mirrors
           condact model#215 §2b). Stage C frozen here, NOT invocable.

WHAT:      doc/design/2026-08-10-moe-slow-state-gating-prereg.md (two-stage,
           §6 power note); doc/design/frozen/2026-08-10-moe-slow-state-harness.py
           + -verify.py + positive/null controls + the stage-stamped
           result; doc/research/2026-08-10-moe-slow-state-stage-e-diagnostics.md.
           S(t) = cross-sectional std of ROC60 on each month's LAST TRADING
           DAY, held for the next month; A_raw = S > trailing-12-month
           median; A applied = A_raw[month−1] (causal). Stage E: A=1 signal
           +0.0157 vs A=0 +0.0202; contrast −0.0045, CI [−0.0599, +0.0456]
           includes 0; A flips in all 8 folds; guards met (38/27 months,
           785/572 days). KILL-shaped, no authority.

WHY/DIR:   The condact Stage-E note left ONE axis open — "the yearly
           concentration may live at REGIME timescale (months), not daily
           state." This is that follow-up, on a single changed axis (the
           activation clock), reusing condact's real-signal machinery
           verbatim. Result: the monthly gate gives the SAME non-result as
           the daily gate and leans negative. AND — the load-bearing
           finding — a monthly gate has ~65 effective months (not ~1,350
           days); the contrast SE ≈0.027 would need ~14× more effective
           months (~decades) to resolve a plausible +0.02 gate. The axis is
           both null on the seen folds and structurally unpowerable.

EVIDENCE:  artifact:      2026-08-10-moe-slow-state-stageE-result.json
                          [VERIFIED — slow-state verifier exit 0;
                          stage=E-exploratory, kind=result, corpus pin
                          870f68eb… carried; features_sha256 matches the v2
                          FEATS list condact also imports]
           prod or exp:   experiment; corpus read-only, isolated worktree;
                          no production path written
           existing data: merged v2 constants (CUTS/PARAMS/SEEDS/FEATS) +
                          the sha-pinned frozen corpus ONLY — operator
                          directive honored (no future accrual)
           best-known?:   yes — real-signal = ic_real − ic_shuffle
                          (embargo-floor-robust difference); fold constants
                          imported from the frozen v2 table, not re-derived;
                          positive+null controls pass before the real read;
                          Stage-C KILL/unreachability expectation recorded
                          BEFORE its clock matures
           scope:         nothing deploys; no gate moves; the first-iteration
                          effect surface (L1/L2 shadows, serving chain) is
                          untouched

TESTS:     slow-state verifier green on all three committed artifacts
           (positive control, null control, Stage-E result); positive
           control PASS (contrast +0.130, CI excludes 0), null control KILL
           (shuffled months, CI covers 0). P0 sweep clean — no open P0
           touches this harness; nearest neighbor #190 (dependence-adequate
           null) is addressed by the §6 effective-month power note.

NEXT:      Stage C only under its own reviewed amendment on the orch#939
           extension corpus, on the deterministic clock (≥24 realized-label
           months per arm — not reachable before ~2030+; expectation: KILL
           or perpetually-under-guard). Any OTHER condition axis (sector,
           breadth, rate regime) is a NEW dated prereg and may not inherit
           this run's data. No substitute estimand is pursued here.
