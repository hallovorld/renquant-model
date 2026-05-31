# P1 Linear Research — Known Limitations

Tracks open issues against `renquant_model_linear.research` /
`renquant_model_linear.trainer` so the PR shipping each fix can close them
deterministically.

## L1 · No thread-parallel CPU execution (PR #15 review blocker)

**Status**: contained by `scheduler="linear"` forcing in research CLI +
process-wide lock in trainer. True per-trial isolation pending.

### Symptom
Reviewer reproduced empirically on PR #15 head `7d122dd`:
- Sequential `train_single_run(seed=k)` for `k ∈ {1,2,3,4}` ⇒ stable
  val-pred hashes and ICs.
- Five thread-parallel repetitions of the same four calls ⇒ all four
  artifacts mismatched the sequential reference; seed 1's IC drifted
  from `-0.1324` to values like `+0.0625`, `+0.1458`, `-0.2336`
  depending on interleaving.

### Root cause
`train_single_run` mutates process-global RNG state at start:
```python
torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
```
and downstream operations consume that state:
- `load_panel_with_split(..., shuffle_labels=True)` calls
  `np.random.permutation`.
- DLinear / NLinear weight init uses `torch.nn.Linear` default init
  (consumes torch global RNG).
- Training-loop dropout (none in current DLinear/NLinear bodies, but
  any future addition would race).

`renquant_common.run_parallel` uses a `ThreadPoolExecutor` on CPU. Two
trials A and B running concurrently:
1. Trial A: `_set_seed(S_A)` → global RNG = S_A
2. Trial B: `_set_seed(S_B)` → global RNG = S_B   (clobbers A)
3. Trial A: `Linear(...)` init → consumes seed S_B (wrong!)
4. Persisted artifact for trial A ≠ deterministic function of `S_A`.

The scientific evidence contract — "same cut+seed produces byte-identical
artifact" — is broken whenever `scheduler ∈ {auto, parallel}` and
`device=cpu`.

### Contained-by

**1. Research CLI forces linear scheduling.**
`renquant_model_linear.research._force_linear_scheduler` downgrades
`scheduler ∈ {auto, parallel}` to `"linear"` with a logged warning, so
the default linear-research path runs trials sequentially.

**2. Trainer-level process-wide lock.**
`renquant_model_linear.trainer._TRAINER_LOCK` (a `threading.Lock`)
serializes the entire `train_single_run` body. This protects direct
callers (ad-hoc concurrent driver scripts, Optuna trials wired against
the trainer module) even when they bypass the research CLI.

### Long-term fix
Plumb per-trial `torch.Generator()` + `np.random.Generator()` through
the trainer:
- `_set_seed` returns generators instead of mutating globals.
- `load_panel_with_split` accepts an `rng=` kwarg for permutation.
- `_build_model` accepts a `generator=` for weight init
  (`torch.nn.init.kaiming_uniform_(weight, generator=g)` etc.).
- Drop `_TRAINER_LOCK` once true isolation lands.
- Remove `_force_linear_scheduler` once the regression test verifying
  thread-parallel determinism passes.

### Regression test
`tests/patchtst/test_dlinear_trainer.py::test_linear_research_cli_forces_linear_scheduler`
pins the CLI behavior.

`tests/patchtst/test_dlinear_trainer.py::test_train_single_run_holds_trainer_lock`
pins the lock contract.

When the long-term fix lands, replace these with the actual
sequential-vs-parallel determinism test the reviewer requested.
