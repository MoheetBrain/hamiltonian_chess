"""Parser/renderer round-trip, quoting and value fidelity."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    LOSSLESS,
    PROMPT_VIEW,
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Goal,
    Scope,
    State,
    Term,
    Type,
    parse_state,
    render_state,
)

from .conftest import NAT, PROP, build_minimal_state, build_rich_state


def test_rich_state_round_trips_exactly(rich_state: State) -> None:
    text = render_state(rich_state)
    assert parse_state(text) == rich_state


def test_rendering_is_idempotent(rich_state: State) -> None:
    text = render_state(rich_state)
    assert render_state(parse_state(text)) == text


def test_minimal_state_round_trips(minimal_state: State) -> None:
    assert parse_state(render_state(minimal_state)) == minimal_state


def test_document_ends_with_a_newline_and_starts_with_the_magic(rich_state: State) -> None:
    text = render_state(rich_state)
    assert text.startswith("TL0 0.1.0 state:demo\n")
    assert text.endswith("status OPEN\n")


@pytest.mark.parametrize(
    "value",
    [None, 0, 1, -17, 2**70, 1.5, -0.25, 1e20, 1e-20, True, False, "", "plain", 'q"uote'],
)
def test_every_value_kind_round_trips(value: object) -> None:
    state = State(
        state_id="s.v",
        scopes=(Scope("r"),),
        goals=(Goal("g", "r", Term("lit", NAT, value)),),  # type: ignore[arg-type]
    )
    assert parse_state(render_state(state)) == state


@pytest.mark.parametrize(
    "text",
    [
        'quotes "here"',
        "back\\slash",
        "new\nline",
        "carriage\rreturn",
        "tab\there",
        "unicode ∀x ∈ ℝ",
        "control \x00\x01\x1f\x7f",
        "brackets ( ) [ ] { } = #",
        " leading and trailing ",
    ],
)
def test_awkward_text_survives_quoting(text: str) -> None:
    state = State(
        state_id="s.q",
        scopes=(Scope("r"),),
        declarations=(Decl("d", text, Type(text), "r", DeclKind.FREE),),
        claims=(Claim("c", ClaimRole.FACT, "r", Term("op", PROP, text), attributes={"k": text}),),
    )
    rendered = render_state(state)
    # Newlines inside data must be escaped, so the record count is unaffected by content.
    assert len(rendered.splitlines()) == 5
    assert parse_state(rendered) == state


def test_deeply_nested_structured_types_round_trip() -> None:
    sort = Type("A", (Type("B", (Type("C", (Type("D"),)),)), Type("E")))
    state = State(state_id="s.t", scopes=(Scope("r"),), goals=(Goal("g", "r", Term("x", sort)),))
    assert parse_state(render_state(state)) == state


def test_zero_one_and_many_goals_all_round_trip() -> None:
    for count in (0, 1, 2, 5):
        goals = tuple(
            Goal(f"g.{index}", "r", Term("p", PROP), focused=index == 0) for index in range(count)
        )
        state = State(state_id="s.g", scopes=(Scope("r"),), goals=goals)
        assert parse_state(render_state(state)) == state
        assert len(state.goals) == count


def test_prompt_view_is_declared_lossy_and_omits_actions(rich_state: State) -> None:
    assert LOSSLESS.is_lossless
    assert not PROMPT_VIEW.is_lossless
    view = render_state(rich_state, PROMPT_VIEW)
    assert "\nact " not in view
    assert "\nact " in render_state(rich_state, LOSSLESS)


def test_two_distinct_states_never_render_alike() -> None:
    first = build_rich_state("state:a")
    second = build_rich_state("state:b")
    assert render_state(first) != render_state(second)
    assert render_state(build_minimal_state()) != render_state(first)
