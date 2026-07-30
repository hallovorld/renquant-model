# Progress: make the frozen decision rule executable, and find what it costs

STATUS:   RECOVERED. Supersedes #100, which GitHub auto-closed when #101
          merged and its base branch was deleted — this PR was stacked on it.
          #100's content was verified ABSENT from `main` before rebuilding
          (`tools/traded_estimand_run.py` and its tests were both missing), so
          the close would have silently dropped 688 lines including the
          tie-complement estimand fix. Rebuilt directly on `main`, which now
          carries #101's prereg, so nothing is duplicated and no stack
          remains.

STATUS:   delivered (runner + 14 tests). Stacked on renquant-model#99, which is
          itself stacked on #96. NO subject has been run: the runner REFUSES
          until the prereg is on origin/main.

          Fixed by claude (2026-07-29, review finding #1 on #100): the freeze
          check only verified the prereg PATH existed on `origin/main`, not
          that it matched the local copy byte-for-byte. Once the prereg
          merged once, a later unmerged local edit to the same path still
          passed the gate forever after — the exact loophole
          preregistration exists to close. Now also hashes the local file
          and rejects a mismatch. 2 new regression tests added.

          Fixed by claude (2026-07-29, review finding #2 on #100): `main()`
          passed `rehearsal=not frozen` into `run_subject()`, so once the
          prereg was frozen an explicit `--i-am-not-preregistering` was
          silently ignored and the output was unstamped — indistinguishable
          from a real verdict, the one direction the REHEARSAL stamp exists
          to prevent. The flag now FORCES rehearsal
          (`rehearsal = (not frozen) or args.i_am_not_preregistering`)
          regardless of freeze state. 2 more regression tests added.

WHAT:     `tools/traded_estimand_run.py`. Executes prereg §7 with two
          properties made mechanical rather than promised:
            1. it will not run before the prereg is MERGED and matches the
               local copy byte-for-byte (checks `origin/main:<path>` exists
               AND its blob hash equals `git hash-object` of the local file —
               a local edit by the person about to read the answer, even
               after the prereg has merged once, is the thing
               preregistration prevents). `--i-am-not-preregistering`
               rehearses and stamps every output line REHEARSAL so a
               transcript cannot be mistaken for a verdict;
            2. a VOID never COMPUTES the real arm — not "computes and declines
               to print". A void a reader can see through is advisory, and an
               advisory void is how an estimand gets chosen after the fact.

WHY/DIR:  §7 is prose. Two verdicts on this programme were published and
          retracted because a prose procedure was followed loosely.

          Building it produced a finding about the prereg itself. On the FIRST
          synthetic run the controls VOIDed a signal-free corpus. Measured
          properly: the registered |t| > 2.0 bar flags 8.0% of genuinely clean
          arms on this synthetic panel (12/150), so ALL-clean over five arms
          voids ~34% of valid experiments — against the 14% registered in §5
          from the clf corpus (3% per arm).

          The same frozen rule discards between 14% and 34% of valid work
          depending on panel shape. §5 registered only the low end. That is an
          amendment to the prereg, not a threshold to quietly loosen, and it is
          better found now than after a subject comes back VOID.

          A hypothesis I checked and DISCARDED: that 60-day overlapping labels
          make fold means autocorrelated, breaking the plain one-sample t.
          Measured lag-1 autocorrelation of null fold means: mean +0.001,
          median +0.040. The independence assumption holds; the bar is simply
          not calibrated to this statistic's tails.

EVIDENCE: artifact: `tools/traded_estimand_run.py` +
                    `tests/test_traded_estimand_run.py`, branch
                    `feat/traded-estimand-runner` stacked on
                    `prereg/traded-estimand-spread` (54481b8).
  prod or exp:      EXPERIMENT tooling, READ-ONLY. Reads corpora, writes
                    nothing. No registered subject was run.
  existing data:    Yes, measured this session on SYNTHETIC signal-free panels
                    (660 dates x 60 names, 44 folds) so no real corpus was
                    consumed: per-arm false-flag 12/150 = 8.0%; |t| median
                    0.69, p90 1.85, max 3.71; ALL-clean void rate ~34%
                    [DERIVED 1-0.92^5]. Lag-1 autocorrelation of null fold
                    means: mean +0.001, median +0.040, |ac|>0.2 in 3/20 arms.
  best-known?:      For the runner's two properties, yes (both directly
                    tested). The 8% figure is specific to this synthetic
                    geometry; the honest claim is the RANGE 14%-34%, not a
                    single rate.
  scope:            `renquant-model` tools + tests + this doc. No pin advanced,
                    no umbrella change, no live surface touched.

VERIFICATION:
          14 tests pass (`pytest tests/test_traded_estimand_run.py -q`).
          `test_void_does_not_compute_the_real_arm` monkeypatches the
          estimator to raise, so the test fails if the real arm is ever
          computed on a VOID. `test_frozen_check_reads_the_REMOTE_not_the_worktree`
          fails if a working-tree copy of the prereg is accepted as frozen.
          `test_frozen_check_rejects_a_local_edit_after_the_prereg_has_merged`
          builds a real git repo with `origin/main` frozen and a
          diverged local copy and fails if the gate is not byte-exact;
          `test_frozen_check_passes_when_local_copy_matches_origin_main_exactly`
          pins the non-regressed positive path.
          `test_the_registered_control_rule_voids_valid_experiments` pins the
          finding so a future change cannot quietly loosen the bar instead of
          amending §5.
          `test_the_flag_forces_rehearsal_even_when_the_prereg_IS_frozen` (new)
          asserts a frozen run passed `--i-am-not-preregistering` still stamps
          every output line REHEARSAL; `test_a_frozen_run_without_the_flag_is_NOT_stamped`
          (new) pins the counterpart — a genuine frozen verdict carries no
          rehearsal stamp.

NEXT:     Amend prereg §5 to register the RANGE and the geometry dependence
          before it freezes. Only then run PatchTST and prod XGB.
