"""Canonical equality and conservative alpha-normalization utilities."""

from __future__ import annotations

from arena.canonical.schema import CanonicalExpression, CanonicalState

BINDERS = {"forall", "exists", "lambda", "sum_over", "integral_over"}


def alpha_normalize(expression: CanonicalExpression) -> CanonicalExpression:
    """Replace bound-variable spellings by depth-indexed identities.

    Binder nodes must have `(variable, body, ...)` arguments. Free variables are preserved.
    This deliberately rejects no syntax; structural validators enforce binder arity.
    """

    def visit(node: CanonicalExpression, environment: tuple[str, ...]) -> CanonicalExpression:
        if node.op == "var" and isinstance(node.value, str) and node.value in environment:
            distance = len(environment) - 1 - environment[::-1].index(node.value)
            return CanonicalExpression("bound", value=distance, sort=node.sort)
        if node.op in BINDERS and len(node.args) >= 2:
            binder = node.args[0]
            if binder.op != "var" or not isinstance(binder.value, str):
                return CanonicalExpression(
                    node.op,
                    tuple(visit(arg, environment) for arg in node.args),
                    node.value,
                    node.sort,
                    node.attributes,
                )
            normalized_var = CanonicalExpression("binder", value=len(environment), sort=binder.sort)
            remainder = tuple(visit(arg, environment + (binder.value,)) for arg in node.args[1:])
            return CanonicalExpression(
                node.op,
                (normalized_var, *remainder),
                node.value,
                node.sort,
                node.attributes,
            )
        return CanonicalExpression(
            node.op,
            tuple(visit(arg, environment) for arg in node.args),
            node.value,
            node.sort,
            node.attributes,
        )

    return visit(expression, ())


def expressions_equivalent(left: CanonicalExpression, right: CanonicalExpression) -> bool:
    return alpha_normalize(left).to_dict() == alpha_normalize(right).to_dict()


def states_identical(left: CanonicalState, right: CanonicalState) -> bool:
    return left.mathematical_hash == right.mathematical_hash
