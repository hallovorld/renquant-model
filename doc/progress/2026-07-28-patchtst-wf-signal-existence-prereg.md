# Progress: frozen prereg — PatchTST signal existence over the 43-fold WF corpus

STATUS:   prereg FROZEN (no evaluation run yet). Docs only.

WHAT:     Adds `doc/research/2026-07-28-patchtst-wf-signal-existence-prereg.md`:
          fold-level IC + decile-spread statistics over the 43-fold corpus
          (`wf-pt-b4e47e2c-batch1`), two placebo arms (120d shift matched to the WF
          gate + within-date shuffle), calibrated-vs-raw both computed, and a frozen
          three-way decision rule (GO third blend leg / KILL as alpha source /
          UNDERPOWERED) with ties resolving to UNDERPOWERED.

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

EVIDENCE: corpus 43/43 folds trained ($18.30 of the $25 cap, exact prereg quarantine
          signature) + 43/43 calibrators fitted locally; audited on disk as
          43 manifest retrains = 43 fold dirs = 43 `model.pt` = 43 calibration files.
          No IC/Sharpe claim is made in this PR — it freezes the test that will produce
          one, so the §4(b) sanity triad applies to the RESULTS doc, not here.

NEXT:     Run the frozen evaluation over the 43 folds (read-only, quarantined corpus,
          frozen input bundle root 8072ca77…), then a results doc carrying every arm
          with its matched placebo, and the verdict under the frozen rule.
