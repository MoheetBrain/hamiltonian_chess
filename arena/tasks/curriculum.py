"""Information-seeking curriculum acquisition.

Difficulty is not the target.  The selector favors tasks which distinguish candidates,
reduce uncertain rankings near the frontier, and cover under-sampled mechanisms.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean, pvariance

from arena.canonical.schema import GoldStatus
from arena.tasks.schema import ArenaTask


def _unit(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("performance probabilities must be finite")
    if not 0.0 <= value <= 1.0:
        raise ValueError("performance probabilities must be in [0, 1]")
    return float(value)


def binary_entropy(probability: float) -> float:
    """Binary entropy in bits, used only as an empirical uncertainty proxy."""

    probability = _unit(probability)
    if probability in {0.0, 1.0}:
        return 0.0
    return -probability * math.log2(probability) - (1 - probability) * math.log2(1 - probability)


@dataclass(frozen=True, slots=True)
class TaskPerformance:
    candidate_id: str
    task_id: str
    successes: int
    attempts: int

    def __post_init__(self) -> None:
        if self.attempts <= 0:
            raise ValueError("attempts must be positive")
        if not 0 <= self.successes <= self.attempts:
            raise ValueError("successes must lie in [0, attempts]")

    @property
    def probability(self) -> float:
        # Jeffreys smoothing avoids pretending a one-shot result has zero uncertainty.
        return (self.successes + 0.5) / (self.attempts + 1.0)


@dataclass(frozen=True, slots=True)
class AcquisitionWeights:
    disagreement: float = 0.65
    expected_ranking_information: float = 0.15
    frontier_uncertainty: float = 0.10
    dimension_novelty: float = 0.10

    def __post_init__(self) -> None:
        values = (
            self.disagreement,
            self.expected_ranking_information,
            self.frontier_uncertainty,
            self.dimension_novelty,
        )
        if any(value < 0 for value in values) or sum(values) <= 0:
            raise ValueError("acquisition weights must be non-negative with positive sum")


DEFAULT_ACQUISITION_WEIGHTS = AcquisitionWeights()


@dataclass(frozen=True, slots=True)
class AcquisitionScore:
    task_id: str
    total: float
    disagreement: float
    expected_ranking_information: float
    frontier_uncertainty: float
    dimension_novelty: float
    observed_candidates: int


def representation_performance_variance(probabilities: Sequence[float]) -> float:
    """Population variance normalized to [0, 1]."""

    values = tuple(_unit(value) for value in probabilities)
    return min(1.0, pvariance(values) / 0.25) if len(values) >= 2 else 0.0


def expected_ranking_information_gain(probabilities: Sequence[float]) -> float:
    """A bounded proxy for information gained about pairwise candidate rankings.

    It is largest when plausible candidates are close but the task is not unanimously
    trivial or impossible.  This is intentionally labelled a proxy, not exact mutual
    information.
    """

    values = tuple(_unit(value) for value in probabilities)
    if len(values) < 2:
        return 0.0
    task_resolvability = binary_entropy(fmean(values))
    pairwise_closeness = fmean(
        1.0 - abs(left - right)
        for index, left in enumerate(values)
        for right in values[index + 1 :]
    )
    return task_resolvability * pairwise_closeness


def acquisition_score(
    task: ArenaTask,
    probabilities: Sequence[float],
    *,
    dimension_frequency: int = 0,
    frontier_probabilities: Sequence[float] = (),
    weights: AcquisitionWeights = DEFAULT_ACQUISITION_WEIGHTS,
) -> AcquisitionScore:
    values = tuple(_unit(value) for value in probabilities)
    frontier = tuple(_unit(value) for value in frontier_probabilities) or values
    disagreement = representation_performance_variance(values)
    ranking_information = expected_ranking_information_gain(frontier)
    frontier_uncertainty = fmean(binary_entropy(value) for value in frontier) if frontier else 0.0
    novelty = 1.0 / (1.0 + max(0, dimension_frequency))
    weight_sum = (
        weights.disagreement
        + weights.expected_ranking_information
        + weights.frontier_uncertainty
        + weights.dimension_novelty
    )
    total = (
        weights.disagreement * disagreement
        + weights.expected_ranking_information * ranking_information
        + weights.frontier_uncertainty * frontier_uncertainty
        + weights.dimension_novelty * novelty
    ) / weight_sum

    # Rejected canonical records remain useful negative probes but must not outrank
    # verified worlds solely through uncertainty.  They never enter hard gates.
    quality_factor = {
        GoldStatus.GOLD: 1.0,
        GoldStatus.SILVER: 0.85,
        GoldStatus.REJECT: 0.50,
    }[task.trajectory.quality]
    return AcquisitionScore(
        task.task_id,
        total * quality_factor,
        disagreement,
        ranking_information,
        frontier_uncertainty,
        novelty,
        len(values),
    )


class InformationCurriculum:
    """Deterministic acquisition over task/candidate performance predictions."""

    def __init__(self, weights: AcquisitionWeights = DEFAULT_ACQUISITION_WEIGHTS) -> None:
        self.weights = weights

    def rank(
        self,
        tasks: Iterable[ArenaTask],
        predictions: Mapping[str, Mapping[str, float]],
        *,
        frontier_candidates: Iterable[str] = (),
        dimension_counts: Mapping[tuple[str, tuple[int, ...]], int] | None = None,
    ) -> tuple[AcquisitionScore, ...]:
        task_list = tuple(tasks)
        frontier_ids = frozenset(frontier_candidates)
        if dimension_counts is None:
            counts: Counter[tuple[str, tuple[int, ...]]] = Counter()
        else:
            counts = Counter(dimension_counts)
        scored: list[AcquisitionScore] = []
        for task in task_list:
            task_predictions = predictions.get(task.task_id, {})
            values = tuple(task_predictions[candidate] for candidate in sorted(task_predictions))
            frontier = tuple(
                task_predictions[candidate]
                for candidate in sorted(frontier_ids & task_predictions.keys())
            )
            key = (task.dimensions.domain, task.dimensions.mechanism_key)
            scored.append(
                acquisition_score(
                    task,
                    values,
                    dimension_frequency=counts[key],
                    frontier_probabilities=frontier,
                    weights=self.weights,
                )
            )
        return tuple(sorted(scored, key=lambda item: (-item.total, item.task_id)))

    def select(
        self,
        tasks: Iterable[ArenaTask],
        predictions: Mapping[str, Mapping[str, float]],
        count: int,
        *,
        frontier_candidates: Iterable[str] = (),
        dimension_counts: Mapping[tuple[str, tuple[int, ...]], int] | None = None,
    ) -> tuple[AcquisitionScore, ...]:
        if count < 0:
            raise ValueError("selection count must be non-negative")
        return self.rank(
            tasks,
            predictions,
            frontier_candidates=frontier_candidates,
            dimension_counts=dimension_counts,
        )[:count]


def performance_table(
    observations: Iterable[TaskPerformance],
) -> dict[str, dict[str, float]]:
    """Aggregate repeated observations without depending on insertion order."""

    grouped: dict[tuple[str, str], list[TaskPerformance]] = {}
    for item in observations:
        grouped.setdefault((item.task_id, item.candidate_id), []).append(item)
    table: dict[str, dict[str, float]] = {}
    for (task_id, candidate_id), rows in sorted(grouped.items()):
        successes = sum(row.successes for row in rows)
        attempts = sum(row.attempts for row in rows)
        table.setdefault(task_id, {})[candidate_id] = (successes + 0.5) / (attempts + 1.0)
    return table
