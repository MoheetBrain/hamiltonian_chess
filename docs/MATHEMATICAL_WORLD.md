# Canonical Mathematical World v0

The Arena compares languages against one immutable, representation-independent world. A
candidate parser may reconstruct this world, but it may not define truth, legality, evidence,
or quality.

## State and transition contract

`CanonicalState` contains typed objects, bindings and scope, assumptions, established facts,
propositions, a goal, open or discharged obligations, evidence dependencies, legal actions,
plausible-invalid actions, and terminal status. `CanonicalTransition` binds a before-state,
one action, an after-state, and explicit verifier records. `CanonicalTrajectory` binds the
problem and final answer to a quality label and provenance.

Mathematical hashes exclude display state IDs and execution metadata. Artifact hashes include
them. Every record uses sorted, compact UTF-8 JSON for identity. Candidate surfaces therefore
cannot gain credit by changing timestamps, labels, or runtime configuration.

## Arena World v0

The frozen generator defaults to 676 one-transition tasks: 52 in each of 13 domains.

| Domain families | Mechanisms |
|---|---|
| arithmetic, algebra, logic | evaluation, variable isolation, implication |
| binding, sets | alpha-renaming, membership |
| probability, statistics | conditional roles, sample mean |
| calculus, linear algebra | differentiation, shape inference |
| physical dimensions, optimization | unit algebra, convex minimization |
| partial operations | division, roots, log, inverse, indexing, conditioning |
| reasoning evidence | dependency-preserving derivation replay |

Every initial state has at least one legal action and one plausible invalid action. The default
quality split is 520 Gold, 104 Silver, and 52 Reject.

## Quality policy

- Gold requires an accepted native structural check plus an accepted, explicitly trusted
  independent domain-template replay with a certificate hash.
- Silver has a native accepted check but the independent check is absent or unknown.
- Reject contains an explicit refutation or failed verification.

Absence of a check never counts as success. This synthetic v0 world establishes infrastructure
and targeted mechanisms; it is not evidence that the templates cover all mathematics.

## Evolution boundary

Changing the canonical schema is a governed Type-C proposal, not an ordinary language
mutation. It requires a schema version, migration, new generators, verifier updates, and a
fresh assurance cache. No candidate language can silently extend the canonical ontology.
