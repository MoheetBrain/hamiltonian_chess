"""Versionable in-memory surrogate datasets."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from arena.canonical.schema import stable_hash
from arena.surrogate.features import FeatureSchema


@dataclass(frozen=True, slots=True)
class SurrogateExample:
    candidate_id: str
    features: Mapping[str, float]
    target: float
    weight: float = 1.0
    group: str = "default"

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must not be empty")
        if not math.isfinite(self.target) or not 0.0 <= self.target <= 1.0:
            raise ValueError("calibrated-surrogate targets must lie in [0, 1]")
        if not math.isfinite(self.weight) or self.weight <= 0:
            raise ValueError("example weight must be positive and finite")
        if any(not math.isfinite(float(value)) for value in self.features.values()):
            raise ValueError("features must be finite")


@dataclass(frozen=True, slots=True)
class SurrogateDataset:
    examples: tuple[SurrogateExample, ...]
    schema: FeatureSchema

    @classmethod
    def from_examples(cls, examples: Iterable[SurrogateExample]) -> SurrogateDataset:
        rows = tuple(sorted(examples, key=lambda item: (item.candidate_id, item.group)))
        if not rows:
            raise ValueError("surrogate dataset cannot be empty")
        schema = FeatureSchema.fit([item.features for item in rows])
        return cls(rows, schema)

    @property
    def content_hash(self) -> str:
        return stable_hash(
            {
                "features": list(self.schema.names),
                "examples": [
                    {
                        "candidate_id": item.candidate_id,
                        "features": dict(sorted(item.features.items())),
                        "target": item.target,
                        "weight": item.weight,
                        "group": item.group,
                    }
                    for item in self.examples
                ],
            }
        )

    def matrix(self) -> tuple[list[list[float]], list[float], list[float]]:
        features = [list(self.schema.transform(item.features)) for item in self.examples]
        targets = [item.target for item in self.examples]
        weights = [item.weight for item in self.examples]
        return features, targets, weights

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": list(self.schema.names),
            "examples": [
                {
                    "candidate_id": item.candidate_id,
                    "features": dict(item.features),
                    "target": item.target,
                    "weight": item.weight,
                    "group": item.group,
                }
                for item in self.examples
            ],
        }
