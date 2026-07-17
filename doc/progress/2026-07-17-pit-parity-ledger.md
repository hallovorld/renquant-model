# G4: PIT input-parity ledger (design §5.1 admission prerequisite)

STATUS: delivered (tooling + first real backfill); admission verdict = see below
WHAT: `experiments/ensemble_phase0/pit_parity_ledger.py` — one fail-closed
parity verdict per session comparing the prod and shadow arms' run-bundle
INPUT evidence (data-layer universe subset, per-ticker data watermarks,
regime evidence, decision skew ≤ declared tolerance, bundle schema), with
scorer-side fields (artifact hashes, config/watchlist hashes) explicitly
excluded from the verdict as the experimental variable and reported
informationally. As-of run selection reuses `backfill_scores.
select_asof_runs` (same close-anchored cutoff as the canonical validator).
Backfill + single-date CLI; ledger rows to
`experiments/ensemble_phase0/output/pit_parity/*.jsonl`.

## First real backfill (2026-06-22 → 2026-07-17, read-only)

**3/20 sessions parity** (06-25, 06-29, 07-10; skews 1.4–4.5 h within the
same-session tolerance; all input dimensions matched). 1 session missing
the prod side (07-11). **16 sessions fail with
`missing_shadow_run: no as-of-eligible live run` — a STRUCTURAL finding,
not a data defect:** the shadow e2e normally runs post-close (daily_104
Step 4 after the 13:55 PT prod daily), so under the frozen close-anchored
decision schedule its runs are excluded as look-ahead. The prod side
passes only because pre-close INTRADAY runs exist — which are sell-only
runs, not the buy-decision runs either.

## Implication for Phase A admission (honest reading)

Under the frozen US_EQUITY_CLOSE schedule, the shadow expert's evidence is
inadmissible on ~85% of sessions BY TIMING, and the prod runs that DO pass
the cutoff are not the decision-producing runs. The actual daily process
(both arms batch post-close, orders queue for next open) matches a
NEXT-SESSION-OPEN decision instant, under which both arms' post-close runs
would be point-in-time valid with hours of margin. Changing the declared
decision schedule is a DESIGN decision (it changes the scored return
interval), belongs to the same re-registration discussion as the
evidence-volume question (model#58/#59 blocker ③), and is NOT made here.
The ledger machinery is schedule-agnostic and ready for whichever schedule
the re-registration freezes.

## Tests

`tests/test_pit_parity_ledger.py`: 11 — full match; missing run/bundle/
fields fail closed; watermark mismatch; shadow-⊄-prod universe; subset OK;
regime mismatch; schema mismatch; skew boundary (at/over); scorer-side
differences never enter the verdict.
