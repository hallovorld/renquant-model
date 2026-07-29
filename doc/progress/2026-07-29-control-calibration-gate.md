# Progress: a control arm must be shown to be null before it certifies anything

STATUS:   delivered (primitive + tests). The PatchTST verdict itself is NOT
          changed by this PR and remains INCONCLUSIVE.

WHAT:     New `renquant_model_common/control_calibration.py`:
          `assess_control(values)` -> `ControlVerdict{CLEAN | NOT_NULL |
          UNPROVEN}` and `gate_comparison(controls)` -> `(may_proceed,
          verdicts)`. A control whose own |t| exceeds a threshold is NOT_NULL
          and VOIDS the comparison; a control with too few observations is
          UNPROVEN, which is explicitly not usable. Supplying no controls
          raises rather than passing. 13 tests.

WHY/DIR:  Measured 2026-07-29 on the 43-fold PatchTST walk-forward corpus while
          building the kill-line prereg. The evaluation reads its real arm
          against a `shift120` label-displacement placebo and a 5-seed label
          shuffle:

              arm                  mean IC       t        p
              real                +0.0343    +1.38    0.178
              shift120 (placebo)  +0.0715    +2.90    0.006   <- SIGNIFICANT
              shuffle  (null)     +0.0013    +0.90    0.375

          The placebo scored HIGHER than the real arm and was the only arm to
          clear significance. A control in that state cannot support a verdict
          in EITHER direction: it does not represent the no-signal world, so
          both "the real arm beats it" and "the real arm fails to beat it" are
          uninterpretable.

          Displacing a label by 120 trading days was assumed to destroy
          alignment. It does not — a score carrying slow-moving cross-sectional
          structure still correlates with a return window six months out. The
          assumption was never tested because controls are usually assumed null
          BY CONSTRUCTION. That is the habit this primitive breaks.

EVIDENCE:
  artifact:       `renquant-model` @ `origin/main` 8579fa7 + this branch.
                  Corpus: `scratchpad/wf-eval/scores.parquet` (88,750 rows,
                  625 score dates, 142 tickers, 43 folds) joined to
                  `RenQuant/data/transformer_v4_wl200_clean.parquet`
                  (`fwd_60d_excess`), READ-ONLY.
  prod or exp:    EXPERIMENT/analysis + a new library primitive. No production
                  data, config, or artifact written. The corpus lives in the
                  quarantined scratch namespace, as its own prereg requires.
  existing data:  Yes, and the headline was RE-MEASURED this session rather
                  than recalled, which changed it twice:
                  1. As the harness computes it, real = +0.0278 (t=+1.22) vs
                     shift120 = +0.0715 (t=+2.90), apparent gap -0.0437. But
                     the harness applies `lab.shift(-120)` with NO
                     realignment, so the arms sit on different samples:
                     real = 625 score dates ending 2026-03-31; shift120 = 524
                     ending 2025-11-03. The 101 dates only `real` can evaluate
                     are ALL the NEWEST (verified `min(lost) > max(shift)`)
                     and carry mean IC = -0.0128 — i.e. `real` was charged for
                     an era `shift120` never saw. This is the same
                     `.shift(-N)` sample-drift defect that retracted an
                     earlier verdict, still live in this harness.
                  2. Recomputed on the COMMON 524-date sample: real rises to
                     +0.0343 (t=+1.38) — and shift120 is UNCHANGED at +0.0715
                     (t=+2.90). So the placebo's significance is NOT a
                     sample-drift artefact. It survives the correction, which
                     is what makes it a finding rather than a bug report.
  best-known?:    For "this control is not null", yes — direct measurement,
                  reproduced on a common sample. NOT claimed: any verdict on
                  PatchTST. This corpus has produced two retracted verdicts;
                  a third analysis of it is a screen, not a decision.
  scope:          `renquant-model` only. No pin advanced, no umbrella change,
                  no live surface touched.

SCOPE/LIMITS:
          The threshold (|t| > 2.0) is a REGISTERED CHOICE, not an estimate: it
          is deliberately stricter than a discovery bar because wrongly
          trusting a broken control costs a published-then-retracted verdict,
          while wrongly rejecting a usable control costs one more control run.
          Callers who registered a different bar pass `max_abs_t`.

          This decides only whether a control is fit to be a null. It does not
          compute a treatment effect, choose an estimand, or rank models. It
          pairs with `lag_alignment`: that module makes arms share a sample,
          this one makes the control mean something once they do.

VERIFICATION (both runs this session, `--continue-on-collection-errors`):
  baseline `origin/main` 8579fa7 : 539 passed, 19 collection errors
  this branch                    : 552 passed, 19 collection errors
  552 - 539 = 13, exactly the new tests. The 19 errors are a pre-existing
  environment fault (`_SixMetaPathImporter`) present identically on untouched
  `origin/main`; this PR neither causes nor fixes them.

NEXT:     1. The `wf-eval` harness still contains the unaligned
             `lab.shift(-120)`. Any future run of it must go through
             `lag_alignment` first; the corrected numbers above were produced
             that way by hand.
          2. A PatchTST kill-line prereg CANNOT be run on this corpus: its
             only significant arm is a control, and the corpus has already
             been used for two retracted verdicts. A verdict needs a validated
             control and score dates not yet consumed.
