import pytest

from arena.canonical.schema import (
    Binding,
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    EvidenceNode,
    MathObject,
    Obligation,
)


@pytest.fixture
def representative_state() -> CanonicalState:
    x = CanonicalExpression("symbol", value="x", sort="Real", attributes=(("role", "free"),))
    zero = CanonicalExpression("literal", value=0, sort="Real")
    two = CanonicalExpression("literal", value=2, sort="Integer")
    squared = CanonicalExpression("power", (x, two), sort="Real")
    nonnegative = CanonicalExpression("ge", (squared, zero), sort="Proposition")
    goal = CanonicalExpression("equals", (squared, zero), sort="Proposition")
    obligation = Obligation("obl:defined", nonnegative, source="domain-check")
    solve = CanonicalAction(
        action_id="act:factor",
        operation="factor",
        target_ids=("obj:polynomial",),
        arguments=(squared,),
        warrant="ring-normalization",
        preconditions=(nonnegative,),
        generated_obligations=(obligation,),
        expected_usefulness=0.875,
    )
    invalid = CanonicalAction(
        action_id="act:divide-zero",
        operation="divide",
        target_ids=("obj:polynomial",),
        arguments=(zero,),
        warrant="cancellation",
        expected_usefulness=-0.25,
    )
    return CanonicalState(
        state_id="state:representative-α",
        objects=(
            MathObject("obj:polynomial", "Polynomial[Real]", squared, shape=(2, "n")),
            MathObject("obj:distance", "Quantity", unit="m/s"),
        ),
        bindings=(Binding("bind:x", "x", "Real", "scope:root", "forall"),),
        assumptions=(nonnegative,),
        established_facts=(CanonicalExpression("finite", (x,), sort="Proposition"),),
        propositions=(goal, nonnegative),
        goal=goal,
        obligations=(obligation,),
        evidence_dependencies=(
            EvidenceNode("ev:1", "VERIFIED", (), "native", "abc123"),
            EvidenceNode("ev:2", "UNKNOWN", ("ev:1",), "sympy", None),
        ),
        local_scope=("scope:root", "bind:x"),
        legal_actions=(solve,),
        plausible_invalid_actions=(invalid,),
        terminal_status="OPEN",
        execution_metadata=(("model", "test-model"), ("run", "007")),
    )
