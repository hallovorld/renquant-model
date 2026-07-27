# AMENDMENT 1 — G4 XGB rerun batch (voids batch 1; freezes the PROVEN matrix)

**Amends** `2026-07-27-g4-xgb-rerun-prereg.md` (merged model#78). Unamended
sections stand verbatim: seeds {101–105}, the §4 frozen revision table, the
§2 bidirectional cover rule, §5 abort-and-void, §6 PatchTST gating, §7
non-goals. **Frozen on merge; nothing launches before.**

## 0. Batch-1 VOID declaration (honest record)

Batch 1 launched 2026-07-27 08:53Z after the #78 freeze and was stopped at
bar 1 of seed 101 by the leakage guard: the frozen `--strategy-config-name
strategy_config.json` is the DAILY-TRADING profile — `walkforward` never
engages (and its `manifest_path` names a nonexistent file), so the
SimAdapter legacy-loaded the 2026 production scorer into a 2024 window and
the guard refused. Zero provenance, zero DB rows, zero evidence produced;
nothing was salvaged. Root cause: the author froze an invocation that had
never been executed end-to-end. Three further latent defects were found
while repairing (all would have voided later batches): the static
`sim_baseline` profile predates the 2026-05-21 QP contract and fails it;
the 39-fold `walkforward_manifest.json` has no eligible fold before
~2024-03-25 (fail-closed by design); a fresh worktree lacks four groups of
untracked/uncommitted inputs (below). **Process rule added by this
amendment: no invocation may be frozen without a completed end-to-end smoke
on the exact environment (§3).**

## 1. Amended §2 rows (everything else in §2 stands)

| item | frozen value |
|---|---|
| config derivation (NEW, per-batch step 0) | derive the prod-semantic WF config with the gate's own builder: `build_wf_config_from_prod(prod_config=<worktree runtime strategy-104 configs/strategy_config.json @5c3eae9d>, manifest_path='artifacts/sim/walkforward_manifest_gbdt_prod_recipe_v2.calibrated.json', strategy_dir=<WT>/backtesting/renquant_104)` → written to `artifacts/diagnostics/wf_eval_configs/strategy_config.sim_g4rerun_prod_semantic.json`; its sha256 recorded in the batch report. This is the SAME mechanism the continuously-verified weekly WF gate uses (`--derive-config-from-prod`); it inherits the QP-satisfying prod ranking block, engages the 43-fold calibrated manifest (start-eligible from 2023-12-26), and strips `shadow_models` (builder-documented, no trade-decision effect) |
| per-seed invocation | `python -m renquant_backtesting.wf_gate.sim_driver --repo-root <WT> --strategy-config-name artifacts/diagnostics/wf_eval_configs/strategy_config.sim_g4rerun_prod_semantic.json --start 2024-01-02 --end 2026-03-28 --no-compare --seed <S> --sim-db-path data/sim_runs_seed<S>.db --skip-preflight` (env: worktree-runtime PYTHONPATH, `RENQUANT_REPO_ROOT=<WT>`, cwd `<WT>`) |
| single authority leg | `--no-compare` (driver-native; supersedes the `--compare-to` same-name mechanism of the original §2 — same effect, explicit flag). One `run_backtest` ⇒ one `sim_run_id` ⇒ one DB ⇒ one ledger |
| post-steps per seed (NEW) | (a) `python -m renquant_backtesting.analysis.backfill_forward_returns --repo-root <WT> --db data/sim_runs_seed<S>.db --source sim` — without it admissibility is 0/N ("no realized labels"); (b) model#65 converter with `--provenance-ledger <that seed's JSONL> --manifest-file <the 43-fold manifest> --expert-name xgb --score-column raw_panel` over the full window |
| per-seed validity tripwires (NEW) | `SimAdapter init: models=N>0` and `score_distribution>0` — the stale-models failure mode exits 0 with an EMPTY universe; an empty leg is VOID and, being an environment defect, batch-voids per §5 |
| wall-clock (measured, supersedes the ~3 h estimate) | ~24 min/leg measured at 2.4 s/bar × ≈562 bars + 72 s init; budget 45 min/leg; 5 seeds sequential ≈ 2–4 h local CPU |

## 2. Amended §4 additions — environment provisioning (hard precondition)

A fresh worktree assembled from git alone CANNOT run this sim: four input
groups are untracked or exist only as uncommitted live-tree state. Frozen
provisioning (copy live tree → worktree, same relpaths; per-file manifests
with size/mtime/sha256 archived with the batch report):

1. `data/ohlcv/` (~250 MB, 2788 files) — the full price store; the smoke
   proved the self-fetched fallback covers only ~1 year and yields 0 bars.
   Launch while the store is fresh relative to the last close, or re-copy
   after the daily fetch (a stale store triggers a slow, abortable
   yfinance refetch at init).
2. `backtesting/renquant_104/artifacts/walkforward_gbdt_prod_recipe_v2/` +
   `artifacts/sim/walkforward_calibrators/` — the M6 RE-STAMPED fold
   calibrators, which exist ONLY as uncommitted live-tree modifications;
   the git-committed versions pin a scorer fingerprint the fold scorers no
   longer advertise (loud ValueError). The copy manifests ARE the
   provenance for this uncommitted state.
3. `backtesting/renquant_104/models/<ticker>/` for the watchlist
   (~1.2 GB; 141/145 exist; CRWV/RKLB/SPCX/SPY have no model and never
   enter the universe) — git HEAD models are the stale April snapshot and
   the staleness gate silently EMPTIES the universe (exit 0, 0 candidates;
   the §1 tripwire exists precisely for this).
4. `data/sec_fundamentals_daily.parquet` + `data/earnings_surprise/` +
   `data/news_sentiment_alpaca/` (~48 MB) — absent ⇒ fail-closed
   `panel_fundamentals_missing`, zero buys.

Reads from the live tree are copy-only (cp), never git, never writes; the
displaced worktree originals are preserved in the scratchpad.

## 3. The completed end-to-end smoke (the §0 process rule, satisfied)

Executed 2026-07-27 ~09:23Z in the exact assembled worktree, seed 999
(non-batch seed), window 2024-01-02→2024-01-16, the §1 invocation verbatim:
10 bars, models=121, WF folds engaged (cutoffs 2023-10-02 ×9 / 2023-10-23
×1, `is_real_content_digest: true`, revision pins recorded);
`score_distribution=1160`; ledger = 10 `fold_resolved` + 10
`score_committed`, all `persisted: true`, `pit_violation: false`, non-null
watermarks; the 10 `score_observation_key` tuples exactly cover the DB
(§2 rule PASS); converter end-to-end: 0 provenance rejects, cross-checks
pass, and after the backfill post-step **10/10 admitted**, outputs stamped
`classification: EXPLORATORY_ONLY` with ledger-verbatim identity fields.
Smoke artifacts are quarantined as NON-EVIDENCE (seed 999 is outside the
frozen set; its DB/ledger/outputs are excluded from the corpus and
retained only as the smoke record).

## 4. Notes binding future readers

- The manifest is schema v1 (no `artifact_sha256`): loader warnings today,
  fail-closed after 2026-09-01 — irrelevant to this batch, relevant to any
  batch after that date.
- The frozen converter revision 9b4970cb remains valid: model origin/main
  has advanced but `experiments/ensemble_phase0/` is byte-identical
  (verified during the smoke).
- Nothing in this amendment changes any disposition boundary: outputs stay
  `EXPLORATORY_ONLY`; GO/KILL of G4 remains with the v4 registered
  machinery; Phase 0's dual-expert evidence-volume prerequisite remains
  BLOCKED pending the PatchTST decision (§6 of the base document).
