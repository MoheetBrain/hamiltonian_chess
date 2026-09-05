"""League manager facade with Hall-of-Fame and Pareto promotion."""

from __future__ import annotations

from collections.abc import Sequence

from arena.fitness.pareto import Objective
from arena.league.matches import LeagueMatch
from arena.league.registry import LeagueRegistry
from arena.league.selection import rank_registry


class LeagueManager:
    def __init__(self, registry: LeagueRegistry | None = None) -> None:
        self.registry = registry or LeagueRegistry()

    def record(self, match: LeagueMatch) -> None:
        self.registry.record_match(match)

    def rank(self, objectives: Sequence[Objective]) -> tuple[tuple[str, ...], ...]:
        return rank_registry(self.registry, objectives)
