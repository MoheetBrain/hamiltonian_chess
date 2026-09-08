"""Two state identities the project has historically conflated, separated and made explicit.

``docs/LEAN_BACKEND_STATE_IDENTITY_V0.md`` is the prose companion; this module is the mechanism.

The measurement that forces this design: ``docs/CANONICAL_VNEXT_PILOT.md`` mapped **0 of 368**
real Lean states losslessly into ``arena-canonical-v0.1.0``, and raw pretty-printed state equality
scored **40.6%** where real semantic agreement was **98.1%** (``univ`` under ``open Finset`` versus
``Finset.univ`` without it).  So there is no canonical form to identify states by, *and* the
rendered text is not an identity either.  Manual §17.4 permits backend-native truth; this module
takes that permission and states precisely what it buys.

Two different questions were previously asked with one object:

:class:`KernelStateIdentity`
    *Which actual backend state is this?*  Grounded in the elaboration session, the backend's own
    state handle, and a normalised digest of the goal together with the scope it was rendered
    under.  It is the identity a verifier, a branch operation or a replay cares about.

:class:`WorkspaceProjectionIdentity`
    *Which declared information was exposed to the candidate language?*  Two ``R_ONLY`` languages
    render different bytes and MUST produce the same value here (manual §12.3, §26.2); a
    ``P_CHANGE``/``O_CHANGE``/``A_CHANGE`` language may legitimately produce a different one, and
    the :class:`~arena.evolution.record.InterventionClass` it declares says which is expected.

Neither is a semantic decision procedure and neither claims to be.  Only Lean decides whether two
states are the same mathematics, and nothing here asks it to.  LOSSLESS_FIRST, ABSTRACT_LATER: no
field is invented that the Lean backend cannot supply faithfully.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable

from arena.canonical.schema import canonical_json, stable_hash
from arena.evolution.record import InterventionClass
from arena.trajectory.schema import BackendStateEnvelope, PPScope

#: Name of the goal-text normalisation applied before digesting.  Recorded in every identity so a
#: future change of normalisation is visible as a different identity rather than a silent drift.
GOAL_TEXT_NORMALIZATION = "goal-text-nfc-linewise-rstrip-v0"

#: Identity schema version.  Distinct from ``arena-canonical-v0.1.0`` on purpose.
STATE_IDENTITY_SCHEMA_VERSION = "arena-backend-state-identity-v0"

#: Default workspace kind for the Lean tactic arena.
LEAN_TACTIC_WORKSPACE = "LEAN4_TACTIC_WORKSPACE_V0"


def normalize_goal_text(text: str) -> str:
    """Normalise rendered goal text before digesting it.

    Exactly four transformations, all of them presentational, none of them mathematical:

    1. Unicode NFC, so ``⊢`` composed two different ways is one character;
    2. ``\\r\\n`` and ``\\r`` collapse to ``\\n``;
    3. trailing whitespace is stripped from each line;
    4. leading and trailing blank lines are dropped.

    It does **not** reorder hypotheses, alpha-rename binders, unfold notation, resolve namespaces,
    or normalise the scope-dependent spelling of a name.  Anything more would be a claim about
    Lean's semantics that this project cannot support (0/368 lossless canonicalisation).
    """

    unified = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _scope_payload(scope: PPScope) -> dict[str, Any]:
    """Canonical, order-insensitive form of an elaboration scope."""

    return {
        "current_namespace": scope.current_namespace,
        "open_declarations": sorted(scope.open_declarations),
        "options": sorted([list(pair) for pair in scope.options]),
    }


def goal_digest_of(text: str, scope: PPScope) -> tuple[str, str]:
    """Return ``(goal_digest, scope_digest)`` for a rendered goal under a scope.

    The two are kept apart so a reader can see whether two states differ in their mathematics
    or only in the scope they were printed under -- the distinction the 40.6% / 98.1% measurement
    is about.
    """

    scope_digest = stable_hash(_scope_payload(scope))
    goal = stable_hash(
        {
            "normalization": GOAL_TEXT_NORMALIZATION,
            "goal": normalize_goal_text(text),
        }
    )
    return goal, scope_digest


# =============================================================================================
# KernelStateIdentity
# =============================================================================================


@dataclass(frozen=True, slots=True)
class BackendSessionRef:
    """One elaboration session of one formal backend.

    A backend state handle (Lean's ``sid``) is only meaningful *inside* the session that issued
    it: ``sid=3`` in one session and ``sid=3`` in another name different live states and cannot be
    branched between.  Carrying the session explicitly is what stops two episodes' handles from
    being silently equated.
    """

    backend_kind: str = "LEAN4_TACTIC_STATE_PP"
    session_kind: str = "LEAN4_DOJO_REPL"
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_kind": self.backend_kind,
            "session_kind": self.session_kind,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            backend_kind=str(payload.get("backend_kind", "LEAN4_TACTIC_STATE_PP")),
            session_kind=str(payload.get("session_kind", "LEAN4_DOJO_REPL")),
            session_id=str(payload.get("session_id", "")),
        )


@dataclass(frozen=True, slots=True)
class KernelStateIdentity:
    """Identity of the actual backend/mathematical state.

    **What it guarantees.**

    * :attr:`kernel_key` -- ``(backend_kind, session_id, state_id)``.  Two identities with equal
      kernel keys name the *same saved backend state*: the backend itself says so, the state can
      be re-entered with ``branch()``, and this holds **whatever the goal was rendered as**.  It
      is therefore independent of pretty-printing scope, of ``pp`` options, and of any renderer.
    * :attr:`reelaboration_key` -- ``(backend_kind, scope_digest, goal_digest)``.  Stable across
      re-elaboration: a fresh session that re-elaborates the same declaration and replays the same
      actions reaches an identity with the *same* re-elaboration key even though the session id
      and the ``sid`` are new.  This is the key a bank, a cache or a determinism check uses.
    * :attr:`identity_hash` -- a deterministic digest of both keys plus the normalisation name.
      Suitable as a dictionary key and as a provenance stamp.

    **What it does not guarantee.**

    * It is **not** a semantic equality decision procedure.  Two states that are the same
      mathematics but printed under different scopes (``univ`` vs ``Finset.univ``) have different
      re-elaboration keys.  A ``False`` from :meth:`same_after_reelaboration_as` means *unknown*,
      never *different mathematics*.  Only Lean can decide that, and this module never asks it to.
    * It is **not** raw string comparison.  The digest is taken over normalised text (NFC,
      line-wise right-strip, blank-line trim) bound to the scope it was rendered under, so
      identity survives presentational noise that byte equality would reject.  The normalisation
      is deliberately shallow and named in the identity itself.
    * A kernel key from one session says nothing at all about a state in another session.  It is
      not comparable across sessions and :meth:`same_kernel_state_as` will report ``False``.
    * It carries no canonical form.  ``arena-canonical-v0.1.0`` maps 0 of 368 real Lean states
      losslessly, so there is nothing to carry.
    """

    backend_kind: str
    session_id: str
    state_id: str
    goal_digest: str
    scope_digest: str
    #: The *record* session binding the envelope itself carries, when it carries one
    #: (``BackendStateEnvelope.session_id``, a content-addressed function of the session's opening
    #: conditions -- see ``arena.trajectory.arena_v0.derive_session_id``).  It answers a different
    #: question from :attr:`session_id`: "which stored episode does this state belong to", not
    #: "which live session can I branch in".  Two *different* live episodes of the same theorem
    #: under the same policy and seed share a record session id and do **not** share a live one,
    #: which is why the two are carried side by side and only the live one is in
    #: :attr:`kernel_key`.  Empty when the backend record carries no binding.
    record_session_id: str = ""
    normalization: str = GOAL_TEXT_NORMALIZATION
    schema_version: str = STATE_IDENTITY_SCHEMA_VERSION

    # -- construction --------------------------------------------------------------

    @classmethod
    def from_envelope(
        cls, envelope: BackendStateEnvelope, *, session: BackendSessionRef
    ) -> KernelStateIdentity:
        """Build the identity of the state the backend just handed out.

        ``session`` is the **live** session -- the one whose handles can still be branched to.
        The envelope's own record binding, if it has one, is carried alongside rather than
        substituted for it; ``getattr`` because that field is owned by ``schema.py`` and its
        absence must degrade to "no binding recorded" rather than to an import-time failure.
        """

        goal, scope = goal_digest_of(envelope.pp, envelope.pp_scope)
        return cls(
            backend_kind=envelope.backend_kind,
            session_id=session.session_id,
            state_id=envelope.state_id,
            goal_digest=goal,
            scope_digest=scope,
            record_session_id=str(getattr(envelope, "session_id", "") or ""),
        )

    def rendered_under(self, goal_text: str, scope: PPScope) -> KernelStateIdentity:
        """The same backend state, re-rendered.

        Used to state the guarantee mechanically: changing how a state is printed changes the
        re-elaboration key and leaves the kernel key untouched.
        """

        goal, scope_digest = goal_digest_of(goal_text, scope)
        return KernelStateIdentity(
            backend_kind=self.backend_kind,
            session_id=self.session_id,
            state_id=self.state_id,
            goal_digest=goal,
            scope_digest=scope_digest,
            record_session_id=self.record_session_id,
            normalization=self.normalization,
            schema_version=self.schema_version,
        )

    # -- keys ----------------------------------------------------------------------

    @property
    def kernel_key(self) -> str:
        """Session-scoped, scope-independent, authoritative."""

        return f"{self.backend_kind}|{self.session_id}|{self.state_id}"

    @property
    def reelaboration_key(self) -> str:
        """Session-independent, scope-dependent, sufficient-but-not-necessary."""

        return f"{self.backend_kind}|{self.scope_digest[:16]}|{self.goal_digest}"

    @property
    def record_key(self) -> str:
        """The stored-episode binding, for cross-referencing a ``VerifiedTrajectory``.

        Not the live handle: two different episodes of the same theorem under the same policy and
        seed share this key and cannot be branched between.  Use :attr:`kernel_key` for that.
        """

        return f"{self.backend_kind}|{self.record_session_id}|{self.state_id}"

    @property
    def identity_hash(self) -> str:
        return stable_hash(
            {
                "schema": self.schema_version,
                "kernel_key": self.kernel_key,
                "record_key": self.record_key,
                "reelaboration_key": self.reelaboration_key,
                "normalization": self.normalization,
            }
        )

    # -- comparisons ---------------------------------------------------------------

    def same_kernel_state_as(self, other: KernelStateIdentity) -> bool:
        """``True`` iff the backend says these are the same saved state in the same session."""

        return self.kernel_key == other.kernel_key

    def same_after_reelaboration_as(self, other: KernelStateIdentity) -> bool:
        """``True`` iff the same goal was rendered under the same scope.

        Sufficient for "same state", **not** necessary: ``False`` means *unknown*.
        """

        return self.reelaboration_key == other.reelaboration_key

    # -- serialization -------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "backend_kind": self.backend_kind,
            "session_id": self.session_id,
            "state_id": self.state_id,
            "goal_digest": self.goal_digest,
            "scope_digest": self.scope_digest,
            "record_session_id": self.record_session_id,
            "normalization": self.normalization,
            "kernel_key": self.kernel_key,
            "record_key": self.record_key,
            "reelaboration_key": self.reelaboration_key,
            "identity_hash": self.identity_hash,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            backend_kind=str(payload["backend_kind"]),
            session_id=str(payload["session_id"]),
            state_id=str(payload["state_id"]),
            goal_digest=str(payload["goal_digest"]),
            scope_digest=str(payload["scope_digest"]),
            record_session_id=str(payload.get("record_session_id", "")),
            normalization=str(payload.get("normalization", GOAL_TEXT_NORMALIZATION)),
            schema_version=str(payload.get("schema", STATE_IDENTITY_SCHEMA_VERSION)),
        )


# =============================================================================================
# WorkspaceProjectionIdentity
# =============================================================================================


class InformationSlot(StrEnum):
    """The declared information a Lean tactic workspace may expose.

    A *slot* is a semantic position, not a key name: two languages that both expose the goal call
    the slot :attr:`GOAL_TEXT` however they spell it in their own output.  That is what lets an
    ``R_ONLY`` pair agree on identity while disagreeing on every byte.
    """

    GOAL_TEXT = "GOAL_TEXT"
    GOAL_COUNT = "GOAL_COUNT"
    BACKEND_KIND = "BACKEND_KIND"
    BACKEND_STATE_ID = "BACKEND_STATE_ID"
    PP_SCOPE = "PP_SCOPE"
    STEP_INDEX = "STEP_INDEX"
    ATTEMPTS_REMAINING = "ATTEMPTS_REMAINING"
    TERMINAL_STATUS = "TERMINAL_STATUS"
    LAST_DIAGNOSTIC = "LAST_DIAGNOSTIC"


#: Prefix for a key a renderer emitted that maps to no declared slot.  Nothing is dropped
#: silently: an undeclared key becomes its own opaque slot and therefore changes the identity.
UNDECLARED_SLOT_PREFIX = "UNDECLARED:"

#: Keys the default derivation treats as carrying no information of their own: the renderer's name
#: and a digest that is a function of a value already in another slot.
_NON_INFORMATIONAL_KEYS = frozenset({"renderer_id", "pp_sha256"})

#: How the default derivation reads a rendered payload produced by the arena's own renderers.
_DEFAULT_KEY_TO_SLOT: dict[str, InformationSlot] = {
    "goals_pp": InformationSlot.GOAL_TEXT,
    "n_goals": InformationSlot.GOAL_COUNT,
    "backend_kind": InformationSlot.BACKEND_KIND,
    "state_id": InformationSlot.BACKEND_STATE_ID,
    "pp_scope": InformationSlot.PP_SCOPE,
    "step_index": InformationSlot.STEP_INDEX,
    "attempts_remaining": InformationSlot.ATTEMPTS_REMAINING,
    "terminal_status": InformationSlot.TERMINAL_STATUS,
}

_TEXT_SLOTS = frozenset({InformationSlot.GOAL_TEXT, InformationSlot.LAST_DIAGNOSTIC})


def canonicalise_slot_value(slot: str, value: Any) -> Any:
    """Canonical form of one slot's value, so equal information hashes equally."""

    if slot in _TEXT_SLOTS:
        return normalize_goal_text(str(value))
    if isinstance(value, PPScope):
        return _scope_payload(value)
    if isinstance(value, Mapping):
        return {str(key): canonicalise_slot_value("", item) for key, item in sorted(value.items())}
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, tuple | list):
        return [canonicalise_slot_value("", item) for item in value]
    return str(value)


@runtime_checkable
class InformationDeclaringRenderer(Protocol):
    """A renderer that declares *what* it shows, separately from *how* it shows it.

    A renderer that implements this protocol can be compared for ``R_ONLY`` parity.  One that does
    not gets a conservative identity derived from its output keys, which will differ as soon as it
    renames a key -- correct, because without a declaration there is no evidence the information
    is the same.
    """

    @property
    def renderer_id(self) -> str: ...

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]: ...

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class WorkspaceProjectionIdentity:
    """Identity of the declared information exposed to one candidate language.

    **What it guarantees.**

    * :attr:`projection_hash` is a function of the workspace kind, the set of exposed slots and
      the canonicalised value in each slot -- and of **nothing else**.  ``renderer_id`` and
      :attr:`rendered_bytes_digest` are recorded for provenance and are *excluded* from it, which
      is exactly what makes two ``R_ONLY`` renderings compare equal while their bytes differ.
    * Undeclared output keys are folded in under :data:`UNDECLARED_SLOT_PREFIX`, so a renderer
      cannot smuggle extra information past the identity by inventing a key name.
    * It is deterministic and order-insensitive: slot order in the source mapping never matters.

    **What it does not guarantee.**

    * It is not evidence that two languages are *equally usable*; it says the same declared
      information was available, which is manual §12.3's parity precondition and no more.
    * It is only as good as the renderer's declaration.  A renderer that mislabels a slot produces
      a false parity.  The declaration is a **claim by the language**, checkable against the
      rendered bytes by a reader but not proved here.
    * Equal projection hashes with different :attr:`rendered_bytes_digest` values are the
      *expected* shape of an ``R_ONLY`` pair; equal bytes are not required and never asserted.
    """

    workspace_kind: str
    exposed_slots: tuple[str, ...]
    information_digest: str
    intervention_class: str = InterventionClass.R_ONLY.value
    renderer_id: str = ""
    rendered_bytes_digest: str = ""
    slots_were_declared: bool = False
    schema_version: str = STATE_IDENTITY_SCHEMA_VERSION

    @classmethod
    def from_information(
        cls,
        information: Mapping[str, Any],
        *,
        workspace_kind: str = LEAN_TACTIC_WORKSPACE,
        intervention_class: InterventionClass = InterventionClass.R_ONLY,
        renderer_id: str = "",
        rendered: Mapping[str, Any] | None = None,
        slots_were_declared: bool = False,
    ) -> WorkspaceProjectionIdentity:
        """Build an identity from a slot -> value mapping."""

        canonical = {
            str(slot): canonicalise_slot_value(str(slot), value)
            for slot, value in information.items()
        }
        return cls(
            workspace_kind=workspace_kind,
            exposed_slots=tuple(sorted(canonical)),
            information_digest=stable_hash(canonical),
            intervention_class=intervention_class.value,
            renderer_id=renderer_id,
            rendered_bytes_digest=(
                "" if rendered is None else stable_hash(canonical_json(dict(rendered)))
            ),
            slots_were_declared=slots_were_declared,
        )

    @classmethod
    def from_rendered(
        cls,
        rendered: Mapping[str, Any],
        *,
        workspace_kind: str = LEAN_TACTIC_WORKSPACE,
        intervention_class: InterventionClass = InterventionClass.R_ONLY,
        extra: Mapping[str, Any] | None = None,
    ) -> WorkspaceProjectionIdentity:
        """Conservative fallback for a renderer that declares nothing.

        Known keys map to their slot; every other key becomes an opaque
        ``UNDECLARED:<key>`` slot.  This is deliberately strict -- an undeclared renderer that
        renames ``goals_pp`` to ``goal`` gets a different identity, because nothing has
        established that the two carry the same information.
        """

        information: dict[str, Any] = {}
        for key, value in rendered.items():
            if key in _NON_INFORMATIONAL_KEYS:
                continue
            slot = _DEFAULT_KEY_TO_SLOT.get(key)
            information[slot.value if slot else f"{UNDECLARED_SLOT_PREFIX}{key}"] = value
        for key, value in (extra or {}).items():
            information[str(key)] = value
        return cls.from_information(
            information,
            workspace_kind=workspace_kind,
            intervention_class=intervention_class,
            renderer_id=str(rendered.get("renderer_id", "")),
            rendered=rendered,
            slots_were_declared=False,
        )

    @property
    def projection_hash(self) -> str:
        """Identity of the declared information.  Excludes renderer id and rendered bytes."""

        return stable_hash(
            {
                "schema": self.schema_version,
                "workspace_kind": self.workspace_kind,
                "exposed_slots": list(self.exposed_slots),
                "information_digest": self.information_digest,
            }
        )

    def same_declared_information_as(self, other: WorkspaceProjectionIdentity) -> bool:
        return self.projection_hash == other.projection_hash

    def differs_only_in_rendering(self, other: WorkspaceProjectionIdentity) -> bool:
        """The ``R_ONLY`` shape: same declared information, different bytes."""

        return self.same_declared_information_as(other) and (
            self.rendered_bytes_digest != other.rendered_bytes_digest
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "workspace_kind": self.workspace_kind,
            "exposed_slots": list(self.exposed_slots),
            "information_digest": self.information_digest,
            "intervention_class": self.intervention_class,
            "renderer_id": self.renderer_id,
            "rendered_bytes_digest": self.rendered_bytes_digest,
            "slots_were_declared": self.slots_were_declared,
            "projection_hash": self.projection_hash,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            workspace_kind=str(payload["workspace_kind"]),
            exposed_slots=tuple(str(item) for item in payload.get("exposed_slots", ())),
            information_digest=str(payload["information_digest"]),
            intervention_class=str(
                payload.get("intervention_class", InterventionClass.R_ONLY.value)
            ),
            renderer_id=str(payload.get("renderer_id", "")),
            rendered_bytes_digest=str(payload.get("rendered_bytes_digest", "")),
            slots_were_declared=bool(payload.get("slots_were_declared", False)),
            schema_version=str(payload.get("schema", STATE_IDENTITY_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceProjection:
    """What a Solver is actually given: exact bytes, plus the identity of the information in them.

    This is ``Ω_L``'s output.  The bytes are the language's; the identity is the arena's account
    of what those bytes were allowed to contain.
    """

    identity: WorkspaceProjectionIdentity
    rendered: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"identity": self.identity.to_dict(), "rendered": dict(self.rendered)}


def project_workspace(
    renderer: Any,
    envelope: BackendStateEnvelope,
    *,
    extra: Mapping[str, Any] | None = None,
    workspace_kind: str = LEAN_TACTIC_WORKSPACE,
    intervention_class: InterventionClass = InterventionClass.R_ONLY,
) -> WorkspaceProjection:
    """Render a state through ``Ω_L`` and identify the information that rendering exposed.

    If the renderer implements :class:`InformationDeclaringRenderer` its declaration is used and
    ``slots_were_declared`` is ``True``; otherwise the conservative key-derived fallback runs.
    """

    rendered = dict(renderer.render(envelope))
    if isinstance(renderer, InformationDeclaringRenderer):
        information = dict(renderer.declare_information(envelope))
        information.update(dict(extra or {}))
        identity = WorkspaceProjectionIdentity.from_information(
            information,
            workspace_kind=workspace_kind,
            intervention_class=intervention_class,
            renderer_id=str(getattr(renderer, "renderer_id", "")),
            rendered=rendered,
            slots_were_declared=True,
        )
    else:
        identity = WorkspaceProjectionIdentity.from_rendered(
            rendered,
            workspace_kind=workspace_kind,
            intervention_class=intervention_class,
            extra=extra,
        )
    return WorkspaceProjection(identity=identity, rendered=rendered)


# =============================================================================================
# R_ONLY parity
# =============================================================================================


@dataclass(frozen=True, slots=True)
class ProjectionParityResult:
    """The answer to "may these two languages be compared as a representation change?"."""

    intervention_class: str
    parity_required: bool
    parity_holds: bool
    bytes_differ: bool
    explanation: str

    @property
    def admissible(self) -> bool:
        """``True`` unless parity was required and did not hold."""

        return self.parity_holds or not self.parity_required

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervention_class": self.intervention_class,
            "parity_required": self.parity_required,
            "parity_holds": self.parity_holds,
            "bytes_differ": self.bytes_differ,
            "admissible": self.admissible,
            "explanation": self.explanation,
        }


def check_projection_parity(
    left: WorkspaceProjectionIdentity,
    right: WorkspaceProjectionIdentity,
    intervention_class: InterventionClass,
) -> ProjectionParityResult:
    """Check visible-information parity for a declared intervention class.

    Manual §12.3 and §26.2: only ``R_ONLY`` claims to hold visible information fixed, and it is
    the only class for which parity is mandatory.  For every other class a difference in the
    projection identity is the *intended effect of the intervention* and must not be reported as
    a violation -- reporting it as one is how an ontology change gets mislabelled a representation
    change (manual §26.3).
    """

    required = intervention_class.requires_visible_information_parity
    holds = left.same_declared_information_as(right)
    bytes_differ = left.rendered_bytes_digest != right.rendered_bytes_digest
    if required and holds:
        explanation = "R_ONLY: the same declared information was exposed; the renderings " + (
            "differ in bytes, which is the point" if bytes_differ else "are byte-identical"
        )
    elif required:
        explanation = (
            "R_ONLY parity VIOLATED: the two projections expose different declared information, "
            f"{sorted(set(left.exposed_slots) ^ set(right.exposed_slots))} differ by slot; this "
            "pair may not support a representation claim"
        )
    else:
        explanation = (
            f"{intervention_class.value} does not require visible-information parity "
            "(manual §26.3); a difference here is the intervention, not a fault"
        )
    return ProjectionParityResult(
        intervention_class=intervention_class.value,
        parity_required=required,
        parity_holds=holds,
        bytes_differ=bytes_differ,
        explanation=explanation,
    )
