"""Declared finite universes with exact enumeration denominators."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import product

from arena.canonical.schema import CanonicalExpression


@dataclass(frozen=True, slots=True)
class ExhaustiveResult:
    universe_id: str
    declared_parameters: tuple[tuple[str, str], ...]
    exact_denominator: int
    enumerated_cases: int
    passed_cases: int
    failed_case_ids: tuple[str, ...]
    complete: bool


def enumerate_scalar_expressions(
    *,
    max_depth: int = 2,
    atom_values: tuple[int, ...] = (-1, 0, 1),
    binary_operators: tuple[str, ...] = ("add", "sub", "mul"),
) -> tuple[CanonicalExpression, ...]:
    """Enumerate every full/short tree in a small, explicitly declared grammar."""

    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    expressions = {
        CanonicalExpression("integer", value=value, sort="Int").content_hash: CanonicalExpression(
            "integer", value=value, sort="Int"
        )
        for value in atom_values
    }
    frontier = tuple(expressions.values())
    for _ in range(max_depth):
        prior = tuple(expressions.values())
        generated = tuple(
            CanonicalExpression(operator, (left, right), sort="Int")
            for operator, left, right in product(binary_operators, prior, prior)
        )
        for expression in generated:
            expressions.setdefault(expression.content_hash, expression)
        if len(expressions) == len(frontier):
            break
        frontier = tuple(expressions.values())
    return tuple(expressions[key] for key in sorted(expressions))


def enumerate_directed_graphs(node_count: int) -> tuple[dict[str, tuple[str, ...]], ...]:
    """Enumerate all loop-free directed graphs on labelled nodes."""

    if not 0 <= node_count <= 4:
        raise ValueError("v0 graph universe supports 0..4 nodes")
    nodes = tuple(f"e:{index}" for index in range(node_count))
    edges = tuple((source, target) for source in nodes for target in nodes if source != target)
    graphs: list[dict[str, tuple[str, ...]]] = []
    for mask in range(1 << len(edges)):
        graph: dict[str, list[str]] = {node: [] for node in nodes}
        for index, (source, target) in enumerate(edges):
            if mask & (1 << index):
                graph[source].append(target)
        graphs.append({node: tuple(targets) for node, targets in graph.items()})
    return tuple(graphs)


def run_universe[T](
    universe_id: str,
    cases: Iterable[T],
    case_id: Callable[[T], str],
    predicate: Callable[[T], bool],
    *,
    parameters: dict[str, str],
) -> ExhaustiveResult:
    materialized = tuple(cases)
    failed = tuple(case_id(case) for case in materialized if not predicate(case))
    return ExhaustiveResult(
        universe_id=universe_id,
        declared_parameters=tuple(sorted(parameters.items())),
        exact_denominator=len(materialized),
        enumerated_cases=len(materialized),
        passed_cases=len(materialized) - len(failed),
        failed_case_ids=failed,
        complete=True,
    )
