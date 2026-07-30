# SCREEN DESIGN 2 (FROZEN): the momentum family, on the traded estimand

**Frozen:** 2026-07-29, **before any arm was computed and before screen 1's
results existed.** This revision contains **NO result**. Screen 1
(`2026-07-29-vol-conditioned-momentum-reversion-screen.md`, design commit
`ff91d67`) was launched but had not returned when this was written, so this
design cannot have been informed by its outcome.

**Trigger:** operator preference, stated 2026-07-29 — *"我其实更偏向动量模型"*
(I lean towards a momentum model). A preference is a legitimate reason to
**register a test**. It is not a reason to loosen one, and §5 makes the bar
**stricter**, not looser, as the price of asking a second question of the same
corpus.

---

## 1. What is genuinely new here, stated before the numbers

A prior sealed result already screened the momentum family and killed it:
`mom_12_1`, `mom_6_1`, short-term reversal, MA200, 52-week-high **all fail the
20/60d bar on 104** (memory: `canonical-price-trend-no-multiday-edge`).

**This screen does not pretend that did not happen.** Two things differ, and
only these two:

1. **A different estimand.** That work read **full cross-section IC**.
   renquant-model#101 registers, as a measurement-design claim, that IC and the
   **top-decile spread** — the cut the live buy path actually trades — can
   diverge, because IC spends its power on the ~90% of names never acted on.
   Re-measuring a killed family on the traded cut is a legitimate new question.
2. **Two constructions the prior list did not contain**, both motivated by a
   measurement rather than by search: orchestrator#615 found the live scorer's
   dominant lever is `STD60` (marginal effect `+0.2301`, an order of magnitude
   above every price-trend feature). So **volatility-scaled** momentum and
   **volatility-gated** momentum are the constructions that mechanism implies.

**Disclosed, not hidden:** arm M1 below is *plain 20-day momentum*, which is in
the spirit of the prior kill list. It is labelled a near-replication and is
included as a calibration reference, not as a candidate.

## 2. Corpus — the SAME corpus screen 1 consumes

| input | sha256 |
|---|---|
| `RenQuant/data/alpha158_291_fundamental_dataset.parquet` | `7defdacf97f8eb057a9a56a2eb7bc6eb48bc33adb9fd00a2a6c36943be87daa5` |

READ-ONLY production file; the runner pins it and **aborts** on mismatch.

**This corpus is now consumed by two screens.** It can confirm neither. Every
positive from either screen requires a confirmatory prereg on a corpus neither
has touched. Recorded here so the double-dip is on the record.

**Label:** `fwd_60d_excess`, per-date cross-sectionally z-scored
(`build_alpha158_qlib.py:497`); moments measured in the runner's §0. Units are
**standard deviations, not return.** No P&L claim is possible from this document.

## 3. Arms, fixed now

`ret(n) = 1/ROC{n} − 1`, since `ROC{n} = close[t−n]/close[t]`
(verified: `build_alpha158_qlib.py:231`, `alpha158_ops.py:256`).
`z(·)` and the `STD60` terciles are per-date cross-sectional, as in screen 1.

| id | arm | role |
|---|---|---|
| M1 | `ret(20)` | **near-replication** of a known negative — calibration reference |
| M2 | `ret(60) − ret(5)` | intermediate momentum net of the last week (a `12−1`-style construction at this panel's available horizons) |
| **M3** | `ret(60) / STD60` | **volatility-scaled momentum** — implied by orch#615 |
| **M4** | `ret(60)` where `STD60` is above its per-date median, else `0` | **volatility-gated momentum** — the *pure-momentum* form of screen 1's N1, i.e. what the operator's preference actually asks for |

`ret(60)` alone is **NOT re-run here**: it is screen 1 arm R1 on this identical
corpus, so it is the same test. Its result is cited from screen 1 rather than
counted twice.

The panel carries `ROC5/10/20/30/60` only, so horizons beyond 60 trading days
(`mom_12_1` proper, MA200, 52-week-high) are **not constructible from it** and
are therefore **out of scope** — not silently omitted. Testing them needs the
raw OHLCV join, which is a separate registration.

## 4. Estimands and estimator — identical to screen 1, deliberately

E1 full cross-section Spearman IC per date; E2 top-decile spread with
`k = round(0.10·n)`, `k ≥ 1`; `n < 20` dates dropped. Both reported for every
arm, no best-of. Estimator `dependence_aware_mean`, `block_length = 60`,
`n_boot = 2000`, resolving only when block `t`, bootstrap CI and
leave-one-block-out agree. Five within-date label shuffles per arm per estimand;
a control above the arm's own `|t|` **VOIDS** it.

Using screen 1's estimator unchanged is what makes the two screens comparable.

## 5. Multiplicity — the bar goes UP, and screen 1's goes up with it

Screen 1 registered 10 tests ⇒ Bonferroni `|t| ≥ 2.81`. This screen adds
**4 arms × 2 estimands = 8 tests**. The joint family is **18 tests**:

> **Bonferroni α = 0.05 two-sided over 18 tests ⇒ `|t| ≥ 2.99`.**

**This supersedes screen 1's 2.81 — upward.** Tightening a threshold after
freezing is conservative and permitted; loosening one is not, and is not done
here. Any arm in either screen with `|t| < 2.99` is **not screen-interesting**,
including a screen-1 arm that would have cleared 2.81.

## 6. What this screen is licensed to output — only these two

1. **An M-arm's E2 spread is above every replication reference (M1 and screen
   1's R1/R2/R3), its controls are clean, and `|t| ≥ 2.99`** ⇒ the *only*
   licensed action is to register a **confirmatory prereg on an unseen corpus.**
   No factor is added to any model. No config change. No capital action.
2. **Anything else** ⇒ momentum is **not supported on this corpus on either
   estimand**, and the operator's stated preference does **not** survive
   measurement here. That outcome will be reported as plainly as a positive
   would be.

**Explicitly ruled out in advance:** a positive on M1 (the near-replication)
would contradict the prior sealed result and must be treated as a **red flag
about this screen's plumbing**, not as a rehabilitation of 20-day momentum. That
is why M1 is in the design.

## 7. Limits registered in advance

- **Estimator plumbing is validated by positive controls before any verdict is
  read** (`tests/test_trend_screens.py`): a planted signal must be recovered and
  a signal-free panel must not be. A screen whose estimator cannot detect a
  known effect can only produce uninformative negatives.
- In-sample over the full panel history; the factors are formulaic so no
  parameters leak, but the arm set is mine.
- **No cost, turnover or capacity model.** M2 contains a 5-day leg and M4
  re-gates monthly-to-weekly; a positive would still need a cost model before it
  meant money.
- `STD60` terciles/medians are taken on the **full panel cross-section**, which
  is **not** the vol-capped support the live path scores (orch#615 §4). M3 and
  M4 in particular would need a serving-support replication.
- Out of scope by construction: every horizon beyond 60 trading days (§3).

---

**Nothing in this revision is a result.**

---

# RESULTS (appended 2026-07-29, after the design commit `192f1b1`)

Verbatim output: `doc/research/data/2026-07-29-screen2.log`. JSON:
`doc/research/data/2026-07-29-screen2.json`. `[VERIFIED — this session]`, corpus
PIN OK, 725,547 rows / 2,597 dates / 292 tickers, label `mean = −0.0000`,
`sd = 0.9982` — units are **standard deviations, not return.**

## The registered verdict: OUTCOME 2. Momentum is not supported here.

| arm | E1 IC | t | ctl | E2 spread | t | ctl | E2 status |
|---|---:|---:|---:|---:|---:|---:|---|
| M1 `ret(20)` *(near-replication)* | −0.0250 | −1.81 | 1.85 | **−0.0460** | **−2.52** | 0.95 | clean, resolves |
| M2 `ret(60)−ret(5)` *(12−1 style)* | +0.0004 | +0.09 | 0.87 | **−0.0571** | **−2.66** | 1.00 | clean, resolves |
| M3 `ret(60)/STD60` *(vol-scaled)* | +0.0016 | +0.15 | 1.12 | +0.0079 | +0.20 | 1.05 | null |
| **M4 `ret(60)` gated to high `STD60`** | −0.0007 | −0.04 | 1.16 | **+0.0773** | **+2.41** | 1.46 | clean, resolves |

Joint 18-test bar `|t| ≥ 2.99`. **Nothing clears it.** Across both screens,
**0 of 18 registered tests are screen-interesting.**

## M1 behaved as the tripwire was meant to: it did NOT rehabilitate

§6 registered that a *positive* M1 would be a plumbing red flag. M1 came back
**−0.0460 (t = −2.52)**, consistent with the prior sealed result that killed the
family. The tripwire is silent, so the plumbing is not implicated — and the
positive controls in `tests/test_trend_screens.py` (9 passed) independently show
the estimator recovers a planted `+0.30` effect and stays null without one, so a
negative here is a real negative rather than a dead estimator.

## Answering the operator's preference directly, with the numbers

Stated preference (2026-07-29): *"我其实更偏向动量模型"*. Measured on this corpus:

**Unconditional momentum is priced NEGATIVELY on the cut the system trades, at
three independent horizons, every one with clean controls:**

| construction | E2 spread | t | control max\|t\| |
|---|---:|---:|---:|
| `ret(60)` *(screen 1 R1)* | −0.0519 | −2.59 | **0.38** |
| `ret(20)` *(M1)* | −0.0460 | −2.52 | 0.95 |
| `ret(60) − ret(5)` *(M2)* | −0.0571 | −2.66 | 1.00 |

Three horizons, three clean controls, same sign, similar magnitude. Each is
individually below the 2.99 bar, and their **agreement is not a fourth test** —
they are three views of the same underlying trend axis on the same corpus, so
they cannot be pooled into significance. What they do establish is that the
negative sign is **not one horizon's artifact.**

**The positive sign on this universe sits with reversion, not momentum:**
`rev20` **+0.1268** (t +2.82, control 1.54, clean) — screen 1 R3.

**One momentum construction flips the sign, and it is the GATE, not the
scaling:** vol-**gated** `ret(60)` (M4) = **+0.0773** (t +2.41, control 1.46,
resolves), against plain `ret(60)` at −0.0519 — a sign flip from restricting
momentum to above-median-`STD60` names. Vol-**scaled** `ret(60)/STD60` (M3) is
**+0.0079, t +0.20** — nothing. So dividing by volatility does not help;
*conditioning on* it does.

**But M4 is not a finding, for two stated reasons, and I am not going to soften
either:**
1. `|t| = 2.41` is **below the registered 2.99 bar**, which I raised myself in
   §5 before any number existed.
2. It **conflicts in sign with screen 1's N1** (−0.0346, VOID), which applied a
   related vol-conditioning (high *tercile* momentum + low-tercile reversion).
   Two registered arms built on the same conditioning idea disagree in sign. An
   effect that flips with an incidental construction choice is not an effect
   yet.

M4 is therefore **the only thread in 18 tests worth a properly-powered
confirmatory test on a corpus neither screen has touched** — which is exactly
and only what §6 outcome 1 would have licensed, and it did not even reach that.

## A defect in my own control rule, disclosed

Every arm whose real `|t|` is near zero is labelled **VOID** — e.g. M2's E1 at
`t = +0.09` against a control max of 0.87. That is the registered rule ("a
control above the arm's own `|t|` VOIDs it") applied literally, but for a null
arm *any* control noise exceeds it, so the VOID label is mechanically guaranteed
and carries **no information beyond "this arm is null".** It should not be read
as "something is broken".

This is a design flaw in the rule, not in these results, and disclosing it makes
*more* of this output null rather than less. The rule is **not amended
retroactively.** A future registration should gate VOID on the control clearing
an absolute bar, not on it merely out-scoring a null arm.
