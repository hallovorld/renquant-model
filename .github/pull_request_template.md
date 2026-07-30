<!-- Keep this body SHORT. Durable detail belongs in the doc the checklist names. -->

## What
<one paragraph — what changed and why, in brief>

## Checklist (repo contract)
- [ ] Tests pass, or this is docs-only (say so). If a fix changes behaviour, a test **fails without it**.
- [ ] Baseline recorded: suite counts on `origin/main` **and** on this branch, side by side. Any new failure is **explained**, not absorbed by editing the test.
- [ ] English throughout; no live production inputs touched; not self-merged (Codex reviews).
- [ ] **Gate design rule (GOAL-5 AC6):** if this PR adds/tightens a HARD capital-admission gate (can take a name or the book from tradeable→not-tradeable via `raise` / zero-candidates / sell-only / buy-block, not a market decision), the PR states its **governed override path** — *identity* (who lifts it, via what reviewed surface), *expiry* (explicit restore condition + auto-alarm, **not "temporary"**), *binding* (scoped by fingerprint + provenance in the run bundle). True kill-switches say so explicitly. **N/A if no such gate.** Canonical: `renquant-orchestrator doc/design/2026-07-20-ac6-gate-design-rule.md`; Universal Rule §7 in `RenQuant doc/arch/subrepo-operating-model.md`.
- [ ] **Prereg discipline.** A study PR states whether its design commit precedes its results commit, and any confirmatory estimand names a **naive single-column baseline** drawn from the model own most-used inputs (`doc/research/templates/PREREG_TEMPLATE.md` T16 / §5b). A clean placebo panel does not license an interpretation.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
