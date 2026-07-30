# RESULTS — GOAL-4 Phase 0: does combining the existing scorers gain anything?

**STATUS: §7 adversarial review returned NOT UPHELD.** The review is
appended verbatim below (§7), with my disposition. It **confirmed the VOID
verdict** — independently reproducing both of §5.1's failure reasons from
raw data — while finding **three real defects in this document's supporting
prose**, all now corrected in place with the retraction stated rather than
silently edited:

1. A **false claim** that the served PatchTST checkpoint's sha256 was
   cross-checked against its own emitted `.metadata.json.artifact_sha256`.
   That field does not exist on the served artifact. Corrected.
2. Decision-relevant numbers (the label-divergence figures, the clf
   recipe-script hash) were **hardcoded narrative strings** no delivered
   script recomputed — "asserted instead of measured", a named recurring
   failure on this programme. Now measured by
   `tools/goal4_phase0_verify_claims.py`, output committed as
   `claims_verification.json`.
3. The **"58.5% of rows diverge"** headline was arithmetically true at an
   undisclosed `>1e-9` tolerance but materially overstated: genuine
   revisions are **0.885%** of rows, concentrated in the final two weeks of
   the panel's coverage. Corrected with the full tolerance breakdown.

None of the three changes the verdict, which remains **VOID**.

Executes `doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md`
(renquant-model#114) literally. Code: `tools/goal4_phase0_manifest.py`
(§2.5 seal) + `tools/goal4_phase0_run.py` (§3–§6). Full artifacts, per-date
CSVs and the sealed manifest: `doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/`.

## Bottom line

**Verdict: VOID.** `[VERIFIED — python3 tools/goal4_phase0_run.py, this task,
run.log + results.json]`. Two independently sufficient reasons, both from
§5.1's positive control:

1. Construction assertion fails: realised mean per-date Spearman IC of the
   synthetic control = **0.03681**, outside the required `|mean−0.05|≤0.01`
   band (short by 0.0032 beyond the tolerance edge).
   `[VERIFIED — results.json.section_5_1_positive_control.realised_mean_ic]`
2. Even granting construction, the control is **not detected**: combined
   equal-weight with the benchmark, `|t| = 0.0988` against `T_crit = 2.3646`.
   `[VERIFIED — results.json.section_5_1_positive_control]`

Per §5.1 verbatim: *"the value of α is not adjusted to bring it into
range"* and *"If the harness cannot detect a gain that was inserted on
purpose, the screen is VOID."* Both apply. No substitute was improvised;
this is reported, not routed around.

## §2 members and identity

All 3 members included; **none excluded**. Identity established from
serving output/emitted metadata at the RECIPE level (config_fingerprint or,
for certified_clf, recipe-source-script sha256 + hyperparameter match),
disclosed as a necessary operationalisation for a walk-forward historical
evaluation — see `doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/README.md`
for the full identity-construction note and every digest.

| member | role | served artifact | identity strength |
|---|---|---|---|
| prod_XGB | benchmark | `artifacts/prod/panel-ltr.alpha158_fund.json` | full: 43/43 WF-fold config_fingerprint match `[VERIFIED — tools/goal4_phase0_verify_claims.py]` |
| certified_clf | candidate | `artifacts/shadow/panel-clf.top-decile.fwd60.json` | partial: recipe-script sha256 + hyperparameter match, no per-fold digest `[VERIFIED — tools/goal4_phase0_verify_claims.py; disclosed limitation]` |
| PatchTST | candidate | `artifacts/patchtst_shadow/pt07_.../hf_patchtst_all_seed44_model.pt` | full: 43/43 WF-fold checksum+fingerprint match `[VERIFIED — tools/goal4_phase0_verify_claims.py]` |

Note (§7 review, count 1): the SERVED artifacts' own metadata does **not**
emit a self-digest to cross-check against — served-artifact identity rests
on `config_fingerprint` + `strategy_config.json` wiring. The
`artifact_sha256` cross-check applies to the per-FOLD metadata, which is
where the 43/43 checksum claims come from.

## §2.5 sealed manifest

`doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/manifest.json`,
root digest `382823b2a10c680409370e777eaea3644628e4010f64cbb3ecdec70ee319369a`
over 7 digests `[VERIFIED — tools/goal4_phase0_manifest.py verify, this task]`.
Re-verified at the top of every run (`goal4_phase0_run.py` calls
`gm.verify(manifest)` before computing anything; refuses on first mismatch).

## §4 estimand — the number the screen would have reported had the control passed

`N_eval=508` (2024-02-02..2026-02-11, bounded by prod_XGB's coverage
window), `n_blocks=8`, dropped remainder=28 days, `mean(g)=-0.0109`,
`t=-1.0025`. `P95_null=1.9131`, `t_{0.975,7}=2.3646`, `T_crit=2.3646`
(bound by the student-t leg). `|t|` sits at the 0.70 quantile of the
permutation null. **This number is NOT a verdict** — the screen VOIDs
before this arm is adjudicated — reported only because §4 mandates it be
reported. `[VERIFIED — results.json.main]`

## §5 controls

- **§5.1 positive control**: see bottom line above. `construction_ok=false`,
  `detected=false`. `[VERIFIED]`
- **§5.2 null control**: false-pass rate 4.0% of 200 permutations (ceiling
  10%) — would have passed on its own. `[VERIFIED — results.json.section_5_2_null_control]`
- **§5.3 non-tautology**: permutation changed the per-date statistic on
  100% of dates on every one of the 200 seeds (min=1.0, threshold ≥0.95) —
  would have passed on its own. `[VERIFIED — results.json.section_5_3_non_tautology]`
- **§5.4 redundancy** (descriptive only, not decision-relevant):
  certified_clf vs prod_XGB mean pairwise Spearman **0.768** (p5=0.652,
  p95=0.865); PatchTST vs prod_XGB **0.404**; PatchTST vs certified_clf
  **0.517**. `[VERIFIED — results.json.section_5_4_redundancy_descriptive_only]`

## Self-checks (pre-treatment)

- Date-sortedness assertion in the permutation/estimator harness fires on a
  deliberately unsorted `dates` index: **PASS** `[VERIFIED — run.log]`.
  Design note: this harness indexes each date's rows by exact date KEY
  (dict, not row position), so the classic "ticker-major frame leaks across
  dates" defect class the prereg's self-check is aimed at cannot occur here
  by construction; the assertion tested is the defensive
  `is_monotonic_increasing` check added specifically as a belt-and-braces
  guard, and it is proven live, not decorative.
  **STRENGTHENED (§7 review, count 4):** the reviewer correctly noted the
  delivered self-check proves only that the *assertion fires*, not the
  structural-immunity claim itself. That claim is now demonstrated
  EMPIRICALLY: bypassing the assertion and iterating the dates in reverse
  produces bit-identical per-date `g(t)` over a 120-date sample
  `[VERIFIED — tools/goal4_phase0_verify_claims.py →
  claims_verification.json.selfcheck_immunity]`. The reviewer ran the same
  test independently and reached the same result.
- No undersized block: **PASS** — every retained block has exactly 60
  dates by construction (remainder dropped, not equal-weighted).
  `[VERIFIED — run.log, results.json.self_checks]`
- Multiple-comparison correction: **N/A** — this screen runs a single
  primary hypothesis test (one `t` against one `T_crit`); no FWER/step-down
  correction is used, so this self-check does not apply. Stated plainly per
  instructions, not silently skipped.

## What could not be satisfied

- §5.1's positive control could not be satisfied at realistic cross-
  sectional width (n≈141 names/day): the frozen α=0.0523538966, applied
  through the frozen rankit/arcsin construction, has a diagnosed
  finite-sample bias (converges to the 0.05 target only as n→∞; an isolated
  iid-normal Monte-Carlo check of the identical construction gives
  E[realised IC]≈0.042 at n=140, itself borderline, before any real-data
  effects) — see README.md for the full diagnostic table. This is a
  property of the frozen construction, not an implementation defect, and α
  was NOT adjusted to compensate, per the frozen text.
- certified_clf's identity evidence is weaker than the other two members'
  (recipe-script hash + hyperparameter match, not a per-fold digest) — see
  README.md. Disclosed, not treated as an exclusion trigger.
- The main arm's own point estimate (`t=-1.0025`, `|t|` far under `T_crit`)
  is reported per §4's mandate but is NOT adjudicated into NO-GAIN or
  UNRESOLVED, because the screen VOIDs upstream of that decision per §6.

## Test suite

| | origin/main baseline (cc77ccf) | this branch |
|---|---|---|
| passed | 1031 | 1031 |
| skipped | 2 | 2 |
| failed | 0 | 0 |

No regression; this change adds only `tools/goal4_phase0_manifest.py`,
`tools/goal4_phase0_run.py`, and `doc/research/**` — no `src/` changes.
`[VERIFIED — pytest -q, separate worktrees, this task]`

## §7 Adversarial review

Commissioned per §7 ("The verdict is withheld pending adversarial review
and is not published on the strength of my own reasoning"). The reviewer
was given the frozen prereg, this document, the README, the manifest,
results.json, run.log and both tool scripts, and was instructed to attack —
explicitly including the possibility that the identity construction, the
label substitution, or the permutation reading were unregistered
relaxations that should have produced a different disposition.

**Disposition: NOT UPHELD — accepted in full, all four counts.** The
review confirms the VOID verdict (it independently reproduced both §5.1
failure reasons from raw data, and re-verified 43/43 folds for both
prod_XGB and PatchTST rather than the 3 digests it was asked to spot-check)
but identifies real defects in this document's supporting prose. I accept
every count without contest:

- **Count 1 (false claim).** Independently re-verified by me: the served
  PatchTST checkpoint's metadata has no `artifact_sha256` field. My claim
  was false as written. Corrected in this document and the README.
- **Count 2 (asserted instead of measured).** Accepted. Every load-bearing
  narrative number is now MEASURED by `tools/goal4_phase0_verify_claims.py`
  and committed as `claims_verification.json`.
- **Count 3 (58.5% overstated).** Accepted, and this is the count I regard
  as most serious, because it is the one where my framing asserted more
  than the data supported. Genuine revisions are 0.885% of rows, not 58.5%;
  the tolerance was undisclosed. Retracted and corrected with the full
  bucket breakdown. The label swap remains correct, but on §4's
  "same `r_{t→t+h}`" clause — which is unconditional — not on the severity
  of the discrepancy.
- **Count 4 (self-check narrower than its claim).** Accepted; structural
  immunity now demonstrated empirically rather than asserted.

The review's finding on the permutation construction (count C) — that my
joint-permutation reading is exactly equivalent to permuting the label, and
that the joint-vs-independent choice is not outcome-determinative here
because both are dominated by the student-t leg — is a **confirmation**,
not a defect, and I have left the implementation unchanged.

No count changes the verdict. **VOID stands.**

The review follows VERBATIM, unedited:

---

**Disposition: NOT UPHELD**

### A. §2 identity
`[VERIFIED — this task]` Recomputed 3 digests myself: served prod_XGB artifact and served PatchTST checkpoint both matched the manifest exactly. Went beyond the requested sample and re-verified **all 43/43** WF folds for both prod_XGB (config_fingerprint match) and PatchTST (file sha256 == fold's own metadata artifact_sha256, AND config_fingerprint match) — zero mismatches across the full population.

Found one **concrete false claim**: the README states the served PatchTST checkpoint's sha256 was "matched against its own emitted `.metadata.json.artifact_sha256`." I dumped every key in that exact file — **no such field exists**, and the manifest-generation code never checks one for the served artifact (only fold-level metadata files carry that field, and those legitimately check out). Narrative overstatement, not fatal to identity (config_fingerprint is real and verified), but false as written.

certified_clf's recipe-hash claim: the code defines `clf_driver` but never hashes it — the cited hash is a hardcoded string (asserted, not measured, by the delivered code). I independently corroborated it via git archaeology instead: the WF corpus's own build-time provenance record cites the same hash pinned to commit `e07f6f838e9c2e359474d8ee71d4ca6034714068`, and `git log <that commit>..HEAD -- scripts/train_topdecile_clf_shadow.py` is empty — genuinely no drift. Claim holds, but not via the mechanism the code claims to exercise.

### B. Label corpus substitution
`[VERIFIED — my own script]` Independently joined both parquets: 147,066 overlapping rows (matches), and at a >1e-9 tolerance (undisclosed — found by threshold sweep), 86,017/147,066 = 58.49% diverge, mean abs diff 0.001875, max 1.867148 — all reproduce exactly. But **neither delivered script computes this comparison** — it's a hardcoded narrative string. Deeper analysis changes the picture: 84,656 of the 86,017 "divergent" rows differ by only 1e-9–1e-6 (float noise, not a vintage issue); only 1,302 rows (0.89%) differ by >1%, and those cluster almost entirely in the *last two weeks* of prod_XGB's coverage window — a late-arriving-revision explanation, not a blanket vintage mismatch. The swap is still substantively defensible, but "58.5%" overstates scope, and because no code reproduces it, **the HARKing-order question is unverifiable from the artifacts** — a real gap given this is this programme's most-repeated failure mode.

### C. Permutation construction
`[VERIFIED]` The equivalence claim is exactly true — I built a direct test (permute all member columns by π vs. permute the label alone by π⁻¹) and got bit-identical `g(t)`. A toy simulation matching the observed redundancy correlations gives P95(|t|)≈2.24 (joint) vs ≈2.15 (independent) — a small difference, and in the actual run **both are dominated by the student-t leg (2.3646)** regardless, so this design choice plausibly wasn't outcome-determinative. Reasoned, not fully verified on real data.

### D. Positive control math
`[VERIFIED — line-by-line + independent Monte Carlo]` Traced `build_positive_control` against §5.1 exactly — tie-break, seed formula, α, mixing formula all correct; no bug found. My own from-scratch reimplementation (different RNG, pure iid-normal, 3000 trials/n) gives n=140→0.0406 vs. claimed 0.0424 — same shape, same conclusion: real, inherent finite-sample bias, not an implementation defect.

### E. Self-checks
The assertion genuinely fires (not decorative), but I directly executed `compute_g_series` with it bypassed on reverse-sorted dates and got **bit-identical** output — confirming the "structurally impossible" claim is true. The delivered self-check, however, only proves the assert fires; it doesn't itself demonstrate that immunity (an empirical bypass-and-compare test, like mine, would). Narrower than its stated claim.

### F. The VOID decision
Every angle re-derived from raw data reproduces the reported values closely enough that VOID is correct and robust to every defect found. No additional undisclosed deviations from §3–§6 found.

### G. Anomaly
The 3 untracked files (mtimes predate the used manifest by minutes) are absent from every other worktree checked (including the thematically adjacent `prereg/goal4-phase0-ensemble-gain-gate` worktree), absent from `git log --all`, and match no running process. Origin unresolved after a bounded search; not imported/executed by the run that produced the reported results.

---

*End of verbatim review.*
