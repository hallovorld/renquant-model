# xgb_mom_60d prereg v2 — embargoed folds

STATUS:    design only; no run. The admissibility repair after model#212.

WHAT:      doc/design/2026-08-09-xgb-mom-60d-prereg-v2.md — one amended
           element (fold calendar: 91-calendar-day gap > the ~84-day
           label realization window; fold-8 dropout rule stated) plus
           run-time integrity duties (sha asserted BEFORE read; result
           JSON carries admissible_verdict null-until-countersigned;
           controls re-run under the new folds and committed). Features/
           params/seeds/guards/legs inherited verbatim from model#211.

WHY/DIR:   The operator asked when their momentum model arrives; the
           honest path is a valid verdict, and the only invalid part of
           v1 was temporal separation. Expectation set IN THE DOC: a
           weaker number than the leaky diagnostic is the expected
           direction.

EVIDENCE:  artifact:      the gap arithmetic [DERIVED — 60 trading days
                          ≈ 84 calendar days < 91-day gap]; v1 defect
                          record [VERIFIED — model#212 merged]; corpus
                          sha pinned [VERIFIED — hashed 2026-08-09].
           prod or exp:   experiment; corpus read-only
           existing data: the merged v1 prereg + the inadmissible run's
                          diagnostics (hypothesis-only)
           best-known?:   yes — fold-8 dropout and the ≥6-of-realized
                          bar are frozen now, not decided at run time
           scope:         one execution post-merge, same day; PASS →
                          shadow-candidacy memo gated on #937/#931.

TESTS:     the committed harness + controls re-run under the new folds
           (their JSONs committed with the result).

NEXT:      merge → controls → one execution → verdict published with
           committed JSON + verifier, same day.
