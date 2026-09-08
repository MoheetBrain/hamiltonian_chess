# Hamiltonian Chess — Meta-Goal

> **This document sits ABOVE `GOAL.md` in the project hierarchy.**
>
> `GOAL.md` is **not** superseded and **not** edited. It remains the scientific constitution for
> controlled local Game-R experiments, and every discipline it mandates — matched comparisons,
> frozen semantics inside an assay, matched Solver, matched visible information, deterministic
> verification, shortcut attacks, provenance, cache discipline, preregistration, parent-vs-child
> comparison — remains binding wherever an assay is run.
>
> What changes is what those assays are *for*.
>
> Established 2026-09-08 by owner directive. Historical results are preserved and are not
> reinterpreted by this document.

---

## 1. The mission

**Hamiltonian Chess exists to build an open-ended experimental system in which artificial agents
discover machine-facing mathematical languages that improve verified long-horizon mathematical
reasoning, learning, search and generalisation, relative to English and existing human-designed
formal languages.**

The system is:

```
        VERIFIED MATHEMATICAL WORLD
                    +
            LANGUAGE POPULATION
                    +
              SOLVER AGENTS
                    +
      LANGUAGE-DESIGN ARCHITECT
                    +
                 VERIFIER
                    +
                 FITNESS
                    ↓
        REPEATED LANGUAGE EVOLUTION
                    ↓
       BEST LANGUAGE FOUND SO FAR
```

"Best" means **the strongest robust language found under declared models, mathematics
distributions and compute budgets**. It does not mean globally optimal, and no result may claim
otherwise.

## 2. What the project is not

It is **not** "prove HML beats JSON".
It is **not** "prove representation R matters on a 24-item micro-benchmark".
It is **not** the design of a new mathematical DSL by hand.

Those are measurement problems, or products, *inside* the larger system. The object of study is
the **discovery process**, not any particular language it finds.

The project must be capable of succeeding without discovering a custom language. "Strong generic
representations, including English, remain unbeaten within the declared search, models, tasks and
compute" is a valid and publishable outcome. English is not an enemy to be defeated; it is the
**incumbent organism**, and a candidate earns status only by beating strong incumbents.

## 3. The demotion of Game R — stated precisely

**Game R is now the local causal fitness assay.** Its role is to answer one question:

> Given a parent language and a child produced by mutation μ, did μ actually help?

That is a matched, paired, parity-controlled comparison — exactly what the existing machinery
does well, and exactly what `GOAL.md` §5 and §13 specify. It is *not* the top-level mission, and
its qualification rules for micro-probes must **never** become the global evolutionary reward.

Two consequences follow, and both are binding:

1. **Nothing in the V1–V7 record is retracted.** `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED`,
   `RSTAR_NOT_IDENTIFIED`, `GAME_R_INSTRUMENT_NOT_QUALIFIED` and `TRAINING_LANGUAGE_V0_BASELINE`
   all stand. The forensic audit's findings stand.
2. **The failure of a micro-probe instrument is no longer a blocker on the project.** It is a
   statement about one assay. The programme spent seven phases asking whether the ruler was good
   enough; the ruler is now mounted on a machine, and the machine's output is what is measured.

## 4. The four layers, and which may evolve

The single hardest constraint in this project is that **a candidate must never win by changing
mathematical truth**. The layers are therefore separated, and the boundary between B and A is the
one that must never move.

| Layer | Content | Evolvable? |
|---|---|---|
| **A. Mathematical truth kernel** | What is true; what transitions are legal; what constitutes a proof. Owned by the verifier and the formal backend (Lean/mathlib, SymPy, Z3). | **NEVER.** Fixed and verifier-governed. |
| **B. Reasoning ontology** | Which concepts are first-class and explicitly represented: fact, assumption, goal, subgoal, obligation, dependency, evidence, provenance, warrant, branch, failure, counterexample, conjecture, epistemic state. | **Yes**, subject to truth preservation. Whether making a concept explicit *helps* is exactly what the system is meant to discover. |
| **C. Language semantics** | What the language can say, and what it leaves implicit or derivable. | **Yes, if truth-preserving.** A language may omit a derivable relation or make one explicit; it may not invent an unverified relation, expose an oracle, or alter a truth value. |
| **D. Surface, grammar, morphology, serialisation** | Concrete syntax, lexicon, binding notation, ordering, compression, encoding. | **Yes**, freely. |

**The invariant.** For every state `S` and every language `L`, rendering through `L` and recovering
must reproduce the backend's own state identity. A gene may change what is *shown* and how; it may
never change what is *true*. This is checked by a mechanical semantic gate before any candidate is
evaluated, and a candidate that fails it is eliminated — never traded off against performance.

**The boundary that needs care.** Layer C's freedom is real: a language that makes a dependency
edge explicit is showing something derivable from the truth kernel, which is legitimate and is
`GOAL.md`'s Game P. A language that shows the *answer* is cheating. The line is: **a candidate may
expose only what is deterministically derivable from the canonical mathematics, and never the
solution label, a future proof step, an oracle value, or an unverified inference.** Two mechanisms
enforce it: the semantic gate above, and the rendered-prompt adversary
(`arena/experiments/rendered_prompt_adversary.py`), which attacks the exact bytes a Solver
receives and is non-compensatory.

## 5. Why long horizon is the central quantity

The interesting scientific claim is not "representation changes accuracy by a few points on a
one-step multiple-choice question". That is close to established in the prompt-format literature,
and the project's own history shows how fragile such a measurement is at small n.

The claim worth testing is:

> **Language advantage grows as the reasoning horizon grows.**

A representation that keeps a long derivation legible, keeps dependencies locatable, makes an
obligation impossible to forget, and makes a failed branch cheap to abandon should matter *more*
at twenty steps than at one. If that is true it is a substantial finding about machine-facing
mathematical cognition. If it is false — if the advantage is flat or shrinks — that is also a real
result and must be reported as such.

### 5.1 A correction this document must carry (prior-art audit, 2026-09-08)

The claim as stated above is **partly a tautology, and its truth is metric-dependent.**
`docs/HAMILTONIAN_PRIOR_ART_BOUNDARY.md` establishes three separate propositions that the slogan
silently conflates:

1. **Representation shifts per-step accuracy.** Already established, repeatedly and at large
   effect sizes. Not available as a contribution.
2. **A per-step edge compounds over a horizon.** Also established, and under independent per-step
   errors it is simply arithmetic: `p^n` versus `q^n`. Publishing it would be publishing
   exponentiation.
3. **A representation × horizon *interaction* that is not accounted for by compounding.** This is
   the actual seam. The literature is cleanly bipartite — work that varies representation holds
   depth fixed; work that varies depth holds representation fixed — and nobody crosses them.

**The trap, stated explicitly so no one falls into it later.** With `p > q`, the absolute
accuracy gap `p^n − q^n` is **unimodal in `n`**: it rises, peaks, and then collapses toward zero as
both terms go to zero. So "the gap widens with horizon" is *true* for horizon-at-fixed-success-rate
and for log-odds, and *false* for absolute accuracy difference at large fixed `n`. **The metric
must be preregistered before any horizon claim is made**, and a result that only appears under one
undeclared metric choice is not a result.

**Verified numerically, 2026-09-08.** Take a parent per-step hazard of 0.870 and a child of 0.905 —
a *constant* +3.5-point edge, with **zero** representation × horizon interaction by construction:

| horizon `H` | 1 | 5 | 10 | 20 | 40 | 80 |
|---|---|---|---|---|---|---|
| child `p^H` | 0.9050 | 0.6071 | 0.3685 | 0.1358 | 0.0184 | 0.0003 |
| parent `q^H` | 0.8700 | 0.4984 | 0.2484 | 0.0617 | 0.0038 | 0.0000 |
| **absolute gap** | 0.0350 | 0.1087 | **0.1201** | 0.0741 | 0.0146 | 0.0003 |
| log-odds gap | 0.353 | 0.441 | 0.569 | 0.871 | 1.593 | 3.156 |

The absolute gap **peaks at `H = 8` and decays to zero**. Comparing `H = 1` to `H = 20` gives
**+0.039** — "advantage grows with horizon". Comparing `H = 20` to `H = 80` gives **−0.074** —
"advantage shrinks with horizon". **Both are computed from the same null, in which nothing
interacts with horizon at all.** Choose the buckets after seeing the curve and this statistic will
hand you either headline. That is not a hypothetical failure mode; it is the default one.

Note the last row: the **log-odds** gap is monotone and, under pure compounding, grows *linearly*
in `H`. That is precisely why the estimand must be defined on the **per-step** log-odds hazard,
where pure compounding predicts a **constant** — giving a real null that a real interaction can
depart from. `docs/LONG_HORIZON_FITNESS_V0.md` fixes this as `β` (super-compounding), with rank
reversal as the secondary endpoint and the absolute gap demoted to descriptive.

The two versions worth actually winning, because compounding cannot explain either:

- **A rank reversal across horizon** — representation A beats B at short horizon and loses at long
  horizon. Compounding preserves ordering, so a reversal is not a corollary of it.
- **Super-compounding** — the *per-step* gap itself widens with depth.

Everything downstream (the fitness design, the trajectory arena, the preregistration of any
confirmatory claim) must target one of those two, with the metric fixed in advance.

This reorients everything downstream: the required substrate is **verified multi-step
trajectories**, not multiple-choice probes, and the required fitness is a **vector including a
horizon dimension**, not a scalar accuracy.

## 6. What must be built (and in what order)

1. **A verified trajectory world.** The highest-priority missing substrate. Every existing Arena
   environment is a single-step, two-option probe; long-horizon reasoning cannot be measured by
   any of them. Truth stays with the backend, and the Arena canonical schema is **not** required
   to losslessly encode backend states — a backend-native semantic envelope is permitted where the
   canonical schema cannot reach.
2. **A language meta-genome** wide enough that a mutation can change the ontology, the state
   topology, the lexicon and the action granularity — not only the skin. A parity audit has
   already measured that two of the current eight seed surfaces share 98.6% of their bytes, so the
   present genome does not span the space the mission needs.
3. **A multi-fidelity evaluator** with successive halving, so that expensive levels run only on
   candidates that survived cheap ones.
4. **An outer loop that actually runs**: population → choose parent → mutate → semantic gate →
   evaluate → record fitness → archive → next generation.
5. **A durable language-fitness memory**, which is the dataset a surrogate is eventually trained
   on.

## 7. Method discipline — what the outer game inherits

Evolutionary search does not license sloppiness. The following carry over unchanged from
`GOAL.md` and from the V7 forensic audit, and apply to every fitness reading:

- **No granularity substitution.** A statistic computed on a coarser population than the claim
  drawn from it is invalid. This was the programme's recurring failure mode; it recurs more easily
  in a search loop, not less.
- **Selection and evaluation are separate.** A candidate selected on a pool is never scored on
  that pool. A max over k hypotheses is corrected for k.
- **Thresholds are representable.** A gate must be a value the estimator can actually take at the
  planned n.
- **Sample size is designed, never inherited.**
- **Provenance and cache identity are complete**, and cross-condition reuse is impossible by
  construction rather than by convention.
- **Preregistration binds any confirmatory claim.** Exploratory search inside the loop is fine and
  expected; a *claim* about a language requires a frozen protocol.
- **Failure is recorded, never quietly regenerated.**

## 7a. The novelty boundary — binding on every claim this project makes

`docs/HAMILTONIAN_PRIOR_ART_BOUNDARY.md` returns **`NOVEL_ONLY_IN_COMBINATION`**, and that verdict
is binding. Every load-bearing component of this architecture is already in print, and two are in
print *in this exact domain with this exact metric*:

- A hand-designed machine-facing proof language for a proof assistant already reports **+20–29
  points of kernel-verified pass@1** over the incumbent. The field has already noticed that
  machine-facing language design pays.
- Automated search over how state is rendered to an LLM agent, scored by that agent's downstream
  task success, is already published.
- Canonical content with many renderings is roughly twenty years old.
- The outer loop's machinery — quality-diversity, successive halving, archives — is commodity.

**Consequences, which are not negotiable.** The project may not claim to have invented a
mathematical DSL, to have introduced the idea that representation matters, to have introduced
searching over representations, or to have introduced agents inventing symbols. **Publishing the
architecture alone would be `LARGELY_COVERED_BY_PRIOR_ART`.** What survives is narrow and must be
earned as a *result*, not asserted as a design: a population search over the design of a
machine-facing mathematical state presentation — ontology, topology, grammar, morphology, binding,
action granularity, workspace — under *enforced information parity*, with the primitive set held
constant, scored by *verified long-horizon* capability.

Two controls follow directly and must be built in from the start, because the nearest prior work
is already vulnerable on both: a **compute- and sampling-matched control** (published gains in this
area have been attributed to self-correction and extra sampling rather than to the artifact), and
**enforced information parity** (the nearest mechanistic match deliberately breaks parity by
optimising for token reduction — a language that merely says less is not a better language).

## 8. Naming discipline

`GOAL.md` §16's evidence ladder is unchanged and still governs what a language may be called:
`VALID_CANDIDATE` → `FITNESS_CANDIDATE` → `LEARNABILITY_CANDIDATE` → `ROBUST_CANDIDATE` →
`RSTAR_0_1`. The outer loop produces **the best language found so far under a declared budget**,
which is a leaderboard position and nothing more. A winner of one generation is not a
`FITNESS_CANDIDATE`, and no result from an unreplicated loop may be called `RSTAR`.

## 8a. The three standing risks to the whole programme

Recorded here because they threaten the mission itself, not any one experiment, and because two of
them were measured rather than argued.

1. **Memorisation reported as reasoning.** mathlib4 is `HISTORICALLY_EXPOSED` and exposure is
   transitive, so a solver closing a twenty-step proof may be recalling it. Nothing in the current
   design distinguishes recall from reasoning, and the only local control is a single-use sealed
   split. **Therefore the defensible phrasing is "long-horizon execution under kernel
   verification", not "long-horizon reasoning"** — and the difference must be stated in any
   result, not buried.
2. **Verification that is secretly a string match.** Measured: raw pretty-printed Lean state
   equality scores **40.6%** where real semantic agreement is **98.1%** (`univ` versus
   `Finset.univ` — scope-dependent rendering). A string-comparing verifier would reject 59.4% of
   *correct* steps. **Truth must stay with the backend's own state identity**, never a text
   comparison. This is the single easiest way to build a plausible-looking arena that measures
   nothing.
3. **Horizon measured on automation rather than reasoning.** A single heavy tactic can close many
   steps at once, so an unrestricted tactic set makes "horizon" a property of the automation, not
   of the language. The tactic set must be recorded per trajectory and restrictable by parameter.

## 9. The governing principle

The recent programme spent its effort perfecting the fitness meter. The meter is good and is kept.
**It is now mounted on the machine.** The machine is verified mathematics, plus a language
population, plus a Solver, plus fitness, plus an Architect, plus mutation, plus repeated
generations.

**Do not design the winner. Build the game that can discover it.**
