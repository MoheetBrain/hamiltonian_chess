"""Paired evaluation statistics with uncertainty; no single noisy run ranking."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    estimate: float
    lower: float
    upper: float
    n: int


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> Interval:
    if total <= 0:
        raise ValueError("total must be positive")
    p = successes / total
    denominator = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), total)


def paired_bootstrap_difference(
    challenger: tuple[float, ...],
    control: tuple[float, ...],
    *,
    seed: int = 0,
    resamples: int = 4000,
    alpha: float = 0.05,
) -> Interval:
    if len(challenger) != len(control) or not challenger:
        raise ValueError("paired samples must have equal non-zero lengths")
    deltas = tuple(left - right for left, right in zip(challenger, control, strict=True))
    estimate = sum(deltas) / len(deltas)
    rng = random.Random(seed)
    bootstraps = sorted(
        sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(resamples)
    )
    lower_index = max(0, int((alpha / 2) * resamples))
    upper_index = min(resamples - 1, int((1 - alpha / 2) * resamples) - 1)
    return Interval(estimate, bootstraps[lower_index], bootstraps[upper_index], len(deltas))
