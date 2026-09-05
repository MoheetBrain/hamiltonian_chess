"""Deterministic multi-objective Pareto ranking."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from arena.fitness.metrics import Direction


@dataclass(frozen=True, slots=True)
class Objective:
    name: str
    direction: Direction = Direction.MAXIMIZE
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("objective name must not be empty")
        if self.tolerance < 0:
            raise ValueError("objective tolerance must be non-negative")


@dataclass(frozen=True, slots=True)
class ParetoPoint:
    candidate_id: str
    metrics: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must not be empty")
        if any(not math.isfinite(value) for value in self.metrics.values()):
            raise ValueError("Pareto metrics must be finite")


def dominates(left: ParetoPoint, right: ParetoPoint, objectives: Sequence[Objective]) -> bool:
    if not objectives:
        raise ValueError("at least one Pareto objective is required")
    strictly_better = False
    for objective in objectives:
        if objective.name not in left.metrics or objective.name not in right.metrics:
            raise KeyError(f"missing Pareto objective {objective.name!r}")
        left_value = left.metrics[objective.name]
        right_value = right.metrics[objective.name]
        if objective.direction == Direction.MAXIMIZE:
            if left_value < right_value - objective.tolerance:
                return False
            strictly_better |= left_value > right_value + objective.tolerance
        else:
            if left_value > right_value + objective.tolerance:
                return False
            strictly_better |= left_value < right_value - objective.tolerance
    return strictly_better


def pareto_fronts(
    points: Iterable[ParetoPoint], objectives: Sequence[Objective]
) -> tuple[tuple[ParetoPoint, ...], ...]:
    point_list = tuple(points)
    remaining = {point.candidate_id: point for point in point_list}
    if len(remaining) == 0:
        return ()
    if len(remaining) != len(point_list):
        raise ValueError("candidate ids must be unique")
    fronts: list[tuple[ParetoPoint, ...]] = []
    while remaining:
        values = tuple(remaining.values())
        front = tuple(
            sorted(
                (
                    point
                    for point in values
                    if not any(
                        other.candidate_id != point.candidate_id
                        and dominates(other, point, objectives)
                        for other in values
                    )
                ),
                key=lambda point: point.candidate_id,
            )
        )
        if not front:
            raise RuntimeError("failed to extract Pareto front")
        fronts.append(front)
        for point in front:
            del remaining[point.candidate_id]
    return tuple(fronts)


def pareto_ranks(points: Iterable[ParetoPoint], objectives: Sequence[Objective]) -> dict[str, int]:
    point_list = tuple(points)
    if len({point.candidate_id for point in point_list}) != len(point_list):
        raise ValueError("candidate ids must be unique")
    return {
        point.candidate_id: rank
        for rank, front in enumerate(pareto_fronts(point_list, objectives))
        for point in front
    }


def pareto_front(
    points: Iterable[ParetoPoint], objectives: Sequence[Objective]
) -> tuple[ParetoPoint, ...]:
    fronts = pareto_fronts(tuple(points), objectives)
    return fronts[0] if fronts else ()


def crowding_distance(
    front: Sequence[ParetoPoint], objectives: Sequence[Objective]
) -> dict[str, float]:
    """NSGA-II crowding distance for deterministic within-front selection."""

    distances = {point.candidate_id: 0.0 for point in front}
    if len(front) <= 2:
        return {candidate: math.inf for candidate in distances}
    for objective in objectives:
        ordered = sorted(
            front, key=lambda point: (point.metrics[objective.name], point.candidate_id)
        )
        distances[ordered[0].candidate_id] = math.inf
        distances[ordered[-1].candidate_id] = math.inf
        low = ordered[0].metrics[objective.name]
        high = ordered[-1].metrics[objective.name]
        if high == low:
            continue
        for index in range(1, len(ordered) - 1):
            candidate = ordered[index].candidate_id
            if not math.isinf(distances[candidate]):
                previous = ordered[index - 1].metrics[objective.name]
                following = ordered[index + 1].metrics[objective.name]
                distances[candidate] += (following - previous) / (high - low)
    return distances
