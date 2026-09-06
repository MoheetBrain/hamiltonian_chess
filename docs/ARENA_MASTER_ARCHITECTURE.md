# Arena Master Architecture

## Six layers

1. **Canonical truth** — versioned typed states, actions, transitions, verification, stable
   mathematical identity. Candidate code cannot write truth.
2. **Model-view genome** — Track E reversible codec choices plus Track C truth-derived
   projections. Every addition and omission is accounted.
3. **Fitness instrument** — independent oracle, positive/counterfactual/destructive/swap
   families, frozen model/runtime/prompt/statistics.
4. **Population search** — founders, one-gene matched children, lineage, novelty, Pareto gates.
5. **Hidden validation and matched learning** — fresh promotion/OOD, then equal-budget training
   only after stable behavioral evidence.
6. **R* trajectory factory** — released representation/protocol generates verified state-action
   trajectories only after all prior gates pass.

## Seven contracts

- **Architect:** proposes typed genes, mutations, corpus or instrument requests; cannot see
  sealed answers or change truth/verifiers/scoring.
- **Builder:** deterministically compiles typed proposals; has no creative or judging authority.
- **Experimentalist:** accepts or rejects instruments using dumb rules, positive/destructive
  controls, counterfactuals, swaps, malformed outputs, and floor/ceiling checks.
- **Solver:** sees only the permitted candidate view and tools; never sees an oracle label.
- **Refuter:** runs deterministic adversarial checks, then verifies and minimizes suggested
  exploits; every confirmed failure becomes regression memory.
- **Curriculum designer:** maximizes information and mechanism coverage from verified pools;
  cannot use sealed outcomes or representation winners to select tasks.
- **League manager:** enforces eligibility, niches, Pareto/Hall-of-Fame state, promotion,
  retirement, and halving; cannot override semantic death gates.

The event log is the single source for any future visual game. Models propose; deterministic
compilers, verifiers, and frozen statistical gates decide.
