# L3 meta-label classifier — prereg execution attempt: NO ADMISSIBLE VERDICT

The 2026-08-09 execution of `doc/design/2026-08-09-l3-classifier-prereg.md`
(v1, model#207) as amended by `…-prereg-v2.md` (v2, model#208) is recorded
here as **exploratory diagnostics only**. It does NOT count as the prereg's
one execution and records **no PASS/KILL verdict**: the L3 hypothesis —
whether the panel's entry quality is predictable from these entry-time
features — remains UNTESTED under prereg discipline. model#209 remains an
execution block.

## 0 · Admissibility — why this run cannot carry the prereg verdict

Two defects, both established in codex review on PR #210, make this run
inadmissible as the frozen prereg's single execution:

1. **Leg 3 is not aligned with the frozen target.** The prereg trains on
   candidate-level `win = fwd_20d > 0` with mean `fwd_20d` uplift as the
   primary metric (v1 §2) and scopes sell-side use OUT (v1 §6). But the
   frozen 34-row external list mixes evaluation horizons and actions — buy
   {1d: 12, 5d: 10, 10d: 10} plus sell {1d: 2} `[VERIFIED — committed
   external CSV key field, recomputed this session]` — and the runner
   scores raw `trade_evaluations.fwd_return` on that population with no
   20-day alignment and no sell-direction mapping. This is the same label
   mismatch tracked in model#209. Leg 3's −0.0454 is a number about a
   different question, not evidence for or against the prereg target.
2. **Fold-defining guards were not frozen before execution.** The runner
   introduces `min_train=300`, `min_test=50`, `min_pre_dates=60`,
   `min_selected=10`, and a fixed quarterly boundary grid starting
   2024-07-01 (`data/2026-08-09-l3-experiment-run.py`). None of these
   appear in v1 or v2; they determine the nine realized folds and are the
   direct reason the declared live-only arm yields zero folds (§4). They
   were execution-time implementation choices — a pre-run control script
   does not retroactively preregister them.

The committed `…-l3-exp-summary.json` records the frozen four-leg gate
ARITHMETIC as `"as_run_gate_arithmetic": "KILL"` with
`"admissible_verdict": null` plus an admissibility note; the verifier
reproduces the arithmetic and itself exits 1 if the summary ever records
an admissible verdict. No committed machine surface encodes a prereg
verdict, and this record makes no KILL (and no PASS) claim. The measured
values are unchanged and the CSV artifacts remain byte-identical to the
run.

What a valid fresh prereg must freeze BEFORE its single execution: a
target-aligned external test (candidate-level `fwd_20d` temporal holdout,
or a prospective external set aligned to the training target and buy-side
scope), the exact fold calendar, every guard
(min-train/test/pre-dates/selected) and the undefined-selection rule —
then execute once.

Reproducibility of the diagnostics: `data/2026-08-09-l3-experiment-run.py`
(the run script; re-checks the frozen CSV hash `eecfd050…` at start) ·
committed outputs `…-l3-exp-folds-all.csv`, `…-l3-exp-placebo.csv`,
`…-l3-exp-external.csv`, `…-l3-exp-pooled-predictions.csv`,
`…-l3-exp-summary.json` · `data/2026-08-09-l3-exp-verify.py` recomputes all
four leg numbers from the committed artifacts alone and exits 1 on drift
`[VERIFIED — run this session, exit 0; it prints the as-run gate
arithmetic KILL explicitly marked INADMISSIBLE as a prereg verdict]`.

## 1 · The four legs — diagnostic arithmetic, not a verdict `[VERIFIED — summary JSON + verifier recomputation]`

| leg | frozen bar | measured | gate arithmetic | admissible? |
|---|---|---|---|---|
| 1 · fold consistency | median uplift@τ=0.5 > 0 AND ≥⅔ folds > 0 | median **+0.0017** (+17bp/20d), share **0.667** (6/9, exactly ⅔) | pass — marginal | folds depend on unfrozen guards (§0.2) |
| 2 · placebo | median > within-date-shuffle p95 (200 seeds) | +0.0017 > **0.0000** | pass — near-vacuous (§3) | same fold caveat |
| 3 · external (once-only, frozen 34 rows) | uplift ≥ 0 | **−0.0454** on the 4/34 rows clearing τ=0.5 | fail | **NO — target-misaligned (§0.1)** |
| 4 · calibration | pooled slope ∈ [0.5, 2.0] | **−0.0008** | fail | pooled predictions inherit the unfrozen fold scheme |

Under the frozen gate these four results evaluate to KILL, but per §0 that
evaluation is not an admissible prereg outcome and is not recorded as one.

## 2 · What the diagnostics suggest (hypothesis-generating only)

The most informative number is the calibration slope ≈ **0**: across 5,492
pooled out-of-fold predictions, the fitted P shows no relationship to
realized wins. Per-fold AUC agrees — 9 folds range 0.41–0.62 around 0.5,
and the descriptive depth-2 GBDT does no better (0.48–0.60) `[VERIFIED —
folds CSV]`, so "logistic too small" is not the obvious out. These are
diagnostics over folds built with unfrozen guards (§0.2); they motivate the
next prereg's design, they do not settle the hypothesis.

Mechanically, the model collapses toward the base rate: with base win rate
0.63, most predictions sit just above 0.5, so τ=0.5 selects 80–100% of each
fold's rows (e.g. 559/614, 777/792, 471/471). The "uplift" then measures the
exclusion of a small low-P tail — a +17bp/20d effect with no calibration
behind it. The one large fold (+2.8%, 2026-04, 253/1,730 selected) is the
only fold where the model discriminated at all, and it is a single fold in a
live-heavy quarter.

## 3 · Annotations on the two arithmetically-passing legs

* **Leg 2's bar was degenerate at this configuration.** 165 of the 200
  placebo runs produced a median uplift of EXACTLY 0.0 — a shuffled-label
  model predicts ≈ the base rate for every row, τ=0.5 selects everything,
  and the uplift is identically zero. The placebo p95 is therefore 0, and
  "beat the placebo" reduces to "excluded anything at all". A future prereg
  should place τ relative to the base rate (the v1 design took τ=0.5 as
  neutral; with base 0.63 it is not).
* **Leg 1 sits exactly on its own edge**: share-positive is 6/9 = 0.667, the
  frozen minimum, and the median is +17bp against a 20-day horizon whose
  cross-sectional σ is ~12% — indistinguishable from noise without leg 4's
  support, which the arithmetic fails.

## 4 · The declared live-only variant: NOT EVALUABLE

The v1-declared live-only training variant produced **zero folds**: the live
slice spans 40 dates, and the runner's guards (≥60 pre-boundary dates, ≥300
training rows — unfrozen, per §0.2) are unreachable inside it. The variant
is reported as unevaluable rather than silently skipped —
`…-folds-liveonly.csv` is empty by measurement, not omission. Any live-only
re-attempt needs a redesigned, PRE-FROZEN fold scheme in a new dated
prereg.

## 5 · External detail (the once-only read)

The frozen 34-row list resolved exactly (34/34, no drift — the feasibility
verifier's funnel re-confirmed pre-run). Walk-forward fold models scored all
34; 4 cleared τ=0.5; those 4 underperformed the 34-row mean by −4.5pp
`[VERIFIED — external CSV]`. Beyond the small-n / 3-run-date / correlated-
horizon caveats both prereg versions stated, §0.1 applies: the population
mixes 1/5/10-day horizons and includes sells, and `fwd_return` is not the
training target — so this number is not usable for the prereg question in
either direction. The once-only trade_evaluations outcome read has now been
spent on a misaligned population; a fresh prereg needs a fresh, aligned
external design.

## 6 · What this record does and does not show

* It does NOT show the L3 hypothesis is dead — no admissible verdict was
  produced, and the hypothesis remains untested under prereg discipline.
* The diagnostics (slope ≈ 0, AUC ≈ 0.5, base-rate collapse at τ=0.5) are
  genuine warning signs for THESE 4 entry-time features (panel_score, mu,
  rank_score, n_candidates_that_date) on this history — input to the next
  design, not a conclusion.
* Not that the panel is broken — the panel's own edge is not at issue; its
  entry-quality PREDICTABILITY from its own emitted scalars is.
* Not a license to iterate inside this prereg: v1's clause binds — no
  feature additions, no threshold moves. Any new attempt (τ relative to
  base rate, features from a repaired producer stamp, a live-only-feasible
  fold scheme, a target-aligned external leg) is a NEW dated prereg.

## 7 · Consequence for the three-layer machine

L3 still does not earn a shadow lane — not because a KILL was recorded, but
because no admissible PASS exists and none can come from this run. The
allocation machine's value continues to rest on L1 (exposure control,
shadow-deployed, first row 2026-08-10) and L2 (allocation engine,
backtested + cost-passed, merged). The L3 slot stays empty until a fresh,
correctly-frozen prereg passes — an empty slot is a valid state of the
design (orch#918 §3 scoped L3 as an independent, severable layer).

## Corrections (visible, per LONG row 10)

* Earlier revisions of this record (and PR #210's original title/body)
  claimed "one execution, zero deviations", "executed exactly as frozen",
  and "Verdict: KILL". All three are RETRACTED per codex review on PR #210:
  leg 3 was target-misaligned (§0.1), fold-defining guards were not frozen
  (§0.2), and consequently no prereg verdict — KILL or PASS — is recorded.
  The measured numbers themselves are unchanged and remain reproducible
  from the committed artifacts.
* A further codex finding on PR #210 (at `db59069`): the machine-readable
  artifacts still encoded the retracted verdict as canonical — the summary
  JSON's `"verdict": "KILL"` field, the verifier's printed "verdict KILL",
  and the run script's "the ONE execution of the frozen prereg" header.
  All three surfaces were re-labelled fail-closed: the summary now stores
  `"as_run_gate_arithmetic": "KILL"` + `"admissible_verdict": null` + an
  admissibility note, the verifier prints INADMISSIBLE wording and exits 1
  if an admissible verdict is ever recorded, and the run-script header
  states the re-scope. Measured values unchanged; CSV artifacts remain
  byte-identical to the run.
