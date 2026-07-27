# G4 XGB rerun — amendment 2 (batch-2 void + tax-fixed base)

## STATUS
delivered

## WHAT
Preregistration amendment only; NOTHING RUNS BEFORE MERGE. Voids batch 2
(kernel integrity guard stopped seed 101 at bar 2025-06-24:
sell_economic_gaps — real tax-netting bug, deterministic across seeds) and
re-freezes on the fixed base: umbrella 15c218e7 (#532) with pipeline
dbcab26 (#217) committed in-lock; backtesting/common worktree-local rows
unchanged; bundle/guard/offline/all other rules stand verbatim.

## WHY/DIR
The batch's persistence-ON path executed validators the --no-persist
weekly gate never runs, exposing a latent live fail-close risk
(compute_disposed_lot_tax taxed gain-lots without same-event loss
netting). Fixed in both kernel copies (codex-approved #217/#532),
validator untouched. Prereg discipline: defect ⇒ void ⇒ fix ⇒ amendment ⇒
fresh smoke ⇒ re-freeze.

## EVIDENCE
Batch-2 crash forensics (MA lot pair verified to 10 decimals; zero RNG on
the decision path ⇒ deterministic); fix PRs merged with 16 pinned tests
per repo incl. the exact MA case (tax must be 0.0); Smoke C on the new
base: PREFLIGHT OK → 10 bars/121 models → POST-RUN OK, exit 0, value
identical to Smokes A/B; guard also caught the intermediate re-provision
state (337 mismatches) before any run.

## NEXT
Codex review → merge = freeze → launch batch 3 (5 seeds, ~2–4 h) →
bar-2025-06-24 validator-clean confirmation → per-seed post-steps →
total report → model#64 re-review.
