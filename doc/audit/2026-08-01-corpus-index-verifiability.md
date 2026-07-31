# Two committed indexes, no bytes — and one of them cannot be found at all

**Bottom line `[本次实测 2026-08-01]`.** model#139 rescued the clf/WF closure bundle (61
files) from a session scratchpad hours before it would have been unrecoverable. The
obvious next question — *was it the only one?* — has a measured answer: **no.**

| committed index | files | found | verifiable |
|---|---:|---:|:--|
| `2026-07-30-patchtst-closure-v2/INDEX.json` | 7 | **7** | **yes** |
| `2026-07-29-clf-wf-closure-bundle/bundle_index.json` | 61 | 0 | no — rescued in **model#139**, not yet on `main` |
| **`2026-07-29-patchtst-43fold-corpus-index.json`** | **133** | **0** | **no** |

The third is 14.8 MB, root digest `b8aa2d99…`, laid out by fold date
(`2023-10-02/`, `2023-10-23/`, …).

## Where it was looked for, so a nil result is interpretable

| location | fold-date layout present |
|---|---|
| the repo (`doc/research/evidence/`, `…/artifacts/`) | no |
| `RenQuant/artifacts/**` to depth 4 | **no** — `patchtst_shadow/` holds only `canonical_5seed_mps` and `pt07_strict_trainfit_embargo60_20260522` |
| `/tmp` | no |
| this session's scratchpad | two directories share the date layout (`wt_fold_scorers_gitver_bak`, `wt_calibrators_gitver_bak`) and contain **0 of the 133 indexed paths** |

## What this is NOT

**Not a fabrication claim.** *"Not locatable"* and *"never existed"* are different
statements and only the first is measured. This programme has a **2026-07-28/29 incident
on exactly this distinction**, and one half of that incident was **me wrongly re-flagging
a REAL corpus as fake**. The audit reports where it looked and what it found; it draws no
conclusion about why.

**Already known, and separate:** model#124 disqualified this corpus for a different
reason — *0 of 43 checkpoint sha256 matched the live served digest*. That is a statement
about **fitness for the closure study**; this one is about **verifiability at all**.

## What landed

`tools/corpus_index_audit.py` — enumerates indexes **by `schema` field, not filename**
(the three are named `bundle_index.json`, `INDEX.json` and `…-corpus-index.json`; a
filename rule would have missed two of three), reports found/matched/drifted per index,
**records the roots it searched**, and exits 1 when any index is unverifiable.

Its anti-vacuity condition is about the **subjects**: finding no index at all is an
**error**, not a pass.

Tests: 6, including a control that a *verifiable* index is reported as such — without
one, "unverifiable" would only mean the audit cannot find anything.
