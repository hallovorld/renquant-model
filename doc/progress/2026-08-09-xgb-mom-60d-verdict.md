# xgb_mom_60d executed as frozen — KILL (leg 2: 4/8 folds)

STATUS:    completed outcome; one execution, zero deviations.

WHAT:      doc/research/2026-08-09-xgb-mom-60d-verdict.md + committed
           artifacts (harness, result JSON, both pre-run control JSONs,
           verifier). Verdict KILL on the frozen §3 gate: mean real
           signal +0.0221 (leg 1 pass) but only 4/8 folds positive
           (leg 2 bar: ≥6); A/A stable; recency pass.

WHY/DIR:   Phase-2 step 5 of the operator's re-planning. The learned
           momentum form is episodic (2020/2025/2026 strong, quiet years
           negative) — real on average, not persistent; the standing-arm
           bar demanded persistence.

EVIDENCE:  artifact:      2026-08-09-xgbmom-result.json [VERIFIED —
                          verifier recomputed legs+verdict, exit 0];
                          controls: positive PASS (+0.3715 planted),
                          null KILL (−0.0027) — committed.
           prod or exp:   experiment; corpus read-only (sha pinned in the
                          merged prereg); nothing served
           existing data: the frozen WF corpus only
           best-known?:   yes — the episodic pattern is stated WITH its
                          matching prior evidence; the only legitimate
                          follow-up (conditional activation) is named as
                          a NEW prereg, not smuggled in
           scope:         no arm enters the system; P0 sweep done
                          pre-publication (only #209, unrelated).

TESTS:     data/2026-08-09-xgbmom-verify.py exit 0 [VERIFIED — run].

NEXT:      Phase-2 ⑥ (freshness checker full-window) and Phase-3 items;
           conditional-activation prereg only on operator interest.
