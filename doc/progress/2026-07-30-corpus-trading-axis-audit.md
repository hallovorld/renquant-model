# Progress: re-derive corpus purge margin and label maturity ON THE TRADING AXIS

STATUS:   delivered (one read-only tool, usable as a gate). No production path
          written, no config or artifact touched. Adds the C5 progress doc that
          was missing at PR open (codex MED 1).

WHAT:     `tools/corpus_trading_axis_audit.py` — given a WF score corpus and a
          trading-date axis, re-derives (a) whether any row's score_date sits
          at or before its own fold cutoff, and (b) what fraction of score
          dates have a `--lookahead`-TRADING-day forward window ending past the
          corpus's own last date. Indexes the axis directly rather than doing
          calendar arithmetic. Exits NON-ZERO on failure, so it is usable as a
          gate rather than only as a script.

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
                  READ-ONLY and pinned by sha256:
                    clf corpus  `clf_wf_scores.parquet`
                                1da3fcfab06af1e5…5bc4efe4
                    PatchTST    `wf-eval/scores.parquet`
                                6eb209e2491b26b1…e2606d18
                    SPY axis    `RenQuant/data/ohlcv/SPY/1d.parquet`
                                0987e3b638cb9659…1b30a10f2c
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

NEXT:     Wire it as an actual gate wherever a corpus is stamped
          label-verified, so the check runs instead of being available. A tool
          that must be remembered is not a gate.
