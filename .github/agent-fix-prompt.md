# renquant-model · agent fix prompt

You are addressing review findings on an open PR in the `renquant-model`
repo (model families: GBDT panel-LTR, PatchTST, PatchTSMixer, DLinear,
NLinear). The reviewer's comments are appended at the bottom.

## What to do (in this order)

1. **Read every finding.** Don't skip or reorder.

2. **For each finding**: identify the smallest concrete change that
   resolves it. Read the surrounding code first (`Read`, `git log`),
   then `Edit` / `Write`. NEVER change unrelated code in the same
   pass — keep blast radius small.

3. **Run tests** that cover the changed code path:

   ```bash
   PYTHON=/Users/renhao/git/github/RenQuant/.venv/bin/python
   $PYTHON -m pytest tests/patchtst/ -q       # or tests/gbdt/ / tests/linear/
   ```

   If a test exists targeting the changed area, run it. If no test
   exists for what you changed, ADD ONE per CLAUDE.md §7.1 (every fix
   has a paired test).

4. **Commit** with a clear message naming each finding addressed:

   ```
   fix(<scope>): address review findings #1, #3

   ... brief explanation of what was changed for each ...

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   ```

5. **Push** with `--force-with-lease`. The wrapping workflow posts a
   summary comment via `gh`.

## Repo-specific fix gotchas (renquant-model)

In addition to umbrella defaults (CLAUDE.md §7 invariants), watch for:

1. **Model-aware artifact identity** — every model family has a `kind`
   field that `scorer.load` dispatches on. PRs adding a model family
   must register a `hf_<name>` entry point in `pyproject.toml` under
   `[project.entry-points."renquant_common.scorers"]`. See PR #17 / #18
   for past defects.

2. **Effective vs requested feature flags** — `BuildSummaryTask` and
   `PersistModelTask` MUST stamp EFFECTIVE flag values
   (`uses_distributional_head`, `uses_film_regime`, `uses_cross_stock_attn`),
   not the requested ones from `args.*`. PatchTSMixer ignores
   PatchTST-only flags by construction.

3. **Placebo cross-split-leak** — `--shuffle-labels` / `--label-shift-days`
   paths MUST NOT leak across train/val boundaries (fixed in PR #9).
   Any fix touching the placebo machinery needs to re-verify.

4. **`--detector-version` threading** — research code calling
   `compute_hmm_regime_labels` must thread `detector_version=` through
   from `ExperimentSpec`. Hardcoded `"v2026-05-31"` is OK during the
   migration window; flag drift.

## What you MUST NOT do

- No drift fixes (only the reviewed findings)
- No untested changes (CLAUDE.md §7.1)
- No silent skips — if a finding can't be addressed, say so explicitly
- No new dependencies unless the reviewer requested

## Tools available

`Bash`, `Edit`, `Write`, `Read`, `gh`, `git`. The wrapping workflow
posts a summary comment automatically — you don't need to `gh pr
comment` manually unless that step is disabled.

---

## Reviewer feedback to address

(Auto-appended by the workflow.)
