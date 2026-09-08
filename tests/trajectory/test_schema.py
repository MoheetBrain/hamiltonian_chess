"""The record must not be able to describe something that did not happen."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from arena.trajectory.schema import (
    TRAJECTORY_SCHEMA_VERSION,
    Actor,
    BackendStateEnvelope,
    CanonicalProjectionStatus,
    DerivedView,
    EvidenceKind,
    FormalBackend,
    PPScope,
    SourceVersion,
    TerminalStatus,
    TrajectoryAction,
    TrajectoryIntegrityError,
    TrajectoryProvenance,
    Verdict,
    VerifiedTrajectory,
    VerifierEvidence,
    content_sha256,
    derive_trajectory_id,
)

BACKEND = FormalBackend(
    system="lean4",
    toolchain="leanprover/lean4:v4.10.0-rc1",
    lean_version_string="Lean (version 4.10.0-rc1, arm64-apple-darwin23.5.0, ...)",
    mathlib_commit="29dcec074de168ac2bf835a77ef68bbe069194c5",
    mathlib_build_root="/built/mathlib4",
    olean_count=5680,
)

SOURCE = SourceVersion(
    dataset="LeanDojo Benchmark 4",
    license="CC BY 2.0",
    split="train",
    file_path="Mathlib/Order/RelSeries.lean",
    full_name="RelSeries.smash_castAdd",
    commit="29dcec074de168ac2bf835a77ef68bbe069194c5",
    start=(514, 1),
    end=(518, 26),
)

PROVENANCE = TrajectoryProvenance(
    trust_tier="A_NATIVE_VERIFIED",
    generator="test",
    generated_utc="2026-09-08T00:00:00+00:00",
    seed=7,
    sealed_splits_not_read=("random/val.json",),
)


def make_states(count: int) -> tuple[BackendStateEnvelope, ...]:
    return tuple(
        BackendStateEnvelope(
            index=index,
            state_id=str(index),
            pp="no goals" if index == count - 1 else f"⊢ goal {index}",
            pp_scope=PPScope(current_namespace="RelSeries"),
            n_goals=0 if index == count - 1 else 1,
        )
        for index in range(count)
    )


def make_actions(count: int, actor: Actor = Actor.REFERENCE) -> tuple[TrajectoryAction, ...]:
    return tuple(
        TrajectoryAction(
            index=index,
            from_state_id=str(index),
            to_state_id=str(index + 1),
            actor=actor,
            tactic=f"rw [lemma_{index}]",
            wall_ms=index + 1,
        )
        for index in range(count)
    )


def kernel_evidence(*, sorry_ax: bool = False) -> VerifierEvidence:
    return VerifierEvidence(
        kind=EvidenceKind.TERMINAL_KERNEL,
        verifier="lean4-kernel",
        verdict=Verdict.KERNEL_REJECTED if sorry_ax else Verdict.KERNEL_VERIFIED,
        print_axioms="'probe_x' depends on axioms: [propext, Quot.sound]",
        contains_sorry_ax=sorry_ax,
        contains_of_reduce_bool=False,
    )


def make_trajectory(
    steps: int = 5,
    *,
    terminal: TerminalStatus = TerminalStatus.CLOSED_VERIFIED,
    actor: Actor = Actor.REFERENCE,
    with_kernel: bool = True,
    reference_horizon: int = 5,
) -> VerifiedTrajectory:
    states = make_states(steps + 1)
    actions = make_actions(steps, actor)
    evidence: list[VerifierEvidence] = [
        VerifierEvidence(
            kind=EvidenceKind.STEP,
            verifier="lean4-repl",
            verdict=Verdict.ACCEPTED,
            step=action.index,
            from_state_id=action.from_state_id,
            to_state_id=action.to_state_id,
            tactic=action.tactic,
        )
        for action in actions
    ]
    if with_kernel:
        evidence.append(kernel_evidence())
    draft = VerifiedTrajectory(
        trajectory_id="pending",
        problem_id="Mathlib/Order/RelSeries.lean::RelSeries.smash_castAdd",
        formal_backend=BACKEND,
        source_version=SOURCE,
        states=states,
        actions=actions,
        verifier_evidence=tuple(evidence),
        terminal_status=terminal,
        provenance=PROVENANCE,
        reference_horizon=reference_horizon,
    )
    return replace(draft, trajectory_id=derive_trajectory_id(draft.problem_id, draft.content_hash))


# -- round trip ---------------------------------------------------------------------------


def test_round_trip_preserves_every_field() -> None:
    original = make_trajectory(5)
    restored = VerifiedTrajectory.from_dict(json.loads(original.to_json()))
    assert restored == original
    assert restored.to_dict() == original.to_dict()
    assert restored.schema_version == TRAJECTORY_SCHEMA_VERSION


def test_round_trip_through_a_bank_line() -> None:
    original = make_trajectory(7, reference_horizon=9)
    line = original.to_json()
    assert "\n" not in line
    assert VerifiedTrajectory.from_dict(json.loads(line)).horizon.achieved == 7


# -- content hashes -----------------------------------------------------------------------


def test_content_hash_is_deterministic_and_ignores_wall_clock() -> None:
    first = make_trajectory(4)
    second = make_trajectory(4)
    assert first.content_hash == second.content_hash

    retimed = replace(
        second,
        actions=tuple(replace(action, wall_ms=action.wall_ms + 5000) for action in second.actions),
        provenance=replace(second.provenance, generated_utc="2099-01-01T00:00:00+00:00"),
    )
    assert retimed.content_hash == first.content_hash, "timing must not change identity"
    assert retimed.to_dict()["actions"][0]["wall_ms"] != first.to_dict()["actions"][0]["wall_ms"]


def test_content_hash_changes_when_the_mathematics_changes() -> None:
    original = make_trajectory(4)
    tampered = replace(
        original,
        actions=(replace(original.actions[0], tactic="aesop"),) + original.actions[1:],
    )
    assert tampered.content_hash != original.content_hash


def test_derived_trajectory_id_is_a_function_of_the_content() -> None:
    first = make_trajectory(3)
    second = make_trajectory(3)
    assert first.trajectory_id == second.trajectory_id
    assert first.trajectory_id.startswith("vt-")
    assert make_trajectory(4).trajectory_id != first.trajectory_id


def test_pp_hash_tampering_is_detected_on_load() -> None:
    payload = json.loads(make_trajectory(3).to_json())
    payload["states"][1]["backend_native"]["pp"] = "⊢ something else entirely"
    with pytest.raises(ValueError, match="pp_sha256 mismatch"):
        VerifiedTrajectory.from_dict(payload)


def test_content_hash_tampering_is_detected_on_load() -> None:
    payload = json.loads(make_trajectory(3).to_json())
    payload["terminal_status"] = TerminalStatus.FAILED.value
    payload["horizon"]["verified"] = 3
    with pytest.raises(TrajectoryIntegrityError, match="content_hash mismatch"):
        VerifiedTrajectory.from_dict(payload)


def test_envelope_identity_is_state_id_plus_content_hash() -> None:
    envelope = BackendStateEnvelope(index=0, state_id="3", pp="⊢ True")
    assert envelope.pp_sha256 == content_sha256("⊢ True")
    assert envelope.envelope_id == f"LEAN4_TACTIC_STATE_PP:3:{envelope.pp_sha256[:32]}"


def test_a_state_id_means_nothing_outside_the_session_that_issued_it() -> None:
    """RT-02: Lean hands out per-session integers, so ``"1"`` alone is not an identity."""

    here = BackendStateEnvelope(index=1, state_id="1", pp="⊢ p", session_id="lean4-repl-aaa")
    there = BackendStateEnvelope(index=1, state_id="1", pp="⊢ p", session_id="lean4-repl-bbb")
    assert not here.same_backend_state_as(there)
    assert here.envelope_id != there.envelope_id
    assert here.same_backend_state_as(replace(there, session_id="lean4-repl-aaa"))


def test_the_session_binding_is_part_of_the_records_identity() -> None:
    """A record that names its session hashes differently from one that does not."""

    unbound = make_trajectory(3)
    bound = replace(
        unbound,
        states=tuple(
            replace(state, session_id="lean4-repl-aaa", problem_id=unbound.problem_id)
            for state in unbound.states
        ),
    )
    assert bound.content_hash != unbound.content_hash
    assert bound.states_hash != unbound.states_hash
    core = bound.semantic_core()["states"][0]
    assert core["session_id"] == "lean4-repl-aaa"
    assert core["problem_id"] == unbound.problem_id


def test_records_written_before_the_binding_keep_their_hashes_byte_for_byte() -> None:
    """The committed banks must not be invalidated: an absent field is an absent claim.

    ``semantic_core`` writes the binding only when there is one, so the pre-image of a legacy
    record's ``content_hash`` — and therefore its ``trajectory_id`` — is unchanged.
    """

    legacy = make_trajectory(3)
    assert all(state.session_id == "" and state.problem_id == "" for state in legacy.states)
    for state in legacy.semantic_core()["states"]:
        assert set(state) == {"index", "state_id", "backend_kind", "pp_sha256", "n_goals"}
    assert legacy.states[0].envelope_id.count(":") == 2, "no session segment when unbound"


def test_state_identity_is_the_backend_id_never_the_rendered_string() -> None:
    """`univ` vs `Finset.univ`: the same state renders differently under a different scope."""

    open_finset = BackendStateEnvelope(
        index=0,
        state_id="4",
        pp="⊢ ∑ i in univ, f i = 0",
        pp_scope=PPScope(open_declarations=("Finset",)),
    )
    qualified = BackendStateEnvelope(index=0, state_id="4", pp="⊢ ∑ i in Finset.univ, f i = 0")
    assert open_finset.pp != qualified.pp
    assert open_finset.pp_sha256 != qualified.pp_sha256
    assert open_finset.same_backend_state_as(qualified), "identity is the backend's sid"

    different_state_same_text = BackendStateEnvelope(index=0, state_id="9", pp=qualified.pp)
    assert not qualified.same_backend_state_as(different_state_same_text)


# -- horizon accounting -------------------------------------------------------------------


def test_horizon_counts_actions_not_reference_length() -> None:
    trajectory = make_trajectory(6, reference_horizon=20)
    horizon = trajectory.horizon
    assert horizon.achieved == 6
    assert horizon.verified == 6
    assert horizon.reference == 20
    assert int(horizon) == 6
    assert horizon.reference_actions == 6 and horizon.solver_actions == 0


def test_verified_horizon_is_zero_unless_the_kernel_closed_it() -> None:
    for status in (
        TerminalStatus.OPEN,
        TerminalStatus.FAILED,
        TerminalStatus.ABANDONED,
        TerminalStatus.BUDGET_EXHAUSTED,
        TerminalStatus.ERROR_BACKEND,
    ):
        trajectory = make_trajectory(5, terminal=status, with_kernel=False)
        assert trajectory.horizon.achieved == 5
        assert trajectory.horizon.verified == 0, status


def test_solver_and_reference_actions_are_counted_separately() -> None:
    trajectory = make_trajectory(4, actor=Actor.SOLVER)
    assert trajectory.horizon.solver_actions == 4
    assert trajectory.is_single_actor
    trajectory.require_single_actor(Actor.SOLVER)
    with pytest.raises(TrajectoryIntegrityError, match="cannot be reported as a REFERENCE"):
        trajectory.require_single_actor(Actor.REFERENCE)


def test_mixed_actor_trajectory_is_visible() -> None:
    trajectory = make_trajectory(4)
    mixed = replace(
        trajectory,
        actions=(replace(trajectory.actions[0], actor=Actor.SOLVER),) + trajectory.actions[1:],
    )
    assert not mixed.is_single_actor
    assert mixed.actors == {Actor.SOLVER, Actor.REFERENCE}


def test_tactic_head_counts_report_the_automation_mix() -> None:
    trajectory = make_trajectory(3)
    mutated = replace(
        trajectory,
        actions=(replace(trajectory.actions[0], tactic="aesop"),) + trajectory.actions[1:],
    )
    assert mutated.tactic_head_counts() == {"aesop": 1, "rw": 2}


# -- terminal status ----------------------------------------------------------------------


def test_open_is_the_only_non_absorbing_status() -> None:
    assert TerminalStatus.OPEN.is_terminal is False
    for status in TerminalStatus:
        if status is TerminalStatus.OPEN:
            continue
        assert status.is_terminal
        assert TerminalStatus.OPEN.can_transition_to(status)
        assert status.can_transition_to(status)
        assert not status.can_transition_to(TerminalStatus.CLOSED_VERIFIED) or (
            status is TerminalStatus.CLOSED_VERIFIED
        )


def test_failed_cannot_be_upgraded_to_closed_verified() -> None:
    assert not TerminalStatus.FAILED.can_transition_to(TerminalStatus.CLOSED_VERIFIED)
    assert not TerminalStatus.BUDGET_EXHAUSTED.can_transition_to(TerminalStatus.CLOSED_VERIFIED)


def test_required_statuses_exist() -> None:
    names = {status.value for status in TerminalStatus}
    assert {
        "OPEN",
        "CLOSED_VERIFIED",
        "FAILED",
        "ABANDONED",
        "BUDGET_EXHAUSTED",
    } <= names


# -- integrity ----------------------------------------------------------------------------


def test_broken_chain_is_refused() -> None:
    """Ten unrelated one-step probes cannot be dressed up as a ten-step trajectory."""

    states = make_states(4)
    actions = list(make_actions(3))
    actions[1] = replace(actions[1], from_state_id="99")
    with pytest.raises(TrajectoryIntegrityError, match="the chain is broken"):
        VerifiedTrajectory(
            trajectory_id="x",
            problem_id="p",
            formal_backend=BACKEND,
            source_version=SOURCE,
            states=states,
            actions=tuple(actions),
            verifier_evidence=(),
            terminal_status=TerminalStatus.OPEN,
            provenance=PROVENANCE,
        )


def test_state_and_action_counts_must_agree() -> None:
    with pytest.raises(TrajectoryIntegrityError, match="must equal"):
        VerifiedTrajectory(
            trajectory_id="x",
            problem_id="p",
            formal_backend=BACKEND,
            source_version=SOURCE,
            states=make_states(3),
            actions=make_actions(5),
            verifier_evidence=(),
            terminal_status=TerminalStatus.OPEN,
            provenance=PROVENANCE,
        )


def test_closed_verified_requires_kernel_evidence() -> None:
    with pytest.raises(TrajectoryIntegrityError, match="requires a TERMINAL_KERNEL"):
        make_trajectory(3, with_kernel=False)


def test_closed_verified_is_refused_when_the_kernel_saw_sorry_ax() -> None:
    states = make_states(3)
    actions = make_actions(2)
    with pytest.raises(TrajectoryIntegrityError, match="requires a TERMINAL_KERNEL"):
        VerifiedTrajectory(
            trajectory_id="x",
            problem_id="p",
            formal_backend=BACKEND,
            source_version=SOURCE,
            states=states,
            actions=actions,
            verifier_evidence=(kernel_evidence(sorry_ax=True),),
            terminal_status=TerminalStatus.CLOSED_VERIFIED,
            provenance=PROVENANCE,
        )


def test_empty_trajectory_is_refused() -> None:
    with pytest.raises(TrajectoryIntegrityError, match="at least the initial state"):
        VerifiedTrajectory(
            trajectory_id="x",
            problem_id="p",
            formal_backend=BACKEND,
            source_version=SOURCE,
            states=(),
            actions=(),
            verifier_evidence=(),
            terminal_status=TerminalStatus.OPEN,
            provenance=PROVENANCE,
        )


# -- the canonical-schema refusal ----------------------------------------------------------


def test_derived_view_never_claims_a_canonical_state() -> None:
    view = DerivedView()
    assert view.canonical_state is None
    assert view.canonical_projection_status is CanonicalProjectionStatus.UNMAPPABLE
    assert view.to_dict()["canonical_state"] is None


def test_a_non_null_canonical_state_is_rejected_on_load() -> None:
    payload = DerivedView().to_dict()
    payload["canonical_state"] = {"op": "Eq", "sort": "Prop"}
    with pytest.raises(ValueError, match="must be null"):
        DerivedView.from_dict(payload)


def test_serialized_state_carries_the_backend_envelope_not_a_canonical_record() -> None:
    payload = json.loads(make_trajectory(2).to_json())
    state = payload["states"][0]
    assert set(state["backend_native"]) == {"kind", "pp", "pp_scope", "pp_sha256", "n_goals"}
    assert state["backend_native"]["kind"] == "LEAN4_TACTIC_STATE_PP"
    assert state["derived"]["canonical_state"] is None
    assert "canonical_state" not in json.dumps(payload["formal_backend"])
