"""Search-efficiency measurements."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from arena.fitness.metrics import MetricEstimate, mean_metric


@dataclass(frozen=True, slots=True)
class SearchRun:
    expanded_nodes: int
    verifier_calls: int
    solved: bool

    def __post_init__(self) -> None:
        if self.expanded_nodes < 0 or self.verifier_calls < 0:
            raise ValueError("search counts must be non-negative")


def search_efficiency(runs: Iterable[SearchRun]) -> MetricEstimate:
    rows = tuple(runs)
    if not rows:
        raise ValueError("at least one search run is required")
    # Higher is better; unsolved runs receive zero, and solved runs reward fewer calls.
    values = [
        1.0 / (1.0 + run.expanded_nodes + run.verifier_calls) if run.solved else 0.0 for run in rows
    ]
    return mean_metric("search_efficiency", values)
