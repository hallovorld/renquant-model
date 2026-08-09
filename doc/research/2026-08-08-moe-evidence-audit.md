# MoE evidence audit: no alpha claim is justified yet

**Status: exploratory audit, not a model-selection or promotion result.** This
report tests whether the available evidence supports the proposition that the
current MoE/combiner programme adds alpha to the panel champion. It does not.
The report is intentionally useful when the answer is negative: it separates
what was measured from what would have to be true before another combiner is
worth building.

## Decision

**Keep the panel scorer as champion. Do not deploy a regime/sector MoE, a
learned gate, or an equal-rank panel/classifier blend.** The evidence supports
neither incremental IC nor a cost-aware top-N return claim. A classifier tail
overlay remains a hypothesis only, subject to a new, prospectively frozen
experiment.

This is not a claim that mixtures of experts cannot work in finance. It is a
claim about the present book, inputs, and evidence quality.

## What is already decisive

### 1. The sector x regime route is not estimable

The original 15-sector x 4-regime routing proposal has regime-level effective
sample sizes of about 2--3 for BEAR, BULL_VOLATILE, and CHOPPY. A 60-cell
routing table cannot be estimated on that amount of date-level information.
The revised design records this explicitly and correctly excludes C4 on
arithmetic grounds, not taste. See the canonical design's
[combiner ladder](https://github.com/hallovorld/renquant-orchestrator/blob/main/doc/design/2026-08-07-moe-revision-2-power-and-membership.md#7-combiner-ladder-ordered-by-what-the-data-can-afford).

### 2. The frozen 75/25 slow-momentum blend was independently rejected

The point-in-time, label-interval-purged confirmatory record has 278 retained
paired dates. Its governed row reports mean incremental IC `-0.0108`, adjusted
t `-0.72`, and a block-bootstrap interval `[-0.0250, +0.0024]`. The implied
economics are `-33.7 bps`, and the blend's mean IC is below panel. This is a
proper negative result: the 33-date diagnostic generated the hypothesis, and
the later confirmation rejected it without trying replacement weights. The
inputs and CSV-only verifier are in the canonical
[S10 confirmatory record](https://github.com/hallovorld/renquant-orchestrator/blob/main/doc/research/2026-08-08-moe-s10-confirmatory-kill.md).

### 3. The earlier three-member ensemble evaluator was not sensitive enough

The prior 508-date, 60-day-block ensemble test is **VOID**, rather than a null
result: its frozen positive control could not detect a realistic injected
increment. At an injected realised IC near `0.05`, the measured t statistic was
only `+0.53`; even an injected `0.12` did not meet the predeclared threshold.
That is a property of the evidence instrument, so it cannot certify any real
combiner. The persisted
[result](data/2026-07-30-goal4-phase0-ensemble-gain/results.json) and
[power probe](data/2026-07-30-goal4-phase0-ensemble-gain/control_power_probe.json)
are the governing sources.

## Independent panel/classifier re-analysis

`tools/moe_evidence_audit.py` is a new, read-only recalculation of the panel
and certified top-decile-classifier corpora. It is deliberately simpler than a
production experiment:

* It joins the scores by the same `(date, ticker)` and evaluates **both** arms
  against the panel corpus's `fwd_60d_excess` label only.
* It compares panel, classifier, and a zero-free-parameter equal-weight blend
  of their within-date percentile ranks.
* It reports daily cross-sectional Spearman IC and the average realised panel
  label of the top three names.
* It forms only complete, chronological 60-date blocks and drops the final
  partial block. The resulting t statistics are descriptive; there is no
  selected winner, confidence pass, cost model, or promotion claim.

Run it against the exact local panel input named in the output:

```bash
../RenQuant/.venv/bin/python tools/moe_evidence_audit.py \
  --panel ../RenQuant/data/exp/oos_pick_table_recipe_v2.parquet
```

The committed output is
[the audit JSON](data/2026-08-08-moe-evidence-audit.json). Its input SHA-256s,
coverage, label-vintage differences, and all reported aggregation conventions
are carried in the file rather than asserted in prose.

| increment versus panel | all-date mean | complete 60-date block mean | block SE | descriptive t | result |
|---|---:|---:|---:|---:|---|
| classifier IC | -0.0225 | -0.0266 | 0.0106 | -2.51 | worse on this fixed IC target |
| equal-blend IC | -0.0090 | -0.0106 | 0.0080 | -1.33 | no incremental IC support |
| classifier top-3 panel-label outcome | -0.1227 | -0.1709 | 0.1799 | -0.95 | no tail-return support |
| equal-blend top-3 panel-label outcome | +0.0497 | +0.0395 | 0.0653 | +0.60 | hypothesis only; not detectable |

There are eight complete blocks (480 dates); 28 dates are deliberately
dropped rather than treated as a ninth, smaller independent observation. The
classifier and panel rank correlation is `0.7190`: diversity exists, but it
does not translate into a supported IC improvement. The apparent top-three
improvement is directionally interesting but has neither adequate precision
nor a turnover/cost model, so it cannot be called alpha.

### Interpretation rule

The classifier is meaningfully different from panel, but difference is only a
precondition for alpha. The audit shows whether that difference improves a
fixed target on the shared corpus; it does **not** use the observed values to
select a weight, a sector, a regime, or a deployment rule. Any positive
top-three observation without a cost model and an adequately powered,
prospective confirmation is not an alpha claim.

The two stored `fwd_60d_excess` columns are highly rank-correlated but not
byte-identical. The audit records the magnitude and frequency of material
differences. This means all future comparisons must freeze one label source and
its content digest before fitting or scoring.

## Is a better alternative practical?

Yes, but not as another MoE. The only technically defensible candidate is a
**constrained tail overlay**:

1. Keep panel as the base ranking.
2. On each date, residualise classifier rank against panel rank, so the
   candidate can use only information not already expressed by panel.
3. Fit one non-negative, strongly zero-shrunk overlay coefficient *inside each
   training fold only*. No sector table, regime gate, or weight grid is
   permitted.
4. Score an embargoed validation fold with the trained coefficient; when the
   coefficient is zero, the result is mechanically identical to panel.
5. Evaluate one prospectively frozen primary: top-N **net** return at the
   actual holding horizon. IC non-inferiority, turnover, capacity, and a
   synthetic positive control are mandatory guards, not secondary charts.

The economic rationale is narrow: the exploratory audit can reveal a
classifier/panel disagreement at the top of the ranking even when full-list IC
does not improve. That is relevant to a top-N book, but is not evidence that
the disagreement is profitable. The residual construction avoids claiming that
regime or sector membership has been learned from an unidentifiable number of
state transitions.

It is **not ready to run as a confirmation experiment** until the evaluator
first demonstrates power at a predeclared minimum economically material effect.
The prior positive-control failure proves that the existing 60-day ensemble
instrument does not meet that bar. A replacement must either use a justified,
matching 20-day label and adequate independent blocks, or collect additional
unseen history. A `H=60` evaluation with only eight complete blocks cannot
answer a small-increment question reliably.

## External evidence and its limits

* The finance-specific AlphaMix paper presents a two-stage expert/router
  architecture with positive results on its own US and China datasets. It is
  motivation for testing a mechanism, not evidence for this book or this
  route: its universe, data, labels, and router differ materially.
  [Sun, Wang, and An (2022)](https://arxiv.org/abs/2207.07578)
* General MoE theory finds that gating choice and overspecification affect
  sample efficiency. That reinforces the penalty for adding a gate when the
  available effective sample is tiny; it does not create financial alpha.
  [Nguyen, Ho, and Rinaldo (NeurIPS 2024)](https://proceedings.neurips.cc/paper_files/paper/2024/hash/d65befe6b80ecf7f180b4def503d7776-Abstract-Conference.html)
* Dynamic model averaging is a valid online model-uncertainty method, but it
  needs a frozen forgetting rule and realized, delayed outcomes. It is not a
  free alpha source, and a top-N implementation must charge switching costs.
  [Raftery, Karny, and Ettler (2010)](https://sites.stat.washington.edu/people/raftery/Research/PDF/Karny2010.pdf)
* Searching many weights, gates, and slices on one financial backtest makes
  apparently strong configurations easy to manufacture. This is why the report
  treats every currently observed alternative as hypothesis-generating only.
  [Bailey et al. (2014)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)

## Bottom line

There is data supporting a **negative** conclusion: the current MoE claims are
not sufficiently identified, the only frozen slow-blend confirmation failed,
and the legacy broad-ensemble evaluator lacked sensitivity. There is data
supporting one limited research hypothesis: classifier information may affect
the top of the panel ranking. There is no data supporting a claim of incremental
alpha, a regime/sector gate, or deployment.
