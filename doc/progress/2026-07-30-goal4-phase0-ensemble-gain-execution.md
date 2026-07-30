# Progress: GOAL-4 Phase-0 ensemble-gain screen — VOID

STATUS:   delivered (execution of a pre-merged FREEZE, this PR). Verdict
          WITHHELD pending adversarial review (§7) — appended below once
          commissioned. Provisional verdict from the frozen harness: VOID,
          on the §5.1 positive control (construction assertion fails AND
          the control is not detected).

WHAT:     Executes `doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md`
          (renquant-model#114, frozen, merged before this PR) literally.
          Adds `tools/goal4_phase0_manifest.py` (§2.5 sealed source
          manifest) + `tools/goal4_phase0_run.py` (§3-§6: combination,
          estimator, critical value, controls, decision rule) +
          `doc/research/2026-07-30-goal4-phase0-ensemble-gain-results.md`
          (bottom-line writeup) + `doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/`
          (sealed manifest, results.json, run.log, per-date CSVs, README
          with the full identity/label-provenance disclosure).

WHY/DIR:  GOAL-4 has had zero acceptance-criterion-gated work for weeks
          (see the prereg's own §0); this screen was the first thing
          registered against it. The result is VOID, not GO/NO-GAIN/
          UNRESOLVED: the §5.1 positive control (a synthetic member with
          population Spearman IC=+0.05 by closed-form construction,
          combined equal-weight with the benchmark) fails BOTH its
          construction assertion (realised mean IC 0.03681, outside
          [0.04,0.06]) AND detection (|t|=0.099 vs T_crit=2.3646) — per
          the frozen text, α is NOT adjusted and the screen VOIDs. This is
          a genuine, diagnosed property of the frozen construction at
          realistic cross-sectional width (~141 names/day): the
          rankit/arcsin closed form the prereg specifies is asymptotic
          (n->infinity) and has real finite-sample bias at this n — an
          isolated Monte-Carlo check of the identical construction (no
          real data) shows E[realised IC]~=0.042 at n=140, itself
          borderline. GOAL-4 remains undefined-by-evidence: this screen
          did not run to a verdict on the ensemble question, it found the
          screen itself under-powered at the frozen construction. No
          substitute statistic, threshold, or relaxed tolerance was
          used — VOID is reported as VOID.

EVIDENCE: artifact: `doc/research/2026-07-30-goal4-phase0-ensemble-gain-results.md`
                    + `doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/`
                    (this PR), on `renquant-model` branch
                    `g4/phase0-ensemble-gain-execution-90978` off
                    `origin/main` @ `cc77ccf`. Reproduced by:
                      `python3 tools/goal4_phase0_manifest.py generate`
                      `python3 tools/goal4_phase0_run.py`
                    (both read-only over `/Users/renhao/git/github/RenQuant`
                    and `/Users/renhao/renquant_bundles`; write only under
                    `doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/`).
  prod or exp:      EXPERIMENT. All inputs opened READ-ONLY; sealed
                    manifest re-verified (refuse-on-mismatch) at the top
                    of every run; nothing written outside this branch or
                    outside the output dir.
  existing data:    Yes — §2 identity: prod_XGB and PatchTST have FULL
                    per-fold (43/43) config_fingerprint/checksum
                    verification against their live-served identity
                    (`strategy_config.json` wiring, independently
                    confirmed); certified_clf has a weaker evidence trail
                    (recipe-script sha256 + hyperparameter match, no
                    per-fold digest) -- disclosed, not exclusion-triggering.
                    Label corpus: found and fixed a real ~58.5%-of-rows
                    mismatch between the prod-XGB panel's bundled label
                    and the current, mutually-consistent label vintage
                    (used the latter for ALL members per §4's
                    "same r_{t->t+h}" requirement).
  best-known?:      N/A for a VOID verdict -- no GO/NO-GAIN/UNRESOLVED
                    number is licensed. The main arm's own point estimate
                    (t=-1.0025, N_eval=508, n_blocks=8) is reported per
                    §4's mandate but explicitly NOT adjudicated (§6: VOID
                    supersedes the |t| vs T_crit comparison).
  scope:            `renquant-model` docs + two read-only tool scripts
                    under `tools/`. No production panel, artifact, config,
                    model, or live-surface written. No pin advanced.

NEXT:     GOAL-4's ensemble question remains unanswered. Before re-running
          this exact combination rule, the §5.1 positive control needs a
          registration that accounts for the finite-n bias in the
          rankit/arcsin construction (e.g. target ρ_s empirically
          calibrated at the ACTUAL n via simulation before freezing α, or
          widen the tolerance band with the reasoning stated up front) --
          that is a fresh freeze, not a re-run of this one (§7.4-equivalent
          discipline: a VOID verdict is not revised by changing the
          procedure after seeing the result). Separately, if a future
          registration wants certified_clf's identity evidence at the same
          strength as the other two members, the WF corpus driver
          (`wf_clf_corpus.py`, currently only in scratch bundles, not
          committed to this repo) would need to persist a per-fold
          config_fingerprint the way the XGB/PatchTST WF manifests already
          do.
