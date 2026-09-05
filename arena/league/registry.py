"""Persistent multi-axis ratings for the candidate league.

This intentionally has no scalar Elo field.  Domain, mechanism, and objective axes are
stored independently so strengths and regressions cannot hide inside one average.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

from arena.fitness.metrics import ConfidenceInterval, mean_metric
from arena.league.matches import LeagueMatch, MatchObservation

REGISTRY_VERSION = "arena-league-v0.1.0"
DEFAULT_BASELINES: tuple[tuple[str, str], ...] = (
    ("L0_STRUCTURED_ENGLISH", "Structured English"),
    ("L1_CURRENT_HML", "Current HML"),
    ("L2_SEXPR", "S-expression"),
    ("L3_JSON_AST", "JSON AST"),
)


@dataclass(frozen=True, slots=True)
class AxisRating:
    value: float
    interval: ConfidenceInterval
    observations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "interval": asdict(self.interval),
            "observations": self.observations,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            float(raw["value"]),
            ConfidenceInterval(**raw["interval"]),
            int(raw["observations"]),
        )


@dataclass(slots=True)
class CandidateRecord:
    candidate_id: str
    display_name: str
    baseline: bool = False
    active: bool = True
    domain_ratings: dict[str, AxisRating] = field(default_factory=dict)
    mechanism_ratings: dict[str, AxisRating] = field(default_factory=dict)
    objective_metrics: dict[str, float] = field(default_factory=dict)
    pareto_status: str = "UNEVALUATED"
    parent_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "display_name": self.display_name,
            "baseline": self.baseline,
            "active": self.active,
            "domain_ratings": {
                key: value.to_dict() for key, value in sorted(self.domain_ratings.items())
            },
            "mechanism_ratings": {
                key: value.to_dict() for key, value in sorted(self.mechanism_ratings.items())
            },
            "objective_metrics": dict(sorted(self.objective_metrics.items())),
            "pareto_status": self.pareto_status,
            "parent_ids": list(self.parent_ids),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            candidate_id=str(raw["candidate_id"]),
            display_name=str(raw.get("display_name", raw["candidate_id"])),
            baseline=bool(raw.get("baseline", False)),
            active=bool(raw.get("active", True)),
            domain_ratings={
                str(key): AxisRating.from_dict(value)
                for key, value in raw.get("domain_ratings", {}).items()
            },
            mechanism_ratings={
                str(key): AxisRating.from_dict(value)
                for key, value in raw.get("mechanism_ratings", {}).items()
            },
            objective_metrics={
                str(key): float(value) for key, value in raw.get("objective_metrics", {}).items()
            },
            pareto_status=str(raw.get("pareto_status", "UNEVALUATED")),
            parent_ids=tuple(str(item) for item in raw.get("parent_ids", ())),
        )


def _rating(values: list[float], name: str) -> AxisRating:
    estimate = mean_metric(name, values)
    interval = ConfidenceInterval(
        max(0.0, estimate.interval.lower),
        min(1.0, estimate.interval.upper),
        estimate.interval.confidence,
        estimate.interval.method,
    )
    return AxisRating(estimate.value, interval, len(values))


class LeagueRegistry:
    def __init__(self, *, seed_baselines: bool = True) -> None:
        self.candidates: dict[str, CandidateRecord] = {}
        self.observations: list[MatchObservation] = []
        self.matches: list[str] = []
        if seed_baselines:
            for candidate_id, name in DEFAULT_BASELINES:
                self.register(candidate_id, name, baseline=True)

    def register(
        self,
        candidate_id: str,
        display_name: str | None = None,
        *,
        baseline: bool = False,
        parent_ids: Iterable[str] = (),
    ) -> CandidateRecord:
        if not candidate_id:
            raise ValueError("candidate_id must not be empty")
        parents = tuple(parent_ids)
        if candidate_id in parents:
            raise ValueError("candidate cannot be its own parent")
        existing = self.candidates.get(candidate_id)
        if existing is not None:
            if baseline:
                existing.baseline = True
            return existing
        record = CandidateRecord(
            candidate_id,
            display_name or candidate_id,
            baseline=baseline,
            parent_ids=parents,
        )
        self.candidates[candidate_id] = record
        return record

    def record_observation(self, observation: MatchObservation) -> None:
        if observation.candidate_id not in self.candidates:
            self.register(observation.candidate_id)
        self.observations.append(observation)
        self._recompute(observation.candidate_id)

    def record_match(self, match: LeagueMatch) -> None:
        if match.match_id in self.matches:
            raise ValueError(f"duplicate match id {match.match_id!r}")
        self.matches.append(match.match_id)
        affected: set[str] = set()
        for observation in match.observations:
            if observation.candidate_id not in self.candidates:
                self.register(observation.candidate_id)
            self.observations.append(observation)
            affected.add(observation.candidate_id)
        for candidate_id in sorted(affected):
            self._recompute(candidate_id)

    def _recompute(self, candidate_id: str) -> None:
        domain_values: defaultdict[str, list[float]] = defaultdict(list)
        mechanism_values: defaultdict[str, list[float]] = defaultdict(list)
        for observation in self.observations:
            if observation.candidate_id != candidate_id or not observation.verified:
                continue
            domain_values[observation.domain].append(observation.score)
            for mechanism in observation.mechanisms:
                mechanism_values[mechanism].append(observation.score)
        record = self.candidates[candidate_id]
        record.domain_ratings = {
            domain: _rating(values, f"domain:{domain}")
            for domain, values in sorted(domain_values.items())
        }
        record.mechanism_ratings = {
            mechanism: _rating(values, f"mechanism:{mechanism}")
            for mechanism, values in sorted(mechanism_values.items())
        }

    def set_objectives(self, candidate_id: str, metrics: Mapping[str, float]) -> None:
        if candidate_id not in self.candidates:
            self.register(candidate_id)
        self.candidates[candidate_id].objective_metrics = {
            str(name): float(value) for name, value in sorted(metrics.items())
        }

    def set_pareto_status(self, candidate_id: str, status: str) -> None:
        if candidate_id not in self.candidates:
            raise KeyError(candidate_id)
        self.candidates[candidate_id].pareto_status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": REGISTRY_VERSION,
            "candidates": [self.candidates[key].to_dict() for key in sorted(self.candidates)],
            "observations": [asdict(item) for item in self.observations],
            "matches": list(self.matches),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        if raw.get("version") != REGISTRY_VERSION:
            raise ValueError(f"unsupported registry version {raw.get('version')!r}")
        registry = cls(seed_baselines=False)
        registry.candidates = {
            record.candidate_id: record
            for record in (CandidateRecord.from_dict(item) for item in raw.get("candidates", ()))
        }
        registry.observations = [
            MatchObservation(
                candidate_id=str(item["candidate_id"]),
                task_id=str(item["task_id"]),
                domain=str(item["domain"]),
                mechanisms=tuple(item.get("mechanisms", ())),
                score=float(item["score"]),
                opponent_id=item.get("opponent_id"),
                verified=bool(item.get("verified", True)),
            )
            for item in raw.get("observations", ())
        ]
        registry.matches = [str(item) for item in raw.get("matches", ())]
        # Recompute ratings from primary observations, rather than trusting cached values.
        for candidate_id in registry.candidates:
            registry._recompute(candidate_id)
        return registry

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Self:
        with Path(path).open(encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))


MultiAxisRegistry = LeagueRegistry
