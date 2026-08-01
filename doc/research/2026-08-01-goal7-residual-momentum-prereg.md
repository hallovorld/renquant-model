# PREREG (FREEZE CANDIDATE) — standalone residual-momentum: one run, one verdict

**Frozen on merge of this PR. No IC, no score, no label statistic may be computed for
this study before that merge.** The design was reviewed to approval as model#161; the
inference method's construction protocol as model#162. This document resolves every
constant both left open, and nothing else — where it and #161 disagree, THIS document
governs.

## 0. Known-trap checklist (each names a measured failure this design must not repeat)

| trap | guard here |
|---|---|
| overlapping-label naive t (killed model#124/#128/#135) | worst-case calibrated bar, §4; no N/h anywhere |
| permutation null's wrong width (model#153: real ρ₁ 0.82–0.975, permuted ≈0) | permutation is centring-only, never width |
| Bartlett L=h−1 oversized (probe + independent audit: size 0.117 @ nominal .05) | L = 59 AND empirically calibrated bar, §4 |
| "both bars published" as pseudo-control (codex on #162) | precommitted worst-case rule, §4.3 |
| running before freezing (Stage-0's own reverted violation) | §7 execution gate |
| same-name-different-object labels | §2 pins the label constructor quote and file digests at run time |

## 1. Candidate (all constants FROZEN here)

Residual momentum, exactly as approved in #161 §2: rolling OLS of daily dividend-adjusted
TR returns on SPY-TR over `t−273…t−21` (window **252**, skip **21**, min obs **200**);
score = `Σε/(σ_ε·√N)`; per-date cross-sectional z. Feature family F1–F5 as approved
(§2b), composite `S` = equal-weight z-mean over available features, **≥3 of 5** required,
ETFs carry no F3.

**The 43 no-dividend-column names are DECLARED non-payers `[假设, frozen]`.** Direction
of error if false for any name: its TR and hence its momentum is understated — a bias
AGAINST the candidate, acceptable to freeze. The sector map is
`data/ticker_sectors.json`, snapshot `as_of 2026-05-18`; its sha256 is recorded by the
runner at execution and the snapshot-PIT limitation is inherited as stated in #161.

## 2. Data (pinned by digest at run time)

Panel `data/alpha158_291_fundamental_dataset.parquet` (2,599 dates, 292 names; labels
per-date z-scored price-return excess vs SPY — constructor quoted in #161's AC4 comment;
Spearman is invariant to the z-scoring; the dividend omission inside the label is a
recorded limitation biasing against payers). OHLCV per-name parquets. Eligible dates:
formation-feasible dates only (measured ≈2,150); names/date floor **50**; the runner
records every exclusion count.

## 3. Estimands

* **E1 (decision):** mean per-date Spearman IC of `S` vs `fwd_20d_excess`, all eligible
  dates. h=20 declared from theory in #161; h=60 descriptive only.
* **E2 (parsimony):** paired per-date `ΔIC = IC(S) − IC(F1)`.
* Per-feature ICs: Bonferroni α/5 diagnostics, never decision inputs.

## 4. Inference — the #162 protocol, instantiated and closed

1. **Statistic pipeline `T`:** HAC-t (Bartlett, **L = 59**) on the per-date series, via
   `renquant_common.metrics.hac_se.hac_t_stat(lag=59)` (measured equal to the frozen
   SE_HAC formula; model#159).
2. **Admissible generator family (the frozen DGP argument):** the momentum IC series'
   dependence has two named sources — label overlap (MA(19) **by construction** of a
   20-day forward label) and signal persistence (a 252-day formation window advancing
   one day at a time, an AR-type component). The family is therefore
   `{overlap-MA(19) variance-matched, AR(p) fitted per #162 §2 with p ≤ 20}` — both
   sources represented, neither assumed away. This argument is the one #162 requires a
   consumer to freeze; it is hereby frozen.
3. **Bar (precommitted worst-case, closing the stress path):**
   `t* = max(t*_MA, t*_AR)` at **α = 0.05 two-sided**, each `t*` the seeded 95th
   percentile of |T| under its generator (≥5,000 reps, seed **20260801**, n = the
   realized eligible-date count). AR adequacy envelope: max abs ACF deviation over lags
   1…40 ≤ 2 plug-in SEs; **if the AR fit fails adequacy, the family collapses to
   {overlap-MA(19)} and `t*` = t*_MA alone, with the failure printed** — the collapse
   rule is frozen now so no run-time judgement exists.
4. **Validation gates (all must pass before any verdict is read):** positive control
   (committed pure-noise series must not reject at ≈α); machinery self-check (#162 §4);
   both `t*` values and the realized ACF published regardless of outcome.
5. **Decision:**
   * `H1`: mean IC(S) ≥ **+0.04** AND `|T|` ≥ t\* AND placebo mean |IC| < **0.01**
     (5 within-date permutation draws, centring only) → RETAIN-to-shadow; else KILL.
   * `H2` (only if H1 passes): if `ΔIC`'s HAC-t < t\* (family adds nothing) AND F1
     independently satisfies the full H1 criterion → deploy F1; else deploy S.
   * `UNRESOLVED-METHOD` if any validation gate fails; `UNRESOLVED-POWER` if the
     realized `MDE = t*·SE_HAC` exceeds **0.06** (a bar that cannot be met by a
     plausible effect must be said, not run through).
6. KILL and UNRESOLVED are reportable outcomes with the same prominence as RETAIN.

## 5. What RETAIN licenses — and does not

RETAIN licenses a SHADOW lane only, subject to orch#699's four mechanical preconditions
and pipeline dependency D1 (formula artifact kind), per #161 §4. It does not touch the
WF gate, capital admission, or any production surface. Nothing here changes the live
book.

## 6. Multiplicity ledger

Decision tests: **2** (H1 on S; H2's ΔIC). Bonferroni within the decision family:
α/2 each side of t\* derivation? No — frozen simpler and stricter: both H1 and H2 are
tested at the SINGLE worst-case t\* derived at α = 0.05/2 = **0.025** per test. The
seeded calibration uses the 97.5th percentile accordingly. Diagnostics (5 features,
h=60, ACF plots) carry no α budget; they decide nothing.

## 7. Execution gate

The runner may execute only after: (a) this PR is merged unmodified; (b) the runner PR
itself is merged; (c) the run is a single invocation, its full JSON output committed
verbatim (quarantine-on-invalid per the v1-v2 precedent). Any deviation = the run is
VOID and says so.

## Not claimed

That the candidate will pass — the local prior is unfavourable and KILL is expected
under that prior. That the worst-case family covers nonlinear/regime dependence beyond
its two named sources — #162's own limit, inherited; if the realized ACF shows structure
neither generator expresses (adequacy failure AND MA-inconsistency, printed by the
runner), the honest outcome is UNRESOLVED-METHOD, and §4.3's collapse rule does not
override the positive-control gate.
