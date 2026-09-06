"""Deterministic truth-derived projections and information accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arena.canonical.schema import CanonicalAction, CanonicalState, stable_hash

from .genome import (
    ActionGoalProjection,
    ContentGenome,
    DependencyProjection,
    EvidenceProjection,
    ObligationProjection,
    PremiseProjection,
    StateDeltaProjection,
)

PROJECTION_VERSION = "arena-truth-derived-projection-v1.0.0"


@dataclass(frozen=True, slots=True)
class DerivedRelation:
    relation: str
    payload: dict[str, Any]
    witness_hashes: tuple[str, ...]
    derivation_rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation": self.relation,
            "payload": self.payload,
            "witness_hashes": list(self.witness_hashes),
            "derivation_rule": self.derivation_rule,
            "relation_hash": stable_hash(
                {
                    "relation": self.relation,
                    "payload": self.payload,
                    "witness_hashes": self.witness_hashes,
                    "derivation_rule": self.derivation_rule,
                }
            ),
        }


@dataclass(frozen=True, slots=True)
class TruthDerivedView:
    source_state_hash: str
    previous_state_hash: str | None
    option_set_hash: str
    relations: tuple[DerivedRelation, ...]
    omissions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_version": PROJECTION_VERSION,
            "source_state_hash": self.source_state_hash,
            "previous_state_hash": self.previous_state_hash,
            "option_set_hash": self.option_set_hash,
            "relations": [item.to_dict() for item in self.relations],
            "omissions": list(self.omissions),
        }


def _witness(value: object) -> str:
    return stable_hash(value)


def _relation(
    name: str, payload: dict[str, Any], witnesses: tuple[object, ...], rule: str
) -> DerivedRelation:
    return DerivedRelation(name, payload, tuple(_witness(item) for item in witnesses), rule)


def _state_payload(state: CanonicalState) -> dict[str, Any]:
    return state.to_dict(include_execution=False, include_display_identity=False)


def _action_payload(action: CanonicalAction) -> dict[str, Any]:
    payload = action.to_dict()
    payload.pop("expected_usefulness", None)
    return payload


def _changed_fields(before: CanonicalState, after: CanonicalState) -> tuple[str, ...]:
    left, right = _state_payload(before), _state_payload(after)
    return tuple(key for key in sorted(left) if left[key] != right[key])


def derive_truth_view(
    state: CanonicalState,
    genome: ContentGenome,
    *,
    options: tuple[CanonicalAction, ...] = (),
    previous_state: CanonicalState | None = None,
) -> TruthDerivedView:
    """Compile a view from allowed canonical inputs, never from option correctness labels."""

    relations: list[DerivedRelation] = []
    omissions: list[str] = []
    payload: dict[str, Any]

    evidence = state.evidence_dependencies
    if genome.dependency_projection == DependencyProjection.IMPLICIT:
        omissions.append("explicit_dependency_edges")
    else:
        edges = [
            {"from": node.evidence_id, "to": dependency}
            for node in evidence
            for dependency in node.dependencies
        ]
        if genome.dependency_projection == DependencyProjection.EXPLICIT_LOCAL_EDGE:
            local = set(state.local_scope)
            local_edges = [edge for edge in edges if edge["from"] in local or edge["to"] in local]
            edges = local_edges if local_edges else edges[-1:]
        relations.append(
            _relation(
                "dependency_edges",
                {"edges": edges},
                tuple({"id": node.evidence_id, "deps": node.dependencies} for node in evidence),
                genome.dependency_projection.value,
            )
        )

    option_payloads = tuple(_action_payload(action) for action in options)
    if genome.action_goal_projection == ActionGoalProjection.IMPLICIT:
        omissions.append("explicit_action_goal_links")
    else:
        links: list[dict[str, Any]] = []
        objects = {item.object_id: item.to_dict() for item in state.objects}
        goal_hash = state.goal.content_hash
        for action in options:
            link: dict[str, Any] = {
                "action_id": action.action_id,
                "target_ids": list(action.target_ids),
                "goal_hash": goal_hash,
            }
            if genome.action_goal_projection == ActionGoalProjection.TARGET_BLOCK:
                link["target_block"] = [
                    objects[item] for item in action.target_ids if item in objects
                ]
            links.append(link)
        relations.append(
            _relation(
                "action_goal_links",
                {"links": links},
                (*option_payloads, state.goal.to_dict()),
                genome.action_goal_projection.value,
            )
        )

    if genome.premise_projection == PremiseProjection.GLOBAL_LIST:
        premises = [item.to_dict() for item in state.assumptions]
        relations.append(
            _relation(
                "global_premises",
                {"premises": premises},
                tuple(premises),
                PremiseProjection.GLOBAL_LIST.value,
            )
        )
    else:
        action_premises = [
            {
                "action_id": action.action_id,
                "premises": [item.to_dict() for item in action.preconditions],
            }
            for action in options
        ]
        name = (
            "action_local_premises"
            if genome.premise_projection == PremiseProjection.ACTION_LOCAL
            else "action_premise_edges"
        )
        relations.append(
            _relation(
                name, {"actions": action_premises}, option_payloads, genome.premise_projection.value
            )
        )

    if genome.obligation_projection == ObligationProjection.GLOBAL:
        obligations = [item.to_dict() for item in state.obligations]
        relations.append(
            _relation(
                "global_obligations",
                {"obligations": obligations},
                tuple(obligations),
                ObligationProjection.GLOBAL.value,
            )
        )
    elif genome.obligation_projection == ObligationProjection.OWNER_LOCAL:
        owners: dict[str, list[dict[str, Any]]] = {}
        for obligation in state.obligations:
            owners.setdefault(obligation.source, []).append(obligation.to_dict())
        relations.append(
            _relation(
                "owner_local_obligations",
                {"owners": owners},
                tuple(item.to_dict() for item in state.obligations),
                ObligationProjection.OWNER_LOCAL.value,
            )
        )
    else:
        action_obligations = [
            {
                "action_id": action.action_id,
                "obligations": [item.to_dict() for item in action.generated_obligations],
            }
            for action in options
        ]
        relations.append(
            _relation(
                "action_local_obligations",
                {"actions": action_obligations},
                option_payloads,
                ObligationProjection.ACTION_LOCAL.value,
            )
        )

    if previous_state is None:
        omissions.append("state_delta_unavailable_without_previous_state")
    elif genome.state_delta_projection == StateDeltaProjection.FULL_BEFORE_AFTER:
        relations.append(
            _relation(
                "full_state_transition",
                {"before": _state_payload(previous_state), "after": _state_payload(state)},
                (_state_payload(previous_state), _state_payload(state)),
                StateDeltaProjection.FULL_BEFORE_AFTER.value,
            )
        )
    else:
        changed = _changed_fields(previous_state, state)
        before, after = _state_payload(previous_state), _state_payload(state)
        if genome.state_delta_projection == StateDeltaProjection.DELTA_PLUS_CONTEXT:
            payload = {
                "changed": {key: {"before": before[key], "after": after[key]} for key in changed},
                "unchanged_context_hash": stable_hash(
                    {key: after[key] for key in sorted(after) if key not in changed}
                ),
            }
        else:
            payload = {
                "changed_relations": [
                    {
                        "field": key,
                        "before_hash": _witness(before[key]),
                        "after_hash": _witness(after[key]),
                    }
                    for key in changed
                ]
            }
        relations.append(
            _relation(
                "state_delta",
                payload,
                (_state_payload(previous_state), _state_payload(state)),
                genome.state_delta_projection.value,
            )
        )

    if genome.evidence_projection == EvidenceProjection.STATUS_ONLY:
        payload = {"status": {node.evidence_id: node.status for node in evidence}}
    elif genome.evidence_projection == EvidenceProjection.PROOF_EDGE:
        payload = {
            "proof_edges": [
                {"from": node.evidence_id, "to": dependency}
                for node in evidence
                for dependency in node.dependencies
            ]
        }
    else:
        payload = {
            "provenance": [
                {
                    "evidence_id": node.evidence_id,
                    "status": node.status,
                    "authority": node.authority,
                    "certificate_hash": node.certificate_hash,
                }
                for node in evidence
            ]
        }
    relations.append(
        _relation(
            "evidence_projection",
            payload,
            tuple(
                {
                    "evidence_id": node.evidence_id,
                    "status": node.status,
                    "dependencies": node.dependencies,
                    "authority": node.authority,
                    "certificate_hash": node.certificate_hash,
                }
                for node in evidence
            ),
            genome.evidence_projection.value,
        )
    )

    return TruthDerivedView(
        source_state_hash=state.mathematical_hash,
        previous_state_hash=previous_state.mathematical_hash if previous_state else None,
        option_set_hash=stable_hash(option_payloads),
        relations=tuple(relations),
        omissions=tuple(sorted(omissions)),
    )
