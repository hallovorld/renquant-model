# The artifacts are now version-controlled — they were one session from gone

`README.md` in this directory states the position as of 2026-07-30:

> *"It is committed **on its own**, ahead of the 6.97 MB of artifacts it names, because
> the artifacts live in a session scratchpad that is garbage-collected and the
> definition is the part that makes them verifiable at all."*

**Measured 2026-07-31**: the 61 files were still alive, in **this session's** scratchpad
(`…/428feb92-…/scratchpad/`). One session boundary from being unrecoverable, while **ten
committed documents cite the bundle**.

| check, re-run before copying | result |
|---|---:|
| files present in the scratchpad | **61 / 61** |
| per-file `sha256` matching the index | **61 / 61** |
| drifted | **0** |
| total bytes vs index (`6,969,817`) | **exact** |
| per-file `sha256` re-checked **after** the copy | **61 / 61** |

`root_digest_sha256` unchanged: `901f0addd19b7381775f9dd593e046b862863b8bb04bb0de7260eb405423810a`.

## The `.gitignore` interception, recorded because it nearly hid the whole thing

`.gitignore:12` is `data/`, which matches this path. A plain `git add -A` stages
**nothing** here — and would have let me report "corpus persisted" while the tree was
still only in `/private/tmp`. `git status --porcelain` returning **0 new files** after a
61-file copy is what caught it.

The files are therefore added with **`git add -f`**, deliberately and against the
directory's default. The justification is the README's own sentence above: the index was
committed *"ahead of"* the artifacts, so committing them completes a stated intent rather
than overriding a policy. **If a reviewer disagrees, the right fix is to move the bundle
out of `data/` — not to drop it back into a temp directory.**

## What this changes

The ten citing documents' evidence is now reproducible by anyone with the repo, instead
of by nobody. Nothing about the bundle's *content* or *conclusions* is touched here.
