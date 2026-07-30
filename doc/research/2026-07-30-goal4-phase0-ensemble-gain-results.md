# RESULTS — GOAL-4 Phase 0: does combining the existing scorers gain anything?

**STATUS: verdict WITHHELD pending adversarial review (§7).** The review and
its disposition are appended verbatim below before this PR is mergeable.
Do not cite anything in this document as confirmed until that section is
present and states UPHELD.

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
| prod_XGB | benchmark | `artifacts/prod/panel-ltr.alpha158_fund.json` | full: 43/43 WF-fold config_fingerprint match `[VERIFIED]` |
| certified_clf | candidate | `artifacts/shadow/panel-clf.top-decile.fwd60.json` | partial: recipe-script sha256 + hyperparameter match, no per-fold digest `[VERIFIED, disclosed limitation]` |
| PatchTST | candidate | `artifacts/patchtst_shadow/pt07_.../hf_patchtst_all_seed44_model.pt` | full: 43/43 WF-fold checksum+fingerprint match `[VERIFIED]` |

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

`[TO BE APPENDED VERBATIM — commissioned, not yet run as of this commit]`
