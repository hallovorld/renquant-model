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
| config (FROZEN CONTENT, not launch-generated) | the prod-semantic WF config derived DURING THE SMOKE with the gate's own builder (`build_wf_config_from_prod`, the weekly gate's `--derive-config-from-prod` mechanism: QP-strict prod ranking block inherited, 43-fold calibrated manifest engaged, `shadow_models` stripped) is itself part of the frozen input bundle (§2) at `backtesting/renquant_104/artifacts/diagnostics/wf_eval_configs/strategy_config.sim_g4rerun_prod_semantic.json`; the launch consumes the bundle copy verbatim — nothing is generated at launch time |
| per-seed invocation | `python -m renquant_backtesting.wf_gate.sim_driver --repo-root <WT> --strategy-config-name artifacts/diagnostics/wf_eval_configs/strategy_config.sim_g4rerun_prod_semantic.json --start 2024-01-02 --end 2026-03-28 --no-compare --seed <S> --sim-db-path data/sim_runs_seed<S>.db --input-bundle <bundle> --input-bundle-root 8072ca77…aea1 --input-bundle-covered-root <each of the six frozen roots> --skip-preflight` (env: worktree-runtime PYTHONPATH, `RENQUANT_REPO_ROOT=<WT>`, offline proxy per §2, cwd `<WT>`) |
| single authority leg | `--no-compare` (driver-native; supersedes the `--compare-to` same-name mechanism of the original §2 — same effect, explicit flag). One `run_backtest` ⇒ one `sim_run_id` ⇒ one DB ⇒ one ledger |
| post-steps per seed (NEW) | (a) `python -m renquant_backtesting.analysis.backfill_forward_returns --repo-root <WT> --db data/sim_runs_seed<S>.db --source sim` — without it admissibility is 0/N ("no realized labels"); (b) model#65 converter with `--provenance-ledger <that seed's JSONL> --manifest-file <the 43-fold manifest> --expert-name xgb --score-column raw_panel` over the full window |
| per-seed validity tripwires (NEW) | `SimAdapter init: models=N>0` and `score_distribution>0` — the stale-models failure mode exits 0 with an EMPTY universe; an empty leg is VOID and, being an environment defect, batch-voids per §5 |
| wall-clock (measured, supersedes the ~3 h estimate) | ~24 min/leg measured at 2.4 s/bar × ≈562 bars + 72 s init; budget 45 min/leg; 5 seeds sequential ≈ 2–4 h local CPU |

## 2. Amended §4 additions — the FROZEN INPUT BUNDLE (content-addressed,
## immutable, verified before seed 101)

A fresh worktree assembled from git alone CANNOT run this sim: four input
groups are untracked or exist only as uncommitted live-tree state. Per the
round-1 review, these are frozen NOW, pre-merge, as an immutable
content-addressed bundle built from the SMOKE-PROVEN worktree snapshot
(never re-copied from the mutable live tree):

- **Bundle location:** `/Users/renhao/renquant_bundles/g4-rerun-inputs-20260727/`
  (read-only, `chmod -R a-w`), 4,429 input files, ~1.6 GB. (The round-2
  manifest superseded the round-1 one: the pinned checker itself caught a
  build artifact — a since-deleted `MANIFEST.sha256.tmp` listed in the
  round-1 manifest — proving the checker rejects manifest/file-set drift.)
- **Manifest:** `MANIFEST.sha256` inside the bundle — one line per file:
  `sha256  size  relpath` — committed VERBATIM in this PR at
  `doc/research/evidence/2026-07-27-g4-rerun-input-bundle.MANIFEST.sha256`.
- **Frozen root digest** (sha256 of the manifest file itself):
  `8072ca771d0cab732687efdbca929dbacae34a0b72cb26ad423ccac6ade8aea1`
- **The load-bearing guard lives WITH the driver (round-3 ruling) and is
  enforced THROUGH the launched command:**
  `renquant_backtesting.wf_gate.input_bundle_guard` at the frozen
  backtesting revision `1bb24559` (backtesting#79, codex-approved). The
  §1 invocation carries `--input-bundle <bundle> --input-bundle-root
  8072ca771d0cab732687efdbca929dbacae34a0b72cb26ad423ccac6ade8aea1` plus
  the six frozen `--input-bundle-covered-root` values (`data/ohlcv`,
  `data/earnings_surprise`, `data/news_sentiment_alpaca`,
  `backtesting/renquant_104/artifacts/walkforward_gbdt_prod_recipe_v2`,
  `backtesting/renquant_104/artifacts/sim/walkforward_calibrators`,
  `backtesting/renquant_104/models`); the DRIVER runs the guard before
  any config/data loading (mismatch ⇒ exit 4, `run_backtest` never
  reached) and again after the sim and all outputs (mismatch ⇒ exit 6,
  execution-time input mutation ⇒ batch VOID). Covered roots are
  EXPLICIT, caller-frozen values: the bundle-derived variant was
  field-falsified (735 false VOIDs — a root-level singleton claimed all
  of `data/`, flagging the sim's own outputs). The wrapper additionally
  runs the standalone guard CLI once pre-batch and persists all captured
  verdicts (`logs/verify_preflight.txt`, per-seed grep of the driver's
  `INPUT BUNDLE ...` lines) in the batch archive. The model-repo file
  `doc/research/evidence/2026-07-27-verify_g4_input_bundle.py` remains as
  REFERENCE/evidence only — it is no longer the enforced guard.
- **Offline enforcement (no refresh escape hatch):** the batch runs with
  `HTTP_PROXY=HTTPS_PROXY=ALL_PROXY=http://127.0.0.1:9` (unroutable) so
  NO network fetch can succeed: if the frozen OHLCV store is deemed fresh
  by the kernel's rule, zero network is attempted; if it is deemed stale,
  the refetch fails immediately and the sim aborts BEFORE scoring —
  either way no unfrozen data can enter. The former "re-copy after the
  daily fetch" language is REMOVED; a batch whose store goes stale is
  re-frozen via a new amendment, never refreshed in place.
  `revision_pins` still attest the CODE; the bundle manifest attests the
  DATA/ARTIFACT inputs, closing the uncommitted-live-state gap.

The bundle covers (original live→worktree copy manifests retained in the
batch archive as staging evidence only — the bundle is the sole
authoritative source):

1. `data/ohlcv/` (~250 MB, 2788 files) — the full price store; the smoke
   proved the self-fetched fallback covers only ~1 year and yields 0 bars.
   Under the offline enforcement above, a store deemed stale at init
   aborts the batch before scoring; there is NO in-place refresh path.
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

The live tree was read (cp) exactly once, during the smoke's staging; from
this amendment on, ONLY the bundle is consumed. Displaced worktree
originals are preserved in the scratchpad.

## 3. The completed end-to-end smokes (the §0 process rule, satisfied)

TWO smokes, both seed 999 (non-batch), both quarantined as NON-EVIDENCE.

**Smoke B — the ENFORCED command (round-3 requirement: the prior smoke
cannot prove an enforcement path added after it ran):** executed 2026-07-27
~11:52Z on the re-assembled worktree (backtesting at `1bb24559`), the §1
invocation verbatim including the guard flags and the offline proxy:
`INPUT BUNDLE PREFLIGHT OK: root=8072ca77…aea1` → 10 bars, models=121,
walkforward engaged → `INPUT BUNDLE POST-RUN OK: root=8072ca77…aea1`,
exit 0, final value byte-identical to Smoke A ($100,036 — deterministic
replay under the frozen seed). The §1 post-steps then ran on the Smoke-B
DB/ledger (`sim_runs_smoke999b.db` +
`wf_provenance/wfsim-20260727T115215Z-87eca98a.jsonl`, 20 records =
10 `fold_resolved` + 10 `score_committed`) with the frozen bundle and the
pinned backtesting revision: forward-return backfill wrote 1,170 rows;
the model#65 converter at the frozen revision `9b4970cb` (git-archive
export) reported **0 provenance rejects, exact ledger↔DB cover, 10/10
admitted** (`DONE: expert=xgb wrote=10 rejected=0 (no_provenance=0)
admitted=10`; canonical admissibility-ledger fingerprint
`sha256:7eff7427c989e3da…bc69`). The full Smoke-B chain exits cleanly
end-to-end; its outputs are archived with the smoke record and
quarantined as NON-EVIDENCE.

**Smoke A — the original chain proof:** executed 2026-07-27 ~09:23Z, seed 999
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
