# ERRATA 2026-07-31 — "a statement about the DATA" is narrowed

**This document does not touch the prereg it corrects.** The first attempt at this
errata inserted HTML pointer comments into the registered lines *while claiming the
document was byte-identical*. Codex on model#141 caught it: that is an edit, and a
substring test cannot establish immutability. The prereg file is now restored and this
PR changes **zero bytes** of it — the pinning below is what a reader checks instead of
taking my word for it.

## What is corrected

**Subject:** `doc/research/2026-07-30-momentum-total-return-prereg.md`

| pin | value |
|---|---|
| registering commit (`prereg(FREEZE)`) | `048975f4e030d3a90bd8ee1c97466f00f4810b52` |
| blob at that commit | `ab25a63a2cec8698fdde828c6eb0270192b2a9d3` |
| **revision this errata is written against** | `origin/main` |
| **blob at that revision** | `c0e03c95f8087c9d3572148d79891b7adf7043b0` |
| sha256 of those bytes | `bad1ade550cf102597d57bcc7558a3518cdae9ffac631e5c196a8ae7157f8f3d` |
| size | 63 323 bytes |

The blob moved between the freeze and `main` because two later commits **appended** to
the document (`d256d8f` results, `4166e4c` the §7 adversarial review, `2f71dc2`
provenance pins, `f4f3a83` the earlier `block_length = h` errata). Both pins are given
so a reader can tell an append from an edit rather than trusting either.

## The clauses

Cited by **stable heading** first, because line numbers move when a document is
appended to; line numbers as they stand at blob `c0e03c95` are given second.

| # | heading | line | registered text |
|---|---|---:|---|
| 1 | `## 5c. Registered DATA diagnostic D1 — no verdict attached` | 400 | "**D1 is a statement about the DATA, not about momentum.**" |
| 2 | `## Bottom line` (point 3) | 502 | "**The dividend confound is REFUTED as the explanation of the aborted run's headline pattern**" |
| 3 | `## Bottom line` (point 3, cont.) | 504 | "and it is a statement about the DATA, not about momentum." |
| 4 | `## 3. D1 — the dividend confound is REFUTED (a statement about the DATA)` | 591 | the heading itself |

## The narrowing

The first half — that the construction removes what this dataset's own `dividend`
column says was there — **stands as an internal result**. The second half does not.

`exdiv_gap()` identifies ex-dividend days as `s["dividend"] > 0` — **the same
`dividend` column the total-return construction consumes**
`[VERIFIED — 本次实测 2026-07-31, tools/build_total_return_series.py:250]`.

> **If the feed itself is wrong — a missing event, a wrong amount, a wrong date — the
> construction will not adjust for it AND D1 will not look for it**, because it reads
> the event calendar off that same column. D1 tests *"did we remove what our own data
> says was there."* **It cannot fail on a bad feed, so it cannot be a statement about
> the data.**

Every surviving validation has that shape: `V3` is the identity over the same `D`,
`V2` compares non-payers to themselves, `V7` reconciles CAGR against a yield from that
column. `V5` — the vendor's independently built `adj close` — is the only one that
could contradict the feed, and it produced nothing (column present, **0** non-null
rows over 2 658 rows × 6 tickers; model#133).

| claim | status |
|---|---|
| the TR construction is internally correct | **supported** — −66.6 → −4.8 bp, V2 exact 0.0, V3 4.4e-16 |
| the confound is removed **from the source data** | **NOT established** |
| a momentum result here is free of a dividend-yield tilt | **NOT established** |

## Unaffected

§6's verdict **`UNRESOLVED / TILT-NOT-EXCLUDED — nothing licensed`** never rested on
the data claim and is not touched. An errata that quietly widened its own reach would
be a second over-reach.

## Notes on this errata itself

**Its date was wrong once.** Written first as `2026-07-31`'s predecessor header
`ERRATA-2026-08-01`, while the clock read **2026-07-31 06:39 PDT** — a date asserted
rather than read, inside the one document whose purpose is showing what was claimed and
when. Corrected before any reviewer saw it, and recorded here rather than silently
rewritten.

**Its form was wrong once.** See the top of this file. The lesson is narrower than "be
careful": *appending to a frozen document and editing its registered lines are not the
same act*, and a test that greps for a surviving substring measures neither. What
establishes immutability is pinning the blob.
