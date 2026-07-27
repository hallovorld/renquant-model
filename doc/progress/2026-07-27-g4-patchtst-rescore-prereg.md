# G4 PatchTST rescore — preregistration PR

## STATUS
delivered

## WHAT
Preregistration only; NOTHING DISPATCHES BEFORE MERGE. Frozen matrix for
the 43-fold Modal T4 train-only rescore (code 9942bce6, recipe
b4e47e2cd77af660, timeout 7200, quarantined scratch namespace) + local
8-way calibrator leg; $20 HARD cap with a 3-pod projection tripwire and
halt-on-any-failed-fold; expected terminal signature exit 1 +
failed_folds=[] (the #76 diagnostic quarantine, i.e. SUCCESS here).

## WHY/DIR
The PatchTST half of the G4 Phase-A corpus, under the operator's
2026-07-27 <$20 Modal grant. With-calibrators-on-Modal measured over cap
($25.4+ right-censored lower bound); train-only ($16.8 projected) +
local calibrators keeps the complete corpus within the cap.

## EVIDENCE
Probe (train 2388.1s, calibrator right-censored at 3600s,
FunctionTimeoutError verbatim) and pre-freeze smoke (1/1 fold, 2384.41s
cuda, checksum sha256:8a926df3bb9e4a66, AC7 PASS, exact quarantine
signature) both on the frozen code path; spend to date $1.45 of $20.

## NEXT
Codex review → merge = freeze → dispatch 43 folds (~40 min wall-clock,
parallel pods) → cost tripwire after 3 pods → local calibrators → total
report → follow-up sim prereg (PatchTST analog of batch 3).
