# The clf/WF closure bundle — its INDEX, sealed

`bundle_index.json` here is the surviving definition of the evidence bundle that ten
committed documents cite (model#115). It is committed **on its own**, ahead of the
6.97 MB of artifacts it names, because the artifacts live in a session scratchpad that
is garbage-collected and the definition is the part that makes them verifiable at all.

## What was measured, 2026-07-30

| | value |
|---|---|
| `root_digest_sha256` | `901f0addd19b7381775f9dd593e046b862863b8bb04bb0de7260eb405423810a` |
| matches the digest cited in the 2026-07-29 retraction (`901f0add…`) | **yes** |
| `n_files` | **61** |
| `total_bytes` | 6,969,817 |
| files present on disk at measurement time | **61 / 61** |
| spans | {'bughunt': 21, 'clf-wf': 6, 'corrected-eval': 23, 'wf-eval': 11} |

`[VERIFIED — json read of the surviving index plus an os.path.exists sweep over its 61
relative paths, 2026-07-30]`

## What this settles, and what it does not

**Settles (model#115 step 1):** the bundle is **not lost**. Its definition survives with
a digest that matches the citation, and every one of its 61 files existed when this was
measured. The 61-vs-44 discrepancy the retraction described also reconciles exactly:
`clf-wf` (6) + `wf-eval` (11) = **17**, and 44 + 17 = 61.

**Does not settle:** the artifacts themselves are still outside version control, in a
path that will not survive the session. Committing this index does not make the
citations reproducible — it makes them *checkable in principle* and records precisely
what would have to be recovered.

## Why nothing here was ever committed by default

`.gitignore:12` is a bare **`data/`**, which git applies at **any depth** — so
`doc/research/data/` is ignored wholesale `[VERIFIED — git check-ignore -v]`. Every
corpus that *is* tracked under it was force-added past that rule. So the reason ten
documents cite an uncommitted bundle is not that someone forgot: **the repository's
default is to drop it**, silently, and only an explicit `git add -f` overrides that.

This file is committed with `-f` for the same reason.

## Why the index alone, first

Committing 6.97 MB of parquet into a research repo is a judgement call that deserves its
own decision. Losing the definition is not: without it, nobody can even establish which
61 files were meant, and this programme has already had one digest citation go stale
because files were appended after it was written. The definition is cheap, durable and
the prerequisite for either remedy.

## Next

1. Decide where the 61 artifacts live durably — repo, or an operator-owned data root.
2. Re-state every citation of `f6b6ef6d…` (44 files) against `901f0add…` (61), **together**,
   since appending to a bundle voids each prior citation of its root one at a time.
