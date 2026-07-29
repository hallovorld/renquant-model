# Progress: prereg template — the night's failures, made inheritable

STATUS:   delivered. Template only; changes no existing prereg.

WHAT:     Adds `doc/research/templates/PREREG_TEMPLATE.md` with a two-tier
          applicability gate (codex MED): BASELINE for any study that changes what we
          believe, CONFIRMATORY only when the rule would change a model's STATUS or
          trigger a production action. Control calibration (§5) and pre-publication
          adversarial review (§7) are CONFIRMATORY-only; the trap checklist, estimand
          naming and input provenance are BASELINE. Mandatory sections plus a
          15-row known-trap checklist, three rows of which (T13 HARKed estimand, T14
          uncalibrated control, T15 stale digest citation) were paid for in the last
          few hours.

WHY/DIR:  Two CLOSE verdicts on the same question were published and retracted in one
          day. The second died on a commissioned adversarial review. Writing the
          lessons into retraction notes stops nothing; a template that the next prereg
          copies is the only form that carries.

EVIDENCE: artifact:      `doc/research/templates/PREREG_TEMPLATE.md` (this PR)
          `[VERIFIED - this PR's diff]`.
           prod or exp:   docs/tooling only - a reusable template, not a
          model result or production artifact.
           existing data: each new trap row cites its measured cost
          `[VERIFIED - adversarial review + this session's runs]`: T13, the
          estimand chosen after seeing which one gave CLOSE, against frozen
          text that named the other - the decisive break (model#92's
          `patchtst-closure-retraction.md`); T14, a bare sign-count control
          passing 37.5% of the time on signal-free input (and zero-skill AR
          scores 50-55%), i.e. structurally unable to fail; T15, a cited root
          digest of f6b6ef6d.../44 files against an actual 901f0add.../61
          because the bundle was appended to after citation - note that
          `901f0add...` is itself only reproducible with model#93's tool fix
          (APPROVED, not yet merged as of this writing), a fact T15's own row
          in the template should name for anyone trying to verify it today.
           best-known?:   n/a - a process template, no model/statistic
          ranking claim.
           scope:         "template + trap-checklist change only; no existing
          prereg is modified, no model claim is made. Section 5 (control
          calibration, >=40 reps / ~10% false-pass ceiling) and section 7
          (PRE-publication adversarial review) are gated confirmatory-only:
          required when the prereg's decision rule could change model status
          or a production-facing action, N/A for routine diagnostics/
          exploratory work (codex MED, addressed 2026-07-29 - the two
          sections were previously unconditionally mandatory, disproportionate
          for routine work)."

NEXT:     Use it for the next PatchTST attempt, which needs a new prereg naming the
          estimand up front and a bias-corrected estimator. INCONCLUSIVE stands until
          then.
