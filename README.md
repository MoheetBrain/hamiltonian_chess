# Hamiltonian Arena

Hamiltonian Arena is an evidence-first experimental system for comparing and evolving
machine-facing mathematical representations. Mathematical truth lives in a versioned
canonical IR and independent verifiers; candidate languages are reversible views over that
IR. A syntax cannot earn fitness by changing what a mathematical state means.

GOAL= Feed the system a huge verified mathematical world + agents + a space of possible language designs. Let agents repeatedly invent, test, learn, mutate and recombine mathematical languages until they discover languages that make AI better at mathematics than English.

The repository is an isolated successor experiment. It treats Structured English,
HML-compatible syntax, S-expressions, JSON ASTs, typed prefix forms, compact symbolic forms,
graph triples, and role-labelled hybrids as equal seed candidates.

## Quick start

```bash
uv sync --all-extras
uv run arena init
uv run arena worlds build --count 600
uv run arena languages seed
uv run arena league run --tier 1
uv run arena status
uv run pytest
```

No command may freeze `R*-V0` unless every hard release gate is backed by stored evidence.
The absence of a winner is a valid scientific result.

The checked-in v0 artifacts contain 676 tasks, eight seed evaluations, one static Pareto
league, and an explicit `RSTAR_BLOCKED_BY_MODEL_FITNESS` decision. `L5_COMPACT_SYMBOLIC` is
only the static byte-cost frontier; it is not an R* winner.

## Design boundary

```text
canonical mathematics -> candidate renderer -> model surface -> solver action
          ^                                            |
          +--------------- verifier -------------------+
```

Execution metadata, model identity, timing, and timestamps do not participate in canonical
mathematical identity. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/CURRENT_STATE.md](docs/CURRENT_STATE.md).

Protocol details live in [docs/ARENA_PROTOCOL.md](docs/ARENA_PROTOCOL.md), the genome in
[docs/LANGUAGE_GENOME.md](docs/LANGUAGE_GENOME.md), soundness boundaries in
[docs/SOUNDNESS.md](docs/SOUNDNESS.md), and the live sprint gate in
[docs/FOUR_DAY_SPRINT.md](docs/FOUR_DAY_SPRINT.md).
