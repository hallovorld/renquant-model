# v1_fast frozen params — the fast momentum clock (model#199 build item 1)

**Date:** 2026-08-03 · `renquant-model` · GOAL-8 fast arm

STATUS:    params module + accessor + freeze-pin tests; NO production run
           yet (the freeze-then-run discipline: #199 is the authority; this
           merely makes the freeze executable). Build items 2-3 (weekly job
           produces both artifacts; s104 shadow_models entry) follow.
WHAT:      `_frozen_params_v1_fast` (63/5/50 + v0's non-clock knobs verbatim)
           + `params_v1_fast()` + exports. Two pins: the module equals the
           #199 literals; v0 and v1_fast differ ONLY on the clock keys —
           a "tune" of the fast lane cannot smuggle in a different model.
WHY:       Operator 2026-08-03: fast momentum as a shadow-only daily-ntfy
           patrol lane, SEPARATE from the slow v0 lane bound for the prod
           MoE; params frozen in #199 before any run.

EVIDENCE:

```
tests:  1523 passed / 0 failed (2 new freeze pins).  [本次实测]
scope:  "params + accessor + tests only; no runner, no job, no serving
         change; nothing produces a v1_fast artifact yet."
```

## Revert

git revert; nothing consumes the new accessor.
