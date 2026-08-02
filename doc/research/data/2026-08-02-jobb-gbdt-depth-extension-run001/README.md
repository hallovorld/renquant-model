# GOAL-6 Job B — gbdt WF depth-extension results bundle (run-001)

The COMPLETED backward depth-extension of the production gbdt walk-forward
lineage, produced by `tools/wf_gbdt_depth_extension.py` (merged in model#185)
under the documented vintage seam: **82 new windows, cutoffs 2019-01-14 ..
2023-09-11**, extending the 43-window production ladder to **125 windows**
under the renquant-backtesting#94 append-only identity rule.

## Contents (committed BYTES — 30 MB total, under the bundle byte cap)

| path | what |
| --- | --- |
| `gbdt_depth_extension_manifest.json` | the run's extension lineage manifest: `recipe_id`, `root_rule`, `old_lineage_root_sha` (d1161f8d…, the existing 43), `new_lineage_root_sha` (83496eac…, all 125), per-window rows (new + existing), the `vintage_seam` block, input digests, plan, wall time (837.9 s) |
| `window_artifacts/<cutoff>/panel-ltr.json` | the 82 per-window snapshot artifacts (booster bytes + self-carried #94 admissibility fields), key-for-key mirrors of the production window artifacts |
| `RUN_CLAIM.json` | the sealed atomic run claim (status `consumed`), binding `manifest_sha256` to the manifest bytes committed here |

## Byte home and provenance

The DURABLE byte home of this run is the sealed, read-only run directory
`~/renquant-data-store/goal6-jobb-gbdt-depth/run-001/` (claimed atomically,
sealed 0444 at finish). This bundle is a verbatim byte copy committed for
in-repo verification; `tests/test_jobb_depth_extension_bundle.py` recomputes
every artifact digest, both lineage roots, the claim binding, the #94
causal-admissibility margins, the artifact type contracts, and the
vintage-seam completeness from the committed bytes alone.

## The vintage seam (why these windows carry `input_vintage`)

The golden reproduction of the earliest EXISTING window FAILED prediction
parity (max|delta| = 0.649) because the lineage-relevant inputs were rebuilt
on 2026-08-01 with revised history; the June-vintage bytes no longer exist on
disk. Per the operator decision (2026-08-02), the ladder was NOT regenerated;
the extension ran on the current vintage with the seam recorded first-class:
the manifest's `vintage_seam` block carries the decision, the measured drift,
the rebuilt-input digests, and the digest-bound evidence report
(`evidence_golden_report_sha256`), and every new window row is stamped
`input_vintage: "2026-08-01-rebuild"` so no consumer can pool across the seam
without seeing it.

The golden evidence + backward-ladder plan are already committed at
`doc/research/data/2026-08-02-jobb-gbdt-depth-extension/`
(`golden_report.json`, `extension_plan.json`, from model#185) — and that
committed `golden_report.json` IS the evidence this run's seam block binds:
its content sha256 (28a4a396…) equals the seam's
`evidence_golden_report_sha256`, and the batch admission digest-verified its
recorded input digests against the batch's freshly-computed ones at
execution time (same 2026-08-01 input vintage, still on disk at run time).
