"""Item C/I: state transitions, the computed delta, and its fail-closed verification rule."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Action,
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Evidence,
    Goal,
    Obligation,
    Scope,
    State,
    Status,
    StatusError,
    Term,
    TrainingDataError,
    Transition,
    VerificationOutcome,
    build_default_registry,
)

from .conftest import NAT, PROP

SPLIT = Action(
    "a.split",
    "split",
    ("g.0",),
    (),
    "case analysis on parity",
    (),
    (Obligation("ob.even", "s.a", Term("even", PROP), Status.OPEN, "split"),),
)
ACCEPTED = VerificationOutcome("arena.native", "0.1.0", Status.VERIFIED, True, details="ok")
RECORD = Evidence("e.v", Status.VERIFIED, "arena.native", "0.1.0")


def _before() -> State:
    return State(
        state_id="s.before",
        scopes=(Scope("s.a"),),
        declarations=(Decl("d.n", "n", NAT, "s.a", DeclKind.FREE),),
        goals=(Goal("g.0", "s.a", Term("p", PROP), Status.OPEN, True),),
        actions=(SPLIT,),
    )


def _after() -> State:
    return State(
        state_id="s.after",
        scopes=(Scope("s.a"), Scope("s.b", "s.a")),
        declarations=(
            Decl("d.n", "n", NAT, "s.a", DeclKind.FREE),
            Decl("d.k", "k", NAT, "s.b", DeclKind.FREE),
        ),
        claims=(Claim("c.new", ClaimRole.FACT, "s.a", Term("q", PROP), Status.DERIVED),),
        goals=(
            Goal("g.0", "s.a", Term("p", PROP), Status.VERIFIED, True, "e.v"),
            Goal("g.1", "s.b", Term("r", PROP), Status.OPEN),
        ),
        obligations=(Obligation("ob.even", "s.a", Term("even", PROP), Status.OPEN, "split"),),
        evidence=(RECORD,),
        terminal_status="BRANCHING",
    )


def test_the_delta_is_computed_from_the_two_states() -> None:
    delta = Transition("t.1", _before(), SPLIT, _after(), (ACCEPTED,)).delta()
    assert delta.goals_added == ("g.1",)
    assert delta.goals_removed == ()
    assert delta.goals_closed == ("g.0",)
    assert delta.obligations_added == ("ob.even",)
    assert delta.claims_added == ("c.new",)
    assert delta.declarations_added == ("d.k",)
    assert delta.evidence_added == ("e.v",)
    assert delta.scopes_added == ("s.b",)
    assert delta.generated_obligations_missing == ()
    assert delta.terminal_status_changed
    assert not delta.is_empty


def test_a_no_op_transition_reports_an_empty_delta() -> None:
    state = _before()
    delta = Transition("t.0", state, SPLIT, state).delta()
    assert delta.is_empty
    assert delta.generated_obligations_missing == ("ob.even",)


def test_a_verified_outcome_without_a_record_in_the_next_state_is_refused() -> None:
    unrecorded = State(
        state_id="s.after",
        scopes=(Scope("s.a"),),
        goals=(Goal("g.0", "s.a", Term("p", PROP), Status.OPEN, True),),
    )
    with pytest.raises(StatusError, match="no matching verification record"):
        Transition("t.bad", _before(), SPLIT, unrecorded, (ACCEPTED,))


def test_a_transition_may_carry_an_unverified_outcome_without_a_record() -> None:
    refuted = VerificationOutcome("arena.native", "0.1.0", Status.REFUTED, False, details="no")
    unrecorded = State(
        state_id="s.after",
        scopes=(Scope("s.a"),),
        goals=(Goal("g.0", "s.a", Term("p", PROP), Status.OPEN, True),),
    )
    transition = Transition("t.ok", _before(), SPLIT, unrecorded, (refuted,))
    assert transition.verification[0].status is Status.REFUTED
    assert transition.delta().generated_obligations_missing == ("ob.even",)


def test_an_action_may_not_be_substituted_under_an_offered_id() -> None:
    impostor = Action("a.split", "close", (), (), "different action, same id")
    with pytest.raises(TrainingDataError, match="differs from the action of the same id"):
        Transition("t.x", _before(), impostor, _after())


def test_an_externally_proposed_action_is_allowed() -> None:
    fresh = Action("a.fresh", "apply", (), (Term("lemma", PROP, "L"),))
    assert Transition("t.y", _before(), fresh, _after()).action is fresh


def test_a_transition_serialises_with_a_content_hash() -> None:
    surface = build_default_registry().default
    payload = Transition("t.1", _before(), SPLIT, _after(), (ACCEPTED,)).to_dict(surface)
    assert set(payload) == {
        "transition_id",
        "state_before",
        "rendered_state_before",
        "action",
        "rendered_action",
        "state_after",
        "rendered_state_after",
        "verification",
        "delta",
        "surface",
        "content_hash",
    }
    assert len(str(payload["content_hash"])) == 64


def test_the_transition_id_must_be_present() -> None:
    with pytest.raises(TrainingDataError, match="transition_id"):
        Transition("", _before(), SPLIT, _after())
