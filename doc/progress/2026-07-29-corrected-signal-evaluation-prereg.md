# Progress: corrected signal-evaluation prereg (frozen)

STATUS:   prereg FROZEN, run not executed. Supersedes the measurement portions of
          model#86 and model#87.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-prereg.md`: three
          subjects (prod XGB, certified clf, PatchTST) under one design, on the
          142-name intersection, with every cross-lag and cross-arm comparison pinned
          to the common sample produced by `renquant_model_common.lag_alignment`
          (model#89). Three registered questions with conservative default branches,
          each decided by `dependence_aware_mean` (block-t + moving-block bootstrap
          + leave-one-block-out, `.resolves` requires all three to agree on sign) —
          not a bare single-statistic threshold. Q2's 7-lag selection carries a
          Bonferroni-corrected `ci_level` and a `block_length = max(60, L)` floor
          (the label's own 60d overlap never shortens just because a shorter lag
          is being tested); Q3 is a paired per-block contrast (one registered
          estimator/SE), not two independently-computed t-statistics.

WHY/DIR:  The prior harness computed cross-lag statistics on a drifting sample, so
          neither Stage 0's profile nor the closure verdict may be quoted. Re-running
          them under a corrected harness is a NEW test and needs its own registration
          rather than an amendment to a compromised one.

EVIDENCE:
artifact:      `doc/research/2026-07-29-corrected-signal-evaluation-prereg.md`
               (design only, this PR) + `src/renquant_model_common/lag_alignment.py`
               (model#89, MERGED 2026-07-29T08:39:02Z, commit 2151dfc), which
               formalizes the defect class named in T11/T12
               `[VERIFIED — this PR's diff + gh pr view 89]`
prod or exp:   design/experiment — no production artifact touched; no model
               performance claim is made by this PR
existing data: T11/T12's motivating investigation lived in session-local
               scratch and its specific numbers are not independently
               reproducible by a reviewer of this repo, so they are not
               quoted here (same standard applied on model#89 per codex
               HIGH). The general defect class (`Y.shift(-lag)` nulling
               newest rows; paired arms drawn from different score windows)
               is stated qualitatively in T11/T12 and does not depend on
               those specific numbers being verifiable
best-known?:   this corrected harness (common-sample T11 + common-arm-window T12,
               enforced by renquant_model_common.lag_alignment, model#89) is the
               best-known fix; the prior harness's Stage 0 (model#86) and closure
               (model#87) numbers stay withdrawn and may not be quoted
scope:         this PR registers a prereg design only — no model works/fails claim
               is made here, so the §4(b) sanity triad applies to the future
               results doc once this prereg is executed, not to this PR

NEXT:     model#89 is now MERGED (2151dfc, 2026-07-29T08:39:02Z), the primitive
          this design pins every comparison to (including `dependence_aware_mean`).
          The joint/multiplicity inference procedure is frozen in §2/§3: one
          estimator (`dependence_aware_mean`) for every decision, Bonferroni-
          corrected `ci_level` for Q2's 7-lag family, and a paired per-block
          contrast for Q3. Both preconditions this doc previously blocked on
          are now satisfied — the design is ready to run on the corrected
          primitive. Results are a separate PR against immutable inputs once
          execution is authorized; this PR carries the frozen design only.
          The prod XGB doubles as the positive control: if it lands UNRESOLVED,
          every verdict becomes UNRESOLVED, because a design that cannot
          detect the model that trades cannot speak about the others.
