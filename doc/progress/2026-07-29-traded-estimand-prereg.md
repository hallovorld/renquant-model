# Progress: freeze the traded estimand before measuring anything with it

STATUS:   delivered (frozen prereg only). Contains NO result. The confirmatory
          runs begin after this merges.

WHAT:     `doc/research/2026-07-29-traded-estimand-prereg.md`. Registers the
          top-decile spread — the cut the live buy path already trades — as the
          estimand, with a frozen estimator, a frozen control protocol, a
          frozen decision rule, and an explicit list of which corpora are
          already consumed.

WHY/DIR:  Every gate in this programme has been read off full cross-section IC,
          the rank correlation across ALL names. The system trades the top
          decile. IC spends its power on the ~90% of the cross-section we never
          act on, and that mismatch — not sample size — is the likeliest reason
          a day of measurement kept returning "cannot resolve".

          The reframe is what matters: the answer to "we need more data" was
          not more data, more breadth, or more compute. It was measuring the
          decision we actually make.

EVIDENCE: artifact: `doc/research/2026-07-29-traded-estimand-prereg.md`, this
                    branch on `renquant-model` @ origin/main 8579fa7. Inputs
                    read READ-ONLY from the quarantined scratch namespace.
  prod or exp:      EXPERIMENT design. No production data, config, or artifact
                    written. No confirmatory run performed.
  existing data:    Yes — every calibration number in the prereg was measured
                    this session on NULL arms only, so no confirmatory evidence
                    was consumed to write it:
                      - label units `mean=-0.0000, sd=0.9982` (so the statistic
                        is in sd, not return — a P&L reading would have been
                        wrong by construction);
                      - null CI half-width `0.0124 sd` over 12 clean shuffles;
                      - `assess_control` false-flag rate on 30 clean nulls:
                        3% on fold means, 7% on block means — the unit changes
                        the answer, so the prereg registers which one;
                      - therefore ALL-clean over 5 controls voids ~16% of valid
                        experiments, registered in advance as an accepted cost.
                    The SCREEN result that motivated the prereg (clf spread
                    +0.368 sd, t=+3.03, 5/5 placebos null, max |t|=0.84) is
                    named IN the prereg as a screen that cannot confirm itself.
  best-known?:      Yes for the design. NOTHING is claimed about any model.
                    The screen is explicitly not evidence for the registered
                    hypothesis.
  scope:            `renquant-model` docs only. No pin advanced, no umbrella
                    change, no live surface touched.

SCOPE/LIMITS:
          The clf corpus is CONSUMED for this estimand and can never confirm
          it. The only independent clf evidence is forward dates, accruing at
          ~21/month, so that subject is months from decidable. PatchTST and
          prod XGB are unseen on this estimand and are runnable on merge. A
          RESOLVED-POSITIVE would license replacing IC as the gate statistic
          for that subject and nothing else — no capital action, no sizing, no
          expected-return claim, because the statistic carries no cost,
          turnover, or capacity model.

VERIFICATION:
          The document contains no outcome; that is the deliverable. Its own
          §5 records the measurement that disqualifies the `shift120`
          displacement placebo (control `t=+2.90`, more significant than the
          real arm it was meant to null), so a known-broken control cannot be
          reintroduced by default.

NEXT:     On merge, run the frozen rule against PatchTST and prod XGB — the two
          subjects unseen on this estimand — controls first, real arm only if
          the controls pass, verdict withheld pending commissioned adversarial
          review.
