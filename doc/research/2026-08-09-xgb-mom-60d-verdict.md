# xgb_mom_60d — the one execution: NO ADMISSIBLE VERDICT

The single execution of the merged prereg (model#211) ran 2026-08-09 and
its raw output is committed below — but review found the execution does
not meet its own prereg's terms, so **no verdict is recorded against the
frozen §3 gate**. This artifact is exploratory diagnostics only. Nothing
enters the system from this line; deployment stays blocked.

## Why the execution is inadmissible `[VERIFIED — code review of the committed harness, r1]`

1. **No purge/embargo for a 60d label.** Each fold trains through `tr_e`
   and starts testing ~32 calendar days later (e.g. train ..2018-12-31,
   test 2019-02-01..). The label `fwd_60d_excess` realizes over 60
   trading days (≈84 calendar days), so train rows dated in roughly the
   last three months before `tr_e` have realized-label windows that
   extend INTO the test interval. Training labels overlap the evaluation
   period in every fold; per-fold ICs are contaminated in an amount this
   artifact cannot bound. The pre-run synthetic controls (positive /
   null) validate signal detection, not temporal separation — they could
   not have caught this.
2. **The prereg's corpus sha256 was never checked at execution.** The
   pin (`870f68eb…`) existed only in the doc; the harness read the
   parquet path unverified.
3. **The feature list came from a mutable machine-local scratchpad
   JSON**, not from an enforced frozen list. Post-hoc comparison this
   session shows the scratchpad list was set- and order-identical to the
   prereg §5 list, but at execution time nothing enforced that.
4. **The result JSON stores aggregate ICs only** — its verifier can
   recompute the gate arithmetic but cannot establish that the claimed
   corpus, features, and folds actually generated the numbers.

The harness is now hardened for the record (features embedded, corpus
sha asserted in `--real`) — that hardening does not retroactively repair
this run, and the leaky fold construction is retained in the file only
as the record of what ran.

## Raw arithmetic, retained as diagnostics `[VERIFIED — committed result JSON; contaminated per reason 1]`

| fold (test year) | real IC | shuffle IC | real signal |
|---|---|---|---|
| 2019 | −0.005 | +0.022 | −0.026 |
| 2020 | +0.197 | +0.080 | +0.117 |
| 2021 | −0.051 | −0.019 | −0.032 |
| 2022 | +0.018 | −0.008 | +0.026 |
| 2023 | +0.059 | +0.072 | −0.013 |
| 2024 | −0.010 | −0.002 | −0.009 |
| 2025 | +0.114 | +0.041 | +0.073 |
| 2026 (to 05-07) | +0.131 | +0.090 | +0.041 |

Mean real signal +0.0221; 4/8 folds positive; A/A seed std 0.0017.
Applied naively, the frozen gate's arithmetic evaluates to KILL on leg 2
— but that is arithmetic on inadmissible inputs, not an outcome. **No
reading of the fold pattern is offered**: with train labels overlapping
every test window, apparent year-to-year structure cannot be separated
from the contamination, so this note draws no inference from it.

Committed artifacts: `data/2026-08-09-xgbmom-run.py` (harness, r1-hardened) ·
`data/2026-08-09-xgbmom-result.json` (raw per-fold output, unchanged) ·
`data/2026-08-09-xgbmom-control-{positive,null}.json` (pre-run controls:
planted +0.3715 PASS / null −0.0027 KILL) ·
`data/2026-08-09-xgbmom-verify.py` (internal-arithmetic check, exit 0).

## What a valid test requires (a NEW dated prereg — not a rerun of #211)

* corpus sha256 and the exact 70-column §5 feature list **asserted by
  the harness at execution**, with per-fold provenance (corpus hash,
  feature hash, fold bounds, row counts) written into the result
  artifact;
* a purge/embargo **at least as long as the realized 60-day label
  horizon**, with the exact trading-session definition stated, applied
  before every test fold;
* #211's own terms prohibit retrying under its name — its gate remains
  unexecuted in the admissible sense, and this artifact must not be
  cited as its outcome.

## Standing consequences

* No new arm enters the system from this line; nothing below
  shadow-candidacy exists for any momentum learner.
* The conditional-activation idea mentioned in the first push is
  withdrawn along with the episodic reading that motivated it; if it is
  ever pursued, it starts from a NEW prereg with the embargoed fold
  design above.

## Corrections (visible, per review r1)

The first push of this note recorded "**Verdict under the frozen §3
gate: KILL**" and read the fold pattern as "episodic, not persistent"
momentum. Both are withdrawn: the execution was inadmissible for the
four reasons above, so neither a KILL nor any fold-pattern inference can
be recorded. The raw numbers are unchanged; only their status changed —
from preregistered outcome to exploratory diagnostics.
