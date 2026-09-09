# Lean session branching — the load-bearing fact under HC-V0.6

```bash
.venv/bin/python -m research.phase10.branching.probe_branching
```

HC-V0.6 compares two renderings **at the same anchored Lean state**. The guarantee that the arms
saw identical mathematics comes from stepping the same live `state_id` once per arm inside one
session, rather than re-deriving the state for each arm. That is only sound if a successful step
leaves its parent usable and produces a genuinely distinct child.

Measured 2026-09-08, 6 theorems from the LeanDojo **train** split, Lean 4.10.0-rc1 at the built
mathlib checkout:

| property | result |
|---|---|
| two successful steps from one parent give **distinct** child state ids | 6 / 6 |
| the first child's state text is intact after further steps from the parent | always |
| the parent's state text is unchanged after all branches | always |
| a branch taken from a **child** state also succeeds | 6 / 6 |
| the theorem's own first recorded tactic is accepted at the root | 6 / 6 |

An earlier, blunter version of this probe fired seven generic tactics at each root and concluded
nothing: 26 of 28 were `TACTIC_ERROR`, so no theorem ever produced two children and the branching
property was never actually exercised. It is recorded here because "the parent survived seven
rejected steps" reads like evidence and is not — a rejected step never had a chance to invalidate
the handle. The rewrite uses `skip`, which succeeds on any open goal, precisely so that both
branches are real.

Raw output: `out/branching.json`.
