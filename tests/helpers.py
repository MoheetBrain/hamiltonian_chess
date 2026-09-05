from __future__ import annotations

from arena.canonical.schema import (
    Binding,
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    EvidenceNode,
    MathObject,
    Obligation,
)


def integer(value: int) -> CanonicalExpression:
    return CanonicalExpression("integer", value=value, sort="Int")


def variable(name: str, sort: str = "Real") -> CanonicalExpression:
    return CanonicalExpression("var", value=name, sort=sort)


def sample_state(*, metadata: tuple[tuple[str, str], ...] = ()) -> CanonicalState:
    x = variable("x")
    one = CanonicalExpression("real", value=1.0, sort="Real")
    expression = CanonicalExpression("div", (x, one), sort="Real")
    defined = CanonicalExpression("defined", (expression,), sort="Proposition")
    action = CanonicalAction(
        "a:simplify",
        "simplify",
        ("goal",),
        arguments=(expression,),
        warrant="field identity",
    )
    invalid = CanonicalAction(
        "a:divide-zero",
        "divide",
        ("goal",),
        arguments=(integer(0),),
        warrant="invalid zero divisor",
        expected_usefulness=0.0,
    )
    return CanonicalState(
        state_id="state:sample",
        objects=(MathObject("x", "Real"),),
        bindings=(Binding("b:x", "x", "Real", "scope:root"),),
        assumptions=(CanonicalExpression("eq", (x, x), sort="Proposition"),),
        established_facts=(),
        propositions=(defined,),
        goal=CanonicalExpression("eq", (expression, x), sort="Proposition"),
        obligations=(Obligation("o:defined", defined),),
        evidence_dependencies=(EvidenceNode("e:given", "ASSUMED"),),
        local_scope=("scope:root",),
        legal_actions=(action,),
        plausible_invalid_actions=(invalid,),
        execution_metadata=metadata,
    )
