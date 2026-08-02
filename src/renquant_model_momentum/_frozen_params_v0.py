"""The v0 params constants, as a COMMITTED MIRROR that ships in the wheel.

Reviewed `[codex on model#196]`: `params_v0()` sourced these by importing
`tools/goal7_momentum_run.py`, which lives outside `src/` and therefore never enters
the built distribution (`[tool.setuptools.packages.find] where = ["src"]`). An installed
consumer got `FileNotFoundError` on first use while every in-repo test passed — the
package worked only from a checkout.

WHY A MIRROR RATHER THAN AN INVERSION. The obvious alternative is to make this module the
single definition and have the v1 runner import it, which removes drift by construction.
It is rejected here: `tools/goal7_momentum_run.py` is the runner of a SPENT one-shot
study whose result is published and sealed. Editing it changes the bytes a published
result was produced by, for the convenience of a downstream package. The cost of a mirror
is that two copies can diverge; that cost is paid by
`test_params_v0_mirrors_the_sealed_v1_runner`, which fails loudly the moment they do —
and it runs in CI, where the repo is present.

So the split is: this module is what the WHEEL carries, and the sealed runner remains the
source of truth that the repo-side test holds it to. Neither half is asked to prove
something its inputs cannot reach.

Every value below is a transcription. Do not edit one without the other; the test is what
makes that instruction enforceable rather than advisory.
"""

from __future__ import annotations

#: From `tools/goal7_momentum_run.py::FROZEN` (frozen in model#164 §2).
WINDOW = 252
SKIP = 21
MIN_OBS = 200
MIN_FEATURES = 3
NAMES_PER_DATE_FLOOR = 50

#: The runner-declared F5 per-side floor, `MIN_SIDE_OBS` (reviewed in model#177).
MIN_SIDE_OBS = 30

#: What the params block reports as its provenance — the sealed runner remains the
#: authority even though the wheel carries the mirror.
PARAMS_SOURCE = (
    "tools/goal7_momentum_run.py::FROZEN + MIN_SIDE_OBS (frozen in model#164 §2, "
    "F5 floor in model#177); mirrored into renquant_model_momentum._frozen_params_v0 "
    "so the wheel is self-sufficient, with equality held by "
    "test_params_v0_mirrors_the_sealed_v1_runner"
)
