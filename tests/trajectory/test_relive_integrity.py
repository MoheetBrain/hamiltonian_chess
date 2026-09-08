"""RT-02 and RT-03 regressions: what a stored trajectory is allowed to claim about itself.

Both defects are recorded in ``docs/HC_V0_RED_TEAM.md`` and both were confirmed exploits before
the fixes these tests pin down.

RT-03 (``--relive`` verified the wrong thing)
    ``_relive`` called ``ReplayDriver.run``, which plays ``probe.reference_tactics`` — the tactics
    of the *LeanDojo source record*.  ``trajectory.actions`` was never read, so a bank whose every
    stored tactic had been replaced with ``aesop`` relived clean: the check re-verified the
    source, not the artefact.  The Lean-backed tests below execute a real episode, mutate exactly
    one stored action, and require relive to fail *on that action*.

RT-02 (theorem splicing)
    Lean's ``sid``s are per-session small integers, so two unrelated theorems' states could be
    renumbered into one chain and the record loaded clean, claiming ten verified steps.  The
    offline tests below require that splice to be refused at construction *and* on ``from_dict``,
    naming the first state that does not belong.

The RT-02 tests need no Lean.  The RT-03 tests drive a real Lean process and are ``slow``; they
skip with the exact missing paths when the toolchain or the development split is absent, because
a mock kernel would verify nothing.
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
from dataclasses import replace
from typing import Any

import pytest

import arena.trajectory.arena_v0 as arena_v0
from arena.trajectory.arena_v0 import ReplayDriver, relive_trajectory
from arena.trajectory.lean_backend import LeanToolchainConfig
from arena.trajectory.schema import (
    Actor,
    BackendStateEnvelope,
    EvidenceKind,
    PPScope,
    TerminalStatus,
    TrajectoryAction,
    TrajectoryIntegrityError,
    Verdict,
    VerifiedTrajectory,
    VerifierEvidence,
    derive_trajectory_id,
)

from . import find_probe, require_lean, require_train_json
from .test_schema import BACKEND, PROVENANCE, SOURCE, kernel_evidence

# =============================================================================================
# RT-02: two theorems cannot be spliced into one trajectory
# =============================================================================================

#: The two scopes of the theorems the published attack actually spliced.
SCOPE_A = PPScope(current_namespace="MeasureTheory", open_declarations=("Topology", "NNReal"))
SCOPE_B = PPScope(current_namespace="MvPolynomial.IsHomogeneous")

PROBLEM_A = "Mathlib/MeasureTheory/Integral/Bochner.lean::MeasureTheory.weightedSMul_add_measure"
PROBLEM_B = (
    "Mathlib/RingTheory/MvPolynomial/Homogeneous.lean::"
    "MvPolynomial.IsHomogeneous.rename_isHomogeneous_iff"
)


def half(
    *,
    first_index: int,
    steps: int,
    scope: PPScope,
    session_id: str,
    problem_id: str,
    tag: str,
) -> tuple[list[BackendStateEnvelope], list[TrajectoryAction]]:
    """``steps`` actions and their ``steps + 1`` states, numbered from ``first_index``.

    The state ids are the backend's own per-session integers, spelled exactly as the attack
    spells them after renumbering: consecutive, starting at the position in the spliced chain.
    """

    states = [
        BackendStateEnvelope(
            index=first_index + offset,
            state_id=str(first_index + offset),
            pp=f"⊢ {tag} goal {offset}",
            pp_scope=scope,
            session_id=session_id,
            problem_id=problem_id,
        )
        for offset in range(steps + 1)
    ]
    actions = [
        TrajectoryAction(
            index=first_index + offset,
            from_state_id=str(first_index + offset),
            to_state_id=str(first_index + offset + 1),
            actor=Actor.REFERENCE,
            tactic=f"rw [{tag}_lemma_{offset}]",
        )
        for offset in range(steps)
    ]
    return states, actions


def assemble(
    states: list[BackendStateEnvelope],
    actions: list[TrajectoryAction],
    *,
    problem_id: str = PROBLEM_A,
    terminal: TerminalStatus = TerminalStatus.CLOSED_VERIFIED,
) -> VerifiedTrajectory:
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
    evidence.append(kernel_evidence())
    draft = VerifiedTrajectory(
        trajectory_id="pending",
        problem_id=problem_id,
        formal_backend=BACKEND,
        source_version=SOURCE,
        states=tuple(states),
        actions=tuple(actions),
        verifier_evidence=tuple(evidence),
        terminal_status=terminal,
        provenance=PROVENANCE,
        reference_horizon=len(actions),
    )
    return replace(draft, trajectory_id=derive_trajectory_id(problem_id, draft.content_hash))


def splice_payload(
    head: VerifiedTrajectory,
    tail_states: list[BackendStateEnvelope],
    tail_actions: list[TrajectoryAction],
) -> dict[str, Any]:
    """The forged JSON a splicer would write: A's record with B's tail appended."""

    payload = json.loads(head.to_json())
    payload["states"].extend(state.to_dict() for state in tail_states)
    payload["actions"].extend(action.to_dict() for action in tail_actions)
    return payload


def test_a_spliced_trajectory_is_refused_on_construction_and_on_load() -> None:
    """The published RT-02 payload, on records that carry no session binding.

    This is the committed bank's shape: nothing in those states says which session or which
    theorem they came from, so the check that has to catch the splice is the elaboration scope —
    an episode runs inside one file's namespace and ``open``s.
    """

    head_states, head_actions = half(
        first_index=0, steps=5, scope=SCOPE_A, session_id="", problem_id="", tag="A"
    )
    tail_states, tail_actions = half(
        first_index=5, steps=5, scope=SCOPE_B, session_id="", problem_id="", tag="B"
    )
    # the attack renumbers `index` and `state_id` only, so the chain still chains
    tail_states = tail_states[1:]

    with pytest.raises(TrajectoryIntegrityError, match=r"state 6 .*elaboration scope") as raised:
        assemble(head_states + tail_states, head_actions + tail_actions)
    assert "MvPolynomial.IsHomogeneous" in str(raised.value)

    honest = assemble(head_states, head_actions)
    payload = splice_payload(honest, tail_states, tail_actions)
    assert len(payload["states"]) == len(payload["actions"]) + 1, "the forgery is well-formed"

    with pytest.raises(TrajectoryIntegrityError, match=r"state 6"):
        VerifiedTrajectory.from_dict(payload)
    # and the forger cannot reseal his way past it: skipping the hash check does not skip this
    with pytest.raises(TrajectoryIntegrityError, match=r"state 6"):
        VerifiedTrajectory.from_dict(payload, check_hashes=False)


def test_states_from_two_sessions_are_refused_even_under_one_scope() -> None:
    """The scope check is the *legacy* net; the session binding is the real one.

    Two episodes rendered under byte-identical scopes are indistinguishable by scope alone.  A
    record written by this arena carries the session each state came from, and states from two
    sessions cannot be one trajectory.
    """

    head_states, head_actions = half(
        first_index=0,
        steps=3,
        scope=SCOPE_A,
        session_id="lean4-repl-aaa",
        problem_id=PROBLEM_A,
        tag="A",
    )
    tail_states, tail_actions = half(
        first_index=3,
        steps=3,
        scope=SCOPE_A,
        session_id="lean4-repl-bbb",
        problem_id=PROBLEM_A,
        tag="B",
    )
    tail_states = tail_states[1:]

    with pytest.raises(TrajectoryIntegrityError, match=r"state 4 carries session id") as raised:
        assemble(head_states + tail_states, head_actions + tail_actions)
    assert "lean4-repl-bbb" in str(raised.value)

    honest = assemble(head_states, head_actions)
    payload = splice_payload(honest, tail_states, tail_actions)
    with pytest.raises(TrajectoryIntegrityError, match=r"state 4 carries session id"):
        VerifiedTrajectory.from_dict(payload, check_hashes=False)


def test_a_state_may_not_belong_to_a_theorem_the_trajectory_does_not_claim() -> None:
    states, actions = half(
        first_index=0,
        steps=3,
        scope=SCOPE_A,
        session_id="lean4-repl-aaa",
        problem_id=PROBLEM_A,
        tag="A",
    )
    smuggled = list(states)
    smuggled[2] = replace(smuggled[2], problem_id=PROBLEM_B)
    with pytest.raises(TrajectoryIntegrityError, match=r"state 2 was produced on theorem"):
        assemble(smuggled, actions)

    # and a whole chain that agrees with itself but not with the record it sits in
    foreign = [replace(state, problem_id=PROBLEM_B) for state in states]
    with pytest.raises(TrajectoryIntegrityError, match=r"state 0 was produced on theorem"):
        assemble(foreign, actions, problem_id=PROBLEM_A)


def test_re_entering_an_earlier_state_of_the_same_session_is_still_legal() -> None:
    """Legitimate search must not be collateral damage: ``arena.branch`` returns to an old sid.

    The chain then contains the same ``state_id`` twice.  That is a branch, not a splice, and it
    is refused by nothing here — the session binding is what separates the two cases.
    """

    scope, session = SCOPE_A, "lean4-repl-aaa"
    sids = ["0", "1", "2", "1", "3"]
    states = tuple(
        BackendStateEnvelope(
            index=index,
            state_id=sid,
            pp=f"⊢ goal at {sid}",
            pp_scope=scope,
            session_id=session,
            problem_id=PROBLEM_A,
        )
        for index, sid in enumerate(sids)
    )
    actions = tuple(
        TrajectoryAction(
            index=index,
            from_state_id=sids[index],
            to_state_id=sids[index + 1],
            actor=Actor.SOLVER,
            tactic=f"tactic_{index}",
        )
        for index in range(len(sids) - 1)
    )
    branched = assemble(list(states), list(actions), terminal=TerminalStatus.ABANDONED)
    assert branched.horizon.achieved == 4
    assert len({state.state_id for state in branched.states}) == 4, "a sid really is revisited"
    assert VerifiedTrajectory.from_dict(json.loads(branched.to_json())) == branched


def test_the_committed_banks_still_load_under_the_new_invariants() -> None:
    """The artefacts this project has already published must not be invalidated by the fix."""

    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "artifacts" / "trajectory_bank_v0"
    loaded = 0
    for name in ("h5", "h12"):
        bank = root / name / "bank.jsonl"
        if not bank.is_file():
            pytest.skip(f"committed bank not present at {bank}")
        for line in bank.read_text(encoding="utf-8").splitlines():
            if line.strip():
                VerifiedTrajectory.from_dict(json.loads(line))
                loaded += 1
    assert loaded == 26, "both committed banks load with their stored content hashes intact"


# =============================================================================================
# RT-03: relive executes the artefact's own actions
# =============================================================================================


def executable_source(function: Any) -> str:
    """The function's code with its prose removed, so a docstring cannot satisfy an assertion."""

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            node.value = ast.Constant(value="<docstring>")
    return ast.unparse(tree)


def test_relive_reads_the_stored_actions_and_not_the_reference_proof() -> None:
    """A source check, because the behavioural one needs Lean and this must hold everywhere.

    The defect was one identifier deep: ``_relive`` handed the *source record* to a driver that
    plays ``probe.reference_tactics``.  Nothing on the relive path may read those again.
    """

    relive_code = executable_source(relive_trajectory)
    assert "trajectory.actions" in relive_code
    assert "reference_tactics" not in relive_code
    assert "ReplayDriver" not in relive_code

    # and its caller must not smuggle the reference proof back in through the driver
    caller_code = executable_source(arena_v0._relive)
    assert "reference_tactics" not in caller_code
    assert "ReplayDriver" not in caller_code
    assert "relive_trajectory" in caller_code


@pytest.mark.slow
def test_an_honest_trajectory_relives_on_its_own_actions() -> None:
    """The control: without it, a relive that always failed would pass every forgery test."""

    require_lean()
    require_train_json()
    record, probe = find_probe(5, 9)
    config = LeanToolchainConfig.from_env()
    outcome = ReplayDriver(config=config).run(record, probe)
    if outcome.terminal_status is not TerminalStatus.CLOSED_VERIFIED:
        pytest.skip(f"reference proof did not replay: {outcome.terminal_status} {outcome.error}")
    trajectory = outcome.trajectory
    assert trajectory is not None

    relived = relive_trajectory(trajectory, probe, config=config)
    assert relived.matched, relived.detail
    assert relived.actions_executed == trajectory.horizon.achieved
    assert relived.terminal_status is TerminalStatus.CLOSED_VERIFIED


@pytest.mark.slow
def test_relive_fails_on_the_exact_action_that_was_tampered_with() -> None:
    """RT-03 acceptance: one stored tactic is replaced, and relive names *that* action.

    Not a generic "horizon differs": the failure must say which action did not run, because that
    is the difference between a check that executes the artefact and a check that executes
    something else and compares totals.
    """

    require_lean()
    require_train_json()
    record, probe = find_probe(5, 9)
    config = LeanToolchainConfig.from_env()
    outcome = ReplayDriver(config=config).run(record, probe)
    if outcome.terminal_status is not TerminalStatus.CLOSED_VERIFIED:
        pytest.skip(f"reference proof did not replay: {outcome.terminal_status} {outcome.error}")
    trajectory = outcome.trajectory
    assert trajectory is not None
    assert len(trajectory.actions) >= 2

    target = 1
    forged_tactic = "exact hamiltonian_red_team_no_such_lemma"
    actions = list(trajectory.actions)
    actions[target] = replace(actions[target], tactic=forged_tactic)
    tampered = replace(trajectory, actions=tuple(actions))
    assert tampered.horizon.achieved == trajectory.horizon.achieved, "only the text changed"
    assert tampered.terminal_status is TerminalStatus.CLOSED_VERIFIED

    relived = relive_trajectory(tampered, probe, config=config)
    assert not relived.matched
    assert f"stored action {target}" in relived.detail, relived.detail
    assert forged_tactic in relived.detail, relived.detail
    assert relived.actions_executed == target, "it stopped where the forgery is"


@pytest.mark.slow
def test_the_published_action_swap_forgery_no_longer_relives_clean() -> None:
    """The red team's own payload: every tactic replaced by ``aesop``, nothing else touched."""

    require_lean()
    require_train_json()
    record, probe = find_probe(5, 9)
    config = LeanToolchainConfig.from_env()
    outcome = ReplayDriver(config=config).run(record, probe)
    if outcome.terminal_status is not TerminalStatus.CLOSED_VERIFIED:
        pytest.skip(f"reference proof did not replay: {outcome.terminal_status} {outcome.error}")
    trajectory = outcome.trajectory
    assert trajectory is not None

    swapped = replace(
        trajectory,
        actions=tuple(replace(action, tactic="aesop") for action in trajectory.actions),
    )
    relived = relive_trajectory(swapped, probe, config=config)
    assert not relived.matched
    assert "stored action" in relived.detail, relived.detail
