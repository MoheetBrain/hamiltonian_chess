# Arena Protocol

## Players and physics

- Architect proposes auditable genome mutations; it cannot change canonical truth.
- Solver sees only the candidate-language observation and returns a declared schema.
- Refuter attacks scope, binding, types, partiality, evidence, obligations, illegal actions,
  exactness, probability roles, shapes, and parser behavior; failures are minimized and stored.
- Curriculum selects tasks by disagreement, expected ranking information, frontier uncertainty,
  and mechanism novelty rather than raw difficulty.
- League Manager keeps multi-axis ratings, Pareto fronts, and a frozen Hall of Fame.
- Verifiers are physics, not players: native structural checks, SymPy, Z3, numerical
  falsification, and an inspected Lean environment.

## Deterministic run

```bash
uv sync --all-extras
uv run arena init
uv run arena worlds build --count 676 --seed 0
uv run arena worlds validate
uv run arena languages seed
uv run arena mutate --parent L1_CURRENT_HML --n 20 --seed 0
uv run arena league run --tier 1
uv run arena assure L5_COMPACT_SYMBOLIC
uv run arena rstar freeze L5_COMPACT_SYMBOLIC
uv run arena status
```

The freeze command exits non-zero and creates no `artifacts/rstar/v0` directory when a gate is
missing. All primary records enter SQLite; large or human-readable results are
content-addressed artifacts.

## Evaluation tiers

- Tier 0: static codec, canonical roundtrip, reconstruction, coverage, and cost.
- Tier 1: Tier 0 plus assurance-facing diagnostics and league placement.
- Tier 2: explicitly configured matched adaptation. The generic CLI refuses to imply that a
  Tier-2 run occurred; a concrete runner must supply the model and training evidence.

The frozen-model scout is labelled separately and cannot satisfy the matched-learning gate.
