"""Side-channel diagnostics; association triggers investigation, not causal claims."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Observation:
    task_id: str
    candidate_id: str
    task_family: str
    answer_class: str
    token_length: int
    success: bool
    input_text: str
    target_text: str


@dataclass(frozen=True, slots=True)
class SideChannelReport:
    observations: int
    literal_answer_leaks: tuple[str, ...]
    answer_success_mutual_information: float
    family_success_mutual_information: float
    length_success_correlation: float
    critical: bool


def _mutual_information(xs: tuple[str, ...], ys: tuple[str, ...]) -> float:
    if len(xs) != len(ys) or not xs:
        return 0.0
    total = len(xs)
    x_counts = Counter(xs)
    y_counts = Counter(ys)
    joint = Counter(zip(xs, ys, strict=True))
    result = 0.0
    for (x, y), count in joint.items():
        probability = count / total
        result += probability * math.log2(
            probability / ((x_counts[x] / total) * (y_counts[y] / total))
        )
    return result


def _point_biserial(lengths: tuple[int, ...], successes: tuple[bool, ...]) -> float:
    if not lengths or len(set(successes)) < 2:
        return 0.0
    by_status: dict[bool, list[int]] = defaultdict(list)
    for length, success in zip(lengths, successes, strict=True):
        by_status[success].append(length)
    mean_true = sum(by_status[True]) / len(by_status[True])
    mean_false = sum(by_status[False]) / len(by_status[False])
    mean = sum(lengths) / len(lengths)
    variance = sum((length - mean) ** 2 for length in lengths) / len(lengths)
    if variance == 0:
        return 0.0
    p = len(by_status[True]) / len(lengths)
    return (mean_true - mean_false) / math.sqrt(variance) * math.sqrt(p * (1 - p))


def audit(
    observations: tuple[Observation, ...], *, correlation_limit: float = 0.8
) -> SideChannelReport:
    leaks = tuple(
        observation.task_id
        for observation in observations
        if observation.target_text.strip()
        and observation.target_text.strip() in observation.input_text
    )
    successes = tuple(str(item.success) for item in observations)
    length_correlation = _point_biserial(
        tuple(item.token_length for item in observations),
        tuple(item.success for item in observations),
    )
    answer_mi = _mutual_information(tuple(item.answer_class for item in observations), successes)
    family_mi = _mutual_information(tuple(item.task_family for item in observations), successes)
    return SideChannelReport(
        observations=len(observations),
        literal_answer_leaks=leaks,
        answer_success_mutual_information=answer_mi,
        family_success_mutual_information=family_mi,
        length_success_correlation=length_correlation,
        critical=bool(leaks) or abs(length_correlation) >= correlation_limit,
    )
