# G4 Phase 0 data audit — Phase A BLOCKED verdict

STATUS: delivered
WHAT: Read-only audit of `runs.alpaca.db` against the frozen
v2-block-rebalance Phase A requirements. Verdict: Phase A is BLOCKED on
evidence volume — 64 total live-run dates (15 XGB panel-expert dates, 1
PatchTST date) vs ~560 admissible sessions required by the frozen 8-block ×
(60+10)-session design; PatchTST additionally lacks the §5.1 PIT parity
prerequisite. Full findings, including the new fact that `run_bundle_json`
carries reconstructable `trained_date` + artifact-digest provenance since
2026-05-21 (contradicting the blanket MISSING claim in `backfill_scores.py`
for that window), are in
`doc/research/2026-07-16-g4-phase-a-data-audit.md`.
WHY/DIR: G4 is the top-priority goal; the design's own go/no-go tree
requires a documented BLOCKED report when Phase 0 prerequisites fail,
instead of forcing an underpowered comparison. This memo is that report and
defines the ordered blocker chain (shadow-score persistence → PatchTST PIT
parity → forward accumulation or re-registration decision).
EVIDENCE: SQL audit queries against
`file:/Users/renhao/git/github/RenQuant/data/runs.alpaca.db?mode=ro&immutable=1`
(read-only, immutable); counts reproduced in the research memo tables.
NEXT: (1) shadow-score persistence wiring PR (umbrella/pipeline ownership);
(2) design-level decision on 2027-horizon vs re-registration vs pseudo-OOS
reconstruction — requires its own design PR; (3) `backfill_scores.py`
enhancement to reconstruct provenance from `run_bundle_json` for the
2026-05-21+ window (model-repo, small, non-blocking).
