# Progress: closure re-run conflict — explained (estimand difference), pending adversarial review

STATUS:   RESOLVED as a definitional difference, not a bug — the two
          sample-stable constructions were answering different questions
          (persistence vs. horizon), not disagreeing about the same one. The
          re-run under `align_lag_pairs` that this doc originally planned as
          NEXT has already happened and reproduced this run's numbers
          exactly, eliminating the leading candidate cause (date-level vs
          pair-level alignment). What remains open is adversarial review of
          this explanation, not another re-run — PatchTST's recorded status
          stays UNRESOLVED-pending-adversarial-review until that happens.

WHAT:     Adds `doc/research/2026-07-29-patchtst-closure-rerun-conflict.md`: the
          re-run of model#87's frozen rule under the corrected primitive, its
          numbers, the initial apparent conflict with the bug hunt's
          recomputation, and a "Resolution" section tracing that conflict to
          an estimand difference — the audit's `common-SD` construction holds
          score dates common (a horizon question), this run holds label dates
          common (the persistence question the frozen rule actually asks) —
          confirmed by re-running under `align_lag_pairs` and getting
          numerically identical results, ruling out an alignment bug.

WHY/DIR:  model#87's rule is frozen and merged; only its instrument was
          defective. A re-run under the corrected primitive is legitimate.
          Publishing its answer as PatchTST's recorded status while the
          explanation for why it differs from the retracted verdict is
          same-author, unreviewed reasoning is not — hence
          UNRESOLVED-pending-adversarial-review rather than CLOSE.

EVIDENCE: artifact:      `doc/research/2026-07-29-patchtst-closure-rerun-conflict.md`
          (this PR) `[VERIFIED — this PR's diff]`.
           prod or exp:   experiment — signal-evaluation research artifact,
          not a production/live path.
           existing data: this run, recomputed over the content-addressed
          bundle `f6b6ef6d…/wf-eval` `[VERIFIED — recomputed 2026-07-29]`:
          PatchTST negative at all four lags (block t −1.01, −1.39, −1.53,
          −1.88) ⇒ p = 4/4; prod XGB control positive at all four (+1.30,
          +1.36, +1.76, +1.71) ⇒ VALID — mechanically CLOSE under model#87's
          frozen rule. Rerun under `align_lag_pairs`: numerically identical
          (same values to three decimals), ruling out date-vs-pair alignment
          as the source of the earlier apparent conflict with the bug hunt's
          `common-SD` (score-date-common) recomputation, which answers a
          different question and does not bear on this rule.
           best-known?:   not yet — the estimand-difference explanation is
          this run's own reasoning, submitted for adversarial review, not
          independently confirmed. PatchTST's recorded status does not
          change until that review happens.
           scope:         "this re-run and its explanation bear on PatchTST's
          closure question only; no other model/IC/Sharpe claim is made."

NEXT:     Adversarial review of the estimand-difference explanation (not
          another re-run — the re-run this doc originally planned already
          happened, see EVIDENCE). If that review confirms the explanation,
          PatchTST's status updates to CLOSE per model#87's frozen rule; if
          it finds a genuine flaw, PatchTST stays UNRESOLVED and the flaw
          gets recorded the same way this conflict was.
