# GOAL-6 Job B: gbdt WF depth-extension tool — built; golden parity FAILED (input vintage), batch gated off

(PR #185 — `goal6/jobb-gbdt-depth-tool`, fixed by claude)

STATUS:   delivered. Driver + golden gate + `--accept-vintage-seam` mode are
          landed and tested; the 82-window batch itself is deliberately NOT
          run — see NEXT.

WHAT:     Adds `tools/wf_gbdt_depth_extension.py`, the GOAL-6 Job B driver
          that extends the production gbdt WF lineage backward (82 windows,
          2019-01-14 .. 2023-09-11) behind a golden-parity gate
          (`require_golden_pass`), plus a `--accept-vintage-seam` mode that
          admits the batch only when the golden has FAILED and records the
          seam as first-class provenance in the extension manifest.

WHY/DIR:  GOAL-6 workstream (WF corpus depth). The mandated golden
          reproduction of the earliest existing window FAILED prediction
          parity because `data/sec_fundamentals_daily.parquet` was rebuilt
          2026-08-01 with revised historical values — an input-vintage fact,
          not a recipe bug (see "Golden verdict — localization" below). Per
          the operator decision recorded 2026-08-02, regenerating the
          existing 43-window ladder on the new vintage was rejected (it would
          break the WF manifest's stamped artifact ties); `--accept-vintage-
          seam` gives Job B a lawful path to extend the ladder without doing
          that, by making the vintage drift explicit in the manifest instead
          of silent.

EVIDENCE: artifact:      `doc/research/data/2026-08-02-jobb-gbdt-depth-extension/
                         {golden_report.json, extension_plan.json}` (this PR).
  prod or exp:           EXPERIMENT tooling; read-only over RenQuant/production
                         paths (`sys.dont_write_bytecode` before any umbrella
                         import; `--out-dir` refuses to resolve inside the
                         umbrella). No production data/config/artifact written.
  existing data:         Golden reproduction against the earliest existing WF
                         window: max|Δ| = 0.6489841341972351 (target < 1e-6)
                         over 4380 OOS rows / 15 dates
                         `[VERIFIED — golden_report.json]`; localized to the 5
                         fundamental columns' robust-z refit
                         (`gross_profitability` median Δ = 7.13e-3,
                         `book_to_price` scale Δ = 9.45e-3) after
                         `data/sec_fundamentals_daily.parquet` was rebuilt
                         2026-08-01.
  best-known?:           N/A — no IC/Sharpe/effect-size number is asserted;
                         this is a tooling/gate-correctness delivery, not a
                         research result.
  scope:                 `renquant-model` tooling only. 82-window batch
                         computed as a plan (`extension_plan.json`) but NOT
                         executed; full suite 1334 passed (29 new in
                         `tests/test_wf_gbdt_depth_extension.py`, baseline
                         1305).

NEXT:     Launch the 82-window batch with
          `wf_gbdt_depth_extension.py --accept-vintage-seam`
          (~19 min measured upper bound) — a single command, not run in this
          PR per instruction. Both admission paths (no-flag refusal against
          the real failed golden; seam-mode admission) are verified, the
          former end-to-end, the latter by unit test; the actual 82-fit
          training run is deferred to a follow-up.

---

**Bottom line:** the Job B driver (`tools/wf_gbdt_depth_extension.py`) is built and
verified on its pure surface, the backward ladder is computed (**82 new windows,
2019-01-14 .. 2023-09-11**, 21-calendar-day grid), but the mandated golden
reproduction of the earliest existing window **FAILED prediction parity:
max|Δ| = 0.6489841341972351** (target < 1e-6) over 4380 OOS rows / 15 dates
`[VERIFIED: doc/research/data/2026-08-02-jobb-gbdt-depth-extension/golden_report.json]`.
Per the Job B spec this is reported without rationalization and the batch was NOT
launched; the tool hard-refuses batch mode until a passed golden exists — OR, per
the operator decision below, until the seam is declared explicitly.

**DECISION (operator, 2026-08-02): DOCUMENT THE VINTAGE SEAM — do NOT regenerate
the 43-window ladder.** Rationale (recorded verbatim in the tool and the seam
block): the production lineage stamps bind the ACTUAL artifacts in the WF
manifest; regenerating them on the Aug vintage would break that tie and create a
third parallel corpus. The whole ladder is already retrospective (built
June-July 2026 for 2023-2026 cutoffs), so extending on the current vintage with
the seam recorded is methodologically the same object — the seam makes the
June-vs-Aug input drift first-class instead of silent. Implemented as
`--accept-vintage-seam` (see "Vintage-seam mode" below); without the flag the
golden-pass gate is unchanged.

## Golden verdict — localization (measured, not assumed)

Reproduction path is byte-faithful in everything the current inputs still permit:

| check | result |
| --- | --- |
| training slice (rows/tickers/dates) | 526515 / 292 / 1890 — EXACT match |
| sentiment-gate zeroed rows | 366713 — EXACT match (regime replay reproduced) |
| effective_train_cutoff_date | match (2023-07-10) |
| config_fingerprint | match (sha256:f8fb2259b2bf1537, from the strategy-104 subrepo config) |
| 158 global_z norm constants vs today's stats file | max drift 1.8e-9 (float noise) |
| in-sample train IC | +0.1365 vs reference +0.1389 |
| booster bytes | DIFFER → prediction max\|Δ\| = 0.649 |

The divergence localizes to the 5 fundamental columns' robust-z refit:
`data/sec_fundamentals_daily.parquet` was rebuilt **2026-08-01** (panel + stats
files same day) with revised historical values. Measured drift on the golden
train slice: `gross_profitability` median Δ = 7.13e-3 — exactly the
`feature_means_max_abs_delta` in the report; `book_to_price` robust scale
Δ = 9.45e-3 — exactly the `feature_stds_max_abs_delta`. One alpha raw-clip
bound also changed. Different training matrix ⇒ different booster. This is an
input-vintage fact, not a recipe/path divergence.

## What was built

* `tools/wf_gbdt_depth_extension.py` — Job B driver, mirroring the Job A shape
  (`wf_clf_corpus_rebuild_persist.py`): read-only over RenQuant
  (`sys.dont_write_bytecode` set before any umbrella import), recipe imported
  live from `renquant_model_gbdt` (LoadPanelTask → sentiment training gate →
  BuildNormalizationTask → TrainBoosterTask → BuildArtifactTask → fingerprint →
  smoke — the exact `renquant_orchestrator.train_gbdt` sequence the manifest
  names as trainer, with `skip_cv` per the manifest options), params
  ARTIFACT-CARRIED (earliest window's `params` + `best_iter`) and
  cross-asserted equal to `PANEL_LTR_PARAMS` / `DEFAULT_N_ROUNDS`.
* Ladder convention DERIVED from the manifest, not invented: all 42 gaps are
  exactly 21 calendar days, all cutoffs Mondays, and 2023-12-25 (NYSE holiday)
  is a cutoff ⇒ pure arithmetic grid, no holiday adjustment; OOS windows are
  panel trading dates in `(cut, next_cut]`.
* Per-window artifacts mirror the existing windows KEY-FOR-KEY with exact-type
  parity (`check_artifact_field_parity`, incl. the stringified-norm_kind
  incident guard) and must share the existing ladder's recipe fingerprint
  (recipe_match.py mirror) or the window refuses.
* Extension lineage manifest under the #94 append-only rule: new ordered sha
  list (new windows chronologically BEFORE the existing 43), new
  `lineage_root_sha`, old root recorded and recomputable from the suffix;
  `recipe_id` = the lineage lane's recipe fingerprint rule.
* Structural refusals mirrored from backtesting `lineage_lane`: duplicate /
  unordered ladders, artifact-vs-manifest cutoff mismatch, missing artifacts.
* `--out-dir` refuses to resolve inside the umbrella; every input is
  digest-recorded at read time (panel, stats, fundamentals, WF manifest,
  strategy config, SPY OHLCV, GMM artifact).
* Batch gate: `require_golden_pass` — the full batch refuses to train without
  a PASSED `golden_report.json` (added after the measured failure above).

## Config source (measured 2026-08-02)

The strategy-104 SUBREPO config reproduces the June artifacts'
`config_fingerprint` (sha256:f8fb2259b2bf1537) and `config_fingerprint_fields`
byte-exactly; the umbrella copy has drifted (sha256:14586756d4f67691 today).
Every regime key the replay tasks consume was measured equal in both; the
effective sentiment policy matches the artifact-carried policy, and the tool
hard-asserts the produced gate contract against the reference window.

## Numbers

* Ladder: 82 new windows, earliest 2019-01-14, latest 2023-09-11 (panel min
  2016-01-04 — reaches past 2019, no truncation; min-train-dates floor 250
  never binds) `[VERIFIED: extension_plan.json]`.
* Golden fit wall time: **6.7 s** fit, 14.0 s total per window (panel load
  0.4 s cached, regime replay 6.5 s). Implied batch: ≤ 82 × 14 s ≈ **19 min**
  upper bound (backward windows train on strictly less data); ~21–30 min for
  the spec's 90–130-fit range.
* Tests: new file **37 passed**; full suite **1342 passed** (was 1305 before
  this branch).

## Vintage-seam mode (`--accept-vintage-seam`, implements the decision above)

Batch admission has exactly two lawful states (`resolve_vintage_seam`):

* **no flag** — the golden must have PASSED (`require_golden_pass`, unchanged);
* **flag** — the golden must exist and have FAILED: the failed
  `golden_report.json` IS the seam's measured evidence and is referenced from
  the seam block. A PASSED golden under the flag REFUSES (no seam exists — the
  flag would document a lie). A missing golden under the flag REFUSES.

When admitted under the flag, the extension lineage manifest additionally
carries a `vintage_seam` block (`build_vintage_seam`) with these fields:
`input_vintage` ("2026-08-01-rebuild"), `decision`, `decision_rationale`,
`evidence_golden_report` + `evidence_golden_report_sha256` (path + content sha
of the exact evidence bytes; review round 1), `golden_parity_max_abs_delta`
(0.649, carried FROM
the report), `drift` (the report's `feature_means_max_abs_delta` 7.13e-3 →
gross_profitability robust-z median, `feature_stds_max_abs_delta` 9.45e-3 →
book_to_price robust-z scale, global_z max drift 1.8e-9, localization note),
`rebuilt_inputs` (sec_fundamentals_daily.parquet + panel + stats, each with its
CURRENT read-time sha256 and measured mtime date), `rebuild_date_measured`
(2026-08-01), and `non_reproducibility` (the June-vintage bytes no longer exist
on disk; the existing 43 windows are NOT byte-reproducible from current
inputs). Every NEW window row is additionally stamped
`input_vintage: "2026-08-01-rebuild"` so no consumer can pool across the seam
without seeing it. Both roots are kept as before: `old_lineage_root_sha` (over
the existing 43) and `new_lineage_root_sha` (full extended ladder), old root
recomputable from the suffix.

## Review round 1 (Codex on PR #185) — two gate-integrity fixes

1. **Evidence binding.** `resolve_vintage_seam` no longer accepts any local
   failed report: in seam mode it compares EVERY lineage-relevant input digest
   the golden report recorded (the `*_sha256` set golden mode writes — panel,
   fundamentals, alpha stats, WF manifest, strategy config, SPY OHLCV, GMM)
   against the pending batch's freshly-computed digests, key-by-key, and
   refuses on any divergence NAMING the digest ("seam evidence STALE: input
   digest 'panel_sha256' diverged ..."). A report with no recorded digests is
   unusable; a report missing a key (or the batch missing one) refuses. The
   exact evidence bytes are bound into the seam block as
   `evidence_golden_report_sha256` (file content sha256), alongside the
   evidence path. A failed golden now admits ONLY the vintage it actually
   measured.
2. **Atomic predeclared run dirs** (the `tools/goal7_momentum_run.py` claim
   pattern). Default out-root is now the durable
   `~/renquant-data-store/goal6-jobb-gbdt-depth/`; every writing invocation
   (`--golden` or the batch) requires a predeclared `--run-id NNN` and claims
   `run-<NNN>` atomically (fresh `mkdir` + `O_CREAT|O_EXCL RUN_CLAIM.json`)
   BEFORE any training or output write; `run_golden`/`run_extension` assert an
   in-progress claim before touching anything (the runtime tripwire behind
   "no write precedes the claim"); completed outputs — golden report, window
   artifacts, extension manifest, the claim itself — are sealed read-only
   (0444) at finish. An existing run dir (claimed, completed, or crashed)
   refuses; a crashed claim stays in force (refuse-and-investigate), and
   manual removal must leave its own durable record. `--plan-only` is now
   PRINT-only (no writes outside claimed run dirs). The batch takes its
   evidence via `--evidence-golden <run-dir>/golden_report.json` (path + sha
   recorded in the seam block).

New tests for both: stale-digest refusal naming the digest, substituted-report
refusal, true-report admission with sha binding, claim/overwrite/repeat-after-
completion refusals, seal-mode 0444 checks, and monkeypatched-writer proofs
that an unclaimed or sealed run dir refuses before any writer/trainer runs.

## Not done / blocked

* The 82-fit batch: NOT launched (per instruction; the no-flag refusal was
  verified end-to-end against the real failed golden, the seam and claim paths
  by unit tests). Launching is now:
  `--golden --run-id NNN` (fresh evidence on the current vintage), then
  `--run-id MMM --evidence-golden <run-NNN>/golden_report.json
  --accept-vintage-seam` (~19 min measured upper bound). The digest binding
  means the batch must run on the SAME input vintage as its golden evidence —
  if the nightly data rebuild intervenes, the seam admission refuses and a
  fresh `--golden` is required first (that refusal is the designed behavior,
  not a bug).

## Review round 2: the PASSED path was never bound to the input vintage

Round 1 bound the failed-golden path — the seam mode compares every recorded input
digest to the pending batch's freshly-computed one and names the diverging key. The
ordinary admission did not. `resolve_vintage_seam` called `require_golden_pass` and
returned, so the question it asked was *"did parity pass?"* and never *"on which
inputs?"*

A green report recorded against different panel / fundamentals / config bytes therefore
authorized a current batch — the mixed-vintage lineage the whole gate exists to stop,
entering through the door marked *pass*.

It is the more dangerous of the two carried-forward cases: on the failed path the seam
block at least forces the operator to look, while on the passed path **nothing else
examines the inputs at all**.

The comparison is now a named function, `require_current_input_vintage`, called **before
either parity branch**. A golden report — passed or failed — is a measurement of the
bytes it ran on, and carrying it onto different bytes is stale evidence either way.

One consequence worth stating plainly: a passing golden that records **no**
`input_digests` is now refused. Before round 2 that was the *default shape* of a passing
report — nothing required a pass to record what it ran on — so this is a real tightening
and not just a re-ordering.

| claim | value | provenance |
|---|---|---|
| module tests | 41 passed | [VERIFIED — `pytest -q tests/test_wf_gbdt_depth_extension.py`] |
| the round-2 regressions are load-bearing | 3 of 4 fail against the pre-fix tool | [VERIFIED — `git show HEAD:tools/wf_gbdt_depth_extension.py` over the fix, re-run] |
| the fourth is the anti-vacuity control | a current-vintage passed golden still admits, before and after | [VERIFIED — same run] |
