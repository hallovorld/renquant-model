# GOAL-6 Stage 0 — Amendment 4 (visible, PRE-RUN): the paired-contrast aggregation object, frozen

**Amends §5's `t_pair` definition only. Filed before any execution, on the codex
review of the runner (model#174): the seed-aggregation choice changes the inferential
object and its variance, so it is design, not implementation — exactly the boundary
the momentum chain's Amendment 4 settled for its own gates.**

## The defect

§5 as frozen: *"the paired contrast statistic `t_pair(A,B)` is the block-level t of
the per-seed difference series `Δ_A(s) − Δ_B(s)`, s = 1..20, using the same
block-length rule"*. The block rule operates on DATES; the per-seed series indexes
SEEDS. A 20-element seed-indexed sequence has no date blocks to apply — the sentence
is not implementable as written (the same executable-rule failure class as the four
defects Amendments 2–3 repaired).

## The frozen replacement

For arms A and B of a contrast (two statistics at one horizon for H1; one statistic
at two horizons for H2), all on the SAME 20 permutation draws (seeds `20260801+i`,
i = 0..19, paired per date):

1. per date `t` and seed `s`: `δ_X(s, t) = REAL_X(t) − PERM_X(s, t)`;
2. per date, the seed mean: `δ̄_X(t) = (1/20) Σ_s δ_X(s, t)` — the Monte-Carlo
   estimate of REAL minus the permutation-null expectation at that date;
3. the contrast series `D(t) = δ̄_A(t) − δ̄_B(t)`;
4. `t_pair` = the Amendment-3 gap-block t of `D(t)` (H1: blocks at the contrast's
   common horizon; H2: blocks at h = 60 on the two horizons' eligible-date
   intersection — the larger horizon's geometry, the conservative choice);
5. DIAGNOSTIC (no α budget): the across-seed dispersion `sd_s(δ_X(s, t))`, published
   per arm as a per-date summary, so the 20-draw Monte-Carlo noise floor is visible
   next to the decision statistic it feeds.

Rationale: the pairing the prereg wanted — same draws on both sides so seed noise
cancels in `D(t)` — is preserved exactly; the seed MEAN is the only aggregation that
yields a date-indexed series the frozen block rule can consume. Averaging first
shrinks permutation-MC noise by √20 and leaves the date-level dependence structure —
what the blocks exist to handle — untouched.

## Not amended

The 20-seed count, the within-date permutation construction, every H1/H2 threshold,
Holm at family α = 0.10, the §5 persistence VETO (t ≥ 1.0, positive — which the
runner must WIRE, a separate review item), and everything Amendments 1–3 froze.

## Not claimed

That this is the only defensible aggregation — a per-seed block-t distribution
(20 block t's, one per seed) is also coherent; it was not chosen because it makes the
decision statistic a DISTRIBUTION and the frozen decision rule expects a scalar. That
choice is closed here, pre-run, which is the point of the amendment.
