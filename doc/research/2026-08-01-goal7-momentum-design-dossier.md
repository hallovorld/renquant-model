# GOAL-7 momentum design dossier — the complete design/evidence/reference index

**Purpose (operator directive, 2026-08-01):** *preserve the design documents and
references* for the standalone momentum model line. This dossier is the single
committed index: every design document, every frozen rule, every data artifact,
every measured negative, and the external literature each design choice leans on.
It ADDS nothing normative — where it and a frozen prereg disagree, the prereg
governs. Update it by PR whenever the chain gains or closes a document.

## 1. The frozen chain (v1: standalone residual momentum)

| artifact | where | status |
|---|---|---|
| Design (candidate + estimand) | model#161 (review-approved design PR) | merged |
| Inference construction protocol | model#162 | merged |
| **Prereg (all constants frozen)** | `doc/research/2026-08-01-goal7-residual-momentum-prereg.md` (model#164) | **FROZEN on merge** |
| Amendment 1 (prior; F1 exact α-t) | `…-momentum-prereg-amendment-1.md` (model#168) | merged |
| Amendment 2 (bootstrap adequacy) | `…-momentum-prereg-amendment-2.md` (model#170) | merged |
| Amendment 4 (gate replacement: per-member own-bar rates) | `…-momentum-prereg-amendment-4.md` (model#172) + `doc/research/data/2026-08-01-goal7-a4-validation/` | merged |
| Amendment 3 re-proposal (§2 resolves through the fingerprint manifest) | model#176 | in review |
| Runner re-proposal (verify-then-read resolution) | model#177 (supersedes closed #169) | draft, flips on #176 merge |
| Input identity manifest (294 files, per-file sha256) | `renquant-base-data` `manifests/momentum-prereg-inputs-20260801.json` (base-data#60) | merged |
| Durable input store | `~/renquant-data-store/momentum-prereg-inputs-20260801` — 294/294 digests re-verified at publication, frozen read-only (`chmod -R a-w`) | published |

Verdict rules (frozen before any run): single `--execute`, one JSON verdict;
RETAIN licenses **shadow only** (orch#699 + decision D1 — never a direct live
path); KILL closes v1 honestly and the negative is published. The A4 validation
bundle measured the machine's calibrated bars (MA 0.0236 / AR 0.0274) and showed
the negative controls are caught (A 0.0945, C 0.0765; B disclosed as no-teeth).

## 2. Measured negatives that shaped the design (do not re-learn these)

| finding | where | design consequence |
|---|---|---|
| Canonical price-trend has no stable multi-day edge (all 5 canonical signals fail the 20/60d bar) | orchestrator memory + screen docs | plain `ret(k)` arms are calibration references, never candidates |
| Dividend-tilt: removing the tilt made total-return momentum WORSE at all 4 horizons | `doc/research/2026-07-30-momentum-total-return-prereg.md` + `doc/research/data/2026-07-30-momentum-total-return/` | dividend adjustment is load-bearing; the 43 no-dividend names are verified non-payers, frozen in prereg §2 |
| Momentum-family screen: the operator-preferred pure-momentum arm did not survive the traded-estimand check | `doc/research/2026-07-29-momentum-family-screen.md` | v1 candidate is RESIDUAL momentum, not raw momentum |
| Vol-conditioned momentum-reversion screen | `doc/research/2026-07-29-vol-conditioned-momentum-reversion-screen.md` | kept as a v-next direction, not folded into v1 |
| Two-sided tail prereg + horizon prereg | `doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md`, `…-momentum-horizon-prereg.md` | horizon and tail treatment are frozen inputs to v1, not free parameters |
| Intraday (phase −1) net edge negative (−6.4bps @ IC 0.03) | orchestrator research ledger | v1 is close-to-close multi-day; no intraday claim |

## 3. External literature grounding (why each design choice looks the way it does)

Residual momentum (the v1 candidate):
- Blitz, Huij & Martens (2011), *Residual Momentum*, Journal of Empirical
  Finance — momentum on factor-regression residuals; roughly halves the risk of
  total-return momentum and weakens the crash profile. The direct ancestor of
  v1's rolling-OLS-vs-SPY residual score `Σε/(σ_ε·√N)`.
- Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling Losers*,
  Journal of Finance — the original cross-sectional momentum estimand and the
  skip-month convention (v1's skip 21).
- Carhart (1997), *On Persistence in Mutual Fund Performance*, Journal of
  Finance — momentum as a priced factor (UMD); why a standalone momentum model
  must beat its own factor-replication references, which our screens enforce.

Risk and failure modes (why RETAIN → shadow only):
- Daniel & Moskowitz (2016), *Momentum Crashes*, Journal of Financial
  Economics — momentum's left tail is regime-conditional and violent; a fresh
  momentum book must first be observed in shadow across a regime change.
- Barroso & Santa-Clara (2015), *Momentum Has Its Moments*, Journal of
  Financial Economics — volatility-managing momentum tames the crash profile;
  the vol-conditioned v-next direction in §2 is this idea on our panel.
- Novy-Marx (2012), *Is Momentum Really Momentum?*, Journal of Financial
  Economics — intermediate-horizon (12-7) vs recent-horizon momentum; motivates
  keeping horizon a FROZEN choice, not a fitted one.

Breadth and construction:
- Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*, Journal
  of Finance — momentum's cross-asset robustness and its covariance with value;
  relevant when the panel-signal book and a momentum sleeve later coexist.
- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, Journal of
  Financial Economics — time-series (own-return) momentum as the distinct
  cousin; v1 is cross-sectional, and the distinction is why M-arm replication
  references exist in the family screen.
- Ehsani & Linnainmaa (2022), *Factor Momentum and the Momentum Factor*,
  Journal of Finance — much of stock momentum is factor momentum; a v-next
  candidate direction if v1's residual construction leaves edge on the table.

These are the canonical, widely-reproduced entries; none is claimed as evidence
our implementation works — our evidence is exclusively the frozen-prereg chain
in §1 and the measured record in §2.

## 4. Where decisions stand

Operator directives on record: 2026-07-29 *"我其实更偏向动量模型"* (preference
that started GOAL-7); 2026-08-01 *"肯定不放弃！继续探索继续研究"* (RELOCATE
executed, chain continued); 2026-08-01 *"保留设计文档和reference…行业领先…你有
权限做任何决策"* (this dossier; full delegation of research-line decisions).
Delegation is exercised WITHIN the standing discipline: frozen prereg decides
the verdict, negatives are published, RETAIN reaches shadow first, and no gate
is forced. That discipline is what makes a positive result mean something.

Roadmap: v1 verdict (this chain) → if RETAIN: shadow deployment design PR; if
KILL: v-next from §2's kept directions (vol-conditioned momentum-reversion,
factor-momentum residualization), each through the same freeze-then-run door.
