"""V05-01 and V05-03: who chose the action, and what they were looking at when they chose it.

Two HIGH provenance defects are closed here and each test says, in its own docstring, what goes
back to being true if the fix is reverted.  Both defects were about the *record*, not the
environment: the reference proof was already sealed away from the task, but nothing in the emitted
artefact separated an oracle-fed episode from an autonomous one.

* **V05-03** -- ``LeanTrajectoryArena.build_trajectory`` rewrote every action's actor to whatever
  the caller asked for, so a five-action replay of a recorded mathlib proof could be resealed as a
  five-action Solver result and pass ``verify_bank`` both structurally and under ``--relive``.
  The actor is now stamped at the moment of choice from the arena's own ``actor``, and
  ``build_trajectory`` *asserts* the caller's claim.
* **V05-01** -- nothing recorded where a tactic came from.
  :class:`~arena.trajectory.schema.ActionEvidence` binds an action to a policy identity, the
  prompt bytes, the decoding parameters and the exact projection the task handed out; the task
  refuses an action whose observation digest disagrees, and both ``build_trajectory`` and
  ``verify_bank`` refuse a ``SOLVER`` claim over actions with no binding.

The limit is stated once in ``ActionEvidence`` and is worth repeating where the tests live: none
of this cryptographically proves that a black-box model emitted a token.  It binds the action to a
specific policy identity and a specific observed state, makes that binding re-derivable by a
reader, and makes an evidence-free ``SOLVER`` claim structurally impossible.

Nothing here calls a model: the Solver used end to end is :class:`ScriptedSolver`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from arena.trajectory.arena_v0 import (
    ActionSpaceSpec,
    ArenaObservation,
    ArenaStep,
    BackendNativeRenderer,
    LeanTrajectoryArena,
    verify_bank,
)
from arena.trajectory.episode import action_evidence_for, run_episode
from arena.trajectory.lean_backend import LeanTheoremProbe, StepOutcome, TacticPolicy
from arena.trajectory.schema import (
    ActionEvidence,
    ActionProvenanceError,
    Actor,
    BackendStateEnvelope,
    PPScope,
    TerminalStatus,
    TrajectoryIntegrityError,
    VerifiedTrajectory,
)
from arena.trajectory.solver import ScriptedSolver
from arena.trajectory.task import (
    BackendKernelContract,
    TaskBudget,
    VerifiedTask,
    observation_digest_of,
)

from . import find_probe, require_lean, require_train_json
from .test_schema import make_trajectory

REFERENCE = (
    "nlinarith [sq_nonneg (x - y), sq_nonneg (x + y)]",
    "exact absurd hxy (ne_of_gt hlt)",
)

OFFLINE_CONTRACT = BackendKernelContract(
    toolchain="leanprover/lean4:v4.10.0-rc1",
    lean_version_string="(offline test contract; no Lean was consulted)",
    mathlib_build_root="<offline>",
)


# =============================================================================================
# Offline scaffolding: an arena seam that understands evidence, and nothing mathematical
# =============================================================================================


@dataclass(frozen=True, slots=True)
class Scripted:
    """One pre-decided backend response.  The test wrote it; nothing was verified."""

    outcome: StepOutcome
    goal: str = "x y : Nat\n⊢ y + x = y + x"
    error: str = ""


@dataclass(slots=True)
class EvidenceAwareArena:
    """The arena seam a task drives, plus the ``evidence`` keyword the real arena now takes.

    It decides nothing mathematical: every outcome was written down by the test in advance.  It
    exists so the *binding* can be exercised on a machine with no toolchain; the Lean-backed
    tests below are where anything is actually verified.
    """

    script: list[Scripted]
    attempt_budget: int = 8
    evidence_seen: list[ActionEvidence | None] = field(default_factory=list)
    closed: bool = False
    _states: list[BackendStateEnvelope] = field(default_factory=list)
    _terminal: TerminalStatus = TerminalStatus.OPEN
    _scope: PPScope = PPScope()
    _attempts: int = 0

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
        self._terminal = TerminalStatus.OPEN
        self._attempts = 0
        self._states = [
            BackendStateEnvelope(
                index=0, state_id="s0", pp="x y : Nat\n⊢ x + y = y + x", pp_scope=self._scope
            )
        ]
        return self._observe({})

    def step(self, tactic: str, *, evidence: ActionEvidence | None = None) -> ArenaStep:
        self.evidence_seen.append(evidence)
        self._attempts += 1
        item = self.script.pop(0) if self.script else Scripted(StepOutcome.TACTIC_ERROR, error="no")
        info: dict[str, Any] = {
            "outcome": item.outcome.value,
            "wall_ms": 1,
            "action_evidence": "ABSENT" if evidence is None else "PRESENT",
        }
        if item.outcome is StepOutcome.OK:
            self._states.append(
                BackendStateEnvelope(
                    index=len(self._states),
                    state_id=f"s{len(self._states)}",
                    pp=item.goal,
                    pp_scope=self._scope,
                )
            )
            info.update({"tactic_head": tactic.split()[0], "no_op_suspected": False, "n_goals": 1})
            if self._attempts >= self.attempt_budget:
                self._terminal = TerminalStatus.BUDGET_EXHAUSTED
        else:
            info["error"] = item.error
        return ArenaStep(self._observe(info), 0.0, self._terminal, info)

    def abandon(self, reason: str) -> TerminalStatus:
        if not self._terminal.is_terminal:
            self._terminal = TerminalStatus.ABANDONED
        return self._terminal

    def close(self) -> None:
        self.closed = True

    def _observe(self, info: dict[str, Any]) -> ArenaObservation:
        envelope = self._states[-1]
        return ArenaObservation(
            step_index=len(self._states) - 1,
            state_id=envelope.state_id,
            rendered=BackendNativeRenderer().render(envelope),
            n_goals=envelope.n_goals,
            attempts_remaining=max(0, self.attempt_budget - self._attempts),
            terminal_status=self._terminal,
        )


def make_probe(reference: Sequence[str] = REFERENCE) -> LeanTheoremProbe:
    return LeanTheoremProbe(
        problem_id="Mathlib/Fake/Provenance.lean::Fake.provenance_probe",
        full_name="Fake.provenance_probe",
        safe_name="Fake_provenance_probe",
        file_path="Mathlib/Fake/Provenance.lean",
        statement="theorem probe_Fake_provenance (x y : Nat) : x + y = y + x",
        prefix_text="import Mathlib.Tactic\n\nnamespace Fake\nopen Nat\n",
        pp_scope=PPScope(current_namespace="Fake", open_declarations=("Nat",)),
        reference_tactics=tuple(reference),
    )


def make_task(arena: EvidenceAwareArena) -> VerifiedTask:
    return VerifiedTask.from_probe(
        make_probe(),
        backend_kernel_contract=OFFLINE_CONTRACT,
        budget=TaskBudget(model_actions=8, wall_clock_s=600.0),
        arena_factory=lambda: arena,
    )


def write_bank(directory: Path, trajectories: Sequence[VerifiedTrajectory]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bank.jsonl").write_text(
        "".join(t.to_json() + "\n" for t in trajectories), encoding="utf-8"
    )
    return directory


def relabel_as_solver(trajectory: VerifiedTrajectory) -> dict[str, Any]:
    """The V05-03 forgery, verbatim: flip every ``actor`` to SOLVER and reseal the record.

    This is what ``research/phase9/redteam/out/forged_solver_actor/bank.jsonl`` contains, built
    the same way (``attack_trajectory_integrity.py`` T2).  Resealing is essential: without
    recomputing ``content_hash`` the load fails on the hash alone, which proves nothing about the
    actor.
    """

    payload = json.loads(trajectory.to_json())
    for action in payload["actions"]:
        action["actor"] = Actor.SOLVER.value
    resealed = VerifiedTrajectory.from_dict(payload, check_hashes=False)
    return json.loads(resealed.to_json())


# =============================================================================================
# V05-03: the actor is stamped at the moment of choice, and asserted at emission
# =============================================================================================


def test_a_reference_replay_cannot_be_relabelled_as_a_solver_result_by_a_reader(
    tmp_path: Path,
) -> None:
    """Relabelling a committed REFERENCE replay SOLVER must not survive ``verify_bank``.

    This is ``attack_relive.py``'s ``forged_solver_actor`` in miniature and offline: take a
    REFERENCE trajectory, flip every ``actor`` string to ``SOLVER``, reseal so the content hash
    is consistent again, and hand the result to a reader.

    **Reverted:** with the V05-01 structural check removed from ``_structural_problems`` this
    bank verifies clean -- ``passed=True``, and under ``--relive`` the stored actions really do
    re-execute, because they are genuine Lean transitions.  Nothing else in the record notices
    that its five "solver actions" came out of mathlib's own proof.
    """

    honest = make_trajectory(5, actor=Actor.REFERENCE)
    assert verify_bank(write_bank(tmp_path / "honest", [honest])).passed

    forged = write_bank(tmp_path / "forged", [])
    (forged / "bank.jsonl").write_text(
        json.dumps(relabel_as_solver(honest), sort_keys=True) + "\n", encoding="utf-8"
    )
    result = verify_bank(forged)

    assert not result.passed, "a relabelled reference replay must not verify as a SOLVER result"
    assert result.ok == 0
    assert any("no provenance digest" in failure for failure in result.failures), result.failures


def test_build_trajectory_asserts_the_actor_instead_of_rewriting_it() -> None:
    """``build_trajectory(actor=...)`` is a claim about the record, not an edit of it.

    Driven at the schema layer, which is where the rewrite used to be undone: a trajectory whose
    actions are REFERENCE refuses to be reported as a SOLVER result, and vice versa.

    **Reverted:** ``build_trajectory`` goes back to
    ``tuple(replace(action, actor=actor) for action in self._actions)``, so *any* claim is
    satisfied by rewriting the actions to match it and no assertion can ever fail.
    """

    reference = make_trajectory(3, actor=Actor.REFERENCE)
    reference.require_single_actor(Actor.REFERENCE)
    with pytest.raises(TrajectoryIntegrityError, match="cannot be reported as a SOLVER result"):
        reference.require_single_actor(Actor.SOLVER)


@pytest.mark.slow
def test_a_live_reference_replay_is_born_reference_and_refuses_a_solver_claim() -> None:
    """The emission-time half, against real Lean: the actor is fixed when the arena is built.

    An arena constructed with ``actor=Actor.REFERENCE`` -- what :class:`ReplayDriver` now does --
    stamps REFERENCE on every action Lean accepts, and ``build_trajectory(actor=Actor.SOLVER)``
    raises rather than relabelling them.  Its own REFERENCE claim is accepted, and the actions
    carry no provenance digest, which is the honest value for a replay.

    **Reverted:** the same arena emits a perfectly well-formed SOLVER trajectory from mathlib's
    recorded tactics, with ``solver_actions`` equal to the replay length.
    """

    require_lean()
    require_train_json()
    record, probe = find_probe(1, 3)
    arena = LeanTrajectoryArena(attempt_budget=8, fail_fast=True, actor=Actor.REFERENCE)
    try:
        arena.reset(probe, hide_reference=probe.reference_tactics)
        for tactic in probe.reference_tactics:
            if arena.step(tactic).done:
                break
        arena.abandon("reference script exhausted in a provenance test")
        if not arena.states or len(arena.states) < 2:
            pytest.skip("the reference script did not produce a single accepted action")

        from arena.trajectory.arena_v0 import source_version_from_record

        source = source_version_from_record(record)
        with pytest.raises(TrajectoryIntegrityError, match="cannot be reported as a SOLVER"):
            arena.build_trajectory(
                actor=Actor.SOLVER,
                source_version=source,
                reference_horizon=len(probe.reference_tactics),
            )
        honest = arena.build_trajectory(
            actor=Actor.REFERENCE,
            source_version=source,
            reference_horizon=len(probe.reference_tactics),
        )
    finally:
        arena.close()

    assert honest.actors == {Actor.REFERENCE}
    assert honest.unattributed_action_indices == tuple(a.index for a in honest.actions)


@pytest.mark.slow
def test_a_reference_arena_refuses_policy_evidence_on_a_replayed_tactic() -> None:
    """A replay carrying a Solver's evidence would be the more alarming record, so it is refused.

    **Reverted:** ``step()`` accepts the evidence and stamps its digest on a REFERENCE action,
    producing a record that claims a policy chose a tactic read out of the source file.
    """

    require_lean()
    require_train_json()
    _, probe = find_probe(1, 3)
    arena = LeanTrajectoryArena(attempt_budget=4, fail_fast=True, actor=Actor.REFERENCE)
    evidence = ActionEvidence(
        policy_digest="p" * 64,
        prompt_sha256="q" * 64,
        observation_digest="r" * 64,
        decoding_digest="s" * 64,
    )
    try:
        arena.reset(probe, hide_reference=probe.reference_tactics)
        with pytest.raises(ActionProvenanceError, match="actor=REFERENCE"):
            arena.step(probe.reference_tactics[0], evidence=evidence)
    finally:
        arena.close()


# =============================================================================================
# V05-01: the action is bound to a policy and to the state that policy was shown
# =============================================================================================


def test_an_action_bound_to_a_different_observation_is_refused_before_lean_sees_it() -> None:
    """The binding is checked against the projection *this task* just handed out.

    A caller holding the LeanDojo record can produce a tactic without ever looking at the state.
    It cannot produce a matching ``observation_digest`` without doing so, and the check runs
    before the tactic is lowered -- ``EvidenceAwareArena`` never sees the action at all.

    **Reverted:** ``step()`` takes only a tactic, plays whatever it is handed, and the emitted
    action is indistinguishable from one a policy chose while looking at this state.
    """

    arena = EvidenceAwareArena([Scripted(StepOutcome.OK)])
    task = make_task(arena)
    try:
        task.reset()
        stale = ActionEvidence(
            policy_digest="policy-digest",
            prompt_sha256="a" * 64,
            observation_digest="not-the-projection-this-task-returned",
            decoding_digest="decoding-digest",
        )
        with pytest.raises(ActionProvenanceError, match="different observation"):
            task.step("simp", evidence=stale)
    finally:
        task.close()

    assert arena.evidence_seen == [], "the refused action must never reach the backend"


def test_the_matching_binding_is_accepted_and_lands_in_the_action_log() -> None:
    """The positive control for the check above: the honest digest is accepted and recorded.

    **Reverted:** there is no digest to accept, no ``provenance_digest`` in the action log, and
    ``actions_without_provenance`` does not exist to be zero.
    """

    arena = EvidenceAwareArena([Scripted(StepOutcome.OK)])
    task = make_task(arena)
    try:
        projection = task.reset()
        evidence = ActionEvidence(
            policy_digest="policy-digest",
            prompt_sha256="a" * 64,
            observation_digest=observation_digest_of(projection),
            decoding_digest="decoding-digest",
        )
        outcome = task.step("simp", evidence=evidence)
        report = task.episode_report().to_dict()
    finally:
        task.close()

    assert outcome.result.advanced_state
    assert arena.evidence_seen == [evidence]
    assert task.unattributed_actions == 0
    assert report["actions_without_provenance"] == 0
    assert report["action_log"][0]["action_evidence"] == "PRESENT"
    assert report["action_log"][0]["provenance_digest"] == evidence.provenance_digest


def test_evidence_free_stepping_still_works_and_is_recorded_as_such() -> None:
    """Scripted play stays possible; it just stops being able to claim autonomy.

    **Reverted:** evidence-free stepping is the *only* mode, and the artefact it produces is
    byte-shaped exactly like an autonomous one.
    """

    arena = EvidenceAwareArena([Scripted(StepOutcome.OK)])
    task = make_task(arena)
    try:
        task.reset()
        task.step("simp")
        report = task.episode_report().to_dict()
    finally:
        task.close()

    assert arena.evidence_seen == [None]
    assert task.unattributed_actions == 1
    assert report["actions_without_provenance"] == 1
    assert report["action_log"][0]["action_evidence"] == "ABSENT"
    assert report["action_log"][0]["provenance_digest"] == ""


def test_a_solver_trajectory_with_no_provenance_digests_fails_structural_verification(
    tmp_path: Path,
) -> None:
    """The reader's check, independent of how the file was produced (V05-01, item 4).

    A bank file can be written by anything.  ``verify_bank`` therefore refuses a ``SOLVER``
    trajectory whose actions carry no binding, rather than trusting that whatever produced it ran
    the emission-time assertion.

    **Reverted:** ``_structural_problems`` says nothing about provenance, the bank passes, and
    ``horizon.solver_actions`` reports a number no reader can check.
    """

    unbound = make_trajectory(4, actor=Actor.SOLVER)
    result = verify_bank(write_bank(tmp_path / "unbound", [unbound]))

    assert not result.passed
    assert result.ok == 0
    assert any("no provenance digest" in failure for failure in result.failures), result.failures

    bound = replace(
        unbound,
        actions=tuple(
            replace(action, provenance_digest=f"digest-{action.index}")
            for action in unbound.actions
        ),
    )
    bound = replace(bound, trajectory_id=unbound.trajectory_id)
    assert verify_bank(write_bank(tmp_path / "bound", [bound])).passed


def test_a_record_written_before_the_binding_existed_still_loads(tmp_path: Path) -> None:
    """Readable is not the same as believed (the documented choice).

    Every already-published artefact -- ``artifacts/trajectory/hc_v0_5_smoke.json`` included --
    must still load and keep its original ``content_hash`` byte-for-byte, because back-dating
    provenance onto an old record would be worse than refusing it.  A missing digest reads as
    *absent*, and the SOLVER check is what refuses it.

    **Reverted:** nothing changes for these records; they were always accepted, which is the
    defect.
    """

    legacy = make_trajectory(3, actor=Actor.REFERENCE)
    payload = json.loads(legacy.to_json())
    assert all("provenance_digest" not in action for action in payload["actions"])

    reloaded = VerifiedTrajectory.from_dict(payload)
    assert reloaded.content_hash == legacy.content_hash
    assert reloaded.unattributed_action_indices == (0, 1, 2)
    reloaded.require_attributed_actions(Actor.REFERENCE)  # a replay has nothing to bind
    with pytest.raises(TrajectoryIntegrityError, match="carry no provenance digest"):
        reloaded.require_attributed_actions(Actor.SOLVER)


def test_the_digest_is_inside_the_content_hash_so_a_reader_re_derives_it() -> None:
    """A binding outside ``content_hash`` would be a side-car field anyone could edit.

    **Reverted:** ``semantic_core`` omits the digest, so swapping one action's provenance for
    another's leaves the record's hash and id untouched.
    """

    bound = make_trajectory(2, actor=Actor.SOLVER)
    bound = replace(
        bound,
        actions=tuple(replace(a, provenance_digest="d0") for a in bound.actions),
    )
    tampered = replace(
        bound,
        actions=(replace(bound.actions[0], provenance_digest="d1"),) + bound.actions[1:],
    )
    assert bound.content_hash != tampered.content_hash

    payload = json.loads(bound.to_json())
    assert payload["actions"][0]["provenance_digest"] == "d0"
    assert VerifiedTrajectory.from_dict(payload).content_hash == bound.content_hash


def test_incomplete_evidence_is_refused_at_construction() -> None:
    """Half a provenance claim is not a weaker claim; it is an unfalsifiable one.

    **Reverted:** an ``ActionEvidence`` with three empty fields digests to something that looks
    exactly as authoritative as a complete one.
    """

    with pytest.raises(ActionProvenanceError, match="incomplete"):
        ActionEvidence(
            policy_digest="",
            prompt_sha256="a" * 64,
            observation_digest="b" * 64,
            decoding_digest="c" * 64,
        )


def test_the_provenance_digest_is_a_function_of_all_four_fields() -> None:
    """Every field must move the digest, or it is decoration rather than a binding.

    **Reverted:** there is no digest at all.
    """

    base = ActionEvidence(
        policy_digest="p", prompt_sha256="q", observation_digest="r", decoding_digest="s"
    )
    assert base.provenance_digest == ActionEvidence.from_dict(base.to_dict()).provenance_digest
    for field_name in ("policy_digest", "prompt_sha256", "observation_digest", "decoding_digest"):
        altered = replace(base, **{field_name: "CHANGED"})
        assert altered.provenance_digest != base.provenance_digest, field_name


# =============================================================================================
# End to end: an honest episode still passes, with no live model calls
# =============================================================================================


def test_an_honest_offline_episode_binds_every_action(tmp_path: Path) -> None:
    """``run_episode`` supplies real evidence for every proposal, offline.

    :class:`ScriptedSolver` makes no network call and has no runtime; the point here is that the
    runner's wiring -- proposal, projection, solver identity, decoding -- produces a binding the
    task accepts, on every step.

    **Reverted:** ``run_episode`` calls ``active.step(proposal.tactic)`` with nothing attached and
    the emitted episode records ``"actor": "SOLVER"`` as a string literal.
    """

    arena = EvidenceAwareArena([Scripted(StepOutcome.OK), Scripted(StepOutcome.OK)])
    task = make_task(arena)
    solver = ScriptedSolver(default="simp", name="offline-provenance-solver")
    result = run_episode(task, solver, max_steps=2)

    assert result.error == "", result.error
    assert len(result.steps) == 2
    assert all(step.provenance_digest for step in result.steps)
    assert result.steps_with_provenance == 2
    assert [e is not None for e in arena.evidence_seen] == [True, True]
    # Each step is bound to the projection that was current when it was proposed, so consecutive
    # steps over different states carry different observation digests.
    assert result.steps[0].observation_digest != result.steps[1].observation_digest
    # The runner no longer asserts an actor; with an injected arena nothing was emitted to read.
    assert result.to_dict()["actor"] == "NOT_EMITTED"


def test_the_evidence_the_runner_builds_names_the_projection_it_was_built_from() -> None:
    """``action_evidence_for`` is the seam; it must agree with the task's own digest.

    **Reverted:** the function does not exist and there is nothing to agree with.
    """

    arena = EvidenceAwareArena([Scripted(StepOutcome.OK)])
    task = make_task(arena)
    solver = ScriptedSolver(default="simp", name="offline-provenance-solver")
    try:
        projection = task.reset()

        @dataclass(frozen=True, slots=True)
        class _Observation:
            step_index: int
            state_id: str
            rendered: Any

        proposal = solver.propose(
            _Observation(step_index=0, state_id="s0", rendered=projection.rendered)
        )
        evidence = action_evidence_for(proposal, projection, solver)

        assert evidence.observation_digest == observation_digest_of(projection)
        assert evidence.policy_digest == solver.identity.digest
        assert evidence.prompt_sha256 == proposal.prompt_sha256
        # Accepted by the task, which is the only test that matters for the seam.
        task.step(proposal.tactic or "simp", evidence=evidence)
    finally:
        task.close()


@pytest.mark.slow
def test_an_honest_live_episode_emits_a_verifiable_solver_trajectory(tmp_path: Path) -> None:
    """End to end against real Lean, with a scripted (never live) Solver.

    A real ``VerifiedTask`` on a real theorem, played by :class:`ScriptedSolver`, emits a
    trajectory whose actions are ``SOLVER`` **and** carry provenance digests, and that trajectory
    passes ``verify_bank`` structurally.  This is the case the two refusals above must not break.

    ``skip`` is used deliberately rather than the recorded proof: it is a legal tactic that Lean
    accepts and that is not the answer, so the episode is a genuine non-reference action.

    **Reverted:** the same episode emits, but so does an oracle-fed one, and no reader can
    separate them.
    """

    require_lean()
    require_train_json()
    record, probe = find_probe(1, 3)
    task = VerifiedTask.from_leandojo_record(record, probe)
    solver = ScriptedSolver(default="skip", name="offline-live-provenance-solver")
    result = run_episode(task, solver, max_steps=1)

    assert result.error == "", result.error
    assert result.emit_error == "", result.emit_error
    assert result.trajectory is not None
    assert result.to_dict()["actor"] == Actor.SOLVER.value

    emitted = VerifiedTrajectory.from_dict(result.trajectory)
    assert emitted.actors == {Actor.SOLVER}
    assert emitted.actions, "the episode recorded no accepted action to bind"
    assert emitted.unattributed_action_indices == ()
    emitted.require_attributed_actions(Actor.SOLVER)
    assert verify_bank(write_bank(tmp_path / "honest_live", [emitted])).passed
