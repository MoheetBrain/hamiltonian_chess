# HAMILTONIAN CHESS
## Atomic, Machine-Actionable Specification Manual v0.2

**Document class:** Master specification manual  
**Status:** Draft for owner review; supersedes v0.1 prospectively once explicitly accepted by the owner  
**Project:** Hamiltonian Chess / Hamiltonian Arena  
**Purpose:** Reduce specification entropy until implementation is predominantly execution rather than interpretation  
**Primary audience:** Claude Code, Codex, other autonomous engineering/research agents, and the project owner  
**Authority:** This manual does not erase historical HML or Arena documents. It defines how the next project specification is to be decomposed, formalized, implemented, and scientifically evaluated.

---


## v0.2 correction ledger

This revision preserves the v0.1 mission while fixing failure modes that could cause an autonomous implementation agent to optimize the specification process instead of the research programme.

**Critical corrections**

1. Specification work is subordinate to executable scientific progress.
2. Frozen experiments cannot be edited after scientific exposure; they may only be aborted and restarted under a new manifest.
3. `VerifiedTask` is separated from `VerifiedTrajectory`: a stored proof path is not automatically an interactive MDP or a complete legal-action oracle.
4. Recorded trace length is not intrinsic reasoning difficulty. `ObservedTraceLength`, `EpisodeLength`, `DependencyDepth`, and `MinimalProofLength` are distinct.
5. Every candidate change has an `InterventionClass`. Representation-only, projection, ontology, action-space, tokenizer, controller, and joint changes have different fairness contracts and permit different causal claims.
6. Truth fidelity is universal. Visible-information parity is mandatory only where the intervention claims to hold information fixed.
7. Action macros are cost-accounted after lowering, so bundling many kernel operations into one model action cannot create a fake efficiency win.
8. Solver training reward is separated from scientific fitness. Shaped reward cannot substitute for verified terminal capability.
9. HC-V0 is deliberately thin. The full spec tree is a target architecture, not a prerequisite bureaucracy.
10. Pilot population sizes and evaluation budgets are experiment decisions derived from measured cost/variance, not constitutional defaults.
11. Project-hidden data and pretrained-model exposure are separate concepts.
12. `RSTAR` is reserved for representation-only search; `LSTAR` is the broader language/workspace claim.
13. `K` is a family of versioned backend truth contracts, not a forced universal ontology.
14. Final claims must use confirmation evidence that did not guide candidate search, threshold selection, or surrogate training.

# 0. HOW TO READ THIS MANUAL

This document defines **the game that designs mathematical languages**. It does not define the winning language.

The project is not tasked with hand-designing `HML_V4`, inventing hundreds of keywords, or choosing the prettiest grammar. It is tasked with constructing a truth-grounded search environment in which candidate mathematical languages/workspaces can be generated, compiled, verified, learned, tested, compared, archived, mutated, and improved.

Canonical naming:

- **Hamiltonian Chess** = the complete outer language-discovery meta-game.
- **Hamiltonian Arena** = reusable evaluation/assurance infrastructure inside that meta-game.
- **Game R** = a controlled representation-only causal assay inside Arena.
- **HC-V0** = an engineering vertical slice proving that one complete outer generation can execute.
- **Pilot 1** = the first scientific attempt to estimate a language-fitness landscape.

The governing engineering principle is:

> **Reduce specification entropy only until implementation is unambiguous enough to test. Then execute.**

The governing scientific principle is:

> **Do not reduce scientific uncertainty by pretending that an unknown is a specification decision.**

The governing research thesis is:

> **The lexical, grammatical, structural, semantic-workspace, and action primitives inherited from natural language and existing human-designed formalisms are not known to be the optimal computational basis for machine mathematical cognition. Hamiltonian Chess asks whether automated search can discover a better basis.**

## 0.1 Anti-bureaucracy rule

Specification refinement is a means, not a deliverable.

An agent MUST NOT:

- atomize historical prose exhaustively when only a small active contract is needed;
- create a large document hierarchy before an executable dependency requires it;
- block HC-V0 on scientific unknowns HC-V0 is not meant to resolve;
- continue decomposing a requirement that already has clear behavior, failure semantics, and objective tests.

If a requirement has one clear owner intent, explicit inputs/outputs, explicit failure behavior, and an objective acceptance test, further decomposition is OPTIONAL unless a contradiction is found.

## 0.2 V0 boundary

HC-V0 is engineering-only. It proves this state transition executes:

```text
population
 -> parent selection
 -> mutation
 -> compilation
 -> truth/assurance gate
 -> evaluation on a verifier-backed task
 -> fitness record
 -> archive update
 -> next-generation state
```

No HC-V0 winner is a scientific language winner.

# 1. NORMATIVE LANGUAGE

The words below have exact meanings throughout all Hamiltonian Chess specifications.

- **MUST / SHALL** — mandatory. An implementation that violates it is non-conforming.
- **MUST NOT / SHALL NOT** — forbidden.
- **SHOULD** — default requirement; deviation requires a recorded ADR explaining why.
- **SHOULD NOT** — default prohibition; deviation requires an ADR.
- **MAY** — explicitly delegated freedom.
- **UNKNOWN** — a scientifically or technically unresolved question. It is not permission to guess.
- **OWNER_DECISION_REQUIRED** — cannot be resolved by an implementation agent without explicit owner authorization.
- **EXPERIMENT_DECISION** — may be resolved by a frozen preregistered experiment.
- **ENGINEERING_DECISION** — may be resolved by engineering judgment within declared constraints.

No document may use words such as `best`, `robust`, `fair`, `sufficient`, `general`, `clean`, `strong`, `efficient`, `meaningful`, `valid`, or `matched` without either:

1. referring to a controlled glossary definition; or
2. defining an experiment-specific operational meaning.

---

# 2. SPECIFICATION ENTROPY DOCTRINE

## 2.1 Definition

`Specification entropy` means the breadth of materially different implementations that could satisfy the written specification while differing in ways that matter to owner intent or scientific validity.

It is an engineering metaphor, not a measured Shannon entropy.

## 2.2 Three states that MUST NOT be conflated

### A. OWNER AMBIGUITY

The owner has an intended meaning, but the specification permits materially different interpretations.

This is a defect.

### B. SCIENTIFIC UNKNOWN

No one currently knows the correct answer.

This is not a defect. It MUST remain typed as `UNKNOWN` or `HYPOTHESIS` until evidence resolves it.

### C. DELEGATED FREEDOM

Several implementations are acceptable provided explicit constraints hold.

This is not ambiguity.

## 2.3 Hard readiness blockers

An implementation packet is blocked by any of:

- owner ambiguity affecting observable behavior;
- undefined critical term used in a mandatory requirement;
- hidden default affecting scientific inference;
- scientific uncertainty that would otherwise be silently guessed;
- missing failure semantics for a critical operation;
- missing objective acceptance condition for a mandatory behavior;
- contradiction with a higher-authority active contract.

`READY_FOR_IMPLEMENTATION` requires zero applicable hard blockers.

## 2.4 Optional entropy score

A weighted score MAY be used for triage, but MUST NOT replace the hard-blocker rule. One critical ambiguity cannot be compensated by a low total score.

## 2.5 Stopping rule

Decomposition SHALL stop when the next decomposition step would not change code behavior, scientific validity, testability, authority, failure handling, or owner intent.

“More atomic” is not automatically “better.”

# 3. DOCUMENT AUTHORITY, FREEZING, AND PRECEDENCE

Mission authority, experiment authority, and evidence authority are distinct.

## 3.1 Prospective project authority

For work not yet scientifically exposed:

1. explicit owner directive whose scope is clear;
2. current accepted `00_CONSTITUTION.md`;
3. current subsystem specification;
4. accepted ADR / decision record;
5. implementation packet;
6. current code/tests;
7. historical HML/Arena documents;
8. comments/handoffs/temporary recommendations.

A casual owner message does not silently amend the constitution. Constitutional changes SHOULD explicitly say they modify mission, invariants, or controlled definitions.

## 3.2 Frozen experiment authority

Once an experiment crosses its declared scientific exposure boundary:

- its frozen manifest governs that experiment;
- the owner MAY abort it;
- a replacement requires a new experiment/manifest version;
- thresholds, endpoints, samples, promotion rules, or invalidation rules MUST NOT be edited while continuing to call it the same confirmatory experiment.

A later directive may supersede the experiment prospectively, never retroactively.

## 3.3 Evidence immutability

Raw artifacts and historical results are immutable evidence.

Corrections are additive:

```text
original claim
 -> correction/superseding record
 -> current interpretation
```

No agent may rewrite history to match the new architecture.

# 4. PERMANENT CONSTITUTION

The future `00_CONSTITUTION.md` SHOULD contain only the material in this section, or a tighter equivalent.

## 4.1 Mission

Hamiltonian Chess SHALL build an experimental system that searches the design space of machine-facing mathematical languages and reasoning workspaces to discover whether any candidate enables otherwise matched AI systems to learn and perform verified mathematics more effectively than strong human-designed baselines.

## 4.2 Core thesis

Natural-language and existing formal-language primitives are historically optimized for human communication, human proof practice, software engineering, or formal verification. They are not known to be optimal for neural mathematical cognition.

Hamiltonian Chess SHALL test, rather than assume, whether machine-specific alternatives improve:

- verified problem completion;
- long-horizon reasoning survival;
- learning/sample efficiency;
- systematic and structural generalization;
- search efficiency;
- error recovery;
- robustness;
- token/compute efficiency.

## 4.3 The project does not presuppose a winner

The following are valid outcomes:

- controlled English remains best;
- Lean-like syntax remains best;
- JSON/S-expression remains best;
- representation matters but only for particular model families;
- morphology matters but ontology does not;
- projection matters more than syntax;
- action granularity matters more than lexicon;
- no practically useful language effect is found under bounded search;
- local search fails because the landscape is too rugged;
- a novel machine-designed language wins after adaptation;
- the best language changes with reasoning horizon or model architecture.

## 4.4 Mathematical truth is not a contestant

A candidate SHALL NOT receive credit for changing mathematical truth conditions.

A candidate may change how mathematics is exposed, structured, named, composed, serialized, or manipulated through verified macros. It may not redefine `∀` as `∃`, accept false proofs, hide unsatisfied preconditions, or exploit verifier bugs.

## 4.5 Evidence before claims

No `RSTAR`, `LSTAR`, “machine-native language,” or superiority claim may be made without the evidence tier specified in this manual.

## 4.6 Human aesthetics are non-objective

Human readability, prettiness, familiarity, resemblance to ordinary mathematics, or intuitive elegance SHALL NOT be fitness objectives unless explicitly included in a separate deployment constraint.

A language that is ugly to humans but measurably superior for AI is a valid result.

---

# 5. PRIOR-ART BOUNDARY: WHAT THIS PROJECT IS NOT

Hamiltonian Chess MUST NOT be implemented as another instance of an already-solved neighbouring problem.

## 5.1 HML

Historical HML is an **ancestral organism and semantic-engineering asset**, not the predetermined answer.

HML's historical architecture already separated surface text from a typed semantic core and generated multiple views/backends from that core. Preserve that insight. Do not preserve HML's surface lexicon as sacred.

## 5.2 Lean / Isabelle / Rocq

These are formal proof systems and proof languages with trusted or relatively trusted verification mechanisms.

Hamiltonian Chess SHALL use systems such as Lean as:

- truth/verifier backends;
- sources of verified proof trajectories;
- strong baseline model-facing representations;
- targets for lowering/compilation.

Hamiltonian Chess SHALL NOT attempt to rewrite Lean merely to claim a new proof language.

## 5.3 LLM-oriented proof DSLs / AST interfaces

The project MUST assume there is prior art in redesigning proof languages for LLMs and exposing proof ASTs to agents. Therefore the novelty claim SHALL NOT be:

- “we designed a formal language for LLMs”;
- “we use JSON ASTs”;
- “we let an LLM manipulate proof trees”;
- “we constrain generation with a grammar.”

## 5.4 OpenMath / MMT / OMDoc-like systems

The project MUST assume prior art exists for semantic mathematical interchange and foundation-independent mathematical knowledge representation.

Therefore the novelty claim SHALL NOT be “we invented a universal semantic IR for mathematics.”

## 5.5 Wolfram / SymPy / Julia / JAX / Stan

These systems solve adjacent but different problems: symbolic computation, numerical/scientific programming, differentiable array computation, or probabilistic modelling.

They SHOULD be treated as execution backends, baseline languages, or domain libraries where relevant—not targets to be rebuilt.

## 5.6 Emergent communication

The project MUST assume prior art exists in agents learning communication protocols.

Therefore “agents invent symbols by reinforcement learning” is insufficient as a novelty claim.

## 5.7 Defensible research object

The research object to investigate is the conjunction:

> **Open-ended automated search over the design of machine-facing mathematical cognition languages/workspaces—including reasoning ontology, information projection, state topology, binding/type structure, grammar, morphology, action granularity and serialization—evaluated by verified long-horizon mathematical capability under matched adaptation and strong baselines.**

This remains a novelty candidate, not an unqualified novelty claim, until a dedicated prior-art audit supports it.

---

# 6. CONTROLLED GLOSSARY

The following terms are canonical.

## 6.1 `K` — Truth Kernel

A backend-grounded mathematical semantics and verification layer that determines whether mathematical claims and primitive transitions are valid under a declared formal universe.

`K` is not the model-facing language.

`K` MUST be versioned.

## 6.2 `KernelState`

The backend-native or canonical semantic state on which mathematical validity is defined.

A Lean proof state MAY be represented by a Lean-native semantic envelope rather than forced into a lossy universal AST.

## 6.3 `WorkspaceState`

The state exposed to, maintained for, or manipulated by the Solver under candidate language `L`.

It may contain derived structures permitted by a projection policy, but MUST remain truth-grounded.

## 6.4 `L` — Candidate Language/Workspace

The complete machine-facing cognitive interface under evaluation.

For this project:

\[
L=(O,P,S,T,G,M,A,I)
\]

where each component is defined below.

## 6.5 `O` — Reasoning Ontology

Which model-facing state entities are first-class.

Examples: goal, obligation, dependency, failed branch, warrant, evidence, counterexample, conjecture.

`O` is not the truth kernel.

## 6.6 `P` — Projection / Visibility Policy

Which truth-grounded facts or deterministic derived relations from `K` and permitted history are made explicit to the Solver.

`P` MUST NOT expose future proof steps, answer labels, minimum proof paths, candidate correctness labels, or other oracle information.

## 6.7 `S` — State Topology

How workspace entities and relations are organized: sequence, tree, DAG, graph, hypergraph, local contexts, goal-centric clusters, etc.

## 6.8 `T` — Type / Identity / Binding System

How types, binder identity, scope, freshness, references, partiality, and related static semantic information are represented to the Solver.

## 6.9 `G` — Grammar

The formal composition rules defining well-formed candidate expressions and workspace records.

## 6.10 `M` — Morphology / Lexicon

How semantic units are mapped into tokens/morphemes/symbol sequences.

Examples: English keywords, controlled English, conventional math symbols, abbreviations, compositional symbolic morphemes, invented morphemes, hybrids.

## 6.11 `A` — Action Protocol and Granularity

How the Solver expresses reasoning/search moves.

`A` may define high-level verified macros, but those macros MUST lower to truth-kernel-supported primitive effects or backend-verifiable programs.

## 6.12 `I` — Interface / Serialization

Ordering, field structure, delimiters, redundancy, local adjacency, compression, graph traversal, ID formatting, and other presentation details.

## 6.13 `τ` — Tokenizer/Input Encoder

The tokenizer or low-level model encoder. It SHALL remain fixed during early language comparisons unless a dedicated tokenizer co-design experiment is active.

## 6.14 `π` — Solver

The AI model/policy that attempts mathematical reasoning.

## 6.15 `C` — Search Controller

The algorithm controlling reasoning/search: greedy policy, beam search, MCTS, best-first, retry loop, branch manager, retrieval policy, etc.

`C` is not part of `L` in early causal experiments, although later joint co-design is permitted.

## 6.16 `D` — Task/Environment Distribution

The declared mathematical problem distribution used for training/evaluation.

## 6.17 `U` — Tools/Libraries

Permitted external resources such as theorem libraries, retrieval, symbolic systems, calculators, SMT solvers, etc.

## 6.18 `V` — Verifier

The trusted checker/oracle used to adjudicate mathematical validity within its supported domain.

## 6.19 `B` — Resource Budget

Training tokens, inference tokens, GPU-hours, wall-clock constraints, tool-call limits, branch limits, etc.

## 6.20 `VerifiedTrajectory`

A contiguous sequence of mathematically grounded states and actions whose transitions and terminal status are supported by a verifier/backend.

## 6.21 `Reasoning Horizon`

The number of sequential dependent reasoning transitions required or observed in an episode. It is not the number of concatenated unrelated microtasks.

## 6.22 `Fitness`

A vector of measured outcomes under a fully declared evaluation context. It is not a single arbitrary score.

## 6.23 `Searchability`

The degree to which observations from previously evaluated candidates predict useful future candidate modifications better than a null/random search process.

---

## 6.24 `BackendKernelContract`

A versioned verifier/transition contract for one backend or mathematical domain.

Hamiltonian Chess does not require one universal lossless `KernelState` for every branch of mathematics.

## 6.25 `VerifiedTask`

An executable verifier-backed task with:

- initial truth-grounded state;
- terminal criteria;
- action decoding/lowering;
- transition/verifier interface;
- declared tools/libraries;
- explicit failure semantics.

A `VerifiedTask` supports interaction. A stored `VerifiedTrajectory` does not necessarily do so.

## 6.26 `InterventionClass`

Every candidate comparison SHALL be typed as one of:

- `R_ONLY`
- `P_CHANGE`
- `O_CHANGE`
- `T_CHANGE`
- `A_CHANGE`
- `TAU_CHANGE`
- `C_CHANGE`
- `JOINT`

The class determines the fairness contract and the causal claims permitted.

## 6.27 `EvaluationUniverse`

The declared context under which fitness is estimated:

```text
task distribution
backend/kernel versions
Solver initialization/checkpoint
tokenizer
controller
tools
adaptation data
adaptation budget
inference budget
verifier
seeds
evaluation split
code/manifest versions
```

Fitness outside this universe is UNKNOWN until replicated.

## 6.28 `ProjectHidden`

Data not inspected or used by Hamiltonian search/development before its confirmation role was frozen.

This does not imply that the pretrained model never saw equivalent data.

## 6.29 `ModelExposureStatus`

One of:

- `KNOWN_PRE_CUTOFF_PUBLIC`
- `KNOWN_POST_CUTOFF`
- `LIKELY_PRETRAINING_EXPOSURE`
- `UNKNOWN`
- `NEWLY_GENERATED_AFTER_MODEL_FREEZE`

## 6.30 `ObservedTraceLength`

Number of transitions in one stored demonstration.

Not automatically the minimum reasoning horizon required by the task.

## 6.31 `EpisodeLength`

Number of model-facing decisions in an actual interactive Solver run.

## 6.32 `KernelStepCount`

Number/cost of trusted backend operations after action lowering.

## 6.33 `DependencyDepth`

A task-family-specific structural dependency measure.

## 6.34 `MinimalProofLength`

Shortest proof/solution length under a declared action system, only when independently established. Otherwise `UNKNOWN`.

## 6.35 `LSTAR`

A claim about the broader language/workspace search.

## 6.36 `RSTAR`

Reserved for a representation-only `R_ONLY` search under fixed projection, ontology, action semantics, tokenizer, controller, and other declared variables.

# 7. THREE SEMANTIC LAYERS — PERMANENT FIREWALL

The word `semantics` SHALL NOT be used without specifying which layer is meant.

## 7.1 Mathematical semantics / truth conditions (`K`)

What the mathematical object actually means and what constitutes a valid result.

This is frozen within an experiment.

## 7.2 Candidate-language semantics (`σ_L`)

What each candidate construct denotes or does.

For each primitive or macro `c`, the candidate specification SHOULD define:

\[
\llbracket c \rrbracket_L
\]

or an equivalent formal mapping/lowering.

This can evolve if it preserves truth-kernel validity.

## 7.3 Reasoning ontology (`O`)

What intermediate cognitive/workspace concepts are first-class for the Solver.

This can evolve.

Example:

- candidate A has no explicit `OBLIGATION` object;
- candidate B makes obligations first-class;
- both remain grounded in the same mathematical truth.

---

# 8. PROGRAMMING-LANGUAGE CONSTITUTION FOR EVERY CANDIDATE

Every executable candidate language SHALL provide explicit answers to the language-design questions traditionally separated in programming-language semantics.

## 8.1 Abstract syntax

What semantic/workspace constructs exist independent of concrete spelling?

## 8.2 Concrete syntax

How are those constructs serialized for the model?

## 8.3 Static semantics

What is well-formed, well-typed, correctly scoped, and identity-consistent?

## 8.4 Denotational semantics

What does each construct mean in the truth/workspace model?

## 8.5 Operational semantics

What state transition occurs when an action is executed?

Preferred judgment shape:

\[
\frac{premises}{S \xrightarrow{a} S'}
\]

## 8.6 Proof/verification semantics

What establishes that an inference/action/result is acceptable, proven, refuted, unsupported, unresolved, approximate, or otherwise epistemically classified?

## 8.7 Failure semantics

What happens when parsing, typing, lowering, tool execution, or verification fails?

`UNKNOWN`, `TIMEOUT`, `UNSUPPORTED`, and `FALSE` MUST remain distinct.

---

# 9. WHY RANDOM SYMBOL SUBSTITUTION IS NOT A LANGUAGE DISCOVERY

The following transformation is explicitly considered scientifically weak:

```text
APPLY  -> ZXQ
GOAL   -> VUU
CREATE -> BLF
```

when no other compositional or structural property changes.

This is an encryption/permutation control, not evidence of improved semantics or morphology.

Hamiltonian Chess SHALL include such permutations only as controls for pretrained lexical familiarity.

A candidate morphology is more interesting when it has internal composition, for example:

```text
role + operation + direction + target + status
```

so that related meanings share reusable substructure.

The exact morphemes are NOT predetermined.

---

# 10. LANGUAGE META-GENOME V0

The meta-genome defines the generative search space. It does not enumerate the entire mathematical-language universe, which is unbounded.

## 10.1 Canonical object

```text
LanguageMetaGenomeV0 {
    genome_version,
    ontology,
    projection,
    topology,
    typing_binding,
    grammar,
    morphology,
    action_protocol,
    interface,
    deferred_features,
}
```

## 10.2 Ontology genes `O`

Each SHALL be optional/searchable unless kernel requirements force otherwise.

Candidate values include:

- explicit facts;
- assumptions;
- definitions;
- active goals;
- subgoals;
- obligations;
- dependencies;
- warrants;
- evidence/provenance;
- branches;
- failed branches;
- counterexamples;
- conjectures;
- epistemic labels;
- unresolved metavariables;
- repair history.

V0 SHALL NOT declare every concept mandatory.

## 10.3 Projection genes `P`

Potential visibility features include:

- direct dependency links;
- binder → use links;
- action → target links;
- premise → action links;
- definedness/precondition status;
- local neighborhood summaries;
- branch status;
- state deltas;
- evidence edges.

Every projection feature MUST declare a deterministic derivation procedure and admissibility audit.

## 10.4 Topology genes `S`

Initial families:

- `SEQUENCE`
- `TREE`
- `DAG`
- `GRAPH`
- `HYPERGRAPH`
- `GOAL_CENTRIC`
- `DEPENDENCY_LOCAL`
- `BRANCH_LOCAL`
- `HYBRID`

## 10.5 Type/binding genes `T`

Initial dimensions:

- type explicitness: `NONE | SELECTIVE | FULL`
- identity: `SURFACE_NAME | SCOPED_ID | INDEXED`
- scope: `IMPLICIT | DELIMITED | EXPLICIT_SCOPE_ID`
- freshness: `IMPLICIT | DECLARED`
- partiality: `IMPLICIT | PRECONDITION_TAGGED | EXPLICIT_OPTIONALITY`

## 10.6 Grammar genes `G`

Initial families:

- `NATURAL_ENGLISH`
- `CONTROLLED_ENGLISH`
- `FORMAL_ENGLISH`
- `PREFIX`
- `INFIX`
- `POSTFIX`
- `S_EXPR`
- `TYPED_BLOCK`
- `JSON_AST`
- `GRAPH_TRIPLE`
- `HYBRID`

Each executable grammar MUST emit a machine-readable grammar/validator.

## 10.7 Morphology genes `M`

### Lexicon family

- `NATURAL_ENGLISH`
- `CONTROLLED_ENGLISH`
- `FORMAL_ENGLISH`
- `CONVENTIONAL_MATH_SYMBOLS`
- `ABBREVIATED_ENGLISH`
- `ARBITRARY_ATOMIC_SYMBOLS` — control family
- `COMPOSITIONAL_SYMBOLIC`
- `INVENTED_MORPHEMES`
- `HYBRID`

### Semantic granularity

- `COARSE`
- `MEDIUM`
- `ATOMIC`
- `HIERARCHICAL`

### Morphological composition

- `FLAT_WORD`
- `ROLE_PREFIX`
- `ROLE_SUFFIX`
- `COMPOSITIONAL`
- `ALGEBRAIC`

The system MUST test the possibility that English has a large zero-shot advantage due to pretraining while invented/compositional morphology has a later matched-adaptation advantage.

## 10.8 Action protocol genes `A`

Possible payload levels:

- `ACTION_ONLY`
- `ACTION_ARGS`
- `ACTION_ARGS_TARGET`
- `ACTION_WARRANT`
- `ACTION_PRECONDITIONS`
- `ACTION_STATE_DELTA`
- `FULL_STRUCTURED_ACTION`

Possible granularity:

- `MACRO`
- `MESO`
- `PRIMITIVE`
- `HIERARCHICAL`

Example experimental axis:

```text
MACRO:
APPLY_THEOREM

MESO:
MATCH + INSTANTIATE + APPLY

PRIMITIVE:
SELECT + UNIFY + CREATE_OBLIGATION + UPDATE_GOAL + COMMIT
```

## 10.9 Interface genes `I`

Initial dimensions:

- goal position;
- context order;
- dependency locality;
- field ordering;
- explicit labels;
- delimiter family;
- redundancy level;
- compression level;
- stable semantic IDs;
- graph traversal order;
- repeated local context;
- error-detection/checksum structure.

## 10.10 Deferred genes

The following SHALL be disabled in the first causal search unless explicitly activated by a later ADR:

- candidate-specific tokenizer training;
- model architecture modification;
- candidate-specific external search controller;
- candidate-specific theorem library;
- candidate-specific verifier.

---

# 11. META-GENOME CONSTRAINTS

The meta-genome MUST support cross-field constraints.

Examples:

- `INDEXED` binders require a renderer capable of deterministic index assignment.
- `GRAPH` topology requires deterministic node identity.
- `COMPOSITIONAL_SYMBOLIC` morphology requires a declared morpheme grammar.
- `ACTION_STATE_DELTA` requires deterministic state-delta validation.
- any explicit dependency projection requires a derivation algorithm.

Invalid combinations SHALL fail before model evaluation as `DEAD_GENOME_CONSTRAINT`.

The meta-genome MUST be versioned.

Changes to the schema itself require an ADR and migration policy.

---

# 12. LANGUAGE COMPILER CONTRACT

Every `LanguageCandidate` SHALL compile from genome to an executable phenotype.

## 12.1 Required outputs

```text
LanguageCandidate {
    candidate_id,
    genome_version,
    genome,
    genome_hash,
    intervention_class,
    parent_ids,
    mutation_ids,
    compiler_version,
    truth_kernel_contracts,
    projection_version,
    renderer_or_encoder,
    parser_or_decoder,
    static_checker,
    semantic_mapping,
    action_lowering,
    grammar_artifact_if_applicable,
    creation_seed,
    status,
}
```

## 12.2 Universal postconditions

A successful candidate MUST:

- deterministically encode every admitted workspace state in its supported domain;
- preserve truth-relevant identity, binding, scope, and types required by its declared interface;
- emit stable hashes;
- lower actions into trusted backend operations or verifiable programs;
- fail closed on unsupported constructs;
- expose all declared intervention deltas.

## 12.3 Intervention-specific requirements

### `R_ONLY`

MUST prove:

- same visible semantic inventory;
- same candidate alternatives/action semantics;
- same truth state;
- only approved representational/morphological/interface structure differs.

### `P_CHANGE` / `O_CHANGE` / `T_CHANGE` / `A_CHANGE`

MUST provide:

- a machine-readable parent delta;
- admissibility audit;
- no hidden answer/future-state information;
- a claim label matching the intervention class.

Strict visible-information parity is not required because the intervention intentionally changes it.

### `JOINT`

MUST enumerate every changed component. It may participate in broad search, but component-level causal claims require later ablation.

## 12.4 Failure outcomes

- `DEAD_GENOME_CONSTRAINT`
- `DEAD_COMPILE`
- `DEAD_STATIC_SEMANTICS`
- `DEAD_TRUTH_FIDELITY`
- `DEAD_INFORMATION_PARITY` where parity is required
- `DEAD_ACTION_LOWERING`
- `DEAD_LEAKAGE`
- `DEAD_UNDECLARED_INTERVENTION`

No dead candidate receives Solver compute.

# 13. TRUTH KERNEL AND ACTION LOWERING

Action granularity may evolve without allowing a candidate to redefine truth.

Define:

- `A_K` — trusted primitive/backend actions;
- `A_L` — candidate model-facing actions/macros.

A candidate action MUST lower as:

\[
\operatorname{lower}_L(a_L) \rightarrow [a_{K1},\ldots,a_{Kn}]
\]

or an equivalent backend-verifiable program.

## 13.1 Macro accounting

A macro does not receive free compute.

Every episode SHALL record at least:

- `model_action_count`;
- `kernel_step_count`;
- tool calls;
- verifier calls;
- wall-clock;
- tokens/compute.

When comparing action-granularity candidates, report both model-facing efficiency and underlying kernel/tool cost.

## 13.2 Atomicity is not presumed optimal

The project SHALL NOT assume the finest primitive decomposition is best. A macro may be a legitimate cognitive abstraction if it remains truth-grounded and its cost is honestly accounted.

## 13.3 Backend plurality

`K` is a role fulfilled by versioned backend contracts such as Lean, SMT, CAS, or exact arithmetic. Do not force all domains into one lossy universal semantic object.

# 14. INNER GAME — MATHEMATICAL REASONING ENVIRONMENT

For a fixed candidate `L`, define:

\[
\mathcal{M}_L=(\mathcal{S}_K,\mathcal{A}_L,T_K,\Omega_L)
\]

A training algorithm MAY attach shaped reward, but the scientific environment definition remains separable from training reward design.

## 14.1 Solver observation

\[
o_t=\Omega_L(S_t,H_t)
\]

where `H_t` contains only permitted history.

## 14.2 Solver action

\[
a_t\sim\pi_\theta(a\mid o_t,C,U,B)
\]

## 14.3 Transition

```text
model-facing action
 -> decode/lower
 -> trusted backend operations
 -> verifier
 -> next truth-grounded state OR explicit failure
```

## 14.4 Terminal outcomes

- `VERIFIED_SOLVED`
- `VERIFIED_REFUTED` where valid
- `UNRECOVERABLE_INVALID_ACTION`
- `SEARCH_BUDGET_EXHAUSTED`
- `TOOL_TIMEOUT`
- `UNSUPPORTED`
- `ENVIRONMENT_ERROR`

`ENVIRONMENT_ERROR` SHALL NOT count as mathematical failure.

## 14.5 Training reward versus scientific fitness

Training MAY use shaping such as subgoal discharge or valid-step rewards.

Promotion SHALL NOT rely on a shaping signal if verified terminal capability does not improve.

Primary scientific evaluation SHOULD center verifier-grounded terminal success plus preregistered secondary metrics.

## 14.6 Replay versus interaction

### `TRAJECTORY_REPLAY`

The Solver predicts/consumes transitions from a recorded trajectory.

Useful for adaptation and diagnostics.

It does not demonstrate autonomous problem solving.

### `INTERACTIVE_TASK`

The Solver acts in a `VerifiedTask` and may take alternative paths.

Required for claims about search, repair, free-running proof completion, or autonomous long-horizon capability.

# 15. OUTER GAME — LANGUAGE EVOLUTION META-POMDP

The true fitness of a language is latent and observed only through finite experiments. Therefore the outer process is better treated as a POMDP/meta-optimization process than as a simple deterministic MDP.

Define outer state:

\[
X_t=(\mathcal{P}_t,\mathcal{A}_t,\mathcal{E}_t,\hat F_t,\mathcal{H}_t,D_t,B_t)
\]

where:

- `P_t` = active population;
- `A_t` = archive/Hall of Fame;
- `E_t` = accumulated experimental evidence;
- `F_hat_t` = current fitness estimates/surrogate predictions;
- `H_t` = lineage, mutation, exploit and failure history;
- `D_t` = available curriculum/evaluation state;
- `B_t` = remaining budget.

## 15.1 Architect action

```text
MutationProposal {
    proposal_id,
    parent_candidate_id,
    mutation_family,
    exact_changes,
    hypothesis,
    predicted_benefit,
    predicted_cost,
    requested_fidelity,
    required_tests,
    seed,
}
```

## 15.2 Outer transition

```text
proposal
 -> schema validation
 -> candidate compilation
 -> deterministic assurance
 -> Refuter
 -> multi-fidelity evaluation
 -> evidence update
 -> archive/population decision
 -> language-fitness memory append
```

## 15.3 Candidate fitness vs Architect reward

Candidate fitness SHALL remain a vector.

A future learned Architect MAY use a scalar search reward such as:

\[
r_t = \Delta HV_t + \lambda IG_t - \eta Cost_t
\]

where:

- `ΔHV` = Pareto hypervolume improvement;
- `IG` = information gain about the landscape;
- `Cost` = evaluation cost.

This is a search-controller reward, not the definition of mathematical quality.

V0 SHALL NOT train an RL Architect.

---

# 16. ROLES AND AUTHORITY BOUNDARIES

Logical roles are fixed. Physical model count is not.

## 16.1 Architect AI

MAY:

- inspect development evidence;
- inspect genomes/lineages;
- propose typed mutations;
- propose hypotheses;
- request approved evaluation fidelity.

MUST NOT:

- read sealed answers;
- modify the truth kernel;
- modify verifier outputs;
- modify evaluation thresholds after results;
- approve its own semantic gate.

## 16.2 Solver AI

Receives candidate workspace and permitted tools.

MUST NOT receive answer oracle, hidden labels, or candidate-specific privileged information.

## 16.3 Refuter AI

Attempts to discover:

- semantic collisions;
- scope/binder errors;
- side channels;
- malformed lowering;
- prompt leakage;
- candidate-specific exploits;
- verifier loopholes;
- pathological edge cases.

## 16.4 Builder

SHOULD be deterministic software wherever possible.

It translates typed candidate genomes/proposals into executable phenotypes.

## 16.5 Experimentalist

Owns instrument validity, controls, power, leakage audits, and preregistration checks.

## 16.6 League Manager

Owns population/archive/resource allocation under predeclared policy.

It cannot override semantic death.

## 16.7 Verifier

Non-strategic authority over mathematical validity within its declared trust domain.

## 16.8 Curriculum Designer

DISABLED for sealed evaluation.

Adaptive curriculum may be activated later for training/development only under a separate spec.

## 16.9 Number of agents

The V0 scientific architecture requires only three strategic AI roles:

1. Architect
2. Solver
3. Refuter

Other roles SHOULD be software or independent audit contexts.

Parallel Solver workers are throughput workers, not distinct game-theoretic roles.

---

# 17. VERIFIED TASK AND TRAJECTORY WORLD

The critical data abstraction is a collection of verifier-grounded tasks plus any verified trajectories available through them.

## 17.1 `VerifiedTask`

```text
VerifiedTask {
    task_id,
    problem_id,
    source_system,
    source_version,
    source_hash,
    backend_kernel_contract,
    domain,
    theorem_group,
    split,
    initial_state_ref,
    terminal_predicate,
    action_interface,
    tool/library_contract,
    verifier_adapter,
    provenance,
}
```

A `VerifiedTask` is interactive.

## 17.2 `VerifiedTrajectory`

```text
VerifiedTrajectory {
    trajectory_id,
    task_id,
    source_system,
    source_version,
    source_hash,
    transitions: [
        {
            step_index,
            state_ref,
            backend_native_state,
            normalized_semantic_envelope_if_available,
            recorded_action,
            action_semantics,
            verifier_evidence,
            next_state_ref,
            terminal_after,
        }
    ],
    terminal_status,
    observed_trace_length,
    dependency_depth_if_defined,
    minimal_proof_length: VALUE | UNKNOWN,
    provenance,
}
```

## 17.3 Critical epistemic rule

A recorded trajectory is one demonstrated path, not automatically:

- the only legal path;
- the optimal path;
- the shortest proof;
- a complete legal-action oracle;
- evidence every step was necessary.

A Solver action different from the recorded action is not mathematically wrong unless the verifier establishes that.

## 17.4 Backend-native truth is allowed

Do not force all mathematics through an old canonical schema if information is lost.

## 17.5 Failed branches

Do not invent failed branches retrospectively. Generate them online and record verifier outcomes.

## 17.6 Horizon terminology

Report separately:

- `ObservedTraceLength`
- `EpisodeLength`
- `DependencyDepth`
- `MinimalProofLength` when established.

Do not call a 50-step recorded proof a “50-step required reasoning task” without evidence of necessity/minimality.

# 18. DATA SOURCE ADMISSION

Every admitted source SHALL have a `SourceAdmissionRecord` containing:

```text
source_id
license_or_access_status
formal_backend
version/commit
hashes
extraction_method
verification_method
project_exposure_status
model_exposure_status
supported_task_mode: REPLAY | INTERACTIVE | BOTH
observed_trace_distribution
dependency_depth_distribution_if_available
domain_distribution
grouping_unit
admitted_for: TRAIN | DEV | SCOUT | PROMOTION | OOD | FINAL
known_limitations
```

## 18.1 Project exposure versus model exposure

Previously inspected data is not project-hidden later merely because it is hashed or renamed.

Project-hidden data may still be present in pretrained model data. Claims MUST distinguish:

- project search-holdout;
- temporal/post-training holdout;
- structural OOD;
- unknown model exposure.

## 18.2 Grouped splits

Where possible, split by theorem/module/repository/problem family, not random steps from the same proof family.

## 18.3 V0 engineering admission

HC-V0 needs only enough verifier-backed material to prove the loop executes.

No arbitrary minimum corpus size is required for the engineering smoke.

## 18.4 Scientific admission

Pilot 1 sample counts SHALL be chosen after task variance, episode cost, minimum practical effect, and power/precision are measured.

If only replay data is available, V0 may proceed as engineering, but autonomous long-horizon claims remain blocked.

# 19. BASELINE / FOUNDER POPULATION

English and existing formalisms are incumbents, not enemies.

## 19.1 Founder classes

The first broad scientific founder roster SHOULD contain approximately 12 distinct families:

1. Natural mathematical English
2. Controlled mathematical English
3. Formal role-labelled English
4. Historical HML
5. JSON AST
6. S-expression
7. Typed prefix
8. Compact symbolic
9. Graph triples / graph serialization
10. Lean-like tactic/state representation
11. Lean-like term/AST representation
12. Compositional invented-morpheme prototype

A MiniLang-like baseline MAY be added only if implementation/licensing and semantic parity are clear.

## 19.2 Founder rule

No founder is privileged.

Historical HML is one ancestor.

Controlled English remains in the Hall of Fame indefinitely.

Lean-like baselines remain in the Hall of Fame indefinitely where the domain permits.

## 19.3 V0 thin slice

The engineering-only vertical slice SHALL use only 3–4 existing founders. It is not a scientific tournament.

Recommended:

- Controlled English
- JSON AST
- Historical HML or Compact Symbolic
- Lean-like representation if supported by the chosen trajectory arena

---

# 20. MUTATION OPERATORS

## 20.1 Mutation families

- `ONTOLOGY_MUTATION`
- `PROJECTION_MUTATION`
- `TOPOLOGY_MUTATION`
- `BINDING_TYPE_MUTATION`
- `GRAMMAR_MUTATION`
- `MORPHOLOGY_MUTATION`
- `ACTION_GRANULARITY_MUTATION`
- `INTERFACE_MUTATION`
- `MULTI_GENE_MUTATION` — deferred until interaction phase
- `TOKENIZER_MUTATION` — deferred
- `META_GENOME_MUTATION` — long-term only

## 20.2 Early causal reconnaissance

Early generations SHOULD prefer one gene family per child so parent-child effects are interpretable.

## 20.3 Interaction phase

Do not permanently optimize ontology, then grammar, then morphology in irreversible sequence.

After single-family reconnaissance, explicitly test interactions such as:

- ontology × topology;
- topology × grammar;
- grammar × morphology;
- morphology × interface;
- action granularity × ontology.

## 20.4 Search operator escalation

Local mutation is conditional on measured landscape properties.

If local neighbors show useful correlation, use local search aggressively.

If the landscape is rugged/nonlocal, permit larger LLM-designed jumps, quality diversity, and later recombination.

---

# 21. CANDIDATE LIFECYCLE STATE MACHINE

Every candidate SHALL occupy exactly one lifecycle state.

```text
PROPOSED
  -> GENOME_VALID
  -> COMPILED
  -> SEMANTIC_GATE_PASS
  -> REFUTER_PASS
  -> SCOUT_ELIGIBLE
  -> SCOUTED
  -> ADAPTATION_ELIGIBLE
  -> ADAPTED
  -> PROMOTION_ELIGIBLE
  -> PROMOTED
  -> ROBUSTNESS_ELIGIBLE
  -> ROBUST_CANDIDATE
  -> HALL_OF_FAME
```

Terminal/non-progress states:

```text
DEAD_GENOME_CONSTRAINT
DEAD_COMPILE
DEAD_STATIC_SEMANTICS
DEAD_SEMANTIC_PARITY
DEAD_ACTION_LOWERING
DEAD_LEAKAGE
DEAD_REFUTER
ELIMINATED_SCOUT
ELIMINATED_ADAPTATION
ELIMINATED_PROMOTION
ELIMINATED_INSTABILITY
ARCHIVED_SPECIALIST
VOID_INSTRUMENT
```

State transitions SHALL be code-enforced.

---

# 22. FITNESS VECTOR

Truth validity is a hard gate, not a weighted fitness component.

Every fitness record is conditional on an `EvaluationUniverse` and carries uncertainty.

For valid candidates maintain a vector such as:

\[
F(L)=(Q_{terminal},Q_{horizon},L_{sample},Q_{OOD},S_{search},R_{repair},E_{invalid},C_{token},C_{kernel},C_{compute},R_{robust})
\]

- `Q_terminal`: verified terminal success rate.
- `Q_horizon`: performance as genuine horizon/dependency depth changes.
- `L_sample`: capability versus matched adaptation exposure.
- `Q_OOD`: declared holdout/generalization performance.
- `S_search`: branches/states/retries/model decisions/tool calls per solve.
- `R_repair`: recovery after rejected/bad paths.
- `E_invalid`: invalid-action/verifier rejection rate.
- `C_token`: tokens per episode/verified solve.
- `C_kernel`: backend/kernel operations after lowering.
- `C_compute`: wall-clock/GPU/tool cost.
- `R_robust`: stability across seeds/tasks and later model families.

## 22.1 Shaped reward is not fitness

Solver training MAY use intermediate shaping.

The evolutionary archive MUST NOT promote candidates solely because they exploit shaping while verified terminal capability is unchanged or worse.

## 22.2 No arbitrary universal scalar

Use Pareto/quality-diversity logic unless a scalar is explicitly frozen for a controller experiment.

Default tie-breaking:

```text
truth/soundness
> verified terminal capability
> long-horizon / held-out generalization
> learnability
> search/repair reliability
> efficiency
```

# 23. THE CENTRAL HAMILTONIAN PREDICTION

The most distinctive high-level hypothesis is not merely that representation changes one-step accuracy.

It is:

> **A genuinely useful mathematical cognition language/workspace should preserve or increase its advantage as reasoning dependency length and horizon increase.**

Operationally, evaluate candidate deltas across horizons:

\[
\Delta_L(h)=J(L,h)-J(L_{control},h)
\]

The project SHOULD explicitly test whether:

\[
\Delta_L(20) > \Delta_L(1)
\]

or analogous monotonic/interaction patterns, without assuming they must hold.

A language that helps only trivial one-step formatting but not multi-step verified reasoning is not the desired end product.

---

# 24. THREE LANGUAGE QUESTIONS

Hamiltonian Chess SHALL distinguish three research regimes.

## Q-A — Pretrained-model language

\[
L^*_{pretrained}
\]

Which language best exploits a fixed pretrained model with minimal/no adaptation?

Controlled English may dominate because of pretraining familiarity.

## Q-B — Matched-adaptation language

\[
L^*_{adapted}
\]

Which language yields the strongest learning curve after equalized mathematical exposure?

This is a more serious test of machine-native morphology/structure.

## Q-C — Model + language co-design

\[
(L^*,\theta^*)=\arg\max_{L,\theta}J(L,\theta)
\]

This is long-term.

It SHALL NOT begin until Q-A/Q-B infrastructure and rewards are trustworthy.

---

# 25. MULTI-FIDELITY EVALUATION LADDER

Full matched training for every candidate is computationally impossible. Use successive halving / quality-diversity resource allocation.

The gate structure is normative; exact counts and budgets are experiment-specific.

## Gate 0 — deterministic validity

No model calls.

Schema, compile, truth fidelity, intervention declaration, required parity, action lowering, leakage/assurance.

## Gate 1 — cheap scout

Catastrophic unreadability and gross failure detection.

MUST NOT crown a language.

## Gate 2 — short matched adaptation

Early acquisition/learnability.

## Gate 3 — medium adaptation / genuine multi-step tasks

Learning curve plus early horizon signal.

## Gate 4 — serious finalist

Large fresh evaluation, multiple seeds, interactive tasks where supported, search/repair metrics.

## Gate 5 — champion confirmation

Required:

- fresh project-hidden confirmation data;
- strong incumbent controls;
- example-matched adaptation;
- token/compute-matched confirmation where relevant;
- selection-bias/multiplicity protection;
- independent rerun.

## Gate 6 — robust validation

Required before `LSTAR_0_1`:

- at least two meaningfully distinct Solver families;
- structural/domain holdout;
- strong incumbent survival;
- no unresolved critical truth/leakage defects;
- explicit model-exposure caveats.

`RSTAR_0_1` additionally requires an `R_ONLY` search/confirmation.

Exact sample sizes, budgets, and promotion fractions SHALL be frozen after V0 calibration and before observing the results they govern.

# 26. FAIR COMPARISON AND CAUSAL-CLAIM CONTRACT

“Fair” depends on the intervention class.

## 26.1 Universal declaration

Every comparison MUST declare:

- tasks/distribution;
- truth-kernel/backend versions;
- Solver initialization/checkpoint;
- tokenizer;
- controller;
- tools/libraries;
- adaptation examples/order;
- adaptation/inference budgets;
- verifier;
- seeds;
- output/action protocol;
- intervention class.

## 26.2 `R_ONLY`

Hold fixed:

- truth state;
- visible mathematical information;
- action semantics/cardinality;
- tokenizer;
- Solver;
- controller;
- tools;
- training examples;
- evaluation tasks;
- verifier;
- compute regime.

Only approved representation/morphology/interface structure differs.

## 26.3 Other intervention classes

`P_CHANGE`, `O_CHANGE`, `T_CHANGE`, and `A_CHANGE` intentionally alter the cognitive interface.

They estimate system-level value of that intervention and MUST NOT be reported as pure representation effects.

## 26.4 `JOINT`

Broad search may change multiple components. A JOINT winner may be promoted as a system candidate, but causal attribution requires later ablations.

## 26.5 Adaptation fairness

After matched adaptation, weights may differ by design.

Fairness means same initialization, semantically matched math exposure, same optimizer policy unless separately studied, plus example-matched and token/compute-matched reporting where relevant.

## 26.6 Tokenizer/morphology confound

A fixed pretrained tokenizer gives different segmentation/frequency priors to English words and invented symbols.

Therefore:

- Q-A may measure language under the incumbent tokenizer;
- claims about intrinsic morphology require matched-adaptation and tokenization/frequency controls;
- changing the tokenizer is `TAU_CHANGE` or `JOINT`.

## 26.7 Output protocol

Prefer universal semantic action IDs for local input-representation assays when feasible.

# 27. PROJECTION ADMISSIBILITY

The statement “projection may expose any deterministically derivable true relation” is too permissive.

Every projection feature SHALL declare:

```text
projection_id
source_fields
derivation_algorithm
maximum derivation budget
uses_answer_label? false
uses_future_state? false
uses_hidden_solution? false
uses_minimum_proof_path? false
uses_candidate_correctness? false
```

Projection classes:

### P0 — direct relations

Directly present in the trusted state.

### P1 — local deterministic structure

Binder/use links, dependency edges, direct typing relations, local precondition status.

### P2 — bounded derived summaries

Permitted only with declared bounded derivation cost and no target-solution oracle.

### P3 — solution-dependent / future-dependent

Forbidden in candidate input.

Any uncertain projection is `OWNER/EXPERIMENT_REVIEW_REQUIRED` before use.

---

# 28. VERIFIER TRUST CONTRACT

Every verifier backend SHALL declare:

```text
verifier_id
version/domain
trust assumptions
accepted constructs
unsupported constructs
timeout semantics
UNKNOWN semantics
error semantics
replay/rechecking method
```

Rules:

- `UNKNOWN != FALSE`
- `TIMEOUT != FALSE`
- `TOOL_ERROR != MATHEMATICAL_INVALID`
- candidate success is never awarded because the verifier crashed
- candidate failure is never assigned merely because infrastructure failed

For high-stakes promotion, prefer independent replay/checking where practical.

---

# 29. REFUTER / GOODHART DEFENCE

Evolution optimizes loopholes aggressively. The Refuter is a first-class adversarial component, not an omniscient certifier.

Required attack classes include:

- answer position;
- semantic ID leakage;
- label leakage;
- lexical overlap;
- length/token patterns;
- field ordering;
- first/last mention;
- binder renaming;
- alpha-equivalence;
- irrelevant reorderings;
- duplicated information;
- malformed syntax;
- scope shadowing;
- partial operations;
- parser permissiveness;
- verifier crashes/timeouts;
- prompt injection;
- cross-split identifiers;
- theorem/module identity;
- reward-shaping exploits;
- macro-cost hiding;
- retrieval/tool asymmetry.

Confirmed exploits become permanent regression tests.

A shortcut detector making claims about model-visible cues MUST receive the exact model-visible surface, not a privileged canonical representation.

Default assurance wording:

```text
0 known critical exploits under attack_suite_version X
```

not “shortcut-free” or “unexploitable”.

Adaptive exploit discovery may use development data. Confirmation uses a frozen attack suite on fresh data or a valid selection-adjusted procedure.

# 30. STATISTICAL DECISION RULES

## 30.1 Paired design

Retain task-level paired outcomes and theorem/problem-family identifiers.

## 30.2 Tiny samples are smoke only

Small `n` such as 24 may calibrate engineering. Scientific sample size is justified by minimum practical effect, power/precision, dependence, and multiplicity.

## 30.3 Confirmatory manifests SHALL specify

```text
primary endpoint
minimum practical effect delta_min
sample size / precision target
paired method
multiplicity policy
cluster/grouping unit
stopping rule
allowed outcomes
evaluation-universe hash
```

## 30.4 Search creates winner's curse

Thousands of evolving candidates can overfit the development fitness surface.

Therefore:

- scout/search evidence is developmental;
- selected finalists require fresh confirmation;
- confirmation data MUST NOT guide mutation, candidate selection, thresholds, or surrogate training;
- repeated reuse of confirmation sets requires an explicit reusable-holdout/sequential-inference policy or new fresh data.

## 30.5 Discovery/evaluation separation

Do not discover the best heuristic/candidate on a small set and treat the same unadjusted score as confirmation.

Use disjoint discovery/evaluation data or valid family-wise/selection-aware inference.

## 30.6 Cluster dependence

Steps from the same theorem/module/problem family are not independent. Split/group and estimate uncertainty accordingly.

## 30.7 Store uncertainty

Keep raw task outcomes, intervals/posteriors, and paired effects—not only means.

# 31. SEARCHABILITY METRICS

The project SHALL explicitly measure whether language space is searchable.

Maintain at least:

- valid-neighbor rate;
- beneficial-mutation rate;
- parent-child fitness correlation;
- gene-effect directional consistency;
- local ruggedness `|F(child)-F(parent)|`;
- rank stability;
- novelty/diversity coverage;
- surrogate predictability on unseen edges;
- frequency of cross-gene epistasis.

Do not claim “searchable landscape” merely because one mutant wins.

A future formal decision rule SHALL be preregistered after the first pilot provides variance estimates.

---

# 32. POPULATION SEARCH POLICY

## 32.1 HC-V0 smoke

Normative engineering requirement:

- 3–4 existing founders;
- 1–4 children;
- exactly one generation;
- deterministic/stub or cheap live evaluation;
- no superiority claim.

## 32.2 Pilot 1 budget is experiment-specific

Earlier illustrative values such as 12 founders, 32 children/generation, and 10 generations are NOT binding defaults.

Pilot 1 population size, generations, promotion fractions, and budgets SHALL be selected only after HC-V0 measures:

- compile/death rate;
- evaluator latency/cost;
- task variance;
- candidate-pair discordance;
- long-horizon task availability;
- available compute.

## 32.3 Early search discipline

Early scientific search SHOULD retain strong incumbents, maintain diversity, prefer single-family mutations for causal reconnaissance, disable crossover until parent-child effects are interpretable, and stop at the preregistered budget.

If local effects are predictive, exploit local mutation. If not, use larger Architect jumps / quality diversity. If no useful effect is found under the declared universe, stop rather than search indefinitely for novelty.

# 33. LANGUAGE-FITNESS MEMORY

Every evaluation SHALL append a durable machine-readable record.

```text
LanguageFitnessRecord {
    record_id,
    parent_candidate_ids,
    candidate_id,
    mutation_ids,
    genome_hash,
    truth_kernel_version,
    dataset_manifest_hash,
    solver_id,
    tokenizer_id,
    controller_id,
    toolset_id,
    verifier_id,
    adaptation_budget,
    inference_budget,
    horizon_bucket,
    task_level_outcomes,
    fitness_vector,
    uncertainty,
    semantic_gate_results,
    refuter_results,
    failure_modes,
    wall_clock,
    compute_cost,
    prompt_hashes,
    code_commit,
    created_at,
}
```

This is not merely logging. It becomes the training set for future surrogate/Architect models.

---

# 34. WHEN THE ARCHITECT MAY LEARN

V0 uses structured evolutionary search and LLM proposals, not RL.

A surrogate fitness model MAY be activated only after enough clean evidence exists.

Recommended initial eligibility gate:

- >=1,000 valid evaluated parent-child edges OR an ADR justifying fewer;
- train/evaluation split by parent lineage/group;
- held-out rank prediction materially above null;
- no leakage from sealed promotion data.

A learned/RL Architect remains deferred until:

- reward semantics are stable;
- the multi-fidelity evaluator is reliable;
- candidate-fitness memory is large enough;
- Goodhart attacks are passing;
- a surrogate can predict some structure in unseen mutations.

---

# 35. PHASE-8 / V1–V7 HISTORICAL WORK

Historical micro-probes and Phase-8 machinery are not discarded.

## KEEP / REUSE

- rendered-prompt adversary machinery;
- power-analysis utilities;
- deterministic parity checks;
- cache/provenance systems;
- live Solver harnesses;
- semantic assurance;
- matched-training infrastructure;
- Refuter/fuzzing tools.

## DEMOTE TO DIAGNOSTIC

- formal expression depth;
- precondition conjunction;
- transitive dependency;
- other small next-action probes.

They may validate instrumentation or isolate local causal effects.

They SHALL NOT define the global language reward.

## DO NOT RUN BY DEFAULT

An unfinished founder tournament whose scientific role was defined before this meta-game reset SHALL NOT be resumed merely because its code exists.

---

# 36. REPOSITORY SPECIFICATION ARCHITECTURE

The full logical architecture may eventually be decomposed deeply, but HC-V0 MUST NOT block on creating dozens of mostly empty documents.

## 36.1 Minimum authoritative V0 set

```text
spec/
├── SOURCE/
│   ├── HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md
│   └── SOURCE_LEDGER.md
├── 00_CONSTITUTION.md
├── 01_GLOSSARY.md
├── 02_CLAIM_LEDGER.jsonl
├── language/
│   ├── LANGUAGE_META_GENOME_V0.md
│   └── language_genome_v0.schema.json
├── world/
│   ├── VERIFIED_TASK_TRAJECTORY_CONTRACT.md
│   └── SOURCE_ADMISSION_SCHEMA.json
├── evaluation/
│   └── HC_V0_EVALUATOR_CONTRACT.md
├── meta_game/
│   ├── HC_V0_OUTER_LOOP.md
│   └── LANGUAGE_FITNESS_MEMORY_SCHEMA.json
├── implementation/
│   ├── HC_V0_MANIFEST.yaml
│   └── HC_V0_ACCEPTANCE_TESTS.md
└── ADR/
```

Only files required to remove a current blocker need to exist.

## 36.2 Mature target architecture

As dependencies appear, split contracts for truth kernels, language compiler, mutation/lifecycle, statistics, robustness, data policy, Refuter, and experiment change control.

Do not create documents merely to satisfy a directory diagram.

## 36.3 Source preservation

Historical GOAL/HML/Arena documents remain preserved and cited in `SOURCE_LEDGER.md`.

# 37. EPISTEMIC TYPE SYSTEM FOR REQUIREMENTS

Every atomic specification statement SHALL have exactly one primary type:

- `OBJECTIVE`
- `INVARIANT`
- `HYPOTHESIS`
- `KNOWN_FACT`
- `UNKNOWN`
- `OWNER_DECISION`
- `ENGINEERING_DECISION`
- `PREFERENCE`
- `DELEGATED_FREEDOM`
- `NON_GOAL`
- `DEFERRED`

Each record SHALL include:

```text
id
source_ref
statement
type
status
scope
owner
dependencies
contradictions
resolution_method
acceptance_or_evidence
```

An agent MAY NOT convert `HYPOTHESIS` into `KNOWN_FACT` without an evidence/decision record.

An agent MAY NOT convert `UNKNOWN` into `ENGINEERING_DECISION` merely to continue coding unless the unknown is explicitly delegated.

---

# 38. SPECIFICATION REFINEMENT PIPELINE

Use refinement only to the depth required by the next executable dependency.

1. Preserve raw owner intent.
2. Identify current authority and any frozen experiment.
3. Atomize only active normative claims.
4. Type scientific status: fact / hypothesis / unknown / decision.
5. Define overloaded critical terms.
6. Write behavioral contracts: inputs, outputs, preconditions, postconditions, invariants, failures, delegated freedom, tests.
7. Trace implementation leaves to current requirements/ADRs.
8. Run hard readiness blockers.
9. Turn scientific unknowns into experiments only when they block a claim/decision.
10. Once a leaf is objectively testable, code it.

## 38.1 Timebox

For HC-V0, specification/refinement SHOULD consume no more than roughly 25% of the implementation session unless a genuine owner ambiguity or semantic-substrate blocker is discovered.

Do not recursively atomize the entire historical repository before building the thin vertical slice.

# 39. IMPLEMENTATION PACKET TEMPLATE

```text
TASK-ID:
TITLE:
STATUS: READY_FOR_IMPLEMENTATION | BLOCKED

PURPOSE:

SOURCE REQUIREMENTS:

AUTHORIZED FILES:

INPUTS:

OUTPUTS:

PRECONDITIONS:

REQUIRED BEHAVIOUR:

FORBIDDEN BEHAVIOUR:

INVARIANTS:

FAILURE SEMANTICS:

DELEGATED FREEDOMS:

SCIENTIFIC UNKNOWNS TO PRESERVE:

DEPENDENCIES:

ACCEPTANCE TESTS:

PROVENANCE/HASH REQUIREMENTS:

DONE IFF:
```

If any `OWNER_AMBIGUITY` remains, status SHALL be `BLOCKED`.

---

# 40. HAMILTONIAN CHESS V0 — MINIMUM VERTICAL SLICE

HC-V0 proves the outer loop executes. It is not a scientific language tournament.

## 40.1 Preconditions

- useful Phase-8 engineering is salvaged;
- baseline tests are green;
- minimum V0 specs in Section 36.1 exist;
- at least one verifier-backed `VerifiedTask` OR explicitly replay-only source is admitted;
- 3–4 existing candidates can encode the chosen workspace;
- one controlled mutation exists;
- truth/assurance gate works;
- one Solver adapter OR deterministic stub evaluator works;
- fitness records persist deterministically.

## 40.2 Flow

```text
load population
 -> choose parent using deterministic V0 policy
 -> apply one controlled mutation
 -> compile child
 -> truth/assurance gate
 -> evaluate on a small verifier-backed arena
 -> write LanguageFitnessRecord
 -> compare/archive
 -> emit next-generation state
```

## 40.3 Evaluation mode

Preferred: `INTERACTIVE_TASK`.

Allowed for engineering-only V0: `TRAJECTORY_REPLAY`.

If replay-only is used, autonomous long-horizon solving remains explicitly blocked.

## 40.4 Candidate scale

- 3–4 founders;
- 1–4 children;
- exactly one generation;
- stub evaluation may validate orchestration;
- at least one real backend/verifier interaction SHOULD run if practical.

## 40.5 Success criterion

The loop executes end-to-end with deterministic lineage, truthful intervention classification, verifier/assurance provenance, durable fitness memory, and reproducible archive update.

No improvement is required.

## 40.6 Sentinels

Exactly one primary sentinel:

- `META_GAME_V0_EXECUTABLE`
- `META_GAME_ARCHITECTURE_READY`
- `META_GAME_BLOCKED_BY_TRAJECTORY_WORLD`
- `META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD`
- `META_GAME_BLOCKED_BY_SEMANTIC_SUBSTRATE`
- `SPEC_BLOCKED_BY_OWNER_AMBIGUITY`

No `RSTAR` or `LSTAR` claim is allowed.

# 41. PILOT 1 — FIRST SCIENTIFIC LANGUAGE-LANDSCAPE STUDY

Pilot 1 begins only after HC-V0 is executable and the scientific evaluator has a frozen manifest.

## 41.1 Objective

Determine whether the bounded meta-genome produces a measurable, reproducible, partially searchable fitness landscape on verifier-backed mathematics.

## 41.2 Budget determination

Before preregistration measure:

- compile/death rate;
- episode cost;
- metric variance;
- pair discordance;
- task/horizon availability;
- practical effect size;
- total compute budget.

Then freeze founder roster, children/generation, generations, promotion policy, diversity policy, evaluation fidelity, and stop budget.

## 41.3 Required questions

- Do language/workspace families differ under matched conditions?
- How do effects interact with horizon?
- Do parent-child mutations produce reproducible effects?
- Which intervention classes matter?
- Does morphology survive matched adaptation beyond pretraining familiarity?
- Is prior mutation evidence predictive of future mutation outcomes?
- Are important epistatic interactions present?

## 41.4 Search versus confirmation

Search may adapt on development evidence.

Any champion/superiority claim requires fresh search-independent confirmation.

## 41.5 Stop condition

Stop at the preregistered search/evaluation budget. Do not continue until a custom language wins.

# 42. ACCEPTANCE TEST CATEGORIES

At minimum, repository CI SHOULD contain tests for:

## Specification / schemas

- glossary uniqueness;
- no duplicate IDs;
- schema validation;
- authority precedence;
- unresolved ambiguity lint.

## Language genome

- deterministic serialization;
- hash stability;
- constraint rejection;
- mutation provenance;
- lineage integrity.

## Compiler

- deterministic rendering;
- binding/scope preservation;
- type preservation;
- semantic parity;
- no answer leakage;
- action lowering.

## Trajectory world

- state/action/next-state linkage;
- deterministic replay;
- verifier evidence;
- horizon calculation;
- split isolation;
- provenance hashes.

## Evaluation

- matched task identity;
- cache key completeness;
- prompt hash identity;
- candidate/task pairing;
- paired statistics;
- no train/promotion overlap;
- no hidden data exposure.

## Evolution

- candidate lifecycle transition legality;
- population update determinism;
- archive update;
- dead candidate cannot be evaluated;
- one full smoke generation.

## Refuter

- alpha-renaming;
- answer-order controls;
- surface leakage tests;
- verifier failure distinction;
- parser permissiveness regression.

---

# 43. FAILURE SEMANTICS AND SCIENTIFIC SENTINELS

The system MUST prefer explicit negative/blocked states over optimistic prose.

Recommended sentinels include:

```text
SPEC_BLOCKED_BY_OWNER_AMBIGUITY
SPEC_BLOCKED_BY_UNDEFINED_CRITICAL_TERM
TRAJECTORY_SOURCE_NOT_ADMISSIBLE
DEAD_SEMANTIC
DEAD_LEAKAGE
INSTRUMENT_INVALID
LANDSCAPE_NOT_ESTABLISHED
LANDSCAPE_TOO_RUGGED_FOR_LOCAL_SEARCH
REPRESENTATION_EFFECT_MODEL_SPECIFIC
MATCHED_ADAPTATION_SIGNAL_FOUND
ROBUST_LANGUAGE_CANDIDATE_FOUND
NO_PRACTICALLY_USEFUL_LANGUAGE_EFFECT_FOUND
```

Negative evidence is a valid project result.

---

# 44. CHANGE CONTROL

## 44.1 Constitution change

Requires explicit owner authorization.

## 44.2 Meta-genome schema change

Requires ADR, migration, new schema version, and impact analysis.

## 44.3 Truth-kernel change

Requires new kernel version, verification, migration, and explicit experiment invalidation review.

## 44.4 Experiment-manifest change after scientific exposure

Forbidden unless the experiment is marked invalid and restarted under a new manifest version.

## 44.5 Engineering refactor

Allowed if public contracts, hashes where required, and scientific behaviour remain unchanged.

---

# 45. WHAT THE OWNER DOES

The owner SHOULD NOT hand-design hundreds of languages.

The owner is responsible for:

1. mission and scientific boundaries;
2. accepting/rejecting constitution changes;
3. resolving true owner-intent ambiguities;
4. approving major search-space expansions;
5. approving compute/cost limits;
6. approving claims/releases.

The owner is NOT responsible for:

- manually inventing every grammar;
- writing every morpheme;
- choosing every mutation;
- manually annotating millions of trajectories;
- deciding every engineering implementation detail.

---

# 46. WHAT CODEX / CLAUDE DOES

The implementation/research agent is responsible for:

1. atomizing and formalizing specifications;
2. identifying ambiguities rather than guessing;
3. implementing deterministic schemas/contracts;
4. auditing existing repo assets before rebuilding;
5. constructing the trajectory world;
6. implementing the meta-genome compiler;
7. implementing the outer loop;
8. running only preregistered scientific experiments;
9. preserving provenance and negative results;
10. proposing evidence-backed changes through ADRs.

It MUST NOT silently redesign the project while implementing it.

---

# 47. IMMEDIATE EXECUTION ORDER

Optimize for the shortest path to an executable meta-game without discarding useful infrastructure.

## Step 1 — Salvage current Phase-8 engineering

Timebox the salvage.

Preserve rendered-prompt adversary, power/statistics utilities, live harness, parity/assurance code, and useful generators.

Do NOT finish the obsolete founder tournament merely because it was in progress.

Commit salvage separately.

## Step 2 — Freeze this manual as source

After owner acceptance, save v0.2 unchanged under `spec/SOURCE/`.

Do not immediately explode it into dozens of documents.

## Step 3 — Create the minimum authority set

Create only Section 36.1's minimum V0 contracts.

## Step 4 — Repository remap

Classify existing components:

- `KEEP`
- `REFACTOR`
- `DEMOTE_TO_DIAGNOSTIC`
- `ARCHIVE`
- `MISSING`

Prefer reuse over reimplementation.

## Step 5 — Audit world assets

Critical question:

> Which existing source can support the cheapest genuine interactive multi-step `VerifiedTask`?

Also inventory replay-only sources.

## Step 6 — Select one V0 world

Choose the smallest verifier-backed world adequate for end-to-end execution.

## Step 7 — Implement only missing V0 pieces

- minimal executable meta-genome subset;
- one mutation;
- compiler bridge;
- fitness record;
- archive/population state.

## Step 8 — Run one deterministic outer generation

Use 3–4 existing candidates and 1–4 children.

A stub may validate orchestration; at least one real backend/verifier interaction SHOULD run if practical.

## Step 9 — Red-team the loop

Attack lineage/provenance, truth mutation, cache identity, oracle leakage, dead-candidate enforcement, and fitness-memory immutability.

## Step 10 — Stop and hand off

Do NOT continue directly into Pilot 1.

Report measured V0 costs, variance, and blockers so the scientific pilot can be designed from evidence.

# 48. THINGS THE PROJECT MUST NOT DO NEXT

Do NOT:

- invent `HML_V4` by hand;
- generate 100 hand-designed languages;
- run 100 AI agents because “more agents” sounds evolutionary;
- train an RL Architect immediately;
- resume a scientifically obsolete founder tournament automatically;
- build another micro-benchmark as the global objective;
- download a million problems before proving the trajectory adapter works;
- optimize tokenizer and language simultaneously in V0;
- co-evolve curriculum and language before local measurement works;
- rewrite Lean/OpenMath/MMT/SymPy/Julia/JAX;
- let candidates change the verifier;
- let candidates access future proof states;
- use human readability as the winner criterion;
- search indefinitely until novelty appears.

---

# 49. SOURCE-REFINEMENT / TRACEABILITY LEDGER

Every normative requirement SHOULD trace to one or more source classes:

```text
OWNER_DIRECTIVE
CURRENT_ARENA_GOAL
HML_LEGACY_GOAL
HML_LEGACY_ARCHITECTURE
SEMANTICS_SOURCE_SYNTHESIS
EXPERIMENTAL_RESULT
FORENSIC_AUDIT
PRIOR_ART_AUDIT
SPECIFICATION_RESEARCH
ENGINEERING_ADR
```

Historical HML repository evidence establishes useful prior architecture: surface syntax was separated from a typed semantic core, and the semantic core was treated as the source of truth while JSON/graph/English/backend views were projections. Preserve that design lesson while allowing the model-facing language to evolve.

The source synthesis from programming-language semantics establishes the architectural requirement to distinguish operational, denotational, and proof/axiomatic semantics and to make binding/scope explicit.

The specification-refinement guide establishes the process requirement to preserve raw source intent, atomize claims, type epistemic status, eliminate owner ambiguity, keep scientific unknowns explicit, construct behavioural contracts, and maintain traceability.

---

# 50. BOOTSTRAP DIRECTIVE FOR CLAUDE/CODEX

```text
HAMILTONIAN CHESS V0 — EXECUTION BOOTSTRAP

Read HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md completely.

PRIMARY RULE:
Do not spend the session perfecting documents.
Do not resume the obsolete Phase-8 founder tournament.
Do not design a new language.
Build the smallest truthful outer loop that can eventually discover one.

PHASE A — SALVAGE
1. Inspect Git, all worktrees, untracked Phase-8 files, tests, and import path.
2. Preserve useful Phase-8 engineering:
   rendered-prompt adversary, power/statistics utilities, live harness, parity/assurance,
   reusable generator code.
3. Do not freeze or run the old founder experiment.
4. Write PHASE8_SALVAGE_HANDOFF.md.
5. Commit salvage separately.

PHASE B — MINIMUM AUTHORITY / REMAP
6. Save this accepted manual unchanged under spec/SOURCE/.
7. Create only the minimum V0 spec set in Section 36.1.
8. Create a CURRENT claim ledger; do not atomize every historical sentence.
9. Ask the owner only if a genuine owner ambiguity blocks V0 behavior.
10. Remap repository assets:
       KEEP / REFACTOR / DEMOTE_TO_DIAGNOSTIC / ARCHIVE / MISSING.

PHASE C — WORLD
11. Inventory verifier-backed task/trajectory assets.
12. Distinguish:
       VerifiedTask       = interactive environment
       VerifiedTrajectory = one recorded path.
13. Never treat a recorded next action as the only correct action unless the verifier proves it.
14. Choose the smallest source supporting a real V0 backend/verifier interaction.
15. If only replay is available, continue engineering V0 but record the interactive-world blocker.

PHASE D — THIN META-GAME
16. Implement the MINIMAL executable subset of LanguageMetaGenomeV0.
17. Use 3–4 EXISTING candidates; do not invent HML_V4.
18. Implement exactly one controlled mutation with an InterventionClass.
19. Compile/gate the child.
20. Evaluate using a deterministic stub if needed for orchestration, plus at least one real
    verifier/backend interaction if practical.
21. Persist immutable LanguageFitnessRecord(s).
22. Update archive/population.
23. Emit next-generation state.

PHASE E — VERIFY
24. Run:
       python -m pytest
       python -m ruff check .
       python -m ruff format --check .
       python -m mypy arena
25. Add tests for:
       truth cannot mutate
       intervention class is explicit
       dead candidates cannot evaluate
       lineage/provenance determinism
       action macro kernel-cost accounting
       fitness-memory append-only semantics
       task vs trajectory distinction
       one complete outer generation.

HARD STOPS:
- no paid cloud compute unless separately authorized;
- no 120-mutant run;
- no RL Architect;
- no scientific founder tournament;
- no LSTAR/RSTAR claim;
- no giant corpus ingestion;
- no universal canonical rewrite;
- no exhaustive historical-spec atomization.

TIME DISCIPLINE:
Spend no more than roughly one quarter of the session on specification/refinement unless a
real owner ambiguity or semantic blocker is discovered.

FINAL HANDOFF:
Return:
  PHASE8_SALVAGE
  MINIMUM_SPEC_STATUS
  REPOSITORY_REMAP
  VERIFIED_TASK_SOURCE
  VERIFIED_TRAJECTORY_SOURCE
  META_GENOME_V0_MINIMAL_SUBSET
  INTERVENTION_CLASS_USED
  OUTER_LOOP
  DID_ONE_GENERATION_EXECUTE?
  REAL_VERIFIER_CALL?
  FITNESS_MEMORY
  TESTS
  GIT
  MEASURED_COSTS
  BLOCKERS
  SINGLE HIGHEST-EV NEXT ACTION

End with exactly one:
  META_GAME_V0_EXECUTABLE
  META_GAME_ARCHITECTURE_READY
  META_GAME_BLOCKED_BY_TRAJECTORY_WORLD
  META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD
  META_GAME_BLOCKED_BY_SEMANTIC_SUBSTRATE
  SPEC_BLOCKED_BY_OWNER_AMBIGUITY

The objective is not to design the winner.
The objective is to make one honest generation run.
```

# APPENDIX A — EXAMPLE ATOMIC REQUIREMENT

```text
REQ-LANG-0042

SOURCE:
OWNER_DIRECTIVE / morphology hypothesis

TYPE:
INVARIANT

STATEMENT:
A pure morphology comparison SHALL NOT change visible mathematical information.

INPUTS:
- KernelState S
- Projection P
- Parent language Lp
- Child language Lc

PRECONDITIONS:
- P(S) is identical by semantic identity across both arms.
- Lp and Lc differ only in approved morphology genes.
- same tokenizer and Solver checkpoint are frozen.

POSTCONDITIONS:
- both prompts decode to identical semantic inventory.
- only morphology/interface bytes differ within the declared mutation.

FAILURE:
If semantic inventory differs, comparison = INVALID_CONFOUND.

VERIFY:
- canonical inventory hash equality;
- candidate diff audit;
- prompt provenance hashes.

SCIENTIFIC UNKNOWN PRESERVED:
Whether the morphology change improves capability.
```

---

# APPENDIX B — EXAMPLE UNKNOWN OBJECT

```text
UNKNOWN-U-MORPH-001

QUESTION:
Does compositional invented morphology outperform controlled English after matched adaptation?

TYPE:
SCIENTIFIC UNKNOWN

DO NOT RESOLVE BY:
- owner intuition
- aesthetic judgement
- zero-shot performance alone

RESOLUTION PATH:
EXP-MORPH-001

REQUIRED CONDITIONS:
- same semantic state
- same visible information
- same Solver base checkpoint
- same training examples
- example-matched condition
- token/compute-matched confirmation
- long-horizon evaluation

STATUS:
OPEN
```

---

# APPENDIX C — EXAMPLE ARCHITECT MUTATION

```text
MUT-00814

parent: L-0048
family: MORPHOLOGY_MUTATION

change:
  lexicon_family:
    FORMAL_ENGLISH -> COMPOSITIONAL_SYMBOLIC

preserved:
  ontology
  projection
  topology
  typing/binding
  grammar abstract syntax
  action granularity
  interface ordering

hypothesis:
  compositional morphemes reduce lexical polysemy and improve long-horizon state tracking
  after matched adaptation.

expected_cost:
  worse zero-shot acquisition

required_tests:
  semantic parity
  morpheme grammar validity
  answer leakage
  H5/H20 comparison after adaptation
```

---

# APPENDIX D — CLAIM TIERS

Evidence tier and lifecycle state are orthogonal.

## `VALID_CANDIDATE`

Passed deterministic genome/compile/truth/assurance gates required by its intervention class.

Means “0 known blocking defects under the declared gate,” not “shortcut-free” or universally valid.

## `FITNESS_CANDIDATE`

Shows reproducible practical improvement on a declared local assay with fresh or selection-adjusted evidence.

## `LEARNABILITY_CANDIDATE`

Survives matched adaptation and fresh evaluation.

## `ROBUST_CANDIDATE`

Survives multiple seeds plus declared structural/domain holdouts and strong incumbents.

## `RSTAR_0_1`

Reserved for `R_ONLY`.

Requires strong controls, matched conditions, holdout confirmation, and at least two meaningfully distinct Solver families.

Meaning: strongest robust representation discovered under the declared representation-only universe.

## `LSTAR_0_1`

For the broader language/workspace search where ontology, projection, action protocol, morphology, structure, or other intervention classes may vary.

Requires strong incumbents, matched-adaptation confirmation, genuine interactive/long-horizon evaluation where claimed, fresh search-independent confirmation, at least two distinct Solver families, no unresolved critical truth/leakage defect, and ablation records for JOINT candidates when component claims are made.

Meaning: strongest robust language/workspace candidate discovered under the declared Hamiltonian Chess search universe.

Neither label means globally optimal for every possible AI or mathematical domain.

# APPENDIX E — FINAL NORTH STAR

> **Hamiltonian Chess does not design the winning mathematical language by hand. It defines a truth-grounded mathematical world, a generative meta-space of possible machine-facing mathematical languages/workspaces, and an evidence-preserving evolutionary game in which candidate languages are compiled, verified, learned, used for genuine long-horizon mathematics, attacked, compared, archived, and mutated. The project succeeds if this process either discovers reproducible improvements over strong human-designed incumbents or produces bounded evidence that declared regions of language-design space do not provide useful gains.**

And the specification doctrine is:

> **Make owner intent lossless, make scientific uncertainty explicit, make implementation contracts executable, and leave as few interpretive degrees of freedom as possible.**

