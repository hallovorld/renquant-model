#!/usr/bin/env python3
"""Execute the frozen traded-estimand rule. The rule refuses, the runner obeys.

`doc/research/2026-07-29-traded-estimand-prereg.md` §7 states a decision
procedure. A procedure written in prose is a promise; two verdicts on this
programme have already been published and retracted because a promise was
followed loosely. This runner makes the two properties that actually matter
mechanical:

  1. **It will not run before the prereg is frozen.** Frozen means merged into
     `origin/main`. Until then the estimand can still be edited by whoever is
     about to read the answer, which is the definition of not-preregistered.
     `--i-am-not-preregistering` exists for rehearsal and stamps every line of
     output as REHEARSAL so a rehearsal transcript can never be mistaken for a
     verdict.

  2. **Controls run FIRST, and a VOID never computes the real arm.** Not
     "computes it and declines to print it" — never computes it. If a human
     can read the treatment effect off a voided run, the void is advisory, and
     an advisory void is how a HARKed estimand gets chosen.

Everything else — the estimand, the estimator, the control protocol, the
verdict thresholds — is read from the prereg's registered constants and is not
re-litigated here.

Read-only. Reads corpora, writes nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from renquant_model_common.control_calibration import gate_comparison  # noqa: E402
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402

#: Registered in prereg §2 / §4 / §5. Changing any of these makes a run a new
#: screen requiring a new registration (§7.4), so they are constants, not flags.
PREREG_DOC = "doc/research/2026-07-29-traded-estimand-prereg.md"
LABEL = "fwd_60d_excess"
BLOCK_TDAYS = 60
TOP_FRACTION = 0.10
MIN_NAMES_PER_DATE = 20
N_CONTROL_SEEDS = 5
N_BOOT = 3000

VOID = "VOID"
RESOLVED_POSITIVE = "RESOLVED-POSITIVE"
RESOLVED_NEGATIVE = "RESOLVED-NEGATIVE"
UNRESOLVED = "UNRESOLVED"


class PreregNotFrozen(RuntimeError):
    """Raised when the rule would run before it is merged."""


def prereg_is_frozen(repo: str = ".") -> tuple[bool, str]:
    """Is the prereg present on `origin/main`, AND is the locally-visible copy
    byte-identical to it?

    Both halves matter. Existence-on-remote alone is not enough: once the
    prereg has merged once, a later unmerged local edit to the same path
    still exists nowhere except the local worktree, so a check that only asks
    "does origin/main have this path" would pass forever after the first
    merge — even while the copy actually driving this run has since diverged.
    That is exactly the loophole preregistration exists to close, so this
    also hashes the local file and rejects any mismatch against the frozen
    `origin/main` blob.
    """
    try:
        exists = subprocess.run(
            ["git", "-C", repo, "cat-file", "-e", f"origin/main:{PREREG_DOC}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"cannot query git ({exc})"
    if exists.returncode != 0:
        return False, (f"{PREREG_DOC} is NOT on origin/main — the prereg has "
                       f"not merged, so its rule is not frozen")
    try:
        remote_hash = subprocess.run(
            ["git", "-C", repo, "rev-parse", f"origin/main:{PREREG_DOC}"],
            capture_output=True, text=True, timeout=30,
        )
        local_hash = subprocess.run(
            ["git", "-C", repo, "hash-object", PREREG_DOC],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"cannot verify the local copy against origin/main ({exc})"
    if remote_hash.returncode != 0 or local_hash.returncode != 0:
        return False, (f"{PREREG_DOC} could not be hashed locally — treated "
                       f"as not frozen")
    if remote_hash.stdout.strip() != local_hash.stdout.strip():
        return False, (f"{PREREG_DOC} on origin/main does not match the local "
                       f"working copy byte-for-byte — a local edit to the "
                       f"frozen prereg, even unmerged, disqualifies this run")
    return True, f"{PREREG_DOC} present on origin/main and matches the local copy exactly"


def spread_per_date(frame: pd.DataFrame, ycol: str) -> pd.Series:
    """Prereg §2: mean(top-k) - mean(the REMAINING n-k). Arms are complements.

    An earlier revision took the arms as `nlargest(k)` and `nsmallest(n-k)`,
    which select INDEPENDENTLY: when `raw` ties across the k boundary the same
    row lands in both arms. In the degenerate all-ties case `nlargest(1)` and
    `nsmallest(n-1)` both return row 0, so the bottom arm was not the
    complement of the top and the statistic was not the registered estimand.
    This affected the real arm AND every control arm, since both route
    through here.

    Fixed by sorting ONCE on a declared deterministic tie policy and
    splitting by POSITION, which makes complementarity structural instead of
    contingent on the tie distribution. Tie policy: `raw` descending, then
    `ticker` ascending — reproducible across row orderings, not merely stable
    within one file. Kept identical to the same fix in
    `tools/traded_estimand_calibration.py`: one estimand, one implementation
    of it, and a test pins the twin against drifting.
    """
    tiebreak = ["raw", "ticker"] if "ticker" in frame.columns else ["raw"]
    ascending = [False, True][:len(tiebreak)]

    def one(g: pd.DataFrame) -> float:
        if len(g) < MIN_NAMES_PER_DATE:
            return np.nan
        k = max(1, int(round(len(g) * TOP_FRACTION)))
        if k >= len(g):                       # no complement to compare against
            return np.nan
        ordered = g.sort_values(tiebreak, ascending=ascending, kind="mergesort")
        top = ordered.iloc[:k]
        rest = ordered.iloc[k:]               # exact complement, by construction
        return top[ycol].mean() - rest[ycol].mean()
    return frame.groupby("date").apply(one, include_groups=False).dropna()


def control_arms(frame: pd.DataFrame, fold_of: pd.Series) -> dict[str, list[float]]:
    """Prereg §5: within-date label shuffles, aggregated to FOLD means."""
    out: dict[str, list[float]] = {}
    for seed in range(N_CONTROL_SEEDS):
        rng = np.random.default_rng(seed)
        shuffled = frame.copy()
        shuffled["y_shuf"] = shuffled.groupby("date")[LABEL].transform(
            lambda s: rng.permutation(s.values))
        per_date = spread_per_date(shuffled, "y_shuf")
        fold_means = per_date.groupby(fold_of.reindex(per_date.index)).mean()
        out[f"shuffle_seed{seed}"] = list(fold_means.dropna().values)
    return out


@dataclass
class Outcome:
    subject: str
    verdict: str
    reason: str
    corpus_sha256: str
    rehearsal: bool
    control_verdicts: list = field(default_factory=list)
    #: Populated ONLY when the controls passed. On a VOID this stays None and
    #: the real arm is never computed — see the module docstring.
    real: dict | None = None

    def describe(self) -> str:
        tag = "REHEARSAL — NOT A VERDICT | " if self.rehearsal else ""
        lines = [f"{tag}subject={self.subject}  verdict={self.verdict}",
                 f"{tag}corpus sha256={self.corpus_sha256}",
                 f"{tag}{self.reason}"]
        for v in self.control_verdicts:
            lines.append(f"{tag}  control {v.describe()}")
        if self.real is not None:
            r = self.real
            lines.append(
                f"{tag}  real arm: spread={r['mean']:+.4f} sd  "
                f"block_t={r['block_t']:+.2f}  "
                f"CI=[{r['ci_low']:+.4f},{r['ci_high']:+.4f}]  "
                f"lobo=[{r['lobo_low']:+.4f},{r['lobo_high']:+.4f}]")
        else:
            lines.append(f"{tag}  real arm: NOT COMPUTED")
        return "\n".join(lines)


def run_subject(frame: pd.DataFrame, *, subject: str, corpus_sha256: str,
                rehearsal: bool) -> Outcome:
    frame = frame.dropna(subset=["raw", LABEL])
    fold_of = frame.drop_duplicates("date").set_index("date")["fold_idx"]

    # §7.1 — controls FIRST.
    may_proceed, verdicts = gate_comparison(control_arms(frame, fold_of))
    if not may_proceed:
        bad = ", ".join(v.name for v in verdicts if not v.usable)
        return Outcome(
            subject=subject, verdict=VOID,
            reason=(f"control(s) {bad} are not null, so the comparison is VOID "
                    f"(§7.1). The real arm was NOT computed — a void a reader "
                    f"can see through is advisory, and an advisory void is how "
                    f"an estimand gets chosen after the fact."),
            corpus_sha256=corpus_sha256, rehearsal=rehearsal,
            control_verdicts=verdicts)

    # §7.2 — only now.
    per_date = spread_per_date(frame, LABEL)
    r = dependence_aware_mean(list(per_date.values),
                              block_length=BLOCK_TDAYS, n_boot=N_BOOT)
    real = {"mean": r.mean, "block_t": r.block_t, "ci_low": r.ci_low,
            "ci_high": r.ci_high, "lobo_low": r.lobo_low,
            "lobo_high": r.lobo_high, "n_blocks": r.n_blocks}

    # §7.3 — thresholds as registered.
    max_control_t = max((abs(v.t_stat) for v in verdicts), default=0.0)
    positive = (r.resolves and r.ci_low > 0 and r.mean > 0
                and abs(r.block_t) > max_control_t)
    negative = r.resolves and r.ci_high < 0 and r.mean < 0
    if positive:
        verdict, why = RESOLVED_POSITIVE, (
            f"all three views positive, CI low {r.ci_low:+.4f} > 0, and the "
            f"real |t| {abs(r.block_t):.2f} exceeds the largest control |t| "
            f"{max_control_t:.2f}")
    elif negative:
        verdict, why = RESOLVED_NEGATIVE, (
            f"all three views negative and CI high {r.ci_high:+.4f} < 0")
    else:
        verdict, why = UNRESOLVED, (
            "the three views do not agree with a CI excluding zero. Per §6 "
            "this is a statement about POWER, not about the model, and must "
            "not be reported as a negative.")
    return Outcome(subject=subject, verdict=verdict, reason=why,
                   corpus_sha256=corpus_sha256, rehearsal=rehearsal,
                   control_verdicts=verdicts, real=real)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subject", required=True,
                    help="registered subject name, e.g. patchtst / prod_xgb")
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--i-am-not-preregistering", action="store_true",
                    help="rehearsal on an unmerged prereg; output is stamped "
                         "REHEARSAL and is not a verdict")
    args = ap.parse_args(argv)

    frozen, note = prereg_is_frozen(args.repo)
    if not frozen and not args.i_am_not_preregistering:
        raise PreregNotFrozen(
            f"REFUSING TO RUN: {note}. Merge the prereg first, or pass "
            f"--i-am-not-preregistering to rehearse (output will be stamped "
            f"REHEARSAL and cannot be cited)."
        )
    print(f"prereg: {note}")

    corpus = pd.read_parquet(args.corpus)
    digest = hashlib.sha256(args.corpus.read_bytes()).hexdigest()
    # The flag FORCES rehearsal, it does not merely permit running unfrozen.
    # `rehearsal = not frozen` alone meant that once the prereg was frozen the
    # flag silently stopped stamping, so a rehearsal on a frozen prereg
    # produced output indistinguishable from a verdict — the one direction
    # this stamp exists to prevent.
    rehearsal = (not frozen) or args.i_am_not_preregistering
    outcome = run_subject(corpus, subject=args.subject, corpus_sha256=digest,
                          rehearsal=rehearsal)
    print(outcome.describe())
    print("\nPer §10, no verdict is published until it survives a commissioned "
          "adversarial review briefed to refute it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
