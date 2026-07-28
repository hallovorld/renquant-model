# G4 PatchTST rescore — preregistration PR

## STATUS
delivered

## WHAT
Preregistration only; NOTHING DISPATCHES BEFORE MERGE. Frozen matrix for
the 43-fold Modal T4 train-only rescore under the operator's $25 HARD cap
(inclusive of the $1.45 probe/smoke pre-spend, frozen as
--pre-spend-usd): single run namespace wf-pt-b4e47e2c-batch1; phase 1 =
exactly the 3 newest cutoffs; phase 2 = the full 43-list (resume
dispatches the 40 absent, zero retrain); THE budget control is bt#82's
execute-time gate (hard timeout bound 2900 s per absent fold + immutable
five-field budget_contract; projection/dispatch-note are diagnostics
only); expected success signature = exit 1 + failed_folds=[] +
skip_calibrators_diagnostic quarantine; local 8-way calibrator leg
afterward; total reporting; halt + amendment on any failed fold or gate
refusal.

## WHY/DIR
The PatchTST half of the G4 Phase-A corpus. With-calibrators-on-Modal
measured over cap (right-censored ≥$25.4 at the old timeout); train-only
under the hard 2900 s bound fits: worked worst-case ≈ $24.65 ≤ $25.

## EVIDENCE
Pre-freeze smoke on the frozen invocation shape (1/1 fold, 2384.41 s
cuda, checksum 8a926df3…, AC7 PASS, exact quarantine signature) — smoke
artifacts retained durably at
/Users/renhao/renquant_bundles/g4-modal-smoke-20260727/ (§2 of the
prereg). Budget machinery (bt#81+#82) merged with its own test suites
(434 passed incl. the $25/2900 worked example and the budget-contract
drift matrix).

## NEXT
Codex review → merge = freeze → phase 1 (3 pods, ~40 min) → gate → phase
2 (40 pods) → local calibrators → total report → follow-up sim prereg.
