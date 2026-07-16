# G4: correct the Phase A audit — PatchTST persistence already exists (shadow DB)

Date: 2026-07-16

## What

Appends a same-day CORRECTION to
`doc/research/2026-07-16-g4-phase-a-data-audit.md` (merged this morning as
model#58): the audit's blocker ① claimed PatchTST per-date score persistence
does not exist, based on querying only the prod arm DB (`runs.alpaca.db`).
The daily shadow e2e has been persisting PatchTST per-date scores to
`data/runs.alpaca_shadow.db` since 2026-05-19 — 15 `hf_patchtst` dates,
continuous per-session since 06-25 (verified read-only and independently
reproduced by the reviewer).

## Corrected blocker chain

1. ~~Persistence wiring~~ → the real gap was `.pt` checkpoint provenance,
   fixed by RenQuant#484 (merged 2026-07-16)
2. PIT parity ledger (§5.1) — unchanged, still missing
3. ~560-session evidence volume — unchanged, still binding; both experts
   now accrue forward
4. NEW: `backfill_scores.py` must support the shadow DB as the PatchTST
   expert source

## Why a correction, not a silent edit

The memo is merged evidence referenced by the BLOCKED verdict. The verdict
stands; the actionable path changed. Future readers need both the original
error and the verified correction in one place.
