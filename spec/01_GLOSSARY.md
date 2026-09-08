# 01 — CONTROLLED GLOSSARY

**Source:** manual §6.1–§6.36 (canonical terms) and §1 (restricted adjectives). This file is
load-bearing: §1 forbids a set of adjectives unless they refer to a controlled glossary definition
or carry an experiment-specific operational meaning. **Part B of this file is what makes the rest
of `spec/` legal under §1.**

Each entry carries its §37 epistemic type where a type applies. Definitional entries are
`INVARIANT` (they fix meaning and may not be silently re-read); entries that assert something about
the world carry the type of that assertion.

---

# PART A — CANONICAL TERMS (§6)

## A.0 Two distinctions this project has historically conflated

Read these two before anything else.

### `InterventionClass` (§6.26) — `INVARIANT`

**Every candidate comparison SHALL be typed as exactly one of:**

| Class | What changes | Fairness contract | Causal claim permitted |
|---|---|---|---|
| `R_ONLY` | representation / morphology / interface bytes only | full held-fixed contract of §26.2 | representation effect |
| `P_CHANGE` | projection / visibility policy `P` (§6.6) | parent delta + admissibility audit (§12.3, §27) | value of that projection, **not** a representation effect |
| `O_CHANGE` | reasoning ontology `O` (§6.5) | as above | value of that ontology change |
| `T_CHANGE` | type / identity / binding system `T` (§6.8) | as above | value of that binding change |
| `A_CHANGE` | action protocol / granularity `A` (§6.11) | as above **plus** kernel-cost accounting (§13.1) | value of that action design |
| `TAU_CHANGE` | tokenizer `τ` (§6.13) | model-level change; §26.6 | tokenizer/morphology joint effect only |
| `C_CHANGE` | search controller `C` (§6.15) | controller experiment | controller effect |
| `JOINT` | two or more of the above | enumerate every changed component (§12.3) | **system-level only**; component attribution requires later ablation (§26.4) |

The class **determines** the fairness contract and the causal claims permitted (§6.26, §12.3, §26).
Strict visible-information parity is mandatory **only** where the intervention claims to hold
information fixed (§0 v0.2 correction 6). An undeclared intervention is a candidate death:
`DEAD_UNDECLARED_INTERVENTION` (§12.4).

### The horizon family (§6.30–§6.34) — `INVARIANT`

These five quantities are **distinct numbers** and **SHALL** be reported separately (§17.6).

| Term | §  | Definition | What it is **not** |
|---|---|---|---|
| `ObservedTraceLength` | §6.30 | number of transitions in **one stored demonstration** | not the minimum reasoning horizon the task requires |
| `EpisodeLength` | §6.31 | number of **model-facing decisions** in an actual interactive Solver run | not the recorded proof's length |
| `KernelStepCount` | §6.32 | number/cost of **trusted backend operations after action lowering** | not the model action count; a macro lowering to 30 kernel steps costs 30 (§13.1) |
| `DependencyDepth` | §6.33 | a **task-family-specific structural dependency measure** | not a token count and not a step count |
| `MinimalProofLength` | §6.34 | shortest proof/solution length under a declared action system, **only when independently established**; otherwise the literal value `UNKNOWN` | never inferred from an observed trace |

`Reasoning Horizon` (§6.21) is the number of sequential **dependent** reasoning transitions
required or observed in an episode. It is **not** the number of concatenated unrelated microtasks.

**Forbidden phrasing (§17.6):** calling a recorded 50-step proof a "50-step required reasoning
task" without evidence of necessity or minimality.

---

## A.1 Truth and state

| Term | § | Definition | Type |
|---|---|---|---|
| `K` — Truth Kernel | 6.1 | Backend-grounded mathematical semantics and verification layer that determines whether claims and primitive transitions are valid under a declared formal universe. **`K` is not the model-facing language.** `K` MUST be versioned. | `INVARIANT` |
| `KernelState` | 6.2 | The backend-native or canonical semantic state on which mathematical validity is defined. A Lean proof state MAY be represented by a Lean-native semantic envelope rather than forced into a lossy universal AST. | `INVARIANT` |
| `WorkspaceState` | 6.3 | The state exposed to, maintained for, or manipulated by the Solver under candidate language `L`. May contain derived structures permitted by a projection policy; MUST remain truth-grounded. | `INVARIANT` |
| `BackendKernelContract` | 6.24 | A versioned verifier/transition contract for **one** backend or mathematical domain. Hamiltonian Chess does **not** require one universal lossless `KernelState` for every branch of mathematics. | `INVARIANT` |
| `V` — Verifier | 6.18 | The trusted checker/oracle adjudicating mathematical validity **within its declared trust domain** (§28). | `INVARIANT` |

## A.2 The candidate language `L = (O, P, S, T, G, M, A, I)` (§6.4)

`L` is the **complete machine-facing cognitive interface under evaluation** — not a syntax.

| Component | § | Definition |
|---|---|---|
| `O` — Reasoning Ontology | 6.5 | Which model-facing state entities are first-class (goal, obligation, dependency, failed branch, warrant, evidence, counterexample, conjecture). **`O` is not the truth kernel.** |
| `P` — Projection / Visibility Policy | 6.6 | Which truth-grounded facts or deterministic derived relations from `K` and permitted history are made explicit to the Solver. `P` **MUST NOT** expose future proof steps, answer labels, minimum proof paths, candidate correctness labels, or other oracle information (see §27 classes P0–P3). |
| `S` — State Topology | 6.7 | How workspace entities and relations are organized: sequence, tree, DAG, graph, hypergraph, local contexts, goal-centric clusters. |
| `T` — Type / Identity / Binding System | 6.8 | How types, binder identity, scope, freshness, references, and partiality are represented to the Solver. |
| `G` — Grammar | 6.9 | Formal composition rules defining well-formed candidate expressions and workspace records. |
| `M` — Morphology / Lexicon | 6.10 | How semantic units map to tokens/morphemes/symbol sequences. |
| `A` — Action Protocol and Granularity | 6.11 | How the Solver expresses reasoning/search moves. `A` **MAY** define high-level verified macros, but those macros **MUST** lower to truth-kernel-supported primitive effects or backend-verifiable programs. |
| `I` — Interface / Serialization | 6.12 | Ordering, field structure, delimiters, redundancy, local adjacency, compression, graph traversal, ID formatting, presentation. |

## A.3 The evaluation apparatus

| Term | § | Definition | Type |
|---|---|---|---|
| `τ` — Tokenizer / input encoder | 6.13 | The tokenizer or low-level model encoder. **SHALL remain fixed** during early language comparisons unless a dedicated tokenizer co-design experiment is active. | `INVARIANT` |
| `π` — Solver | 6.14 | The AI model/policy that attempts mathematical reasoning. | `INVARIANT` |
| `C` — Search Controller | 6.15 | The algorithm controlling reasoning/search (greedy, beam, MCTS, best-first, retry loop, branch manager, retrieval policy). **`C` is not part of `L` in early causal experiments**, although later joint co-design is permitted. | `INVARIANT` |
| `D` — Task/Environment Distribution | 6.16 | The declared mathematical problem distribution used for training/evaluation. | `INVARIANT` |
| `U` — Tools/Libraries | 6.17 | Permitted external resources: theorem libraries, retrieval, symbolic systems, calculators, SMT solvers. | `INVARIANT` |
| `B` — Resource Budget | 6.19 | Training tokens, inference tokens, GPU-hours, wall-clock, tool-call limits, branch limits. | `INVARIANT` |
| `EvaluationUniverse` | 6.27 | The declared context under which fitness is estimated: task distribution · backend/kernel versions · Solver initialization/checkpoint · tokenizer · controller · tools · adaptation data · adaptation budget · inference budget · verifier · seeds · evaluation split · code/manifest versions. **Fitness outside this universe is `UNKNOWN` until replicated.** | `INVARIANT` |

## A.4 Tasks, trajectories, fitness

| Term | § | Definition | Type |
|---|---|---|---|
| `VerifiedTask` | 6.25 | An **executable, interactive** verifier-backed task with: initial truth-grounded state; terminal criteria; action decoding/lowering; transition/verifier interface; declared tools/libraries; explicit failure semantics. | `INVARIANT` |
| `VerifiedTrajectory` | 6.20 | A contiguous sequence of mathematically grounded states and actions whose transitions and terminal status are supported by a verifier/backend. **One recorded path.** A stored `VerifiedTrajectory` does **not** necessarily support interaction (§6.25). | `INVARIANT` |
| `Fitness` | 6.22 | A **vector** of measured outcomes under a fully declared `EvaluationUniverse`. It is **not** a single arbitrary score. | `INVARIANT` |
| `Searchability` | 6.23 | The degree to which observations from previously evaluated candidates predict useful future candidate modifications better than a null/random search process. | `INVARIANT` |

## A.5 Exposure — two separate concepts (§6.28, §6.29, §18.1)

| Term | § | Definition | Type |
|---|---|---|---|
| `ProjectHidden` | 6.28 | Data **not inspected or used by Hamiltonian search/development** before its confirmation role was frozen. **This does not imply the pretrained model never saw equivalent data.** Previously inspected data is not project-hidden later merely because it is hashed or renamed (§18.1). | `INVARIANT` |
| `ModelExposureStatus` | 6.29 | Exactly one of `KNOWN_PRE_CUTOFF_PUBLIC`, `KNOWN_POST_CUTOFF`, `LIKELY_PRETRAINING_EXPOSURE`, `UNKNOWN`, `NEWLY_GENERATED_AFTER_MODEL_FREEZE`. | `INVARIANT` |

These are **separate fields** in every `SourceAdmissionRecord`
(`spec/world/SOURCE_ADMISSION_SCHEMA.json`). Conflating them is the error §18.1 exists to prevent.

## A.6 Claim labels

| Term | § | Definition | Type |
|---|---|---|---|
| `LSTAR` | 6.35 | A claim about the **broader language/workspace search**, where ontology, projection, action protocol, morphology, structure, or other intervention classes may vary. Requires Gate 6 (§25) and Appendix D's `LSTAR_0_1` conditions. | `INVARIANT` |
| `RSTAR` | 6.36 | **Reserved for a representation-only `R_ONLY` search** under fixed projection, ontology, action semantics, tokenizer, controller, and other declared variables. `RSTAR_0_1` additionally requires an `R_ONLY` search **and** confirmation (§25 Gate 6). | `INVARIANT` |

Neither label means globally optimal for every possible AI or mathematical domain (Appendix D).

---

# PART B — OPERATIONAL MEANINGS FOR §1's RESTRICTED ADJECTIVES

§1: *"No document may use words such as `best`, `robust`, `fair`, `sufficient`, `general`, `clean`,
`strong`, `efficient`, `meaningful`, `valid`, or `matched` without either (1) referring to a
controlled glossary definition; or (2) defining an experiment-specific operational meaning."*

These are the controlled definitions. A document in `spec/` that uses one of these words **SHALL**
cite the entry below or supply its own operational meaning inline. Where a plainer word exists,
`spec/` prefers the plainer word and these entries exist to police quotations and inherited names.

| # | Word | Controlled operational meaning | Trace |
|---|---|---|---|
| B.1 | **best** | Only ever *"leading under the declared `EvaluationUniverse` and search budget"*. Never "globally optimal". A generation winner is a **leaderboard position**, not a scientific winner (§0.2, §40.5, Appendix D). | §6.27, §40 |
| B.2 | **robust** | Reserved for `ROBUST_CANDIDATE` (Appendix D): survives multiple seeds **plus** declared structural/domain holdouts **plus** incumbent-grade baselines. Elsewhere use *resistance to a named perturbation*, and name it. `R_robust` in the fitness vector = stability across seeds/tasks and later model families (§22). | Appendix D, §22 |
| B.3 | **fair** | Has **no** context-free meaning here. "Fair" is always *"satisfies the fairness contract of the declared `InterventionClass`"* (§26). For `R_ONLY` that is the §26.2 held-fixed list; for `P_/O_/T_/A_CHANGE` it is machine-readable parent delta + admissibility audit + a claim label matching the class (§12.3). | §26 |
| B.4 | **sufficient** | Only as *"passes a declared, representable threshold at the planned n"*. A threshold that the estimator cannot attain at the planned n is `THRESHOLD_UNREPRESENTABLE` and is not a threshold. Never "enough data" without a number. | §30.2, §30.3 |
| B.5 | **general** | Only as *"generalization to a declared holdout"* — `Q_OOD` in the fitness vector, measured on a named split with a named grouping unit (§18.2, §22). Never "generally true". | §22, §18.2 |
| B.6 | **clean** | Only as *"0 known critical defects under the declared gate and attack-suite version"* — the §29 default wording. Never "shortcut-free", never "unexploitable". | §29, Appendix D |
| B.7 | **strong** (of a baseline) | *Incumbent-grade*: a founder that is retained in the Hall of Fame indefinitely by §19.2 — controlled English, and Lean-like baselines where the domain permits — evaluated under the same `EvaluationUniverse` as the candidate. | §19.2, §25 Gate 5 |
| B.8 | **efficient** | Always disambiguated into a named cost dimension of the §22 vector: `C_token` (tokens per episode/verified solve), `C_kernel` (backend operations after lowering), `C_compute` (wall-clock/GPU/tool cost), or `S_search` (branches/states/retries/decisions/tool calls per solve). A model-facing efficiency claim **MUST** be reported alongside `C_kernel` (§13.1). `L_sample` covers learning/sample efficiency = capability versus held-fixed adaptation exposure. | §22, §13.1 |
| B.9 | **meaningful** | Only as *"exceeds the preregistered minimum practical effect `delta_min`"*. Statistical significance alone is not this word. | §30.3 |
| B.10 | **valid** | Two disjoint controlled senses, never interchanged. (a) *Mathematically valid* — the verifier accepted it within its declared trust domain (§28). (b) `VALID_CANDIDATE` (Appendix D) — passed the deterministic genome/compile/truth/assurance gates **required by its intervention class**, meaning "0 known blocking defects under the declared gate", not "shortcut-free" or universally valid. Lifecycle state `GENOME_VALID` (§21) is sense (b) at the schema stage only. | §28, Appendix D, §21 |
| B.11 | **matched** | *Held fixed by an enumerated list.* Never a vibe. "Matched adaptation" = same initialization, semantically equal mathematical exposure, same optimizer policy unless separately studied, **plus** example-matched and token/compute-matched reporting where relevant (§26.5). "Matched comparison" = the §26.1 universal declaration list is identical across arms except the declared intervention. | §26.1, §26.5 |

## B.12 Words this project also refuses without a number

`ENGINEERING_DECISION`. Not from §1, added because the repository's own audits name them as the
failure mode: *significant* (state the test, the n, and the multiplicity policy — §30.3);
*long-horizon* (state which of §6.30–§6.34 is meant); *diverse* (state the behavioural descriptor
and its measured value — two of this repository's eight seed surfaces share 98.6% of their state
bytes, so "diverse population" is a measurable claim, not an adjective).

---

---

## B.13 Restricted words inside manual-verbatim names

`ENGINEERING_DECISION`. Several §1-restricted words appear inside **names the manual fixes** and
that `spec/` therefore quotes rather than chooses. In those positions the word is part of a proper
name, not an adjective, and it carries the manual's own meaning at the cited section:

- `§25 Gate 2 — short matched adaptation`, `§25 Gate 6 — robust validation` — gate titles.
- `§26 FAIR COMPARISON AND CAUSAL-CLAIM CONTRACT` — section title; the operational content is
  §26.1's declaration list and §26.2's fixed-variable list, per §B.3.
- `§14.4 VERIFIED_REFUTED where valid` — outcome vocabulary, sense §B.10(a).
- `§21 GENOME_VALID`, `Appendix D VALID_CANDIDATE`, `§31 valid-neighbor rate` — enumerated state
  and metric names, sense §B.10(b).
- `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` — a sentinel name recorded before this glossary
  existed; it is not re-read, per `spec/00_CONSTITUTION.md` C9.
- `§42 matched task identity`, `§26.5 example-matched / token-compute-matched` — test-category and
  reporting names, sense §B.11.
- `§29 0 known critical exploits under attack_suite_version X` — the required assurance wording,
  sense §B.6.

Quoting these names is permitted. Coining a **new** name containing one of these words is not,
unless the coinage cites the Part B entry that fixes its meaning.

---

## CONFORMANCE GAPS

1. **`InterventionClass` does not exist anywhere in this repository.** `grep -rn
   "InterventionClass\|intervention_class" arena/ tests/ docs/` returns **zero matches**
   (2026-09-08). §6.26 requires every comparison to declare one; §12.4 defines
   `DEAD_UNDECLARED_INTERVENTION`; §26 makes the class determine the fairness contract. Nothing in
   code can currently represent, record, or enforce it. Type: `KNOWN_FACT`. Blocking for HC-V0
   success criterion §40.5 ("truthful intervention classification").
2. **The horizon family is partially implemented under different names.**
   `arena/trajectory/schema.py` (untracked at time of writing) defines
   `Horizon(achieved, verified, reference, solver_actions, reference_actions)`. Mapping to §6.30–§6.34:
   `reference` ≈ `ObservedTraceLength`; `achieved`/`solver_actions` ≈ `EpisodeLength`;
   **`KernelStepCount` is absent**; **`DependencyDepth` is absent**; **`MinimalProofLength` is
   absent** (and §6.34 requires the literal `UNKNOWN` when not independently established). The
   in-repo names are not the manual's names. Type: `KNOWN_FACT`.
3. **`VerifiedTask` does not exist in code.** `grep -rn "VerifiedTask" arena/ tests/` returns zero
   matches; only `VerifiedTrajectory` is implemented. §6.25/§17.1 separate them, and §14.6 makes
   the distinction decide which claims are permitted. Type: `KNOWN_FACT`.
