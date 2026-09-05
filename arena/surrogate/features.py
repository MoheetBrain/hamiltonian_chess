"""Deterministic, dependency-free feature extraction."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


def _categorical_number(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)


def extract_features(candidate: Any) -> dict[str, float]:
    """Flatten a genome-like record without importing or privileging a genome family.

    Numeric genes remain numeric.  Categorical genes receive a stable SHA-256-derived
    coordinate (never Python's process-randomized ``hash``), and collections expose both
    length and member features.
    """

    if hasattr(candidate, "to_dict"):
        candidate = candidate.to_dict()
    elif is_dataclass(candidate):
        candidate = asdict(candidate)  # type: ignore[arg-type]
    if not isinstance(candidate, Mapping):
        raise TypeError("candidate features require a mapping or dataclass-like record")

    result: dict[str, float] = {}

    def visit(path: str, value: Any) -> None:
        if value is None:
            result[f"{path}.__missing__"] = 1.0
        elif isinstance(value, bool):
            result[path] = float(value)
        elif isinstance(value, (int, float)):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"non-finite feature at {path}")
            result[path] = numeric
        elif isinstance(value, str):
            result[path] = _categorical_number(value)
        elif isinstance(value, Mapping):
            result[f"{path}.__size__"] = float(len(value))
            for key in sorted(value, key=str):
                visit(f"{path}.{key}", value[key])
        elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            result[f"{path}.__length__"] = float(len(value))
            for index, item in enumerate(value):
                visit(f"{path}.{index}", item)
        else:
            result[path] = _categorical_number(str(value))

    for key in sorted(candidate, key=str):
        visit(str(key), candidate[key])
    return dict(sorted(result.items()))


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    names: tuple[str, ...]

    @classmethod
    def fit(cls, rows: Sequence[Mapping[str, float]]) -> FeatureSchema:
        return cls(tuple(sorted({name for row in rows for name in row})))

    def transform(self, row: Mapping[str, float]) -> tuple[float, ...]:
        return tuple(float(row.get(name, 0.0)) for name in self.names)


@dataclass(frozen=True, slots=True)
class FeatureVector:
    candidate_id: str
    names: tuple[str, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.names) != len(self.values):
            raise ValueError("feature names and values must have equal length")
