"""The first content-bearing Arena genome.

This schema is deliberately separate from :class:`LanguageGenome`.  A language genome
changes the reversible surface used to serialize a canonical state.  A content genome
chooses which truth-derived relations are made local or explicit in the model view.
Neither schema can modify canonical truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any, Self

from arena.canonical.schema import stable_hash
from arena.genome.schema import LanguageGenome

MODEL_VIEW_GENOME_VERSION = "arena-model-view-genome-v1.0.0"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class SearchTrack(StrEnum):
    EQUAL_INFORMATION = "TRACK_E_EQUAL_INFORMATION"
    CONTENT_PROJECTION = "TRACK_C_CONTENT_PROJECTION"


class DependencyProjection(StrEnum):
    IMPLICIT = "IMPLICIT"
    EXPLICIT_EDGE = "EXPLICIT_EDGE"
    EXPLICIT_LOCAL_EDGE = "EXPLICIT_LOCAL_EDGE"


class ActionGoalProjection(StrEnum):
    IMPLICIT = "IMPLICIT"
    TARGET_ID = "TARGET_ID"
    TARGET_BLOCK = "TARGET_BLOCK"


class PremiseProjection(StrEnum):
    GLOBAL_LIST = "GLOBAL_LIST"
    ACTION_LOCAL = "ACTION_LOCAL"
    EXPLICIT_EDGE = "EXPLICIT_EDGE"


class ObligationProjection(StrEnum):
    GLOBAL = "GLOBAL"
    OWNER_LOCAL = "OWNER_LOCAL"
    ACTION_LOCAL = "ACTION_LOCAL"


class StateDeltaProjection(StrEnum):
    FULL_BEFORE_AFTER = "FULL_BEFORE_AFTER"
    DELTA_PLUS_CONTEXT = "DELTA_PLUS_CONTEXT"
    EXPLICIT_CHANGED_RELATIONS = "EXPLICIT_CHANGED_RELATIONS"


class EvidenceProjection(StrEnum):
    STATUS_ONLY = "STATUS_ONLY"
    PROOF_EDGE = "PROOF_EDGE"
    LOCAL_PROVENANCE = "LOCAL_PROVENANCE"


CONTENT_ENUMS = {
    "dependency_projection": DependencyProjection,
    "action_goal_projection": ActionGoalProjection,
    "premise_projection": PremiseProjection,
    "obligation_projection": ObligationProjection,
    "state_delta_projection": StateDeltaProjection,
    "evidence_projection": EvidenceProjection,
}


@dataclass(frozen=True, slots=True)
class ContentGenome:
    dependency_projection: DependencyProjection = DependencyProjection.IMPLICIT
    action_goal_projection: ActionGoalProjection = ActionGoalProjection.IMPLICIT
    premise_projection: PremiseProjection = PremiseProjection.GLOBAL_LIST
    obligation_projection: ObligationProjection = ObligationProjection.GLOBAL
    state_delta_projection: StateDeltaProjection = StateDeltaProjection.FULL_BEFORE_AFTER
    evidence_projection: EvidenceProjection = EvidenceProjection.STATUS_ONLY

    def to_dict(self) -> dict[str, str]:
        return {item.name: getattr(self, item.name).value for item in fields(self)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        if set(raw) != set(CONTENT_ENUMS):
            raise ValueError("content genome must contain exactly the six v1 content genes")
        return cls(
            dependency_projection=DependencyProjection(raw["dependency_projection"]),
            action_goal_projection=ActionGoalProjection(raw["action_goal_projection"]),
            premise_projection=PremiseProjection(raw["premise_projection"]),
            obligation_projection=ObligationProjection(raw["obligation_projection"]),
            state_delta_projection=StateDeltaProjection(raw["state_delta_projection"]),
            evidence_projection=EvidenceProjection(raw["evidence_projection"]),
        )

    @property
    def genome_hash(self) -> str:
        return stable_hash({"version": MODEL_VIEW_GENOME_VERSION, "content": self.to_dict()})

    def with_gene(self, name: str, value: str) -> Self:
        if name not in CONTENT_ENUMS:
            raise ValueError(f"unknown content gene: {name}")
        raw = self.to_dict()
        raw[name] = value
        return type(self).from_dict(raw)


@dataclass(frozen=True, slots=True)
class ModelViewGenome:
    candidate_id: str
    parent_ids: tuple[str, ...]
    track: SearchTrack
    surface: LanguageGenome
    content: ContentGenome
    schema_version: str = MODEL_VIEW_GENOME_VERSION

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.candidate_id):
            raise ValueError(f"invalid model-view candidate id: {self.candidate_id!r}")
        if self.candidate_id in self.parent_ids or len(set(self.parent_ids)) != len(
            self.parent_ids
        ):
            raise ValueError("model-view ancestry must be unique and non-reflexive")
        if self.schema_version != MODEL_VIEW_GENOME_VERSION:
            raise ValueError(f"unsupported model-view genome: {self.schema_version}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "parent_ids": list(self.parent_ids),
            "track": self.track.value,
            "surface": self.surface.to_dict(),
            "content": self.content.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        required = {
            "schema_version",
            "candidate_id",
            "parent_ids",
            "track",
            "surface",
            "content",
        }
        if set(raw) != required:
            raise ValueError("model-view genome has missing or unknown fields")
        return cls(
            schema_version=str(raw["schema_version"]),
            candidate_id=str(raw["candidate_id"]),
            parent_ids=tuple(str(item) for item in raw["parent_ids"]),
            track=SearchTrack(raw["track"]),
            surface=LanguageGenome.from_dict(raw["surface"]),
            content=ContentGenome.from_dict(raw["content"]),
        )

    @property
    def genome_hash(self) -> str:
        return stable_hash(self.to_dict())


CONTENT_GENE_METADATA: dict[str, dict[str, object]] = {
    "dependency_projection": {
        "values": [item.value for item in DependencyProjection],
        "invariant": "every emitted dependency edge exists in canonical evidence",
        "slices": ["dependency_chain", "large_context"],
        "cost_tier": 1,
        "instrumentation": "edge recall, locality and semantic-collapse ablation",
    },
    "action_goal_projection": {
        "values": [item.value for item in ActionGoalProjection],
        "invariant": "targets are copied or resolved only from displayed action options",
        "slices": ["action_goal_assignment", "repeated_identity"],
        "cost_tier": 1,
        "instrumentation": "target assignment and option-swap invariance",
    },
    "premise_projection": {
        "values": [item.value for item in PremiseProjection],
        "invariant": "premises are canonical assumptions or option preconditions",
        "slices": ["premise_attribution", "partial_operation"],
        "cost_tier": 1,
        "instrumentation": "premise attribution and destroyed-premise collapse",
    },
    "obligation_projection": {
        "values": [item.value for item in ObligationProjection],
        "invariant": "obligations and owners are copied from canonical source fields",
        "slices": ["obligation_ownership", "multiple_goals"],
        "cost_tier": 1,
        "instrumentation": "owner selection and owner-swap counterfactual",
    },
    "state_delta_projection": {
        "values": [item.value for item in StateDeltaProjection],
        "invariant": "delta is a deterministic comparison of canonical before and after",
        "slices": ["state_delta", "large_context"],
        "cost_tier": 2,
        "instrumentation": "changed-field recovery and before/after swap",
    },
    "evidence_projection": {
        "values": [item.value for item in EvidenceProjection],
        "invariant": "status, provenance and proof edges come from canonical evidence",
        "slices": ["dependency_chain", "evidence_provenance"],
        "cost_tier": 1,
        "instrumentation": "licensed-evidence selection and edge ablation",
    },
}


def content_gene_metadata() -> dict[str, dict[str, object]]:
    """Return stable metadata; callers may serialize it directly."""

    return {name: dict(value) for name, value in CONTENT_GENE_METADATA.items()}
