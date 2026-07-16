# G4 Phase 0 data audit: Phase A is BLOCKED on evidence volume, not schema

Date: 2026-07-16
Status: Phase 0 verdict — **BLOCKED**; champion unchanged (per design go/no-go
tree, doc/research/2026-07-12-ensemble-combination-experiment.md §5.3)
Sources: `runs.alpaca.db` read-only audit (`file:...?mode=ro&immutable=1`),
frozen manifest defaults (`experiment_manifest.py`), Phase A runner floors
(`phase_a_runner.py`).

## Bottom line

Phase A cannot run on current evidence and will not become runnable by
waiting a few weeks. The frozen v2-block-rebalance design requires **≥ 8
non-overlapping evaluation observations spaced 70 sessions apart
(block_length_days=60 + embargo_sessions=10) ≈ 560 admissible sessions with
BOTH experts admitted per-date**. The audited evidence base today:

| Evidence dimension | Audited value | Requirement | Gap |
|---|---|---|---|
| Distinct live-run dates in `pipeline_runs` | 64 (2026-04-22 → 2026-07-16) | ~560 | ~9x |
| Dates with in-bundle `trained_date` provenance | ~40 (2026-05-21 →) | ~560 | ~14x |
| XGB panel expert dates (`active_scorer=panel_ltr_xgboost`) | 15 | ~560 | ~37x |
| PatchTST expert dates (`hf_patchtst`) | **1** | ~560 | ~560x |
| PatchTST PIT parity evidence (§5.1 admission prereq) | none | required | blocked |

The binding constraint is the **second expert**: PatchTST has essentially no
persisted per-date score history (1 date) and no point-in-time parity ledger,
so even the schema fixes that merged today (pipeline#202, umbrella#482,
pin#483) cannot make it admissible retroactively.

## What the audit found (new facts)

1. **`run_bundle_json` carries reconstructable provenance since 2026-05-21.**
   `panel_contract.details.trained_date` is present in 896 rows across 4
   model vintages (2026-05-18: 490, 2026-06-21: 195, 2026-07-05: 34,
   2026-07-06: 177), and `artifact_hashes.*` binds each run to sha256 file
   digests of the exact panel/ngboost/calibration artifacts. Recent
   `candidate_scores` rows also stamp `panel_ltr_artifact` per row (12,105 of
   239,477 rows). The blanket "training_cutoff is MISSING everywhere"
   statement in `backfill_scores.py`'s docstring is therefore too strong for
   the 2026-05-21+ window: for those rows an honest reconstruction from
   durable in-bundle provenance is possible (reading recorded provenance is
   not fabrication). This is worth a `backfill_scores.py` enhancement PR, but
   it does NOT unblock Phase A — the XGB window is still ≤ 40 sessions and
   PatchTST is still absent.

2. **The DB history is structurally short.** `pipeline_runs` persistence
   begins 2026-04-22. No amount of metadata reconstruction extends the
   window backward past that date.

3. **60-session blocks are tied to the label contract.** The frozen
   `embargo_justification` ties the 10-session embargo to the 60-session
   block and the forward-return label horizon. Shrinking `block_length_days`
   to fit the available window would (a) change the estimand, (b) violate
   the pre-registered manifest, and (c) reintroduce forward-return overlap
   between blocks. It is not a free parameter; any change is a re-registration
   (new experiment version) requiring its own design review.

## Blocker chain (ordered)

1. **PatchTST per-date score persistence does not exist.** The shadow scorer
   runs (its artifact digest appears in run bundles under
   `shadow_models[0]`), but per-date shadow scores are not persisted to any
   queryable store (1 date in `candidate_scores`). Until a shadow-score
   persistence path ships and runs daily, the second expert accumulates zero
   admissible evidence. This is the first actionable unblock and it is
   umbrella/pipeline wiring, not model-repo work.
2. **PatchTST PIT parity ledger (§5.1) does not exist** — required for its
   admission as an expert independent of score volume.
3. **Forward accumulation at the frozen design needs ~560 admissible
   sessions (~2.2 years).** With #202/#482/#483 merged, forward evidence
   starts accumulating (for XGB) once the live machine syncs pins — but the
   frozen block design makes Phase A a 2027+ event on forward data alone.
4. **Decision required (design-level, not this memo):** either
   (a) accept the 2027 horizon, (b) re-register a shorter-horizon evaluation
   contract as a new experiment version through design review, or
   (c) scope a pseudo-OOS historical reconstruction (archived model vintages
   + point-in-time feature panel replay over 2024-2026). Option (c) is a
   multi-week research build with known leakage traps (fund-freshness
   serving axis) and requires its own design PR before any code.

## What this does NOT change

- The champion stays unchanged (design §5.3 BLOCKED branch).
- No Phase A comparison was run; no L1-vs-champion claim of any kind exists.
- The schema/wiring work merged today remains necessary for every future
  path — it is the forward-evidence foundation, just not sufficient.

## CORRECTION (2026-07-16, same day — verified against runs.alpaca_shadow.db)

The blocker-chain item ① above ("PatchTST per-date score persistence does
not exist") is **WRONG**. This audit only queried the PROD arm DB
(`data/runs.alpaca.db`). The daily shadow e2e (`daily_104.sh` Step 4, since
2026-05-19) runs the full pipeline a second time with the shadow scorer and
persists per-date scores to the isolated `data/runs.alpaca_shadow.db`
through the same runner/persistence path. Verified counts (read-only,
`mode=ro&immutable=1`, independently reproduced):

| Shadow DB evidence | Value |
|---|---|
| Distinct live-run dates | 40 (2026-05-19 → 2026-07-15) |
| `active_scorer=hf_patchtst` dates | **15** (2026-06-22 →, continuous per-session since 06-25) |
| `active_scorer=panel_ltr_xgboost` dates | 11 (pre-swap window) |

Corrected blocker chain:
1. ~~PatchTST per-date persistence wiring~~ — ALREADY EXISTS (shadow DB).
   The real gap was provenance: the shadow arm's panel artifact is a
   PatchTST `.pt` checkpoint (non-JSON), so the umbrella#482 JSON extraction
   yields NULL forever. FIXED by RenQuant#484 (active-scorer runtime
   metadata fallback, merged 2026-07-16).
2. PatchTST PIT parity ledger (§5.1) — still missing (unchanged).
3. Evidence volume vs the frozen ~560-session design — still the binding
   constraint (unchanged), but BOTH experts now accrue per-session forward
   (XGB in prod DB post pin-sync; PatchTST in shadow DB since 06-25).
4. Phase A tooling must read the SHADOW DB for the PatchTST expert —
   `backfill_scores.py` currently assumes a single DB (new work item).

The headline verdict (Phase A BLOCKED on evidence volume) is unchanged;
the actionable path is materially better than stated above.
