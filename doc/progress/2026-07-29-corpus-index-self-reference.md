# Progress: corpus_index — an index written inside its own root now verifies

STATUS:   delivered (tool fix + 2 tests, 9/9). Found by walking into it.

WHAT:     `build_index` gains an `exclude`, wired so `generate --out` and
          `verify --index` both drop the index file when it lands inside the indexed
          root. The rule is recorded in the artifact's own
          `digest_construction.self_exclusion` field so it is reproducible without
          reading the code.

WHY/DIR:  The natural layout is the index next to the artifacts it describes. That
          layout was broken: an index cannot contain its own digest, so `verify`
          failed immediately with "present in corpus but not in index" — a message
          that points at the data when the fault is in the tool. I hit this while
          sealing a confirmatory bundle; the next person would have hit it too.

EVIDENCE: reproduced then fixed `[VERIFIED — tools/corpus_index.py verify, 2026-07-29]`:
          the same bundle that reported "present in corpus but not in index:
          INDEX.json" now reports `VERIFY OK: 3 files, 6901 bytes, root_digest
          1a50d4ae…`. Two new tests pin both halves: an index written inside the root
          verifies, AND the exclusion does not hide a genuinely extra file (a planted
          `sneaked.bin` still fails verification by name). Suite 9/9.

NEXT:     None for this tool. The fix unblocks sealing bundles in the obvious layout.
