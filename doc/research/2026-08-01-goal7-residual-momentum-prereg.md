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

**The 43 no-dividend-column names (frozen verbatim in §2) are VERIFIED non-payers
`[本次实测 2026-08-01]`:** the vendor's dividend endpoint returns **zero dividend events
since 2016-01-01 for 43/43, 0 query failures**. Same-vendor caveat, stated: this is the
same vendor (yfinance) whose per-file `dividend` column the OHLCV store carries — no
independent vendor exists locally (the TR study measured `adj close` 100% NaN for every
watchlist name carrying it), so a vendor-wide omission would evade this check.
**Precommitted handling:** should any evidence of payment for these names surface before
execution, that name is EXCLUDED by a further visible amendment or the run is
UNRESOLVED-DATA; no directional-bias argument is made (in a cross-sectional rank
statistic the direction of such an error is not identifiable, per review). The sector map is
`data/ticker_sectors.json`, snapshot `as_of 2026-05-18`; its sha256 is recorded by the
runner at execution and the snapshot-PIT limitation is inherited as stated in #161.

## 2. Data — pinned by digest NOW `[本次实测 2026-08-01]`

| input | sha256 |
|---|---|
| `data/alpha158_291_fundamental_dataset.parquet` (2,599 dates, 292 names) | `55811f6387e67411fe11a20eb1d5d929086c5a9dc2675496f3d8592fed2c0dba` |
| `data/ticker_sectors.json` (as_of 2026-05-18) | `ec26bb1efcf8463519366478ae72c933f93c9d110d65f8af1634e2fcbb578d3b` |
| OHLCV combined (sha256 over sorted `ticker:file-sha` lines, **292/292** present) | `4d4638a9f0d69f940fb36a73c28e92883d51b686ab032aebedf559c174c2c1d0` |

Labels are per-date z-scored price-return excess vs SPY (constructor quoted in #161's
AC4 comment; Spearman invariant to the z-scoring; the in-label dividend omission is a
recorded limitation biasing against payers). Eligible dates: formation-feasible only
(measured ≈2,150); names/date floor **50**; the runner records every exclusion count.

**The 43 no-dividend-column names, frozen verbatim:** ABNB, ADBE, AFRM, AMD, AMZN, ANET,
APP, BSX, CMG, COHR, COIN, CRWD, DDOG, DOCU, ESTC, EW, FTNT, GLD, HUBS, ISRG, LITE, MDB,
NET, NFLX, NOW, OKTA, ON, PANW, PCTY, PLTR, RBLX, SHOP, SMCI, SNOW, SOFI, SPOT, TEAM,
TSLA, VEEV, VRTX, WDAY, ZM, ZS.

**UNRESOLVED-DATA rule:** at execution the runner recomputes all three digests and the
43-name list. ANY mismatch → the run completes nothing and reports **UNRESOLVED-DATA**
with the differing digests; proceeding on changed inputs is not an option this document
grants.

## 3. Estimands

* **E1 (decision):** mean per-date Spearman IC of `S` vs `fwd_20d_excess`, all eligible
  dates. h=20 declared from theory in #161; h=60 descriptive only.
* **E2 (parsimony):** paired per-date `ΔIC = IC(S) − IC(F1)`.
* Per-feature ICs: Bonferroni α/5 diagnostics, never decision inputs.

## 4. Inference — the #162 protocol, instantiated and closed

1. **Statistic pipeline `T`:** HAC-t (Bartlett, **L = 59**) on the per-date series, via
   `renquant_common.metrics.hac_se.hac_t_stat(lag=59)` (measured equal to the frozen
   SE_HAC formula; model#159), **pinned to the implementation that will execute**: the
   PINNED runtime copy `.subrepo_runtime/repos/renquant-common/src/renquant_common/metrics/hac_se.py`,
   sha256 `c568ed51428b642c936eda865779b57e0282814f170bb1528e86be2ba9f9b8bc`. The runner
   verifies this digest BEFORE computing anything; mismatch → **UNRESOLVED-DATA** — a
   shared-library change after this merge cannot silently alter the frozen statistic.
2. **Admissible generator family (the frozen DGP argument):** the momentum IC series'
   dependence has two named sources — label overlap (MA(19) **by construction** of a
   20-day forward label) and signal persistence (a 252-day formation window advancing
   one day at a time, an AR-type component). The family is therefore
   `{overlap-MA(19) variance-matched, AR(p) fitted per #162 §2 with p ≤ 20}` — both
   sources represented, neither assumed away. This argument is the one #162 requires a
   consumer to freeze; it is hereby frozen.
3. **Bar (precommitted worst-case, closing the stress path):**
   `t* = max(t*_MA, t*_AR)` at **α = 0.025 two-sided per test** (the §6 Bonferroni split
   of a 0.05 family across the two decision tests), each `t*` the seeded **97.5th
   percentile** of |T| under its generator (**5,000 reps exactly**, seed **20260801**,
   n = the realized eligible-date count). AR adequacy envelope: max abs ACF deviation over lags
   1…40 ≤ 2 plug-in SEs. **If the AR fit fails adequacy, the outcome is
   UNRESOLVED-METHOD** — per #162's governing rule, a family whose persistence member
   cannot be justified does not get to proceed on the overlap member alone; dropping a
   named dependence source is not a fallback, it is an unjustified null.
4. **Validation gates (all must pass before any verdict is read), with frozen
   arithmetic:** each gate runs **5,000 reps** at seed **20260801**; Monte-Carlo
   SE = √(0.025·0.975/5000) ≈ 0.0022; the frozen tolerance is **±3·SE = ±0.0066**.
   * positive control: the committed pure-noise series' rejection rate under the full
     protocol must lie within **[0.0184, 0.0316]**;
   * machinery self-check (#162 §4): series simulated from each admissible generator,
     pushed through the identical pipeline, must reject within the same band;
   * both `t*` values and the realized ACF are published regardless of outcome.
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

Decision tests: **2** (H1 on S; H2's ΔIC), Bonferroni: **α = 0.025 per test**, bars at
the seeded **97.5th percentile** — the single calibration §4.3 specifies; no other α or
percentile appears anywhere in this document. Diagnostics (5 features,
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
