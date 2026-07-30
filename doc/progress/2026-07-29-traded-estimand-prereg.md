# Progress: freeze the traded estimand before measuring anything with it

STATUS:   delivered (frozen prereg only). Contains NO result; the
          confirmatory runs begin after this merges.
          Supersedes the closed #99: that PR was stacked on renquant-model#96
          (its §D depends on `control_calibration.assess_control`) and GitHub
          auto-closed it when #96 merged and its base branch was deleted.
          #96 MERGED as `0c82f6a`. This branch is rebased onto that `main`
          commit (rebase was a no-op — the branch already sat directly on
          `0c82f6a`, so there was no stack and no conflict), and §D was
          re-run on the rebased tree `85be1a3`, reproducing from the
          canonical import path with no PYTHONPATH override. The dependency
          is discharged; the hold conditions are cleared and the PR is ready
          for review (NOT self-merged).

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
                       --subject clf
                       --corpus <scratch>/clf-wf/clf_wf_scores.parquet
                       --screen-corpus <scratch>/clf-wf/clf_wf_scores.parquet
                       --patchtst-corpus <scratch>/wf-eval/scores.parquet
                       --panel RenQuant/data/transformer_v4_wl200_clean.parquet
                       --require-pinned`
                    (verified FULL, sections A-E, this session)
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
                    writing the registration. §D is VERIFIED against
                    post-merge `main` (renquant-model#96 landed
                    `control_calibration.assess_control`), reproducing from
                    the canonical import path with no PYTHONPATH override
                    and no stacked branch:
                      - §A label units `mean=-0.0000, sd=0.9982` (so the
                        statistic is in sd, not return — a P&L reading would
                        have been wrong by construction);
                      - §C null CI half-width `0.0124 sd`, seeds 1000-1011;
                      - §D `assess_control` false-flag on 30 clean nulls
                        (seeds 5000-5029): 3% fed fold means, 7% fed block
                        means — the unit changes the answer, so the prereg
                        registers which one;
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
          inputs: PIN OK on all three, VERIFICATION MODE FULL, sections
          A-E. Re-run post-#96-merge on the rebased tree `85be1a3`
          (#96 merged as `0c82f6a`, landing `control_calibration`, so §D
          runs from the canonical import path with no PYTHONPATH override
          and no stack): fold means 1/30 = 3%, block means 2/30 = 7%,
          ~16% of valid experiments voided.
          Two PRE-EXISTING doc/output inconsistencies were surfaced by this
          re-run and are left for review rather than silently edited, since
          both touch registered text:
            (1) §5 Amd.1's table states the ALL-clean void rate as `14%`
                `[DERIVED — 1-0.97^5]`, but the verifier prints `~16%`
                (P(survive)=84%). Cause is rounding propagation only:
                1-(29/30)^5 = 15.6% from the exact 1/30, vs 1-0.97^5 =
                14.1% from the rounded 3%. No measurement changed.
            (2) §6 cites `[VERIFIED — calibration §C]` for the real arm's
                half-width `0.2176 sd` at effect `0.3680 sd`, but §C no
                longer emits a real-arm half-width (by design — it defers
                that to the runner at verdict time to preserve
                controls-first ordering). The number itself reproduces, but
                from §B: (0.5432-0.1081)/2 = 0.2176. The citation should
                read §B. The document contains no
          outcome; that is the deliverable. Its own §5 records the
          measurement that disqualifies the `shift120` displacement placebo
          (control `t=+2.90`, more significant than the real arm it was meant
          to null), so a known-broken control cannot be reintroduced by
          default.

AMENDMENT 1 (this push, before any confirmatory run):
          §5's false-flag rate is corpus-geometry dependent, and the first
          revision registered only one end. Measured: 3% per arm on the clf
          corpus (292 names x 43 folds) -> 14% void; 8.0% per arm (12/150) on a
          synthetic signal-free panel (60 names x 44 folds) -> 34% void. The
          same frozen rule therefore discards 14%-34% of valid work depending
          on panel shape. Registered consequence: each subject must MEASURE its
          own corpus's rate on 30 clean shuffles and report it with the
          verdict, so a VOID is interpretable rather than mute. The threshold
          is NOT loosened and no re-run-on-VOID allowance is granted — both
          would be moving the goalpost after seeing the cost.
          Surfaced by building the executable runner (renquant-model#100): its
          FIRST synthetic run VOIDed a signal-free corpus.

NEXT:     DONE (this push): #96 merged as `0c82f6a`; this branch is rebased
          onto that `main`; `tools/traded_estimand_calibration.py` re-run on
          the rebased tree `85be1a3` confirming §D reproduces from the
          canonical import path with no PYTHONPATH override, PIN OK on all
          three inputs; §D retagged `[VERIFIED — re-run post-#96-merge on
          85be1a3]`; the `agent:manual-hold` condition is cleared.
          REMAINING: this PR needs Codex review and merge by the reviewer —
          it is deliberately NOT self-merged. Only after it merges, run the
          frozen rule against PatchTST and prod XGB — the two subjects
          unseen on this estimand — controls first, real arm only if the
          controls pass, verdict withheld pending commissioned adversarial
          review. The two inconsistencies logged under VERIFICATION are
          reviewer calls: both are presentation-level (a rounding
          propagation and a section citation), neither changes a registered
          rule, threshold, estimand, estimator, or control protocol.
