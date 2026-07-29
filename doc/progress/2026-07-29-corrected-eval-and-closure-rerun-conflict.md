# Progress: Q1 corrected-eval results (exploratory) + PatchTST closure re-run conflict (explained, pending adversarial review)

STATUS:   Two findings on this PR, tracked together after the orchestrator's
          progress-doc check flagged the branch's original two separate files
          as `multiple progress docs present` (exactly one is required per
          PR). Consolidated here verbatim, one field-set per part.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-results.md`
          (Part 1) and `doc/research/2026-07-29-patchtst-closure-rerun-conflict.md`
          (Part 2). See each part below for its own WHAT/WHY/EVIDENCE/NEXT.

WHY/DIR:  Both parts stem from model#90's frozen prereg and its two
          downstream re-runs (corrected Q1 evaluation; PatchTST closure
          re-run). See each part below.

EVIDENCE: see each part's own EVIDENCE block below (both use the literal
          §4(b) sub-fields: artifact: / prod or exp: / existing data: /
          best-known?: / scope:).

NEXT:     see each part's own NEXT below.

---

## Part 1 — corrected-evaluation results — EXPLORATORY only (not yet confirmatory)

STATUS:   in-progress. Restores the results document that was removed from model#90 for
          citing an unauditable path, but review (PR #92, two CHANGES_REQUESTED passes)
          caught that the restored bundle is itself defective in two ways this doc must
          not paper over — downgraded to exploratory per the fix below.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-results.md`: the Q1
          decision statistic recomputed with the merged three-view estimator, the raw-IC
          contrast, and an explicit statement of what is NOT established. The document
          now leads with an EXPLORATORY caveat (not confirmatory) instead of presenting
          the numbers as a settled post-prereg verdict.

WHY/DIR:  model#90 froze the design and merged; its numbers had been stripped because
          they pointed at session scratch. The artifacts are now retained and
          content-addressed over their OUTPUT files, so the same numbers are quotable as
          exploratory findings — but two defects block treating them as confirmatory:
          (1) the retained bundle (`harness.py`/`results.json`/`verdict.json`) is
          timestamped 2026-07-28 23:34-23:35 PDT, ~3h BEFORE model#90 merged at
          2026-07-29 02:19:34 PDT `[VERIFIED - git log -1 8579fa7; ls -la on the
          bundle]` — it cannot be "recomputed against the merged prereg" when it
          predates the merge; (2) the harness reads mutable inputs from
          `/Users/renhao/git/github/RenQuant/data/...` and session-scratch parquet
          outside the bundle, and imports from `/private/tmp/renquant-model-pr89-review
          /src` — the root digest covers only outputs, so a verifier cannot reproduce
          these numbers from the bundle alone.

EVIDENCE:
artifact:      /Users/renhao/renquant_bundles/corrected-eval-20260729/ (44 files, root
               digest f6b6ef6d5055600df190da9d56c32453e31b71c54ff5beeda88e12caac0df38a
               over OUTPUT files only, re-verifiable with `tools/corpus_index.py
               verify`, model#91 — does NOT cover inputs, see WHY/DIR)
prod or exp:   experiment — signal-evaluation research artifact, not a production/live
               path
existing data: model#90's Q1 result was stripped for citing an unauditable
               session-scratch path; this PR recomputes the SAME statistic
               (`d = REAL - persistence` on per-date rank IC, block_length 60, 1500
               bootstrap resamples, via `dependence_aware_mean`, model#89) against the
               retained bundle above, but the bundle predates model#90's merge by ~3h
               and reads unhashed mutable inputs, so it is exploratory, not a
               falsifiable post-freeze confirmatory record
               `[VERIFIED - recomputed 2026-07-29, ordering defect found on review]`
best-known?:   not confirmatory — see STATUS. The paired-difference numbers (prod XGB
               +0.0359 t +1.23 CI [+0.0218, +0.0787]; certified clf +0.0113 t +1.31 CI
               [+0.0049, +0.0275]; PatchTST -0.0488 t -2.31 CI [-0.0772, -0.0050]) and
               the raw-IC contrast (only prod XGB resolves; certified clf's absolute IC,
               largest block t of the three at +1.52, still crosses zero
               [-0.0287, +0.1749]) are exploratory only until re-run per NEXT
scope:         "this is /Users/renhao/renquant_bundles/corrected-eval-20260729/,
               experiment, EXPLORATORY (not confirmatory — predates model#90's merge,
               unhashed inputs) Q1 paired-difference vs each subject's own 60-day-lagged
               persistence baseline — vs raw-IC levels where only prod XGB resolves."
               No Sharpe or return claim is made.

NEXT:     Re-run the harness strictly AFTER model#90's merge (8579fa7), with the exact
          input parquet files (panel, prod-XGB scores, clf/PatchTST WF scores) and the
          code revision pinned and content-hashed INTO the bundle itself — not read from
          mutable RenQuant/scratch paths — before any confirmatory claim is made. Until
          then this stays exploratory. The clf's ABSOLUTE IC must not be quoted as
          established anywhere regardless of that re-run; its paired result may.
          PatchTST's closure still needs its own registered kill rule — model#87 is
          retracted and may not be reused as-is.

---

## Part 2 — closure re-run conflict — explained (estimand difference), pending adversarial review

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
