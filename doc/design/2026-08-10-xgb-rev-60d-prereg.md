# xgb_rev_60d — prereg: the reversal twin of xgb_mom_60d

STATUS: frozen before any run. This is a DESIGN DOC ONLY: no harness code
exists for this model yet, no run has happened, and no number in this doc
was computed from the label. NO RUN HAPPENS UNTIL THIS PR MERGES; the
execution harness lands as a SEPARATE follow-up PR whose every constant is
bound to this frozen text (feature list + sha, fold table, params, seed
tuple, corpus pin), mirroring `doc/design/frozen/2026-08-09-xgbmom-v2-harness.py`
and its committed verifier. xgb_rev_60d is the reversal TWIN of
xgb_mom_60d prereg v2 (`doc/design/2026-08-09-xgb-mom-60d-prereg-v2.md`,
model#213): every element except the feature list — folds, purge rule,
params, seeds, guards, the four PASS/KILL legs, the corpus pin, the
machine-surface rules — is inherited verbatim from that frozen doc.

## 1 · The frozen features — the ONLY element that differs from the momentum twin

**Hypothesis.** Mean-reversion-flavored windowed statistics — deviation of
price from its own recent anchor, plus the volume/volatility conditioning
under which liquidity-provision returns concentrate — carry cross-sectional
information about `fwd_60d_excess` that is complementary to the momentum
twin's trend/extremum families. Brief literature grounding: short-horizon
past-return reversal (Jegadeesh 1990; Lehmann 1990) and long-horizon
overreaction (De Bondt & Thaler 1985); reversal profits as compensation
for liquidity provision, increasing in volatility (Nagel 2012, RFS);
return autocorrelation more negative after high-volume sessions
(Campbell, Grossman & Wang 1993, QJE), and reversal concentrated in
high-turnover/less-liquid names (Avramov, Chordia & Goyal 2006, JFE).
Hence: deviation-from-anchor families (MA, RESI), trend-quality/staleness
families that mark choppy regimes where reversion dominates (RSQR, IMXD),
price-volatility conditioning (STD), price–volume interaction (CORR,
CORD), and volume level/volatility/direction conditioning (VMA, VSTD,
WVMA, VSUMP, VSUMN).

**Direction semantics, recorded before the run.** The learner is XGBoost
`rank:pairwise`, which fits sign from data; "reversal" names the feature
semantics (deviation-from-anchor + liquidity-provision conditioning), NOT
a hard sign constraint. No column is negated, and the gate rewards only
real-minus-shuffle signal, not any particular learned direction.

**Expectation-setting, recorded before the run.** The classical reversal
horizon is days-to-one-month; at a 60-trading-session label the prior is
WEAK and KILL is the expected outcome. No gate moves because of that
expectation.

**Selection rule (frozen; the table below is its complete output, not a
menu).** Take every alpha158 windowed family present in the corpus that is
(a) DISJOINT from the momentum twin's 14 frozen families
(BETA/CNTN/CNTP/IMAX/IMIN/MAX/MIN/QTLD/QTLU/RANK/ROC/RSV/SUMN/SUMP), and
(b) not an exact linear difference of columns frozen in either twin:
CNTD (= CNTP − CNTN) and SUMD (= SUMP − SUMN) are excluded because their
legs are momentum-frozen; VSUMD (= VSUMP − VSUMN) is excluded because its
legs are in THIS list — the momentum twin set this same keep-P/N-drop-D
convention `[DERIVED — Alpha158 formula sheet identities; the momentum
list keeps CNTP/CNTN/SUMP/SUMN and none of the D differences]`.
Single-day K-bar shape columns (KMID/KLEN/KMID2/KUP/KUP2/KLOW/KLOW2/
KSFT/KSFT2) and normalized level columns (OPEN0/HIGH0/LOW0/VWAP0) are
excluded: they are not windowed family statistics and sit outside the
twin structure. Fundamental/news columns are excluded: the twin contract
is price/volume-only, like the momentum twin. That leaves exactly
**12 families × the same 5 windows (5/10/20/30/60) = 60 columns**.

| family | Alpha158 construction (standard) | reversal role |
|---|---|---|
| MA | Mean(close,w)/close | price displacement vs its own w-day mean — the deviation-from-anchor core |
| RESI | Resi(close,w)/close | residual off the fitted linear trend — de-trended displacement |
| RSQR | R² of the linear trend fit | low R² = choppy, weakly-trending regime where reversion dominates |
| STD | Std(close,w)/close | price volatility — Nagel (2012) conditioning |
| IMXD | (idx(max) − idx(min))/w | staleness/ordering of the window's extremes |
| CORR | Corr(close, log(volume+1), w) | price–volume level correlation — CGW (1993) conditioning |
| CORD | Corr(Δclose ratio, Δvolume ratio, w) | price-change–volume-change correlation |
| VMA | Mean(volume,w)/volume | volume level vs its own mean |
| VSTD | Std(volume,w)/volume | volume volatility |
| WVMA | volume-weighted price-change volatility | turbulence of volume-weighted moves |
| VSUMP | volume-up share (volume analog of SUMP) | directional volume pressure, up leg |
| VSUMN | volume-down share (volume analog of SUMN) | directional volume pressure, down leg |

Family constructions above are the standard Alpha158 formulas `[DERIVED —
the corpus is the alpha158 builder's output; the schema pins names, not
formulas]`. Every EXISTENCE claim is checked against the corpus itself:
all 60 columns below are present in
`data/alpha158_291_fundamental_dataset.parquet` (178-column schema), the
momentum twin's 70 are present, the overlap between the two lists is
empty, and the label `fwd_60d_excess` is present `[VERIFIED — read from
the parquet schema via pyarrow.parquet.read_schema, 2026-08-09]`.

**The frozen 60-column list** (alphabetical = harness embedding order,
same convention as the momentum harness; no alternatives exist):

```
CORD10, CORD20, CORD30, CORD5, CORD60,
CORR10, CORR20, CORR30, CORR5, CORR60,
IMXD10, IMXD20, IMXD30, IMXD5, IMXD60,
MA10, MA20, MA30, MA5, MA60,
RESI10, RESI20, RESI30, RESI5, RESI60,
RSQR10, RSQR20, RSQR30, RSQR5, RSQR60,
STD10, STD20, STD30, STD5, STD60,
VMA10, VMA20, VMA30, VMA5, VMA60,
VSTD10, VSTD20, VSTD30, VSTD5, VSTD60,
VSUMN10, VSUMN20, VSUMN30, VSUMN5, VSUMN60,
VSUMP10, VSUMP20, VSUMP30, VSUMP5, VSUMP60,
WVMA10, WVMA20, WVMA30, WVMA5, WVMA60
```

`features_sha256 = 256496c2e34dedb8599aaa06bf7d4dc69c4dd3795cd8b00032f113db4f365eed`
`[DERIVED — sha256(json.dumps(FEATS)) over the alphabetical list above,
the identical convention the momentum harness persists]`. The follow-up
harness MUST embed this list verbatim and persist this exact hash in
every control and result artifact.

Label: `fwd_60d_excess` (same as the momentum twin) `[VERIFIED — present
in the parquet schema]`.

## 2 · The folds — inherited verbatim from mom v2 §1 `[DERIVED — gap ≥ 90 calendar days > the ~84-day realization window of a 60-trading-day label]`

Train ends 12-31; test starts 04-01 of the following year (gap 91 calendar
days), test ends 12-31 of that year. Eight folds:

| fold | train | test |
|---|---|---|
| 1..7 | 2016-01-01..YYYY-12-31 for YYYY in 2018..2024 (expanding) | (YYYY+1)-04-01..(YYYY+1)-12-31 |
| 8 | 2016-01-01..2025-12-31 | 2026-04-01..2026-05-07 (corpus end; ~26 sessions — the min_test=100-row guard applies and fold 8 drops out if unmet, COUNTED) |

The shuffle placebo runs on the SAME folds. No other calendar freedom
exists.

## 3 · Run-time integrity duties — inherited verbatim from mom v2 §2

0. **PER-ROW PURGE IS THE GUARANTEE** — the calendar gap in §2 is design
   intent, not the enforcement. The follow-up harness computes every
   training row's realized label endpoint as the 60th trading session
   after its date ON THE CORPUS'S OWN CALENDAR and drops any row whose
   endpoint is not strictly before the fold's test start (a row whose
   endpoint falls beyond the corpus end is treated as +inf and purged);
   fold-wise purge counts and the max surviving endpoint are persisted in
   the result artifact.
1. The harness asserts the corpus sha256 ==
   `870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e`
   BEFORE reading (the momentum twin's pin, unchanged — the identical
   corpus file).
2. The result JSON carries `corpus_sha256`, the literal fold table,
   `features_sha256` (== §1's hash), `artifact_kind`
   (`"control"`/`"result"`), and `admissible_verdict` — **null until
   review confirms**. A committed fail-closed verifier (the follow-up
   PR's twin of `doc/design/frozen/2026-08-09-xgbmom-v2-verify.py`) exits
   1 if a non-null verdict appears without this doc's literal
   counter-signature line
   `COUNTERSIGN: <artifact-name> admissible_verdict=<verdict>` — the
   model#210/#212 machine-surface rule. The same verifier also enforces,
   on every control and result artifact: the frozen feature-list sha256,
   the literal fold table, the per-fold purge endpoints strictly before
   each test start, the corpus pin, and the gate arithmetic recomputed
   from the artifact's own numbers.
3. Pre-run synthetic controls (positive planted + null) run under THESE
   folds and THIS feature list, and their JSONs are committed with the
   harness before any real run. The planted signal is frozen HERE so the
   harness has no freedom:
   `signal = 0.35*RESI20 + 0.25*CORR60 + noise` (the same 0.35/0.25
   shape as the momentum controls, on two columns from §1's frozen
   list). Positive control must PASS the gate, null control must KILL,
   hard exit codes; the purge machinery must be exercised (endpoints
   computed and bounded per fold).

## 4 · Gates — the same four legs, arithmetic inherited verbatim

Computed on real-minus-shuffle per-fold signal (seed-mean over the frozen
seed tuple), exactly as the momentum harness implements:

1. Seed-mean real signal > 0;
2. **≥6 positive folds OF THE FIXED 8 — an unrealized fold (fold 8
   failing its min-test guard) counts NON-POSITIVE** (NaN > 0 is false),
   so missing data can only cost a shot at the bar, never lower it;
3. A/A seed std ≤ 0.01 across seeds (42, 43, 44);
4. recency guard on the recent folds (test years 2024/2025/2026),
   verbatim from the momentum harness: the leg fails only when the SOLE
   recent support is the short 2026 stub (fold 8 positive while the 2024
   and 2025 folds are non-positive).

Frozen training constants, identical to the momentum twin:

```
PARAMS = {objective: rank:pairwise, eta: 0.05, max_depth: 5,
          min_child_weight: 50, subsample: 0.7, colsample_bytree: 0.7,
          nthread: 10, verbosity: 0}
SEEDS = (42, 43, 44); num_boost_round = 100
MIN_TRAIN = 1000 rows; MIN_TEST = 100 rows (fold dropout guard)
label clip ±5; per-fold train-fitted z-score, clip ±5; fillna(0);
placebo = per-DATE label permutation on the same folds;
per-day cross-sectional Spearman IC, days with ≥5 names.
```

PASS earns a shadow-candidacy memo gated on orch#937/#931 (the momentum
twin's rule, unchanged); KILL is a completed outcome and closes the line.

## 5 · Freeze clause — no sweeps; deviations void the run

There are NO alternative feature lists, windows, families, labels,
params, seeds, folds, thresholds, or control recipes: this doc is the
complete specification and §1's table is its only feature set. Exactly
ONE real execution is authorized, after (a) this PR merges and (b) the
follow-up harness PR — carrying the harness, verifier, fail-closed tests,
and both control JSONs — merges bound to this text. Any deviation from
this doc (column set, fold calendar, purge rule, params, seed tuple,
gate arithmetic, corpus pin, control recipe) VOIDS the run; a voided run
is not evidence and cannot be republished as diagnostic support. Runner
guards are prereg content: every fold-defining and admission-defining
constant lives in this frozen table, not in run-time judgment.
