# VERIFIED TASK / VERIFIED TRAJECTORY CONTRACT

**Source:** manual §17 (whole section), §6.20, §6.25, §6.30–§6.34, §14.6, §18.
**Authority rank 3** (`spec/00_CONSTITUTION.md` C7). Restricted adjectives carry
`spec/01_GLOSSARY.md` Part B meanings.

This contract exists because v0.2 correction 3 names the conflation it prevents:

> *"`VerifiedTask` is separated from `VerifiedTrajectory`: a stored proof path is not automatically
> an interactive MDP or a complete legal-action oracle."*

and correction 4:

> *"Recorded trace length is not intrinsic reasoning difficulty."*

---

## 1. The two objects are different kinds — `INVARIANT` (§6.20, §6.25)

| | `VerifiedTask` | `VerifiedTrajectory` |
|---|---|---|
| **Kind** | an **executable environment** | a **recorded path** |
| Supports interaction | **yes, by definition** (§6.25) | **not necessarily** (§6.25) |
| Solver may deviate | yes — that is the point | n/a; nothing is running |
| Licenses claims about search, repair, free-running proof completion, autonomous long-horizon capability | **yes** (§14.6 `INTERACTIVE_TASK`) | **no** (§14.6 `TRAJECTORY_REPLAY`) |
| Useful for | scientific evaluation; V0's preferred mode (§40.3) | adaptation, diagnostics, engineering smoke (§14.6, §40.3) |

A collection of `VerifiedTrajectory` records is **not** a `VerifiedTask` world. Deriving the
former from the latter is legitimate and common; asserting the reverse is the defect.

---

## 2. `VerifiedTask` schema — §17.1 — `INVARIANT`

```text
VerifiedTask {
    task_id,
    problem_id,
    source_system,
    source_version,
    source_hash,
    backend_kernel_contract,      # §6.24 — versioned, per-backend, not universal
    domain,
    theorem_group,                # the grouping unit for splits and clustering (§18.2, §30.6)
    split,
    initial_state_ref,            # -> KernelState (§6.2); MAY be backend-native (§17.4)
    terminal_predicate,           # decides VERIFIED_SOLVED / VERIFIED_REFUTED (§14.4)
    action_interface,             # decoding + lowering: A_L -> [A_K...] (§13)
    tool/library_contract,        # U (§6.17)
    verifier_adapter,             # V (§6.18) + its §28 trust declaration
    provenance,
}
```

### 2.1 Required behaviour of each field

- **`terminal_predicate` MUST distinguish all seven §14.4 outcomes**: `VERIFIED_SOLVED`,
  `VERIFIED_REFUTED` (where valid), `UNRECOVERABLE_INVALID_ACTION`, `SEARCH_BUDGET_EXHAUSTED`,
  `TOOL_TIMEOUT`, `UNSUPPORTED`, `ENVIRONMENT_ERROR`.
  **`ENVIRONMENT_ERROR` SHALL NOT count as mathematical failure** (§14.4).
- **`action_interface` MUST define `lower_L(a_L) -> [a_K1 … a_Kn]`** or an equivalent
  backend-verifiable program (§13). A macro that cannot be lowered is `DEAD_ACTION_LOWERING`
  (§12.4).
- **`verifier_adapter` MUST carry the §28 declaration**: `verifier_id`, version/domain, trust
  assumptions, accepted constructs, unsupported constructs, timeout semantics, `UNKNOWN` semantics,
  error semantics, replay/rechecking method. And the four §28 rules hold:
  `UNKNOWN != FALSE` · `TIMEOUT != FALSE` · `TOOL_ERROR != MATHEMATICAL_INVALID` ·
  a candidate never succeeds because the verifier crashed, and never fails because infrastructure
  failed.
- **`initial_state_ref` MAY point at a backend-native envelope** (§17.4, §6.2). See §5 below.

### 2.2 Per-episode accounting the task MUST emit — §13.1 — `INVARIANT`

Every episode run against a `VerifiedTask` **SHALL** record at least:
`model_action_count` · `kernel_step_count` · tool calls · verifier calls · wall-clock ·
tokens/compute.

**A macro does not receive free compute** (§13.1). When comparing action-granularity candidates
(`A_CHANGE`), both model-facing cost and underlying kernel/tool cost **MUST** be reported. §13.2:
the finest primitive decomposition is **not** presumed optimal — a macro is a legitimate cognitive
abstraction if it stays truth-grounded and its cost is honestly accounted.

---

## 3. `VerifiedTrajectory` schema — §17.2 — `INVARIANT`

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
            normalized_semantic_envelope_if_available,   # optional, never mandatory (§17.4)
            recorded_action,
            action_semantics,
            verifier_evidence,
            next_state_ref,
            terminal_after,
        }
    ],
    terminal_status,
    observed_trace_length,                                # §6.30
    dependency_depth_if_defined,                          # §6.33, may be absent
    minimal_proof_length: VALUE | UNKNOWN,                # §6.34 — literal UNKNOWN by default
    provenance,
}
```

`normalized_semantic_envelope_if_available` is **optional by construction**. Its absence is a
recorded fact, not a defect (§17.4).

---

## 4. The critical epistemic rule — §17.3 — `INVARIANT`

**A recorded trajectory is one demonstrated path.** It is **not** automatically:

- the only legal path;
- the optimal path;
- the shortest proof;
- a complete legal-action oracle;
- evidence that every step was necessary.

**A Solver action different from the recorded action is NOT mathematically wrong unless the
verifier establishes that.**

Direct consequences that bind implementation:

1. A scorer that compares the Solver's action to the recorded action **by string or token
   equality** implements none of the above and is forbidden as a verifier. It may exist only as a
   labelled descriptive statistic. This is measured, not hypothetical: raw pretty-printed Lean
   state equality scores **40.6%** where real semantic agreement is **98.1%**, so a
   string-comparing verifier would reject **59.4% of correct steps**
   (`docs/VERIFIED_TRAJECTORY_ARENA_V0.md` §4.3, `docs/HAMILTONIAN_CHESS_META_GOAL.md` §8a).
   Type of that measurement: `KNOWN_FACT`.
2. "Off-trajectory" is not a failure class. The §14.4 outcome list has no such member.
3. A recorded trajectory **MUST NOT** be used to enumerate the legal action set at a state.

---

## 5. Backend-native truth is allowed — §17.4 — `INVARIANT`

**Do not force all mathematics through an old canonical schema if information is lost.**

The permitted arrangement is: truth stays with the backend's own state identity; a canonical or
normalized envelope is an **optional projection**, recorded when it exists and marked absent when
it does not.

This is not a preference. It is forced by measurement: the repository's canonical schema maps
**0 of 368 real Lean states losslessly** (79.3% with loss, 20.7% unmappable) —
`docs/CANONICAL_VNEXT_PILOT.md`, `docs/HAMILTONIAN_CHESS_REPO_REMAP.md` §3.1. Type: `KNOWN_FACT`.

Consequence for `Ω_L` (§14.1): if the state is a backend-native envelope, the observation function
of every candidate language **MUST** be defined over that envelope. A candidate that can only
render the canonical schema is `UNSUPPORTED` on that task family, not silently lossy.

---

## 6. Failed branches — §17.5 — `INVARIANT`

**Do not invent failed branches retrospectively.** Generate them online and record verifier
outcomes.

A `VerifiedTrajectory` synthesised from a successful recorded proof by inserting plausible wrong
turns is fabricated evidence, and under `spec/00_CONSTITUTION.md` C9 it may not be written to any
store as if it were observed.

---

## 7. Horizon reporting — §17.6 — `INVARIANT`

Every trajectory, episode, and fitness record **SHALL** report these separately and under these
names (`spec/01_GLOSSARY.md` A.0):

| Field | § | Rule |
|---|---|---|
| `ObservedTraceLength` | 6.30 | transitions in one stored demonstration |
| `EpisodeLength` | 6.31 | model-facing decisions in an actual interactive run |
| `KernelStepCount` | 6.32 | trusted backend operations **after** action lowering |
| `DependencyDepth` | 6.33 | task-family-specific structural measure; may be absent, and absence is recorded |
| `MinimalProofLength` | 6.34 | `VALUE` **only** when independently established; otherwise the literal `UNKNOWN` |

**FORBIDDEN (§17.6):** describing a recorded 50-step proof as a "50-step required reasoning task"
without evidence of necessity or minimality. Any `Reasoning Horizon` (§6.21) claim states which of
the five quantities it is about, and horizon means **sequential dependent** transitions, never
concatenated unrelated microtasks.

Two related traps, both already measured in this repository, that a horizon claim must clear:

- **Automation, not reasoning.** A single heavy tactic can close many steps at once, so an
  unrestricted tactic set makes "horizon" a property of the automation. The tactic set **MUST** be
  recorded per trajectory and restrictable by parameter
  (`docs/HAMILTONIAN_CHESS_META_GOAL.md` §8a.3).
- **Metric choice.** Under pure compounding with no interaction at all, the absolute accuracy gap
  is **unimodal in horizon**: for a constant per-step edge of 0.870 → 0.905 it peaks at H = 8 and
  decays to 0.0003 by H = 80, so H1→H20 reads "+0.039, advantage grows" and H20→H80 reads "−0.074,
  advantage shrinks" **from the same null** (`docs/HAMILTONIAN_CHESS_META_GOAL.md` §5.1,
  `docs/LONG_HORIZON_FITNESS_V0.md` §4.4). The metric **MUST** be declared before the comparison.

---

## 8. Replay versus interaction — §14.6, §40.3 — `INVARIANT`

| Mode | Definition | What it demonstrates |
|---|---|---|
| `TRAJECTORY_REPLAY` | Solver predicts/consumes transitions from a recorded trajectory | adaptation and diagnostics. **Does not demonstrate autonomous problem solving.** |
| `INTERACTIVE_TASK` | Solver acts in a `VerifiedTask` and may take alternative paths | required for claims about search, repair, free-running proof completion, or autonomous long-horizon capability |

HC-V0 **prefers** `INTERACTIVE_TASK` and **allows** `TRAJECTORY_REPLAY` for engineering-only
execution (§40.3). **If replay-only is used, autonomous long-horizon solving remains explicitly
blocked**, and the sentinel `META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD` (§40.6) applies.

Every `SourceAdmissionRecord` therefore carries `supported_task_mode: REPLAY | INTERACTIVE | BOTH`
(§18, `spec/world/SOURCE_ADMISSION_SCHEMA.json`).

---

## 9. Admission — pointer, not a second contract

Source admission is specified by §18 and machine-checked by
`spec/world/SOURCE_ADMISSION_SCHEMA.json`. Two rules restated here because they bind this contract
directly:

- **§18.2 grouped splits.** Split by theorem/module/repository/problem family, **not** random steps
  from the same proof family. Steps within a trajectory are dependent (§30.6).
- **§18.3 V0 engineering admission.** HC-V0 needs only enough verifier-backed material to prove the
  loop executes. **No arbitrary minimum corpus size is required for the engineering smoke.**
  Scientific sample counts are chosen after variance and cost are measured (§18.4, §32.2).

---

## CONFORMANCE GAPS

Each is a measured statement about this repository as of 2026-09-08, not an opinion.

1. **`VerifiedTask` is not implemented.** `grep -rn "VerifiedTask" arena/ tests/` returns zero
   matches. `arena/trajectory/schema.py` and `arena/trajectory/arena_v0.py` (untracked, written
   concurrently) implement `VerifiedTrajectory` and a replay/live driver, but there is no object
   with the §17.1 field set — no `terminal_predicate`, no `action_interface`, no
   `tool/library_contract` as a first-class contract. Type: `KNOWN_FACT`. **Effect:** any
   autonomous long-horizon claim is blocked; §40.3's preferred `INTERACTIVE_TASK` mode is
   unavailable through a declared task object even where the Lean backend can in fact be driven
   interactively.
2. **Horizon fields do not carry the manual's names or its full set.**
   `arena/trajectory/schema.py` defines `Horizon(achieved, verified, reference, solver_actions,
   reference_actions)`. `KernelStepCount` (§6.32), `DependencyDepth` (§6.33) and
   `MinimalProofLength` (§6.34, including its literal `UNKNOWN`) have no field. Type: `KNOWN_FACT`.
3. **Existing Arena environments are horizon 1.** Every environment in `arena/environments/` is a
   single-step, two-option probe; the only `CanonicalTrajectory(...)` construction in the package
   passes a one-element tuple (`arena/tasks/generators/world_v0.py:507`). **Maximum horizon
   anywhere in the committed repository: 1** (`docs/HAMILTONIAN_CHESS_META_MDP.md` §1,
   `docs/HAMILTONIAN_CHESS_REPO_REMAP.md` §3.3). Nothing committed can measure a horizon effect.
   Type: `KNOWN_FACT`.
4. **The canonical schema cannot carry Lean states.** 0 of 368 real Lean states map losslessly
   (§5 above). §17.4 permits the backend-native route, so this is a gap against the *existing
   canonical pipeline*, not against the manual. Type: `KNOWN_FACT`.
5. **The one committed multi-step-looking alternative is not multi-step.** The
   `lean_runtime_v2_full` capture holds 1,150 transitions over 1,085 theorems, mean horizon
   **1.06**, and **0 of 65 adjacent pairs chain** — an elaboration-time capture
   (`docs/HAMILTONIAN_CHESS_META_MDP.md` §7). Type: `KNOWN_FACT`.
6. **The available interactive substrate is real but external and read-only-audited.** A built
   mathlib4 with a compiled `lean_dojo_repl` starts in 3.2 s and runs tactics at 193 steps/s;
   `random/train.json` holds 118,517 records, 59,557 with `traced_tactics`, 250,814 steps, and
   **1,605 theorems whose reference proof needs ≥20 tactics** (max 128)
   (`docs/VERIFIED_TRAJECTORY_ARENA_V0.md`, `docs/HAMILTONIAN_CHESS_META_MDP.md` §7). The
   `random/{val,test}` and `novel_premises/{val,test}` splits are **SEALED and were not opened**;
   they **MUST NOT** be opened outside a frozen confirmatory manifest (§30.4, §3.2). Type:
   `KNOWN_FACT`.
