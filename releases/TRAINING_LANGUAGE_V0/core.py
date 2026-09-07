"""TL0 core object model.

The core is deliberately small.  Ten record kinds carry every structure the Arena's
canonical substrate names -- terms, types, propositions, definitions, assumptions, facts,
goals, variables, identities, binders, scope, dependencies, obligations, evidence and
state -- and *nothing else is grammar*.  Domain vocabulary (algebra, number theory,
analysis, ...) is added as :class:`Library` **data**, never as new record kinds.

Three of the measured REQUIRED gaps in ``docs/CANONICAL_VNEXT_PILOT.md`` are native here
rather than carried:

* **multi-goal with per-goal context** -- :class:`State` holds a tuple of :class:`Goal`,
  each naming a :class:`Scope`; scopes form a forest, so two goals may sit in genuinely
  different contexts.
* **obligation scope (N4)** -- :class:`Obligation` carries ``scope_id`` directly.
* **structured types (G3)** -- :class:`Type` is a head plus parameters, not a flat string.
* **let-bound values (N2)** -- :class:`Decl` carries an optional ``value`` term.
* **metavariables / substitution (G2 == G6)** -- one structure: ``METAVAR`` declarations
  plus :attr:`State.substitution`.

Anything a *consumer* schema cannot express is carried in an explicit :class:`Extension`
record rather than dropped; see :mod:`canonical_adapter`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

LANGUAGE_ID = "TL0"
LANGUAGE_VERSION = "0.1.0"
DOCUMENT_MAGIC = "TL0"

#: The release's evidence level.  This package is packaging and interfaces; it is not a
#: tournament result and must never be labelled as one.
EVIDENCE_LEVEL = "TRAINING_LANGUAGE_V0_BASELINE"

Value = str | int | float | bool
Attributes = tuple[tuple[str, str], ...]

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-/]*$")

#: Attribute keys under this prefix are reserved for the canonical boundary carriers in
#: :mod:`canonical_adapter`.  Reserving them is what makes carrying lossless: a TL0
#: attribute can never collide with a carrier and be silently overwritten.
RESERVED_ATTRIBUTE_PREFIX = "tl0."


class TL0Error(ValueError):
    """Any TL0 structural violation.  All TL0 failures are subclasses of this."""


class StatusError(TL0Error):
    """An epistemic-status rule was violated.  See :class:`Status`."""


def is_identifier(value: str) -> bool:
    """True when ``value`` may be spelled as a bare TL0 identifier."""

    return isinstance(value, str) and bool(_ID_RE.match(value))


def _check_id(value: str, what: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise TL0Error(f"{what} must be a bare identifier, got {value!r}")
    return value


def _check_name(value: str, what: str) -> str:
    """Labels need only be non-empty text: the renderer quotes anything not atom-shaped."""

    if not isinstance(value, str) or not value:
        raise TL0Error(f"{what} must be non-empty text, got {value!r}")
    return value


def normalise_attributes(
    value: Mapping[str, str] | Sequence[tuple[str, str]] | None,
) -> Attributes:
    """Return attributes in the one spelling TL0 ever emits: sorted, deduplicated pairs.

    Sorting here is what makes the renderer independent of dict insertion order.
    """

    if value is None:
        return ()
    items: Sequence[tuple[str, str]]
    items = tuple(value.items()) if isinstance(value, Mapping) else tuple(value)
    pairs = tuple(sorted((str(key), str(item)) for key, item in items))
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise TL0Error("duplicate attribute key")
    for key in keys:
        if not key:
            raise TL0Error("attribute key must be non-empty")
        if key.startswith(RESERVED_ATTRIBUTE_PREFIX):
            raise TL0Error(
                f"attribute key {key!r} uses the reserved {RESERVED_ATTRIBUTE_PREFIX!r} "
                "namespace, which belongs to the canonical boundary carriers"
            )
    return pairs


def check_value(value: Value | None) -> Value | None:
    """Reject scalars TL0 cannot render round-trippably (NaN, infinities)."""

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise TL0Error("term value must be a finite number")
        return value
    raise TL0Error(f"term value must be a JSON scalar, got {type(value).__name__}")


class Status(StrEnum):
    """The six epistemic states an annotation may carry.

    ``VERIFIED`` is the only privileged one: it is *not representable* without a named
    verifier and a verification record.  The rule is enforced twice -- once when the
    annotation is constructed (it must name an ``evidence_id``) and once when a
    :class:`State` is assembled (that id must resolve to a ``VERIFIED`` :class:`Evidence`
    node carrying a verifier name and version).  Both raise :class:`StatusError`.
    """

    ASSUMED = "ASSUMED"
    PROPOSED = "PROPOSED"
    DERIVED = "DERIVED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    OPEN = "OPEN"


class DeclKind(StrEnum):
    """What a declaration *is*.  One record covers every naming construct in the core."""

    OBJECT = "object"
    FREE = "free"
    FORALL = "forall"
    EXISTS = "exists"
    LAMBDA = "lambda"
    LET = "let"
    IMPLICIT = "implicit"
    INSTANCE = "instance"
    METAVAR = "metavar"
    DEFINITION = "definition"


class ClaimRole(StrEnum):
    """Why a proposition is present.  Roles are data; they add no grammar."""

    ASSUMPTION = "assumption"
    FACT = "fact"
    PROPOSITION = "proposition"
    DEFINITION = "definition"
    IDENTITY = "identity"


@dataclass(frozen=True, slots=True)
class Type:
    """A structured type: a head symbol plus type parameters.

    This is the G3 fix.  ``Binding.type_name`` in the canonical substrate is a flat
    string; 84.6% of real Lean context entries carry compound types.  Here
    ``[Fun [Nat] [Prop]]`` is a tree, and the flat-string encoding used at the canonical
    boundary is injective and reversible rather than lossy (see :mod:`canonical_adapter`).
    """

    head: str
    params: tuple[Type, ...] = ()

    def __post_init__(self) -> None:
        _check_name(self.head, "type head")
        if not isinstance(self.params, tuple):
            raise TL0Error("type params must be a tuple")


UNKNOWN_TYPE = Type("Unknown")
PROP_TYPE = Type("Prop")


@dataclass(frozen=True, slots=True)
class Term:
    """The single expression node.  Terms, propositions and identities are all Terms."""

    op: str
    sort: Type = UNKNOWN_TYPE
    value: Value | None = None
    args: tuple[Term, ...] = ()
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_name(self.op, "term op")
        if not isinstance(self.args, tuple):
            raise TL0Error("term args must be a tuple")
        object.__setattr__(self, "value", check_value(self.value))
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))

    def walk(self) -> Iterator[Term]:
        """Pre-order traversal.  Used by library validation and the human renderer."""

        yield self
        for child in self.args:
            yield from child.walk()


@dataclass(frozen=True, slots=True)
class Scope:
    """A node in the context forest.  ``parent_id`` is ``None`` for a root scope."""

    scope_id: str
    parent_id: str | None = None

    def __post_init__(self) -> None:
        _check_id(self.scope_id, "scope_id")
        if self.parent_id is not None:
            _check_id(self.parent_id, "scope parent_id")
        if self.parent_id == self.scope_id:
            raise TL0Error(f"scope {self.scope_id} cannot be its own parent")


@dataclass(frozen=True, slots=True)
class Decl:
    """A declaration: object, variable, binder, definition, let-value or metavariable.

    Collapsing all of these into one record is the main reason the core stays small.
    ``value`` is the N2 fix (let-bound locals carry a definition).
    """

    decl_id: str
    name: str
    sort: Type
    scope_id: str
    kind: DeclKind = DeclKind.FREE
    value: Term | None = None
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_id(self.decl_id, "decl_id")
        _check_name(self.name, "decl name")
        _check_id(self.scope_id, "decl scope_id")
        object.__setattr__(self, "kind", DeclKind(self.kind))
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))


def _check_status_evidence(status: Status, evidence_id: str | None, what: str) -> None:
    if status is Status.VERIFIED and not evidence_id:
        raise StatusError(
            f"{what} cannot be VERIFIED without a verification record: "
            "set evidence_id to a VERIFIED evidence node naming its verifier"
        )
    if evidence_id is not None:
        _check_id(evidence_id, f"{what} evidence_id")


@dataclass(frozen=True, slots=True)
class Claim:
    """An annotation over a proposition: assumption, fact, proposition, definition, identity."""

    claim_id: str
    role: ClaimRole
    scope_id: str
    statement: Term
    status: Status = Status.PROPOSED
    evidence_id: str | None = None
    depends_on: tuple[str, ...] = ()
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_id(self.claim_id, "claim_id")
        _check_id(self.scope_id, "claim scope_id")
        object.__setattr__(self, "role", ClaimRole(self.role))
        object.__setattr__(self, "status", Status(self.status))
        _check_status_evidence(self.status, self.evidence_id, f"claim {self.claim_id}")
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class Goal:
    """One goal, in one scope.  A state may hold zero, one or many.

    This plus :class:`Scope` is the G1 + N1 + N4 fix: the canonical substrate has exactly
    one mandatory goal and state-global bindings, which made 17.4% of measured Lean states
    (zero goals) unmappable and lost the per-goal context of the multi-goal ones.
    """

    goal_id: str
    scope_id: str
    statement: Term
    status: Status = Status.OPEN
    focused: bool = False
    evidence_id: str | None = None
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_id(self.goal_id, "goal_id")
        _check_id(self.scope_id, "goal scope_id")
        object.__setattr__(self, "status", Status(self.status))
        object.__setattr__(self, "focused", bool(self.focused))
        _check_status_evidence(self.status, self.evidence_id, f"goal {self.goal_id}")
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class Obligation:
    """A proof obligation, scoped.  ``scope_id`` is the N4 fix."""

    obligation_id: str
    scope_id: str
    statement: Term
    status: Status = Status.OPEN
    source: str = "core"
    evidence_id: str | None = None
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_id(self.obligation_id, "obligation_id")
        _check_id(self.scope_id, "obligation scope_id")
        _check_name(self.source, "obligation source")
        object.__setattr__(self, "status", Status(self.status))
        _check_status_evidence(self.status, self.evidence_id, f"obligation {self.obligation_id}")
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class Evidence:
    """A verification record.  Nothing else may license ``Status.VERIFIED``."""

    evidence_id: str
    status: Status
    verifier: str = ""
    verifier_version: str = ""
    certificate_hash: str | None = None
    details: str = ""
    depends_on: tuple[str, ...] = ()
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_id(self.evidence_id, "evidence_id")
        object.__setattr__(self, "status", Status(self.status))
        if self.status is Status.VERIFIED and not (self.verifier and self.verifier_version):
            raise StatusError(
                f"evidence {self.evidence_id} cannot be VERIFIED without a named "
                "verifier and verifier_version"
            )
        if self.verifier:
            _check_name(self.verifier, "verifier")
        if self.verifier_version:
            _check_name(self.verifier_version, "verifier_version")
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class Action:
    """A reasoning step proposal: operation, target, arguments, warrant, preconditions,
    generated obligations and its own verification status."""

    action_id: str
    operation: str
    targets: tuple[str, ...] = ()
    arguments: tuple[Term, ...] = ()
    warrant: str = ""
    preconditions: tuple[Term, ...] = ()
    generated_obligations: tuple[Obligation, ...] = ()
    status: Status = Status.PROPOSED
    evidence_id: str | None = None
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        _check_id(self.action_id, "action_id")
        _check_name(self.operation, "action operation")
        object.__setattr__(self, "status", Status(self.status))
        _check_status_evidence(self.status, self.evidence_id, f"action {self.action_id}")
        object.__setattr__(self, "attributes", normalise_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class Extension:
    """An explicit lossless carrier for anything the core does not model natively.

    Extensions are *visible in the rendered text*.  That is the point: a consumer that
    cannot interpret ``owner``/``key`` still sees that something was carried rather than
    silently dropped.
    """

    owner_id: str
    key: str
    payload: str

    def __post_init__(self) -> None:
        _check_id(self.owner_id, "extension owner_id")
        _check_name(self.key, "extension key")
        if not isinstance(self.payload, str):
            raise TL0Error("extension payload must be text")


@dataclass(frozen=True, slots=True)
class LibraryRef:
    """A domain library in force for this state.  Vocabulary, never grammar."""

    library_id: str
    version: str

    def __post_init__(self) -> None:
        _check_id(self.library_id, "library_id")
        _check_name(self.version, "library version")


def _require_unique(values: Sequence[str], what: str) -> None:
    if len(values) != len(set(values)):
        duplicates = sorted({item for item in values if values.count(item) > 1})
        raise TL0Error(f"duplicate {what}: {duplicates}")


@dataclass(frozen=True, slots=True)
class State:
    """A complete TL0 state.  Fail-closed: an invalid state cannot be constructed."""

    state_id: str
    scopes: tuple[Scope, ...] = ()
    libraries: tuple[LibraryRef, ...] = ()
    declarations: tuple[Decl, ...] = ()
    claims: tuple[Claim, ...] = ()
    goals: tuple[Goal, ...] = ()
    obligations: tuple[Obligation, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    substitution: tuple[tuple[str, Term], ...] = ()
    actions: tuple[Action, ...] = ()
    extensions: tuple[Extension, ...] = ()
    terminal_status: str = "OPEN"
    language_version: str = LANGUAGE_VERSION

    def __post_init__(self) -> None:
        _check_id(self.state_id, "state_id")
        _check_name(self.terminal_status, "terminal_status")
        if self.language_version != LANGUAGE_VERSION:
            raise TL0Error(f"unsupported TL0 version {self.language_version!r}")
        self._validate_scopes()
        self._validate_identity()
        self._validate_references()
        self._validate_statuses()
        self._validate_substitution()

    # -- validation ----------------------------------------------------------------

    def _validate_scopes(self) -> None:
        ids = [item.scope_id for item in self.scopes]
        _require_unique(ids, "scope_id")
        known = set(ids)
        for scope in self.scopes:
            if scope.parent_id is not None and scope.parent_id not in known:
                raise TL0Error(f"scope {scope.scope_id} names unknown parent {scope.parent_id}")
        parents = {item.scope_id: item.parent_id for item in self.scopes}
        for scope_id in ids:
            seen: set[str] = set()
            cursor: str | None = scope_id
            while cursor is not None:
                if cursor in seen:
                    raise TL0Error(f"scope cycle through {scope_id}")
                seen.add(cursor)
                cursor = parents[cursor]

    def _validate_identity(self) -> None:
        declared = (
            [item.decl_id for item in self.declarations]
            + [item.claim_id for item in self.claims]
            + [item.goal_id for item in self.goals]
            + [item.obligation_id for item in self.obligations]
            + [item.evidence_id for item in self.evidence]
            + [item.action_id for item in self.actions]
        )
        _require_unique(declared, "record id")
        _require_unique([item.library_id for item in self.libraries], "library_id")

    def _validate_references(self) -> None:
        scopes = {item.scope_id for item in self.scopes}
        scoped: tuple[tuple[str, str], ...] = (
            *((item.decl_id, item.scope_id) for item in self.declarations),
            *((item.claim_id, item.scope_id) for item in self.claims),
            *((item.goal_id, item.scope_id) for item in self.goals),
            *((item.obligation_id, item.scope_id) for item in self.obligations),
        )
        for owner, scope_id in scoped:
            if scope_id not in scopes:
                raise TL0Error(f"{owner} names unknown scope {scope_id}")
        for action in self.actions:
            for obligation in action.generated_obligations:
                if obligation.scope_id not in scopes:
                    raise TL0Error(
                        f"action {action.action_id} generates an obligation in unknown "
                        f"scope {obligation.scope_id}"
                    )
        known = self.known_ids()
        for owner, references in self._dependency_edges():
            for reference in references:
                if reference not in known:
                    raise TL0Error(f"{owner} depends on unknown id {reference}")
        for extension in self.extensions:
            if extension.owner_id not in known and extension.owner_id != self.state_id:
                raise TL0Error(f"extension names unknown owner {extension.owner_id}")

    def _dependency_edges(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return (
            *((item.claim_id, item.depends_on) for item in self.claims),
            *((item.evidence_id, item.depends_on) for item in self.evidence),
            *((item.action_id, item.targets) for item in self.actions),
        )

    def _validate_statuses(self) -> None:
        records = {item.evidence_id: item for item in self.evidence}
        holders: tuple[tuple[str, Status, str | None], ...] = (
            *((item.claim_id, item.status, item.evidence_id) for item in self.claims),
            *((item.goal_id, item.status, item.evidence_id) for item in self.goals),
            *((item.obligation_id, item.status, item.evidence_id) for item in self.obligations),
            *((item.action_id, item.status, item.evidence_id) for item in self.actions),
            *(
                (obligation.obligation_id, obligation.status, obligation.evidence_id)
                for action in self.actions
                for obligation in action.generated_obligations
            ),
        )
        for owner, status, evidence_id in holders:
            if evidence_id is not None and evidence_id not in records:
                raise TL0Error(f"{owner} names unknown evidence {evidence_id}")
            if status is not Status.VERIFIED:
                continue
            record = records[str(evidence_id)]
            if record.status is not Status.VERIFIED:
                raise StatusError(
                    f"{owner} is VERIFIED but evidence {record.evidence_id} is "
                    f"{record.status.value}"
                )
            if not (record.verifier and record.verifier_version):
                raise StatusError(
                    f"{owner} is VERIFIED but evidence {record.evidence_id} names no verifier"
                )

    def _validate_substitution(self) -> None:
        metavars = {item.decl_id for item in self.declarations if item.kind is DeclKind.METAVAR}
        seen: set[str] = set()
        for name, _ in self.substitution:
            if name in seen:
                raise TL0Error(f"duplicate substitution for {name}")
            seen.add(name)
            if name not in metavars:
                raise TL0Error(f"substitution names undeclared metavariable {name}")

    # -- accessors -----------------------------------------------------------------

    def known_ids(self) -> frozenset[str]:
        return frozenset(
            [item.scope_id for item in self.scopes]
            + [item.decl_id for item in self.declarations]
            + [item.claim_id for item in self.claims]
            + [item.goal_id for item in self.goals]
            + [item.obligation_id for item in self.obligations]
            + [item.evidence_id for item in self.evidence]
            + [item.action_id for item in self.actions]
        )

    @property
    def focus_goal(self) -> Goal | None:
        """The focused goal, the first goal, or ``None`` when the state has no goal."""

        for goal in self.goals:
            if goal.focused:
                return goal
        return self.goals[0] if self.goals else None

    def scope_chain(self, scope_id: str) -> tuple[str, ...]:
        """Root-to-leaf scope path.  This is a goal's *context*."""

        parents = {item.scope_id: item.parent_id for item in self.scopes}
        if scope_id not in parents:
            raise TL0Error(f"unknown scope {scope_id}")
        chain: list[str] = []
        cursor: str | None = scope_id
        while cursor is not None:
            chain.append(cursor)
            cursor = parents[cursor]
        return tuple(reversed(chain))

    def declarations_in_scope(self, scope_id: str) -> tuple[Decl, ...]:
        """Declarations visible from ``scope_id``, i.e. its per-goal context."""

        chain = set(self.scope_chain(scope_id))
        return tuple(item for item in self.declarations if item.scope_id in chain)

    def with_extension(self, owner_id: str, key: str, payload: str) -> State:
        return replace(self, extensions=(*self.extensions, Extension(owner_id, key, payload)))


__all__ = [
    "DOCUMENT_MAGIC",
    "RESERVED_ATTRIBUTE_PREFIX",
    "EVIDENCE_LEVEL",
    "LANGUAGE_ID",
    "LANGUAGE_VERSION",
    "PROP_TYPE",
    "UNKNOWN_TYPE",
    "Action",
    "Attributes",
    "Claim",
    "ClaimRole",
    "Decl",
    "DeclKind",
    "Evidence",
    "Extension",
    "Goal",
    "LibraryRef",
    "Obligation",
    "Scope",
    "State",
    "Status",
    "StatusError",
    "TL0Error",
    "Term",
    "Type",
    "Value",
    "check_value",
    "is_identifier",
    "normalise_attributes",
]
