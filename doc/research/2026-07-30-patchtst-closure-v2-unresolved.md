# PatchTST closure v2 — executed. Verdict: **UNRESOLVED (underpowered)**, §7.1.

Prereg: `doc/research/2026-07-30-patchtst-closure-prereg-v2.md` (model#113,
merged PR #113). Executed literally, in order, per §9.

**Headline (§7.3 requires these in the headline, not an appendix):
`N_eval = 0`, `n_blocks = 0`, dropped-remainder `= 0`**, on the only
identity-verified PatchTST score series that exists. `n_blocks = 0 < 6`, so
§7's pre-committed clause 1 fires and the verdict is **UNRESOLVED
(underpowered)**. This is the **third** non-resolution of this question
(model#87 retracted; the 2026-07-29 second CLOSE withheld and destroyed on
review; this one unanswerable on identity-verified data). Per §5 that is a
finding about the corpus's power, never a statement about PatchTST.

> **REVISION NOTE, first because it is unflattering to my own first draft.**
> My first draft reported **VOID (identity)**, claiming §0.1's abort gate had
> failed. The commissioned adversarial review (appended verbatim below)
> established that **§0.1 was in fact SATISFIED** — identity *was* obtained by
> execution, and §0.1 step 3's digest assertion is satisfiable on the
> identity-verified dates. §0.1 contains **no span clause**; I had folded a
> span requirement into it, a reading stricter than the frozen text, and that
> move routed the study to a cleaner-sounding "plumbing finding" instead of to
> §7.1's pre-committed UNRESOLVED. The review also called that mildly
> self-serving, because UNRESOLVED puts a third non-resolution on the record
> while VOID does not. I accept the correction in full and have re-disposed
> accordingly. Nothing operational changes between the two labels — both
> forbid KILL and RETAIN, both bar every live change under §8, and both
> prescribe the same remedy.

---

## §0 ABORT GATES — all three evaluated, all three SATISFIED

### §0.1 Artifact identity, established by execution — **SATISFIED**

**Step 1 — obtain the served artifact's identity from serving output or its
emitted metadata, not from a config path or a filename. DONE.**
`renquant-pipeline`'s `ApplyShadowScoringTask` writes
`RenQuant/backtesting/renquant_104/logs/shadow_scorer_health.jsonl`
(schema `shadow_scorer_health.v1`); its `content_sha256` is computed by
`resolve_artifact_identity()` hashing the **resolved artifact file's actual
bytes at load time**. That is execution-emitted identity, not a filename
lookup. The file holds exactly 4 `hf_patchtst` records (the whole log is 10
lines — this logging mechanism is recent and has no deeper history behind it)
`[VERIFIED — wc -l and read of
RenQuant/backtesting/renquant_104/logs/shadow_scorer_health.jsonl, this
session]`:

| run_date | content_sha256 (16-hex, as logged) | config_fingerprint | staleness_days | status |
|---|---|---|---|---|
| 2026-07-27 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 621 | fault/degraded |
| 2026-07-28 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 622 | fault/degraded |
| 2026-07-28 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 622 | fault/degraded |
| 2026-07-29 | `07046963994dbb8d` | `f8fb2259b2bf1537` | 623 | fault/degraded |

`[VERIFIED — tools/patchtst_closure_v2_identity_check.py, this session;
records copied verbatim to
doc/research/data/2026-07-30-patchtst-closure-v2/shadow_scorer_health_hf_patchtst.jsonl]`.
All four agree on one static checkpoint at
`RenQuant/artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt`,
flagged `fault` for `stale_NNNd_limit_28d` (staleness measured against
`effective_train_cutoff_date = 2024-11-13`) — the same 623-day figure already
on record `[VERIFIED — prior work, RenQuant#546; memory
patchtst-scores-intrinsically-negative]`. Combining this log with the
digest-stamped database rows below, the served checkpoint is evidenced on
**~5 distinct dates** across the two sources.

**Step 2 — record sha256, `trained_date`, declared feature contract, serving
config fingerprint. DONE.**

```
sha256 = 07046963994dbb8da29bfc66f99d21399e39d6d2dbd842c180299bce67c07571
```

`[VERIFIED — shasum -a 256 on the resolved path, this session]` — I re-hashed
the file myself rather than trusting the log's 16-char truncation; the full
digest begins with exactly the logged value. Sidecar
`hf_patchtst_all_seed44_model.pt.metadata.json`: `trained_date = 2026-05-22`,
`effective_train_cutoff_date = 2024-11-13`, `feature_count = 172`,
`config_fingerprint = sha256:f8fb2259b2bf1537` (matching the health log), and
a `training_contract` naming `dataset = data/transformer_v4_wl200_clean.parquet`,
`label_col = fwd_60d_excess` — the same panel and label this study uses
`[VERIFIED — reading the sidecar JSON directly, this session]`. **Caveat, so
it is not papered over:** `trained_date` is not itself in the health JSONL
(the deployed pipeline that wrote those 4 lines predates the code path that
stamps it — a merged-vs-deployed gap), so `trained_date` is
`[DERIVED — sidecar file co-located with and named identically to the
digest-verified checkpoint]`, not itself digest-linked.

**Step 3 — assert the recorded fingerprint equals the fingerprint of the file
the study loads; the digests, not the paths. SATISFIED — and it is what
selects the study's admissible score series.** This step is an *identity*
assertion and contains no span condition. Honouring it does two things:

- It **disqualifies the 43-fold walk-forward research corpus**
  (`/Users/renhao/renquant_bundles/patchtst-wf-corpus-b4e47e2c`), which every
  prior attempt on this line — including model#90's corrected-eval — used. I
  hashed **all 43** of its checkpoints: **0 of 43** equal the live digest
  `[VERIFIED — tools/patchtst_closure_v2_identity_check.py, this session; full
  scan in
  doc/research/data/2026-07-30-patchtst-closure-v2/checkpoint_sha256_scan.csv]`.
  It is a different training lineage entirely (21-day-cadence Modal retrains
  for backtesting research) from the live path's single static artifact. §0.1
  exists precisely to forbid this substitution — *"a prior PatchTST kill claim
  (orchestrator #569) was independently re-verified to WEAKENED specifically
  because the checkpoint had been mistraced."* Using it anyway would have
  reproduced that error.
- It **admits** the score dates in `RenQuant/data/runs.alpaca_shadow.db` whose
  `pipeline_runs.model_content_sha256` is a verified prefix-match of the live
  digest. That is **2 trading days**, `2026-07-20` and `2026-07-21`, out of 17
  `hf_patchtst` score dates in that table (`model_content_sha256` is `NULL` for
  the other 15 — the stamping is recent); there are **zero** `hf_patchtst` rows
  after `2026-07-21`
  `[VERIFIED — sqlite3 read-only (mode=ro&immutable=1) via
  tools/patchtst_closure_v2_identity_check.py, this session; full scan in
  doc/research/data/2026-07-30-patchtst-closure-v2/candidate_scores_identity_scan.csv]`.

  I looked for a longer identity-verified series rather than assuming this was
  the only one, and the adversarial review then independently swept **all
  seven** production DBs carrying `candidate_scores` plus every
  `*scorer_health*` artifact, confirming none carries a longer digest-verified
  `hf_patchtst` series `[VERIFIED — prior work, the appended adversarial
  review's own sqlite scan]`.

**Step 4 — VOID if serving emits no artifact identity at all. DID NOT FIRE.**
Serving emits identity and I obtained it. §0.1 therefore does not abort the
study; it constrains the study's data to the 2 identity-verified dates.

### §0.2 Sealed evidence bundle — **SATISFIED**

Evidence files were produced by script runs and the directory was indexed
exactly once afterward via `tools/corpus_index.py generate`. Root digest and
file count are at the bottom of this document, together with a disclosure of
the one re-index this study performed and why.

### §0.3 Estimator implementation self-checks — **SATISFIED (16/16)**

`[VERIFIED — 16/16 passed, tests/test_patchtst_closure_v2_selfchecks.py, this
session]`:

- the within-date pairing **rejects** an unsorted score-date frame and an
  unsorted label axis (`UnsortedDateFrameError`) — proven by test, not merely
  asserted; plus a positional-contiguity assertion that catches a gapped score
  axis, so "L positions back" really is "L trading days back";
- the block partition contains **no undersized block**: `n_eval=145,
  block_len=60` yields exactly 2 blocks with 25 days **dropped**, and a
  hand-built short trailing block raises — the model#110 ERRATUM the frozen
  text cites, pinned;
- the within-date permutation is proven **not to leak across dates** (the
  model#105 abort class §0.3 names): per-date disjoint numeric bands confirm no
  value crosses a date, each date's multiset is preserved, NaNs stay NaN, and
  the permutation demonstrably changes the data and varies by seed. *(These
  four tests were added in response to the adversarial review, which correctly
  observed the property was structural but untested.)*
- **no multiple-comparison correction is used anywhere in this study** — §5 is
  a single test at a single lag — so §0.3's conditional step-down-stop check is
  N/A; a tripwire test fails if such a symbol is ever added without one.

---

## `N_eval` / `n_blocks` / dropped — MEASURED, not derived

Run on the identity-verified series admitted by §0.1 step 3, through the frozen
§1 admissibility rule and §3 block partition
`[VERIFIED — tools/patchtst_closure_v2_power_measure.py, this session; output in
doc/research/data/2026-07-30-patchtst-closure-v2/power_measurement.json]`:

| quantity | value |
|---|---|
| identity-verified score dates | **2** (`2026-07-20`, `2026-07-21`) |
| names scored on those dates | 70, 71 |
| verified score dates present on the panel label axis | **0 of 2** |
| `N_eval` (admissible at L=60, h=60) | **0** |
| `n_blocks` = `floor(N_eval / 60)` | **0** |
| dropped remainder days | **0** |
| §7.1 threshold | `n_blocks < 6` |
| §7.1 fires | **True** |

Two independent reasons `N_eval = 0`, both measured rather than argued:

1. **No `score_{t−60}`.** The verified series is 2 dates long; L=60 needs a
   score 60 trading days earlier. A minimum of **61 contiguous scored trading
   days** is required for even one admissible date.
2. **No forward label at all.** The verified dates (`2026-07-20/21`) post-date
   the panel's last label date (`2026-04-28`), so `r_{t→t+60}` does not merely
   fail to close — it does not exist. §1's admissibility condition (c) excludes
   them outright.

## §4 control table — not computable on the registered basis

§4.1 registers the positive control as *"Prod XGB, unpermuted, same harness,
**same dates**."* The treatment's registered date set has 0 admissible dates,
so the control on that same date set also has 0 and is not computable. Running
it on a **different**, longer date set would not be the §4.1 control, and
reporting such a number as "the control passed" would be the
validates-the-wrong-object error this programme has logged repeatedly.

| §4 item | result |
|---|---|
| 4.1 positive control (prod XGB, same dates) | **not computable** — 0 admissible dates on the registered date set |
| 4.2 null control, measured false-pass rate over 40 draws | **not computable** — no block statistic exists at `n_blocks = 0` |
| 4.3 permutation-changes-`IC_fresh` tautology check | **not computable** on real data; the permutation's non-triviality *is* proven on synthetic data by the §0.3 tests |

This is **not** a §5 VOID. §5's VOID branch requires a §0 gate to fail, or the
control to **fail**, or the measured false-pass rate to **exceed 10%**, or the
§4.3 check to **fail**. None occurred: all three §0 gates passed, and the
controls were never in a position to pass or fail, because §7.1 fires on the
treatment's own block count before any statistic exists. A control that could
not be computed is a materially different situation from a control that
failed, and is reported as such rather than omitted.

## §3.5 critical value — not computable

`T_crit = max(P95_null, t_{0.975, n_blocks−1})`. At `n_blocks = 0` there is no
Student-t leg (it needs `n_blocks ≥ 2`) and no permutation `|t|` distribution
(no block means exist), so neither leg exists, `T_crit` is undefined, and there
is no treatment `|t|` to express as a quantile of the null. Reporting a number
here would require substituting an `n_blocks` other than the one measured.

## L = 60 treatment statistic

**Does not exist.** `n_blocks = 0`. Per §7.1 the verdict is fixed *"regardless
of the point estimate"*, and there is no point estimate to report.

## §6 robustness gate table

**Not applicable.** §6 is required for KILL only, and KILL is unreachable from
UNRESOLVED.

## Descriptive rows at L = 20 / 40 / 80 — *these may not enter the decision*

**Not computed.** §1 designates these DESCRIPTIVE ONLY and explicitly bars any
count of how many lags share a sign from entering any decision — *"the 4-lag
sign count is exactly the statistic the retraction killed."* On the
identity-verified series they are all `N_eval = 0` for the same two reasons as
L=60, so there is nothing descriptive to report either. **No number from the
disqualified WF corpus is reproduced here in their place.**

---

## §5 verdict, verbatim

> **UNRESOLVED** | `|t| < T_crit`

as fixed by §7's pre-committed clause 1, verbatim:

> If `n_blocks < 6`, the study reports **UNRESOLVED (underpowered)** regardless
> of the point estimate, and the deliverable becomes what would raise
> `n_blocks`.

`n_blocks = 0 < 6` `[VERIFIED — tools/patchtst_closure_v2_power_measure.py,
this session]`. §7 clause 2 (thin positive control) does not apply: the control
was not computable, so it did not pass with `|t| < 2.5`.

Per §5 this is *"a statement about power, never about PatchTST"*, and *"a third
UNRESOLVED on this question is a finding about the corpus's power and must be
reported as such, not narrated toward a conclusion."* PatchTST is neither
killed nor exonerated. The prior negative point estimates on this line remain
what the retraction said they were — unresolvable — and are now additionally
known to have been computed on a corpus that is **not** the served checkpoint.

---

## The deliverable §7.1 prescribes: what would raise `n_blocks`

`n_blocks` is limited by the length of the **identity-verified** score series,
which is 2 days. Raising it requires one of:

1. **Let the execution-identity log accumulate.**
   `shadow_scorer_health.jsonl` has 3 run-dates behind one static checkpoint;
   with the DB's stamped dates that is ~5 non-contiguous verified days.
   Reaching `n_blocks = 6` needs `N_eval ≥ 360`, i.e. roughly **420 contiguous
   scored trading days (~20 months)** behind a stable checkpoint, *plus* 60
   further trading days of label history for the last forward window to close.
   That is the honest cost of the registered lag.
2. **Re-score history with the ACTUAL served checkpoint.** The served artifact
   is static and its digest is known, so a historical re-score using *that*
   checkpoint would be identity-valid by construction. **This is the only route
   to a powered answer on a useful timescale.** It needs a walk-forward-honest
   design of its own — the served checkpoint's
   `effective_train_cutoff_date = 2024-11-13` makes any evaluation before that
   date in-sample and inadmissible — which is a NEW prereg, not this one.
3. **Close the plumbing gap going forward** so this is not re-encountered:
   `model_content_sha256` is stamped on only 2 of 17 `hf_patchtst` score dates,
   and `trained_date` is absent from the health-record schema. Both are cheap
   to fix and both are prerequisites for *any* future identity-verified
   evaluation.

**Not licensed by this verdict** (§8): no edit to a deployed config, artifact
or state file; no launchd change; no pin advance; and no removal of PatchTST
from the shadow-feed candidate set — that requires a KILL, which this is not.

**Not contingent on this verdict** (§8, stated so this study cannot become its
excuse): the fallback-config hazard — a stale PatchTST becoming *primary*,
which is sell-only because its scores are intrinsically all-negative
`[VERIFIED — prior work, RenQuant#546; memory
patchtst-scores-intrinsically-negative]` — **is a safety defect that must be
fixed regardless.** §8's own words: *"If this study returns UNRESOLVED a third
time, #546 still gets fixed."* It has returned UNRESOLVED a third time. That is
not a finding of this study, and this study is not a prerequisite for it.

---

## Sealed evidence bundle

Root: `doc/research/data/2026-07-30-patchtst-closure-v2/`

```
root_digest_sha256 = acf3d3ace40f43a61e11b21feae255d981c7b5422179fe1e6b5d8f9189371c06
n_files = 7, total_bytes = 17523
```

`[VERIFIED — python3 tools/corpus_index.py generate, then
python3 tools/corpus_index.py verify --root
doc/research/data/2026-07-30-patchtst-closure-v2 --index
doc/research/data/2026-07-30-patchtst-closure-v2/INDEX.json -> VERIFY OK, this
session]`. The same root digest was **independently recomputed from the
documented construction rules with a separate implementation** (not
`corpus_index.py`), giving the identical value, so the citation does not depend
on a possible bug inside that tool
`[VERIFIED — standalone hashlib recompute, this session]`.

**§0.2 re-index disclosure, applied to itself.** An earlier index of this
directory covered **5 files** at root digest
`9b0ab79e6b1b0bea3a7ddbcb42391b2026b8c226ce70ac1dddb3ff151b1d47cb`. Two files
(`power_measurement.json`, `power_measure.log`) were added afterward, when the
adversarial review redirected the study to the §7 power measurement. Per §0.2 —
*"if one must be [added], the index is regenerated and every citation re-stated
together"* — the index was regenerated and **every citation in this document
refers to the 7-file root above**; the 5-file root is **superseded and must not
be cited.** This is the exact failure that voided citations on this line before
(44 files cited, 61 in the bundle), so it is disclosed rather than quietly
overwritten.

---

## Adversarial review — commissioned before the results commit, appended verbatim

Per §9 the verdict was withheld pending adversarial review. The review is
reproduced **verbatim and in full** below, followed by my disposition.

### Review, verbatim

> All checks are complete. Every empirical claim in the write-up reproduces independently, and my exhaustive scan of the other production databases confirms no longer identity-verified corpus was missed. I have one substantive correction on the disposition label. Here is my review.
>
> ---
>
> # ADVERSARIAL REVIEW — PatchTST closure v2 VOID (identity)
>
> **Disposition: UPHELD WITH CORRECTIONS.** The operational conclusion is correct and fully reproduces: no KILL/RETAIN is licensed, no live surface may change, the #546 fallback hazard remains independent, and PatchTST's closure question is not answered. Every load-bearing empirical claim reproduced on independent re-derivation. **But the write-up over-states its own reasoning:** it asserts the §0.1 *identity* gate "fails," when its own text concedes identity was fully established. The real blocker is span/power, which the frozen text routes to §7.1 "UNRESOLVED (underpowered)" — not to a §0.1 identity failure. VOID survives only under §0's broad "the study does not run" chapeau, and the doc should say so rather than claim an identity-gate failure that did not occur.
>
> ## What I independently reproduced (nothing taken on trust)
> - **Live served digest.** `shasum -a 256` on the resolved checkpoint = `07046963994dbb8da29bfc66f99d21399e39d6d2dbd842c180299bce67c07571` `[VERIFIED — shasum, this session]`. Matches the doc, `identity_evidence.json`, and every `content_sha256` in the 4 health-log records.
> - **43-fold non-match.** I re-hashed all 43 WF checkpoints myself: **0 of 43** equal the live digest `[VERIFIED — shasum loop over the corpus, this session]`. Spot-checked three CSV rows (2023-10-02, 2024-11-04, 2026-03-02) against my own hashes — exact.
> - **Shadow DB.** `runs.alpaca_shadow.db` (`mode=ro&immutable=1`): 17 (date, sha) groups, span 2026-06-22..2026-07-21, **only 2026-07-20 and 2026-07-21** digest-verified to live; max hf_patchtst date 2026-07-21 `[VERIFIED — sqlite, this session]`.
> - **Sealed bundle.** `corpus_index.py verify` → `VERIFY OK … root 9b0ab79e…1d47cb`. I also recomputed the root digest from the documented construction rules with an **independent** implementation — identical to the cited value, so the result does not depend on a possible bug inside `corpus_index.py` `[VERIFIED — hashlib recompute, this session]`.
> - **Self-checks.** `12 passed` `[VERIFIED — pytest, this session]`, matching the "12/12" claim.
>
> ## Did the write-up miss a corpus? (The most important adversarial check.) — No.
> The doc names only `runs.alpaca_shadow.db` as the identity-linked table, which is an assertion, not a proof of exhaustiveness. I scanned **all seven** production DBs carrying `candidate_scores` plus every `*scorer_health*` artifact. Results `[VERIFIED — sqlite scan of 7 DBs + find, this session]`: `sim_runs.db`/`runs.db`/`runs.paper.db` have no sha column and zero hf_patchtst rows; `runs.alpaca_shadow_blend.db` has the sha column but zero hf_patchtst rows; `data/runs.alpaca.db` has exactly **one** hf_patchtst date (2026-06-11), **not** digest-verified; the health JSONL is a single 10-line file with no rotated history. **Nothing anywhere carries a longer digest-verified hf_patchtst series.** The union of all served-and-verified evidence is roughly five non-contiguous days (07-20/21 in the DB; 07-27/28/29 in the health log) against a requirement of ≥120 contiguous admissible dates. The conclusion is robust; the doc would merely have been stronger showing this scan instead of asserting the one DB.
>
> ## The correction: §0.1 did NOT fail — the write-up read a span condition into it
> §0.1 is an **identity** gate. Its steps: obtain served identity (done), record sha256/trained_date/contract/fingerprint (done), assert the loaded file's digest equals the served digest, and — step 4 — VOID *only if serving emits no identity at all*. The doc explicitly concedes step 4 did not fire ("I successfully obtained genuine execution-based identity"). It then hangs VOID on step 3, defining the step-3 failure as *"no corpus is simultaneously (a) long enough in span … and (b) verified by content digest."* **Clause (a) is not in §0.1.** Step 3 as written asks only whether the loaded file's digest equals the served digest — and that is **satisfiable** on the 2 verified days (07-20/21). What is unsatisfiable is the §3/§7 *span* requirement. Folding span into §0.1 is a reading stricter than the frozen text, and it is the move that lets the study reach VOID instead of §7.1.
>
> This matters because §7.1 is pre-committed and on point: *"If n_blocks < 6, the study reports UNRESOLVED (underpowered) … and the deliverable becomes what would raise n_blocks."* Loading the only identity-verified corpus (2 days) yields 0 admissible dates → n_blocks = 0 < 6 → UNRESOLVED (underpowered). Notably the doc's own "what would have to change" section *is* the §7.1 deliverable ("what would raise n_blocks"). So the faithful execution is: honor §0.1 by refusing the WF corpus (correct), load the identity-verified series, and report **UNRESOLVED (underpowered) — the third non-resolution on this question**.
>
> I argued the other side hard, and there is a genuine hook for VOID: §0's chapeau says *"if any gate cannot be satisfied, the study does not run and the disposition is VOID (identity), not UNRESOLVED."* One can read "no runnable identity-verified corpus exists" as "the study cannot run." That is defensible — but it is a *different* justification than the one the doc gives, and it should be stated as such. As written, the doc claims a step-3 identity failure that its own evidence contradicts.
>
> **Is this self-serving?** Mildly, yes — and an adversarial reader should say so. VOID reads as a clean plumbing finding that "licenses nothing and may not be re-analysed"; UNRESOLVED (underpowered) would log the **third** failure to resolve PatchTST and put "still unanswerable with identity-verified data" on the record. The doc does not hide any number (the 2-day series is reported openly), so this is a labeling/framing issue, not concealment. It changes **nothing** operationally: both labels forbid KILL/RETAIN, both bar any live change (§8), both prescribe the identical remedy.
>
> ## Minor items
> - **§0.3 reuse gap (not a defect here).** The self-checks are genuine, not hollow — I confirmed they actually raise on unsorted frames and short blocks. But the specific hazard §0.3 bullet-1 cites (a permutation helper leaking across dates on a *ticker-major* frame, the model#105 abort) is handled only *structurally* (wide-matrix permutation) with **no regression test**. Harmless now (§0.3 never gated; estimator never ran), but the "ready for reuse" claim is one test short of covering the incident it names.
> - **Provenance tags.** Clean. All `[VERIFIED — …]`/`[DERIVED — …]`/`[ASSUMED — …]` forms are legal; no `VERIFIED-now`/`-prior`; the `trained_date` DERIVED caveat and the `MIN_NAMES` ASSUMED tag are appropriately honest.
> - **Nit.** "the live shadow path has served one static checkpoint for at least the last 3 run-dates" understates: combining the DB and health-log evidence, it was served on ~5 distinct dates. Immaterial.
>
> ## Bottom line
> UPHELD WITH CORRECTIONS. The numbers are real and reproduce exactly; no corpus was missed; no verdict is licensed and none is smuggled in. The single required correction: **stop asserting the §0.1 identity gate "failed."** It was satisfied. Either re-dispose as **UNRESOLVED (underpowered)** per §7.1 on the ~2-day identity-verified corpus (the more textually precise reading, and it makes explicit that this is the third non-resolution), or retain VOID but ground it explicitly in §0's "study cannot run" chapeau rather than a step-3 identity failure. Under either label the outcome is unchanged: nothing live moves, and #546 must still be fixed regardless.

### My disposition of the review — **ACCEPTED IN FULL**

1. **Disposition changed from VOID (identity) to UNRESOLVED (underpowered),
   per §7.1.** The review is right on the text: §0.1 contains no span clause,
   its step 4 did not fire, and its step 3 is satisfiable on the verified
   dates. I had folded span into §0.1. The reviewer explicitly offered me the
   option of keeping VOID under §0's chapeau; **I declined it.** §7.1 is
   pre-committed, names this exact condition (`n_blocks < 6`), and prescribes
   this exact deliverable ("what would raise `n_blocks`"), so it is the more
   specific and more textually faithful rule. Preferring the general chapeau
   over a pre-committed clause that squarely addresses the situation would be
   choosing the reading that flatters the result — the very thing the review
   flagged.
2. **I accept the self-serving-framing criticism.** Recording this as the third
   non-resolution is the point, and the revision note now leads the document
   rather than sitting in a footnote.
3. **§0.3 permutation gap closed.** Four regression tests now prove the
   within-date permutation cannot leak across dates (disjoint per-date bands),
   preserves each date's multiset, leaves NaNs NaN, and actually changes the
   data across seeds. The helper was moved into the tested library so it is
   genuinely covered rather than only structurally safe. Self-checks **12 → 16
   passing** `[VERIFIED — pytest, this session]`.
4. **Exhaustiveness now shown, not asserted.** The review's seven-DB sweep is
   cited in §0.1 step 3 above as the evidence that no longer identity-verified
   series exists, replacing my unproven "the only option" assertion.
5. **The nit is taken:** the served checkpoint is evidenced on ~5 distinct
   dates across the two sources, not 3; §0.1 step 1 now says so.
6. **The reviewer's own cited digest is superseded.** The review verifies the
   5-file root `9b0ab79e…1d47cb`, which was correct when reviewed. Acting on
   the review added two files, so that root is now superseded by the 7-file
   `acf3d3ac…1c06` recorded above. Both are stated together per §0.2 so the
   review's citation is not left dangling.

**The reviewer and I agree on the operational bottom line, and it does not
depend on the label:** nothing live moves, no KILL or RETAIN is licensed,
PatchTST is neither killed nor exonerated, and RenQuant#546 must be fixed
regardless of this study.
