# Progress: frozen prereg — PatchTST signal existence over the 43-fold WF corpus

STATUS:   prereg FROZEN (no evaluation run yet; corpus exists but is not yet
          pinned to a stable, citable path — see RECONCILIATION below).
          Docs only.
          CORRECTION (visible, per long-term-agreements.md entry 10, not a
          silent overwrite): an earlier version of this doc claimed the
          43-fold corpus was already trained and quarantined under run-id
          `wf-pt-b4e47e2c-batch1`, "audited on disk as 43 manifest retrains
          = 43 fold dirs = 43 model.pt = 43 calibration files." At the time,
          no run by that name could be found in this repo's git history, so
          it was retracted as unlocatable.
          RECONCILIATION (this pass, per model#91's queued corpus-index
          evidence): that retraction was itself imprecise. model#91 commits
          a content-addressed index (`corpus_id: wf-pt-b4e47e2c-batch1`,
          recipe `b4e47e2c`, cutoffs 2023-10-02 → 2026-03-02, `{fold_dirs:
          43, model_pt: 43, calibration_json: 43}`, `failed_folds: []`,
          `budget_contract.max_total_usd = 25.0`) that matches the earlier
          claim's run-id, fold count, and $25 cap exactly `[VERIFIED —
          doc/research/evidence/2026-07-29-patchtst-43fold-corpus-index.json
          on the model#91 branch, read directly this session]`. The batch
          is real, quarantined in session scratch BY the governing dispatch
          design (not committed to any repo by design) — a git-history-only
          check finds nothing there, which is not the same as nonexistence.
          The corpus exists (root digest `b8aa2d99...`) but is still not at
          a stable, citable path this prereg's evaluation script can read
          from. The frozen dispatch plan was model#82 / backtesting#81-#82
          ($16.8 projected / $20 hard cap); separately, it has not itself
          been executed to 43/43.

WHAT:     Adds `doc/research/2026-07-28-patchtst-wf-signal-existence-prereg.md`:
          fold-level IC + decile-spread statistics over the 43-fold corpus
          (to be generated per model#82's frozen dispatch plan), three placebo arms
          (within-date shuffle, decision-weighted + 120d shift, descriptive-only +
          persistence-matched, veto), calibrated-vs-raw both computed, and a frozen
          three-way decision rule (GO third blend leg / KILL as alpha source /
          UNDERPOWERED) with ties resolving to UNDERPOWERED.
          Round 3 (codex HIGH): the `shift120` arm needs label dates past the
          panel's covered range for cutoffs near the end of the 43-fold span, so
          `df=42` can't be assumed for every fold. Added a frozen fold-eligibility
          rule (§2): a fold counts toward the `real − shift120` report iff its
          shifted window is fully within the panel's actual max date, checked
          programmatically at evaluation time — never hand-counted here.
          Round 4 (codex HIGH, this pass): T1 (documented in model#86) showed the
          `shift+120d` placebo lands near the score's own predictive peak
          (lag-100d IC = +0.078, t=3.21), making `real − shift120` structurally
          negative, not a null — so it could not remain the decision statistic.
          Retired `shift120` to a descriptive-only report; `t_d` (and GO/KILL/
          UNDERPOWERED) is now built from `real − within-date-shuffle` over the
          full 43 folds (`df=42`, no eligibility exclusion), matching model#86
          §3's independently-frozen null choice — no run of Stage 0 was needed to
          borrow this, only its already-frozen design. Also added the
          persistence-matched control as a third arm (veto), mirroring model#86
          §3.2/§5 exactly (same alignment/coverage/variance rules): GO cannot be
          declared if `real − persistence` is not positive at t ≥ 1.0, since that
          pattern is stale-score persistence, not fresh information.

WHY/DIR:  The single-window read is not decidable. Measured on the fresh serving fold
          (val 2025-05-20 → 2026-04-27, 235 dates, 33,370 rows) — a review round
          could not locate this file and flagged the claim as unverified pending
          re-measurement; found this session at
          `ptserve/2026-07-21/hf_patchtst_all_seed44_val_preds.parquet` in local
          scratch and the numbers below independently reproduced by loading the
          parquet and recomputing per-date Spearman IC directly `[VERIFIED —
          recomputed directly this session, not carried over]`: per-date rank IC +0.0430, naive t +5.39,
          but the 60-trading-day label overlap leaves n_eff ≈ 4, so the block-adjusted
          t is **+0.70** — +0.043 and 0.00 are not separable. The within-date shuffle
          placebo is clean (−0.0008 over 5 seeds), so this is a POWER problem, not a
          cross-sectional artefact. The live funnel independently showed calibrated
          conviction ≈ 0.50 (IQR 0.011) and sized to zero — the expected behaviour of
          an unresolvable signal, not proof of its absence. The 43 folds exist
          precisely to convert one window into 43, which is the properly-powered
          diagnostic `doc/memory/mid-term/model-edge.md` requires before closing or
          switching architecture.

EVIDENCE: artifact:      `hf_patchtst_all_seed44_val_preds.parquet`, found at
          `ptserve/2026-07-21/` in local scratch (single serving fold, val
          2025-05-20 → 2026-04-27, 235 dates × 142 tickers, 33,370 rows)
          `[VERIFIED — recomputed directly from the parquet's own pred/label
          columns this session, exact match to all figures below]`; the
          43-fold corpus itself EXISTS (`corpus_id: wf-pt-b4e47e2c-batch1`,
          43/43 fold_dirs/model_pt/calibration_json, root digest
          `b8aa2d99...`) per model#91's content-addressed index `[VERIFIED —
          doc/research/evidence/2026-07-29-patchtst-43fold-corpus-index.json
          on the model#91 branch, read directly this session]`, but is
          quarantined in session scratch and not yet pinned to a stable,
          citable path this evaluation script can read from.
           prod or exp:   experiment (prereg only — the 43-fold corpus
          exists but is not yet pinned to a committed path, and the frozen
          43-fold evaluation has not run; this PR adds no model/data claim
          beyond the single-fold motivating measurement above).
           existing data: single serving fold — per-date rank IC +0.0430,
          naive t +5.39, block-adjusted t (60-trading-day label overlap,
          n_eff ≈ 4) +0.70, within-date shuffle placebo (5 seeds) −0.0008,
          real − placebo +0.0438; live funnel independently showed
          calibrated conviction ≈ 0.50 (IQR 0.011), sized to zero.
           best-known?:   n/a — no IC/Sharpe number is claimed for the
          43-fold corpus yet; this PR freezes the test design (including
          the KILL threshold `d_min = 0.01`, see the research doc) that
          will produce one.
           scope:         "this is a frozen prereg document (test design +
          decision rule), not a model/IC/Sharpe result — the §4(b) sanity
          triad applies to the RESULTS doc that follows the evaluation
          run, not to this PR."

NEXT:     Pin the quarantined corpus (`wf-pt-b4e47e2c-batch1`, root digest
          `b8aa2d99...` per model#91) to a stable, citable path — an
          ephemeral session-scratch location is not itself a valid prereg
          input, per model#87's same requirement. Then run the frozen
          evaluation over the 43 folds (read-only, frozen input bundle root
          8072ca77…), and produce a results doc carrying every arm with its
          matched placebo and the verdict under the frozen rule.
