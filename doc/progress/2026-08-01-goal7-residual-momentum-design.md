# Progress: GOAL-7 residual-momentum standalone model — design opened for discussion

WHAT: `doc/design/2026-08-01-goal7-residual-momentum-standalone.md` — the candidate the
non-supportive record points at. Prior raw price and raw TR momentum results are non-supportive or unresolved here
(canonical bars predate the overlapping-label corrections; the TR study ended
UNRESOLVED with worse point estimates at all 4 horizons); residual momentum
(Blitz–Huij–Martens 2011) is the one classic variant untested here, and its zero-fitted-
parameter form makes the panel's full ~2,594-date history out-of-sample by construction —
which is what rescues power (MDE ≈ 0.037 at the +0.04 bar, conditional, vs hopeless on
~500-date corpora).

DISCIPLINE: for discussion, not frozen; no IC computed anywhere in this change; the
inference section complies with the model#124/#128/#135 reopen condition (HAC validated by
positive control + size probe; no N/h; permutation as centring only per model#153).
KILL is declared an acceptable outcome up front.

PARALLEL: a read-only feasibility measurement (formation-window coverage on the 292
universe, TR/dividend coverage, the `fwd_20d_excess` constructor quoted verbatim,
eligible-date counts) is running and will attach to the frozen version per AC4.

Docs only. No code, no config, no production surface touched.
