"""``VerifiedTask``: the interactive environment, its failure policy, and the game property.

Three tiers:

* **pure** -- identity, sealing, cost accounting and the structural argument that ``step()``
  cannot read the reference proof.  Runs anywhere.
* **scripted** -- the task's bookkeeping driven through :class:`ScriptedArena`, a stand-in for the
  *arena seam*.  It is emphatically **not** a mock Lean: it decides nothing mathematical and every
  outcome it returns was written down by the test in advance.  It exists so the retry policy, the
  budget, the terminal vocabulary and the ``ENVIRONMENT_ERROR``-is-not-a-mathematical-failure rule
  can be exercised on a machine with no toolchain.
* **Lean-backed** -- marked ``slow``, skipped with a precise reason when the toolchain or the
  development split is absent.  Everything mathematical is here, including the one that matters:
  a non-reference action accepted by Lean.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import arena.trajectory.task as task_module
from arena.trajectory.arena_v0 import (
    ActionSpaceSpec,
    AnswerLeakageError,
    ArenaObservation,
    ArenaStep,
    BackendNativeRenderer,
)
from arena.trajectory.lean_backend import (
    LeanTheoremProbe,
    SealedSplitError,
    StepOutcome,
    TacticPolicy,
)
from arena.trajectory.schema import BackendStateEnvelope, PPScope, TerminalStatus
from arena.trajectory.task import (
    TERMINAL_OUTCOME_NAMES,
    ActionResult,
    BackendKernelContract,
    FailurePolicy,
    FailurePolicySpec,
    HashedLeakageGuard,
    ReferenceProofExposureError,
    RetryScope,
    SolvabilityAttestation,
    TaskBudget,
    TaskStateError,
    VerifiedTask,
    attest_solvable_by_replay,
    classify_backend_outcome,
    decode_action,
    seal_reference_proof,
    select_verified_tasks,
    strip_reference,
)

from . import fake_mathlib_root, find_probe, require_lean, require_train_json

# Distinctive enough that finding it inside a task would be unambiguous.
REFERENCE = (
    "nlinarith [sq_nonneg (x - y), sq_nonneg (x + y)]",
    "exact absurd hxy (ne_of_gt hlt)",
    "simpa using congrArg Nat.succ hEq",
)

OFFLINE_CONTRACT = BackendKernelContract(
    toolchain="leanprover/lean4:v4.10.0-rc1",
    lean_version_string="(offline test contract; no Lean was consulted)",
    mathlib_build_root="<offline>",
)


def make_probe(reference: Sequence[str] = REFERENCE) -> LeanTheoremProbe:
    return LeanTheoremProbe(
        problem_id="Mathlib/Fake/Task.lean::Fake.task_probe",
        full_name="Fake.task_probe",
        safe_name="Fake_task_probe",
        file_path="Mathlib/Fake/Task.lean",
        statement="theorem probe_Fake_task_probe (x y : Nat) : x + y = y + x",
        prefix_text="import Mathlib.Tactic\n\nnamespace Fake\nopen Nat\n",
        pp_scope=PPScope(current_namespace="Fake", open_declarations=("Nat",)),
        reference_tactics=tuple(reference),
    )


def make_task(
    *,
    arena: ScriptedArena | None = None,
    budget: TaskBudget | None = None,
    failure_policy: FailurePolicySpec | None = None,
    reference: Sequence[str] = REFERENCE,
) -> VerifiedTask:
    scripted = arena or ScriptedArena([])
    return VerifiedTask.from_probe(
        make_probe(reference),
        backend_kernel_contract=OFFLINE_CONTRACT,
        budget=budget or TaskBudget(model_actions=8, wall_clock_s=600.0),
        failure_policy=failure_policy,
        arena_factory=lambda: scripted,
    )


# =============================================================================================
# ScriptedArena: a stand-in for the arena seam, NOT for Lean
# =============================================================================================


@dataclass(frozen=True, slots=True)
class Scripted:
    """One pre-decided backend response.  The test wrote it; nothing was verified."""

    outcome: StepOutcome
    goal: str = "x y : Nat\n⊢ y + x = y + x"
    error: str = ""
    closes: bool = False


@dataclass(slots=True)
class ScriptedArena:
    """Deterministic stand-in for ``LeanTrajectoryArena``'s public seam.

    It mirrors the real arena's terminal bookkeeping exactly (``BACKEND_DEAD``/``TIMEOUT`` ->
    ``ERROR_BACKEND``, ``SESSION_EXPIRED`` -> ``ABANDONED``, policy refusals leave the episode
    open, an accepted step that closes goes ``CLOSED_VERIFIED``, the attempt cap goes
    ``BUDGET_EXHAUSTED``) and mirrors nothing else.  It never decides mathematics: it replays what
    the test asked for.
    """

    script: list[Scripted]
    attempt_budget: int = 8
    start_fails: bool = False
    start_goal: str = "x y : Nat\n⊢ x + y = y + x"
    default: Scripted = Scripted(StepOutcome.TACTIC_ERROR, error="scripted rejection")
    closed: bool = False
    tactics: list[str] = field(default_factory=list)
    _states: list[BackendStateEnvelope] = field(default_factory=list)
    _terminal: TerminalStatus = TerminalStatus.OPEN
    _attempts: int = 0
    _scope: PPScope = PPScope()

    # -- the seam the task drives ----------------------------------------------

    @property
    def terminal_status(self) -> TerminalStatus:
        return self._terminal

    @property
    def states(self) -> tuple[BackendStateEnvelope, ...]:
        return tuple(self._states)

    @property
    def legal_action_space(self) -> ActionSpaceSpec:
        return ActionSpaceSpec.from_policy(TacticPolicy.record_only())

    def reset(
        self, probe: LeanTheoremProbe, *, hide_reference: Sequence[str] | None = None
    ) -> ArenaObservation:
        self._scope = probe.pp_scope
        self._terminal = TerminalStatus.ERROR_BACKEND if self.start_fails else TerminalStatus.OPEN
        self._attempts = 0
        self.tactics = []
        self._states = [
            BackendStateEnvelope(
                index=0,
                state_id="s0",
                pp="" if self.start_fails else self.start_goal,
                pp_scope=self._scope,
                n_goals=0 if self.start_fails else 1,
            )
        ]
        return self._observe({})

    def step(self, tactic: str) -> ArenaStep:
        self.tactics.append(tactic)
        self._attempts += 1
        item = self.script.pop(0) if self.script else self.default
        info: dict[str, Any] = {"outcome": item.outcome.value, "wall_ms": 1}
        if item.outcome is StepOutcome.OK:
            self._states.append(
                BackendStateEnvelope(
                    index=len(self._states),
                    state_id=f"s{len(self._states)}",
                    pp=item.goal,
                    pp_scope=self._scope,
                    n_goals=0 if item.closes else 1,
                )
            )
            info.update({"tactic_head": tactic.split()[0], "no_op_suspected": False, "n_goals": 1})
            if item.closes:
                info["kernel"] = {"verified": True, "contains_sorry_ax": False}
                self._terminal = TerminalStatus.CLOSED_VERIFIED
            elif self._attempts >= self.attempt_budget:
                self._terminal = TerminalStatus.BUDGET_EXHAUSTED
        else:
            info["error"] = item.error
            if item.outcome in {StepOutcome.BACKEND_DEAD, StepOutcome.TIMEOUT}:
                self._terminal = TerminalStatus.ERROR_BACKEND
            elif item.outcome is StepOutcome.SESSION_EXPIRED:
                self._terminal = TerminalStatus.ABANDONED
            elif item.outcome in {StepOutcome.SORRY_REFUSED, StepOutcome.POLICY_REJECTED}:
                pass
            elif self._attempts >= self.attempt_budget:
                self._terminal = TerminalStatus.BUDGET_EXHAUSTED
        return ArenaStep(self._observe(info), 0.0, self._terminal, info)

    def abandon(self, reason: str) -> TerminalStatus:
        if not self._terminal.is_terminal:
            self._terminal = TerminalStatus.ABANDONED
        return self._terminal

    def close(self) -> None:
        self.closed = True

    def _observe(self, info: Mapping[str, Any]) -> ArenaObservation:
        state = self._states[-1]
        return ArenaObservation(
            step_index=len(self._states) - 1,
            state_id=state.state_id,
            rendered={"goals_pp": state.pp},
            n_goals=state.n_goals,
            attempts_remaining=max(0, self.attempt_budget - self._attempts),
            terminal_status=self._terminal,
        )


def accept(times: int = 1, *, closes: bool = False) -> list[Scripted]:
    return [
        Scripted(StepOutcome.OK, closes=closes and index == times - 1) for index in range(times)
    ]


# =============================================================================================
# The structural claim: step() cannot read the reference proof
# =============================================================================================

#: Identifiers that would give ``step()`` a path to the answer.  ``reference_seal`` is in the list
#: on purpose: the seal holds only digests, and ``step()`` still must not touch it.
FORBIDDEN_IN_STEP = frozenset(
    {
        "reference_tactics",
        "reference_proof",
        "reference_seal",
        "traced_tactics",
        "gold_tactic",
        "gold_tactics",
        "hide_reference",
        "seal_reference_proof",
        "strip_reference",
        "from_probe",
        "from_leandojo_record",
    }
)


def _class_def(tree: ast.AST, name: str) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _identifiers(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
    return found


def _reachable_identifiers(cls: ast.ClassDef, entry: str) -> set[str]:
    """Every identifier ``entry`` can reach through the class's own methods and properties."""

    members = {
        node.name: node
        for node in cls.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    seen: set[str] = set()
    pending = [entry]
    identifiers: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen or name not in members:
            continue
        seen.add(name)
        found = _identifiers(members[name])
        identifiers |= found
        pending.extend(found & members.keys())
    return identifiers


def test_step_cannot_reach_the_reference_proof_by_ast() -> None:
    """An AST proof, not a promise: nothing ``step()`` calls even names the reference proof."""

    tree = ast.parse(Path(task_module.__file__).read_text(encoding="utf-8"))
    reachable = _reachable_identifiers(_class_def(tree, "VerifiedTask"), "step")

    assert not reachable & FORBIDDEN_IN_STEP, sorted(reachable & FORBIDDEN_IN_STEP)
    # the scan really is reaching things: step() does use the arena and the leakage guard
    assert {"_require_arena", "leakage_guard", "_finish_attempt"} <= reachable


def test_the_ast_scan_would_catch_a_task_that_peeked() -> None:
    """Negative control for the scan above."""

    offender = ast.parse(
        "class VerifiedTask:\n"
        "    def step(self, a):\n"
        "        return self._cheat(a)\n"
        "    def _cheat(self, a):\n"
        "        return self.reference_tactics[0]\n"
    )
    reachable = _reachable_identifiers(_class_def(offender, "VerifiedTask"), "step")
    assert "reference_tactics" in reachable & FORBIDDEN_IN_STEP


def _reachable_objects(root: object, *, limit: int = 60_000) -> Iterable[str]:
    """Every string reachable from ``root``, including through ``__slots__`` and closures."""

    seen: set[int] = set()
    queue: list[Any] = [root]
    visited = 0
    while queue and visited < limit:
        obj = queue.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        visited += 1
        if isinstance(obj, str):
            yield obj
            continue
        if isinstance(obj, bytes | int | float | bool | type(None) | type):
            continue
        if isinstance(obj, Mapping):
            queue.extend(obj.keys())
            queue.extend(obj.values())
            continue
        if isinstance(obj, list | tuple | set | frozenset):
            queue.extend(obj)
            continue
        for cell in getattr(obj, "__closure__", None) or ():
            queue.append(cell.cell_contents)
        queue.extend(getattr(obj, "__defaults__", None) or ())
        queue.extend((getattr(obj, "__dict__", None) or {}).values())
        for klass in type(obj).__mro__:
            for slot in getattr(klass, "__slots__", ()) or ():
                if hasattr(obj, slot):
                    queue.append(getattr(obj, slot))


def test_no_reference_tactic_is_reachable_from_a_live_task() -> None:
    """The runtime half of the structural claim: the text is not in the object graph at all."""

    task = make_task()
    strings = set(_reachable_objects(task))
    assert not strings & set(REFERENCE)
    for tactic in REFERENCE:
        assert not any(tactic in item for item in strings)
    # ... and the count and digests survive, so the task still knows how long the proof was
    assert task.reference_seal.tactic_count == len(REFERENCE)
    assert len(task.reference_seal.tactic_digests) == len(REFERENCE)


def test_the_object_scan_would_catch_a_task_that_kept_the_text() -> None:
    """Negative control: a probe that still carries the proof is found, and also refused."""

    probe = make_probe()
    assert set(_reachable_objects(probe)) & set(REFERENCE)
    with pytest.raises(ReferenceProofExposureError):
        VerifiedTask(
            probe=probe,
            reference_seal=seal_reference_proof(REFERENCE)[0],
            leakage_guard=HashedLeakageGuard(),
        )


def test_stripping_a_probe_removes_only_the_reference() -> None:
    probe = make_probe()
    stripped = strip_reference(probe)
    assert stripped.reference_tactics == ()
    assert stripped.statement == probe.statement
    assert stripped.repl_source() == probe.repl_source()


def test_the_seal_is_digests_and_lengths_and_nothing_else() -> None:
    seal, guard = seal_reference_proof(REFERENCE)
    payload = json.dumps(seal.to_dict())
    for tactic in REFERENCE:
        assert tactic not in payload
    assert seal.tactic_count == 3
    assert all(len(digest) == 64 for digest in seal.tactic_digests)
    assert seal.tactic_byte_lengths == tuple(len(t.encode()) for t in REFERENCE)
    assert guard.armed


# =============================================================================================
# The hashed leakage guard: recognises the answer without holding it
# =============================================================================================


def test_the_guard_detects_a_leaked_tactic_and_cannot_reveal_it() -> None:
    _, guard = seal_reference_proof(REFERENCE)
    payload = f'{{"goals_pp": "x y : Nat\\n{REFERENCE[0]}"}}'
    digest = guard.find_leak(payload)
    assert digest is not None
    with pytest.raises(AnswerLeakageError) as caught:
        guard.assert_clean(payload, where="the observation")
    message = str(caught.value)
    assert REFERENCE[0] not in message
    assert digest[:16] in message


def test_the_guard_passes_an_ordinary_observation() -> None:
    _, guard = seal_reference_proof(REFERENCE)
    guard.assert_clean('{"goals_pp": "x y : Nat\\n\\u22a2 x + y = y + x"}', where="the observation")


def test_short_secrets_are_not_registered() -> None:
    """``rfl`` occurs inside goal text by coincidence; the measured filter uses the same bound."""

    _, guard = seal_reference_proof(("rfl", "omega"))
    assert not guard.armed


def test_a_task_refuses_to_show_an_observation_containing_the_answer() -> None:
    arena = ScriptedArena([Scripted(StepOutcome.OK, goal=f"⊢ P\n-- hint: {REFERENCE[0]}")])
    task = make_task(arena=arena)
    task.reset()
    with pytest.raises(AnswerLeakageError):
        task.step("intro h")


# =============================================================================================
# Task identity and descriptor
# =============================================================================================


def test_task_id_is_deterministic_and_excludes_the_renderer() -> None:
    """Two candidate languages must be able to play the *same* task."""

    class Shouty:
        renderer_id = "shouty-v0"

        def render(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
            return {"renderer_id": self.renderer_id, "G": state.pp.upper()}

    first = make_task()
    twin = make_task()
    other_language = VerifiedTask.from_probe(
        make_probe(),
        backend_kernel_contract=OFFLINE_CONTRACT,
        budget=TaskBudget(model_actions=8, wall_clock_s=600.0),
        renderer=Shouty(),
        arena_factory=lambda: ScriptedArena([]),
    )
    assert first.task_id == twin.task_id == other_language.task_id
    assert first.task_id.startswith("vtask-")
    assert "renderer" not in json.dumps(first.semantic_core())


def test_task_id_changes_with_the_budget_and_the_failure_policy() -> None:
    strict = make_task(
        failure_policy=FailurePolicySpec(policy=FailurePolicy.TERMINATE_ON_FIRST_INVALID)
    )
    lenient = make_task(failure_policy=FailurePolicySpec(max_retries=3))
    bigger = make_task(budget=TaskBudget(model_actions=99))
    assert len({strict.task_id, lenient.task_id, bigger.task_id}) == 3


def test_the_descriptor_carries_the_manual_17_1_fields_and_no_answer() -> None:
    descriptor = make_task().descriptor()
    for key in (
        "task_id",
        "problem_id",
        "source_system",
        "source_hash",
        "backend_kernel_contract",
        "initial_state_ref",
        "action_interface",
        "verifier_adapter",
        "terminal_predicate",
        "budget",
        "failure_policy",
        "provenance",
        "state_identity_scheme",
    ):
        assert key in descriptor, key
    assert descriptor["mode"] == "INTERACTIVE_TASK"
    payload = json.dumps(descriptor)
    for tactic in REFERENCE:
        assert tactic not in payload


def test_the_initial_state_ref_is_computable_without_starting_lean() -> None:
    ref = make_task().initial_state_ref
    assert ref.full_name == "Fake.task_probe"
    assert len(ref.statement_digest) == 64
    assert len(ref.prefix_digest) == 64


def test_the_failure_policy_is_declared_and_defaults_to_one_retry() -> None:
    """Declared before any Solver performance was observed; option (b) of the directive."""

    policy = make_task().failure_policy
    assert policy.policy is FailurePolicy.ONE_DIAGNOSTIC_RETRY
    assert policy.max_retries == 1
    assert policy.effective_retries == 1
    assert policy.scope is RetryScope.PER_CONSECUTIVE_RUN
    assert policy.declared_before_measurement


# =============================================================================================
# Action decoding and outcome classification
# =============================================================================================


def test_decode_rejects_what_is_not_an_action_and_passes_everything_else() -> None:
    assert decode_action("simp [Nat.add_comm]") == ("simp [Nat.add_comm]", "")
    assert decode_action("")[0] is None
    assert decode_action("   ")[0] is None
    assert decode_action(42)[0] is None
    assert decode_action("intro\x00h")[0] is None
    # deliberately NOT rejected here: Lean decides whether this is legal
    assert decode_action("this is not lean at all")[0] == "this is not lean at all"


def test_every_backend_outcome_lowers_into_the_manual_vocabulary() -> None:
    for outcome in StepOutcome:
        assert isinstance(classify_backend_outcome(outcome.value), ActionResult)


def test_only_a_verifier_rejection_is_a_mathematical_failure() -> None:
    assert ActionResult.REJECTED_INVALID_ACTION.is_mathematical_failure
    for result in ActionResult:
        if result is not ActionResult.REJECTED_INVALID_ACTION:
            assert not result.is_mathematical_failure
    assert not ActionResult.ENVIRONMENT_ERROR.is_mathematical_failure
    assert not ActionResult.ENVIRONMENT_ERROR.attributable_to_solver
    assert not ActionResult.TOOL_TIMEOUT.attributable_to_solver
    assert ActionResult.UNSUPPORTED.attributable_to_solver


def test_every_terminal_status_has_a_manual_name() -> None:
    assert set(TERMINAL_OUTCOME_NAMES) == set(TerminalStatus)


# =============================================================================================
# Scripted: reset, transitions, terminals
# =============================================================================================


def test_reset_is_deterministic_and_re_elaboration_stable() -> None:
    task = make_task(arena=ScriptedArena([]))
    first = task.reset()
    start_first = task.state_identity()
    second = task.reset()
    start_second = task.state_identity()

    assert dict(first.rendered) == dict(second.rendered)
    assert first.identity.projection_hash == second.identity.projection_hash
    assert start_first.same_after_reelaboration_as(start_second)
    # a new session's handles address new live states: the kernel key must NOT be reused
    assert not start_first.same_kernel_state_as(start_second)
    assert task.episode_index == 2


def test_an_accepted_transition_advances_the_state_and_is_typed() -> None:
    task = make_task(arena=ScriptedArena(accept(1)))
    task.reset()
    before = task.state_identity()
    outcome = task.step("omega")

    assert outcome.result is ActionResult.ACCEPTED_TRANSITION
    assert outcome.advanced
    assert not outcome.done
    assert outcome.terminal_status is TerminalStatus.OPEN
    assert outcome.terminal_outcome == "OPEN"
    assert not outcome.state_identity.same_kernel_state_as(before)
    assert outcome.cost.kernel_step_count == 1
    assert outcome.cost.lowered_action_count == 1


def test_a_closing_transition_is_verified_solved_with_reward_one() -> None:
    task = make_task(arena=ScriptedArena(accept(2, closes=True)))
    task.reset()
    task.step("intro h")
    outcome = task.step("omega")

    assert outcome.terminal_status is TerminalStatus.CLOSED_VERIFIED
    assert outcome.terminal_outcome == "VERIFIED_SOLVED"
    assert outcome.reward == 1.0
    assert task.is_terminal()
    # closing costs a second verifier call: the separate `#print axioms` re-elaboration
    assert outcome.cost.verifier_call_count == 2


def test_an_invalid_action_is_rejected_with_the_right_typed_result() -> None:
    arena = ScriptedArena([Scripted(StepOutcome.TACTIC_ERROR, error="unknown identifier 'foo'")])
    task = make_task(arena=arena)
    task.reset()
    before = task.state_identity()
    outcome = task.step("exact foo")

    assert outcome.result is ActionResult.REJECTED_INVALID_ACTION
    assert outcome.result.is_mathematical_failure
    assert not outcome.advanced
    assert outcome.state_identity.same_kernel_state_as(before)
    assert outcome.diagnostic == "unknown identifier 'foo'"
    assert outcome.cost.kernel_step_count == 0
    assert outcome.cost.lowered_action_count == 1


def test_a_parse_failure_never_reaches_the_backend() -> None:
    arena = ScriptedArena(accept(1))
    task = make_task(arena=arena)
    task.reset()
    outcome = task.step("")

    assert outcome.result is ActionResult.PARSE_FAILURE
    assert outcome.backend_outcome == "NOT_LOWERED"
    assert outcome.cost.lowered_action_count == 0
    assert outcome.cost.verifier_call_count == 0
    assert arena.tactics == []


def test_an_out_of_interface_action_is_unsupported_not_a_mathematical_failure() -> None:
    arena = ScriptedArena([Scripted(StepOutcome.SORRY_REFUSED, error="`sorry` is refused")])
    task = make_task(arena=arena)
    task.reset()
    outcome = task.step("sorry")

    assert outcome.result is ActionResult.UNSUPPORTED
    assert not outcome.result.is_mathematical_failure
    assert outcome.result.attributable_to_solver


def test_environment_error_is_distinct_from_mathematical_failure() -> None:
    """Manual §14.4 / §28: a dead backend is never scored against the policy."""

    arena = ScriptedArena([Scripted(StepOutcome.BACKEND_DEAD, error="lean exited with 1")])
    task = make_task(arena=arena)
    task.reset()
    outcome = task.step("simp")

    assert outcome.result is ActionResult.ENVIRONMENT_ERROR
    assert not outcome.result.is_mathematical_failure
    assert not outcome.result.attributable_to_solver
    assert outcome.terminal_status is TerminalStatus.ERROR_BACKEND
    assert outcome.terminal_outcome == "ENVIRONMENT_ERROR"
    assert outcome.reward == 0.0
    # the retry allowance is untouched: the Solver did nothing wrong
    assert outcome.retries_remaining == 1


def test_a_tool_timeout_is_named_separately_from_an_environment_error() -> None:
    arena = ScriptedArena([Scripted(StepOutcome.TIMEOUT, error="step timed out after 60s")])
    task = make_task(arena=arena)
    task.reset()
    outcome = task.step("decide")

    assert outcome.result is ActionResult.TOOL_TIMEOUT
    assert outcome.terminal_status is TerminalStatus.ERROR_BACKEND
    assert outcome.terminal_outcome == "TOOL_TIMEOUT"
    assert not outcome.result.is_mathematical_failure


def test_a_failed_session_start_is_an_environment_error() -> None:
    task = make_task(arena=ScriptedArena([], start_fails=True))
    task.reset()
    assert task.terminal_status() is TerminalStatus.ERROR_BACKEND
    assert task.terminal_outcome() == "ENVIRONMENT_ERROR"


def test_abandoning_an_episode_is_not_a_failure() -> None:
    task = make_task(arena=ScriptedArena(accept(1)))
    task.reset()
    task.step("intro h")
    assert task.abandon("scripted policy ran out of moves") is TerminalStatus.ABANDONED
    assert task.terminal_outcome() == "EPISODE_ABANDONED"


def test_stepping_a_terminal_episode_raises_rather_than_relabelling_it() -> None:
    task = make_task(arena=ScriptedArena(accept(1, closes=True)))
    task.reset()
    task.step("omega")
    with pytest.raises(TaskStateError):
        task.step("omega")


def test_stepping_before_reset_raises() -> None:
    with pytest.raises(TaskStateError):
        make_task().step("omega")


# =============================================================================================
# The retry policy, behaving exactly as declared
# =============================================================================================


def test_one_diagnostic_retry_gives_exactly_one_retry() -> None:
    arena = ScriptedArena(
        [
            Scripted(StepOutcome.TACTIC_ERROR, error="first rejection"),
            Scripted(StepOutcome.TACTIC_ERROR, error="second rejection"),
        ]
    )
    task = make_task(arena=arena)
    task.reset()

    first = task.step("exact foo")
    assert first.terminal_status is TerminalStatus.OPEN
    assert first.retries_remaining == 0
    assert first.diagnostic == "first rejection"

    second = task.step("exact bar")
    assert second.terminal_status is TerminalStatus.FAILED
    assert second.terminal_outcome == "UNRECOVERABLE_INVALID_ACTION"
    assert task.is_terminal()


def test_an_accepted_transition_restores_the_retry_allowance() -> None:
    arena = ScriptedArena(
        [
            Scripted(StepOutcome.TACTIC_ERROR, error="a"),
            Scripted(StepOutcome.OK),
            Scripted(StepOutcome.TACTIC_ERROR, error="b"),
        ]
    )
    task = make_task(arena=arena)
    task.reset()
    assert task.step("exact foo").retries_remaining == 0
    assert task.step("intro h").retries_remaining == 1
    third = task.step("exact bar")
    assert third.terminal_status is TerminalStatus.OPEN
    assert third.retries_remaining == 0


def test_per_episode_scope_does_not_restore_the_allowance() -> None:
    arena = ScriptedArena(
        [
            Scripted(StepOutcome.TACTIC_ERROR, error="a"),
            Scripted(StepOutcome.OK),
            Scripted(StepOutcome.TACTIC_ERROR, error="b"),
        ]
    )
    task = make_task(arena=arena, failure_policy=FailurePolicySpec(scope=RetryScope.PER_EPISODE))
    task.reset()
    task.step("exact foo")
    task.step("intro h")
    assert task.step("exact bar").terminal_status is TerminalStatus.FAILED


def test_terminate_on_first_invalid_ends_the_episode_immediately() -> None:
    arena = ScriptedArena([Scripted(StepOutcome.TACTIC_ERROR, error="nope")])
    task = make_task(
        arena=arena,
        failure_policy=FailurePolicySpec(policy=FailurePolicy.TERMINATE_ON_FIRST_INVALID),
    )
    task.reset()
    outcome = task.step("exact foo")
    assert outcome.terminal_status is TerminalStatus.FAILED
    assert outcome.retries_remaining == 0


def test_the_failure_policy_never_terminates_on_a_harness_fault() -> None:
    """Two consecutive backend deaths would exhaust a retry allowance if they counted."""

    arena = ScriptedArena([Scripted(StepOutcome.SESSION_EXPIRED, error="lifetime cap")])
    task = make_task(arena=arena)
    task.reset()
    outcome = task.step("simp")
    assert outcome.result is ActionResult.ENVIRONMENT_ERROR
    assert outcome.terminal_status is TerminalStatus.ABANDONED
    assert outcome.retries_remaining == 1


def test_the_diagnostic_is_one_minimal_line_and_is_truncated() -> None:
    arena = ScriptedArena(
        [Scripted(StepOutcome.TACTIC_ERROR, error="x" * 900 + "\nsecond line of the trace")]
    )
    task = make_task(arena=arena)
    task.reset()
    diagnostic = task.step("exact foo").diagnostic
    assert len(diagnostic) == 401
    assert "second line" not in diagnostic


# =============================================================================================
# Budget and cost (manual §13.1)
# =============================================================================================


def test_budget_exhaustion_terminates_the_episode() -> None:
    arena = ScriptedArena(accept(3), attempt_budget=3)
    task = make_task(arena=arena, budget=TaskBudget(model_actions=3, wall_clock_s=600.0))
    task.reset()
    task.step("intro a")
    task.step("intro b")
    last = task.step("intro c")

    assert last.terminal_status is TerminalStatus.BUDGET_EXHAUSTED
    assert last.terminal_outcome == "SEARCH_BUDGET_EXHAUSTED"
    assert last.reward == 0.0
    assert task.attempts_remaining == 0


def test_the_wall_clock_budget_terminates_the_episode() -> None:
    arena = ScriptedArena(accept(1))
    task = make_task(arena=arena, budget=TaskBudget(model_actions=8, wall_clock_s=1e-9))
    task.reset()
    outcome = task.step("intro h")
    assert outcome.terminal_status is TerminalStatus.BUDGET_EXHAUSTED
    assert arena.terminal_status is TerminalStatus.ABANDONED  # documented divergence


def test_the_six_cost_counters_stay_separate_and_tokens_are_typed_slots() -> None:
    arena = ScriptedArena([Scripted(StepOutcome.TACTIC_ERROR, error="no"), *accept(2, closes=True)])
    task = make_task(arena=arena)
    task.reset()
    task.step("exact foo")
    task.step("intro h")
    task.step("omega")

    cost = task.cost.to_dict()
    assert cost["model_action_count"] == 3
    assert cost["lowered_action_count"] == 3
    assert cost["kernel_step_count"] == 2
    assert cost["verifier_call_count"] == 4
    assert cost["tool_call_count"] == 4
    assert cost["wall_clock_s"] >= 0.0
    assert cost["prompt_tokens"] is None
    assert cost["completion_tokens"] is None
    assert cost["total_tokens"] is None
    assert len(cost["per_action"]) == 3
    # never flattened into "steps"
    assert "steps" not in cost


def test_the_episode_report_is_self_describing() -> None:
    task = make_task(arena=ScriptedArena(accept(1, closes=True)))
    task.reset()
    task.step("omega")
    report = task.episode_report().to_dict()

    assert report["terminal_outcome"] == "VERIFIED_SOLVED"
    assert report["reward"] == 1.0
    assert report["actions_attempted"] == 1
    assert report["actions_accepted"] == 1
    assert report["reference_tactic_count"] == 3
    assert report["failure_policy"]["policy"] == "ONE_DIAGNOSTIC_RETRY"
    assert report["renderer_id"] == BackendNativeRenderer().renderer_id
    assert len(report["action_log"]) == 1


# =============================================================================================
# Task selection: deterministic, seeded, sealed splits refused
# =============================================================================================


def _write_split(tmp_path: Path, records: list[dict[str, Any]], name: str) -> Path:
    path = tmp_path / "leandojo" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_the_selector_refuses_every_sealed_split(tmp_path: Path) -> None:
    for sealed in ("random/val.json", "random/test.json"):
        path = tmp_path / sealed
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(SealedSplitError):
            select_verified_tasks(train_json=path, limit=1, scan_limit=1)


def test_the_selector_is_deterministic_and_filters_by_reference_length(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=10)
    for index, record in enumerate(records):
        record["traced_tactics"] = record["traced_tactics"][: 1 + index % 5]
    split = _write_split(tmp_path, records, "train.json")

    def run(seed: int, low: int, high: int | None) -> tuple[str, ...]:
        selection = select_verified_tasks(
            train_json=split,
            mathlib_root=root,
            backend_kernel_contract=OFFLINE_CONTRACT,
            min_reference_length=low,
            max_reference_length=high,
            limit=4,
            seed=seed,
            scan_limit=10,
        )
        assert all(low <= t.reference_seal.tactic_count for t in selection)
        if high is not None:
            assert all(t.reference_seal.tactic_count <= high for t in selection)
        return tuple(task.task_id for task in selection)

    assert run(7, 1, None) == run(7, 1, None)
    assert run(7, 1, None) != run(11, 1, None)
    easy = run(7, 1, 2)
    hard = run(7, 4, None)
    assert easy and hard
    assert set(easy).isdisjoint(hard)


def test_selected_tasks_carry_provenance_and_no_answer(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=3)
    split = _write_split(tmp_path, records, "train.json")
    selection = select_verified_tasks(
        train_json=split,
        mathlib_root=root,
        backend_kernel_contract=OFFLINE_CONTRACT,
        limit=3,
        seed=5,
        scan_limit=3,
    )
    manifest = selection.manifest()
    assert manifest["records_scanned"] == 3
    assert "random/val.json" in manifest["sealed_splits_not_read"]
    assert "HISTORICALLY_EXPOSED" in manifest["contamination"]
    for task in selection:
        assert task.source_version is not None
        assert task.source_version.split == "train"
        assert task.reference_seal.solvability is SolvabilityAttestation.ASSERTED_BY_SOURCE
        assert task.provenance.static_leakage_filters == ("NONE_TRIPPED",)
        assert "step_0" not in json.dumps(task.descriptor())


# =============================================================================================
# Lean-backed: the game property and the real verdicts
# =============================================================================================


def _live_task(record: dict[str, Any], probe: LeanTheoremProbe, **kwargs: Any) -> VerifiedTask:
    return VerifiedTask.from_leandojo_record(record, probe, **kwargs)


@pytest.mark.slow
def test_reset_is_deterministic_against_live_lean() -> None:
    require_lean()
    require_train_json()
    record, probe = find_probe(1, 3)
    with _live_task(record, probe) as task:
        first = task.reset()
        # a session that failed to start would satisfy the equalities below vacuously
        assert task.terminal_status() is TerminalStatus.OPEN
        assert str(first.rendered["goals_pp"]).strip()
        start_first = task.state_identity()
        second = task.reset()
        assert task.terminal_status() is TerminalStatus.OPEN
        start_second = task.state_identity()

    assert dict(first.rendered) == dict(second.rendered)
    assert start_first.same_after_reelaboration_as(start_second)
    assert not start_first.same_kernel_state_as(start_second)
    assert first.identity.projection_hash == second.identity.projection_hash


@pytest.mark.slow
def test_lean_accepts_an_alternative_non_reference_action() -> None:
    """The game property (manual §17.3, §14.6): Lean decides, not the transcript.

    The *test* knows the reference proof and asserts the accepted action is not in it.  The
    *task* never did: it holds only digests, so it could not have consulted the answer even if
    the implementation had wanted to.
    """

    require_lean()
    require_train_json()
    record, probe = find_probe(2, 6)
    reference = set(probe.reference_tactics)
    candidates = [
        candidate
        for candidate in ("norm_num", "simp", "omega", "constructor", "intro h", "skip")
        if candidate not in reference
    ]

    accepted: str | None = None
    with _live_task(
        record, probe, failure_policy=FailurePolicySpec(max_retries=len(candidates) + 1)
    ) as task:
        before = task.reset()
        start = task.state_identity()
        for candidate in candidates:
            outcome = task.step(candidate)
            if outcome.result is ActionResult.ACCEPTED_TRANSITION:
                accepted = candidate
                assert not outcome.state_identity.same_kernel_state_as(start)
                assert outcome.cost.kernel_step_count == 1
                break
            assert outcome.result in {
                ActionResult.REJECTED_INVALID_ACTION,
                ActionResult.UNSUPPORTED,
            }
            if outcome.done:
                break
        assert before is not None

    if accepted is None:  # pragma: no cover - depends on which theorem was sampled
        pytest.skip(f"no generic alternative was legal at {probe.problem_id}")
    assert accepted not in reference


@pytest.mark.slow
def test_lean_rejects_a_bogus_action_and_the_task_types_it() -> None:
    require_lean()
    require_train_json()
    record, probe = find_probe(1, 4)
    with _live_task(record, probe) as task:
        task.reset()
        before = task.state_identity()
        outcome = task.step("exact hamiltonian_chess_no_such_lemma_v0")

    assert outcome.result is ActionResult.REJECTED_INVALID_ACTION
    assert outcome.result.is_mathematical_failure
    assert outcome.diagnostic
    assert outcome.state_identity.same_kernel_state_as(before)


@pytest.mark.slow
def test_sorry_is_unsupported_against_live_lean() -> None:
    require_lean()
    require_train_json()
    record, probe = find_probe(1, 4)
    with _live_task(record, probe) as task:
        task.reset()
        outcome = task.step("sorry")

    assert outcome.result is ActionResult.UNSUPPORTED
    assert not outcome.result.is_mathematical_failure


@pytest.mark.slow
def test_solvability_is_attested_by_replaying_the_reference_once() -> None:
    """Construction-time reason (a): knowing the task is solvable.  Costs one Lean session."""

    require_lean()
    require_train_json()
    record, probe = find_probe(1, 3)
    attestation, detail = attest_solvable_by_replay(record, probe)

    assert attestation in {
        SolvabilityAttestation.REFERENCE_REPLAY_CLOSED_VERIFIED,
        SolvabilityAttestation.REFERENCE_REPLAY_DID_NOT_CLOSE,
    }
    assert detail
    # the attestation carries no tactic text back to the caller
    for tactic in probe.reference_tactics:
        assert tactic not in detail

    task = VerifiedTask.from_leandojo_record(record, probe, attest_by_replay=True)
    try:
        assert task.reference_seal.solvability is attestation
        assert not set(_reachable_objects(task)) & set(probe.reference_tactics)
    finally:
        task.close()


@pytest.mark.slow
def test_an_episode_can_be_emitted_as_a_solver_trajectory() -> None:
    """The documented divergence: the task says FAILED, the record says ABANDONED and why."""

    require_lean()
    require_train_json()
    record, probe = find_probe(1, 3)
    with _live_task(record, probe) as task:
        task.reset()
        task.step("exact hamiltonian_chess_no_such_lemma_v0")
        task.step("exact still_not_a_lemma_v0")
        assert task.terminal_status() is TerminalStatus.FAILED
        trajectory = task.emit_trajectory()

    assert trajectory.terminal_status is TerminalStatus.ABANDONED
    assert f"task_terminal_status={TerminalStatus.FAILED.value}" in trajectory.provenance.notes
    assert "task_terminal_outcome=UNRECOVERABLE_INVALID_ACTION" in trajectory.provenance.notes
    assert trajectory.is_single_actor
    assert trajectory.horizon.reference == task.reference_seal.tactic_count
    payload = json.dumps(trajectory.to_dict())
    for tactic in probe.reference_tactics:
        assert tactic not in payload


@pytest.mark.slow
def test_the_selector_builds_real_tasks_deterministically() -> None:
    require_lean()
    train = require_train_json()

    def run(seed: int) -> tuple[str, ...]:
        selection = select_verified_tasks(
            train_json=train,
            min_reference_length=2,
            max_reference_length=4,
            limit=3,
            seed=seed,
            scan_limit=400,
        )
        return tuple(task.task_id for task in selection)

    assert run(20260908) == run(20260908)
