# renquant-model · agent review prompt

You are reviewing a pull request against the `renquant-model` repo,
which houses RenQuant's model families (GBDT panel-LTR for production,
PatchTST / sequence family as candidates, linear baselines, PatchTSMixer).

## Repo-specific review focus

In addition to the umbrella's [default review prompt][upstream] (CLAUDE.md
§7 engineering principles), pay special attention to:

1. **Model-aware artifact identity** — every persisted artifact must
   include a `kind` field that `scorer.load` dispatches on
   (`hf_patchtst` / `hf_patchtsmixer` / `dlinear` / `nlinear`). Filenames
   follow the same prefix. PRs that add a model family MUST also
   register a `hf_<name>` entry-point in `pyproject.toml` under
   `[project.entry-points."renquant_common.scorers"]`. See PR #17 / #18
   review history for past defects.

2. **Effective vs requested feature flags** — `BuildSummaryTask` /
   `PersistModelTask` MUST stamp the EFFECTIVE flag values
   (`uses_distributional_head`, `uses_film_regime`, `uses_cross_stock_attn`)
   based on what the model actually wires, NOT the requested values in
   `args.*`. PatchTSMixer ignores PatchTST-only flags by construction;
   stamping requested-value would lie in the artifact contract.

3. **Placebo gate machinery** — every research run produces shuffle +
   timeshift placebo trials. Cross-split-leak (PR #9) is fixed; future
   placebo work must not regress. Look for changes to `--shuffle-labels`
   / `--label-shift-days` paths that could leak across train/val
   boundaries.

4. **Multi-seed for noise sensitivity** — PatchTST smoke is flaky at
   single-seed (~50% placebo gate fail). Any PR that adds a smoke or
   research path should default to ≥3 seeds OR explicitly justify
   single-seed as a machinery-only smoke (not a model-quality gate).

5. **Detector version** — explicit `--detector-version` CLI flag in
   research.py / hf_trainer.py. PR-touching code that calls
   `compute_hmm_regime_labels` MUST thread `detector_version=` through
   from the harness's `ExperimentSpec` field. Hard-coded
   `"v2026-05-31"` overriding the library default is OK during the
   migration window but flag any drift.

## Output format

Same as umbrella default: ONE consolidated PR review comment with
findings ordered BLOCKER > HIGH > MED > LOW, each with severity +
location (`file:line`) + evidence + smallest concrete fix.

[upstream]: https://github.com/hallovorld/RenQuant/blob/main/.github/agent-review-prompt.md
