# Progress: M1 vol-cap support test — ABORTED at its own gate

STATUS:   delivered (prereg + result, both in this PR). The registered
          reconstruction gate (§4) fired before any arm was computed;
          the verdict is ABORT, not a result on the vol-cap-support
          question.

WHAT:     `doc/research/2026-07-30-vol-cap-support-mismatch-prereg.md` +
          `tools/vol_cap_support_run.py`. Freezes a one-way test — does
          the deployed model's edge concentrate in the names the
          pre-scoring 60% annualised-vol gate drops before scoring? —
          then runs it. §4's reconstruction gate (reconstructed
          standardised features must land within `|mean|<=0.15`,
          `sd in [0.8,1.25]` on >=90% of 172 columns before any arm is
          trusted) failed at 0.6% (1/172), so per §7.1 the run aborted
          with no arm reported.

WHY/DIR:  Continues the M1 workstream (`renquant-model#103` /
          `orchestrator#615` measured `STD60` as the live scorer's
          largest marginal effect and a 3.09x support gap between the
          names the vol gate keeps vs. drops). This PR was the first
          attempt to answer whether that gap costs edge. It did not
          answer that question: the gate caught a bug in the runner
          (double standardisation) before any arm could be reported —
          `train_production_model.py:240` states the on-disk training
          panel is already normalised, and the runner applied the
          artifact's serving-side moments on top of that a second time.
          §7.4 forbids revising a verdict by changing the procedure, so
          this document's verdict stays ABORT; answering M1 needs a new
          registration that feeds the already-normalised columns to the
          booster directly, not a re-run of this one.

EVIDENCE: artifact: `doc/research/2026-07-30-vol-cap-support-mismatch-prereg.md`
                    + `tools/vol_cap_support_run.py` (this PR), on
                    `renquant-model` @ head `758b740`. Reproduced by:
                      `python3 tools/vol_cap_support_run.py
                       --panel <umbrella>/data/alpha158_291_fundamental_dataset.parquet
                       --artifact <umbrella>/backtesting/renquant_104/artifacts/prod/panel-ltr.alpha158_fund.json
                       --ohlcv-dir <umbrella>/data/ohlcv`
                    Output logged at `doc/research/data/2026-07-30-m1-abort.log`
                    (gitignored per this repo's `.gitignore:12`, so it is
                    a local artifact rather than a committed file — cited
                    here so a reviewer can regenerate it byte-for-byte).
  prod or exp:      EXPERIMENT. Panel (sha256-pinned, ABORTS on mismatch)
                    and artifact opened READ-ONLY; nothing written outside
                    this branch.
  existing data:    Yes — §4 gate result: 1/172 standardised columns (0.6%)
                    landed within the registered tolerance, against a 90%
                    floor. Worst offenders: `book_to_price` (mean +1.4e17),
                    `earnings_yield` (+2.8e16), `VWAP0` (−106.15), `HIGH0`
                    (−72.42), `LOW0` (−71.56) — the exact signature of a
                    second standardisation on already-normalised data
                    (`VWAP0` stored `mu=1.0` vs. panel mean `−0.0065,
                    sd 0.966`; `STD60` stored `mu=0.0576` vs. a freshly
                    computed raw `std(close,60)/close` of `0.047-0.055`).
  best-known?:      N/A — no arm was computed, so there is no edge/no-edge
                    number to compare against a prior best. The ABORT
                    itself is the deliverable (see WHY/DIR).
  scope:            `renquant-model` docs + one read-only tool script.
                    Production panel and artifact opened read-only; no
                    write to any production path; no config, model, or
                    live-surface change.

NEXT:     M1's question (does the vol cap truncate the model's edge)
          remains OPEN — a new registration is required (feed
          already-normalised columns directly to the booster, no second
          standardisation) before it can be answered; that is a fresh
          freeze, not a re-run of this document. Separately, this PR's
          abort surfaced a real function-level defect, filed as
          `RenQuant#545`: the raw-clip contract covers only 158 of 172
          `feature_cols` and leaves all 14 fundamental columns unbounded
          — `book_to_price`'s raw panel values reach a max of `+1.68e19`
          (mean `+3.96e16`), with 11,006 rows (1.52%) exceeding
          `|value|>1e6`. Fixing that needs `fetch_sec_fundamentals.py`'s
          `_safe_ratio` to gain a denominator floor / winsorisation and
          the clip contract to cover all `feature_cols` and error rather
          than silently store `None` — out of scope for this PR.
