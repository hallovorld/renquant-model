# Momentum prereg — Amendment 3 (visible, PRE-RUN): the pinned inputs refresh daily; §2 resolution moves to a fingerprinted snapshot manifest

**Amends §2's input RESOLUTION only. Every digest is unchanged. Filed before any
execution. Revised per the codex review: the referent is a durable base-data manifest,
not a raw directory.**

## The defect, discovered by an unrelated failure `[本次实测 2026-08-01]`

Running the clf bundle's committed `verify_recipe_fidelity.py` failed on feature-means
mismatch — root cause not infidelity but **input drift**: its manifest pinned panel
`7c0c6447…` while the live panel is `55811f63…`, because
`data/alpha158_291_fundamental_dataset.parquet` is refreshed by the daily job. The
momentum prereg pinned **that same daily-moving path**, so its own UNRESOLVED-DATA rule
— correct as a tamper guard — closes the execution window at the next daily refresh.
A freeze that pins a moving path pins a deadline, not an input.

## The remedy chain (ordering per the #171 review)

1. **Durable fingerprint record** — `renquant-base-data#59` publishes
   `manifests/momentum-prereg-inputs-20260801.json`: 294 file entries (panel, sector
   snapshot, 292 OHLCV files), each with sha256 + byte size, plus the combined OHLCV
   digest reproducing §2's arithmetic exactly. The three headline digests are
   byte-identical to this prereg's frozen pins (verified at snapshot AND at manifest
   build). Digests NORMATIVE; location ADVISORY (currently the umbrella experiment
   area, PROVISIONAL pending orch#742 — the snapshot write is self-reported there for
   operator disposition; RELOCATE changes only the manifest's location field).
2. **This amendment** — §2's inputs are henceforth resolved THROUGH that manifest:
   the runner must load `manifests/momentum-prereg-inputs-20260801.json` (content
   sha256 `2912983593782edd52f432d706933ed81041fe97b8e3b670fe30e6b4f6cb71ed` as of
   base-data#59; a reviewed location-only revision may change the file, in which case
   the runner takes the merged base-data main as authoritative), verify every file it
   reads against the manifest's sha256, and treat mismatch or absence as
   UNRESOLVED-DATA. No fallback to the live `data/` paths under any condition.
3. **The runner (#169)** — revised in its own PR to implement exactly that
   verify-then-read resolution before this amendment's chain is mergeable end-to-end.

## The amendment (resolution only; digests, population, and rules untouched)

§2's digest table, the 43-name non-payer list, the closed population, and the
UNRESOLVED-DATA rule are all unchanged by a byte. What changes: the paths §2 resolves
to are the manifest's, and resolution REQUIRES per-file digest verification against the
manifest. The tamper guard keeps guarding; the hidden deadline goes.

## Not claimed

That the daily refresh is wrong — it is the pipeline working. That the clf bundle's
fidelity NO VERDICT is discharged — the opposite: it is unverifiable as committed on
the live tree (its pinned bytes are gone from the pinned path and the bundle committed
no copy; other backups were not searched). That the snapshot's current LOCATION is
final — that is orch#742's operator call; only the digests are frozen here.
