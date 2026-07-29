#!/usr/bin/env python3
"""Reproduce every calibration number in the traded-estimand prereg.

The prereg (`doc/research/2026-07-29-traded-estimand-prereg.md`) is frozen on
measured quantities. This is their derivation: it pins each input by sha256,
ABORTS on a mismatch, seeds every draw deterministically, and prints the
numbers the prereg states — so a reviewer can audit the registration decision
from the branch instead of taking `[VERIFIED — this session]` on trust.

    python3 tools/traded_estimand_calibration.py \\
        --clf-corpus     <scratch>/clf-wf/clf_wf_scores.parquet \\
        --patchtst-corpus <scratch>/wf-eval/scores.parquet \\
        --panel /Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet

Sections map 1:1 onto the prereg:
  A  §2   label units  -> the statistic is in sd, not return
  B  §3   the SCREEN (clf real arm + 5 shuffle placebos)
  C  §6   null CI half-width
  D  §5   assess_control false-flag rate, by aggregation unit
  E  §5   the shift120 ban  (PatchTST corpus, NOT the clf one)

All inputs READ-ONLY. Nothing is written anywhere.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# APPEND, not insert(0): an explicitly-set PYTHONPATH must win, otherwise this
# script silently shadows the very module a reviewer pointed it at.
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402

try:
    from renquant_model_common.control_calibration import assess_control
except ImportError:  # pragma: no cover - ordering, not logic
    assess_control = None  # section D needs renquant-model#96 to be merged

PINNED = {
    "clf_wf_scores.parquet":
        "1da3fcfab06af1e597ac0eb83dff4741ed3dd027de8b8a6b4d58979f5bc4efe4",
    "scores.parquet":
        "6eb209e2491b26b18b7b687c7683f27f8e5cbe56592186bfbac68381e2606d18",
    "transformer_v4_wl200_clean.parquet":
        "3982ca545d4c109b4809b887f2f9bbfc1a9363f7889b6a2ba08504e2668f0676",
}

LABEL = "fwd_60d_excess"
BLOCK = 60
TOP_FRACTION = 0.10
MIN_NAMES = 20
SHIFT_DAYS = 120


def check_pin(path: Path, *, allow_mismatch: bool) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = PINNED.get(path.name)
    if expected is None:
        print(f"  {path.name}: sha256={digest} (not pinned)")
        return
    if digest == expected:
        print(f"  {path.name}: sha256={digest[:16]}… PIN OK")
        return
    msg = (f"{path.name} sha256={digest} != pinned {expected}; the prereg's "
           f"numbers were derived from the pinned input.")
    if not allow_mismatch:
        raise SystemExit(f"ABORT: {msg}")
    print(f"  WARNING: {msg}")


def spread_per_date(frame: pd.DataFrame, ycol: str) -> pd.Series:
    def one(g: pd.DataFrame) -> float:
        if len(g) < MIN_NAMES:
            return np.nan
        k = max(1, int(round(len(g) * TOP_FRACTION)))
        return (g.nlargest(k, "raw")[ycol].mean()
                - g.nsmallest(len(g) - k, "raw")[ycol].mean())
    return frame.groupby("date").apply(one, include_groups=False).dropna()


def shuffled(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = frame.copy()
    out["y_shuf"] = out.groupby("date")[LABEL].transform(
        lambda s: rng.permutation(s.values))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # SUBJECT-PARAMETERISED. Prereg SS5 Amendment 1 requires EVERY confirmatory
    # subject to measure its OWN 30-shuffle false-flag rate before a verdict.
    # The first revision only ran section D on --clf-corpus, so PatchTST and
    # prod XGB had no execution path for a prerequisite the document calls
    # mandatory — the protocol was registered but not executable for the
    # subjects it names. --subject/--corpus closes that.
    ap.add_argument("--subject", required=True,
                    help="registered subject name, e.g. clf / patchtst / prod_xgb")
    ap.add_argument("--corpus", required=True, type=Path,
                    help="that subject's score corpus (sections A/C/D run on IT)")
    ap.add_argument("--screen-corpus", type=Path, default=None,
                    help="optional: the already-consumed clf corpus, for the "
                         "SS3 screen reproduction only")
    ap.add_argument("--patchtst-corpus", type=Path, default=None,
                    help="optional: for the SS5 shift120 ban (PatchTST corpus)")
    ap.add_argument("--panel", type=Path, default=None)
    ap.add_argument("--allow-input-mismatch", action="store_true")
    ap.add_argument("--require-pinned", action="store_true",
                    help="FULL verification: fail if any supplied input is not "
                         "in the PINNED table. Without it the run is PARTIAL.")
    args = ap.parse_args(argv)

    print(f"SUBJECT: {args.subject}")
    print("INPUTS")
    supplied = [x for x in (args.corpus, args.screen_corpus,
                            args.patchtst_corpus, args.panel) if x is not None]
    missing = [x for x in supplied if not x.exists()]
    if missing:
        raise SystemExit("ABORT: required input(s) do not exist: "
                         + ", ".join(str(m) for m in missing))
    unpinned = []
    for p in supplied:
        d = check_pin(p, allow_mismatch=args.allow_input_mismatch)
        if PINNED.get(p.name) is None:
            unpinned.append(p.name)
    if args.require_pinned and unpinned:
        raise SystemExit(
            "ABORT (--require-pinned): not in the PINNED table: "
            + ", ".join(unpinned)
            + ". A FULL verification cannot rest on an unpinned input; add its "
              "digest to PINNED or drop --require-pinned and accept a PARTIAL run.")
    sections = ["A", "C", "D"] + (["B"] if args.screen_corpus else []) + \
               (["E"] if (args.patchtst_corpus and args.panel) else [])
    mode = "FULL" if (args.require_pinned and not unpinned) else "PARTIAL"
    print(f"\nVERIFICATION MODE: {mode}  sections={sorted(sections)}")
    if mode == "PARTIAL":
        print("   (PARTIAL: not every section ran and/or an input is unpinned. "
              "Not the all-sections command the docs describe.)")

    # Corpora differ in whether the label is INLINE. The clf corpus carries
    # fwd_60d_excess; the PatchTST corpus carries only raw/cal and the label
    # must be joined from the panel. That difference is exactly why the first
    # revision could not run this calibration for PatchTST or prod XGB — the
    # registered protocol was not executable for the subjects it named.
    clf = pd.read_parquet(args.corpus)
    if LABEL not in clf.columns:
        if args.panel is None or not args.panel.exists():
            raise SystemExit(
                f"ABORT: subject corpus {args.corpus.name} has no `{LABEL}` "
                f"column, so the label must be joined from --panel, which was "
                f"not supplied. SS5 Amendment 1's per-subject calibration cannot "
                f"be measured without it. Columns present: "
                f"{sorted(clf.columns)[:8]}")
        clf["date"] = pd.to_datetime(clf["date"])
        panel = pd.read_parquet(args.panel, columns=["date", "ticker", LABEL])
        panel["date"] = pd.to_datetime(panel["date"])
        before = len(clf)
        clf = clf.merge(panel, on=["date", "ticker"], how="left")
        print(f"   label `{LABEL}` joined from {args.panel.name}: "
              f"{clf[LABEL].notna().sum()}/{before} rows matched")
    clf = clf.dropna(subset=["raw", LABEL])
    fold_of = clf.drop_duplicates("date").set_index("date")["fold_idx"]

    print(f"\nA. PREREG §2 — label units ({LABEL}) — subject={args.subject}")
    y = clf[LABEL]
    print(f"   mean={y.mean():+.4f}  sd={y.std():.4f}")
    print(f"   -> the statistic is in STANDARD DEVIATIONS, not return")

    # SS3's screen is a clf-corpus ARTEFACT, not part of any subject's
    # calibration. Running it against a confirmatory subject's corpus would
    # compute the very quantity the prereg forbids reading before the
    # controls pass, so it is gated behind an explicit --screen-corpus.
    if args.screen_corpus is None:
        print("\nB. PREREG §3 — SKIPPED (no --screen-corpus). The screen is a "
              "clf artefact; it is NOT part of a subject's calibration.")
    else:
        print("\nB. PREREG §3 — the SCREEN (already observed; cannot confirm itself)")
        scr = pd.read_parquet(args.screen_corpus).dropna(subset=["raw", LABEL])
        real = spread_per_date(scr, LABEL)
        r = dependence_aware_mean(list(real.values), block_length=BLOCK,
                                  n_boot=3000)
        print(f"   screen real arm : spread={r.mean:+.4f} sd  "
              f"block_t={r.block_t:+.2f}  "
              f"CI=[{r.ci_low:+.4f},{r.ci_high:+.4f}]  resolves={r.resolves}")
        ts = []
        for seed in range(5):
            v = spread_per_date(shuffled(scr, seed), "y_shuf")
            rs = dependence_aware_mean(list(v.values), block_length=BLOCK,
                                       n_boot=800)
            ts.append(abs(rs.block_t))
        print(f"   5 shuffle placebos: max |block_t| = {max(ts):.2f}  "
              f"(none resolving is the requirement)")

    print("\nC. PREREG §6 — null CI half-width (12 clean shuffles)")
    hws = []
    for seed in range(1000, 1012):
        v = spread_per_date(shuffled(clf, seed), "y_shuf")
        rs = dependence_aware_mean(list(v.values), block_length=BLOCK, n_boot=600)
        hws.append((rs.ci_high - rs.ci_low) / 2)
    print(f"   median half-width under the null = {np.median(hws):.4f} sd")
    print(f"   -> the MDE is set by the ALTERNATIVE's dispersion, not the "
          f"null's; a subject's own real-arm half-width is reported by the "
          f"RUNNER at verdict time, not here (reading it here would preempt "
          f"the controls-first ordering)")

    print(f"\nD. PREREG §5 Amd.1 — false-flag rate on 30 CLEAN nulls, subject={args.subject}")
    if assess_control is None:
        raise SystemExit(
            "ABORT: renquant_model_common.control_calibration is not "
            "importable, so SS5 Amendment 1's mandatory per-subject false-flag "
            "rate CANNOT be measured. #96 is merged on main, so this means a "
            "broken import path, not a missing dependency. Refusing to report a "
            "calibration that omits a section the prereg calls mandatory.")
    flag = {"fold means": 0, "block means": 0}
    if assess_control is not None:
        for seed in range(5000, 5030):
            v = spread_per_date(shuffled(clf, seed), "y_shuf")
            rs = dependence_aware_mean(list(v.values), block_length=BLOCK,
                                       n_boot=400)
            if abs(rs.block_t) > 2.0:
                flag["block means"] += 1
            fm = v.groupby(fold_of.reindex(v.index)).mean()
            if not assess_control(list(fm.values), name="s").usable:
                flag["fold means"] += 1
        for unit, n in flag.items():
            print(f"   fed {unit:12}: {n}/30 = {n / 30:.0%}"
                  + ("   <- REGISTERED UNIT" if unit == "fold means" else ""))
        p = flag["fold means"] / 30
        print(f"   ALL-clean over 5 controls -> P(valid experiment survives) "
              f"= {(1 - p) ** 5:.0%}, i.e. ~{1 - (1 - p) ** 5:.0%} voided by "
              f"chance")

    if args.patchtst_corpus and args.panel and args.patchtst_corpus.exists():
        print("\nE. PREREG §5 — the shift120 ban")
        print("   NOTE: measured on the PatchTST corpus, NOT the clf one.")
        sc = pd.read_parquet(args.patchtst_corpus)
        sc["date"] = pd.to_datetime(sc["date"])
        panel = pd.read_parquet(args.panel, columns=["date", "ticker", LABEL])
        panel["date"] = pd.to_datetime(panel["date"])
        lab = panel.pivot(index="date", columns="ticker", values=LABEL).sort_index()
        merged = (sc.merge(lab.stack().rename("y_real").reset_index(),
                           on=["date", "ticker"], how="left")
                    .merge(lab.shift(-SHIFT_DAYS).stack().rename("y_shift")
                           .reset_index(), on=["date", "ticker"], how="left"))
        from scipy import stats as st
        fold = merged.drop_duplicates("date").set_index("date")["fold_idx"]
        for arm, col in (("real", "y_real"), ("shift120", "y_shift")):
            d = merged.dropna(subset=["raw", col])
            ic = d.groupby("date").apply(
                lambda g: g["raw"].corr(g[col], method="spearman"),
                include_groups=False).dropna()
            fm = ic.groupby(fold.reindex(ic.index)).mean().dropna()
            t, _ = st.ttest_1samp(fm.values, 0)
            print(f"   {arm:9}: fold-mean IC={fm.mean():+.4f}  t={t:+.2f}  "
                  f"n_folds={len(fm)}")
        print("   -> a control more significant than the arm it nulls is not a "
              "control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
