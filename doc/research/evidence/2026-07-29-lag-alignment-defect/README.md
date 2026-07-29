# Evidence: cross-lag sample-drift defect (2026-07-28/29)

Committed here (not left in local scratch) so the numbers `lag_alignment.py`
cites are independently inspectable by a reviewer, not just asserted.

- `h9_fix.py` — the permutation-test script that produced the recomputation
  cited in `lag_alignment.py`'s module docstring: on a common score-date set,
  PatchTST lag-0 IC +0.028 → +0.043, prod XGB +0.069 → +0.100, with the
  prod-XGB profile reversing (z = -2.09) once the sample is held fixed.
- `h9_results.json` — its raw output.

sha256 at commit time:
- `h9_fix.py`: `6f2f2a5b13074b020544ede9ff0c84ceb023c83b36f6af27fb3b74062e41d976`
- `h9_results.json`: `35b7773a5b652c56e2b0abedb31bb3a297e767a340430faa95c8cd4a8eb87181`

This is the derived-statistics OUTPUT only (a few KB) — not the 43-fold
PatchTST WF corpus itself, which stays in quarantined local scratch per its
own prereg's data-handling contract and is not committed anywhere.
