# GOAL-6 Job B: depth-extension results bundle (run-001) — 82 windows committed + deterministic verifier

(PR: `goal6/jobb-depth-extension-bundle`)

STATUS:   delivered. The COMPLETED 82-window backward extension (run-001,
          produced by the model#185 tool under the documented vintage seam)
          is committed as a verifiable bundle: full artifact BYTES (30 MB,
          under the ~60 MB cap, so no index-only fallback was needed) + the
          extension lineage manifest + the sealed run claim + a 16-test
          deterministic verifier. Nothing merged; the batch itself ran
          outside this PR under the sealed run-dir contract.

WHAT:     Adds `doc/research/data/2026-08-02-jobb-gbdt-depth-extension-run001/`
          (gbdt_depth_extension_manifest.json, RUN_CLAIM.json, 82 x
          window_artifacts/<cutoff>/panel-ltr.json, README) and
          `tests/test_jobb_depth_extension_bundle.py`, mirroring the Job A
          clf-bundle pattern (2026-08-01-clf-wf-lineage-bundle +
          test_clf_lineage_bundle.py).

WHY/DIR:  GOAL-6 (WF corpus depth). The production gbdt ladder had 43 windows
          (2023-10-02 .. 2026-03-02); this run extends the lineage BACKWARDS
          to 2019-01-14 — 125 windows total under the #94 append-only
          identity rule — on the current input vintage with the June-vs-Aug
          seam recorded first-class (operator decision 2026-08-02: do NOT
          regenerate the 43-window ladder; the production lineage stamps bind
          the actual manifest artifacts).

EVIDENCE: artifact:      `doc/research/data/2026-08-02-jobb-gbdt-depth-extension-run001/`
                         (this PR; byte home = the sealed read-only
                         `~/renquant-data-store/goal6-jobb-gbdt-depth/run-001/`).
  prod or exp:           EXPERIMENT corpus; nothing under RenQuant or any
                         production path was written. Bytes were COPIED out
                         of the sealed run dir; the run dir itself untouched.
  existing data:         run-001 manifest: 82 new windows 2019-01-14 ..
                         2023-09-11, ladder 43 -> 125, old root d1161f8d… ->
                         new root 83496eac…, every new row
                         `input_vintage=2026-08-01-rebuild`, min
                         leakage_margin_bdays = 1, wall 837.9 s
                         `[VERIFIED — run-001 manifest, recomputed by this
                         verifier]`. Seam evidence content-sha 28a4a396…
                         equals the model#185-committed golden_report.json
                         (max|delta| = 0.6489841341972351, parity FAIL)
                         `[VERIFIED — this verifier]`.
  best-known?:           N/A — corpus persistence + verification only; no
                         IC/effect-size claim is made here. Scoring/gate use
                         of the extended lineage is downstream work.
  scope:                 verifier recomputes from COMMITTED bytes only:
                         all 82 artifact digests, both roots per the
                         manifest's own root_rule (old root from the suffix),
                         order sensitivity, claim->manifest binding, recipe_id
                         from every artifact via the merged tool's projection,
                         TYPE guards (list norm_kind, 172-aligned means/stds),
                         no-wrong-artifact-behind-a-window, vintage + seam
                         completeness, #94 margins recomputed per row; one
                         OPTIONAL run-dir byte-parity test loudly skips off
                         this machine. `tests/test_jobb_depth_extension_bundle.py`
                         **16 passed**; full suite **1390 passed**
                         `[VERIFIED — make test, this session]`.

NEXT:     Downstream consumption of the 125-window lineage (scoring the
          extended windows' OOS ranges, gate-side lineage stamps over the new
          root) — separate PRs; pooling across the seam must surface the
          per-window `input_vintage` stamps.

---

## Size decision

`du -sh` on run-001 = **30 MB** total (82 artifacts at ~363 KB each) — under
the ~60 MB cap, so the bundle commits the BYTES (the coordinator's
index-only fallback was not needed). The durable byte home remains the
sealed run dir; the README states this.

## What the verifier pins (16 tests)

1. counts + backward-ladder shape (82/43/125; 21-day grid strictly before
   2023-10-02);
2. every committed artifact digest == its manifest row;
3. the manifest DECLARES the root rule the tests implement;
4. new root recomputes from committed bytes (new-window digests recomputed
   from files, not trusted from rows);
5. old root recomputes from the suffix (append-only);
6. root order-sensitivity (swap two shas -> root moves);
7. recipe_id recomputes from EVERY committed artifact via the merged tool's
   `recipe_fingerprint` (one recipe, 82 windows);
8. the sealed RUN_CLAIM binds the committed manifest bytes (status consumed,
   root + manifest sha match);
9. TYPE guards: norm_kind is a per-feature list (never a string), means/stds
   lists aligned to the 172 feature_cols;
10. no wrong artifact behind a window (self-carried cutoff/embargo/effective
    cutoff == row);
11. every new row carries `input_vintage`;
12. seam block complete (all fields incl. `evidence_golden_report_sha256`,
    drift values, 3 rebuilt inputs with digests);
13. the seam evidence resolves to the committed #185 golden_report.json by
    content sha;
14. #94 admissibility margin recomputed from each row's own fields, >= 1
    business day on all 82;
15. every path the verifier reads is inside the repository;
16. OPTIONAL byte parity vs the sealed run dir (loud skip in CI).
