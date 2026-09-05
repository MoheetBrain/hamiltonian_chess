"""Task records layered on top of the immutable canonical mathematical world.

Task dimensions are evaluation metadata.  They deliberately do not participate in a
``CanonicalState.mathematical_hash`` and therefore cannot change mathematical truth.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Self

from arena.canonical.schema import CanonicalTrajectory, stable_hash


class TaskDomain(StrEnum):
    ARITHMETIC = "arithmetic"
    ALGEBRA = "algebra"
    LOGIC = "logic"
    BINDING = "binding"
    SETS = "sets"
    PROBABILITY = "probability"
    STATISTICS = "statistics"
    CALCULUS = "calculus"
    LINEAR_ALGEBRA = "linear_algebra"
    PHYSICAL_DIMENSIONS = "physical_dimensions"
    OPTIMIZATION = "optimization"
    PARTIAL_OPERATIONS = "partial_operations"
    REASONING_EVIDENCE = "reasoning_evidence"


@dataclass(frozen=True, slots=True)
class TaskDimensions:
    """Mechanism-level coordinates used by the Curriculum player.

    All integer dimensions are counts.  ``partiality`` is the number of partial
    operations whose definedness must be tracked, rather than a loosely defined flag.
    """

    domain: str
    reasoning_depth: int = 1
    dependency_depth: int = 0
    scope_depth: int = 0
    quantifier_alternation: int = 0
    number_of_assumptions: int = 0
    number_of_legal_actions: int = 0
    number_of_plausible_invalid_actions: int = 0
    partiality: int = 0
    composition_count: int = 1
    proof_length: int = 1
    cross_domain_interaction: int = 0

    def __post_init__(self) -> None:
        if not self.domain:
            raise ValueError("task domain must not be empty")
        for name, value in asdict(self).items():
            if name != "domain" and value < 0:
                raise ValueError(f"{name} must be non-negative")

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            domain=str(raw["domain"]),
            **{
                name: int(raw.get(name, field_info.default))
                for name, field_info in cls.__dataclass_fields__.items()
                if name != "domain"
            },
        )

    @property
    def mechanism_key(self) -> tuple[int, ...]:
        """A stable curriculum bin independent of domain naming."""

        return (
            self.reasoning_depth,
            self.dependency_depth,
            self.scope_depth,
            self.quantifier_alternation,
            self.partiality,
            self.composition_count,
            self.cross_domain_interaction,
        )


@dataclass(frozen=True, slots=True)
class ArenaTask:
    task_id: str
    trajectory: CanonicalTrajectory
    dimensions: TaskDimensions
    split: str = "train"
    tags: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if self.split not in {"train", "validation", "test", "hall_of_fame"}:
            raise ValueError(f"unsupported task split {self.split!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trajectory": self.trajectory.to_dict(),
            "dimensions": self.dimensions.to_dict(),
            "split": self.split,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @property
    def content_hash(self) -> str:
        raw = self.to_dict()
        raw.pop("task_id", None)
        return stable_hash(raw)


@dataclass(frozen=True, slots=True)
class WorldSummary:
    world_id: str
    count: int
    domain_counts: Mapping[str, int] = field(default_factory=dict)
    quality_counts: Mapping[str, int] = field(default_factory=dict)
