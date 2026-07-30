# PatchTST closure v2 — executed. Disposition: **VOID (identity)**, §0.1.

Prereg: `doc/research/2026-07-30-patchtst-closure-prereg-v2.md` (model#113,
merged PR #113). Executed literally, in order, per §9. **§0.1 — the first
abort gate, evaluated before any statistic — fails**, so no `d(t)`, no block
`t`, no `T_crit`, no control, and no §6 gate was computed. This is not a
judgment call or a relaxed reading; §0.1's own text is explicit that a
failure here is VOID, not UNRESOLVED, and licenses nothing.

Per the frozen text's own instruction, the deliverable of a §0.1 VOID is an
identity-plumbing finding, not an estimate. That is what this document is.

---

## §0.1 — artifact identity, established by execution

**Required, in order (from the frozen text): (1) obtain the served
artifact's identity from serving output/metadata, not a filename; (2) record
sha256 / trained_date / feature contract / config fingerprint; (3) assert
that fingerprint equals the fingerprint of the file the study loads — the
digests, not the paths; (4) if serving emits no identity at all, VOID.**

### Step 1–2: what the live shadow path serves, from execution output

`renquant-pipeline`'s `ApplyShadowScoringTask` writes
`RenQuant/backtesting/renquant_104/logs/shadow_scorer_health.jsonl`
(schema `shadow_scorer_health.v1`) on every run. `content_sha256` in that
file is computed by `resolve_artifact_identity()`
(`renquant-pipeline/src/renquant_pipeline/kernel/panel_pipeline/shadow_health.py`)
hashing the **resolved artifact file's actual bytes at load time** — this is
genuinely execution-based identity, not a config-path or filename lookup, so
it satisfies what §0.1 step 1 asks for.

The file holds exactly 4 `hf_patchtst`-kind records (the log itself is only
9.4KB / 10 lines total — this identity-logging mechanism is recent; there is
no deeper history behind it)
`[VERIFIED — wc -l and file listing on
RenQuant/backtesting/renquant_104/logs/shadow_scorer_health.jsonl, this
session]`:

| run_date | content_sha256 (16-hex, truncated) | config_fingerprint | staleness_days | status |
|---|---|---|---|---|
| 2026-07-27 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 621 | fault/degraded |
| 2026-07-28 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 622 | fault/degraded |
| 2026-07-28 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 622 | fault/degraded |
| 2026-07-29 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 623 | fault/degraded |

`[VERIFIED — tools/patchtst_closure_v2_identity_check.py, this session;
output copied to
doc/research/data/2026-07-30-patchtst-closure-v2/shadow_scorer_health_hf_patchtst.jsonl]`.
Every one of the 4 records agrees: the live shadow path has served **one
static checkpoint** for at least the last 3 run-dates, at
`RenQuant/artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt`,
flagged `status=fault` for `stale_NNNd_limit_28d` (staleness measured
against `effective_train_cutoff_date=2024-11-13`, not `trained_date` — this
is the same `623`-day figure already on record
`[VERIFIED — prior work, RenQuant#546; memory
patchtst-scores-intrinsically-negative]`).

I independently re-hashed the resolved file myself (not trusting the
16-char truncated log value alone):

```
sha256(RenQuant/artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt)
  = 07046963994dbb8da29bfc66f99d21399e39d6d2dbd842c180299bce67c07571
```

`[VERIFIED — shasum -a 256, this session]`. The full 64-hex digest starts
with exactly the 16-hex value the health log carries in every record — the
log's truncated identity and the file's actual bytes agree.

The co-located sidecar `hf_patchtst_all_seed44_model.pt.metadata.json`
(content-identified to the same checkpoint by directory/name, not by a
separate hash check — see the caveat below) carries `trained_date=2026-05-22`,
`feature_count=172`, `config_fingerprint=sha256:f8fb2259b2bf1537` (matches
the health log), and a `training_contract` naming
`dataset=data/transformer_v4_wl200_clean.parquet`,
`label_col=fwd_60d_excess` — the same panel and label this study would use
`[VERIFIED — reading the sidecar JSON directly, this session]`. **Caveat,
stated because §0.1 asks not to paper over exactly this kind of gap:**
`trained_date` is not itself emitted in the health JSONL (the deployed
pipeline version that wrote these 4 lines predates the code path that stamps
it — a merged-vs-deployed gap), so `trained_date` here is
`[DERIVED — sidecar file co-located with, and named identically to, the
digest-verified checkpoint]`, not itself digest-linked. This does not change
the VOID disposition below, which rests on the `content_sha256` comparison
alone.

### Step 3: does that digest equal the file this study would load?

This is where the gate fails. The only historical PatchTST score corpus with
enough date-span to instantiate the frozen §3 block estimator at all is the
**43-fold walk-forward research corpus**
(`/Users/renhao/renquant_bundles/patchtst-wf-corpus-b4e47e2c`, built by
`renquant_backtesting.wf_gate.modal.executor` for walk-forward backtesting,
43 checkpoints retrained every 21 days from cutoff `2023-10-02` through
`2026-03-02`; its derived per-date scores are what `wf-eval/scores.parquet`
holds and what backed the prior model#90 corrected-eval line). I hashed
**every one of its 43 checkpoints** and compared each against the live
digest:

```
$ python3 tools/patchtst_closure_v2_identity_check.py
...
43-fold WF research corpus scan: 43 checkpoints hashed from
  /Users/renhao/renquant_bundles/patchtst-wf-corpus-b4e47e2c
any fold's checkpoint sha256 == live served sha256? False
```

`[VERIFIED — tools/patchtst_closure_v2_identity_check.py, this session; full
scan in
doc/research/data/2026-07-30-patchtst-closure-v2/checkpoint_sha256_scan.csv]`.
**Zero of 43 match.** This is not a coincidence of naming — the WF corpus is
a *different training lineage entirely* (systematic 21-day-cadence Modal
retrains for backtesting research) from the live shadow path's checkpoint
(a single artifact trained once, `trained_date=2026-05-22`,
`effective_train_cutoff_date=2024-11-13`, which does not correspond to any
of the 43 folds' own cutoff-minus-~87-day training windows). §0.1's own text
names exactly this failure mode: *"a prior PatchTST kill claim (#569) was
independently re-verified to WEAKENED specifically because the checkpoint
had been mistraced."* This is the same class of error, caught before a
number was computed instead of after.

I then checked whether ANY genuinely execution-identity-linked historical
score table exists, rather than assuming the WF corpus was the only option.
`RenQuant/data/runs.alpaca_shadow.db` (`candidate_scores` joined to
`pipeline_runs` on `run_id`, filtered to `model_type='hf_patchtst'`) DOES
carry a `model_content_sha256` column stamped per run:

```
runs.alpaca_shadow.db: hf_patchtst candidate_scores present on 17 distinct
  (date, model_content_sha256) groups, span 2026-06-22..2026-07-21
of those, dates where model_content_sha256 is a verified prefix-match of the
  LIVE digest: ['2026-07-20', '2026-07-21']
n execution-identity-VERIFIED hf_patchtst score dates: 2
```

`[VERIFIED — sqlite3 query via
tools/patchtst_closure_v2_identity_check.py, this session, read-only
(`mode=ro&immutable=1`); full scan in
doc/research/data/2026-07-30-patchtst-closure-v2/candidate_scores_identity_scan.csv]`.
`model_content_sha256` is `NULL` (unstamped) for 15 of the 17 dates — the
stamping itself is recent, consistent with the health-log finding above.
Only **2 trading days** (`2026-07-20`, `2026-07-21`) carry a verified match.
There are **zero** `hf_patchtst` rows in this table after `2026-07-21`
(PatchTST appears to have been further demoted out of active shadow scoring
around then, consistent with `topdecile_clf_blend_leg` appearing in the same
health log as a newer shadow lane — not this study's concern to resolve).

The frozen §3 estimator at `L=60, h=60` needs a **contiguous, same-checkpoint
score span of at least 120 trading days** before a single admissible
evaluation date exists (`score_{t-60}` must exist AND the forward 60-day
window from `t` must be complete), and §7's own pre-committed power
expectation is roughly ~500 admissible dates (`n_blocks≈8`). The only
digest-verified series available is **2 days** long. The only span-adequate
series (the WF corpus) is **verifiably not** what the live path serves.

### Step 4 / conclusion

Serving does **not** fail to emit identity at all (§0.1's literal step-4
branch) — I successfully obtained genuine execution-based identity. The
failure is the **step-3 assertion**: no corpus available to this study is
simultaneously (a) long enough in span to run the frozen estimator, and (b)
verified by content digest to equal what the live shadow path has served.
Per §0 and §5: **this is VOID (identity).** "A VOID study licenses nothing
and may not be re-analysed into a verdict" — no fallback lag, no
descriptive-only substitute, no relaxed span requirement was applied.

---

## §0.2 / §0.3 — not reached as formal gates, but engineering-complete

§0 gates are evaluated in order and §0.1 already fails, so §0.2 (sealed
bundle) and §0.3 (estimator self-checks) do not need to pass for this
disposition to be correct. Both were nonetheless done, because the §0.1
investigation itself needed to be reproducible and because the estimator
was fully built (for reuse once the identity gap closes) before this
determination was reached:

- **§0.2, applied to the abort-gate evidence itself.** All evidence files
  (`identity_evidence.json`, `checkpoint_sha256_scan.csv`,
  `candidate_scores_identity_scan.csv`,
  `shadow_scorer_health_hf_patchtst.jsonl`, `run.log`) were generated by one
  script run (`tools/patchtst_closure_v2_identity_check.py`) and the
  directory was indexed exactly once afterward via
  `tools/corpus_index.py generate`; nothing was appended after indexing.
  Root digest recorded below.
- **§0.3 self-checks — all pass, against synthetic data (the estimator was
  never run against the disqualified corpus):**
  - within-date pairing rejects an unsorted score-date frame AND an
    unsorted label-axis frame (`UnsortedDateFrameError`), proven by test,
    not merely asserted;
  - the block partition contains no undersized block (remainder dropped,
    never equal-weighted — the model#110 ERRATUM this frozen text cites);
  - no multiple-comparison correction is used anywhere in this study (§5's
    decision rule is a single test at a single lag, L=60), so the
    step-down-stop self-check is N/A; a tripwire test pins that no such
    correction symbol exists in the library undocumented.

  `[VERIFIED — 12/12 passed,
  tests/test_patchtst_closure_v2_selfchecks.py, this session]`.

---

## §1–§9 — not computed

Per the frozen text, §0 is evaluated before any statistic. None of the
following were computed, and none of the numbers below exist:

- `N_eval`, `n_blocks`, dropped-remainder count (§3) — **not computed**.
- `T_crit`, its two legs, which one binds, the treatment `|t|` as a null
  quantile (§3.5) — **not computed**.
- positive-control `t`, null-control measured false-pass rate, §4.3
  tautology check (§4) — **not computed**.
- the §6 robustness gate table — **not computed** (only relevant to a KILL,
  which cannot be reached from VOID).
- the descriptive L=20/40/80 rows (§1) — **not computed**.

The `tools/patchtst_closure_v2_lib.py` estimator (§1/§3/§3.5/§4 math) and
`tools/patchtst_closure_v2_run.py` (data-loading + orchestration, currently
wired to the disqualified WF corpus and explicitly marked as such at the top
of the file, with no CLI entry point so it cannot be run by accident) are
committed as ready-to-reuse infrastructure, not as a source of a verdict.

## §5 verdict, verbatim

> **VOID** — any §0 abort gate[.]

which is exactly what fired: §0.1 step 3's assertion (`the fingerprint
recorded in step 2 equals the fingerprint of the file the study loads`)
fails for every corpus available to this study.

---

## What would have to change before this question is re-askable

Per §0.1.4's own framing, a §0.1 failure turns the deliverable into an
identity-plumbing issue rather than a measurement. Concretely, closing
PatchTST's closure question needs **one** of:

1. A historical score corpus built by re-scoring the ACTUAL served
   checkpoint(s) — i.e., using the exact artifact(s) `shadow_scorer_health`
   (or an equivalent execution-identity log) shows were live on each
   historical date, back far enough to cover ≥120 admissible trading days
   at L=60. Today that log has 3 days of history behind one static
   checkpoint. It would need to run, unmodified, for roughly 6 months
   before this study could be re-attempted honestly at the registered lag.
2. Alternatively, a `runs.alpaca_shadow.db`-style score-with-verified-digest
   table maintained continuously (not stamped only from `2026-07-20`
   onward) — same span requirement.
3. Nothing about this VOID licenses treating the WF research corpus as a
   proxy "close enough" to live serving. §0.1 exists specifically to
   forbid that substitution after the #569 mistrace precedent; using it
   anyway would be exactly the error this gate is designed to catch.

Per prereg §8, this VOID licenses nothing live-side either: no shadow-path
edit, no config change, no pin advance. The fallback-config hazard
(RenQuant#546) remains **not contingent** on this study and unresolved by
it either way.

---

## Sealed evidence bundle

Root: `doc/research/data/2026-07-30-patchtst-closure-v2/`
Index generated once via `tools/corpus_index.py generate` after every file
above was written:

```
root_digest_sha256 = 9b0ab79e6b1b0bea3a7ddbcb42391b2026b8c226ce70ac1dddb3ff151b1d47cb
n_files = 5, total_bytes = 15359
```

`[VERIFIED — python3 tools/corpus_index.py generate --root
doc/research/data/2026-07-30-patchtst-closure-v2 --out .../INDEX.json,
this session; re-verified with `corpus_index.py verify` immediately after
-> VERIFY OK]`. **Nothing was added to this directory after this digest was
taken.** If a file must be added later, this index is regenerated and every
citation of the old root is re-stated together (§0.2's own rule, applied to
itself).

---

## Adversarial review — WITHHELD PENDING REVIEW

Per §9's publication discipline, this VOID conclusion is withheld pending a
commissioned adversarial review before merge. The review and its
disposition are appended verbatim below.

<!-- ADVERSARIAL_REVIEW_PLACEHOLDER -->
