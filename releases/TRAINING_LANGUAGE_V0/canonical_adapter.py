"""The seam between TL0 and the frozen ``arena-canonical-v0.1.0`` substrate.

Nothing here modifies the substrate.  ``schema_version`` is never bumped -- doing so
re-hashes every state in the project (``docs/CANONICAL_VNEXT_PILOT.md`` section 2).

**The adapter never drops data silently.**  Every mapping decision is recorded as a
:class:`LossItem` with one of four kinds:

``ENCODED``
    Structure preserved through an injective, reversible encoding.  A structured
    :class:`core.Type` becomes the flat ``sort`` string ``"[Fun [Nat] [Prop]]"``: the bytes
    and the tree both survive, but the substrate reasons about it as an opaque string.
``CARRIED``
    Preserved verbatim, out of band, in a reserved ``tl0.*`` attribute on the canonical
    goal expression.  ``attributes`` is ``string -> string`` and survives the strict wire
    validator byte-identically (the pilot's Probe D), which is what makes this viable.
``SYNTHESIZED``
    Data the substrate *requires* but the source did not have -- above all the single
    mandatory ``goal``, which 17.4% of measured real Lean states do not possess.
``DROPPED``
    Genuinely lost.  Only reachable under :attr:`LossPolicy.DROP`.

Two facts about the frozen verifier shape the default compatibility profile, and both were
read out of ``arena/verifier/native.py`` rather than assumed:

* ``native.py:136`` -- ``free_names`` counts only bindings whose ``binder_kind`` is exactly
  ``"free"``.  Emitting an honest ``forall``/``implicit``/``instance`` kind therefore makes
  the frozen verifier report ``UNBOUND_VARIABLE``.
* ``native.py:231-232`` -- ``all_targets = set(object_ids) | {"goal"}``.  An action that
  targets a goal *id* is reported as ``UNKNOWN_ACTION_TARGET``.

:attr:`CompatibilityProfile.ARENA_VERIFIER` rewrites both and carries the truth, so the
reverse mapping is still exact.  :attr:`CompatibilityProfile.HONEST` does neither.
``tests/releases/test_canonical_adapter.py`` runs the real ``NativeVerifier`` over both and
pins the difference, so this is a measurement and not a claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from arena.canonical.schema import (
    SCHEMA_VERSION,
    Binding,
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    EvidenceNode,
    MathObject,
    canonical_json,
)
from arena.canonical.schema import Obligation as CanonicalObligation

from .core import (
    RESERVED_ATTRIBUTE_PREFIX,
    Action,
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Evidence,
    Extension,
    Goal,
    LibraryRef,
    Obligation,
    Scope,
    State,
    Status,
    Term,
    TL0Error,
    Type,
    is_identifier,
    normalise_attributes,
)
from .parser import parse_type
from .renderer import render_type
from .syntax import Cursor, tokenize

CARRIER_VERSION = "tl0-canonical-carrier-v1"
ABSENT_GOAL_OP = "tl0.absent_goal"
ROOT_SCOPE = "tl0.root"
USEFULNESS_KEY = "canonical.expected_usefulness"
_KINDS = {item.value for item in DeclKind}
_STATUSES = {item.value for item in Status}


class CanonicalMappingError(TL0Error):
    """The requested mapping cannot be performed under the requested policy."""


class LossKind(StrEnum):
    ENCODED = "ENCODED"
    CARRIED = "CARRIED"
    SYNTHESIZED = "SYNTHESIZED"
    DROPPED = "DROPPED"


class LossPolicy(StrEnum):
    #: Refuse anything the substrate cannot express natively.  Only ENCODED is tolerated.
    NATIVE_ONLY = "NATIVE_ONLY"
    #: Carry non-native structure in reserved ``tl0.*`` attributes.  The default.
    CARRY = "CARRY"
    #: Emit a substrate-pure state and record every casualty as DROPPED.
    DROP = "DROP"


class CompatibilityProfile(StrEnum):
    #: Rewrite binder kinds and action targets so the frozen NativeVerifier accepts the
    #: state.  The truth is carried, so the reverse mapping is still exact.
    ARENA_VERIFIER = "ARENA_VERIFIER"
    #: Emit honest binder kinds and targets, accepting the frozen verifier's complaints.
    HONEST = "HONEST"


@dataclass(frozen=True, slots=True)
class LossItem:
    kind: LossKind
    feature: str
    detail: str
    carried_in: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "feature": self.feature,
            "detail": self.detail,
            "carried_in": self.carried_in,
        }


@dataclass(frozen=True, slots=True)
class LossReport:
    items: tuple[LossItem, ...] = ()

    def of(self, kind: LossKind) -> tuple[LossItem, ...]:
        return tuple(item for item in self.items if item.kind is kind)

    @property
    def dropped(self) -> tuple[LossItem, ...]:
        return self.of(LossKind.DROPPED)

    @property
    def is_lossless(self) -> bool:
        """No data was lost.  Carrying and synthesis are still recorded."""

        return not self.dropped

    @property
    def is_native(self) -> bool:
        """The substrate expressed everything itself, with no out-of-band carriers."""

        return all(item.kind is LossKind.ENCODED for item in self.items)

    def features(self, kind: LossKind) -> tuple[str, ...]:
        return tuple(item.feature for item in self.of(kind))

    def to_dict(self) -> dict[str, Any]:
        return {
            "carrier_version": CARRIER_VERSION,
            "is_lossless": self.is_lossless,
            "is_native": self.is_native,
            "items": [item.to_dict() for item in self.items],
        }


class _Recorder:
    def __init__(self, policy: LossPolicy) -> None:
        self.policy = policy
        self.items: list[LossItem] = []

    def encoded(self, feature: str, detail: str) -> None:
        self.items.append(LossItem(LossKind.ENCODED, feature, detail))

    def non_native(self, feature: str, detail: str, carrier: str) -> None:
        if self.policy is LossPolicy.NATIVE_ONLY:
            raise CanonicalMappingError(
                f"{feature} cannot be expressed by {SCHEMA_VERSION} natively: {detail}"
            )
        if self.policy is LossPolicy.DROP:
            self.items.append(LossItem(LossKind.DROPPED, feature, detail, None))
            return
        self.items.append(LossItem(LossKind.CARRIED, feature, detail, carrier))

    def synthesized(self, feature: str, detail: str) -> None:
        if self.policy is LossPolicy.NATIVE_ONLY:
            raise CanonicalMappingError(f"{feature} would have to be invented: {detail}")
        self.items.append(LossItem(LossKind.SYNTHESIZED, feature, detail))

    def report(self) -> LossReport:
        return LossReport(tuple(self.items))


@dataclass(frozen=True, slots=True)
class CanonicalMapping:
    canonical: CanonicalState
    losses: LossReport


@dataclass(frozen=True, slots=True)
class TL0Import:
    state: State
    losses: LossReport


# -- type and term encoding --------------------------------------------------------


def encode_type(sort: Type) -> str:
    """Flatten a structured type into the canonical flat ``sort`` string.  Injective."""

    return render_type(sort)


def decode_type(text: str) -> Type:
    """Reverse :func:`encode_type`.  A foreign flat string becomes a bare head."""

    if text.startswith("[") and text.endswith("]"):
        try:
            cursor = Cursor(tokenize(text, line_number=0), line_number=0, line=text)
            sort = parse_type(cursor)
            cursor.finish()
        except TL0Error:
            return Type(text)
        return sort
    return Type(text or "Unknown")


def _attrs(pairs: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(pairs.items()))


def to_expression(term: Term, extra: dict[str, str] | None = None) -> CanonicalExpression:
    merged = dict(term.attributes)
    merged.update(extra or {})
    return CanonicalExpression(
        op=term.op,
        args=tuple(to_expression(item) for item in term.args),
        value=term.value,
        sort=encode_type(term.sort),
        attributes=_attrs(merged),
    )


def from_expression(expression: CanonicalExpression) -> Term:
    attributes = {
        key: value
        for key, value in expression.attributes
        if not key.startswith(RESERVED_ATTRIBUTE_PREFIX)
    }
    return Term(
        op=expression.op,
        sort=decode_type(expression.sort),
        value=expression.value,
        args=tuple(from_expression(item) for item in expression.args),
        attributes=normalise_attributes(attributes),
    )


# -- TL0 -> canonical --------------------------------------------------------------

_CLAIM_BUCKET = {
    ClaimRole.ASSUMPTION: "assumptions",
    ClaimRole.FACT: "established_facts",
    ClaimRole.IDENTITY: "established_facts",
    ClaimRole.PROPOSITION: "propositions",
    ClaimRole.DEFINITION: "propositions",
}

_NON_NATIVE = (
    (
        "scope_forest",
        "canonical bindings are state-global with a flat scope_id and no parent links",
        "goal.attributes['tl0.scopes']",
    ),
    (
        "obligation_scope",
        "canonical Obligation has no scope_id (measured gap N4)",
        "obligation.proposition.attributes['tl0.scope_id']",
    ),
    (
        "let_values",
        "canonical Binding has no value field and Binding(**item) rejects extra keys, so it "
        "is the one structure with no escape hatch (measured gap N2)",
        "goal.attributes['tl0.declarations']",
    ),
    (
        "metavariable_substitution",
        "canonical has no metavariable assignment map (measured gaps G2 == G6)",
        "goal.attributes['tl0.substitution']",
    ),
    (
        "evidence_detail",
        "canonical EvidenceNode has an authority but no verifier_version, details or attributes",
        "goal.attributes['tl0.evidence']",
    ),
    (
        "action_epistemics",
        "canonical CanonicalAction has no status, evidence link or attributes",
        "goal.attributes['tl0.actions']",
    ),
    (
        "libraries",
        "canonical has no slot for the domain libraries in force",
        "goal.attributes['tl0.libraries']",
    ),
)


def _claim_carrier(claim: Claim, order: int) -> dict[str, str]:
    return {
        "tl0.claim_id": claim.claim_id,
        "tl0.role": claim.role.value,
        "tl0.scope_id": claim.scope_id,
        "tl0.status": claim.status.value,
        "tl0.evidence_id": claim.evidence_id or "",
        "tl0.depends_on": canonical_json(list(claim.depends_on)),
        "tl0.attributes": canonical_json(dict(claim.attributes)),
        "tl0.order": str(order),
    }


def _obligation_carrier(obligation: Obligation) -> dict[str, str]:
    return {
        "tl0.scope_id": obligation.scope_id,
        "tl0.evidence_id": obligation.evidence_id or "",
        "tl0.attributes": canonical_json(dict(obligation.attributes)),
    }


def _to_canonical_obligation(obligation: Obligation) -> CanonicalObligation:
    return CanonicalObligation(
        obligation_id=obligation.obligation_id,
        proposition=to_expression(obligation.statement, _obligation_carrier(obligation)),
        status=obligation.status.value,
        source=obligation.source,
    )


def _carriers(state: State) -> dict[str, str]:
    return {
        "tl0.carrier": CARRIER_VERSION,
        "tl0.version": state.language_version,
        "tl0.state_id": state.state_id,
        "tl0.scopes": canonical_json([[i.scope_id, i.parent_id] for i in state.scopes]),
        "tl0.libraries": canonical_json([[i.library_id, i.version] for i in state.libraries]),
        "tl0.declarations": canonical_json(
            [
                {
                    "decl_id": item.decl_id,
                    "name": item.name,
                    "sort": encode_type(item.sort),
                    "scope_id": item.scope_id,
                    "kind": item.kind.value,
                    "value": to_expression(item.value).to_dict() if item.value else None,
                    "attributes": dict(item.attributes),
                }
                for item in state.declarations
            ]
        ),
        "tl0.goals": canonical_json(
            [
                {
                    "goal_id": item.goal_id,
                    "scope_id": item.scope_id,
                    "status": item.status.value,
                    "focused": item.focused,
                    "evidence_id": item.evidence_id,
                    "statement": to_expression(item.statement).to_dict(),
                    "attributes": dict(item.attributes),
                }
                for item in state.goals
            ]
        ),
        "tl0.substitution": canonical_json(
            [[name, to_expression(term).to_dict()] for name, term in state.substitution]
        ),
        "tl0.evidence": canonical_json(
            [
                {
                    "evidence_id": item.evidence_id,
                    "verifier": item.verifier,
                    "verifier_version": item.verifier_version,
                    "details": item.details,
                    "attributes": dict(item.attributes),
                }
                for item in state.evidence
            ]
        ),
        "tl0.actions": canonical_json(
            [
                {
                    "action_id": item.action_id,
                    "status": item.status.value,
                    "evidence_id": item.evidence_id,
                    "attributes": dict(item.attributes),
                    "targets": list(item.targets),
                }
                for item in state.actions
            ]
        ),
        "tl0.extensions": canonical_json(
            [[i.owner_id, i.key, i.payload] for i in state.extensions]
        ),
    }


def to_canonical(
    state: State,
    *,
    policy: LossPolicy = LossPolicy.CARRY,
    profile: CompatibilityProfile = CompatibilityProfile.ARENA_VERIFIER,
) -> CanonicalMapping:
    """Map a TL0 state onto ``arena-canonical-v0.1.0``, recording every mapping decision."""

    recorder = _Recorder(policy)
    recorder.encoded(
        "structured_types",
        "Type trees are flattened into the canonical flat `sort` string using the TL0 type "
        "surface syntax; the encoding is injective and reversible (measured gap G3)",
    )

    objects: list[MathObject] = []
    bindings: list[Binding] = []
    for decl in state.declarations:
        if decl.kind is DeclKind.OBJECT:
            shape, unit = _shape_and_unit(decl)
            objects.append(
                MathObject(
                    object_id=decl.decl_id,
                    type_name=encode_type(decl.sort),
                    value=to_expression(decl.value) if decl.value else None,
                    shape=shape,
                    unit=unit,
                )
            )
            continue
        kind = decl.kind.value
        if profile is CompatibilityProfile.ARENA_VERIFIER:
            kind = "free"
        bindings.append(
            Binding(
                binder_id=decl.decl_id,
                variable=decl.name,
                type_name=encode_type(decl.sort),
                scope_id=decl.scope_id,
                binder_kind=kind,
            )
        )
    if profile is CompatibilityProfile.ARENA_VERIFIER and any(
        item.kind not in (DeclKind.OBJECT, DeclKind.FREE) for item in state.declarations
    ):
        recorder.non_native(
            "binder_kind",
            "arena/verifier/native.py:136 counts only binder_kind == 'free' as declared, so "
            "an honest binder kind makes the frozen verifier emit UNBOUND_VARIABLE",
            "goal.attributes['tl0.declarations']",
        )

    buckets: dict[str, list[CanonicalExpression]] = {
        "assumptions": [],
        "established_facts": [],
        "propositions": [],
    }
    for order, claim in enumerate(state.claims):
        expression = to_expression(claim.statement, _claim_carrier(claim, order))
        buckets[_CLAIM_BUCKET[claim.role]].append(expression)
    if state.claims:
        recorder.non_native(
            "claim_identity",
            "canonical assumption/fact/proposition tuples are bare expressions with no id, "
            "role, scope, status or evidence link; those ride in the expression's own "
            "attributes",
            "expression.attributes['tl0.*']",
        )

    focus = state.focus_goal
    if focus is None:
        recorder.synthesized(
            "goal",
            f"{SCHEMA_VERSION} requires exactly one goal; this state has none, so a "
            f"placeholder {ABSENT_GOAL_OP!r} expression is emitted (measured gap G1: 17.4% "
            "of real Lean states carry zero goals)",
        )
        goal_term = Term(ABSENT_GOAL_OP, Type("Prop"))
    else:
        goal_term = focus.statement
    if len(state.goals) > 1:
        recorder.non_native(
            "multi_goal",
            f"{len(state.goals)} goals with per-goal scope; the substrate holds exactly one",
            "goal.attributes['tl0.goals']",
        )
    for feature, detail, carrier in _NON_NATIVE:
        recorder.non_native(feature, detail, carrier)
    if profile is CompatibilityProfile.ARENA_VERIFIER and len(state.scopes) > 1:
        recorder.non_native(
            "focus_context",
            "arena/verifier/native.py:82-84 requires every binding scope to appear in "
            "local_scope, so the focused goal's context chain is widened to their union",
            "goal.attributes['tl0.goals'] + goal.attributes['tl0.scopes']",
        )
    if state.extensions:
        recorder.non_native(
            "extensions",
            f"{len(state.extensions)} explicit TL0 extension records",
            "goal.attributes['tl0.extensions']",
        )

    carriers = _carriers(state) if policy is LossPolicy.CARRY else {}
    goal_expression = to_expression(goal_term, carriers)

    legal: list[CanonicalAction] = []
    invalid: list[CanonicalAction] = []
    object_ids = {item.object_id for item in objects}
    for action in state.actions:
        if profile is CompatibilityProfile.ARENA_VERIFIER:
            targets = tuple(target if target in object_ids else "goal" for target in action.targets)
        else:
            targets = action.targets
        canonical_action = CanonicalAction(
            action_id=action.action_id,
            operation=action.operation,
            target_ids=targets,
            arguments=tuple(to_expression(item) for item in action.arguments),
            warrant=action.warrant,
            preconditions=tuple(to_expression(item) for item in action.preconditions),
            generated_obligations=tuple(
                _to_canonical_obligation(item) for item in action.generated_obligations
            ),
            expected_usefulness=_expected_usefulness(state, action.action_id),
        )
        (invalid if action.status is Status.REFUTED else legal).append(canonical_action)

    canonical = CanonicalState(
        state_id=state.state_id,
        objects=tuple(objects),
        bindings=tuple(bindings),
        assumptions=tuple(buckets["assumptions"]),
        established_facts=tuple(buckets["established_facts"]),
        propositions=tuple(buckets["propositions"]),
        goal=goal_expression,
        obligations=tuple(_to_canonical_obligation(item) for item in state.obligations),
        evidence_dependencies=tuple(
            EvidenceNode(
                evidence_id=item.evidence_id,
                status=item.status.value,
                dependencies=item.depends_on,
                authority=item.verifier or "native",
                certificate_hash=item.certificate_hash,
            )
            for item in state.evidence
        ),
        local_scope=_local_scope(state, focus, bindings, profile),
        legal_actions=tuple(legal),
        plausible_invalid_actions=tuple(invalid),
        terminal_status=state.terminal_status,
        schema_version=SCHEMA_VERSION,
    )
    return CanonicalMapping(canonical, recorder.report())


def _local_scope(
    state: State,
    focus: Goal | None,
    bindings: list[Binding],
    profile: CompatibilityProfile,
) -> tuple[str, ...]:
    """Choose ``CanonicalState.local_scope``.

    ``arena/verifier/native.py:82-84`` requires every binding's ``scope_id`` to appear in
    ``local_scope``, so the verifier-compatible profile widens the focused goal's context
    chain to the union of every referenced scope.  The true chain is recoverable from
    ``tl0.scopes`` plus the focused goal, so widening loses nothing.
    """

    chain = state.scope_chain(focus.scope_id) if focus else ()
    if profile is CompatibilityProfile.HONEST:
        return chain
    return tuple(dict.fromkeys([*chain, *(item.scope_id for item in bindings)]))


def _shape_and_unit(decl: Decl) -> tuple[tuple[int | str, ...], str | None]:
    mapping = dict(decl.attributes)
    raw = mapping.get("canonical.shape")
    shape: tuple[int | str, ...] = tuple(json.loads(raw)) if raw else ()
    return shape, mapping.get("canonical.unit")


def _expected_usefulness(state: State, action_id: str) -> float:
    for extension in state.extensions:
        if extension.owner_id == action_id and extension.key == USEFULNESS_KEY:
            return float(extension.payload)
    return 1.0


# -- canonical -> TL0 --------------------------------------------------------------


def from_canonical(canonical: CanonicalState) -> TL0Import:
    """Reverse :func:`to_canonical`, or import a foreign canonical state best-effort.

    When the canonical goal carries a ``tl0.carrier`` attribute the original TL0 state is
    reconstructed exactly.  Otherwise the state is rebuilt from the canonical fields alone
    and every invention is recorded as ``SYNTHESIZED``.
    """

    carriers = dict(canonical.goal.attributes)
    if carriers.get("tl0.carrier") == CARRIER_VERSION:
        return TL0Import(_rebuild(canonical, carriers), LossReport())
    return _import_foreign(canonical)


def _rebuild(canonical: CanonicalState, carriers: dict[str, str]) -> State:
    declarations = tuple(
        Decl(
            decl_id=item["decl_id"],
            name=item["name"],
            sort=decode_type(item["sort"]),
            scope_id=item["scope_id"],
            kind=DeclKind(item["kind"]),
            value=(
                from_expression(CanonicalExpression.from_dict(item["value"]))
                if item["value"]
                else None
            ),
            attributes=item["attributes"],
        )
        for item in json.loads(carriers["tl0.declarations"])
    )
    claims: list[tuple[int, Claim]] = []
    for expression in (
        *canonical.assumptions,
        *canonical.established_facts,
        *canonical.propositions,
    ):
        meta = dict(expression.attributes)
        claims.append(
            (
                int(meta["tl0.order"]),
                Claim(
                    claim_id=meta["tl0.claim_id"],
                    role=ClaimRole(meta["tl0.role"]),
                    scope_id=meta["tl0.scope_id"],
                    statement=from_expression(expression),
                    status=Status(meta["tl0.status"]),
                    evidence_id=meta["tl0.evidence_id"] or None,
                    depends_on=tuple(json.loads(meta["tl0.depends_on"])),
                    attributes=json.loads(meta["tl0.attributes"]),
                ),
            )
        )
    claims.sort(key=lambda item: item[0])

    evidence_extra = {item["evidence_id"]: item for item in json.loads(carriers["tl0.evidence"])}
    action_records = json.loads(carriers["tl0.actions"])
    action_extra = {item["action_id"]: item for item in action_records}
    action_order = {item["action_id"]: index for index, item in enumerate(action_records)}
    actions = sorted(
        (
            Action(
                action_id=source.action_id,
                operation=source.operation,
                targets=tuple(action_extra[source.action_id]["targets"]),
                arguments=tuple(from_expression(item) for item in source.arguments),
                warrant=source.warrant,
                preconditions=tuple(from_expression(item) for item in source.preconditions),
                generated_obligations=tuple(
                    _from_canonical_obligation(item) for item in source.generated_obligations
                ),
                status=Status(action_extra[source.action_id]["status"]),
                evidence_id=action_extra[source.action_id]["evidence_id"],
                attributes=action_extra[source.action_id]["attributes"],
            )
            for source in (*canonical.legal_actions, *canonical.plausible_invalid_actions)
        ),
        key=lambda item: action_order[item.action_id],
    )
    return State(
        state_id=carriers["tl0.state_id"],
        scopes=tuple(
            Scope(scope_id, parent) for scope_id, parent in json.loads(carriers["tl0.scopes"])
        ),
        libraries=tuple(
            LibraryRef(library_id, version)
            for library_id, version in json.loads(carriers["tl0.libraries"])
        ),
        declarations=declarations,
        claims=tuple(item for _, item in claims),
        goals=tuple(
            Goal(
                goal_id=item["goal_id"],
                scope_id=item["scope_id"],
                statement=from_expression(CanonicalExpression.from_dict(item["statement"])),
                status=Status(item["status"]),
                focused=bool(item["focused"]),
                evidence_id=item["evidence_id"],
                attributes=item["attributes"],
            )
            for item in json.loads(carriers["tl0.goals"])
        ),
        obligations=tuple(_from_canonical_obligation(item) for item in canonical.obligations),
        evidence=tuple(
            Evidence(
                evidence_id=node.evidence_id,
                status=Status(node.status),
                verifier=evidence_extra[node.evidence_id]["verifier"],
                verifier_version=evidence_extra[node.evidence_id]["verifier_version"],
                certificate_hash=node.certificate_hash,
                details=evidence_extra[node.evidence_id]["details"],
                depends_on=node.dependencies,
                attributes=evidence_extra[node.evidence_id]["attributes"],
            )
            for node in canonical.evidence_dependencies
        ),
        substitution=tuple(
            (name, from_expression(CanonicalExpression.from_dict(payload)))
            for name, payload in json.loads(carriers["tl0.substitution"])
        ),
        actions=tuple(actions),
        extensions=tuple(
            Extension(owner_id, key, payload)
            for owner_id, key, payload in json.loads(carriers["tl0.extensions"])
        ),
        terminal_status=canonical.terminal_status,
        language_version=carriers["tl0.version"],
    )


def _from_canonical_obligation(
    obligation: CanonicalObligation, *, scope_id: str | None = None
) -> Obligation:
    meta = dict(obligation.proposition.attributes)
    return Obligation(
        obligation_id=obligation.obligation_id,
        scope_id=scope_id or meta.get("tl0.scope_id", ROOT_SCOPE),
        statement=from_expression(obligation.proposition),
        status=Status(obligation.status) if obligation.status in _STATUSES else Status.OPEN,
        source=obligation.source,
        evidence_id=(meta.get("tl0.evidence_id") or None) if scope_id is None else None,
        attributes=json.loads(meta.get("tl0.attributes", "{}")) if scope_id is None else {},
    )


def _safe_id(text: str, prefix: str, index: int) -> str:
    return text if is_identifier(text) else f"{prefix}.{index}"


def _import_foreign(canonical: CanonicalState) -> TL0Import:
    """Best-effort import of a canonical state that TL0 did not produce."""

    recorder = _Recorder(LossPolicy.CARRY)
    recorder.synthesized(
        "scope_forest",
        "the source has a flat state-global scope; one root scope is invented and every "
        "referenced scope id is attached beneath it",
    )
    scope_map: dict[str, str] = {}
    for scope_id in (*canonical.local_scope, *(i.scope_id for i in canonical.bindings)):
        if scope_id not in scope_map:
            scope_map[scope_id] = _safe_id(scope_id, "scope", len(scope_map))
    scopes = (Scope(ROOT_SCOPE, None),) + tuple(
        Scope(value, ROOT_SCOPE) for value in dict.fromkeys(scope_map.values())
    )
    known_scopes = {item.scope_id for item in scopes}

    declarations = tuple(
        Decl(
            decl_id=_safe_id(item.object_id, "obj", index),
            name=item.object_id,
            sort=decode_type(item.type_name),
            scope_id=ROOT_SCOPE,
            kind=DeclKind.OBJECT,
            value=from_expression(item.value) if item.value else None,
            attributes=normalise_attributes(_object_attributes(item)),
        )
        for index, item in enumerate(canonical.objects)
    ) + tuple(
        Decl(
            decl_id=_safe_id(item.binder_id, "bind", index),
            name=item.variable,
            sort=decode_type(item.type_name),
            scope_id=scope_map.get(item.scope_id, ROOT_SCOPE),
            kind=DeclKind(item.binder_kind) if item.binder_kind in _KINDS else DeclKind.FREE,
            attributes=normalise_attributes(
                {} if item.binder_kind in _KINDS else {"canonical.binder_kind": item.binder_kind}
            ),
        )
        for index, item in enumerate(canonical.bindings)
    )
    recorder.synthesized(
        "claim_epistemics",
        "canonical assumption/fact/proposition tuples carry no id or status; ids are indexed "
        "and statuses default to ASSUMED/DERIVED/PROPOSED by bucket",
    )
    claims = tuple(
        Claim(
            claim_id=f"claim.{index}",
            role=role,
            scope_id=ROOT_SCOPE,
            statement=from_expression(expression),
            status=status,
        )
        for index, (expression, role, status) in enumerate(
            [
                *((i, ClaimRole.ASSUMPTION, Status.ASSUMED) for i in canonical.assumptions),
                *((i, ClaimRole.FACT, Status.DERIVED) for i in canonical.established_facts),
                *((i, ClaimRole.PROPOSITION, Status.PROPOSED) for i in canonical.propositions),
            ]
        )
    )
    goals: tuple[Goal, ...] = ()
    if canonical.goal.op != ABSENT_GOAL_OP:
        goals = (
            Goal(
                goal_id="goal.0",
                scope_id=ROOT_SCOPE,
                statement=from_expression(canonical.goal),
                status=Status.OPEN,
                focused=True,
            ),
        )
    recorder.synthesized(
        "verifier_version",
        "canonical EvidenceNode records an authority but no verifier version; imported "
        "evidence is marked 'unrecorded' so that nothing can look VERIFIED on import",
    )
    evidence = tuple(
        Evidence(
            evidence_id=_safe_id(item.evidence_id, "evid", index),
            status=Status(item.status) if item.status in _STATUSES else Status.OPEN,
            verifier=item.authority,
            verifier_version="unrecorded",
            certificate_hash=item.certificate_hash,
            depends_on=(),
        )
        for index, item in enumerate(canonical.evidence_dependencies)
    )
    goal_id = goals[0].goal_id if goals else None
    declared = {item.decl_id for item in declarations}
    sources = (*canonical.legal_actions, *canonical.plausible_invalid_actions)
    refuted = (False,) * len(canonical.legal_actions) + (True,) * len(
        canonical.plausible_invalid_actions
    )
    actions = tuple(
        Action(
            action_id=_safe_id(item.action_id, "act", index),
            operation=item.operation,
            targets=tuple(_map_target(target, declared, goal_id) for target in item.target_ids),
            arguments=tuple(from_expression(argument) for argument in item.arguments),
            warrant=item.warrant,
            preconditions=tuple(from_expression(pre) for pre in item.preconditions),
            generated_obligations=tuple(
                _from_canonical_obligation(obligation, scope_id=ROOT_SCOPE)
                for obligation in item.generated_obligations
            ),
            status=Status.REFUTED if flag else Status.PROPOSED,
        )
        for index, (item, flag) in enumerate(zip(sources, refuted, strict=True))
    )
    extensions = tuple(
        Extension(action.action_id, USEFULNESS_KEY, repr(source.expected_usefulness))
        for action, source in zip(actions, sources, strict=True)
    )
    obligations = tuple(
        _from_canonical_obligation(
            item,
            scope_id=(
                None
                if dict(item.proposition.attributes).get("tl0.scope_id") in known_scopes
                else ROOT_SCOPE
            ),
        )
        for item in canonical.obligations
    )
    state = State(
        state_id=canonical.state_id,
        scopes=scopes,
        declarations=declarations,
        claims=claims,
        goals=goals,
        obligations=obligations,
        evidence=evidence,
        actions=actions,
        extensions=extensions,
        terminal_status=canonical.terminal_status,
    )
    return TL0Import(state, recorder.report())


def _map_target(target: str, declared: set[str], goal_id: str | None) -> str:
    if target in declared:
        return target
    if target == "goal" and goal_id is not None:
        return goal_id
    return goal_id or ROOT_SCOPE


def _object_attributes(item: MathObject) -> dict[str, str]:
    attributes: dict[str, str] = {}
    if item.shape:
        attributes["canonical.shape"] = canonical_json(list(item.shape))
    if item.unit is not None:
        attributes["canonical.unit"] = item.unit
    return attributes


__all__ = [
    "ABSENT_GOAL_OP",
    "CARRIER_VERSION",
    "ROOT_SCOPE",
    "USEFULNESS_KEY",
    "CanonicalMapping",
    "CanonicalMappingError",
    "CompatibilityProfile",
    "LossItem",
    "LossKind",
    "LossPolicy",
    "LossReport",
    "TL0Import",
    "decode_type",
    "encode_type",
    "from_canonical",
    "from_expression",
    "to_canonical",
    "to_expression",
]
