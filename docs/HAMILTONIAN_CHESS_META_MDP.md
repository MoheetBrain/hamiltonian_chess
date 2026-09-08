# Hamiltonian Chess — the two nested games

Companion to `docs/HAMILTONIAN_CHESS_META_GOAL.md`. This document defines the architecture
formally enough to implement, and marks precisely which pieces exist in the repository today and
which are missing.

The system is **two nested processes**. The inner one does mathematics. The outer one designs the
language the inner one thinks in. Confusing them is the error this document exists to prevent.

---

## 1. Inner game — mathematical reasoning

An MDP-like environment, parameterised by a language `L`:

```
M_L = (S, A, T_K, r, Ω_L)
```

| Symbol | Meaning | Owner |
|---|---|---|
| `S` | mathematical reasoning state | the formal backend |
| `A` | legal mathematical / search actions | the formal backend |
| `T_K` | transition, executed or checked by the **truth kernel** | verifier |
| `r` | verifier-grounded reward | verifier |
| `Ω_L` | **observation function: how the state is rendered through language `L`** | the language genome |

A state may carry: facts and context, assumptions, goals and subgoals, obligations, dependencies,
evidence and provenance, open branches, failed paths, and search history. **Which of these are
explicitly represented is a gene, not a constant** — that is layer B of the meta-goal, and whether
making each explicit helps is the thing being discovered.

The loop:

```
o_t = Ω_L(S_t)          the Solver sees the state ONLY through the language
a_t ~ π(· | o_t)        the Solver acts
S_t --a_t--> S_{t+1}    the TRUTH KERNEL executes or checks the transition
r_t = r(S_t, a_t, S_{t+1})
```

**The language does not define mathematical truth.** `Ω_L` is an observation function and nothing
more. `T_K` and `r` are independent of `L` — this is the formal statement of the meta-goal's layer
A/B boundary, and it is what makes a language comparison causally interpretable at all: two
languages are two observation functions over one identical process.

### What exists today

| Piece | Status | Evidence |
|---|---|---|
| `Ω_L` | **EXISTS** | `arena/model_view/compiler.py` + `arena/languages/phenotype.py`; genome-driven, round-trip validated by `ModelViewCompiler.validate` |
| `T_K` (single step, synthetic) | **EXISTS** | `arena/verifier/native.py`, per-generator truth oracles |
| `S` with persistent multi-step evolution | **MISSING — verified 2026-09-08** | The schema *supports* multi-step (`CanonicalTrajectory.transitions: tuple[CanonicalTransition, ...]`, `arena/canonical/schema.py:322`) but **no multi-step trajectory is ever constructed**. The only `CanonicalTrajectory(...)` call site in the entire package is `arena/tasks/generators/world_v0.py:507`, and it passes a **one-element tuple** `(transition,)`. Every environment in `arena/environments/` is a single-step, two-option probe. **Maximum horizon anywhere in the repository: 1.** The type exists; the data does not. |
| `A` beyond "choose option A or B" | **MISSING** | the action space is a 2-way choice; there is no action *protocol* to vary |
| `r` beyond binary correctness | **MISSING** | — |

**The inner game is the project's largest hole.** Its observation function is mature and its state
space is one step deep. Nothing currently in the repository can measure a horizon effect, because
nothing has a horizon.

---

## 2. Outer game — language evolution

State:

```
X_t = ( language population,
        archive,
        mutation history,
        estimated fitness,
        curriculum / evaluation state,
        compute budget )
```

An **Architect** action is a four-tuple:

```
a = ( choose parent,
      choose mutation operator,
      choose mutation parameters,
      choose evaluation budget )
```

Transition:

```
mutate language
      ↓
compile / SEMANTIC GATE          ← truth preservation; non-compensatory
      ↓
matched Solver evaluation / adaptation
      ↓
mathematical episodes in M_L     ← the inner game runs here
      ↓
verifier
      ↓
fitness vector
      ↓
population / archive update
```

**This is the actual Hamiltonian Chess game.** Everything the programme has built until now lives
inside one box of it: "matched Solver evaluation".

### What exists today

| Piece | Status | Evidence |
|---|---|---|
| Language population + genome | **EXISTS, and there are TWO separate defects — both verified 2026-09-08** | (1) **The eight registered seed codecs are genome-blind.** `arena/languages/registry.py` holds pre-instantiated *singletons* (`JsonAstLanguage`, `StructuredEnglishLanguage`, …), not classes taking a genome, so they cannot read one by construction: `grep -rn "self\.genome" arena/languages/*/__init__.py` returns nothing, and mutating each of the 14 gene families to every legal value (**44 one-gene variants**) changes **0 of 44** rendered outputs. (2) **The genome-driven path works but its gene→byte map is narrow.** `GenomePhenotypeLanguage` changes the bytes on **24 of 44** variants and loses no round-trip — yet two of the eight seeds rendered through it still share **98.6%** of their state bytes (`docs/PHASE8_SALVAGE_HANDOFF.md` §3.2). Both defects point the same way: **the genome must be able to change the payload structure, not only the skin.** |
| Mutation operators | **EXISTS** | `arena/genome/mutation.py`, `crossover.py` |
| Semantic gate | **EXISTS AND WORKS — verified 2026-09-08** | `ModelViewCompiler.validate` + `arena/assurance/`. Measured directly: all **8/8** seed surfaces round-trip a precondition state losslessly (`recover_canonical_state().mathematical_hash` equals the source state's), and a deliberately tampered renderer that drops one `holds(...)` assumption — which would change which answer is licensed, i.e. change truth — is **refused** with "model-view surface does not recover the canonical mathematical state". This is the enforcement mechanism for the meta-goal's layer A/B boundary, and it is real today. It still needs to be wired as the loop's single fail-closed gate. |
| Matched evaluation | **EXISTS** | `arena/experiments/game_r_formal_v1.py` — parity, cache identity, budget, paired statistics |
| Answer-leakage gate | **EXISTS** | `arena/experiments/rendered_prompt_adversary.py` |
| Fitness vector | **MISSING** | `arena/fitness/` is single-step accuracy oriented; see `docs/LONG_HORIZON_FITNESS_V0.md` |
| Archive / population update | **PARTIAL** | `arena/league/registry.py`, `arena/fitness/pareto.py` |
| **The loop itself** | **MISSING** | nothing iterates generations |
| Fitness memory | **MISSING** | `docs/LANGUAGE_FITNESS_MEMORY.md` |
| Surrogate / learned Architect | **MISSING, and deferred** | see §5 |

---

## 3. How the two games couple

Exactly one quantity crosses the boundary: **the fitness vector**, computed from verified inner-game
outcomes and handed to the outer game. Nothing else may.

Three couplings must be prevented, and each has a named mechanism:

| Leak | Mechanism |
|---|---|
| A language changes what is true | Truth kernel is outside `Ω_L`; semantic gate checks recovery against backend state identity |
| A language exposes the answer | Rendered-prompt adversary on the exact bytes; non-compensatory |
| The outer loop overfits its own evaluation set | Selection and evaluation pools are disjoint; promotion uses fresh data; corrections for the number of candidates in a generation |

**The unit of analysis is the trajectory, not the step.** Steps within a trajectory are dependent;
treating them as independent is precisely the "granularity substitution" the V7 audit named as the
programme's recurring error. Every clustered statistic in the outer loop clusters on the
trajectory (or the problem), never on the step.

---

## 4. Where Game R sits

Game R is the **causal assay inside one outer-loop transition**. When mutation μ produces child
`L'` from parent `L` and the cheap fitness signal suggests an improvement, the assay answers
whether μ caused it:

- identical trajectories, identical Solver, identical decoding, identical envelope;
- only `Ω_L` differs;
- paired outcomes, clustered by trajectory;
- exact McNemar plus a clustered bootstrap interval, Holm-corrected across the generation's
  comparisons;
- a practical-effect threshold declared before the comparison, and an equivalence region so that
  "no significant difference" can be distinguished from "no difference".

The machinery for all of this exists and is tested (`game_r_formal_v1.compare_arms`,
`arena/evaluation/landscape.py`, `arena/experiments/precondition_power.py`). What changes is the
*substrate* it runs on: verified trajectories rather than two-option probes.

**The micro-probe qualification rules are not the evolutionary reward.** A mechanism failing V5/V7
gates says something about that mechanism as an instrument, not about the language population.

---

## 5. Why not reinforcement learning for the Architect

The outer game has expensive delayed reward, an enormous structured action space, noisy fitness
and partial observability. Training a policy on it now would be fitting a high-variance estimator
to a handful of noisy episodes.

The order is therefore: **evolutionary population search with quality-diversity, structured
mutation, successive halving and an archive** → accumulate a fitness history → **fit a surrogate**
`predicted ΔJ(parent, mutation, environment)` → *only then* consider a learned Architect. The
fitness-memory schema is designed now so that the data exists when the time comes.

---

## 6. The V0 slice

`HAMILTONIAN_CHESS_V0` is scoped for **end-to-end executability, not discovery**:

- 3–4 existing seed languages as the population;
- one controlled mutation operator;
- one small verified trajectory arena;
- one cheap evaluation tier;
- one archive update;
- one generation, four candidates.

Success is **the loop runs, deterministically, with provenance, and records a fitness vector**.
Its winner is **not** a scientific result and must not be described as one.

---

## 7. Open questions this architecture does not yet answer

1. **What is the trajectory world?** ~~Determined by the data audit, not by preference.~~
   **RESOLVED 2026-09-08 by measurement** (`docs/VERIFIED_TRAJECTORY_ARENA_V0.md`): **live Lean
   replay**. The exact paths, independently re-verified — record them here because two prior audits
   reached opposite conclusions by confusing two checkouts, and because the corpus is **not** under
   `~/Documents/ChatGPT`:

   | Asset | Path |
   |---|---|
   | Built mathlib4 (18 GB, **5,680** `.olean`) | `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4` |
   | Lean toolchain pinned by that checkout | `lean-toolchain` = `leanprover/lean4:v4.10.0-rc1`; `env -C $MB /Users/moheet/.elan/bin/lean --version` → **4.10.0-rc1** (the bare binary reports 4.33.1 — elan resolves per directory, so **always invoke via `env -C $MB`**) |
   | REPL | `Lean4Repl.lean` present in that checkout, compiled |
   | Problems | `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json` (373 MB, CC BY 2.0) |

   Re-verified independently on `random/train.json`: **118,517** records, **59,557** with
   `traced_tactics`, **250,814** steps; horizon **≥5: 15,275 · ≥10: 5,892 · ≥20: 1,605 · max 128**;
   per-step keys `tactic`, `state_before`, `state_after`, `annotated_tactic`.
   **`random/{val,test}.json` and `novel_premises/{val,test}.json` sit in the same tree and are
   SEALED — they were not opened and must not be.**

   The alternative source (`HML_V3/.../lean_runtime_v2_full.canonical.part-*`) is **unusable for
   horizon**: 1,150 transitions over 1,085 theorems, mean horizon 1.06, and **0 of 65 adjacent
   pairs chain** — it is an elaboration-time capture, exactly as its own caveats say.
2. **Can the observation function survive a real backend state?** The canonical schema reportedly
   maps 0 of 368 real Lean states losslessly; a backend-native envelope is permitted, but then
   `Ω_L` must be defined over that envelope, and the language layer must be able to render it.
   This is the single largest engineering risk in the reset.
3. **Is the action space rich enough to matter?** If the Solver's only action is "pick one of k",
   the action-granularity gene is inert and a large part of the hypothesised long-horizon effect
   cannot appear.
4. **How much does a mutation cost to evaluate?** At measured local rates (~15–36 s per call at
   12–18k prompt tokens), a generation's budget is a hard constraint on population size, and the
   multi-fidelity ladder is what makes it feasible.
