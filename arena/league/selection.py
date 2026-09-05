"""Pareto-based candidate selection for league promotion."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from arena.fitness.pareto import Objective, ParetoPoint, crowding_distance, pareto_fronts
from arena.league.registry import LeagueRegistry


def rank_registry(
    registry: LeagueRegistry,
    objectives: Sequence[Objective],
    *,
    candidate_ids: Iterable[str] | None = None,
) -> tuple[tuple[str, ...], ...]:
    required = {objective.name for objective in objectives}
    if candidate_ids is None:
        ids = tuple(
            candidate_id
            for candidate_id, record in registry.candidates.items()
            if required <= record.objective_metrics.keys()
        )
    else:
        ids = tuple(candidate_ids)
        incomplete = tuple(
            candidate_id
            for candidate_id in ids
            if required - registry.candidates[candidate_id].objective_metrics.keys()
        )
        if incomplete:
            raise ValueError(f"candidates lack required Pareto objectives: {sorted(incomplete)}")
    points = tuple(
        ParetoPoint(candidate_id, registry.candidates[candidate_id].objective_metrics)
        for candidate_id in ids
    )
    fronts = pareto_fronts(points, objectives)
    for rank, front in enumerate(fronts):
        for point in front:
            registry.set_pareto_status(
                point.candidate_id, "FRONTIER" if rank == 0 else f"PARETO_RANK_{rank}"
            )
    return tuple(tuple(point.candidate_id for point in front) for front in fronts)


def select_frontier_diverse(
    points: Sequence[ParetoPoint], objectives: Sequence[Objective], count: int
) -> tuple[str, ...]:
    if count < 0:
        raise ValueError("count must be non-negative")
    selected: list[str] = []
    for front in pareto_fronts(points, objectives):
        distances = crowding_distance(front, objectives)
        ordered = sorted(
            front,
            key=lambda point: (-distances[point.candidate_id], point.candidate_id),
        )
        selected.extend(point.candidate_id for point in ordered[: count - len(selected)])
        if len(selected) >= count:
            break
    return tuple(selected)
