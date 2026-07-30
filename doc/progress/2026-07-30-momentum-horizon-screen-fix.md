# Progress: fix — the placebo shuffle leaked labels across dates on an interleaved frame

(PR #105 — `prereg/momentum-horizon-screen`, fixed by claude)

STATUS:   delivered (round 2, this push). Round 1 fixed the shuffle bug and
          added this doc but left the main research doc's RESULT section
          asserting a valid `UNRESOLVED` verdict. Codex correctly flagged
          (two follow-up CHANGES_REQUESTED reviews) that a broken placebo
          control invalidates the verdict itself, not just its numbers, and
          that the doc cited `doc/research/data/2026-07-30-m2.log`/`.json`
          artifacts that were never committed. Round 2 (this push) recasts
          the result as `ABORTED — INVALID CONTROL` in both the research doc
          and the PR body, and corrects the artifact citation. No re-run of
          the frozen prereg was performed — see NEXT for why that stays out
          of scope.

## Round 2 (this push): recast the verdict, fix the dangling artifact citation

WHAT:     `doc/research/2026-07-30-momentum-horizon-prereg.md` — added an
          ERRATUM block at the top of the RESULT section stating the run is
          `ABORTED — INVALID CONTROL`, not the `UNRESOLVED` verdict as first
          reported: Phase S selection and the Phase H "placebos clean" gate
          both depend on `shuffle_within_date` being a true within-date
          permutation, which round 1 proved it was not. Relabelled the
          verdict heading and the "real finding" diagnostic section as
          `[QUARANTINED ...]`, and added a closing note to "What is NOT
          claimed". Also corrected the dangling citation to
          `doc/research/data/2026-07-30-m2.log`/`.json` — neither file was
          ever committed to this branch or found in any local working copy;
          the citation now says so instead of pointing at files that do not
          exist.

WHY/DIR:  §8 of the frozen prereg forbids revising a verdict by re-running
          under a corrected procedure, but it does not forbid correcting the
          record on what the *first* run actually established. Presenting a
          verdict computed with a proven-broken control as a valid
          `UNRESOLVED` is the kind of "X works/fails" claim CLAUDE.md §7.2
          requires an evidence trail for, and here the trail shows the
          claim does not hold. `ABORTED — INVALID CONTROL` is a distinct,
          more accurate epistemic status than `UNRESOLVED` (a statement
          about the frozen procedure's power), because we can no longer
          certify the procedure ran as designed.

EVIDENCE: artifact: `doc/research/2026-07-30-momentum-horizon-prereg.md`
                    (this push).
  prod or exp:      EXPERIMENT/doc only. No code changed this round; no
                    production data, config, model, or artifact touched.
  existing data:    `[VERIFIED — this session]` `find . -iname
                    "*2026-07-30-m2*"` and `git log --all -- "doc/research/
                    data/2026-07-30-m2*"` both return nothing — the cited
                    log/json artifacts were never committed to this repo at
                    any point in its history.
  best-known?:      N/A — no IC/Sharpe/effect-size number is newly asserted;
                    this round only corrects the epistemic status of
                    already-reported (now-quarantined) numbers.
  scope:            `renquant-model` docs only. No change to code, no new
                    experiment run, no claim about momentum.

NEXT (round 2): PR body updated to match (title + bottom line now say
          `ABORTED — INVALID CONTROL`, per Codex's ask to recast in "the main
          research doc and PR body"). A corrected registration — fixing the
          horizon-biased selection rule, the horizon-aware control bar, and
          the dividend-adjustment gap — is still a new prereg, not a patch to
          this one, and is not started here.

---

## Round 1 (original push)

WHAT:     `tools/momentum_horizon_run.py::shuffle_within_date` rewritten to
          permute `ycol` within each `_dcode` group directly (via
          `f.groupby("_dcode").indices`), instead of a lexsort-and-reindex
          that only shuffled correctly when rows already arrived grouped by
          date. Adds `tests/test_momentum_horizon_shuffle.py`, which
          reproduces Codex's exact counter-example (dates `[d1,d2,d1,d2]`,
          labels `[10,20,11,21]`) plus a larger interleaved-frame
          permutation check and a seed-sensitivity check. This progress doc
          is the second finding — it was missing at PR open.

WHY/DIR:  Both Phase S arm/horizon selection and the Phase H holdout
          "placebos clean" gate in the frozen prereg
          (`doc/research/2026-07-30-momentum-horizon-prereg.md`) depend on
          `shuffle_within_date` producing a TRUE within-date label
          permutation — that is the entire point of a placebo control. The
          old form built the shuffled column by sorting the frame into
          `(_dcode, random)` order and then writing that sorted sequence
          back into the ORIGINAL row positions positionally. That is only a
          correct within-date shuffle if the input frame already arrives
          pre-sorted/grouped by date; on an interleaved frame (the general
          case — `measure()` calls it on `sub`, built from a `.dropna()` on
          the full merged panel, which is date/ticker-interleaved, not
          sorted by date) a row can receive another date's label. Codex's
          reproducer shows exactly this: row 1 (`date=d2`) received label
          `21`, which was `d1`'s.

EVIDENCE: artifact: `tools/momentum_horizon_run.py` (this PR/push), on
                    `renquant-model` PR #105 head `ca944c2` + this fix
                    commit.
  prod or exp:      EXPERIMENT tooling only. No production data, config, or
                    artifact touched. Nothing re-run against the pinned
                    matrix or OHLCV.
  existing data:    `[VERIFIED — this session]` Old code, run against
                    `tests/test_momentum_horizon_shuffle.py`: 2 of 3 tests
                    FAIL (`test_interleaved_frame_does_not_leak_across_dates`,
                    `test_shuffle_is_a_permutation_within_each_date_group`),
                    confirming the leak reproduces on this head. New code:
                    all 3 tests PASS, plus the 27 pre-existing
                    `tests/test_lag_alignment.py` tests (the dependency this
                    tool imports for `dependence_aware_mean`) still pass
                    unchanged.
  best-known?:      N/A — no IC/Sharpe/effect-size number is asserted here.
                    This is a control-mechanism correctness fix, not a
                    result.
  scope:            `renquant-model` tooling + tests only. No claim about
                    momentum, no change to the frozen verdict.

NEXT:     The PR's registered verdict (screen selects A2 `mom_6_1` @ h=20;
          holdout `t=+1.51 < 1.96` -> UNRESOLVED) is UNCHANGED by this fix:
          §8 of the frozen prereg forbids revising a verdict by re-running
          under a corrected procedure — that is a new registration, not a
          patch to this one. Whether the leak actually flipped which
          (arm, horizon) pair Phase S selected, or which screen/holdout
          cells were flagged PLACEBO-DIRTY, is therefore an open question
          left for a future registration, not answered by this commit. The
          PR's own §"What a corrected registration must fix" already lists
          the horizon-aware control bar as item 2; this fix addresses the
          shuffle's correctness but not that item's design change.
