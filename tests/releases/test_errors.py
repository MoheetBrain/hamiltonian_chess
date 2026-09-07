"""Item I error cases.  TL0 fails closed: every malformed input raises a TL0Error."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Extension,
    Goal,
    Scope,
    State,
    Term,
    TL0Error,
    TL0SyntaxError,
    Type,
    parse_state,
)

from .conftest import NAT, PROP

HEAD = "TL0 0.1.0 s\n"


@pytest.mark.parametrize(
    "document,reason",
    [
        ("", "empty document"),
        ("NOTTL0 0.1.0 s\nstatus OPEN\n", "wrong magic"),
        ("TL0 0.1.0 s\n", "no status record"),
        (HEAD + "status OPEN\nstatus OPEN\n", "duplicate status"),
        (HEAD + "wibble x\nstatus OPEN\n", "unknown record"),
        (HEAD + "scope\nstatus OPEN\n", "missing field"),
        (HEAD + "scope r _ extra\nstatus OPEN\n", "trailing token"),
        (HEAD + 'ext r k "unterminated\nstatus OPEN\n', "unterminated string"),
        (HEAD + 'ext r k "bad \\q escape"\nstatus OPEN\n', "unknown escape"),
        (HEAD + 'ext r k "bad \\u00zz"\nstatus OPEN\n', "malformed unicode escape"),
        (HEAD + "scope r _\ngoal g r NOPE 0 _ (p [Prop] _)\nstatus OPEN\n", "unknown status"),
        (HEAD + "scope r _\ngoal g r OPEN 7 _ (p [Prop] _)\nstatus OPEN\n", "bad focus flag"),
        (HEAD + "scope r _\nclaim c nonsense r OPEN _ (p [Prop] _)\nstatus OPEN\n", "unknown role"),
        (HEAD + "scope r _\ndecl d x [Nat] r nonsense _\nstatus OPEN\n", "unknown decl kind"),
        (HEAD + "scope r _\nscope r _\nstatus OPEN\n", "duplicate scope"),
        (
            HEAD + "scope r _\ngoal g elsewhere OPEN 0 _ (p [Prop] _)\nstatus OPEN\n",
            "unknown scope",
        ),
        (HEAD + "scope r _\ndep nobody r\nstatus OPEN\n", "dep with unknown owner"),
        (HEAD + "scope r _\nact a op PROPOSED _\n  target r\nstatus OPEN\n", "unterminated act"),
        (
            HEAD + "scope r _\nact a op PROPOSED _\n  wat x\nend\nstatus OPEN\n",
            "unknown sub-record",
        ),
        (HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop] #z 1)\nstatus OPEN\n", "unknown value tag"),
        (HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop] #i notanint)\nstatus OPEN\n", "bad int"),
        (HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop] #b maybe)\nstatus OPEN\n", "bad bool"),
        (HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop] _\nstatus OPEN\n", "unclosed term"),
        (HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop _)\nstatus OPEN\n", "unclosed type"),
        (
            HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop] _ {k=bare})\nstatus OPEN\n",
            "unquoted attribute",
        ),
        (
            HEAD + "scope r _\ngoal g r OPEN 0 _ (p [Prop] _) \u00a7\nstatus OPEN\n",
            "illegal character",
        ),
    ],
)
def test_malformed_documents_raise(document: str, reason: str) -> None:
    with pytest.raises(TL0Error):
        parse_state(document)
    assert reason


def test_non_text_input_is_refused() -> None:
    with pytest.raises(TL0SyntaxError, match="must be text"):
        parse_state(b"TL0 0.1.0 s\n")  # type: ignore[arg-type]


def test_duplicate_record_ids_are_refused() -> None:
    with pytest.raises(TL0Error, match="duplicate record id"):
        State(
            state_id="s",
            scopes=(Scope("r"),),
            goals=(Goal("x", "r", Term("p", PROP)),),
            claims=(Claim("x", ClaimRole.FACT, "r", Term("q", PROP)),),
        )


def test_a_dependency_on_an_unknown_id_is_refused() -> None:
    with pytest.raises(TL0Error, match="depends on unknown id"):
        State(
            state_id="s",
            scopes=(Scope("r"),),
            claims=(Claim("c", ClaimRole.FACT, "r", Term("p", PROP), depends_on=("ghost",)),),
        )


def test_an_extension_naming_an_unknown_owner_is_refused() -> None:
    with pytest.raises(TL0Error, match="unknown owner"):
        State(state_id="s", scopes=(Scope("r"),), extensions=(Extension("ghost", "k", "v"),))


def test_an_extension_may_name_the_state_itself() -> None:
    state = State(state_id="s", scopes=(Scope("r"),), extensions=(Extension("s", "k", "v"),))
    assert state.extensions[0].owner_id == "s"


def test_the_reserved_attribute_namespace_is_refused() -> None:
    with pytest.raises(TL0Error, match="reserved"):
        Term("p", PROP, attributes={"tl0.claim_id": "c"})
    with pytest.raises(TL0Error, match="reserved"):
        Decl("d", "x", NAT, "r", DeclKind.FREE, attributes={"tl0.anything": "1"})


def test_ids_must_be_bare_identifiers() -> None:
    for bad in ("", "_leading", "has space", "-dash", "uni\u00a7code"):
        with pytest.raises(TL0Error, match="bare identifier"):
            Scope(bad)


def test_labels_must_be_non_empty_but_may_be_awkward() -> None:
    with pytest.raises(TL0Error, match="non-empty"):
        Type("")
    with pytest.raises(TL0Error, match="non-empty"):
        Term("", PROP)
    assert Type("list of nat").head == "list of nat"


def test_non_finite_values_are_refused() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(TL0Error, match="finite"):
            Term("lit", NAT, value)


def test_an_unsupported_language_version_is_refused() -> None:
    with pytest.raises(TL0Error, match="unsupported TL0 version"):
        State(state_id="s", scopes=(Scope("r"),), language_version="9.9.9")
    with pytest.raises(TL0Error, match="unsupported TL0 version"):
        parse_state("TL0 9.9.9 s\nscope r _\nstatus OPEN\n")


def test_whitespace_and_blank_lines_are_tolerated() -> None:
    document = "\n  TL0 0.1.0 s  \n\n   scope r _\n\n  status OPEN  \n\n"
    assert parse_state(document).state_id == "s"
