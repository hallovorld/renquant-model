# Relocate capacity + power reconciliation memo from orchestrator#575

STATUS:    in-progress; round-1-4 findings addressed below
WHAT:      Relocates the capacity/power research memo
           (`doc/research/2026-07-24-capacity-and-power-reconciliation.md`,
           §1-7) and its committed evidence bundle
           (`doc/research/evidence/2026-07-24-capacity-memo/` — 5 analysis
           scripts + 6 result JSONs) from `hallovorld/renquant-orchestrator#575`
           into this repo. This is NOT a byte-identical move — the final
           diff also: (1) `depth_probe.py`, `horizon_matched.py`,
           `structural_decomposition.py`, `feature_redundancy.py` no longer
           hardcode an agent-session scratch path (`/private/tmp/claude-502/
           ...`) — `SCRATCH`/`S` now default to the script's own directory
           and are overridable via `CAPACITY_MEMO_OUT`; `DD`/`RQ` have no
           default and now require `RQ_DATA_DIR`/`RQ_UMBRELLA_ROOT` to be
           set explicitly (round-4 fix below — no machine-specific default
           path). `structural_decomposition.py` also gained a
           REPRODUCIBILITY GAP docstring note: its two inputs
           (`scores_real.parquet`, `scores_placebo.parquet`) come from an
           ad hoc scoring pass that was never itself committed as a script,
           so they are not regenerable from this bundle alone — the note
           states the exact recipe (arm/label/folds/embargo/seeds) needed
           to reproduce them. (2) the memo's §3 TC-lever row and §4 point 3
           no longer claim "zero statistical risk" for the TC 0.4→0.7
           lever — both now read as a conditional scenario pending a
           precommitted execution/P&L validation, per review finding 3 on
           orchestrator#575's first review round. (3) §7.4's exit-stack
           counterfactual — implementation, memo section, and its
           `amputation_per_pos` result key — was REMOVED entirely (round-2
           BLOCKER 3 below); no stop-layer cost claim survives anywhere in
           this repo. (4) the memo's Status line and §4 header/framing were
           downgraded from "decision-grade synthesis" / "what this memo
           recommends" to explicit non-authorizing hypotheses (round-4 fix
           below), since §4's program-priority language leans on live-book
           and TC inputs this repo does not version or reproduce.
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
    prod or exp:   experiment, read-only, no writes. DGTW (test 1) and
                   dispersion (test 2) are measured on cached production
                   scores from an ad hoc pass not committed as a script
                   (see reproducibility caveat below). The exit-stack
                   counterfactual (test 3) was REMOVED per round-2 finding
                   3 below — it read production `strategy_config.json` and
                   OHLCV directly, outside this repo's boundary; no
                   stop-layer claim survives in this repo or this doc.
    existing data: none prior — first DGTW characteristic-matched
                   decomposition on this book
    best-known?:   DGTW adjustment is the standard skill/characteristic
                   separation (Daniel-Grinblatt-Titman-Wermers 1997); first
                   application on this book
    scope:         "DGTW skill +0.243/60d block-t=+2.92 (winsorized
                   t=+1.70 — certification is tail-dependent), a CANDIDATE
                   finding pending reproduction of its score inputs (memo
                   §7 header, §7.1); dispersion-scaled sizing is a
                   hypothesis, not a certified lever, same caveat (memo
                   §7.3). No stop-layer cost claim — §7.4 was removed."
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

## Round 3 review finding addressed

4. BLOCKER — this doc's own §7 EVIDENCE block still described the removed
   TEST 3 (production `strategy_config.json`/OHLCV) and the retracted
   "stop-layer cost −2.69pp/position/60d" number, contradicting round-1-2
   finding 3 immediately above it in this same file. Rewrote the §7
   EVIDENCE block's `prod or exp` and `scope` lines to match the memo's
   current §7 content exactly (test 1/2 only, test 3 removed, no
   stop-layer claim). Also softened memo §7.3's "dispersion-scaled
   position sizing is a live, observable lever" to a candidate hypothesis
   pending reproduction — it does not drive a sizing recommendation,
   matching the same pending-reproduction caveat already applied to §7.1.

## Round 4 review findings addressed

5. MED — all 5 evidence scripts still defaulted `RQ_DATA_DIR` /
   `RQ_UMBRELLA_ROOT` to the operator's absolute umbrella path
   (`/Users/renhao/git/github/RenQuant[/data]`) when the env var was unset,
   contradicting this doc's own "env-overridable, repo-local defaults"
   claim (this repo does not contain the umbrella's `data/` dir, so that
   default only ever worked on one machine). Removed the machine-specific
   default from all 5 scripts (`audit_my_experiment.py`, `depth_probe.py`,
   `horizon_matched.py`, `structural_decomposition.py`,
   `feature_redundancy.py`); `RQ_DATA_DIR`/`RQ_UMBRELLA_ROOT` are now
   required and each script raises `SystemExit` with a clear message if
   unset. `CAPACITY_MEMO_OUT`/`SCRATCH` are unaffected — those already
   defaulted to the script's own directory, which is genuinely repo-local.
6. BLOCKER — this doc's WHAT field still summarized the relocation as
   "byte-identical except [path/TC wording]" although the final diff also
   removed the entire §7.4 exit-stack implementation, script section, and
   result key (round-1-2 finding 3) — a change the WHAT field only surfaced
   later, in the round-1-2 findings appendix, not in the top-level summary
   itself. Rewrote WHAT to state directly that this is not a byte-identical
   move and to list the exit-stack removal as one of its four changes.
7. HIGH — the memo's Status line labeled it a "decision-grade synthesis"
   and §4 was headed "What this memo recommends," while §4's program-
   priority claims (stop feature archaeology; TC/horizon lever priority;
   book-size framing) lean on live-book stats and a TC figure that this
   doc's own EVIDENCE block already says are cited to external sources,
   not versioned or reproduced in this repo. No source run bundle for
   those inputs exists to attach in this fix cycle, so downgraded rather
   than fabricated a manifest: the Status line now states the
   reproducibility scope explicitly (§1 IC_clean and §6 depth-probe are
   in-repo reproducible; live-book/TC/§7 are not) and says §4 is
   non-authorizing; §4's header changed to "What this memo's evidence
   suggests — non-authorizing hypotheses" with an explicit lead-in
   sentence, and each of its 4 points was reworded from an imperative
   ("Stop feature archaeology", "Say the quiet part") to a hedged
   conclusion ("looks like a low-value use of effort", "if the cited
   live-book stats hold up"). No numeric content in §1-6 changed.

Tests: `../RenQuant/.venv/bin/python -m py_compile
doc/research/evidence/2026-07-24-capacity-memo/audit_my_experiment.py
doc/research/evidence/2026-07-24-capacity-memo/depth_probe.py
doc/research/evidence/2026-07-24-capacity-memo/feature_redundancy.py
doc/research/evidence/2026-07-24-capacity-memo/horizon_matched.py
doc/research/evidence/2026-07-24-capacity-memo/structural_decomposition.py`
passed. Manually verified the new fail-closed path: running
`audit_my_experiment.py` with `RQ_DATA_DIR` unset exits 1 with
"RQ_DATA_DIR must be set to the RenQuant umbrella repo's data/ dir" instead
of silently reading the operator's machine. No pytest suite references
these evidence scripts (research artifacts, not production code).
