# Results — horizon × features × regime factorial: ALL SEVEN REGISTERED TESTS NULL

Date: 2026-07-25
Prereg (FROZEN LAW): `doc/research/2026-07-24-factorial-horizon-features-regime-prereg.md` (model#67, merged)
Executor: `scripts/research_factorial_hfr.py` at the model#71 fix (anchor at its own 60d eval, gate-first)
Evidence: `doc/research/evidence/2026-07-25-factorial-hfr/factorial_hfr_result.json` (frozen analyzer's own verdict bundle)

## Verdict — NULL ×7 [VERIFIED], per the frozen analyzer

Anchor reproduced to four decimals (+0.0489 vs +0.0488 expected). All 24
cells trained; 15 specialist-fold fallbacks per specialist cell (as the
prereg's estimability table predicted).

| registered test | stat | p (primary block) | p (2× block) | Holm reject |
|---|---|---|---|---|
| I1 H×R | +0.0053 | 0.833 | 0.824 | no |
| I2 F×R | −0.0002 | 0.973 | 0.973 | no |
| I3 H×F | +0.0042 | 0.531 | 0.525 | no |
| M1 H | −0.0035 | 0.684 | — | no |
| M2a dedup_r70 vs all_172 | +0.0031 | 0.564 | — | no |
| M2b nontechnical_14 vs random_14 | **−0.0125** | 0.256 | — | no |
| M3 specialist vs pooled | +0.0045 | 0.420 | — | no |

## Pre-committed reading (prereg §5, verbatim consequence)

**"All interactions null ⇒ the OFAT reads are rehabilitated."** The earlier
one-factor studies' conclusions stand as scoped: the regime-selection NULL,
the horizon comparisons, and the feature-count question are NOT confounded
by detectable H×F×R interactions at this corpus's resolution.

Secondary notes, read per the frozen rule (main effects only after their
interaction resolves — all resolved null):

- **M2b is the sharpest**: the 14 fundamental/event columns underperform 14
  RANDOM columns (ns) — consistent with D3's standing "selection adds
  nothing over random shrink" prior, and a clean negative under the PIT
  cloud (base-data#51): look-ahead in those columns would have biased this
  arm UP, and it still lost to random.
- M3 ≈ 0 closes the loop on this session's opening question: regime
  specialists do not pay on this panel, now confirmed inside the production
  harness with the production regime labeller.
- The whole H×F×R space is flat at resolution ~±0.01-0.02 — reinforcing the
  capacity memo's allocation: structural levers (objective change
  [model#70 CONFIRMED], TC, participation gating) over H/F/R rearrangement.

## Run integrity

Run 1 (2026-07-25, earlier) VOIDed spuriously on the anchor-horizon wiring
bug (model#71); its 24 printed cell summaries are QUARANTINED. This run is
the first readable execution. The two runs' cell tables are numerically
identical where visible — the bug was in the gate, not the cells — but the
quarantine stands on principle: only this run's numbers are citable.

## Boundaries

Survivorship panel; clean-IC response at the fwd_20d primary eval;
BULL_VOLATILE/CHOPPY not registrable (precommitted); 3 seeds; one model
family. NULL here means "no effect ≥ ~0.01-0.02 detectable", not "exactly
zero".
