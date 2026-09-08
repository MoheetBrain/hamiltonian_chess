# HC-V0 OUTER LOOP

**Source:** manual §40 (minimum vertical slice), §21 (candidate lifecycle), §12 (compiler
contract), §15 (outer game), §32.1 (V0 smoke policy), §33 (fitness memory), §6.26/§26 (intervention
class). Authority rank 3 (`spec/00_CONSTITUTION.md` C7). Restricted adjectives carry
`spec/01_GLOSSARY.md` Part B meanings.

---

## 0. What HC-V0 is, stated plainly — `INVARIANT` (§0.2, §40)

HC-V0 is **engineering-only**. It proves one state transition executes. It is **not** a scientific
language tournament.

> **No HC-V0 winner is a scientific language winner.** (§0.2, restated §40.)

A generation winner is a leaderboard position under a declared budget and nothing more
(`spec/01_GLOSSARY.md` §B.1). No `RSTAR` or `LSTAR` claim is permitted (§40.6). No candidate may be
called a `FITNESS_CANDIDATE`, `LEARNABILITY_CANDIDATE` or `ROBUST_CANDIDATE` on V0 evidence
(Appendix D).

---

## 1. The flow — §40.2 — `INVARIANT`

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

Scale (§32.1, §40.4): **3–4 existing founders · 1–4 children · exactly one generation ·
deterministic or cheap live evaluation · no superiority claim.** A stub evaluator may validate
orchestration; **at least one real backend/verifier interaction SHOULD run if practical**.

Preconditions the loop may not start without (§40.1): salvage done; baseline tests green; the
§36.1 minimum specs exist; at least one verifier-backed `VerifiedTask` **or** an explicitly
replay-only admitted source; 3–4 existing candidates can encode the chosen workspace; one
controlled mutation exists; the truth/assurance gate works; one Solver adapter or deterministic stub
evaluator works; fitness records persist deterministically.

---

## 2. Every comparison declares an `InterventionClass` — `INVARIANT` (§6.26, §12.3, §26)

**This is not optional and not deferrable.** §26.1's universal declaration list makes intervention
class the twelfth required item of every comparison; §12.4 makes an undeclared intervention a
candidate death (`DEAD_UNDECLARED_INTERVENTION`); §40.5 makes "truthful intervention classification"
part of the V0 success criterion.

Rules the loop enforces:

1. The mutation operator's class is declared **before** the child is compiled, is stored on the
   `LanguageCandidate` (§12.1 `intervention_class`), and is copied onto every
   `LanguageFitnessRecord` the child produces.
2. The class **determines** the fairness contract Gate 0 applies
   (`spec/evaluation/HC_V0_EVALUATOR_CONTRACT.md` §4–§5) and the causal claims permitted.
3. A declared class that does not match the actual genome delta is
   `DEAD_UNDECLARED_INTERVENTION`, not a warning.
4. §20.2: early generations **SHOULD** change one gene family per child, so parent-child effects are
   interpretable. A multi-family mutation is `JOINT` and carries only system-level claims (§26.4).

The eight classes and their contracts are in `spec/01_GLOSSARY.md` A.0.

---

## 3. Candidate lifecycle state machine — §21 — `INVARIANT`

**Every candidate SHALL occupy exactly one lifecycle state. Transitions SHALL be code-enforced.**

### 3.1 Progress states, in order

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

HC-V0 reaches at most `SCOUTED`. Everything from `ADAPTATION_ELIGIBLE` onward requires Gates 2–6,
which are `DEFERRED` for V0 (`spec/evaluation/HC_V0_EVALUATOR_CONTRACT.md` §1).

### 3.2 Terminal / non-progress states

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

**A dead candidate MUST NOT receive Solver compute** (§12.4). That is a code-enforced
precondition on the evaluate step, not a convention.

`VOID_INSTRUMENT` is the state for a candidate whose evaluation is uninterpretable because the
instrument failed — distinct from a candidate that was evaluated and eliminated. Recording it is
required by §43's preference for explicit negative states.

---

## 4. Compiler failure outcomes — §12.4 — `INVARIANT`

The compiler emits exactly one of:

| Outcome | Meaning |
|---|---|
| `DEAD_GENOME_CONSTRAINT` | a §11 cross-field constraint is violated; fails **before** model evaluation |
| `DEAD_COMPILE` | genome does not produce an executable phenotype |
| `DEAD_STATIC_SEMANTICS` | not well-formed, well-typed, correctly scoped or identity-consistent |
| `DEAD_TRUTH_FIDELITY` | the candidate changes truth conditions — universal, all classes |
| `DEAD_INFORMATION_PARITY` | parity required by the declared class does not hold |
| `DEAD_ACTION_LOWERING` | an action does not lower to trusted backend operations or a verifiable program |
| `DEAD_LEAKAGE` | oracle information reaches the Solver |
| `DEAD_UNDECLARED_INTERVENTION` | the actual delta is not the declared class |

§21's terminal list and §12.4's list are not identical: §21 has `DEAD_SEMANTIC_PARITY` and
`DEAD_REFUTER`; §12.4 has `DEAD_TRUTH_FIDELITY`, `DEAD_INFORMATION_PARITY` and
`DEAD_UNDECLARED_INTERVENTION`. **Both lists are normative and the union is implemented.** Mapping
used: §21's `DEAD_SEMANTIC_PARITY` covers §12.4's `DEAD_TRUTH_FIDELITY` and
`DEAD_INFORMATION_PARITY`; §21's `DEAD_REFUTER` is the §29 adversarial outcome, which §12.4 does not
cover because it is not a compiler outcome. Type of this mapping: `ENGINEERING_DECISION` (§37),
recorded here because §2.3 makes an unreconciled contradiction with a higher-authority contract a
readiness blocker.

---

## 5. Role boundaries the loop enforces — §16

- **Architect** (§16.1) may inspect development evidence, genomes and lineages, and propose typed
  mutations. It **MUST NOT** read sealed answers, modify the truth kernel, modify verifier outputs,
  modify evaluation thresholds after results, or approve its own semantic gate.
- **Solver** (§16.2) **MUST NOT** receive an answer oracle, hidden labels, or candidate-specific
  privileged information.
- **Refuter** (§16.3) is adversarial, not an omniscient certifier. Its wording is
  `0 known critical exploits under attack_suite_version X` (§29).
- **Builder** (§16.4) SHOULD be deterministic software.
- **League Manager** (§16.6) cannot override semantic death.
- **Curriculum Designer** (§16.8) is DISABLED for sealed evaluation.
- V0 requires exactly three strategic AI roles: Architect, Solver, Refuter (§16.9). Parallel Solver
  workers are throughput workers, not distinct roles.

**V0 SHALL NOT train an RL Architect** (§15.3, §34, §50 hard stops).

---

## 6. What the loop writes — §33

One `LanguageFitnessRecord` per evaluation, conforming to
`spec/meta_game/LANGUAGE_FITNESS_MEMORY_SCHEMA.json`. Append-only: a correction is a new record
with `supersedes`, never an edit (§3.3). A refused or failed evaluation **is a record** (§43).

Fitness stays a **vector** (§6.22, §22). No arbitrary universal scalar (§22.2). Default tie-break
order when one is needed: truth/soundness > verified terminal capability > long-horizon /
held-out generalization > learnability > search/repair reliability > efficiency (§22.2).

---

## 7. Success criterion — §40.5 — `INVARIANT`

> The loop executes end-to-end with deterministic lineage, truthful intervention classification,
> verifier/assurance provenance, durable fitness memory, and reproducible archive update.
>
> **No improvement is required.**

A generation in which every child is eliminated, or in which the child is worse than its parent, is
a **passing** HC-V0 run.

---

## 8. Sentinels — §40.6 — `INVARIANT`

HC-V0 ends with **exactly one** primary sentinel:

```text
META_GAME_V0_EXECUTABLE
META_GAME_ARCHITECTURE_READY
META_GAME_BLOCKED_BY_TRAJECTORY_WORLD
META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD
META_GAME_BLOCKED_BY_SEMANTIC_SUBSTRATE
SPEC_BLOCKED_BY_OWNER_AMBIGUITY
```

**No `RSTAR` or `LSTAR` claim is allowed** (§40.6).

Selection guidance from the manual: if only replay data is available the loop may still run as
engineering, but the interactive-world blocker is recorded (§18.4, §40.3, §50 Phase C step 15) —
that is `META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD`.

---

## 9. Stop rule — §47 Step 10, §48

After one generation: **stop and hand off.** Do **not** continue into Pilot 1. Report measured V0
costs, variance and blockers so the scientific pilot can be designed from evidence (§32.2, §41.2).

Pilot 1 population size, generations, promotion fractions and budgets are `UNKNOWN` and **SHALL**
be selected only after HC-V0 measures compile/death rate, evaluator latency and cost, task variance,
candidate-pair discordance, long-horizon task availability and available compute (§32.2). Earlier
illustrative values such as 12 founders, 32 children per generation and 10 generations are **NOT
binding defaults** (§32.2).

---

## CONFORMANCE GAPS

1. **`InterventionClass` is absent from the repository** (`CLM-GAP-INTERVENTION-040`), so §2 of this
   document is currently unimplementable and §40.5's success criterion cannot be evidenced. Type:
   `KNOWN_FACT`. **This is the single most load-bearing gap in the outer loop.**
2. **The §21 state machine is not implemented as a state machine.** `arena/evolution/loop.py`
   (untracked at time of writing) runs a generation and its tests assert that a killed candidate is
   never scored, but there is no enumerated lifecycle type with code-enforced transitions covering
   all 14 progress states and all 13 terminal states. §21 says transitions **SHALL** be
   code-enforced. Type: `KNOWN_FACT`.
3. **§12.4 and §21 name overlapping but non-identical death vocabularies.** Reconciled in §4 above
   as an `ENGINEERING_DECISION`; flagged because §2.3 treats an unreconciled contradiction with a
   higher-authority contract as a readiness blocker, and because the resolution should be confirmed
   rather than assumed. Type: `ENGINEERING_DECISION`.
4. **The archive/population update is partial.** `arena/league/registry.py` and
   `arena/fitness/pareto.py` exist; nothing iterated generations before the concurrent
   `arena/evolution/loop.py` work (`docs/HAMILTONIAN_CHESS_META_MDP.md` §2). Type: `KNOWN_FACT`.
