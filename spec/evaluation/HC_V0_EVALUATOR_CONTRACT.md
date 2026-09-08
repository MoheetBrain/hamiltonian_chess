# HC-V0 EVALUATOR CONTRACT

**Source:** manual §25 (multi-fidelity ladder), §26 (fair-comparison and causal-claim contract),
§12 (compiler contract), §14.4 (terminal outcomes), §28 (verifier trust), §29 (Refuter), §13.1
(macro accounting). Authority rank 3 (`spec/00_CONSTITUTION.md` C7). Restricted adjectives carry
`spec/01_GLOSSARY.md` Part B meanings.

**Scope:** HC-V0 only. HC-V0 is engineering-only (§0.2, §40). **No HC-V0 result is a scientific
result and no HC-V0 winner is a language winner.**

---

## 1. Which gates HC-V0 runs

| Gate | § | HC-V0 status |
|---|---|---|
| **Gate 0 — deterministic validity** | 25 | **REQUIRED.** No model calls. |
| **Gate 1 — cheap scout** | 25 | **REQUIRED.** Detects catastrophic unreadability and gross failure. **MUST NOT crown a language.** |
| Gate 2 — short matched adaptation | 25 | **DEFERRED** |
| Gate 3 — medium adaptation / multi-step tasks | 25 | **DEFERRED** |
| Gate 4 — serious finalist | 25 | **DEFERRED** |
| Gate 5 — champion confirmation | 25 | **DEFERRED** |
| Gate 6 — robust validation | 25 | **DEFERRED** |

`DEFERRED` is the §37 type: these gates are specified by the manual, are not implemented for V0,
and their absence is recorded rather than worked around. **Nothing in HC-V0 may be described in
Gate 2–6 language.** In particular: no `FITNESS_CANDIDATE`, no `LEARNABILITY_CANDIDATE`, no
`ROBUST_CANDIDATE`, no `RSTAR_0_1`, no `LSTAR_0_1` (Appendix D).

The exact sample sizes, budgets and promotion fractions for Gates 2–6 **SHALL** be frozen only
after V0 calibration and **before** observing the results they govern (§25 final paragraph, §32.2).
They are `UNKNOWN` today and this document does not guess them.

---

## 2. Gate 0 — deterministic validity — `INVARIANT` (§25, §12)

**No model calls.** Every check below is deterministic, and a failure is a candidate death, not a
score.

| Check | § | Failure state (§12.4, §21) |
|---|---|---|
| Genome validates against `spec/language/language_genome_v0.schema.json`, and the §11 cross-field constraints that JSON Schema cannot carry are code-checked | 10, 11 | `DEAD_GENOME_CONSTRAINT` |
| Genome compiles to an executable phenotype (§12.1 `LanguageCandidate` field set) | 12.1 | `DEAD_COMPILE` |
| Static semantics: well-formed, well-typed, correctly scoped, identity-consistent | 8.3, 12.2 | `DEAD_STATIC_SEMANTICS` |
| **Truth fidelity — universal, all intervention classes** | 0 (correction 6), 4.4, 12.2 | `DEAD_TRUTH_FIDELITY` |
| Intervention class declared and matches the actual delta | 6.26, 12.3 | `DEAD_UNDECLARED_INTERVENTION` |
| Required visible-information parity **where the class requires it** | 12.3, 26.2 | `DEAD_INFORMATION_PARITY` |
| Action lowering: every `a_L` lowers to trusted backend operations or a backend-verifiable program | 13 | `DEAD_ACTION_LOWERING` |
| Leakage / assurance: no answer label, future state, hidden solution, minimum proof path or candidate-correctness label reaches the Solver | 27, 29 | `DEAD_LEAKAGE` |

**Two rules that are not negotiable:**

1. **Truth fidelity is universal; parity is conditional** (§0 correction 6). Every candidate must
   preserve truth. Visible-information parity is mandatory **only** where the intervention claims to
   hold information fixed — i.e. `R_ONLY`. A `P_CHANGE` or `O_CHANGE` candidate deliberately changes
   visible information and is **not** failed for it; it is instead required to supply a
   machine-readable parent delta, an admissibility audit, and a claim label matching its class
   (§12.3).
2. **No dead candidate receives Solver compute** (§12.4). Gate 0 runs to completion before Gate 1
   begins.

### 2.1 Universal postconditions a passing candidate satisfies (§12.2)

Deterministically encodes every admitted workspace state in its supported domain · preserves
truth-relevant identity, binding, scope and types required by its declared interface · emits stable
hashes · lowers actions into trusted backend operations or verifiable programs · **fails closed on
unsupported constructs** · exposes all declared intervention deltas.

### 2.2 Failure semantics that Gate 0 must keep distinct (§8.7, §28)

`UNKNOWN`, `TIMEOUT`, `UNSUPPORTED` and `FALSE` are four different things and **MUST NOT** be
collapsed. `UNKNOWN != FALSE`. `TIMEOUT != FALSE`. `TOOL_ERROR != MATHEMATICAL_INVALID`. A candidate
never succeeds because the verifier crashed and never fails because infrastructure failed (§28).

---

## 3. Gate 1 — cheap scout — `INVARIANT` (§25)

**Purpose, and only this purpose:** detect catastrophic unreadability and gross failure.

- Gate 1 **MUST NOT** crown a language (§25 verbatim).
- Gate 1 output is developmental evidence, never confirmatory (§30.4).
- Gate 1 may use a deterministic stub evaluator for orchestration; **at least one real
  backend/verifier interaction SHOULD run if practical** (§40.4, §47 Step 8).
- Every episode records the §13.1 accounting: `model_action_count`, `kernel_step_count`, tool
  calls, verifier calls, wall-clock, tokens/compute.
- Terminal outcomes come from the §14.4 vocabulary. **`ENVIRONMENT_ERROR` SHALL NOT count as
  mathematical failure.**

**Sample sizes are not inherited.** A tiny `n` such as 24 calibrates engineering only (§30.2).
Scientific sample size is justified by minimum practical effect, power or precision, dependence and
multiplicity (§30.2, §30.3) — all `UNKNOWN` until V0 measures task variance and episode cost
(§18.4, §32.2, §41.2).

---

## 4. Universal declaration — required for every comparison — `INVARIANT` (§26.1)

Every comparison, including a V0 smoke comparison, **MUST** declare all twelve:

1. tasks / distribution
2. truth-kernel / backend versions
3. Solver initialization / checkpoint
4. tokenizer
5. controller
6. tools / libraries
7. adaptation examples and their order
8. adaptation and inference budgets
9. verifier
10. seeds
11. output / action protocol
12. **intervention class**

A comparison missing any of the twelve is not a comparison. Item 12 is the one this repository
cannot currently supply (see CONFORMANCE GAPS).

---

## 5. `R_ONLY` fixed-variable list — `INVARIANT` (§26.2)

When and only when the declared class is `R_ONLY`, these are held fixed:

- truth state
- visible mathematical information
- action semantics and cardinality
- tokenizer
- Solver
- controller
- tools
- training examples
- evaluation tasks
- verifier
- compute regime

**Only approved representation, morphology and interface structure differs.**

The proof obligations §12.3 places on an `R_ONLY` candidate are: same visible semantic inventory ·
same candidate alternatives and action semantics · same truth state · only approved
representational/morphological/interface structure differs.

### 5.1 Other classes are not held to this list (§26.3, §26.4)

`P_CHANGE`, `O_CHANGE`, `T_CHANGE` and `A_CHANGE` intentionally alter the cognitive interface. They
estimate the system-level value of that intervention and **MUST NOT** be reported as pure
representation effects. A `JOINT` candidate enumerates every changed component and may be promoted
as a system candidate, but component-level causal attribution requires later ablation.

`TAU_CHANGE` is a model-level change (§26.6): a fixed pretrained tokenizer gives different
segmentation and frequency priors to English words and invented symbols, so claims about intrinsic
morphology require matched adaptation plus tokenization and frequency controls.

### 5.2 Output protocol (§26.7)

For local input-representation assays, prefer universal semantic action IDs where feasible, so the
output channel is not itself an uncontrolled arm of the comparison.

---

## 6. What HC-V0's evaluator explicitly does not do

`DEFERRED` / `NON_GOAL` (§37):

- no matched adaptation, no learning curve, no `L_sample` estimate (Gate 2–3);
- no fresh project-hidden confirmation data (Gate 5) — and therefore no superiority claim of any
  kind (§4.5, §30.4);
- no second Solver family (Gate 6);
- no RL Architect and no surrogate (§15.3, §34, §50 hard stops);
- no scientific founder tournament (§35, §48, §50 hard stops).

---

## CONFORMANCE GAPS

1. **§26.1 item 12 cannot be satisfied today.** `InterventionClass` does not exist in code
   (`spec/02_CLAIM_LEDGER.jsonl` `CLM-GAP-INTERVENTION-040`). Every existing comparison harness —
   `arena/experiments/game_r_formal_v1.py` included — declares the other eleven items and not the
   twelfth. Until it exists, `DEAD_UNDECLARED_INTERVENTION` cannot fire and §40.5's "truthful
   intervention classification" cannot be evidenced. Type: `KNOWN_FACT`.
2. **The truth gate exists and is measured, but is not yet the loop's single fail-closed gate.**
   `ModelViewCompiler.validate` plus `arena/assurance/` were verified on 2026-09-08 to round-trip
   all 8/8 seed surfaces and to refuse a renderer that drops an assumption; the same audit records
   that it "still needs to be wired as the loop's single fail-closed gate"
   (`docs/HAMILTONIAN_CHESS_META_MDP.md` §2). Type: `KNOWN_FACT`.
3. **Gate 0's parity check would currently pass a near-duplicate population.** Two seed surfaces
   share 98.6% of their state bytes (`CLM-FACT-SEEDCOLLAPSE-012`), and 0 of 44 one-gene mutations
   change the bytes of the eight registered seed codecs (`CLM-FACT-GENOMEBLIND-011`). Gate 0 as
   specified detects neither, because §25 Gate 0 checks validity, not diversity. A behavioural-
   descriptor check is a Gate-0 candidate for a later ADR; it is **not** added here, because §0.1
   forbids adding machinery before an executable dependency requires it. Type: `KNOWN_FACT`.
4. **No verifier in the repository carries a complete §28 declaration.** `arena/verifier/native.py`
   is a per-generator truth oracle for single-step synthetic probes; there is no `verifier_id` with
   declared trust assumptions, accepted/unsupported constructs, timeout semantics, `UNKNOWN`
   semantics and replay method. Type: `KNOWN_FACT`.
