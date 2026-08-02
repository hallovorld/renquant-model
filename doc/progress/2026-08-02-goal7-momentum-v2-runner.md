# GOAL-7: momentum v2 runner — gap-block inference, built ahead of the prereg freeze

STATUS: DRAFT PR gated on the v2 prereg freeze (model#191). GATE NOW SATISFIED:
while this runner was being built, #191 MERGED to main at `c280d32` with second
parent `cbe537490a985cc617d9c48ec8756582f4f61e8e` — exactly the commit this
runner implements — and the merged prereg file is byte-identical to that text
`[VERIFIED — git rev-parse c280d32^2 + empty git diff cbe5374..origin/main on
the file, 2026-08-02]`. Zero prereg delta to reconcile; codex review of THIS
diff is the remaining gate. The prereg text GOVERNS (its §5).
WHAT: `tools/goal7_momentum_v2_run.py` — a NEW file; the v1 runner is untouched.
Candidate/inputs/placebo are the v1 objects REUSED BY IMPORT (preflight incl.
`tr_builder_importable`, Amendment-3 manifest resolution, `assemble_day`,
`_spearman_ic`, the TR builder; `sample_acf` imported for the rho_1 valve).
New here is ONLY what the v2 prereg replaces: §2 gap-block machine (h=20 blocks,
gap=20, thin-block drop-and-count, n_surviving floor 40), §3.1 ordering with the
degenerate-scale valve (ddof=1, non-finite or <= 0 -> published +
UNRESOLVED-METHOD, controls never run), the §2.5 |rho_1| >= 0.25 valve, both
frozen Normal controls (PCG64, `default_rng(20260801+r)`, r in 0..999, exactly
n_surviving draws, same t/bar/comparison as H1, rates + per-rep clear/fail
published), then the §4 decision map (MDE gate; H1 with SIGNED t >= bar;
RETAIN-F1 vs RETAIN-S via t_delta). Single-shot claim/result/refusals machinery
mirrors v1 pointed at the NEW predeclared dir
`~/renquant-data-store/goal7-momentum-v2-prereg-run/`; every terminal outcome
consumes the shot; pre-inference identity refusals ledger-then-release.
Preflight additionally requires the v2 prereg file present (absent until #191
merges — refusal by design) and the v1 sealed result present as provenance.
WHY/DIR: v1's single shot sealed UNRESOLVED-METHOD (dependence-modeling family
refused on the realized rho_1 = 0.9269 `[VERIFIED — prior work, model#189]`);
v2 swaps in the dependence-AVOIDING gap-block geometry the prereg freezes.
Building the runner as a gated DRAFT lets codex review the diff in parallel with
the prereg rounds without any execution license existing before the freeze.
RUNNER-DECLARED READINGS (flagged in the PR body for prereg reconciliation):
(1) §4 "mean IC(S)" read as the mean of surviving block means (the location the
§2.3 t tests); per-date grand means additionally published. (2) The single bar
uses df = n_surviving(S) − 1. (3) rho_1 valve evaluated after the sd valve and
before controls (the prereg's §3.1 does not place §2.5 explicitly).
EVIDENCE:
  artifact:      tools/goal7_momentum_v2_run.py (new; v1 imported, not copied),
                 tests/test_goal7_momentum_v2_runner.py (33 tests, synthetic
                 fixtures only, v1 autouse ledger-isolation idiom + guard-on-guard)
  prod or exp:   exp — research runner; no serving surface; zero real-data reads
                 in tests and NO --execute performed (no claim exists:
                 ~/renquant-data-store has no v2 dir `[VERIFIED — ls 2026-08-02]`)
  existing data: v1 sealed result + claim present at the v1 dir `[VERIFIED — ls
                 2026-08-02]`; prereg branch tip read at
                 cbe53749 `[VERIFIED — git show, full text read]`
  best-known?:   yes — reuses the reviewed v1 machinery by import; the only
                 restated code is the guard (hardwired to v1 globals) and the
                 orchestration loop, both noted inline
  scope:         33/33 new-file tests; make test 1426 passed (1393 pre-PR + 33)
                 `[VERIFIED — pytest 2026-08-02, both counts measured]`;
                 partition arithmetic pinned at T=2378 -> 59 blocks and
                 bar(df=58) = 2.0017 `[DERIVED — scipy.stats.t.ppf, matches the
                 prereg's derived value]`
NEXT: prereg #191 freezes (any new clauses reconciled against cbe53749) -> codex
review -> merge -> single --execute under the claim discipline.
AC6: N/A — research tooling.
