"""Multi-axis league observations."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchObservation:
    candidate_id: str
    task_id: str
    domain: str
    mechanisms: tuple[str, ...]
    score: float
    opponent_id: str | None = None
    verified: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.task_id or not self.domain:
            raise ValueError("candidate, task, and domain identifiers are required")
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("match score must lie in [0, 1]")
        if not self.mechanisms:
            raise ValueError("at least one mechanism label is required")


@dataclass(frozen=True, slots=True)
class LeagueMatch:
    match_id: str
    observations: tuple[MatchObservation, ...]
    suite_id: str = "hall-of-fame-v0"

    def __post_init__(self) -> None:
        if not self.match_id:
            raise ValueError("match_id must not be empty")
        if not self.observations:
            raise ValueError("a league match must contain observations")
