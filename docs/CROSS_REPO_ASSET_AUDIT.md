# Cross-repository asset audit

Audit date: 2026-09-05. Arena start commit: `c1dd586db6abb9bd4e72f0048122eb4ddca98739`.

This audit was completed before implementing the representation-fitness continuation. It
searched every remote branch, tag, and reachable commit in the four required private
repositories, rather than treating their default branches as authoritative. Local clones were
also searched under `/Users/moheet/Documents/ChatGPT`; isolated filtered clones under `/tmp`
were used for inspection so no historical worktree was changed.

## Repositories and scientifically important states

| Repository | Important inspected state | Commit | Role |
|---|---|---|---|
| `MoheetBrain/HML_V3` | `codex/open-ended-search-v2` | `4395a8c717a334be58b29d53b43c0c842d0e03ac` | Later renderer search, MicroMath calibration, failure memory |
| `MoheetBrain/HML_V3` | `codex/lean-runtime-semantic-capture-v2` | `99475f4f64b1c47c91b588e8a5b08fed70ca117b` | Lean/runtime capture and corpus architecture |
| `MoheetBrain/HML_V3` | `codex/evidence-first-foundation` | `5d4d7a683cfb081733cc39baa53cfc3baad29d3d` | Earlier evidence-first architecture |
| `MoheetBrain/hml-reasoning-corpus` | `claude/max-ev-representation-experiment-v1` | `bf2cd75a0676afdb73ab15fe5963cb6138e27060` | Best prior matched representation experiment |
| `MoheetBrain/hml-reasoning-corpus` | `codex/reasoning-layer-discovery` | `8d7cc1d99dc6748fd4d6dac174d251671d403678` | Representation-neutral reasoning layer |
| `MoheetBrain/hml-reasoning-corpus` | `codex/synthetic-math-hml` | `91fdda35851caa0445c1becdb1d7a756d5bcee3d` | Historical synthetic corpus work |
| `MoheetBrain/hml-standard` | `main` | `e879f5f5fe55ad2dc4ab15eb1c10a15de91aa59c` | Normative reference, not executable authority |
| `MoheetBrain/hamiltonian-lang` | `codex/final-hml-signal` | `273a5145fb4128daf37493de396126aa8cc84d97` | Executable semantics and final signal forensics |
| `MoheetBrain/hamiltonian-lang` | `feature/hml-reasoning-kernel-v2` | `3b7fe893609c2ce39c8088c1cb0c3fe2e45d6af4` | Reasoning kernel implementation |

The complete machine-readable inventory is
`artifacts/reuse/cross_repo_assets.json`. It assigns every material asset a decision and
records adapter and risk requirements.

## What is reused now

- The common-envelope rule is a binding experimental constraint: every non-state prompt byte,
  response schema, option order, task, and scoring rule must be matched across candidates.
- Group-aware splitting, task-level paired outcomes, clustered bootstrap intervals, exact
  McNemar discordances, cache keys, and pre-registration structure are adapted from the
  max-EV experiment and syntax gate.
- Structured English, S-expression, JSON AST, and current HML remain permanent controls.
- Literal Unicode escape detection, answer/operation leakage, split overlap, deterministic
  ordering, and known-bad/instrument tests become Arena regression gates.
- HML Standard is used as a terminology and conformance reference only. Arena's already-frozen
  canonical truth is not replaced.

## What is not imported as evidence

Prior model scores are historical guidance only. They do not enter Arena fitness estimates.
The strongest previous matched finding was negative for HML: under a common envelope,
canonical JSON beat HML by 2.77 percentage points. A separate max-EV study placed HML third of
four and found the paired difference from its best control unresolved. Earlier large positive
claims are rejected because the neutral prompt envelope was handicapped; one 50K run was also
invalidated by literal `\\uXXXX` sequences appearing only in the HML model payload.

The prior corpora and the Arena v0 world do not share a canonical schema or task oracle. The
5,619-row max-EV dataset is therefore `ADAPT`/`IMPORT_AS_TEST`, not `REUSE_DIRECTLY`, and its
scores cannot be merged with the Arena scout. Its renderer-neutral IR, mutation methodology,
split discipline, and audits are reusable mechanisms.

## Important negative knowledge

- Flat S-expressions can be blind to record-order corruption.
- Goal-centred ordering previously worsened dependency locality; topological ordering was a
  free static improvement only on states with real dependency edges.
- Compression is a Pareto dimension, not an objective and not evidence of reasoning quality.
- Line-count locality was a metric artifact; distance must use characters/tokens.
- Minimal-pair probes saturated at roughly 0.96–0.99 and were non-discriminative.
- MicroMath V2 obtained control parity on all seven valid measured components and no advantage;
  only one of eight intended known-bad renderers actually hid its target relation.
- Automated guards did not replace raw-completion inspection: prior option seeds, distant
  calibration headers, and re-sorted audit options each produced misleading results.

## Conflicts and authority decisions

`artifacts/reuse/conflicts.json` records each disagreement. The general decision rule is:

1. Arena's frozen executable canonical world remains the truth source for this experiment.
2. `hamiltonian-lang` is executable HML authority; `hml-standard` documents it.
3. Empirical repositories supply tasks, controls, audits, and negative knowledge, not truth by
   assertion.
4. Any data import requires a proved adapter and fresh Arena verification before it can be
   called Gold.

## Reuse boundary

No source repository was edited. No old score, hidden split, trained adapter, or candidate
ranking is reused as an Arena observation. Every Arena model call will use freshly frozen Arena
tasks and cache keys containing the model, prompt, candidate, task, and runtime hashes.
