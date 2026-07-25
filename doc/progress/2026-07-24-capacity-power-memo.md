# Relocate capacity + power reconciliation memo from orchestrator#575

STATUS:    in-progress; round-1-2 findings addressed below
WHAT:      Relocates the capacity/power research memo
           (`doc/research/2026-07-24-capacity-and-power-reconciliation.md`,
           §1-7) and its committed evidence bundle
           (`doc/research/evidence/2026-07-24-capacity-memo/` — 5 analysis
           scripts + 6 result JSONs) from `hallovorld/renquant-orchestrator#575`
           into this repo, byte-identical except: (1) `depth_probe.py`,
           `horizon_matched.py`, `structural_decomposition.py`,
           `feature_redundancy.py` no longer hardcode an agent-session
           scratch path (`/private/tmp/claude-502/...`) — `SCRATCH`/`S` now
           default to the script's own directory and are overridable via
           `CAPACITY_MEMO_OUT`; `DD`/`RQ` are overridable via
           `RQ_DATA_DIR`/`RQ_UMBRELLA_ROOT`. `structural_decomposition.py`
           also gained a REPRODUCIBILITY GAP docstring note: its two inputs
           (`scores_real.parquet`, `scores_placebo.parquet`) come from an
           ad hoc scoring pass that was never itself committed as a script,
           so they are not regenerable from this bundle alone — the note
           states the exact recipe (arm/label/folds/embargo/seeds) needed
           to reproduce them. (2) the memo's §3 TC-lever row and §4 point 3
           no longer claim "zero statistical risk" for the TC 0.4→0.7
           lever — both now read as a conditional scenario pending a
           precommitted execution/P&L validation, per review finding 3 on
           orchestrator#575's first review round. No other numeric or
           analytical content changed.
WHY/DIR:   `renquant-orchestrator`'s review (2 rounds, both BLOCKER) found
           the memo and its evidence scripts are model/strategy research —
           `depth_probe.py` and `horizon_matched.py` import
           `renquant_model_gbdt.panel_data`/`panel_trainer` and train XGB
           cells directly, the same hard-boundary violation as the
           factorial-HFR study relocated in `doc/progress/2026-07-24-
           factorial-horizon-features-regime-prereg.md` (that PR's
           precedent: `renquant-orchestrator/CLAUDE.md` forbids model-
           training internals in the orchestration control plane). Per the
           umbrella multi-repo code-placement rule (model research ->
           `renquant-model`, never the orchestrator), this PR completes
           that move so orchestrator#575 can be reduced to a relocation
           record.
EVIDENCE:
  §1-5 capacity/power:
    artifact:      doc/research/evidence/2026-07-24-capacity-memo/horizon_matched_result.json
                   (matched-embargo IC grid) and
                   doc/research/evidence/2026-07-24-capacity-memo/audit_result.json
                   (self-audit of the retracted precursor study); anchor
                   repro cross-referenced against the relocated factorial
                   executor in this repo (mean_ic 0.0488 vs live artifact
                   0.0533)
    prod or exp:   experiment, read-only. Live-book stats cited from the
                   07-24 daily_104 log (equity $10,609, drawdown 4.23%) in
                   the umbrella repo, not reproduced here.
    existing data: TC=0.4 cited to umbrella
                   doc/research/2026-07-02-ic-ceiling-institutional-gap-107-route.md
    best-known?:   first fundamental-law decomposition of this book;
                   ρ=0.25 is the single assumed number (sensitivity
                   0.15-0.35 reported in-memo, §1)
    scope:         survivorship panel ⇒ all levels are upper bounds;
                   block-t and paired statistics are the robust parts
                   (memo §5)
  §6 signal identity:
    artifact:      doc/research/evidence/2026-07-24-capacity-memo/depth_probe.py
                   and doc/research/evidence/2026-07-24-capacity-memo/depth_probe_result.json
    prod or exp:   experiment, read-only; production recipe (all_172,
                   fwd_60d_excess, rank:pairwise, 5 purged folds, 60d
                   embargo, seeds 42/43/44) rebuilt in-harness, NOT scored
                   from the live artifact's own stored scores
    existing data: none prior — first per-date block-bootstrap decomposition
                   of this recipe's clean IC
    best-known?:   first application of block-mean IR measurement (no
                   breadth assumption) to this book
    scope:         "clean IC block-t=1.15 (n=35, NOT significant at 95%);
                   62% of top-10 spread from names moving >±100%; 2026 YTD
                   clean IC +0.0015" (memo §6.1-6.2)
  §7 structural decomposition:
    artifact:      doc/research/evidence/2026-07-24-capacity-memo/structural_decomposition.py,
                   doc/research/evidence/2026-07-24-capacity-memo/structural_decomposition_result.json,
                   doc/research/evidence/2026-07-24-capacity-memo/placebo_clean_all172.json,
                   doc/research/evidence/2026-07-24-capacity-memo/feature_redundancy_result.json
    prod or exp:   exit-stack counterfactual (test 3) applies PRODUCTION
                   `strategy_config.json` BULL_CALM stop params to real
                   OHLCV paths; read-only, no writes
    existing data: none prior — first DGTW characteristic-matched
                   decomposition on this book
    best-known?:   DGTW adjustment is the standard skill/characteristic
                   separation (Daniel-Grinblatt-Titman-Wermers 1997); first
                   application on this book
    scope:         "DGTW skill +0.243/60d block-t=+2.92 (winsorized
                   t=+1.70 — certification is tail-dependent); stop-layer
                   cost −2.69pp/position/60d is a LOWER bound (model exits
                   excluded)" (memo §7.1, §7.4)
  reproducibility caveat: `structural_decomposition.py`'s two score inputs
    (`scores_real.parquet`, `scores_placebo.parquet`) are not committed and
    not regenerable from a script in this bundle — see the
    REPRODUCIBILITY GAP note added at the top of that file for the exact
    recipe to reproduce them.
NEXT:      None from this relocation PR — the memo authorizes nothing;
           follow-ons live in `research/objective-blend-confirmatory` (this
           repo, #68) and `renquant-base-data#51` (PIT audit). Verdicts,
           when earned, register in this repo's `VERDICTS.md`.

## Round 1-2 review findings addressed

1. MED — `audit_my_experiment.py` still hardcoded 3 paths (2 reads of
   `/Users/renhao/git/github/RenQuant/...`, 1 write to a stale
   `/private/tmp/claude-502/...` scratch path) that the relocation's own
   progress-doc claim said were fixed. Parameterized to the same
   `RQ_DATA_DIR` / `CAPACITY_MEMO_OUT` env-overridable pattern as the other
   4 evidence scripts.
2. BLOCKER — §7's DGTW/dispersion/exit-stack conclusions were stated as
   settled/certified findings while their inputs (`scores_real.parquet`,
   `scores_placebo.parquet`) are not committed and have no producer script
   in this repo (a real reproducibility gap, not fixable without re-running
   an ad hoc GBDT scoring pass this fix cycle does not have the original
   inputs for). Narrowed rather than fabricated a producer: §7's header now
   states the gap up front, §7.1's "certified skill" language is downgraded
   to "candidate, pending reproduction," and §7.2's flat "Recommendation:
   the gate metric should be..." is downgraded to a conditional hypothesis.
3. BLOCKER — §7.4's exit-stack counterfactual script
   (`structural_decomposition.py`) read the umbrella's
   `backtesting/renquant_104/strategy_config.json` and production OHLCV
   directly — backtesting/execution-policy analysis outside this repo's
   GBDT-score/model-analysis boundary. Removed (not narrowed) from both the
   script and the memo, since the code cannot stay here at all under any
   framing. `structural_decomposition_result.json`'s now-orphaned
   `amputation_per_pos` key removed to match — TEST 1 (DGTW) and TEST 2
   (dispersion), which stayed, are unaffected: their two output keys did
   not change. §6.3's "stops amputate the tail" hypothesis, which the
   removed §7.4 had claimed to falsify, is now flagged OPEN in §7.4's
   replacement text rather than left standing as either confirmed or
   falsified — the falsification claim is not reproducible in this repo
   either.

Tests: `../RenQuant/.venv/bin/python -m py_compile
doc/research/evidence/2026-07-24-capacity-memo/audit_my_experiment.py
doc/research/evidence/2026-07-24-capacity-memo/structural_decomposition.py`
passed. No pytest suite references these evidence scripts (research
artifacts, not production code).
