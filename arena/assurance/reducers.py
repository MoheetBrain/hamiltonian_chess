"""Deterministic delta-debugging for minimal reproducible failures."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import fields, replace

from arena.canonical.schema import (
    CanonicalExpression,
    CanonicalState,
    CanonicalTransition,
)


def ddmin_sequence[T](
    items: Sequence[T], reproduces: Callable[[tuple[T, ...]], bool]
) -> tuple[T, ...]:
    """Return a 1-minimal subsequence using deterministic delta debugging."""

    current = tuple(items)
    if not reproduces(current):
        raise ValueError("the initial sequence does not reproduce the failure")
    granularity = 2
    while len(current) >= 1:
        chunk_size = max(1, (len(current) + granularity - 1) // granularity)
        reduced = False
        for start in range(0, len(current), chunk_size):
            complement = current[:start] + current[start + chunk_size :]
            if reproduces(complement):
                current = complement
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)

    # Guarantee 1-minimality even when non-monotone predicates defeat chunk removal.
    index = 0
    while index < len(current):
        candidate = current[:index] + current[index + 1 :]
        if reproduces(candidate):
            current = candidate
        else:
            index += 1
    return current


def minimize_text(source: str, reproduces: Callable[[str], bool]) -> str:
    """Reduce first by lines/tokens and then by characters."""

    if not reproduces(source):
        raise ValueError("the source does not reproduce the failure")
    current = source
    lines = current.splitlines(keepends=True)
    if len(lines) > 1:
        current = "".join(ddmin_sequence(lines, lambda parts: reproduces("".join(parts))))
    tokens = tuple(current.split())
    if len(tokens) > 1:
        token_reduced = " ".join(ddmin_sequence(tokens, lambda parts: reproduces(" ".join(parts))))
        if reproduces(token_reduced):
            current = token_reduced
    return "".join(ddmin_sequence(tuple(current), lambda parts: reproduces("".join(parts))))


def _reduce_tuple_field(
    state: CanonicalState,
    field_name: str,
    reproduces: Callable[[CanonicalState], bool],
) -> CanonicalState:
    values = getattr(state, field_name)
    if not values:
        return state

    def predicate(candidate: tuple[object, ...]) -> bool:
        return reproduces(replace(state, **{field_name: candidate}))  # type: ignore[arg-type]

    reduced = ddmin_sequence(values, predicate)
    return replace(state, **{field_name: reduced})  # type: ignore[arg-type]


def _expression_candidates(expression: CanonicalExpression) -> tuple[CanonicalExpression, ...]:
    candidates: list[CanonicalExpression] = list(expression.args)
    for index, argument in enumerate(expression.args):
        for simpler in _expression_candidates(argument):
            args = list(expression.args)
            args[index] = simpler
            candidates.append(replace(expression, args=tuple(args)))
    seen: set[str] = set()
    unique: list[CanonicalExpression] = []
    for candidate in candidates:
        if candidate.content_hash not in seen:
            seen.add(candidate.content_hash)
            unique.append(candidate)
    return tuple(unique)


def minimize_expression(
    expression: CanonicalExpression, reproduces: Callable[[CanonicalExpression], bool]
) -> CanonicalExpression:
    if not reproduces(expression):
        raise ValueError("the expression does not reproduce the failure")
    current = expression
    changed = True
    while changed:
        changed = False
        for candidate in _expression_candidates(current):
            if reproduces(candidate):
                current = candidate
                changed = True
                break
    return current


def minimize_state(
    state: CanonicalState, reproduces: Callable[[CanonicalState], bool]
) -> CanonicalState:
    """Reduce collections and expression trees while retaining ``reproduces``."""

    if not reproduces(state):
        raise ValueError("the state does not reproduce the failure")
    current = state
    tuple_fields = (
        "objects",
        "bindings",
        "assumptions",
        "established_facts",
        "propositions",
        "obligations",
        "evidence_dependencies",
        "local_scope",
        "legal_actions",
        "plausible_invalid_actions",
        "execution_metadata",
    )
    for field_name in tuple_fields:
        current = _reduce_tuple_field(current, field_name, reproduces)

    minimized_goal = minimize_expression(
        current.goal, lambda goal: reproduces(replace(current, goal=goal))
    )
    current = replace(current, goal=minimized_goal)

    for collection_name in ("assumptions", "established_facts", "propositions"):
        values = list(getattr(current, collection_name))
        for index, expression in enumerate(values):
            current_state = current
            current_values = values

            def expression_reproduces(
                item: CanonicalExpression,
                i: int = index,
                values_: list[CanonicalExpression] = current_values,
                state_: CanonicalState = current_state,
                name: str = collection_name,
            ) -> bool:
                replacements = tuple(
                    item if offset == i else value for offset, value in enumerate(values_)
                )
                candidate_state = replace(state_, **{name: replacements})  # type: ignore[arg-type]
                return reproduces(candidate_state)

            values[index] = minimize_expression(
                expression,
                expression_reproduces,
            )
        candidate = replace(current, **{collection_name: tuple(values)})  # type: ignore[arg-type]
        if reproduces(candidate):
            current = candidate

    obligations = list(current.obligations)
    for index, obligation in enumerate(obligations):

        def proposition_reproduces(proposition: CanonicalExpression, i: int = index) -> bool:
            return reproduces(
                replace(
                    current,
                    obligations=tuple(
                        replace(item, proposition=proposition) if offset == i else item
                        for offset, item in enumerate(obligations)
                    ),
                )
            )

        minimized = minimize_expression(
            obligation.proposition,
            proposition_reproduces,
        )
        obligations[index] = replace(obligation, proposition=minimized)
    candidate = replace(current, obligations=tuple(obligations))
    return candidate if reproduces(candidate) else current


def minimize_transition(
    transition: CanonicalTransition,
    reproduces: Callable[[CanonicalTransition], bool],
) -> CanonicalTransition:
    if not reproduces(transition):
        raise ValueError("the transition does not reproduce the failure")
    current = transition
    before = minimize_state(
        current.state_before,
        lambda state: reproduces(replace(current, state_before=state)),
    )
    current = replace(current, state_before=before)
    after = minimize_state(
        current.state_after,
        lambda state: reproduces(replace(current, state_after=state)),
    )
    current = replace(current, state_after=after)
    verification = ddmin_sequence(
        current.verification,
        lambda records: reproduces(replace(current, verification=records)),
    )
    return replace(current, verification=verification)


def minimize_subject(
    subject: CanonicalState | CanonicalTransition,
    reproduces: Callable[[CanonicalState | CanonicalTransition], bool],
) -> CanonicalState | CanonicalTransition:
    if isinstance(subject, CanonicalTransition):
        return minimize_transition(subject, lambda item: reproduces(item))
    return minimize_state(subject, lambda item: reproduces(item))


def is_one_minimal_sequence[T](
    items: Sequence[T], reproduces: Callable[[tuple[T, ...]], bool]
) -> bool:
    """Check the concrete minimality guarantee made by :func:`ddmin_sequence`."""

    current = tuple(items)
    return reproduces(current) and all(
        not reproduces(current[:index] + current[index + 1 :]) for index in range(len(current))
    )


# A guard against accidentally adding mutable fields to the canonical state reducer.
assert all(field.init for field in fields(CanonicalState))
