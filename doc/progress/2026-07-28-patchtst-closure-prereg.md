# Progress: PatchTST closure prereg (frozen)

STATUS:   prereg FROZEN, confirmatory run NOT yet executed under the fixed (T11)
          harness. Docs only.
          CORRECTION (visible, per long-term-agreements.md entry 10, not a
          silent overwrite): a prior head on this branch added a "results"
          commit claiming this prereg had been executed against the 43-fold
          corpus and returned CLOSE (p=4/4). That commit was removed because
          the T11 sample-composition defect invalidates its p=4/4 count, not
          because the corpus itself is fake. Re-verified directly this
          session: `walkforward_patchtst_manifest.json` + its
          `.provenance.json` show 43/43 `calibration.json`, real per-cutoff
          `.pt` checkpoints, and a Modal dispatch record (app_id, cost gate,
          budget contract) `[VERIFIED — direct filesystem inspection this
          session]`. A separate, earlier claim that this same corpus was
          fabricated was itself wrong (checked git branch history only; the
          corpus lives in scratch space by this project's design) — see
          model#87 and model#88's own PR-comment threads for that specific
          correction. The corpus is real; it is NOT yet at a stable,
          content-hashed, checked-in location (session-scoped scratch path),
          which the results doc must still resolve before this prereg's
          verdict can rely on it.

WHAT:     Adds `doc/research/2026-07-28-patchtst-closure-prereg.md`: a registered
          kill test for the claim that PatchTST's walk-forward edge is stale-score
          persistence — four persistence lags (20/40/60/80d), the prod XGB as a
          positive control, a permuted-score negative control, block-level inference,
          and a frozen CLOSE / KEEP-OPEN / INCONCLUSIVE rule. No results in this PR.

WHY/DIR:  GOAL-6 Stage 0 (model#86) is reported to have measured `REAL - persistence`
          as trending negative for PatchTST and positive for the prod XGB, in an
          as-yet-unapproved design (5 unresolved review findings as of 2026-07-29,
          model#86 STATUS: "no run yet"). That looks decisive, which is exactly why
          it may not be acted on where it was found: it was a by-product of a
          MEASUREMENT study, not a registered kill test. New trap T9 in the
          checklist names that failure mode explicitly; this document's OWN test
          design does not depend on Stage 0's specific numbers being final, or even
          real.

          CORRECTION (visible, per long-term-agreements.md entry 10, not a silent
          overwrite): this line previously cited specific six-cell numbers tagged
          `[VERIFIED - goal6-stage0/results.json]`. That artifact cannot exist —
          model#86 has no approved/executed result. Citation and numbers dropped.

          Separately: a bug-hunt script (`bughunt/h6_closure.py`, read-only,
          on the same underlying scores) recomputed this design's statistic
          and found a sample-composition defect (new trap T11, §2/§0 of the
          research doc) — the REAL and PERSIST arms were drawn from
          different, non-overlapping score-date windows. Recomputed on a
          common date set (`h6_results.json`, re-read directly this
          session), PatchTST's result fell from 4/4 to 0/4 and the
          prod-XGB control fell from 4/4 to 1/4 (control invalid)
          `[VERIFIED — h6_results.json]` — the verdict is INCONCLUSIVE, not
          CLOSE. PatchTST is UNRESOLVED. This is a bug-hunt recomputation,
          not the official harness's own output; T11 is now a frozen
          precondition on the harness for any future confirmatory run
          under this design.

EVIDENCE: artifact:      `doc/research/2026-07-28-patchtst-closure-prereg.md`
                         (design, this PR); `walkforward_patchtst_manifest.json`
                         + `.provenance.json` (43-fold corpus, re-verified this
                         session); `bughunt/h6_closure.py` + `h6_results.json`
                         (T11 bug-hunt recomputation, re-verified this session)
          prod or exp:   experiment — a frozen test design plus a bug-hunt
                         recomputation demonstrating a defect; no production
                         artifact touched; no valid confirmatory run exists
                         under the fixed (T11) harness yet
          existing data: model#86's own (unapproved) design measurement motivates
                         this prereg qualitatively, not numerically (see WHY/DIR
                         correction); the 43-fold corpus is real (43/43
                         calibration.json, real checkpoints, real Modal
                         provenance) but lives in session-scoped scratch, not a
                         pinned location; a prior confirmatory run under an
                         earlier version of this same design produced CLOSE
                         (p=4/4), but that run is retracted for the T11
                         sample-composition defect and the bug-hunt
                         recomputation puts it at 0/4 with an invalid control
          best-known?:   n/a — no valid verdict exists yet under the fixed
                         harness; the retracted p=4/4 run is not the
                         best-known result, it is a known-invalid one
          scope:         this is a frozen pre-run design plus a retraction of an
                         invalid prior run under it; the §4(b) sanity triad applies
                         in full to the NEXT results doc, once T11 is fixed in the
                         harness and the corpus is pinned to a stable,
                         content-hashed location

NEXT:     Pin the 43-fold corpus (real, but currently in session-scoped scratch)
          to a stable, content-hashed location or regenerate it under a
          reproducible dispatch; fix the harness per T11 (common score-date set
          for REAL/PERSIST); re-run the confirmatory test; then a NEW results
          doc applying §3 mechanically, including the block-level estimator and
          the four-lag rule's Type-I calibration now frozen in the research
          doc's §2. A CLOSE verdict authorises only the deprecation PR, which
          the standard chain then reviews - it changes nothing live by itself.
