"""Binding, scope, per-goal context, structured types and the substitution structure."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Goal,
    Scope,
    State,
    Term,
    TL0Error,
    Type,
    parse_state,
    render_state,
    render_type,
)
from releases.TRAINING_LANGUAGE_V0.canonical_adapter import decode_type, encode_type

from .conftest import DEEP, FUN, NAT, PROP


def test_scope_chain_is_root_to_leaf(rich_state: State) -> None:
    assert rich_state.scope_chain("s1") == ("s0", "s1")
    assert rich_state.scope_chain("s0") == ("s0",)


def test_two_goals_hold_genuinely_different_contexts(rich_state: State) -> None:
    first = {item.decl_id for item in rich_state.declarations_in_scope("s1")}
    second = {item.decl_id for item in rich_state.declarations_in_scope("s2")}
    assert "d.k" in first and "d.k" not in second
    assert "m.1" in second and "m.1" not in first
    assert "d.n" in first and "d.n" in second  # inherited from the shared parent


def test_a_cyclic_scope_forest_is_refused() -> None:
    with pytest.raises(TL0Error, match="cycle"):
        State(state_id="s", scopes=(Scope("a", "b"), Scope("b", "a")))


def test_a_scope_cannot_be_its_own_parent() -> None:
    with pytest.raises(TL0Error, match="own parent"):
        Scope("a", "a")


def test_an_unknown_parent_scope_is_refused() -> None:
    with pytest.raises(TL0Error, match="unknown parent"):
        State(state_id="s", scopes=(Scope("a", "missing"),))


def test_a_record_in_an_undeclared_scope_is_refused() -> None:
    with pytest.raises(TL0Error, match="unknown scope"):
        State(
            state_id="s",
            scopes=(Scope("r"),),
            claims=(Claim("c", ClaimRole.FACT, "elsewhere", Term("p", PROP)),),
        )


def test_let_bound_declarations_carry_their_value() -> None:
    value = Term("add", NAT, None, (Term("var", NAT, "n"), Term("lit", NAT, 1)))
    state = State(
        state_id="s",
        scopes=(Scope("r"),),
        declarations=(Decl("d", "k", NAT, "r", DeclKind.LET, value=value),),
    )
    parsed = parse_state(render_state(state))
    assert parsed.declarations[0].value == value


@pytest.mark.parametrize("kind", list(DeclKind))
def test_every_binder_kind_round_trips(kind: DeclKind) -> None:
    state = State(
        state_id="s",
        scopes=(Scope("r"),),
        declarations=(Decl("d", "x", NAT, "r", kind),),
    )
    assert parse_state(render_state(state)).declarations[0].kind is kind


@pytest.mark.parametrize("sort", [NAT, PROP, FUN, DEEP, Type("A", (Type("B"), Type("C")))])
def test_type_encoding_is_injective_and_reversible(sort: Type) -> None:
    assert decode_type(encode_type(sort)) == sort


def test_type_encoding_distinguishes_shapes_a_flat_string_would_confuse() -> None:
    left = Type("F", (Type("G", (Type("H"),)),))
    right = Type("F", (Type("G"), Type("H")))
    assert render_type(left) != render_type(right)
    assert decode_type(render_type(left)) == left
    assert decode_type(render_type(right)) == right


def test_a_foreign_flat_sort_becomes_a_bare_head() -> None:
    assert decode_type("Nat") == Type("Nat")
    assert decode_type("list of nat") == Type("list of nat")
    assert decode_type("") == Type("Unknown")


def test_substitution_must_name_a_declared_metavariable() -> None:
    with pytest.raises(TL0Error, match="undeclared metavariable"):
        State(
            state_id="s",
            scopes=(Scope("r"),),
            declarations=(Decl("d", "x", NAT, "r", DeclKind.FREE),),
            substitution=(("d", Term("lit", NAT, 1)),),
        )


def test_substitution_rejects_a_duplicate_assignment() -> None:
    with pytest.raises(TL0Error, match="duplicate substitution"):
        State(
            state_id="s",
            scopes=(Scope("r"),),
            declarations=(Decl("m", "?m", NAT, "r", DeclKind.METAVAR),),
            substitution=(("m", Term("lit", NAT, 1)), ("m", Term("lit", NAT, 2))),
        )


def test_focus_goal_prefers_the_focused_goal(rich_state: State) -> None:
    assert rich_state.focus_goal is not None
    assert rich_state.focus_goal.goal_id == "g.1"
    unfocused = State(
        state_id="s",
        scopes=(Scope("r"),),
        goals=(Goal("a", "r", Term("p", PROP)), Goal("b", "r", Term("q", PROP))),
    )
    assert unfocused.focus_goal is not None
    assert unfocused.focus_goal.goal_id == "a"
    assert State(state_id="s", scopes=(Scope("r"),)).focus_goal is None
