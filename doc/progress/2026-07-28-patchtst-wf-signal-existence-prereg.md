# Progress: frozen prereg — PatchTST signal existence over the 43-fold WF corpus

STATUS:   prereg FROZEN (no evaluation run yet; corpus not yet generated either —
          see CORRECTION below). Docs only.
          CORRECTION (visible, per long-term-agreements.md entry 10, not a
          silent overwrite): an earlier version of this doc claimed the
          43-fold corpus was already trained and quarantined under run-id
          `wf-pt-b4e47e2c-batch1`, "audited on disk as 43 manifest retrains
          = 43 fold dirs = 43 model.pt = 43 calibration files." That does
          not check out — no such run exists in this repo's history or on
          disk; only a 1-fold staged smoke test under this recipe has run.
          Retracted, not restated. The frozen dispatch plan is model#82 /
          backtesting#81-#82 ($16.8 projected / $20 hard cap); it has not
          been executed.

WHAT:     Adds `doc/research/2026-07-28-patchtst-wf-signal-existence-prereg.md`:
          fold-level IC + decile-spread statistics over the 43-fold corpus
          (to be generated per model#82's frozen dispatch plan), two placebo arms
          (120d shift matched to the WF gate + within-date shuffle), calibrated-vs-raw
          both computed, and a frozen three-way decision rule (GO third blend leg /
          KILL as alpha source / UNDERPOWERED) with ties resolving to UNDERPOWERED.

WHY/DIR:  The single-window read is not decidable. Measured on the fresh serving fold
          (val 2025-05-20 → 2026-04-27, 235 dates, 33,370 rows)
          `[VERIFIED — direct parquet read]`: per-date rank IC +0.0430, naive t +5.39,
          but the 60-trading-day label overlap leaves n_eff ≈ 4, so the block-adjusted
          t is **+0.70** — +0.043 and 0.00 are not separable. The within-date shuffle
          placebo is clean (−0.0008 over 5 seeds), so this is a POWER problem, not a
          cross-sectional artefact. The live funnel independently showed calibrated
          conviction ≈ 0.50 (IQR 0.011) and sized to zero — the expected behaviour of
          an unresolvable signal, not proof of its absence. The 43 folds exist
          precisely to convert one window into 43, which is the properly-powered
          diagnostic `doc/memory/mid-term/model-edge.md` requires before closing or
          switching architecture.

EVIDENCE: artifact:      `hf_patchtst_all_seed44_val_preds.parquet` (single serving
          fold, val 2025-05-20 → 2026-04-27, 235 dates × ~142 tickers, 33,370
          rows) `[VERIFIED — direct parquet read]`; the 43-fold corpus itself
          is NOT YET GENERATED — model#82's frozen dispatch plan
          (43 folds, $16.8 projected / $20 cap) has a proven 1-fold smoke
          test (`wf-pt-b4e47e2c-20260727T195313Z`) but the remaining 42
          folds have not been dispatched.
           prod or exp:   experiment (prereg only — neither the corpus nor the
          frozen 43-fold evaluation exist yet; this PR adds no model/data
          claim beyond the single-fold motivating measurement above).
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

NEXT:     Run the frozen evaluation over the 43 folds (read-only, quarantined corpus,
          frozen input bundle root 8072ca77…), then a results doc carrying every arm
          with its matched placebo, and the verdict under the frozen rule.
