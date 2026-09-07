"""The fine-tuning record.

One record is one decision: the state, what could have been done, what was done, what the
verifier said, and where the whole thing came from.

**Two design decisions are worth stating, because both are fixes for measured defects.**

*Targets are rendered through the same surface as the inputs.*
``docs/ROUTE_B_PARITY_AUDIT.md`` defect D3 found that the historical training path always
wrote its target as canonical JSON, so ``L3_JSON_AST`` alone enjoyed
input-grammar == output-grammar -- a live alternative explanation for its historical win.
Here an action is rendered by wrapping it in an :func:`action_envelope` and pushing that
through the *same* :class:`surfaces.Surface`.  Every arm therefore has
input-grammar == output-grammar, and the confound is removed by construction rather than
by preregistration.

*There is exactly one serialization and one hashing scheme.*
The structural spelling of a state is its own lossless TL0 text, and the content hash is
``arena.canonical.schema.stable_hash`` -- the project's existing primitive, the same one
``arena/training/route_b_data.py`` uses.  No second scheme is introduced here.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arena.canonical.schema import stable_hash

from .core import Action, Evidence, Goal, Scope, State, Status, StatusError, TL0Error
from .parser import parse_state
from .renderer import LOSSLESS, render_state
from .surfaces import Surface, SurfaceDescriptor

RECORD_SCHEMA_VERSION = "tl0-training-record-v1"
ACTION_ENVELOPE_STATUS = "ACTION"


class TrainingDataError(TL0Error):
    """A training record is malformed, unprovenanced or fails its own hash."""


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    """What a verifier actually said.  ``VERIFIED`` needs a name and a version, here too."""

    verifier: str
    verifier_version: str
    status: Status
    accepted: bool
    certificate_hash: str | None = None
    details: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", Status(self.status))
        if self.status is Status.VERIFIED and not (self.verifier and self.verifier_version):
            raise StatusError(
                "a VERIFIED training outcome requires a named verifier and verifier_version"
            )
        if self.status is Status.VERIFIED and not self.accepted:
            raise StatusError("a VERIFIED training outcome cannot record accepted=False")

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier": self.verifier,
            "verifier_version": self.verifier_version,
            "status": self.status.value,
            "accepted": self.accepted,
            "certificate_hash": self.certificate_hash,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where the record came from, and the assertion that no sealed split was touched."""

    source: str
    source_id: str
    generator: str
    generator_version: str
    sealed_splits_excluded: bool
    sealed_splits_manifest: str = "artifacts/manifests/SEALED_SPLITS.json"
    licence: str = "unrecorded"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "generator": self.generator,
            "generator_version": self.generator_version,
            "sealed_splits_excluded": self.sealed_splits_excluded,
            "sealed_splits_manifest": self.sealed_splits_manifest,
            "licence": self.licence,
            "notes": self.notes,
        }


def action_envelope(state: State, action: Action) -> State:
    """Wrap one action in the smallest state that still validates.

    The envelope carries the source state's scope forest plus exactly the declarations,
    goals and evidence the action refers to -- never the rest of the state, which would
    leak the answer's context into the target.
    """

    targets = set(action.targets)
    evidence_ids = {action.evidence_id} | {
        item.evidence_id for item in action.generated_obligations
    }
    evidence_ids.discard(None)
    return State(
        state_id=f"{state.state_id}/action",
        scopes=state.scopes,
        declarations=tuple(i for i in state.declarations if i.decl_id in targets),
        goals=tuple(_neutralise(i) for i in state.goals if i.goal_id in targets),
        evidence=tuple(i for i in state.evidence if i.evidence_id in evidence_ids),
        actions=(action,),
        terminal_status=ACTION_ENVELOPE_STATUS,
    )


def _neutralise(goal: Goal) -> Goal:
    """Strip a target goal's own status link; the envelope carries the action, not a verdict."""

    return Goal(
        goal_id=goal.goal_id,
        scope_id=goal.scope_id,
        statement=goal.statement,
        status=goal.status,
        focused=goal.focused,
        evidence_id=goal.evidence_id,
        attributes=goal.attributes,
    )


def action_from_envelope(envelope: State) -> Action:
    if len(envelope.actions) != 1:
        raise TrainingDataError(
            f"an action envelope holds exactly one action, got {len(envelope.actions)}"
        )
    return envelope.actions[0]


def render_action(state: State, action: Action, surface: Surface) -> str:
    """Render one action through the *same* surface as the state.  See D3, above.

    A prompt view hides the candidate actions from the input but must still be able to
    spell a target, so the rendering goes through :meth:`surfaces.Surface.target_surface`,
    which keeps the grammar family and only widens the configuration.
    """

    return surface.target_surface().render(action_envelope(state, action))


def parse_action(text: str, surface: Surface) -> Action:
    return action_from_envelope(surface.target_surface().parse(text))


@dataclass(frozen=True, slots=True)
class StateDelta:
    """What an action actually changed.  Derived from the two states, never asserted."""

    goals_added: tuple[str, ...]
    goals_removed: tuple[str, ...]
    goals_closed: tuple[str, ...]
    obligations_added: tuple[str, ...]
    obligations_discharged: tuple[str, ...]
    claims_added: tuple[str, ...]
    declarations_added: tuple[str, ...]
    evidence_added: tuple[str, ...]
    scopes_added: tuple[str, ...]
    generated_obligations_missing: tuple[str, ...]
    terminal_status_changed: bool

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.goals_added,
                self.goals_removed,
                self.goals_closed,
                self.obligations_added,
                self.obligations_discharged,
                self.claims_added,
                self.declarations_added,
                self.evidence_added,
                self.scopes_added,
                self.terminal_status_changed,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goals_added": list(self.goals_added),
            "goals_removed": list(self.goals_removed),
            "goals_closed": list(self.goals_closed),
            "obligations_added": list(self.obligations_added),
            "obligations_discharged": list(self.obligations_discharged),
            "claims_added": list(self.claims_added),
            "declarations_added": list(self.declarations_added),
            "evidence_added": list(self.evidence_added),
            "scopes_added": list(self.scopes_added),
            "generated_obligations_missing": list(self.generated_obligations_missing),
            "terminal_status_changed": self.terminal_status_changed,
        }


def _added(before: Iterable[str], after: Iterable[str]) -> tuple[str, ...]:
    known = set(before)
    return tuple(item for item in after if item not in known)


@dataclass(frozen=True, slots=True)
class Transition:
    """``state_before -{action}-> state_after``, with what the verifier said about it.

    The delta is *computed* from the two states rather than stored, so it can never
    disagree with the states it claims to relate.  One rule is fail-closed: a transition
    whose verification says ``VERIFIED`` must leave a matching verification record in
    ``state_after``.  Otherwise a trajectory could assert verification that no state can
    show -- the same failure mode section 4 of the spec forbids inside a state.
    """

    transition_id: str
    state_before: State
    action: Action
    state_after: State
    verification: tuple[VerificationOutcome, ...] = ()

    def __post_init__(self) -> None:
        if not self.transition_id:
            raise TrainingDataError("transition_id must be non-empty")
        for existing in self.state_before.actions:
            if existing.action_id == self.action.action_id and existing != self.action:
                raise TrainingDataError(
                    f"action {self.action.action_id} differs from the action of the same id "
                    "offered by state_before"
                )
        for outcome in self.verification:
            if outcome.status is not Status.VERIFIED:
                continue
            matching = [
                item
                for item in self.state_after.evidence
                if item.status is Status.VERIFIED
                and item.verifier == outcome.verifier
                and item.verifier_version == outcome.verifier_version
            ]
            if not matching:
                raise StatusError(
                    f"transition {self.transition_id} records a VERIFIED outcome from "
                    f"{outcome.verifier} {outcome.verifier_version} but state_after holds no "
                    "matching verification record"
                )

    def delta(self) -> StateDelta:
        before, after = self.state_before, self.state_after
        closed_before = {item.goal_id for item in before.goals if item.status is Status.VERIFIED}
        generated = {item.obligation_id for item in self.action.generated_obligations}
        after_obligations = {item.obligation_id for item in after.obligations}
        return StateDelta(
            goals_added=_added((i.goal_id for i in before.goals), (i.goal_id for i in after.goals)),
            goals_removed=_added(
                (i.goal_id for i in after.goals), (i.goal_id for i in before.goals)
            ),
            goals_closed=tuple(
                item.goal_id
                for item in after.goals
                if item.status is Status.VERIFIED and item.goal_id not in closed_before
            ),
            obligations_added=_added(
                (i.obligation_id for i in before.obligations), sorted(after_obligations)
            ),
            obligations_discharged=_added(
                sorted(after_obligations), (i.obligation_id for i in before.obligations)
            ),
            claims_added=_added(
                (i.claim_id for i in before.claims), (i.claim_id for i in after.claims)
            ),
            declarations_added=_added(
                (i.decl_id for i in before.declarations),
                (i.decl_id for i in after.declarations),
            ),
            evidence_added=_added(
                (i.evidence_id for i in before.evidence), (i.evidence_id for i in after.evidence)
            ),
            scopes_added=_added(
                (i.scope_id for i in before.scopes), (i.scope_id for i in after.scopes)
            ),
            generated_obligations_missing=tuple(
                sorted(generated - after_obligations - _discharged(after))
            ),
            terminal_status_changed=before.terminal_status != after.terminal_status,
        )

    def to_dict(self, surface: Surface) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "transition_id": self.transition_id,
            "state_before": render_state(self.state_before, LOSSLESS),
            "rendered_state_before": surface.render(self.state_before),
            "action": render_state(action_envelope(self.state_before, self.action), LOSSLESS),
            "rendered_action": render_action(self.state_before, self.action, surface),
            "state_after": render_state(self.state_after, LOSSLESS),
            "rendered_state_after": surface.render(self.state_after),
            "verification": [item.to_dict() for item in self.verification],
            "delta": self.delta().to_dict(),
            "surface": surface.descriptor().to_dict(),
        }
        payload["content_hash"] = stable_hash(payload)
        return payload


def _discharged(state: State) -> set[str]:
    return {
        item.obligation_id
        for item in state.obligations
        if item.status in (Status.VERIFIED, Status.REFUTED)
    }


@dataclass(frozen=True, slots=True)
class TrainingRecord:
    """One supervised decision.  Structural; rendering happens in :meth:`to_dict`."""

    trajectory_id: str
    problem_id: str
    step_index: int
    state_t: State
    chosen_action: Action
    next_state: State
    verification: VerificationOutcome
    outcome: str
    provenance: Provenance
    candidate_actions: tuple[Action, ...] = ()
    warrant: str = ""
    schema_version: str = RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RECORD_SCHEMA_VERSION:
            raise TrainingDataError(f"unsupported record schema {self.schema_version!r}")
        if self.step_index < 0:
            raise TrainingDataError("step_index must be non-negative")
        if self.candidate_actions and all(
            item.action_id != self.chosen_action.action_id for item in self.candidate_actions
        ):
            raise TrainingDataError(
                f"chosen action {self.chosen_action.action_id} is not among the "
                "candidate actions offered"
            )

    def to_dict(self, surface: Surface) -> dict[str, Any]:
        """Materialise the fine-tuning record against one surface, with its content hash."""

        descriptor = surface.descriptor()
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "trajectory_id": self.trajectory_id,
            "problem_id": self.problem_id,
            "step_index": self.step_index,
            "state_t": render_state(self.state_t, LOSSLESS),
            "rendered_state_t": surface.render(self.state_t),
            "candidate_actions": [
                render_state(action_envelope(self.state_t, item), LOSSLESS)
                for item in self.candidate_actions
            ],
            "rendered_candidate_actions": [
                render_action(self.state_t, item, surface) for item in self.candidate_actions
            ],
            "chosen_action": render_state(
                action_envelope(self.state_t, self.chosen_action), LOSSLESS
            ),
            "rendered_chosen_action": render_action(self.state_t, self.chosen_action, surface),
            "warrant": self.warrant or self.chosen_action.warrant,
            "next_state": render_state(self.next_state, LOSSLESS),
            "rendered_next_state": surface.render(self.next_state),
            "verification": self.verification.to_dict(),
            "outcome": self.outcome,
            "provenance": self.provenance.to_dict(),
            "surface": descriptor.to_dict(),
        }
        payload["content_hash"] = stable_hash(payload)
        return payload

    def content_hash(self, surface: Surface) -> str:
        return str(self.to_dict(surface)["content_hash"])


def validate_record_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on a materialised record: schema, provenance and self-consistent hash."""

    if payload.get("schema_version") != RECORD_SCHEMA_VERSION:
        raise TrainingDataError(f"unsupported record schema {payload.get('schema_version')!r}")
    expected = dict(payload)
    recorded = expected.pop("content_hash", None)
    if recorded is None:
        raise TrainingDataError("record has no content_hash")
    if stable_hash(expected) != recorded:
        raise TrainingDataError("record content_hash does not match its content")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("sealed_splits_excluded"):
        raise TrainingDataError(
            "record does not assert sealed_splits_excluded; refusing it rather than "
            "letting a promotion split leak into training"
        )
    rendered_lengths = (
        len(payload["candidate_actions"]),
        len(payload["rendered_candidate_actions"]),
    )
    if len(set(rendered_lengths)) != 1:
        raise TrainingDataError("candidate action lists disagree in length")
    return payload


def write_jsonl(path: str | Path, records: Iterable[TrainingRecord], surface: Surface) -> str:
    """Write a shard and return its dataset hash.  Refuses unprovenanced records."""

    payloads = [validate_record_dict(record.to_dict(surface)) for record in records]
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in payloads]
    destination.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return stable_hash(payloads)


def read_jsonl(path: str | Path, *, surface: Surface | None = None) -> Iterator[dict[str, Any]]:
    """Read a shard, validating every record; optionally re-parse each rendering."""

    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = validate_record_dict(json.loads(line))
        except (TypeError, ValueError) as error:
            raise TrainingDataError(f"line {number}: {error}") from error
        if surface is not None:
            _check_round_trip(payload, surface, number)
        yield payload


def _check_round_trip(payload: dict[str, Any], surface: Surface, number: int) -> None:
    descriptor: SurfaceDescriptor = surface.descriptor()
    if payload["surface"]["surface_id"] != descriptor.surface_id:
        raise TrainingDataError(
            f"line {number}: record was written for surface "
            f"{payload['surface']['surface_id']!r}, not {descriptor.surface_id!r}"
        )
    for key in ("rendered_state_t", "rendered_next_state"):
        structural = parse_state(payload[key.replace("rendered_", "")])
        if surface.render(structural) != payload[key]:
            raise TrainingDataError(f"line {number}: {key} does not match its structural state")


def make_evidence(outcome: VerificationOutcome, evidence_id: str) -> Evidence:
    """Turn a verifier's verdict into the evidence node a VERIFIED annotation needs."""

    return Evidence(
        evidence_id=evidence_id,
        status=outcome.status,
        verifier=outcome.verifier,
        verifier_version=outcome.verifier_version,
        certificate_hash=outcome.certificate_hash,
        details=outcome.details,
    )


def root_scope(state: State) -> Scope:
    return state.scopes[0]


__all__ = [
    "ACTION_ENVELOPE_STATUS",
    "RECORD_SCHEMA_VERSION",
    "Provenance",
    "StateDelta",
    "Transition",
    "TrainingDataError",
    "TrainingRecord",
    "VerificationOutcome",
    "action_envelope",
    "action_from_envelope",
    "make_evidence",
    "parse_action",
    "read_jsonl",
    "render_action",
    "root_scope",
    "validate_record_dict",
    "write_jsonl",
]
