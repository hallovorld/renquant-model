# LATEST_MODELS refresher never writes into a pinned runtime checkout

STATUS:    delivered. Operational fix to a maintenance script + one caller;
           no model, training, serving, or trading-decision change. Nothing
           in the live tree was touched by this PR (the dirty runtime README
           itself is out of scope here and was already clean when checked —
           see EVIDENCE).

WHAT:      * `scripts/refresh_readme_latest_models.py` gains a WRITE GUARD.
             Before touching `--readme` it computes `refusal_reason()`:
             refuse when the README's absolute OR resolved path contains a
             `.subrepo_runtime` component (the umbrella's pinned runtime
             checkouts), or when the nearest containing git checkout
             (`.git` dir or worktree file) has a detached HEAD (a pinned
             checkout is never on a branch). "Cannot tell" (no `git`
             binary, git errors) is ALSO a refusal — the default is closed,
             not open. A README that is in no git checkout at all (scratch
             dirs, pytest `tmp_path`) is not a pinned tree and stays
             writable, so the five pre-existing tests are unchanged.
           * On refusal: exit code 2, one clear `REFUSED to write ...`
             line on stderr naming the reason, and the rendered table on
             stdout — i.e. the script degrades to a dry-run instead of
             mutating the tree.
           * `--dry-run` (new): render to stdout, never write, exit 0; wins
             over `--allow-runtime`. `--allow-runtime` (new): bypass the
             guard — operator use only; no job passes it.
           * Caller in this repo,
             `renquant_model_patchtst/sequence_training.py` (PatchTST
             `RecordTrainingRunJob`): still `check=False`, but now
             captures output and logs one `README refresh not applied
             (rc=..)` warning on non-zero exit, so a refusal is a log line
             rather than a Markdown table in the training log. Behaviour on
             a normal branch checkout is unchanged.
           * `docs/training_pipelines.md` documents the guard and flags.

           Call sites of the refresher (all found by grep, all `check=False`
           subprocess calls, none passes `--allow-runtime`):
             (1) this repo, `renquant_model_patchtst/sequence_training.py`
                 — patched above (`repo = hf.MODEL_REPO`, i.e. the checkout
                 the trainer runs from);
             (2) renquant-orchestrator,
                 `src/renquant_orchestrator/train_gbdt.py:426-435` — the
                 GBDT driver, resolves `parents[3]/renquant-model/README.md`,
                 so from the runtime orchestrator checkout it lands on the
                 runtime MODEL checkout. READ ONLY here (other repo); it
                 needs no change to be safe once this PR's script is
                 pinned, because the refusal is inside the script and the
                 caller already tolerates non-zero. A mirror of the
                 output-capture cosmetic belongs in an orchestrator PR.
             No Make target, launchd plist, or shell wrapper invokes the
             script directly `[VERIFIED — grep over renquant-model,
             renquant-orchestrator, RenQuant (excluding .git/.venv/
             .subrepo_runtime/backtesting bundle copies)]`.

WHY/DIR:   The 2026-08-23 GBDT training run (`training_runs` row
           `20260823170306-panel_ltr_xgboost-a8cffc`, run_date
           2026-08-23T17:03:06Z = 10:03 PDT) rewrote the `<!-- LATEST_MODELS
           -->` block of `RenQuant/.subrepo_runtime/repos/renquant-model/
           README.md` (mtime 08-23 10:03 PDT, same minute) `[VERIFIED —
           read-only sqlite query of data/sim_runs.db this session; mtime
           per the dispatching report]`. That single dirty tracked file in a
           RUNNING pinned tree made the daily run-surface drift scan alarm
           and the dawn preflight refuse ("pins not aligned" — a
           mislabelled dirty-tree refusal) for 8 sessions. A doc-refresh
           convenience must never be able to mutate a pinned tree; the
           refusal lives in the script itself so every caller — present
           and future, in any repo — is covered without depending on the
           caller remembering a flag.

EVIDENCE:  artifact:      `scripts/refresh_readme_latest_models.py`,
                          `tests/test_refresh_readme_latest_models.py`
                          (+6 tests), `sequence_training.py` caller,
                          `docs/training_pipelines.md`
           prod or exp:   neither — maintenance script; no artifact,
                          fingerprint, or decision path involved
           existing data: live-shaped smoke, READ ONLY: running the new
                          script against the REAL runtime README
                          (`--db RenQuant/data/sim_runs.db --readme
                          RenQuant/.subrepo_runtime/repos/renquant-model/
                          README.md`) exits 2 with the `.subrepo_runtime`
                          reason; README mtime unchanged before/after and
                          `git status --short` in that checkout stays
                          empty `[VERIFIED — this session]`. That checkout
                          is detached at `bd0fa488` (2026-08-11), so the
                          second guard would also have fired
                          `[VERIFIED — git symbolic-ref / log -1]`.
                          The runtime README was already clean (mtime
                          2026-08-30 10:15 PDT, status empty) when read
                          this session — restored by someone else, not by
                          this PR `[VERIFIED — stat + git status,
                          read-only]`.
           best-known?:   yes — closes the mechanism, not the symptom
           scope:         renquant-model only. The orchestrator caller and
                          the umbrella pin advance are follow-ups in their
                          own repos; the fix becomes LIVE only when the
                          model pin advances past this merge (merged is
                          not deployed).

TESTS:     baseline origin/main (`make test`, RenQuant venv): 1622 passed /
           2 failed / 9 skipped. After: 1628 passed / 2 failed / 9 skipped
           — +6 new: refuses under `.subrepo_runtime` (rc=2, README
           byte-identical, table on stdout); refuses in a detached
           checkout (real `git init` + `checkout --detach` in tmp_path);
           writes in a branch checkout; `--allow-runtime` overrides;
           `--dry-run` writes nothing; `--dry-run` wins over
           `--allow-runtime`. The 2 failures are pre-existing and
           unrelated (`test_clf_lineage_bundle.py::test_GOLDEN_artifact_
           only_scoring_reproduces_the_committed_corpus`,
           `test_fold_scoring_contract.py::test_GOLDEN_reproduces_the_
           committed_corpus` — committed-corpus reproduction, identical
           failure on baseline and after) `[VERIFIED — both logs this
           session]`. ruff (default rules) on the touched files: only the
           pre-existing unused `import pytest` in the test module, left as
           is.

NEXT:      * renquant-orchestrator: mirror the output-capture cosmetic in
             `train_gbdt.py`'s README refresh (optional; safety does not
             depend on it).
           * Umbrella: advance the renquant-model pin past this merge so
             the guard is the version the runtime tree actually runs.
