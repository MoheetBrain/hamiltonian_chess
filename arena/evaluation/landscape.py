"""Paired statistics and representation-landscape summaries for fitness v1."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any


@dataclass(frozen=True, slots=True)
class PairedComparison:
    n: int
    accuracy_a: float
    accuracy_b: float
    delta: float
    ci95: tuple[float, float]
    n10: int
    n01: int
    mcnemar_exact_p: float
    clusters: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "accuracy_a": self.accuracy_a,
            "accuracy_b": self.accuracy_b,
            "delta": self.delta,
            "ci95": list(self.ci95),
            "n10": self.n10,
            "n01": self.n01,
            "mcnemar_exact_p": self.mcnemar_exact_p,
            "clusters": self.clusters,
        }


def mcnemar_exact(n10: int, n01: int) -> float:
    if n10 < 0 or n01 < 0:
        raise ValueError("discordant counts must be non-negative")
    n = n10 + n01
    if n == 0:
        return 1.0
    k = min(n10, n01)
    tail = sum(math.comb(n, index) for index in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def paired_comparison(
    outcomes_a: Sequence[bool],
    outcomes_b: Sequence[bool],
    groups: Sequence[str],
    *,
    seed: int = 20260905,
    resamples: int = 4000,
) -> PairedComparison:
    if not outcomes_a or len(outcomes_a) != len(outcomes_b) or len(outcomes_a) != len(groups):
        raise ValueError("paired outcomes and groups must have equal non-zero lengths")
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        grouped[group].append(index)
    group_ids = sorted(grouped)
    deltas = [
        float(left) - float(right) for left, right in zip(outcomes_a, outcomes_b, strict=True)
    ]
    observed = sum(deltas) / len(deltas)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        indices = [index for _ in group_ids for index in grouped[rng.choice(group_ids)]]
        draws.append(sum(deltas[index] for index in indices) / len(indices))
    draws.sort()
    lo = draws[max(0, int(0.025 * resamples))]
    hi = draws[min(resamples - 1, int(0.975 * resamples) - 1)]
    n10 = sum(left and not right for left, right in zip(outcomes_a, outcomes_b, strict=True))
    n01 = sum(right and not left for left, right in zip(outcomes_a, outcomes_b, strict=True))
    return PairedComparison(
        len(outcomes_a),
        sum(outcomes_a) / len(outcomes_a),
        sum(outcomes_b) / len(outcomes_b),
        observed,
        (lo, hi),
        n10,
        n01,
        mcnemar_exact(n10, n01),
        len(group_ids),
    )


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right, strict=True))
    denominator = math.sqrt(
        sum((x - mean_left) ** 2 for x in left) * sum((y - mean_right) ** 2 for y in right)
    )
    return numerator / denominator if denominator else None


def _ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        rank = (cursor + end - 1) / 2 + 1
        for _, index in ordered[cursor:end]:
            result[index] = rank
        cursor = end
    return result


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    return _pearson(_ranks(left), _ranks(right))


def landscape_summary(
    *,
    proposal_count: int,
    gate0_survivors: int,
    edges: Sequence[Mapping[str, Any]],
    rankings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compute the pre-registered descriptive landscape metrics.

    Each edge supplies parent/child accuracy, changed gene and token counts. Rankings supply
    scout and fresh promotion accuracies for the same candidates.
    """

    if proposal_count <= 0 or not 0 <= gate0_survivors <= proposal_count:
        raise ValueError("invalid proposal/survivor counts")
    deltas = [float(edge["child_accuracy"]) - float(edge["parent_accuracy"]) for edge in edges]
    beneficial = [
        delta > 0
        and float(edge.get("promotion_delta", 0.0)) >= -0.05
        and float(edge.get("token_ratio", 1.0)) <= 1.25
        for edge, delta in zip(edges, deltas, strict=True)
    ]
    effects: dict[str, list[float]] = defaultdict(list)
    for edge, delta in zip(edges, deltas, strict=True):
        key = f"{edge['changed_gene']}:{edge.get('old_value', '?')}->{edge.get('new_value', '?')}"
        effects[key].append(delta)
    effect_consistency = {}
    for key, values in sorted(effects.items()):
        positive = sum(value > 0 for value in values)
        negative = sum(value < 0 for value in values)
        effect_consistency[key] = {
            "n": len(values),
            "mean_delta": sum(values) / len(values),
            "directional_consistency": max(positive, negative) / len(values),
        }

    scout = [float(row["scout_accuracy"]) for row in rankings]
    promotion = [float(row["promotion_accuracy"]) for row in rankings]
    tokens = [float(row["mean_input_tokens"]) for row in rankings]
    l5 = next((row for row in rankings if row["candidate_id"] == "L5_COMPACT_SYMBOLIC"), None)
    return {
        "proposal_count": proposal_count,
        "gate0_survivors": gate0_survivors,
        "valid_neighbor_rate": gate0_survivors / proposal_count,
        "evaluated_edges": len(edges),
        "beneficial_mutation_rate": sum(beneficial) / len(beneficial) if beneficial else None,
        "neighbor_fitness_correlation": _pearson(
            [float(edge["parent_accuracy"]) for edge in edges],
            [float(edge["child_accuracy"]) for edge in edges],
        ),
        "gene_effect_consistency": effect_consistency,
        "ruggedness": {
            "mean_absolute_neighbor_delta": sum(map(abs, deltas)) / len(deltas) if deltas else None,
            "median_absolute_neighbor_delta": median(map(abs, deltas)) if deltas else None,
            "max_absolute_neighbor_delta": max(map(abs, deltas)) if deltas else None,
        },
        "rank_stability_spearman": spearman(scout, promotion),
        "static_token_vs_model_spearman": spearman(tokens, promotion),
        "l5_verdict": (
            {
                "scout_accuracy": l5["scout_accuracy"],
                "promotion_accuracy": l5["promotion_accuracy"],
                "mean_input_tokens": l5["mean_input_tokens"],
                "static_advantage_was_useful": bool(
                    float(l5["promotion_accuracy"])
                    >= max(float(row["promotion_accuracy"]) for row in rankings)
                ),
            }
            if l5
            else "NOT_EVALUATED"
        ),
    }


__all__ = [
    "PairedComparison",
    "landscape_summary",
    "mcnemar_exact",
    "paired_comparison",
    "spearman",
]
