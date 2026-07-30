# Progress: corpus cutoff-sanity + label-maturity audit ON THE TRADING AXIS

STATUS:   delivered (one read-only tool, usable as a gate, plus committed
          tests). No production path written, no config or artifact touched.
          Adds the C5 progress doc that was missing at PR open (codex MED 1),
          then a second round addresses a follow-up CHANGES_REQUESTED review
          (codex P1/P2, see "SECOND REVIEW ROUND" below), then a third round
          commits the replay log that the PR body already claimed existed
          (`doc/research/evidence/2026-07-30-corpus-trading-axis-audit.md`)
          and replaces the display-truncated SPY axis hash with the full
          64-char value, then a fourth round closes a silent-coercion bug on
          off-axis dates (codex MED, see "FOURTH REVIEW ROUND" below), then a
          fifth round drops an unreproducible standalone quantitative claim
          from the docstring (codex MED, see "FIFTH REVIEW ROUND" below).

WHAT:     `tools/corpus_trading_axis_audit.py` — given a WF score corpus and a
          trading-date axis, re-derives (a) whether any row's score_date sits
          at or before its own fold cutoff, and (b) what fraction of score
          dates have a `--lookahead`-TRADING-day forward window ending past the
          corpus's own last date. Indexes the axis directly rather than doing
          calendar arithmetic. Exits NON-ZERO on failure, so it is usable as a
          gate rather than only as a script. `tests/test_corpus_trading_axis_audit.py`
          (10 tests) pins the axis-stepping-vs-BDay behaviour on a synthetic
          holiday, the cutoff check, the label-maturity fraction (including
          the invariant that the trailing `lookahead` dates are always
          unverifiable), fail-loud on a corpus missing `date`, fail-loud on an
          off-axis (weekend/holiday) score date, and the CLI's exit codes.

SECOND REVIEW ROUND: a follow-up review (submitted against the pre-fix
          commit, before the first C5/evidence fix landed) raised two more
          findings, addressed here:

          [P1] the tool's docstring described itself as re-deriving a
          "purge margin" (`30 of 43 folds`, min `-4`, `19` overlaps) that it
          does not actually compute — it has no per-fold train/cutoff
          boundary logic. Reviewer offered two fixes: implement the real
          fold-level calculation, or narrow the tool/PR and remove the
          purge-margin claim. Took the narrow path (smallest correct fix):
          the docstring now states explicitly, in a SCOPE paragraph, that
          this script does not compute a purge margin and points to
          renquant-pipeline#228 for that separate, unimplemented question,
          instead of restating its numbers as something this tool measures.
          The PR title/body are updated to match — "label maturity" only,
          not "purge margin".

          [P2] no committed tests for the new CLI. Added
          `tests/test_corpus_trading_axis_audit.py` (8 tests, all passing;
          see VALIDATION). Per the narrowed [P1] scope, these test the
          checks the tool actually performs (axis stepping vs. a holiday,
          cutoff sanity, label maturity, CLI exit codes) rather than a
          fold-level margin calculation that isn't implemented.

FOURTH REVIEW ROUND: a follow-up review against the third-round head found
          that `nth_trading_day_after` (`tools/corpus_trading_axis_audit.py`,
          the `axis.searchsorted(...)` step) silently coerces an off-axis
          corpus date (a weekend or holiday) to the insertion point instead
          of failing — `searchsorted` doesn't distinguish "found" from
          "would insert here", so a malformed Saturday score-date got treated
          as if it were the following Monday, changing both the forward-end
          date and the reported unverifiable fraction without any error.
          Reviewer verified this locally with a synthetic `2024-01-06`
          (Saturday) corpus date against a business-day axis.

          Fix: `nth_trading_day_after` now checks `idx.isin(axis)` before
          calling `searchsorted` and raises `ValueError` naming the off-axis
          date(s) if any are found, so a malformed corpus fails loud instead
          of silently mis-reporting. `cutoff` is unaffected — the existing
          cutoff check is a plain calendar `<=` comparison, not axis
          arithmetic, so it never went through `searchsorted`. Added two
          fixture tests: `nth_trading_day_after` rejecting the exact
          off-axis-Saturday repro, and `audit()` rejecting a corpus built
          from it end-to-end. Test count: 8 -> 10.

FIFTH REVIEW ROUND: a follow-up review against the fourth-round head found
          that the module docstring (`tools/corpus_trading_axis_audit.py:16-20`)
          quoted a standalone SPY-axis-wide root-cause illustration —
          `2,597 cutoffs`, `99.8%` short, `mean 2.23 / median 2 / max 6
          TRADING days` — that has no committed evidence block. Reviewer
          re-ran the underlying calculation on the current axis and confirmed
          `2,597` and `99.8%` reproduce, but the shortfall statistic is
          unit-dependent and does not match the docstring's `2.23` under
          either definition tried (TRADING-day count: mean 2.16; calendar-day
          count: mean 3.17). Reviewer offered two fixes: add a committed
          evidence note and restate the numbers under one explicit
          definition, or drop the quantified sentence and keep the
          qualitative root-cause explanation only.

          Took the qualitative path (smallest correct fix, and consistent
          with the SECOND ROUND precedent of narrowing rather than adding new
          measurement infrastructure): the docstring's root-cause paragraph
          now explains the BDay/busday_count holiday defect in prose only,
          states explicitly that no standalone SPY-axis-wide mean/median/max
          is claimed because that figure is unit-dependent and unbacked by a
          replay log, and points at
          `doc/research/evidence/2026-07-30-corpus-trading-axis-audit.md` for
          the two numbers this tool DOES measure and back with a replay log
          (the per-corpus unverifiable fraction and per-corpus BDay-vs-axis
          shortfall, both already in the EVIDENCE section below — unchanged
          by this round). No functional code was touched, so the existing
          10/10 test pass is unaffected; re-ran it anyway (see VALIDATION).

WHY/DIR:  renquant-pipeline#228 AC-3. `pd.offsets.BDay(n)` and `busday_count`
          count BUSINESS days and do not skip market holidays, so both purge
          margin and label maturity had been asserted on a unit that is
          systematically short.

          The trap worth naming: `BDay(60)` spans exactly 12 weeks = 84
          calendar days, and `ceil(60*7/5)` is ALSO 84 — so switching the unit
          alone fixes nothing. Holidays are the entire defect, which is why the
          tool indexes the axis instead of computing an offset.

EVIDENCE:
  artifact:       `tools/corpus_trading_axis_audit.py` (this PR). Inputs are
                  READ-ONLY and pinned by sha256 (full 64-char hashes, not
                  truncated — see the replay log below for the exact command):
                    clf corpus  `clf_wf_scores.parquet`
                                1da3fcfab06af1e597ac0eb83dff4741ed3dd027de8b8a6b4d58979f5bc4efe4
                    PatchTST    `wf-eval/scores.parquet`
                                6eb209e2491b26b18b7b687c7683f27f8e5cbe56592186bfbac68381e2606d18
                    SPY axis    `RenQuant/data/ohlcv/SPY/1d.parquet`
                                0987e3b638cb9659aac0d5d68e2688773ef40b5f6ec907c9176dec1b30a10f2c
                  Replayable log with the exact command + full raw output for
                  both corpora: `doc/research/evidence/2026-07-30-corpus-trading-axis-audit.md`.
  prod or exp:    EXPERIMENT/audit tooling. Nothing written anywhere; the tool
                  only reads and prints.
  existing data:  Yes — RE-MEASURED this session by running the committed tool,
                  not recalled. Both pinned corpora reproduce identically:

                    rows with score_date <= own cutoff : 0
                    unverifiable score dates          : 60/625 = 9.6%
                    earliest                          : 2026-01-05
                                                        (needs data through
                                                        2026-04-01)
                    a BDay(60) bound would be SHORT on : 99.4% of them,
                                                        mean +3.63 / max +10
                                                        calendar days
                    exit code                          : 1 (FAIL), so it gates

                  That the two independently-built corpora return the SAME
                  9.6% is itself the point: the shortfall is a property of the
                  axis arithmetic, not of either corpus.

                  NOT reproduced here, and therefore attributed rather than
                  claimed: the `<= 0 margin on 30 of 43 folds (minimum -4), 19
                  folds with real return-window overlap` figure is PRIOR WORK
                  from renquant-pipeline#228's original finding
                  `[VERIFIED — prior work, renquant-pipeline#228]`. This tool
                  reports `0` rows at-or-before cutoff on both corpora above,
                  so it does not re-derive that number and this PR does not
                  assert it as its own measurement.
  best-known?:    Yes for the label-maturity fraction on these two pinned
                  corpora. Explicitly NOT claimed: that the labels are
                  immature. The tool's own output says it —
                  `unverifiable != immature`: the label may well be complete in
                  the panel; the CORPUS cannot establish it. The admissible
                  conclusion is that such a corpus must not be DESCRIBED as
                  label-verified.
  scope:          `renquant-model` tools + this doc. No pin advanced, no
                  umbrella change, no live surface touched.

VALIDATION:
          `python3 tools/corpus_trading_axis_audit.py --corpus <corpus> \
              --axis RenQuant/data/ohlcv/SPY/1d.parquet --lookahead 60`
          run this session against BOTH pinned corpora above; output as quoted,
          exit code 1 on the FAIL path (verified separately from the piped run,
          since a pipe masks the tool's own status).

          `python3 -m pytest tests/test_corpus_trading_axis_audit.py -v`
          10 passed, 0 failed, this session (was 8; +2 for the fourth-round
          off-axis-date fix). Re-ran the fourth-round repro directly
          (`nth_trading_day_after(axis, [Timestamp("2024-01-06")], 1)` on a
          business-day axis) and confirmed it now raises `ValueError` instead
          of silently returning `2024-01-09`.

          FIFTH ROUND: docstring-only change, no functional code touched.
          `python3 -c "import ast; ast.parse(open('tools/corpus_trading_axis_audit.py').read())"`
          clean, then re-ran
          `python3 -m pytest tests/test_corpus_trading_axis_audit.py -v` —
          10 passed, 0 failed, unchanged from the fourth round. Grepped the
          repo for the dropped figures (`2,597`, `99.8%`, `mean 2.23`) —
          none remain outside this progress doc's own round-history prose.

NEXT:     Wire it as an actual gate wherever a corpus is stamped
          label-verified, so the check runs instead of being available. A tool
          that must be remembered is not a gate.
