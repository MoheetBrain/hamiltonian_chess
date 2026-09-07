"""Shared fixtures for the TRAINING_LANGUAGE_V0 conformance suite."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Action,
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Evidence,
    Extension,
    Goal,
    LibraryRef,
    Obligation,
    Scope,
    State,
    Status,
    Term,
    Type,
)

NAT = Type("Nat")
PROP = Type("Prop")
FUN = Type("Fun", (NAT, PROP))
DEEP = Type("Fun", (Type("List", (Type("Pair", (NAT, NAT)),)), Type("Set", (PROP,))))


def var(name: str, sort: Type = NAT) -> Term:
    return Term("var", sort, name)


def lit(value: int, sort: Type = NAT) -> Term:
    return Term("lit", sort, value)


def build_rich_state(state_id: str = "state:demo") -> State:
    """A state that exercises every measured REQUIRED gap at once."""

    return State(
        state_id=state_id,
        scopes=(Scope("s0"), Scope("s1", "s0"), Scope("s2", "s0")),
        libraries=(LibraryRef("core", "0.1.0"), LibraryRef("algebra", "0.1.0")),
        declarations=(
            Decl("d.n", "n", NAT, "s0", DeclKind.FORALL),
            Decl("d.p", "P", FUN, "s0", DeclKind.IMPLICIT),
            Decl(
                "d.k",
                "k",
                NAT,
                "s1",
                DeclKind.LET,
                value=Term("add", NAT, None, (var("n"), lit(1))),
            ),
            Decl("d.deep", "phi", DEEP, "s1", DeclKind.INSTANCE),
            Decl("m.1", "?m", NAT, "s2", DeclKind.METAVAR),
            Decl(
                "o.mat",
                "M",
                Type("Matrix", (NAT,)),
                "s0",
                DeclKind.OBJECT,
                value=lit(3),
                attributes={"canonical.shape": "[2, 2]", "canonical.unit": "m"},
            ),
        ),
        claims=(
            Claim("c.1", ClaimRole.ASSUMPTION, "s0", Term("le", PROP, None, (lit(0), var("n")))),
            Claim(
                "c.2",
                ClaimRole.FACT,
                "s1",
                Term("lt", PROP, None, (var("n"), var("k"))),
                Status.VERIFIED,
                "e.1",
                depends_on=("c.1",),
                attributes={"note": 'needs "quotes"\nand a newline\tand a tab'},
            ),
            Claim("c.3", ClaimRole.PROPOSITION, "s2", Term("odd", PROP), Status.PROPOSED),
            Claim("c.4", ClaimRole.IDENTITY, "s0", Term("eq", PROP, None, (var("n"), var("n")))),
        ),
        goals=(
            Goal("g.1", "s1", Term("even", PROP, None, (var("k"),)), Status.OPEN, True),
            Goal("g.2", "s2", Term("odd", PROP, None, (Term("mvar", NAT, "?m"),)), Status.OPEN),
        ),
        obligations=(
            Obligation(
                "ob.1",
                "s2",
                Term("pos", PROP, None, (Term("mvar", NAT, "?m"),)),
                Status.OPEN,
                "case split",
                attributes={"origin": "split"},
            ),
        ),
        evidence=(
            Evidence("e.1", Status.VERIFIED, "arena.native", "0.1.0", "abc123", "kernel accepted"),
            Evidence("e.2", Status.OPEN, details="not attempted"),
        ),
        substitution=(("m.1", lit(7)),),
        actions=(
            Action(
                "a.1",
                "rewrite",
                ("g.1",),
                (Term("lemma", PROP, "add_comm"),),
                "commutativity of +",
                (Term("true", PROP, True),),
                (
                    Obligation(
                        "ob.gen", "s1", Term("ne", PROP, None, (var("k"),)), Status.OPEN, "rewrite"
                    ),
                ),
                Status.PROPOSED,
                attributes={"rank": "1"},
            ),
            Action("a.2", "bogus step", ("o.mat",), (), "", (), (), Status.REFUTED),
        ),
        extensions=(
            Extension("g.2", "lean.universe_levels", '["u","v"]'),
            Extension("a.1", "canonical.expected_usefulness", "0.75"),
        ),
        terminal_status="OPEN",
    )


def build_minimal_state() -> State:
    return State(state_id="state:min", scopes=(Scope("root"),))


def build_single_goal_state() -> State:
    return State(
        state_id="state:one",
        scopes=(Scope("root"),),
        declarations=(Decl("d.x", "x", NAT, "root", DeclKind.FREE),),
        goals=(Goal("g.only", "root", Term("even", PROP, None, (var("x"),)), Status.OPEN, True),),
    )


@pytest.fixture
def rich_state() -> State:
    return build_rich_state()


@pytest.fixture
def minimal_state() -> State:
    return build_minimal_state()


@pytest.fixture
def single_goal_state() -> State:
    return build_single_goal_state()
