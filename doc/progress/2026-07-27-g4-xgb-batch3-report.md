# G4 XGB rerun — BATCH 3 TOTAL REPORT (the first admissible corpus)

## STATUS
delivered

## WHAT
Batch 3 executed 2026-07-27 15:51–17:53Z under the model#78 + #79 + #80
frozen matrix (amendment-2 base): 5 seeds {101–105}, 27-month single-leg
WF sims (2024-01-02→2026-03-28, 561 bars each), driver-enforced input
bundle guard + offline proxy, per-seed forward-return backfill, frozen
model#65 converter (9b4970cb). TOTAL reporting, nothing withheld:

| seed | bars | score rows | integrity | bundle guard pre/post | converter |
|---|---|---|---|---|---|
| 101 | 561 | 61,249 | all OK incl. bar 2025-06-24 | OK / OK | 561 wrote / 0 rejected / 496 admitted |
| 102 | 561 | 61,249 | all OK | OK / OK | 561 / 0 / 496 |
| 103 | 561 | 61,249 | all OK | OK / OK | 561 / 0 / 496 |
| 104 | 561 | 61,249 | all OK | OK / OK | 561 / 0 / 496 |
| 105 | 561 | 61,249 | all OK | OK / OK | 561 / 0 / 496 |

- **Bar 2025-06-24 verdict (amendment-2 §3 expectation): PASS** — the bar
  that killed batch 2 logged `decision trace integrity OK` on every seed;
  the tax-netting fix (#217/#532) is confirmed live in the executing
  kernel.
- **65 unadmitted dates per seed** = the window tail whose 60d forward
  labels have not matured — inadmissible by the label-horizon gate, by
  design, not a defect.
- **Cross-seed identity**: all five seeds produced IDENTICAL corpora
  (row counts and ledger sizes byte-equal) — expected and now measured:
  the decision path consumes no RNG (batch-2 forensics); the frozen seeds
  differentiate only downstream bootstrap statistics. Cross-seed variance
  of the corpus itself is exactly zero; this is a REPORTED property, not
  a defect, and future power analyses must not treat the five corpora as
  independent draws.
- Honest note: seed 105's converter first ran against its MID-RUN DB (a
  sequencing mistake — converters must wait for sim completion); the
  partial result was discarded and the converter rerun on the completed
  DB, matching the other seeds exactly. No influence on the sim itself
  (its outputs are identical to the other seeds').

## WHY/DIR
This is the evidence codex required across model#64/#65: generation-time
provenance (wf_sim_provenance.v1, two-phase, exact ledger↔DB cover),
consumed by the converter as the only identity source, produced under a
five-round-reviewed frozen preregistration. The corpus is the XGB half of
the Phase-A input requirement. All outputs remain `EXPLORATORY_ONLY`
(hard cap); no G4 disposition is taken or implied.

## EVIDENCE
Archive (worktree + scratchpad, retained): per-seed
`data/sim_runs_seed<S>.db`, `data/wf_provenance/wfsim-*.jsonl`
(1,108,468 B each, 561+561 records), `logs/seed<S>.log`,
`logs/verify_seed<S>.txt` (INPUT BUNDLE PREFLIGHT/POST-RUN OK),
`logs/verify_preflight.txt` (VERIFY OK: 4429 files), converter outputs +
`build_manifest_xgb.json` per seed under `phase_a_batch3/`. Frozen input
bundle `/Users/renhao/renquant_bundles/g4-rerun-inputs-20260727`
(root `8072ca77…aea1`) untouched throughout (post-seed guard re-runs).

## NEXT
model#64 re-review with this corpus (its last blocker was "new generated
evidence passes end-to-end"); PatchTST half proceeds under its own prereg
(Modal train-only ≈$17 within the operator's $20 cap + local calibrators);
Phase-A evaluation only via the standing frozen machinery.
