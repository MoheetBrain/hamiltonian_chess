# HC-V0.5 — Interactive Task Specification

Implements manual §6.25 / §17's distinction between a **`VerifiedTask`** (an interactive
environment) and a **`VerifiedTrajectory`** (one recorded path). Before HC-V0.5 only the latter
existed, so the world could be replayed but not played.

Code: `arena/trajectory/task.py`, `arena/trajectory/state_identity.py`,
`arena/trajectory/episode.py`. Backend: `arena/trajectory/lean_backend.py` (unchanged interface).

---

## 1. The object

```
VerifiedTask {
  task_id                    # excludes the renderer, so two languages provably play the same task
  problem_id, source_system, source_version, source_hash
  backend_kernel_contract    # Lean 4.10.0-rc1 + mathlib 29dcec07…
  initial_state_ref, state_identity_scheme
  action_interface           # one Lean tactic string
  verifier_adapter, terminal_predicate
  budget, failure_policy
  reference_seal             # digests only — never the text
  workspace_kind, intervention_class, renderer_id
  mode = INTERACTIVE_TASK
  provenance
}
```

`reset() → WorkspaceProjection` · `observe() → WorkspaceProjection` · `step(action) →
TaskStepResult` · `state_identity()` · `is_terminal()` · `terminal_status()` ·
`terminal_outcome()` · `abandon()` · `episode_report()` · `emit_trajectory()`.

The renderer is **injected**, defaulting to the backend-native one: it is `Ω_L`'s seam, and it is
what a future language assay will vary.

## 2. The defining property

**The Solver may propose an action that is not the reference proof action, and Lean decides.**
Measured independently before any of this was built
(`research/phase9/interactive_probe/probe_non_reference_actions.py`): across 14 theorems Lean
accepted a non-reference tactic in **10**, and in **2** an alternative closed a goal that mathlib
proves differently. That is the difference between imitation and a game.

## 3. Action results — every attempt is typed

`ACCEPTED_TRANSITION` · `REJECTED_INVALID_ACTION` · `PARSE_FAILURE` · `TOOL_TIMEOUT` ·
`ENVIRONMENT_ERROR` · `UNSUPPORTED`.

`is_mathematical_failure` is true **only** for `REJECTED_INVALID_ACTION`.
`attributable_to_solver` is false for `ENVIRONMENT_ERROR` and `TOOL_TIMEOUT`. Manual §14.4 and §28
require that infrastructure failure is never scored as mathematical failure, and the type system
carries that rather than a convention. Every backend `StepOutcome` lowers into exactly one result;
an unmapped outcome raises rather than defaulting to something reassuring.

Terminal mapping: `CLOSED_VERIFIED→VERIFIED_SOLVED`, `BUDGET_EXHAUSTED→SEARCH_BUDGET_EXHAUSTED`,
`FAILED→UNRECOVERABLE_INVALID_ACTION`, `ERROR_BACKEND→ENVIRONMENT_ERROR`/`TOOL_TIMEOUT`,
`ABANDONED→EPISODE_ABANDONED`.

## 4. Failure policy — declared before any performance was observed

**`ONE_DIAGNOSTIC_RETRY`, `max_retries=1`, scope `PER_CONSECUTIVE_RUN`**, stamped into provenance
and into `task_id` with `declared_before_measurement=True`. The alternative
(`TERMINATE_ON_FIRST_INVALID`) is an explicit enum member, so the choice is visible rather than
implicit. Harness faults never consume the allowance.

**Known defect, measured in the first run:** the diagnostic does not reach the Solver (the prompt
reads only `goals_pp`) and decoding is deterministic, so the retry re-proposes the identical
tactic. The policy is currently a no-op that doubles the rejection count. See
`docs/HC_V0_5_RESULT.md` §4.

## 5. Cost accounting (manual §13.1)

Six counters, per action and per episode, **never flattened**: `model_action_count`,
`lowered_action_count`, `kernel_step_count`, `verifier_call_count`, `tool_call_count`,
`wall_clock_s`. Token slots (`prompt_tokens`, `completion_tokens`, `total_tokens`) are typed and
filled by the Solver adapter. This is what stops an action macro bundling many kernel operations
into one model-facing move and appearing cheap.

## 6. The two identities

**`KernelStateIdentity`** — which backend state is this?
`kernel_key` (backend | session | state id) is scope-independent and identifies a re-enterable
state; `reelaboration_key` (backend | scope digest | goal digest) survives re-elaboration in a
fresh session; `record_key` binds a stored episode. Digests are over normalised text bound to a
canonical scope, and the normalisation is **named inside the identity** so a future change is
visible rather than silent. It is **not** a semantic-equality decision procedure: a mismatch means
UNKNOWN, never "different" — which is why `univ` under `open Finset` and bare `Finset.univ` are
handled honestly rather than by string comparison.

**`WorkspaceProjectionIdentity`** — which declared information reached the language?
`projection_hash` is a function of the workspace kind, the declared **slots** and their values —
and **excludes** the renderer id and the rendered bytes. So two `R_ONLY` languages produce the
same projection hash with different bytes, which is exactly the parity precondition of manual
§12.3. `check_projection_parity(left, right, intervention_class)` requires parity only for
`R_ONLY`; for `P_CHANGE`/`O_CHANGE`/`A_CHANGE` a difference **is the intervention**, not a fault.

Full treatment: `docs/LEAN_BACKEND_STATE_IDENTITY_V0.md`.

## 7. Why Lean is not forced through the canonical schema

`arena-canonical-v0.1.0` maps **0 of 368** sampled real Lean states losslessly (79.3% lossy, 20.7%
unmappable). Manual §17.4 permits backend-native truth, and `DerivedView.canonical_state` is typed
**`None`** rather than `dict | None` — the type system, not a comment, refuses to claim a
projection that does not exist. **LOSSLESS_FIRST, ABSTRACT_LATER.**

## 8. Data firewall

Tasks come from the LeanDojo **train** split only
(`…/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json`).
`assert_not_sealed` runs **before any I/O** and refuses all four sealed splits. Selection is a pure
function of `(train_json, scan_limit, length filters, policy, seed)` and filters only on *recorded*
proof length — a difficulty proxy, never Solver performance, and never `MinimalProofLength`, which
stays `UNKNOWN` (§6.34, §17.6).

No OOD claim is available and none is made: mathlib4 is `HISTORICALLY_EXPOSED` and exposure is
transitive.
