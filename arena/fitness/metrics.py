"""Typed fitness measurements with explicit sampling uncertainty."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import NormalDist, fmean, stdev


class Direction(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    lower: float
    upper: float
    confidence: float = 0.95
    method: str = "wilson"

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError("confidence interval lower bound exceeds upper bound")
        if not 0.0 < self.confidence < 1.0:
            raise ValueError("confidence must lie in (0, 1)")

    @property
    def width(self) -> float:
        return self.upper - self.lower


@dataclass(frozen=True, slots=True)
class MetricEstimate:
    name: str
    value: float
    interval: ConfidenceInterval
    sample_count: int
    direction: Direction = Direction.MAXIMIZE
    unit: str = "rate"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("metric name must not be empty")
        if self.sample_count < 0:
            raise ValueError("sample_count must be non-negative")
        if not math.isfinite(self.value):
            raise ValueError("metric value must be finite")

    @property
    def conservative_value(self) -> float:
        return self.interval.lower if self.direction == Direction.MAXIMIZE else self.interval.upper


def wilson_interval(successes: int, trials: int, *, confidence: float = 0.95) -> ConfidenceInterval:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must lie in [0, trials]")
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    probability = successes / trials
    denominator = 1.0 + z * z / trials
    center = (probability + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(probability * (1.0 - probability) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return ConfidenceInterval(
        max(0.0, center - radius),
        min(1.0, center + radius),
        confidence,
        "wilson",
    )


def proportion_metric(
    name: str,
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
    direction: Direction = Direction.MAXIMIZE,
) -> MetricEstimate:
    return MetricEstimate(
        name,
        successes / trials,
        wilson_interval(successes, trials, confidence=confidence),
        trials,
        direction,
    )


def mean_metric(
    name: str,
    observations: Sequence[float] | Iterable[float],
    *,
    confidence: float = 0.95,
    direction: Direction = Direction.MAXIMIZE,
    unit: str = "value",
) -> MetricEstimate:
    values = tuple(float(item) for item in observations)
    if not values:
        raise ValueError("at least one observation is required")
    if any(not math.isfinite(item) for item in values):
        raise ValueError("observations must be finite")
    mean = fmean(values)
    if len(values) == 1:
        interval = ConfidenceInterval(mean, mean, confidence, "singleton")
    else:
        z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
        radius = z * stdev(values) / math.sqrt(len(values))
        interval = ConfidenceInterval(mean - radius, mean + radius, confidence, "normal")
    return MetricEstimate(name, mean, interval, len(values), direction, unit)


@dataclass(frozen=True, slots=True)
class CoverageMetrics:
    canonical_world_coverage: float
    construct_coverage: float
    composition_closure: float
    cross_domain_composition: float
    binder_coverage: float
    definedness_coverage: float
    transition_coverage: float
    missing_constructs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in self.as_mapping().items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")

    def as_mapping(self) -> dict[str, float]:
        return {
            "canonical_world_coverage": self.canonical_world_coverage,
            "construct_coverage": self.construct_coverage,
            "composition_closure": self.composition_closure,
            "cross_domain_composition": self.cross_domain_composition,
            "binder_coverage": self.binder_coverage,
            "definedness_coverage": self.definedness_coverage,
            "transition_coverage": self.transition_coverage,
        }

    @property
    def minimum_coverage(self) -> float:
        return min(self.as_mapping().values())


@dataclass(frozen=True, slots=True)
class MachineMetrics:
    state_reconstruction: MetricEstimate
    next_action_accuracy: MetricEstimate
    top_k_legal_action_recall: MetricEstimate
    invalid_action_rate: MetricEstimate
    verified_next_state_rate: MetricEstimate
    sample_efficiency: MetricEstimate
    ood_generalization: MetricEstimate
    depth_generalization: MetricEstimate
    cross_domain_generalization: MetricEstimate
    search_efficiency: MetricEstimate

    def as_mapping(self) -> dict[str, MetricEstimate]:
        return {
            "state_reconstruction": self.state_reconstruction,
            "next_action_accuracy": self.next_action_accuracy,
            "top_k_legal_action_recall": self.top_k_legal_action_recall,
            "invalid_action_rate": self.invalid_action_rate,
            "verified_next_state_rate": self.verified_next_state_rate,
            "sample_efficiency": self.sample_efficiency,
            "ood_generalization": self.ood_generalization,
            "depth_generalization": self.depth_generalization,
            "cross_domain_generalization": self.cross_domain_generalization,
            "search_efficiency": self.search_efficiency,
        }


MACHINE_METRIC_NAMES = (
    "state_reconstruction",
    "next_action_accuracy",
    "top_k_legal_action_recall",
    "invalid_action_rate",
    "verified_next_state_rate",
    "sample_efficiency",
    "ood_generalization",
    "depth_generalization",
    "cross_domain_generalization",
    "search_efficiency",
)


def machine_metrics_from_trials(
    trials: Mapping[str, tuple[int, int]], *, confidence: float = 0.95
) -> MachineMetrics:
    """Build all required machine metrics from ``(successes, attempts)`` counts."""

    missing = set(MACHINE_METRIC_NAMES) - set(trials)
    if missing:
        raise ValueError(f"missing machine metrics: {sorted(missing)}")
    estimates = {
        name: proportion_metric(
            name,
            *trials[name],
            confidence=confidence,
            direction=(Direction.MINIMIZE if name == "invalid_action_rate" else Direction.MAXIMIZE),
        )
        for name in MACHINE_METRIC_NAMES
    }
    return MachineMetrics(**estimates)


@dataclass(frozen=True, slots=True)
class EfficiencyMetrics:
    characters: float
    tokens: float
    bits_estimate: float
    ast_depth: float
    parse_complexity: float
    compile_latency_ms: float
    model_latency_ms: float
    error_localization: float
    edit_robustness: float
    grammar_complexity: float
    training_token_requirement: float

    def __post_init__(self) -> None:
        for name, value in self.as_mapping().items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

    def as_mapping(self) -> dict[str, float]:
        return {
            "characters": self.characters,
            "tokens": self.tokens,
            "bits_estimate": self.bits_estimate,
            "ast_depth": self.ast_depth,
            "parse_complexity": self.parse_complexity,
            "compile_latency_ms": self.compile_latency_ms,
            "model_latency_ms": self.model_latency_ms,
            "error_localization": self.error_localization,
            "edit_robustness": self.edit_robustness,
            "grammar_complexity": self.grammar_complexity,
            "training_token_requirement": self.training_token_requirement,
        }


@dataclass(frozen=True, slots=True)
class MetricBundle:
    """Open-ended metric vector for persisted experiments and Pareto comparisons."""

    values: Mapping[str, float] = field(default_factory=dict)
    directions: Mapping[str, Direction] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(not math.isfinite(value) for value in self.values.values()):
            raise ValueError("all metric values must be finite")
        unknown = set(self.directions) - set(self.values)
        if unknown:
            raise ValueError(f"directions supplied for absent metrics: {sorted(unknown)}")
