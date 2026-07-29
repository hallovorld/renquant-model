# Progress: Q1 corrected-eval results (exploratory) + PatchTST closure retraction

STATUS:   in-progress, two distinct pieces of content, both now covered here
          (per codex MED — this doc previously said "no closure claim is
          made by this PR" while the diff still added a closure-retraction
          doc; that was wrong, fixed below):
          (1) Q1 corrected-eval results — EXPLORATORY only, not confirmatory
          (review caught the restored bundle is defective in two ways this
          doc must not paper over).
          (2) PatchTST closure retraction — a same-author CLOSE claim (added
          earlier in this PR, built on the estimand-difference reasoning
          this doc previously summarized) was submitted for adversarial
          review and BROKE on six counts, five of them the author's own. The
          claim is withdrawn. PatchTST's status is **INCONCLUSIVE** (not
          CLOSE, not exonerated) — this is the doc's own recorded
          conclusion for this PR, not "no closure claim."

          A prior, DIFFERENT closure document
          (`patchtst-closure-rerun-conflict.md`, the pre-adversarial-review
          version implying CLOSE) was removed from this PR per an earlier
          BLOCKER — that removal was correct and stands. The retraction doc
          added afterward is new, different content: it is the outcome of
          submitting that same reasoning to adversarial review, not a
          restatement of it, and belongs in this PR's scope since it is the
          direct sequel to work this PR already covers.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-results.md`: the Q1
          decision statistic recomputed with the merged three-view estimator, the raw-IC
          contrast, and an explicit statement of what is NOT established. The document
          now leads with an EXPLORATORY caveat (not confirmatory) instead of presenting
          the numbers as a settled post-prereg verdict.

          Removes `doc/research/2026-07-29-patchtst-closure-rerun-conflict.md` (the
          pre-adversarial-review version, out of scope per the earlier BLOCKER).

          Adds `doc/research/2026-07-29-patchtst-closure-retraction.md`: the same
          CLOSE reasoning, submitted to adversarial review, broken on six counts —
          a real digest citation that never verified at the moment it was written
          (§2 T11's frozen score-date-common rule was violated by the arms used,
          which is HARKing once the label-common reading was chosen only after
          seeing it produce CLOSE), a wrong estimator (60-date blocks instead of
          the frozen fold-level t), and model#90's own three-view rule resolving
          only 2 of 4 lags against a ≥3 bar. PatchTST's status: INCONCLUSIVE.

WHY/DIR:  model#90 froze the design and merged; its numbers had been stripped because
          they pointed at session scratch. The artifacts are now retained and
          content-addressed over their OUTPUT files, so the same numbers are quotable as
          exploratory findings — but two defects block treating them as confirmatory:
          (1) the retained bundle (`harness.py`/`results.json`/`verdict.json`) is
          timestamped 2026-07-28 23:34-23:35 PDT, ~3h BEFORE model#90 merged at
          2026-07-29 02:19:34 PDT `[VERIFIED - git log -1 8579fa7; ls -la on the
          bundle]` — it cannot be "recomputed against the merged prereg" when it
          predates the merge; (2) the harness reads mutable inputs from
          `/Users/renhao/git/github/RenQuant/data/...` and session-scratch parquet
          outside the bundle, and imports from `/private/tmp/renquant-model-pr89-review
          /src` — the root digest covers only outputs, so a verifier cannot reproduce
          these numbers from the bundle alone.

EVIDENCE:
artifact:      /Users/renhao/renquant_bundles/corrected-eval-20260729/ (61 files, root
               digest 901f0addd19b7381775f9dd593e046b862863b8bb04bb0de7260eb405423810a
               over OUTPUT files only; model#91 — does NOT cover inputs, see WHY/DIR).
               An earlier citation here (44 files, root f6b6ef6d…) was to a
               since-mutated snapshot of this same directory — outputs were appended
               after that digest was taken, which is exactly why
               `doc/research/2026-07-29-patchtst-closure-retraction.md` retracted it
               as invalid.
               CORRECTION to a prior push on this branch: it claimed
               `tools/corpus_index.py verify` returned VERIFY OK against this root
               because INDEX.json "self-excludes from its own digest per model#93's
               fix." Re-ran that exact command this session against the current tool:
               it still FAILS (root digest mismatch + "present in corpus but not in
               index: INDEX.json") `[VERIFIED - ran the command directly, 2026-07-29]`
               — model#93 (the tool fix for this) is open, unmerged. The
               901f0add…/61-files digest is independently reproducible today only via
               `generate` against a copy of the corpus with INDEX.json excluded (how
               it was produced); direct `verify` against the root as it sits on disk
               does not yet work. Any further appends invalidate the digest regardless.
prod or exp:   experiment — signal-evaluation research artifact, not a production/live
               path
existing data: model#90's Q1 result was stripped for citing an unauditable
               session-scratch path; this PR recomputes the SAME statistic
               (`d = REAL - persistence` on per-date rank IC, block_length 60, 1500
               bootstrap resamples, via `dependence_aware_mean`, model#89) against the
               retained bundle above, but the bundle predates model#90's merge by ~3h
               and reads unhashed mutable inputs, so it is exploratory, not a
               falsifiable post-freeze confirmatory record
               `[VERIFIED - recomputed 2026-07-29, ordering defect found on review]`.
               Separately, the closure-retraction doc's adversarial review found:
               the frozen prereg's §2 T11 requires score-date-common arms and §3
               voids any verdict built on the label-common slices this re-run
               used; ~68-72% of the L=60/80 effect is an era offset, not signal;
               the control passes 37.5% of the time on signal-free input; the
               estimator used (60-date blocks) was unregistered (frozen fold-level
               t gives p=3/4); and model#90's own three-view rule applied to the
               same table resolves only 2 of 4 lags against a >=3 bar
               `[VERIFIED - doc/research/2026-07-29-patchtst-closure-retraction.md,
               this PR's diff]`
best-known?:   not confirmatory — see STATUS. The Q1 paired-difference numbers (prod
               XGB +0.0359 t +1.23 CI [+0.0218, +0.0787]; certified clf +0.0113 t
               +1.31 CI [+0.0049, +0.0275]; PatchTST -0.0488 t -2.31 CI [-0.0772,
               -0.0050]) and the raw-IC contrast (only prod XGB resolves; certified
               clf's absolute IC, largest block t of the three at +1.52, still
               crosses zero [-0.0287, +0.1749]) are exploratory only until re-run
               per NEXT. Separately, PatchTST's closure status is INCONCLUSIVE — the
               best-supported disposition per the retraction doc's own audit, not
               CLOSE and not exoneration; point estimates on the registered basis
               stay negative at every lag but are unresolvable under the frozen rule.
scope:         "this is /Users/renhao/renquant_bundles/corrected-eval-20260729/,
               experiment, EXPLORATORY (not confirmatory — predates model#90's merge,
               unhashed inputs) Q1 paired-difference vs each subject's own 60-day-lagged
               persistence baseline — vs raw-IC levels where only prod XGB resolves."
               No Sharpe or return claim is made. The PatchTST closure verdict made
               by this PR is INCONCLUSIVE (retraction of a same-author CLOSE that
               did not survive adversarial review), not a fresh CLOSE or KEEP-OPEN.

NEXT:     Re-run the harness strictly AFTER model#90's merge (8579fa7), with the exact
          input parquet files (panel, prod-XGB scores, clf/PatchTST WF scores) and the
          code revision pinned and content-hashed INTO the bundle itself — not read from
          mutable RenQuant/scratch paths — before any confirmatory claim is made. Until
          then this stays exploratory. The clf's ABSOLUTE IC must not be quoted as
          established anywhere regardless of that re-run; its paired result may.

          PatchTST's closure question is recorded here as INCONCLUSIVE, per the
          retraction doc's own adversarial audit — this is the disposition, not a
          placeholder pending another PR. A further attempt at resolving it needs a
          NEW prereg that names the estimand up front (persistence vs. horizon) and
          uses a bias-corrected estimator, in its own reviewable PR with pinned/
          hashed inputs and code revision — not reads from mutable local paths. Until
          that lands, PatchTST stays INCONCLUSIVE and no construction's number from
          any prior attempt may be quoted as a fresh verdict.
