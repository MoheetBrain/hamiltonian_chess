"""Versioned canonical mathematical records.

Candidate languages may serialize these values; they never define their truth.  Stable
mathematical hashes intentionally exclude execution metadata and display identifiers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any, Self

SCHEMA_VERSION = "arena-canonical-v0.1.0"


class GoldStatus(StrEnum):
    GOLD = "GOLD"
    SILVER = "SILVER"
    REJECT = "REJECT"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"


def canonical_json(value: Any) -> str:
    """Return the only JSON spelling used for identities and stored artifacts."""

    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CanonicalExpression:
    """A small typed term graph node represented structurally, never by source syntax."""

    op: str
    args: tuple[CanonicalExpression, ...] = ()
    value: str | int | float | bool | None = None
    sort: str = "Unknown"
    attributes: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"op": self.op, "sort": self.sort}
        if self.args:
            result["args"] = [item.to_dict() for item in self.args]
        if self.value is not None:
            result["value"] = self.value
        if self.attributes:
            result["attributes"] = {key: value for key, value in self.attributes}
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        attrs = raw.get("attributes", {})
        return cls(
            op=str(raw["op"]),
            args=tuple(cls.from_dict(item) for item in raw.get("args", ())),
            value=raw.get("value"),
            sort=str(raw.get("sort", "Unknown")),
            attributes=tuple(sorted((str(k), str(v)) for k, v in attrs.items())),
        )

    @property
    def content_hash(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class MathObject:
    object_id: str
    type_name: str
    value: CanonicalExpression | None = None
    shape: tuple[int | str, ...] = ()
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "type_name": self.type_name,
            "value": self.value.to_dict() if self.value else None,
            "shape": list(self.shape),
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            object_id=str(raw["object_id"]),
            type_name=str(raw["type_name"]),
            value=CanonicalExpression.from_dict(raw["value"]) if raw.get("value") else None,
            shape=tuple(raw.get("shape", ())),
            unit=raw.get("unit"),
        )


@dataclass(frozen=True, slots=True)
class Binding:
    binder_id: str
    variable: str
    type_name: str
    scope_id: str
    binder_kind: str = "free"


@dataclass(frozen=True, slots=True)
class Obligation:
    obligation_id: str
    proposition: CanonicalExpression
    status: str = "OPEN"
    source: str = "canonical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "proposition": self.proposition.to_dict(),
            "status": self.status,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            obligation_id=str(raw["obligation_id"]),
            proposition=CanonicalExpression.from_dict(raw["proposition"]),
            status=str(raw.get("status", "OPEN")),
            source=str(raw.get("source", "canonical")),
        )


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    evidence_id: str
    status: str
    dependencies: tuple[str, ...] = ()
    authority: str = "native"
    certificate_hash: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalAction:
    action_id: str
    operation: str
    target_ids: tuple[str, ...]
    arguments: tuple[CanonicalExpression, ...] = ()
    warrant: str = ""
    preconditions: tuple[CanonicalExpression, ...] = ()
    generated_obligations: tuple[Obligation, ...] = ()
    expected_usefulness: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "operation": self.operation,
            "target_ids": list(self.target_ids),
            "arguments": [item.to_dict() for item in self.arguments],
            "warrant": self.warrant,
            "preconditions": [item.to_dict() for item in self.preconditions],
            "generated_obligations": [item.to_dict() for item in self.generated_obligations],
            "expected_usefulness": self.expected_usefulness,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            action_id=str(raw["action_id"]),
            operation=str(raw["operation"]),
            target_ids=tuple(str(item) for item in raw.get("target_ids", ())),
            arguments=tuple(
                CanonicalExpression.from_dict(item) for item in raw.get("arguments", ())
            ),
            warrant=str(raw.get("warrant", "")),
            preconditions=tuple(
                CanonicalExpression.from_dict(item) for item in raw.get("preconditions", ())
            ),
            generated_obligations=tuple(
                Obligation.from_dict(item) for item in raw.get("generated_obligations", ())
            ),
            expected_usefulness=float(raw.get("expected_usefulness", 1.0)),
        )


def _dataclass_records(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


@dataclass(frozen=True, slots=True)
class CanonicalState:
    state_id: str
    objects: tuple[MathObject, ...]
    bindings: tuple[Binding, ...]
    assumptions: tuple[CanonicalExpression, ...]
    established_facts: tuple[CanonicalExpression, ...]
    propositions: tuple[CanonicalExpression, ...]
    goal: CanonicalExpression
    obligations: tuple[Obligation, ...]
    evidence_dependencies: tuple[EvidenceNode, ...]
    local_scope: tuple[str, ...]
    legal_actions: tuple[CanonicalAction, ...]
    plausible_invalid_actions: tuple[CanonicalAction, ...] = ()
    terminal_status: str = "OPEN"
    schema_version: str = SCHEMA_VERSION
    execution_metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(
        self, *, include_execution: bool = True, include_display_identity: bool = True
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "objects": [item.to_dict() for item in self.objects],
            "bindings": _dataclass_records(self.bindings),
            "assumptions": [item.to_dict() for item in self.assumptions],
            "established_facts": [item.to_dict() for item in self.established_facts],
            "propositions": [item.to_dict() for item in self.propositions],
            "goal": self.goal.to_dict(),
            "obligations": [item.to_dict() for item in self.obligations],
            "evidence_dependencies": _dataclass_records(self.evidence_dependencies),
            "local_scope": list(self.local_scope),
            "legal_actions": [item.to_dict() for item in self.legal_actions],
            "plausible_invalid_actions": [
                item.to_dict() for item in self.plausible_invalid_actions
            ],
            "terminal_status": self.terminal_status,
        }
        if include_display_identity:
            result["state_id"] = self.state_id
        if include_execution:
            result["execution_metadata"] = dict(self.execution_metadata)
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            state_id=str(raw.get("state_id", "state:decoded")),
            objects=tuple(MathObject.from_dict(item) for item in raw.get("objects", ())),
            bindings=tuple(Binding(**item) for item in raw.get("bindings", ())),
            assumptions=tuple(
                CanonicalExpression.from_dict(item) for item in raw.get("assumptions", ())
            ),
            established_facts=tuple(
                CanonicalExpression.from_dict(item) for item in raw.get("established_facts", ())
            ),
            propositions=tuple(
                CanonicalExpression.from_dict(item) for item in raw.get("propositions", ())
            ),
            goal=CanonicalExpression.from_dict(raw["goal"]),
            obligations=tuple(Obligation.from_dict(item) for item in raw.get("obligations", ())),
            evidence_dependencies=tuple(
                EvidenceNode(
                    evidence_id=str(item["evidence_id"]),
                    status=str(item["status"]),
                    dependencies=tuple(item.get("dependencies", ())),
                    authority=str(item.get("authority", "native")),
                    certificate_hash=item.get("certificate_hash"),
                )
                for item in raw.get("evidence_dependencies", ())
            ),
            local_scope=tuple(str(item) for item in raw.get("local_scope", ())),
            legal_actions=tuple(
                CanonicalAction.from_dict(item) for item in raw.get("legal_actions", ())
            ),
            plausible_invalid_actions=tuple(
                CanonicalAction.from_dict(item) for item in raw.get("plausible_invalid_actions", ())
            ),
            terminal_status=str(raw.get("terminal_status", "OPEN")),
            schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
            execution_metadata=tuple(
                sorted((str(k), str(v)) for k, v in raw.get("execution_metadata", {}).items())
            ),
        )

    @property
    def mathematical_hash(self) -> str:
        return stable_hash(self.to_dict(include_execution=False, include_display_identity=False))

    @property
    def artifact_hash(self) -> str:
        return stable_hash(self.to_dict())

    def without_execution_metadata(self) -> Self:
        return replace(self, execution_metadata=())


@dataclass(frozen=True, slots=True)
class VerificationRecord:
    verifier: str
    verifier_version: str
    status: VerificationStatus
    accepted: bool
    details: str = ""
    certificate_hash: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalTransition:
    transition_id: str
    state_before: CanonicalState
    action: CanonicalAction
    state_after: CanonicalState
    verification: tuple[VerificationRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "state_before": self.state_before.to_dict(),
            "action": self.action.to_dict(),
            "state_after": self.state_after.to_dict(),
            "verification": [asdict(item) for item in self.verification],
        }


@dataclass(frozen=True, slots=True)
class CanonicalTrajectory:
    trajectory_id: str
    problem: CanonicalExpression
    initial_state: CanonicalState
    transitions: tuple[CanonicalTransition, ...]
    final_state: CanonicalState
    final_answer: CanonicalExpression | None
    proof_closure: str
    quality: GoldStatus
    provenance: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "problem": self.problem.to_dict(),
            "initial_state": self.initial_state.to_dict(),
            "transitions": [item.to_dict() for item in self.transitions],
            "final_state": self.final_state.to_dict(),
            "final_answer": self.final_answer.to_dict() if self.final_answer else None,
            "proof_closure": self.proof_closure,
            "quality": self.quality.value,
            "provenance": dict(self.provenance),
        }

    @property
    def content_hash(self) -> str:
        value = self.to_dict()
        value.pop("trajectory_id", None)
        return stable_hash(value)
