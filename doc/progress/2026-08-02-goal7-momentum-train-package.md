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
  existing data: the sealed v1 runner's `assemble_day`
                 (tools/goal7_momentum_run.py) is the only existing reference
                 construction for this score; golden test proves byte-for-byte
                 score identity against it on a synthetic fixture (8 names /
                 320 bdays, max |delta| = 0.0 over 6 scored names) AND a
                 real-data subset (60/144 live-universe names, panel date
                 2026-05-05, asof 2026-07-01, max |delta| = 0.0, 62 input
                 digests recorded) `[VERIFIED — measured 2026-08-02]`
  best-known?:   yes — the only implementation of design §1 TRAIN; nothing
                 else computes this artifact shape to compare against
  scope:         this is src/renquant_model_momentum (exp, training internals
                 only) vs the sealed v1 runner (tools/goal7_momentum_run.py) —
                 a golden-identity claim only (max |delta| = 0.0), not a new
                 IC/Sharpe number; no serving/scheduling/strategy-config
                 surface touched; live reads READ-ONLY (ohlcv parquets, panel
                 ticker/date columns, ticker_sectors.json); CLI writes only
                 under --out-root
  tests:         new file 33 passed (22 original + 11 added across this
                 codex-review fix pass: params-domain-violation ×9 — 7
                 parametrized out-of-domain cases + min_obs>window +
                 unsupported params_version — ledger-refusal-leaves-no-
                 artifact ×1, and ledger-integrity-refusal-clean-exit-5 ×1,
                 the latter also proving a transient refusal's retry
                 succeeds end-to-end once cleared); full suite 1464 passed,
                 0 failed `[VERIFIED — make test 2026-08-02, 61.78s]`;
                 pre-slice baseline 1431 `[DERIVED — 1464 − 33 new]`

NEXT: codex re-review of this commit's fixes (ledger write-ordering — atomic
  staging-file + rename after ledger success, so a ledger refusal never
  orphans an artifact; a `LedgerIntegrityError` now returns a clean
  `REFUSED-LEDGER` exit 5 distinct from an unexpected-exception path; v0
  param-domain validation, fail-closed for any non-"v0" params_version; and
  this progress doc). On APPROVED, this can merge — the #195 design gate is
  already satisfied (operator comment: #195 merged at `8124fd34`, empty
  reconciliation delta). Slice 3 (TEST/scoring harness) is next in the
  pipeline build order.

## Review round 1: the package worked only from a checkout

`params_v0()` sourced the six frozen constants by importing
`tools/goal7_momentum_run.py`. `[tool.setuptools.packages.find] where = ["src"]`,
so that file never enters the wheel: an installed consumer raised
`FileNotFoundError` at first use while every in-repo test passed. A package
surface that only works from the repo it was built in is not a package surface.

**Fixed by a packaged MIRROR, not by an inversion.** The obvious alternative —
make the package the single definition and have the v1 runner import it —
removes drift by construction and was rejected: `tools/goal7_momentum_run.py`
is the runner of a SPENT one-shot study whose result is published and sealed,
and editing it changes the bytes a published result was produced by, for the
convenience of a downstream package. The cost of a mirror is that two copies
can diverge; `test_params_v0_mirrors_the_sealed_v1_runner` pays it, holding
every mirrored constant equal to the sealed runner's own value wherever the
repo is present — which is CI. The sealed runner remains the authority; the
wheel just carries a copy it is held to.

| claim | value | provenance |
|---|---|---|
| the reviewer's repro now succeeds | `params_v0()` from a clean `--target` install returns all six constants | [VERIFIED — `pip wheel . --no-deps` → `pip install --target` → import, 2026-08-02] |
| module tests | 35 passed | [VERIFIED — `pytest -q tests/test_momentum_train_package.py`] |
| model suite | 1464 passed, 2 skipped | [VERIFIED — `pytest -q`] |
| the wheel-sufficiency test is load-bearing | restoring the pre-fix `train.py` turns it red | [VERIFIED — `git show HEAD:…` over the fix, re-run] |

One note on how that test is written. It does **not** grep `train.py` for the old
path — my first version did, and it failed on a docstring that merely *mentions*
`tools/`, which is checking prose rather than behaviour. It now copies the
package alone into a temp tree with no `tools/` above it and calls `params_v0()`
in a subprocess: the shape of an installed wheel, asserted by running.

## Review round 2: the ledger append was still ordered before the artifact rename

A HIGH finding on the round-1 fix (which introduced the staging-file + rename):
`tools/momentum_train_run.py` appended the ledger row, THEN renamed staging to
final. That reversed the earlier orphan but created the more authoritative
failure — if the rename fails after the ledger append succeeds (disk full,
permission, interruption), the append-only ledger permanently records the
cutoff/params_version with no artifact to match it, and a retry hits the
duplicate-row refusal with no repair path. The round-2 fix that followed
(distinguishing `LedgerIntegrityError` as a clean exit 5) addressed a different
finding and left this ordering unchanged.

**Fixed by reversing the order and adding startup reconciliation.** The
artifact is now finalized (staging write + atomic `Path.replace`) BEFORE the
ledger append is attempted. This makes the ONE recoverable failure mode a
finalized, content-sha-verified artifact with no ledger row — never the
reverse. On startup, `_reconcile_or_refuse` handles an existing artifact three
ways: (a) content-sha fails to verify → refuse, never reconcile; (b) a
matching ledger row already exists → refuse (`REFUSED-ARTIFACT-EXISTS`, the
common already-processed case); (c) no matching row → reconcile by appending
the row for the exact bytes on disk, never by re-training (so `trained_at_utc`
and every other field stay byte-identical across the reconciling retry).

| claim | value | provenance |
|---|---|---|
| finalize precedes ledger append | proven by a spy on `append_to_artifact_ledger` asserting the final-named artifact (and no `.tmp`) already exists at call time | `[VERIFIED — test_finalize_happens_before_ledger_append]` |
| a ledger-append failure leaves a reconcilable artifact, never an orphan | artifact present, `.tmp` absent, ledger empty after the failure; retry reconciles (rc 0) without re-training (content_sha256 unchanged) | `[VERIFIED — test_cli_ledger_refusal_leaves_a_reconcilable_artifact, test_cli_ledger_integrity_refusal_is_clean_exit_5]` |
| an already-ledgered cutoff still refuses (no double-reconcile) | second run on a fully-processed cutoff returns 4, ledger stays at 1 row | `[VERIFIED — test_cli_refuses_when_artifact_already_ledgered]` |
| a tampered on-disk artifact is refused, never reconciled | corrupted content_sha256 → exit 4, ledger stays empty | `[VERIFIED — test_cli_refuses_when_existing_artifact_fails_content_sha]` |
| module tests | 38 passed (35 prior + 3 net new — one prior test renamed to reflect the reversed ordering) | `[VERIFIED — pytest -q tests/test_momentum_train_package.py, 2026-08-02]` |
| model suite | 1469 passed, 0 failed (this machine has the live surfaces the round-1 fix's 2 skips depend on, so nothing skips here) | `[VERIFIED — pytest -q (== make test), 71.93s, 2026-08-02]` |

Scope: only `tools/momentum_train_run.py` (the CLI's two-file protocol) and its
tests changed this round — the round-1 packaged-mirror fix for `params_v0()`
(`src/renquant_model_momentum/_frozen_params_v0.py`, `train.py`) is untouched.
