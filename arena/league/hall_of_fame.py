"""Frozen Hall-of-Fame suites and persistent baselines."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from arena.canonical.schema import GoldStatus, stable_hash
from arena.league.registry import DEFAULT_BASELINES, LeagueRegistry
from arena.tasks.schema import ArenaTask


@dataclass(frozen=True, slots=True)
class HallOfFameSuite:
    suite_id: str
    task_ids: tuple[str, ...]
    domain_counts: tuple[tuple[str, int], ...]
    content_hash: str

    @classmethod
    def from_tasks(
        cls,
        tasks: Iterable[ArenaTask],
        *,
        suite_id: str = "hall-of-fame-v0",
        gold_only: bool = True,
    ) -> HallOfFameSuite:
        rows = tuple(
            task for task in tasks if not gold_only or task.trajectory.quality == GoldStatus.GOLD
        )
        if not rows:
            raise ValueError("Hall-of-Fame suite cannot be empty")
        task_ids = tuple(sorted(task.task_id for task in rows))
        counts = tuple(sorted(Counter(task.dimensions.domain for task in rows).items()))
        return cls(
            suite_id,
            task_ids,
            counts,
            stable_hash(
                {
                    "suite_id": suite_id,
                    "task_hashes": sorted(task.content_hash for task in rows),
                }
            ),
        )


class HallOfFame:
    def __init__(self, suite: HallOfFameSuite, registry: LeagueRegistry | None = None) -> None:
        self.suite = suite
        self.registry = registry or LeagueRegistry()

    @property
    def baseline_ids(self) -> tuple[str, ...]:
        return tuple(candidate_id for candidate_id, _ in DEFAULT_BASELINES)

    def validate_baselines(self) -> bool:
        return all(
            candidate_id in self.registry.candidates
            and self.registry.candidates[candidate_id].baseline
            for candidate_id in self.baseline_ids
        )
