"""The extension rule: a domain is data, and adding one changes no rendered byte."""

from __future__ import annotations

from releases.TRAINING_LANGUAGE_V0 import (
    ALGEBRA_LIBRARY,
    CORE_LIBRARY,
    STANDARD_LIBRARIES,
    Goal,
    OperationSpec,
    OperatorSpec,
    Scope,
    State,
    Term,
    check_vocabulary,
    render_state,
)

from .conftest import NAT, PROP, build_rich_state

TOPOLOGY = CORE_LIBRARY.extend(
    library_id="topology",
    version="0.1.0",
    summary="Point-set topology, added as data only.",
    sorts=("Space", "Open", "Filter"),
    operators=(OperatorSpec("interior", 1, "Open", "topological interior"),),
    operations=(OperationSpec("refine_cover", "refine an open cover"),),
)


def _state_using_topology() -> State:
    return State(
        state_id="s.top",
        scopes=(Scope("r"),),
        goals=(Goal("g", "r", Term("interior", PROP, None, (Term("var", NAT, "U"),))),),
    )


def test_core_vocabulary_covers_a_core_only_state() -> None:
    state = State(
        state_id="s",
        scopes=(Scope("r"),),
        goals=(
            Goal("g", "r", Term("eq", PROP, None, (Term("var", NAT, "a"), Term("lit", NAT, 1)))),
        ),
    )
    assert check_vocabulary(state, (CORE_LIBRARY,)).is_complete


def test_unknown_vocabulary_is_reported_not_raised() -> None:
    report = check_vocabulary(_state_using_topology(), (CORE_LIBRARY,))
    assert not report.is_complete
    assert report.unknown_operators == ("interior",)


def test_registering_a_domain_library_completes_the_report() -> None:
    assert check_vocabulary(_state_using_topology(), (TOPOLOGY,)).is_complete


def test_adding_a_library_changes_no_rendered_byte() -> None:
    state = _state_using_topology()
    before = render_state(state)
    assert check_vocabulary(state, (CORE_LIBRARY,)).unknown_operators == ("interior",)
    assert check_vocabulary(state, (TOPOLOGY,)).unknown_operators == ()
    assert render_state(state) == before


def test_extending_preserves_the_parent_vocabulary() -> None:
    assert set(CORE_LIBRARY.sorts) <= set(ALGEBRA_LIBRARY.sorts)
    assert set(item.symbol for item in CORE_LIBRARY.operators) <= set(
        item.symbol for item in ALGEBRA_LIBRARY.operators
    )


def test_library_content_hashes_are_stable_and_distinct() -> None:
    assert CORE_LIBRARY.content_hash == CORE_LIBRARY.content_hash
    assert len({item.content_hash for item in (*STANDARD_LIBRARIES, TOPOLOGY)}) == 3


def test_the_rich_state_reports_its_undeclared_vocabulary_honestly() -> None:
    report = check_vocabulary(build_rich_state(), STANDARD_LIBRARIES)
    assert "pos" in report.unknown_operators
    assert "bogus step" in report.unknown_operations
    assert "Matrix" not in report.unknown_sorts
