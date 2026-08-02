# GOAL-7 pipeline slice 2: the TRAIN package (`renquant_model_momentum`)

STATUS: planned — built + fully tested, but DO-NOT-MERGE until the
architecture design PR #195 merges; this slice implements design commit
`2fb2447d488b9857dbbcb35d59d2f1caf12d6895` `[VERIFIED — read from
origin/goal7/momentum-pipeline-architecture at build time]` (review round 1;
any later design change is a visible reconciliation delta against that sha).

WHAT: design §1 (TRAIN) as code —
- `src/renquant_model_momentum/train.py`: `train_momentum_artifact(asof,
  universe, params, *, readers)` — pure core over an injected
  `MomentumReaders` protocol (tests need no disk). Computes the per-name
  rolling residual state (F1–F5, formation returns) and the per-date
  cross-sectional stats (per-feature n/mean/sd + used flag) the
  serving/scoring step needs; mechanism functions IMPORTED from
  `renquant_model_common.momentum_features` / `total_return`, never copied.
  `params_v0()` sources 252/21/200, min_features 3, names floor 50,
  min_side_obs 30 BY IMPORT from the sealed v1 runner's `FROZEN` /
  `MIN_SIDE_OBS` (model#164 §2 + model#177) and stamps
  `params_version: "v0"`.
- Artifact contract (gate-compatible per design §1): `kind:
  "momentum_residual_v0"`, self-carried `cutoff_date`,
  `effective_train_cutoff_date` (MEASURED from the pairs actually read, not
  asserted), `cutoff_embargo_days` (= the 21-bday skip; no label enters
  training), params + universe + per-input read digests + `content_sha256`;
  strict JSON (`allow_nan=False`), every list stays a list.
- `src/renquant_model_momentum/ledger.py`:
  `append_to_artifact_ledger(artifact, ledger_path)` — append-only JSONL,
  per-row digest chain (`prev_row_sha` + self `row_sha`), mirroring the Job B
  extension-manifest idiom; refuses tampered history, broken chains,
  duplicate (cutoff_date, params_version) rows, and artifacts whose
  content sha does not recompute. No rewrite API exists.
- `tools/momentum_train_run.py`: thin CLI (`--asof`, `--out-root` default
  `~/renquant-data-store/momentum-train/`, `--dry-run`) wiring real readers —
  live ohlcv/panel READ-ONLY with per-file sha256 recording. NO
  launchd/schedule wiring (slice 5, operator-gated).

WHY/DIR: the v1/v2 studies closed the one-shot question; the design's remedy
is a standing pipeline. TRAIN is the slice that makes every weekly artifact
self-identifying and dispute-answerable (digest recording, not pinning) and
WF-gate-compatible from day one, without touching serving or capital paths.

EVIDENCE:
  artifact:      src/renquant_model_momentum/{__init__,train,ledger}.py,
                 tools/momentum_train_run.py,
                 tests/test_momentum_train_package.py
  prod or exp:   exp — new package + CLI; nothing schedules it, nothing
                 consumes it yet (slices 3–5); zero touched serving surfaces
  golden:        synthetic fixture (8 names / 320 bdays): package scores vs
                 the sealed v1 `assemble_day` — max |delta| = 0.0 over 6
                 scored names `[VERIFIED — measured 2026-08-02]`; PLUS a
                 real-data golden (loud env-skip off-machine): 60-name subset
                 of the 144-name live universe (panel date 2026-05-05) at
                 asof 2026-07-01 — 60/60 scored on both sides, max |delta| =
                 0.0, 62 input digests recorded `[VERIFIED — measured
                 2026-08-02]`
  tests:         new file 22 passed; full suite 1453 passed, 0 failed
                 `[VERIFIED — make test 2026-08-02, 62.6s]`; pre-slice
                 baseline 1431 `[DERIVED — 1453 − 22 new]`
  live reads:    READ-ONLY (ohlcv parquets, panel ticker/date columns,
                 ticker_sectors.json); no git and no writes in the umbrella
                 tree; CLI writes only under --out-root
