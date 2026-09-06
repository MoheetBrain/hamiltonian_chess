# HAMILTONIAN ARENA — PERMANENT PROJECT OBJECTIVE

> **THIS DOCUMENT IS THE PERMANENT SCIENTIFIC OBJECTIVE OF HAMILTONIAN ARENA.**
>
> It overrides sprint plans, current benchmarks, implementation convenience, historical HML objectives, temporary agent recommendations, and individual experiment results.
>
> **It may be changed only with explicit authorization from the project owner.**
>
> Individual experiments may freeze stricter temporary rules, but they may not silently redefine the objective below.

---

## 1. Mission

**Hamiltonian Arena exists to discover whether the way mathematics is represented to an artificial intelligence is itself a causal determinant of mathematical capability, and—if it is—to experimentally discover the strongest machine-facing mathematical representation and reasoning workspace that can be found.**

The project does **not** assume that HML is correct.

It does **not** assume that a novel language must beat Structured English, JSON/AST representations, Lean-like states, S-expressions, or future controls.

It does **not** assume that a useful representation effect exists.

The central scientific hypothesis is:

$$
\boxed{
\exists R
\quad\text{such that}\quad
\text{Capability}(M\,|\,R)
>
\text{Capability}(M\,|\,R_{\mathrm{control}})
}
$$

under controlled conditions in which the underlying mathematics, solver, training information, verification rules, tools, and resource budget are appropriately matched.

The long-run engineering objective is to discover a robust representation \(R^\dagger\) that enables AI systems to learn and perform mathematical reasoning more effectively across many mathematical domains, problem structures, reasoning depths, solver architectures, and resource budgets.

---

## 2. The ultimate objective

The eventual system should support an increasingly general mathematical agent capable of:

* representing mathematical objects and states;
* understanding goals and assumptions;
* maintaining long reasoning chains;
* selecting useful next actions;
* decomposing problems into subgoals;
* retrieving definitions, lemmas, and theorems;
* exploring alternative proof/search branches;
* tracking dependencies and obligations;
* identifying failed paths;
* generating conjectures;
* constructing proofs and derivations;
* verifying proposed results;
* learning from successful and failed trajectories;
* transferring strategies to unseen mathematical structures.

The north star is **maximal capability over formalizable mathematics**.

It is **not** literally “solve every mathematical question forever.” Some mathematical decision problems are undecidable, and no fixed formal system can prove every mathematical truth expressible beyond sufficient strength. The project therefore seeks the strongest achievable **general mathematical problem-solving system**, not a logically impossible guarantee of universal solution.

The desired end state is:

$$
\boxed{
\text{representation}
+
\text{libraries}
+
\text{retrieval}
+
\text{search}
+
\text{verification}
+
\text{curriculum}
+
\text{learning}
\rightarrow
\text{increasingly capable mathematical AI}
}
$$

---

# 3. The fundamental separation

Hamiltonian Arena must permanently distinguish the following objects:

$$
\boxed{
(\Sigma,\;P,\;R,\;\tau,\;\pi,\;C,\;D,\;U,\;V,\;B)
}
$$

where:

| Symbol     | Meaning                                                                      |
| ---------- | ---------------------------------------------------------------------------- |
| \(\Sigma\) | canonical mathematical semantics / truth state                               |
| \(P\)      | visibility or projection policy: which true relations are explicitly exposed |
| \(R\)      | structural/model-facing representation of that information                   |
| \(\tau\)   | tokenizer / model input encoding                                             |
| \(\pi\)    | Solver policy/model                                                          |
| \(C\)      | reasoning/search controller                                                  |
| \(D\)      | mathematical task/environment distribution                                   |
| \(U\)      | available mathematical libraries/tools                                       |
| \(V\)      | verifier/oracle                                                              |
| \(B\)      | training/inference/compute budget                                            |

These variables must **not** initially be optimized simultaneously.

Otherwise an observed gain cannot be causally attributed.

The project therefore proceeds through controlled games in which one class of variable is changed while the others are frozen or matched.

---

# 4. Layer 0 — canonical mathematics

At the bottom of Hamiltonian Arena is a representation-independent mathematical substrate.

A canonical state may contain:

```text
objects
terms
types
definitions
assumptions
facts
propositions
goals
bindings
scope
dependencies
preconditions
obligations
evidence
open branches
legal actions
state transitions
```

Conceptually:

$$
S_t
\xrightarrow{a_t}
S_{t+1}.
$$

Candidate languages do not define whether this transition is mathematically valid.

The verifier does.

### Critical refinement

The canonical substrate is **immutable during a scientific experiment**, but it is **not assumed to be the eternally complete ontology of all mathematics**.

As Hamiltonian Arena expands into new mathematics, the canonical substrate may itself need extensions.

Such extensions require:

```text
new canonical version
new hashes
new verification
new assurance
explicit migration
```

and invalidate experiments that depended on the old semantic universe where appropriate.

Thus:

$$
\boxed{\text{Truth is frozen inside an experiment; the substrate is versioned between experiments.}}
$$

This allows the project to grow without letting a candidate language change the rules during a tournament.

---

# 5. Game R — representation search

This is the **first and scientifically cleanest game**.

During Game R freeze:

$$
\Sigma,\;P,\;\tau,\;\pi,\;C,\;D,\;U,\;V,\;B.
$$

Only \(R\) changes.

Every candidate therefore receives the **same visible mathematical information**.

It may alter:

```text
grammar
syntax
tree/DAG/linear organization
field structure
binder representation
scope representation
identifier system
dependency locality
type placement
role labels
redundancy
canonical ordering
surface morphology
compression
serialization
```

but may not add a derived fact that another representation does not receive.

The causal question is:

$$
\boxed{
\text{Does organizing exactly the same mathematical information differently
change AI reasoning or learning?}
}
$$

This is the foundational representation hypothesis.

---

# 6. Game P — mathematical projection / visibility search

Only after Game R can be measured cleanly should Hamiltonian Arena separately optimize \(P\).

Game P asks:

> **Which mathematically true relations should an AI be shown explicitly rather than required to reconstruct repeatedly?**

Examples include:

```text
dependency edges
binder → use links
action → target-goal links
premise → action links
open obligations
definedness/preconditions
state deltas
proof/evidence edges
branch status
failed-action history
```

A candidate projection may expose only information that can be **deterministically derived from canonical mathematics**.

For example:

```text
canonical state implies B depends on A
                    ↓
projection may render:
DEPENDS_ON(B,A)
```

This is allowed.

The projection may **not** invent:

```text
unverified intermediate inference
hidden answer
oracle state
solution label
future proof step
```

Game P must explicitly measure the cost of additional information:

$$
\text{benefit of explicit relation}
\quad\text{vs}\quad
\text{tokens / redundancy / compute}.
$$

This game therefore discovers the best **mathematical perceptual interface**, not merely notation.

HML_V3's prior finding that most of its search axes changed typography while leaving the represented relations essentially constant is precisely why Game P must exist separately.

---

# 7. Game C — reasoning and search controller

Representation must also remain distinct from the algorithm operating on it.

Game C freezes a sufficiently validated representation and varies reasoning/search machinery such as:

```text
greedy next-action choice
beam search
tree search
backtracking
best-first search
verifier-guided retries
subgoal decomposition
retrieval policy
branch management
proof-state compression
```

The causal question becomes:

$$
\boxed{
\text{Given a fixed mathematical representation, which reasoning controller
uses it most effectively?}
}
$$

A language must never receive credit for an advantage caused entirely by a better search algorithm.

---

# 8. Game T — adaptive mathematical curriculum

A static task distribution will eventually saturate.

This has already occurred in the Arena's own matched-training experiments, and it is exactly the class of problem adaptive-environment work targets.

EvoEnv shows that changing validated environments can preserve useful learning signal when static distributions saturate, while retaining a stable executable reward source.  SPADE similarly targets environments at the learner's capability frontier rather than simply maximizing raw difficulty.  R-Zero motivates uncertainty near the solver's capability frontier, while also illustrating the risks of prolonged self-generated pseudo-labelled feedback. 

Game T therefore eventually chooses or generates **verified mathematical environments near the solver's learning frontier**.

It optimizes neither raw difficulty nor novelty alone.

Useful environments should be:

```text
mathematically valid
independently verifiable
solvable in principle
nontrivial for the current Solver
structurally diverse
informative for learning
```

Where possible, mathematical tasks should become reusable executable environments:

```text
sample(seed)
oracle(instance)
render(instance)
verify(response)
```

so that infinitely or very many fresh instances can be generated while the reward mechanism remains fixed after admission.

This exploits **stable solve–verify asymmetry**: solving may remain difficult even when checking a candidate solution is cheap and reliable. 

---

# 9. Game J — joint co-evolution

Only after the effects of \(R\), \(P\), \(C\), and \(T\) have been studied separately should Hamiltonian Arena investigate their interactions.

Ultimately:

$$
F = F(P,R,C,T,\pi).
$$

There may be no globally optimal representation independent of the problems and search algorithms it supports.

MAESTRO shows that environment and co-player interactions can contain high-regret combinations that are invisible when the dimensions are optimized independently.  ATLAS likewise finds that independently sampled task–level combinations can frequently be unsolvable and that joint curation can become essential. 

Therefore a mature Arena may eventually co-evolve:

```text
representation
projection
curriculum
solver/search policy
```

but **joint evolution is a later phase**, because it sacrifices causal identifiability in exchange for total system performance.

---

# 10. The roles

Hamiltonian Arena freezes **roles and authority boundaries**, not a fixed number of AIs.

The same underlying model may occupy different roles in separate contexts. Different models may also instantiate the same role.

SPADE demonstrates that a single policy can perform environment-designer and solver roles; the relevant distinction is the role contract, not whether the weights physically differ. 

The permanent logical roles are:

### Architect

Proposes candidate changes.

May inspect:

```text
development metrics
candidate genomes
failure memory
aggregate lineage information
measurement weaknesses
resource budget
```

May not inspect:

```text
sealed answers
hidden promotion outcomes
verifier internals that enable exploits
```

The Architect proposes hypotheses.

It never approves its own hypothesis.

### Builder

Transforms a typed proposal into an executable candidate.

Where possible this is deterministic software rather than an AI decision-maker.

### Solver

Attempts mathematical reasoning using the candidate representation.

Matched comparisons use the same Solver checkpoint or identical cloned checkpoints.

The Solver never sees the mathematical oracle.

### Experimentalist

Determines whether a proposed measurement actually measures the intended mathematical capability.

Before fitness can exist, the instrument must pass:

```text
positive controls
relation-destroyed negative controls
counterfactual tests
position/order invariance
shortcut audits
ceiling/floor analysis
response-validity analysis
```

A broken instrument produces:

```text
VOID / INSTRUMENT_INVALID
```

not a language ranking.

### Refuter

Attempts to break representations and reasoning protocols.

It may use deterministic and AI-assisted attacks.

Every verified exploit becomes permanent failure memory.

### Curriculum Designer

Activated only under the appropriate experimental phase.

Selects or proposes informative mathematical environments without exposing sealed evaluation data.

### League Manager

Controls:

```text
population
archive
lineage
Hall of Fame
successive halving
promotion
retirement
resource allocation
```

It cannot override semantic failure.

### Verifier

The highest authority over mathematical correctness.

It should be deterministic or grounded in independently trusted systems wherever possible.

The verifier is **not a strategic player**.

---

# 11. The Arena is not one zero-sum game

The chess metaphor is a visualization, not the mathematical definition of the system.

Hamiltonian Arena contains different strategic relationships:

```text
Architect ↔ Refuter
    adversarial robustness

Architect ↔ Solver
    largely cooperative

Curriculum ↔ Solver
    constrained adversarial / teacher-student

Candidate ↔ Candidate
    evolutionary competition

Solver ↔ mathematical problem
    search/planning

Verifier
    non-strategic authority
```

SPIRAL's zero-sum self-play results are relevant later for developing solver reasoning skills, because continually improving opponents can generate useful strategic pressure and transferable reasoning. 

But representation evolution itself should **not** be forced into an artificial two-player zero-sum formulation.

---

# 12. Candidate search

Candidate representations form a population rather than a single hill-climbing chain.

The search should retain:

```text
strong candidates
structurally distinct candidates
historical champions
useful specialist niches
```

through a Pareto / quality-diversity archive.

MORTAR supports the principle that a mechanism's utility has to be judged through the complete systems it enables and that diversity can be useful during evolution. 

Early experiments should prefer controlled mutations because they provide causal information.

However:

$$
\boxed{\text{local mutation is conditional, not dogma.}}
$$

ACCEL gains efficiency from editing strong neighboring environments under an explicit local-smoothness assumption. 

Hamiltonian Arena must empirically measure whether:

$$
d(R_i,R_j)\text{ small}
\Rightarrow
F(R_i)\approx F(R_j).
$$

If the landscape is locally smooth:

```text
use parent → small child mutations aggressively.
```

If it is rugged:

```text
use larger LLM-designed mechanisms,
quality-diversity,
architectural jumps,
and eventually recombination.
```

Do not spend thousands of generations applying the wrong search operator.

---

# 13. What counts as a fair representation comparison

During Game R, competing representations must satisfy three separate forms of parity:

### Semantic parity

They represent the same underlying mathematical state.

### Visible-information parity

No representation receives solution-relevant information unavailable to another.

### Experimental parity

The following are matched or deliberately controlled:

```text
Solver checkpoint
task identity
action alternatives
response interface
tokenizer
available tools
search algorithm
training procedure
evaluation procedure
hidden splits
```

Candidate-specific output syntax should not contaminate an input-representation experiment.

Prefer a universal response such as:

```text
ACTION_03
```

for early causal tests.

Generation of the representation itself is a separate capability that can later be evaluated.

---

# 14. Matched learning

Pretraining creates familiarity bias.

Therefore zero-shot fitness is only preliminary evidence.

For serious candidates:

```text
same base checkpoint
same canonical mathematics
same optimizer policy
same random-seed protocol
same evaluation tasks
different representation
```

must be used.

Two resource regimes should eventually be reported:

### Example-matched

Same number of mathematical examples.

This measures real-world advantage including representational compactness.

### Token/compute-matched

Approximately matched training tokens / optimization compute.

This helps distinguish:

```text
"representation is easier"
```

from:

```text
"representation simply used fewer tokens."
```

The principal causal object is the **learning curve**, not merely final ceiling performance.

---

# 15. Fitness

No single convenience score defines mathematical representation quality.

First:

$$
\boxed{\text{critical semantic failure} \Rightarrow \text{elimination}}
$$

Then maintain a fitness vector approximately containing:

$$
F(R)=
(
Q_{\mathrm{math}},
Q_{\mathrm{OOD}},
L_{\mathrm{sample}},
S_{\mathrm{search}},
E_{\mathrm{invalid}},
C_{\mathrm{token}},
C_{\mathrm{compute}},
R_{\mathrm{robust}}
).
$$

These correspond approximately to:

```text
verified mathematical success
structural OOD generalization
learning/sample efficiency
search efficiency
invalid-action suppression
token cost
compute/latency cost
robustness across perturbations/seeds/models
```

During search use Pareto/quality-diversity selection.

When an actual deployment champion must be selected, use a **predeclared lexicographic hierarchy**, not retrospective weights.

Default hierarchy:

$$
\boxed{
\text{soundness}
>
\text{verified mathematical capability}
>
\text{OOD/generalization}
>
\text{learnability}
>
\text{search reliability}
>
\text{efficiency}
}
$$

Efficiency may choose between otherwise comparable systems.

It may not compensate for mathematical unreliability.

---

# 16. Naming winners

Do not prematurely call the current leaderboard leader \(R^*\).

Use explicit evidence levels:

```text
VALID_CANDIDATE
    survives semantic assurance

FITNESS_CANDIDATE
    demonstrates a reproducible frozen-model effect

LEARNABILITY_CANDIDATE
    survives matched adaptation

ROBUST_CANDIDATE
    survives hidden/OOD + multiple seeds

RSTAR_0_1
    survives strong controls and multiple meaningfully distinct Solver families
```

The first scientifically defensible optimization target is conditional:

$$
\boxed{
R^*_{M,D,\tau,U,C,B}
\in
\arg\max_R
F(R\mid M,D,\tau,U,C,B)
}
$$

where the optimum is relative to a particular model, mathematical distribution, tokenizer, tools, search controller, and budget.

The broader target is a **robust representation** \(R^\dagger\):

$$
\boxed{
R^\dagger
=
\arg\max_R
\mathbb E_{e\sim\mathcal E}
[F(R\mid e)]
}
$$

over a preregistered collection of meaningful solver families, mathematical domains, structural regimes, and budgets.

`RSTAR_0_1` means:

> the strongest robust representation discovered under the current declared experimental universe.

It does **not** mean:

> mathematically proven globally optimal language for every possible AI.

---

# 17. Verification and reward

Hamiltonian Arena should aggressively exploit tasks where:

$$
\boxed{\text{solve cost} \gg \text{verify cost}.}
$$

Examples can include:

```text
formal proof checking
SAT/SMT assignments
symbolic equivalence
constructed combinatorial witnesses
program execution
exact arithmetic
finite exhaustive universes
```

Candidate mathematical environments should be admitted only after staged validation.

Once admitted, their oracle should be frozen executable behavior rather than an answer generated afresh by the same policy being trained.

This is one of the strongest lessons from EvoEnv. 

LLM self-judgement may generate hypotheses.

It must not become the ultimate source of mathematical reward when a stronger executable verifier exists.

---

# 18. Curriculum objective

Do not permanently commit to any one curriculum proxy such as:

```text
regret
50% uncertainty
p(1-p)
parameter-update norm
interestingness
```

as "the" objective.

The literature does not justify that certainty.

SPADE uses hint-based regret.  R-Zero explicitly targets solver uncertainty around 50%.  PACE argues that common indirect proxies can be noisy or biased and motivates a parameter-change alternative. 

Hamiltonian Arena should treat curriculum metrics as competing hypotheses.

The true criterion is downstream:

$$
\boxed{
\text{Does training on these environments improve fresh,
verified mathematical capability?}
}
$$

Proxy metrics survive only when they predict that.

---

# 19. Historical memory

Hamiltonian Arena must preserve:

```text
previous champions
failed candidates
confirmed exploits
invalid benchmarks
saturated instruments
known shortcuts
historical counterexamples
```

as permanent machine-readable memory.

The system should not repeatedly rediscover the same failure.

Likewise, population history prevents non-transitive regressions and provides a Hall of Fame against which new candidates can be checked.

---

# 20. Success and falsification

The project must be capable of succeeding **without discovering a custom language**.

A valid outcome is:

```text
Strong generic representations remain unbeatable
within the declared search, models, tasks and compute.
```

Another valid outcome is:

```text
Representation matters, but local mutation is not searchable.
```

Another is:

```text
Projection matters much more than syntax.
```

Another is:

```text
Representation advantage is strongly model-specific.
```

These are scientific answers.

The project must never respond to a weak result by silently:

```text
changing hidden tests
changing thresholds
changing the mathematical information
increasing one candidate's teaching
changing the verifier
searching indefinitely until something "wins"
```

Every experiment has:

```text
budget
stopping condition
practical effect threshold
frozen protocol
allowed decision outcomes
```

before scientific evaluation begins.

---

# 21. What Hamiltonian Arena must never become

Hamiltonian Arena is **not** primarily:

```text
a prettier HML project
a compression contest
a parser project
a theorem-prover wrapper
a benchmark optimization project
a dashboard
an agent-count competition
a way to prove a predetermined language wins
```

Infrastructure exists to resolve scientific uncertainty.

Scientific uncertainty does not exist to justify infrastructure.

---

# 22. Post-R* mathematical training system

If `RSTAR_0_1` is earned, the project changes phase.

The representation becomes a fixed machine-facing mathematical workspace.

Then:

```text
verified mathematical environments
            ↓
      canonical state
            ↓
          RSTAR
            ↓
          Solver
       /     |      \
 retrieval search conjecture
       \     |      /
          action
            ↓
         verifier
       /          \
    valid        invalid
      │             │
      ▼             ▼
 next state     failure data
      │             │
      └──────┬──────┘
             ▼
      training trajectory
             │
             ▼
       improve Solver
             │
             ↺
```

Training data should preserve more than final proofs:

```text
S_t
chosen action
target
arguments
warrant
preconditions
obligations
S_t+1
verification
failed alternatives
counterexamples
repairs
subgoals
search decisions
eventual outcome
```

Scale progressively:

$$
10K
\rightarrow
100K
\rightarrow
1M+
$$

only when capability scaling justifies the next stage.

At this later stage, concepts from adaptive environment synthesis and genuine self-play become much more directly applicable: static distributions should give way to verified environments that continue moving the learning frontier as the Solver improves. EvoEnv directly reports this pattern, and SPIRAL provides evidence that adaptive multi-turn game experience can transfer to broader reasoning skills.  

---

# 23. The permanent project loop

The mature Hamiltonian Arena is:

```text
                    CANONICAL MATHEMATICS
                             │
                             ▼
                     EXPERIMENTAL PHASE
                             │
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
      representation     projection        controller
           │                 │                  │
           └─────────────────┼──────────────────┘
                             ▼
                         CANDIDATE
                             │
                             ▼
                    SEMANTIC ASSURANCE
                             │
                        fail ├──────► DEAD
                             │
                             ▼
                         REFUTER
                             │
                        fail ├──────► DEAD
                             │
                             ▼
                    QUALIFIED SOLVER
                             │
                             ▼
                    MATCHED COMPETITION
                             │
                             ▼
                     HIDDEN / OOD TEST
                             │
                             ▼
                      MATCHED LEARNING
                             │
                             ▼
                      LEAGUE / ARCHIVE
                         /          \
                     retain         kill
                       │
                       ▼
                 new hypotheses
                       │
                       └───────────────↺
```

After a robust champion emerges:

```text
RSTAR
   ↓
verified environments
   ↓
Solver training
   ↓
adaptive curriculum
   ↓
stronger Solver
   ↓
harder mathematics
   ↓
verified experience
   └────────────────────────↺
```

---

# 24. Permanent North Star

If every other document becomes confusing, return to this:

> **Hamiltonian Arena exists to determine, by controlled evolutionary experimentation, which externally represented mathematical information, structure, and reasoning interface allow otherwise matched artificial intelligence systems to learn and perform verified mathematics most effectively; to separate those effects from solver, search, tokenizer, curriculum, and compute confounds; and, if reproducible advantages exist, to combine the strongest discovered representation with verified mathematical environments, search, retrieval, and iterative training to build increasingly general mathematical problem-solving systems.**

Or maximally compressed:

$$
\boxed{
\textbf{Freeze mathematical truth. Vary one cognitive interface at a time. Measure what makes the AI a better mathematician. Keep only what survives verification, replication, and hidden tests. Then train on it at scale.}
}
$$

---

