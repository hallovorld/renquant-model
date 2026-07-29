# Progress: freeze the traded estimand before measuring anything with it

STATUS:   delivered (frozen prereg only), MERGE BLOCKED pending
          renquant-model#96. §D's registered false-flag rates depend on
          `control_calibration.assess_control`, which only exists on #96 and
          is unauditable from this branch — this PR carries the
          `agent:manual-hold` label until #96 merges. Contains NO result. The
          confirmatory runs begin after this merges.

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

EVIDENCE: artifact: `doc/research/2026-07-29-traded-estimand-prereg.md` +
                    `tools/traded_estimand_calibration.py` (this PR), on
                    `renquant-model` @ origin/main 8579fa7. Every number is
                    reproduced by:
                      `python3 tools/traded_estimand_calibration.py
                       --clf-corpus <scratch>/clf-wf/clf_wf_scores.parquet
                       --patchtst-corpus <scratch>/wf-eval/scores.parquet
                       --panel RenQuant/data/transformer_v4_wl200_clean.parquet`
                    which pins each input by sha256 and ABORTS on mismatch:
                      clf_wf_scores.parquet      1da3fcfab06af1e5…5bc4efe4
                      wf-eval/scores.parquet     6eb209e2491b26b1…e2606d18
                      transformer_v4_wl200_clean 3982ca545d4c109b…668f0676
                    Corpora READ-ONLY in the quarantined scratch namespace;
                    the panel is a production file, opened for read only.
  prod or exp:      EXPERIMENT design. No production data, config, or artifact
                    written. No confirmatory run performed.
  existing data:    Yes — every calibration number is now traceable to a
                    section of the committed verifier (§A-§E) rather than to
                    "this session", and all of them except the named SCREEN
                    come from NULL arms, so no confirmatory evidence was spent
                    writing the registration. §A-§C and §E are independently
                    reproducible from this branch today; §D is NOT — see below:
                      - §A label units `mean=-0.0000, sd=0.9982` (so the
                        statistic is in sd, not return — a P&L reading would
                        have been wrong by construction);
                      - §C null CI half-width `0.0124 sd`, seeds 1000-1011;
                      - §D `assess_control` false-flag on 30 clean nulls
                        (seeds 5000-5029): 3% fed fold means, 7% fed block
                        means — the unit changes the answer, so the prereg
                        registers which one. PENDING renquant-model#96:
                        `assess_control` is not on `main` yet, so running the
                        committed verifier today prints §D as SKIPPED — this
                        number is not independently reproducible from this
                        branch until #96 merges;
                      - therefore ALL-clean over 5 controls voids ~16% of valid
                        experiments, registered in advance as an accepted cost;
                      - §E the shift120 ban, which running the verifier
                        CORRECTED: that measurement is on the PatchTST corpus,
                        not the clf one, and the first revision of the prereg
                        said "this corpus". Two different subjects were
                        conflated; the text now names each.
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
          `tools/traded_estimand_calibration.py` run against the three pinned
          inputs: PIN OK on all three, and §A, §B, §C, §E reproduce the
          prereg's stated numbers exactly. §D is NOT reproduced — it
          self-reports SKIPPED because `control_calibration` is unimportable
          on this branch; it lands in renquant-model#96, APPROVED but NOT YET
          MERGED, so that section is unauditable until #96 merges. The
          dependency is printed rather than hidden.
          The document contains no outcome; that is the deliverable. Its own
          §5 records the measurement that disqualifies the `shift120`
          displacement placebo (control `t=+2.90`, more significant than the
          real arm it was meant to null), so a known-broken control cannot be
          reintroduced by default.

NEXT:     Merge #96 first, rebase this branch on that main commit, re-run
          `tools/traded_estimand_calibration.py` to confirm §D reproduces
          from the canonical import path, retag it `[VERIFIED]`, then remove
          `agent:manual-hold` and merge this PR. Only then run the frozen
          rule against PatchTST and prod XGB — the two subjects unseen on
          this estimand — controls first, real arm only if the controls
          pass, verdict withheld pending commissioned adversarial review.
