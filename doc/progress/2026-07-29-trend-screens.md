# Progress: two frozen screens on momentum/reversion — both negative

STATUS:   delivered. Two designs frozen BEFORE their runs (git order proves it),
          both run, both OUTCOME 2. 0 of 18 registered tests clear the bar.
          No factor change proposed. No production surface touched.

WHAT:     `doc/research/2026-07-29-vol-conditioned-momentum-reversion-screen.md`
          (design `ff91d67`, results `404fdb0`) — 5 arms.
          `doc/research/2026-07-29-momentum-family-screen.md`
          (design `192f1b1`) — 4 arms, registered on operator preference.
          `tools/vol_conditioned_trend_screen.py`,
          `tools/momentum_family_screen.py` (imports screen 1's estimator so the
          two cannot silently diverge), `tests/test_trend_screens.py`.
          Verbatim runner output + JSON under
          `doc/research/evidence/2026-07-29-trend-screens/` (fixed by claude:
          the original `doc/research/data/` path is caught by this repo's
          blanket `.gitignore` `data/` rule and can never be committed;
          re-ran both pinned runners — identical numbers — and committed
          the output under the existing `doc/research/evidence/<slug>/`
          convention instead).

WHY/DIR:  The operator's reading of the live scorer was that it should combine
          momentum and mean-reversion, then that they lean towards momentum.
          Both are testable. The point of freezing first was that a preference
          must not be able to move a threshold: screen 2 RAISED the joint bar to
          |t| >= 2.99 (18 tests) and that supersedes screen 1's 2.81 upward,
          which is why screen 1's best arm (R3, |t|=2.82) is reported as failing.

EVIDENCE: artifact:  `RenQuant/data/alpha158_291_fundamental_dataset.parquet`
                     sha256 7defdacf97f8eb057a9a56a2eb7bc6eb48bc33adb9fd00a2a6c36943be87daa5,
                     production file opened READ-ONLY, pinned by both runners
                     which ABORT on mismatch. 725,547 rows / 2,597 dates / 292
                     tickers. Label mean=-0.0000 sd=0.9982 MEASURED.
          command:   `<umbrella>/.venv/bin/python tools/vol_conditioned_trend_screen.py
                      --panel <panel> --json-out <...>`  and the same for
                     `tools/momentum_family_screen.py`. Both under `caffeinate`.
          headline:  My own hypothesis is REFUTED. N1 (vol-conditional
                     momentum+reversion) = -0.0346, t=-1.97, VOID, and WORSE
                     than the naive blend it had to beat.
                     Unconditional momentum is priced NEGATIVELY on the traded
                     decile at three horizons with clean controls: ret(60)
                     -0.0519 (t -2.59, ctl 0.38), ret(20) -0.0460 (t -2.52),
                     ret(60)-ret(5) -0.0571 (t -2.66). The positive sign sits
                     with reversion: rev20 +0.1268 (t +2.82, ctl 1.54).
                     The one momentum construction that flips positive is
                     vol-GATED ret(60): +0.0773 (t +2.41, ctl 1.46) — the GATE
                     not the SCALING, since ret(60)/STD60 is +0.0079 t=+0.20.
                     It fails the 2.99 bar AND contradicts N1's sign.
                     Side observation: every arm's |t| is LARGER on the traded
                     top-decile spread than on full cross-section IC, which is
                     renquant-model#101 §1's registered claim, now seen from
                     outside the corpus #101 consumed. SCREEN only.
  prod or exp:     EXPERIMENT. Production panel read-only; nothing written
                   outside this branch; no retrain, no config, no capital action.
  existing data:   Yes — the panel was already on disk. No refetch, no spend.
  best-known?:     Yes for these 9 arms on this corpus. Two things I got wrong
                   and corrected in the record rather than quietly: (a) my
                   registered hypothesis lost to the naive blend it was designed
                   to beat; (b) my control rule mechanically labels any NULL arm
                   VOID, since any control noise out-scores a near-zero t — a
                   design flaw disclosed in the results, which makes MORE of the
                   output null, and NOT amended retroactively.
  scope:           `renquant-model` docs + tools + tests only. No pin advanced,
                   no umbrella change, no orchestrator change.

SCOPE/LIMITS:
          The corpus is now CONSUMED by two screens and can confirm neither. No
          cost, turnover or capacity model: rev5's +0.1243 was VOID anyway and
          rev20's +0.1268 carries no turnover haircut, so a gross spread is not
          an opportunity. Label is per-date z-scored, so +0.1268 is 0.127 SD of
          forward-return dispersion, NOT 12.7% — no P&L claim is possible.
          Horizons beyond 60 trading days (mom_12_1 proper, MA200, 52wk-high)
          are NOT constructible from this panel (ROC5..ROC60 only) and are
          declared out of scope rather than omitted. STD60 terciles/medians are
          on the full panel cross-section, NOT the vol-capped support the live
          path scores (orchestrator#615 §4), so M3/M4 would need a
          serving-support replication before meaning anything operationally.
          The three same-sign momentum horizons are three views of one trend
          axis on one corpus and are NOT pooled into significance.
          Measured control cost: corpus false-flag 1/30 = 3% per arm => 16%
          expected void, but 4 of screen 1's 10 tests VOIDed (40%). Left open.

VERIFICATION:
          `python3 -m pytest tests/test_trend_screens.py -q` -> 9 passed. These
          are POSITIVE CONTROLS run before any verdict was read, because a
          screen whose estimator cannot detect a known effect produces negatives
          indistinguishable from real ones: a planted +0.30 effect must be
          recovered on BOTH estimands, a signal-free panel must stay null, the
          sign must not be inverted, the within-date shuffle must preserve each
          date's label distribution while destroying the score-label link, the
          top-decile k must equal round(0.10*n) exactly as #101 §2 freezes it,
          ret() must invert ROC (ROC=0.5 -> +1.0) and refuse non-positive ROC,
          screen 2 must not re-run ret(60) (it is screen 1's R1), and screen 2's
          bar must be strictly above screen 1's.
          Independently, screen 2's M1 arm is a deliberate tripwire: a POSITIVE
          on a near-replication of a killed factor would have indicted the
          plumbing. It came back -0.0460, consistent with the sealed result.

NEXT:     Under the frozen rules the licensed output is: no factor change. The
          single thread that would justify further work is vol-GATED momentum
          (M4), and only via a confirmatory prereg on a corpus neither screen
          has touched, which must first resolve why M4 and screen 1's N1
          disagree in sign on the same conditioning idea. A future registration
          should also fix the VOID rule to require an absolute control bar.
