"""The two representations HC-V0.6 compares, with ``R_ONLY`` *enforced* rather than asserted.

``docs/HC_V0_6_DESIGN_BRIEF.md`` §2 is the specification; ``docs/HC_V0_6_REPRESENTATIONS.md`` is
the prose companion.  This module is the mechanism.

**Why a stronger contract than slot declaration.**  ``arena/trajectory/state_identity.py`` lets a
renderer *declare* which :class:`~arena.trajectory.state_identity.InformationSlot` values it
exposes, and ``check_projection_parity`` compares those declarations.  The HC-V0.5 red team
(``docs/HC_V0_5_REDTEAM.md``, findings ``V05-14`` / ``V05-15``) showed the hole: a declaration is a
*claim by the language*, and a renderer can declare less than it actually shows.  Nothing in the
declaration machinery can catch that, because the declaration is its only evidence.

HC-V0.6 closes the hole with a contract that a renderer cannot lie about:

    **Every ``R_ONLY`` renderer MUST be a bijective re-encoding of the baseline rendering.**

A renderer ships :meth:`render` *and* :meth:`invert`, and ``invert(R.render(s)) == R_A.render(s)``
is checked byte-for-byte at every state in the bank.  A bijection cannot add information — there
is nothing to add it from — and cannot remove information, or it could not be inverted.  The
declaration then stops being an unverifiable claim: the bijection is the proof that the rendering
carries exactly the declared bytes and nothing else.

Two structural properties make this checkable rather than hoped for:

*declaration-derived rendering*
    :class:`DeclarationDerivedRenderer` implements ``render`` as
    ``self.present(self.declare_information(envelope))`` and **forbids subclasses from overriding
    ``render``** (:meth:`DeclarationDerivedRenderer.__init_subclass__` raises).  ``present`` never
    receives the envelope, so a renderer physically cannot show something it did not declare.

*never mangle silently*
    :func:`parse_tactic_state` refuses to return a parse that does not reconstruct its input, and
    :meth:`EnumeratedWorkspaceRenderer.present` re-inverts its own output before returning it.  A
    state whose shape this module cannot handle raises :class:`UnrenderableStateError` with a
    named :class:`RefusalReason`; it is never silently reshaped.

**The four arms.**

===============  ====================  ==============================================
arm              intervention class    what the Solver sees
===============  ====================  ==============================================
``R_A``          ``R_ONLY`` baseline   Lean's native pretty-printed tactic state,
                                       byte-identical to ``BackendNativeRenderer``
``R_A_PRIME``    ``R_ONLY`` null       the identical characters under a different
                                       whitespace convention: one extra space after
                                       the turnstile, one trailing space per line.
                                       Nothing is moved, relabelled or reordered
``R_B``          ``R_ONLY`` variant    the same characters re-laid out: hypotheses as
                                       an enumerated block, the goal under its own
                                       heading.  An interface (``I``) gene, manual
                                       §10.9 (explicit labels, goal position,
                                       delimiter family)
``R_ABLATED``    ``P_CHANGE``          goal text withheld; goal count and backend
                                       metadata retained
===============  ====================  ==============================================

**Why ``R_A_PRIME`` exists** (design brief §9.4).  ``R_ABLATED`` is an enormous intervention —
the goal text is simply gone.  Detecting it proves the rendering pipeline is causally connected
to the outcome at all, which is necessary but says nothing about sensitivity *at the scale a
representation change plausibly operates*.  ``R_A_PRIME`` supplies that missing rung.  It is a
semantically null byte perturbation: whitespace only, bijective, declaring exactly the baseline's
slots with exactly the baseline's values.  It sits between control ``C1`` (byte-identical) and
``R_B`` (restructured), and it makes the headline number readable:

* ``Δ(R_A, R_A′) ≈ 0`` while ``Δ(R_A, R_B) ≠ 0`` → the effect belongs to the **structure** of the
  rendering, not to the bare fact that the bytes (and hence the token sequence) changed;
* **both** move → the Solver is sensitive to byte perturbation as such, and ``R_B``'s effect
  cannot be attributed to its structure.  That is a finding about the assay, and it blocks the
  representation claim rather than supporting it.

The asymmetry is the point: ``R_A_PRIME`` can only ever *subtract* from what a positive
``Δ(R_A,R_B)`` licenses.  It is a control that can embarrass the result, never one that can
manufacture it.

``R_ABLATED`` is **not** a representation and must never be reported as one.  It is the
sensitivity floor of design brief §4 (control ``C2``).  Its class is *derived* by
:func:`derive_intervention_class` from the declaration it makes — its declared slot set is a
strict subset of the baseline's — and is never a hand-written label; see
:data:`GOAL_VISIBILITY_GENE` for why the gene table cannot express it today.

**Naming collision, flagged not fixed.**  ``arena/experiments/hc_v0_6/schema.py`` (owned by
another work item) declares an ``Arm.R_A_PRIME`` meaning *"the baseline renderer drawn a second
time"*, i.e. design brief §9.2's identity control ``C1``.  That predates §9.4 and is a different
object from the renderer defined here.  This module does not edit that file; the two meanings
must be reconciled before the assay runs.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from arena.evolution.record import GENE_INTERVENTION_CLASS, InterventionClass
from arena.trajectory.schema import BackendStateEnvelope, PPScope, content_sha256
from arena.trajectory.state_identity import (
    LEAN_TACTIC_WORKSPACE,
    InformationSlot,
    WorkspaceProjection,
    WorkspaceProjectionIdentity,
    project_workspace,
)

#: The renderer id of ``arena.trajectory.arena_v0.BackendNativeRenderer``.  :class:`BaselineNative`
#: reuses it deliberately: ``R_A`` *is* that renderer, so HC-V0.5's numbers remain comparable and
#: the byte-equivalence test can compare complete mappings rather than "everything except the id".
BASELINE_RENDERER_ID = "backend-native-v0"

#: The one key of a rendered mapping the Solver adapter reads
#: (``arena.trajectory.solver.OBSERVED_FIELD``).  All three arms emit it, so the assay harness
#: needs no per-arm special case: the arm *is* the value of this key.
RENDERED_STATE_FIELD = "goals_pp"

#: Lean prints the separator between a goal's context and its target at the start of a line.
GOAL_MARKER = "⊢"

#: Lean separates goals with a blank line.
GOAL_SEPARATOR = "\n\n"

#: Text ``R_ABLATED`` substitutes for the goal.  Named so it is greppable in any artefact.
WITHHELD_MARKER = "[GOAL TEXT WITHHELD BY R_ABLATED]"


# =============================================================================================
# Refusals: the shapes this module will not pretend to handle
# =============================================================================================


class RefusalReason(StrEnum):
    """Why a state cannot be re-laid out invertibly.

    A refusal is a *result*, not a bug: a renderer that silently mangles a state is worse than one
    that refuses it, because the mangling would be measured as a representation effect.
    """

    #: ``pp`` is empty.  Not an anchor: an anchored state has open goals (design brief §1).
    EMPTY_PP = "EMPTY_PP"
    #: No line **anywhere in the state** starts with ``⊢``.  Lean prints ``"no goals"`` here;
    #: again not an anchor.  Because this reason is reported as a *count* it must keep exactly
    #: that meaning, so :func:`parse_tactic_state` tests it against the whole pretty-print before
    #: any block is examined — see :data:`EMPTY_LINE_IN_GOAL_BLOCK`.
    NO_GOAL_MARKER = "NO_GOAL_MARKER"
    #: One blank-line-separated block carries more than one ``⊢`` line at column 0, so the block
    #: boundary is not the blank line.  Observed shape: a ``\\r\\n``-delimited multi-goal state.
    MULTIPLE_GOAL_MARKERS_IN_BLOCK = "MULTIPLE_GOAL_MARKERS_IN_BLOCK"
    #: A block contains an empty line, so hypothesis grouping is ambiguous.  Reached by a leading
    #: or trailing newline, or by three or more consecutive newlines.  It is checked across every
    #: block *before* any block is parsed, because a stray blank line is what makes the blank-line
    #: split stop being the goal split: leave it until block parsing and a state whose goal is
    #: plainly present is reported as :data:`NO_GOAL_MARKER` — a materially false diagnosis, since
    #: that reason means "Lean printed 'no goals'".  The reported reason must be the cause and not
    #: whichever symptom happened to surface in the earliest block.
    EMPTY_LINE_IN_GOAL_BLOCK = "EMPTY_LINE_IN_GOAL_BLOCK"
    #: A block's first context line is indented, so it continues a hypothesis that is not there.
    ORPHAN_CONTINUATION_LINE = "ORPHAN_CONTINUATION_LINE"
    #: The number of blank-line-separated blocks disagrees with the backend's own ``n_goals``.
    GOAL_COUNT_MISMATCH = "GOAL_COUNT_MISMATCH"
    #: The parse did not reconstruct its input.  Should be unreachable; it is checked anyway,
    #: because "should be unreachable" is how a silent mangle ships.
    PARSE_NOT_ROUND_TRIPPABLE = "PARSE_NOT_ROUND_TRIPPABLE"
    #: The layout did not invert to the parse it came from.  Same reasoning.
    LAYOUT_NOT_ROUND_TRIPPABLE = "LAYOUT_NOT_ROUND_TRIPPABLE"


class UnrenderableStateError(ValueError):
    """This module refuses to re-lay out this state.  Loud, named, never silent."""

    def __init__(self, reason: RefusalReason, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)


class MalformedLayoutError(ValueError):
    """``invert`` was handed text that is not a rendering this module produced."""


# =============================================================================================
# The parse: Lean's tactic-state pretty-print, decomposed losslessly
# =============================================================================================


@dataclass(frozen=True, slots=True)
class GoalBlock:
    """One goal of a Lean tactic state, decomposed into the pieces a layout may move.

    Every field holds **raw lines**, exactly as Lean printed them, including indentation and any
    trailing whitespace.  Nothing here is normalised: :meth:`unparse` must reproduce the original
    bytes, and :func:`parse_tactic_state` refuses to return a parse for which it does not.
    """

    #: Lean's ``case <tag>`` line, verbatim, or ``None`` when the goal carries no case tag.
    case_line: str | None
    #: One tuple of raw lines per hypothesis: its first line plus any indented continuations.
    hypotheses: tuple[tuple[str, ...], ...]
    #: The ``⊢`` line plus any indented continuations of the target.
    target_lines: tuple[str, ...]

    def unparse(self) -> str:
        lines: list[str] = []
        if self.case_line is not None:
            lines.append(self.case_line)
        for entry in self.hypotheses:
            lines.extend(entry)
        lines.extend(self.target_lines)
        return "\n".join(lines)

    @property
    def case_tag(self) -> str | None:
        """The case tag with Lean's ``case `` keyword removed, or ``None``."""

        return None if self.case_line is None else self.case_line[len("case ") :]


@dataclass(frozen=True, slots=True)
class ParsedTacticState:
    """A whole tactic state as a sequence of :class:`GoalBlock` s.

    Construct it only through :func:`parse_tactic_state`, which checks
    ``parse(pp).unparse() == pp`` before returning.
    """

    blocks: tuple[GoalBlock, ...]

    def unparse(self) -> str:
        return GOAL_SEPARATOR.join(block.unparse() for block in self.blocks)

    @property
    def n_goals(self) -> int:
        return len(self.blocks)


def _parse_goal_block(block: str) -> GoalBlock:
    lines = block.split("\n")
    if any(line == "" for line in lines):
        raise UnrenderableStateError(
            RefusalReason.EMPTY_LINE_IN_GOAL_BLOCK,
            "a goal block contains an empty line, so hypothesis grouping is ambiguous",
        )
    markers = [index for index, line in enumerate(lines) if line.startswith(GOAL_MARKER)]
    if not markers:
        raise UnrenderableStateError(
            RefusalReason.NO_GOAL_MARKER, "a goal block has no line starting with the turnstile"
        )
    if len(markers) > 1:
        raise UnrenderableStateError(
            RefusalReason.MULTIPLE_GOAL_MARKERS_IN_BLOCK,
            f"{len(markers)} turnstile lines in one blank-line-separated block",
        )
    boundary = markers[0]
    head = lines[:boundary]
    case_line: str | None = None
    if head and head[0].startswith("case "):
        case_line = head[0]
        head = head[1:]
    hypotheses: list[list[str]] = []
    for line in head:
        if line[0] in " \t":
            if not hypotheses:
                raise UnrenderableStateError(
                    RefusalReason.ORPHAN_CONTINUATION_LINE,
                    "the first context line is indented, so it continues nothing",
                )
            hypotheses[-1].append(line)
        else:
            hypotheses.append([line])
    return GoalBlock(
        case_line=case_line,
        hypotheses=tuple(tuple(entry) for entry in hypotheses),
        target_lines=tuple(lines[boundary:]),
    )


def parse_tactic_state(pp: str, *, n_goals: int | None = None) -> ParsedTacticState:
    """Decompose Lean's tactic-state pretty-print, or refuse.

    The decomposition is deterministic and purely positional:

    1. goals are the ``\\n\\n``-separated blocks;
    2. within a block, the single line starting with ``⊢`` at column 0 separates the context from
       the target — Lean indents every continuation line, so a ``⊢`` *inside* a hypothesis type is
       not at column 0 and does not confuse the split;
    3. a leading ``case `` line is the case tag;
    4. a context line at column 0 starts a hypothesis; an indented one continues the previous one.

    ``n_goals``, when given, is cross-checked against the block count: a disagreement means the
    block split is not the goal split, and the state is refused rather than re-laid out on a guess.

    Refusals are ordered so that the reason names the *cause*, not the first symptom.  The
    turnstile test runs against the whole pretty-print, so :attr:`RefusalReason.NO_GOAL_MARKER`
    keeps its documented meaning ("Lean printed 'no goals'; not an anchor").  The blank-line test
    then runs across every block before any block is parsed, because a stray empty line is what
    breaks the segmentation — ``"a : Nat\\n\\n\\n⊢ True"`` would otherwise be refused as
    ``NO_GOAL_MARKER`` (its *first* block has no turnstile) despite plainly carrying an open goal,
    and refusal reasons are reported as counts.

    Raises :class:`UnrenderableStateError` for every shape it cannot handle, including the
    "should be unreachable" one where the parse fails to reproduce its own input.
    """

    if pp == "":
        raise UnrenderableStateError(RefusalReason.EMPTY_PP, "the pretty-printed state is empty")
    if not any(line.startswith(GOAL_MARKER) for line in pp.split("\n")):
        raise UnrenderableStateError(
            RefusalReason.NO_GOAL_MARKER,
            "no line starts with the turnstile; Lean prints 'no goals' for a closed state",
        )
    chunks = pp.split(GOAL_SEPARATOR)
    for chunk in chunks:
        if any(line == "" for line in chunk.split("\n")):
            raise UnrenderableStateError(
                RefusalReason.EMPTY_LINE_IN_GOAL_BLOCK,
                "a goal block contains an empty line, so hypothesis grouping is ambiguous",
            )
    blocks = tuple(_parse_goal_block(chunk) for chunk in chunks)
    parsed = ParsedTacticState(blocks=blocks)
    if n_goals is not None and n_goals != len(blocks):
        raise UnrenderableStateError(
            RefusalReason.GOAL_COUNT_MISMATCH,
            f"the backend reports n_goals={n_goals} but the state splits into {len(blocks)} blocks",
        )
    if parsed.unparse() != pp:
        raise UnrenderableStateError(
            RefusalReason.PARSE_NOT_ROUND_TRIPPABLE,
            "the parse did not reproduce its input; refusing to render a state it would mangle",
        )
    return parsed


def refusal_reason(envelope: BackendStateEnvelope) -> RefusalReason | None:
    """``None`` when every arm can render this state, otherwise why ``R_B`` refuses it.

    A bank builder should call this and drop refused states **before** any Solver call.  Refusing
    on pretty-print *shape* is upstream of the Solver, so it is not selection on anything
    downstream of Solver performance (design brief §7).
    """

    try:
        parse_tactic_state(envelope.pp, n_goals=envelope.n_goals)
    except UnrenderableStateError as error:
        return error.reason
    return None


def is_renderable(envelope: BackendStateEnvelope) -> bool:
    """``True`` when every arm can render this state invertibly."""

    return refusal_reason(envelope) is None


# =============================================================================================
# The layout R_B uses, and its inverse
# =============================================================================================

_GOAL_HEADER = re.compile(r"\[GOAL (\d+) OF (\d+)\]")
_HYPOTHESES_HEADER = re.compile(r"\[HYPOTHESES (\d+)\]")
_CASE_PREFIX = "[CASE] "
_TARGET_HEADER = "[TARGET]"

#: Identifier of the layout, so a change to it is visible as a different renderer rather than as a
#: silent drift in the measured effect.
LAYOUT_ID = "enumerated-context-headed-target-v1"


def layout(parsed: ParsedTacticState) -> str:
    """Re-lay out a parsed tactic state: enumerated hypotheses, the target under a heading.

    The characters of every hypothesis and of the target are Lean's own, unchanged.  What changes
    is the *interface*: goals are numbered and counted, the context is an explicitly enumerated
    block with a declared length, the case tag is labelled, and the target sits under its own
    heading rather than being found by scanning for a turnstile.  Those are exactly the interface
    (``I``) dimensions of manual §10.9 — explicit labels, goal position, field ordering, delimiter
    family — and none of them is a change of information.
    """

    total = len(parsed.blocks)
    rendered_blocks: list[str] = []
    for index, block in enumerate(parsed.blocks, start=1):
        lines = [f"[GOAL {index} OF {total}]"]
        if block.case_line is not None:
            lines.append(f"{_CASE_PREFIX}{block.case_tag}")
        lines.append(f"[HYPOTHESES {len(block.hypotheses)}]")
        for position, entry in enumerate(block.hypotheses, start=1):
            lines.append(f"({position}) {entry[0]}")
            lines.extend(entry[1:])
        lines.append(_TARGET_HEADER)
        lines.extend(block.target_lines)
        rendered_blocks.append("\n".join(lines))
    return GOAL_SEPARATOR.join(rendered_blocks)


def _unlayout_block(text: str, *, index: int, total: int) -> GoalBlock:
    lines = text.split("\n")
    position = 0

    def take() -> str:
        nonlocal position
        if position >= len(lines):
            raise MalformedLayoutError("the laid-out goal block ended early")
        line = lines[position]
        position += 1
        return line

    header = _GOAL_HEADER.fullmatch(take())
    if header is None:
        raise MalformedLayoutError("a goal block does not begin with a [GOAL i OF n] header")
    if (int(header.group(1)), int(header.group(2))) != (index, total):
        raise MalformedLayoutError(
            f"goal header says {header.group(1)} of {header.group(2)}, expected {index} of {total}"
        )

    case_line: str | None = None
    if position < len(lines) and lines[position].startswith(_CASE_PREFIX):
        case_line = "case " + take()[len(_CASE_PREFIX) :]

    hypotheses_header = _HYPOTHESES_HEADER.fullmatch(take())
    if hypotheses_header is None:
        raise MalformedLayoutError("a goal block has no [HYPOTHESES n] header")
    declared = int(hypotheses_header.group(1))

    hypotheses: list[tuple[str, ...]] = []
    for ordinal in range(1, declared + 1):
        prefix = f"({ordinal}) "
        line = take()
        if not line.startswith(prefix):
            raise MalformedLayoutError(f"hypothesis {ordinal} does not carry the prefix {prefix!r}")
        entry = [line[len(prefix) :]]
        stop = f"({ordinal + 1}) " if ordinal < declared else None
        while position < len(lines):
            following = lines[position]
            if stop is None:
                if following == _TARGET_HEADER:
                    break
            elif following.startswith(stop):
                break
            entry.append(following)
            position += 1
        hypotheses.append(tuple(entry))

    if take() != _TARGET_HEADER:
        raise MalformedLayoutError("a goal block has no [TARGET] heading")
    target_lines = tuple(lines[position:])
    if not target_lines or not target_lines[0].startswith(GOAL_MARKER):
        raise MalformedLayoutError("the [TARGET] section does not begin with a turnstile line")
    return GoalBlock(case_line=case_line, hypotheses=tuple(hypotheses), target_lines=target_lines)


def unlayout(text: str) -> ParsedTacticState:
    """The inverse of :func:`layout`.  Raises :class:`MalformedLayoutError` on anything else."""

    chunks = text.split(GOAL_SEPARATOR)
    total = len(chunks)
    return ParsedTacticState(
        blocks=tuple(
            _unlayout_block(chunk, index=index, total=total)
            for index, chunk in enumerate(chunks, start=1)
        )
    )


# =============================================================================================
# The renderer base: render is derived from the declaration, structurally
# =============================================================================================


@runtime_checkable
class BijectiveRenderer(Protocol):
    """A renderer whose output can be turned back into the baseline rendering.

    Implementing this protocol is what an ``R_ONLY`` arm claims; :func:`check_bijection` is what
    checks the claim.  ``R_ABLATED`` deliberately does **not** implement it — a lossy projection
    has no inverse, and ``isinstance(R_ABLATED, BijectiveRenderer)`` is ``False`` as a structural
    fact rather than as a comment.
    """

    @property
    def renderer_id(self) -> str: ...

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]: ...

    def invert(self, rendered: Mapping[str, Any]) -> Mapping[str, Any]: ...


class DeclarationDerivedRenderer(ABC):
    """``Ω_L`` whose rendering is a pure function of its own information declaration.

    Subclasses implement :meth:`declare_information` (which sees the envelope) and :meth:`present`
    (which sees only the declaration).  :meth:`render` is composed from the two and **may not be
    overridden**: :meth:`__init_subclass__` raises ``TypeError`` if a subclass tries, so a renderer
    that peeks at the envelope outside its declaration cannot be defined at all.

    This is what upgrades ``check_projection_parity`` from "compares two claims" to "compares two
    claims that the renderings provably could not have exceeded".  It is not proof against a
    renderer that stashes the envelope on itself between the two calls — the arms here are frozen
    dataclasses, which cannot — so a declaration-equality property test backs it up.
    """

    #: Every concrete arm declares its own id as a dataclass field.  Annotated here so the
    #: contract is part of the base class rather than a convention its callers have to trust.
    renderer_id: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "render" in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} overrides render(); a DeclarationDerivedRenderer's rendering must "
                "be present(declare_information(envelope)) so that it cannot exceed its own "
                "declaration. Implement present() instead."
            )

    @abstractmethod
    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        """Which :class:`InformationSlot` values this renderer exposes, and their values."""

    @abstractmethod
    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        """Lay out a declaration.  Receives no envelope, so it can show nothing else."""

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        declaration = MappingProxyType(dict(self.declare_information(envelope)))
        return self.present(declaration)


def _declare_full(envelope: BackendStateEnvelope) -> dict[str, Any]:
    """The baseline declaration: everything ``BackendNativeRenderer`` shows.

    ``pp_sha256`` and ``renderer_id`` are absent on purpose — the identity machinery already
    treats them as non-informational (``state_identity._NON_INFORMATIONAL_KEYS``), a hash being a
    function of a value already declared in another slot.
    """

    return {
        InformationSlot.GOAL_TEXT: envelope.pp,
        InformationSlot.GOAL_COUNT: envelope.n_goals,
        InformationSlot.BACKEND_KIND: envelope.backend_kind,
        InformationSlot.BACKEND_STATE_ID: envelope.state_id,
        InformationSlot.PP_SCOPE: envelope.pp_scope,
    }


def _scope_dict(value: Any) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PPScope) else dict(value)


# =============================================================================================
# R_A — the baseline
# =============================================================================================


@dataclass(frozen=True, slots=True)
class BaselineNative(DeclarationDerivedRenderer):
    """``R_A``: Lean's native pretty-printed tactic state.

    Byte-identical to ``arena.trajectory.arena_v0.BackendNativeRenderer`` — same keys, same
    values, same ``renderer_id`` — so HC-V0.5's measurements remain directly comparable and the
    equivalence can be tested as complete-mapping equality rather than "equal apart from the id".
    Its :meth:`invert` is the identity, which is what makes it the fixed point every other arm's
    inverse must land on.
    """

    arm_id: str = "R_A"
    renderer_id: str = BASELINE_RENDERER_ID

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return _declare_full(envelope)

    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        pp = str(information[InformationSlot.GOAL_TEXT])
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": information[InformationSlot.BACKEND_KIND],
            "state_id": information[InformationSlot.BACKEND_STATE_ID],
            "goals_pp": pp,
            "n_goals": information[InformationSlot.GOAL_COUNT],
            "pp_scope": _scope_dict(information[InformationSlot.PP_SCOPE]),
            "pp_sha256": content_sha256(pp),
        }

    def invert(self, rendered: Mapping[str, Any]) -> Mapping[str, Any]:
        """The identity.  ``R_A`` is the baseline the other inverses must reproduce."""

        return dict(rendered)


# =============================================================================================
# R_A_PRIME — the same characters, a different whitespace convention
# =============================================================================================

#: Identifier of the perturbation, so a change to it is visible as a different renderer rather
#: than as a silent drift in the measured null.  Same reasoning as :data:`LAYOUT_ID`.
PERTURBATION_ID = "double-space-after-turnstile-and-trailing-space-v1"

#: The one space :func:`perturb_whitespace` appends to every line.
_TRAILING_SPACE = " "

#: The turnstile followed by one space — the prefix whose spacing is doubled.
_MARKER_SPACE = f"{GOAL_MARKER} "


def perturb_whitespace(text: str) -> str:
    """A semantically null byte perturbation: whitespace only, and a total bijection on ``str``.

    Two conventions change, and nothing else does:

    1. a line beginning ``"⊢ "`` gains one further space after the turnstile;
    2. every line gains exactly one trailing space.

    Neither moves, relabels, reorders or reveals anything.  No character of a hypothesis or of a
    target is touched; the *only* difference from :func:`BaselineNative.present`'s output is
    whitespace, which is precisely what makes this the null arm rather than a second variant.

    The two conventions are deliberately different in kind.  The trailing space is uniform — every
    line's terminal token changes under any fixed tokenizer — but it is also the first thing a
    prompt-assembly layer would strip, and a stripped ``R_A_PRIME`` would silently collapse into
    control ``C1``.  The doubled space after the turnstile is *interior*: it survives trimming, so
    the perturbation cannot be quietly undone downstream without the ``prompt_sha256`` showing it.

    One consequence worth stating rather than discovering: a *blank* line is a line, so Lean's
    ``"\\n\\n"`` goal separator becomes ``"\\n \\n"``.  Visually that is still a blank line and
    mathematically it is still nothing, but ``"\\n\\n"`` is a single token in many BPE
    vocabularies and ``"\\n \\n"`` is not — which is the perturbation doing exactly its job on
    multi-goal states.  A corollary is that :func:`parse_tactic_state` cannot read this arm's
    output; only :func:`unperturb_whitespace` can, and nothing else ever tries.

    Totality matters.  Appending a space is defined for every line, and doubling ``"⊢ "`` maps
    ``"⊢ x" → "⊢  x"`` and fixes every line that does not start with the marker-and-space; both
    are injective, so their composition is a bijection on all of ``str`` and ``R_A_PRIME`` never
    refuses a state.  ``R_B`` may refuse (its re-layout needs a decomposition that not every
    pretty-print admits), so the bank the assay can actually play is the *intersection*, which is
    ``R_B``'s.  That is a fact to report, not a reason to weaken this arm.
    """

    perturbed: list[str] = []
    for line in text.split("\n"):
        if line.startswith(_MARKER_SPACE):
            line = f"{GOAL_MARKER} {line[len(GOAL_MARKER) :]}"
        perturbed.append(f"{line}{_TRAILING_SPACE}")
    return "\n".join(perturbed)


def unperturb_whitespace(text: str) -> str:
    """The inverse of :func:`perturb_whitespace`.  Raises on anything it did not produce."""

    original: list[str] = []
    for line in text.split("\n"):
        if not line.endswith(_TRAILING_SPACE):
            raise MalformedLayoutError(
                f"a perturbed line does not carry the trailing space convention: {line!r}"
            )
        line = line[: -len(_TRAILING_SPACE)]
        if line.startswith(f"{_MARKER_SPACE} "):
            line = f"{GOAL_MARKER}{line[len(GOAL_MARKER) + 1 :]}"
        original.append(line)
    return "\n".join(original)


@dataclass(frozen=True, slots=True)
class WhitespacePerturbedNative(DeclarationDerivedRenderer):
    """``R_A_PRIME``: the baseline's characters under a different whitespace convention.

    Design brief §9.4's byte-perturbation control, and the module docstring gives the reading it
    licenses.  It is an ``R_ONLY`` arm on exactly the same terms as ``R_B`` — it declares the
    baseline's slots with the baseline's values, and :meth:`invert` reconstructs ``R_A``'s mapping
    byte-for-byte — but it restructures **nothing**.  That is the whole design: it holds structure
    fixed and varies only the bytes, so ``Δ(R_A,R_A′)`` isolates the part of ``Δ(R_A,R_B)`` that
    is not attributable to structure.

    It declares the *envelope's* text, not the perturbed text, so ``R_A``/``R_A_PRIME`` parity is
    exact rather than dependent on how :func:`~arena.trajectory.state_identity.normalize_goal_text`
    happens to normalise.  (That normalisation absorbs the trailing space and does not absorb the
    doubled interior space — an identity computed from the *rendered* bytes would therefore differ.
    Nothing here does that, and nothing may start to without saying so.)
    """

    arm_id: str = "R_A_PRIME"
    renderer_id: str = "hc-v0.6-R_A_PRIME-whitespace-v1"

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return _declare_full(envelope)

    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        text = perturb_whitespace(str(information[InformationSlot.GOAL_TEXT]))
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": information[InformationSlot.BACKEND_KIND],
            "state_id": information[InformationSlot.BACKEND_STATE_ID],
            "goals_pp": text,
            "n_goals": information[InformationSlot.GOAL_COUNT],
            "pp_scope": _scope_dict(information[InformationSlot.PP_SCOPE]),
            "perturbation_id": PERTURBATION_ID,
            "pp_sha256": content_sha256(text),
        }

    def invert(self, rendered: Mapping[str, Any]) -> Mapping[str, Any]:
        """Reconstruct ``R_A``'s rendering exactly, by undoing the whitespace convention.

        The digest carried in the rendering is of the *perturbed* text, so — as with ``R_B`` —
        nothing of the baseline is stashed here to be replayed; the baseline digest is recomputed
        from the recovered characters.
        """

        pp = unperturb_whitespace(str(rendered[RENDERED_STATE_FIELD]))
        return {
            "renderer_id": BASELINE_RENDERER_ID,
            "backend_kind": rendered["backend_kind"],
            "state_id": rendered["state_id"],
            "goals_pp": pp,
            "n_goals": rendered["n_goals"],
            "pp_scope": dict(rendered["pp_scope"]),
            "pp_sha256": content_sha256(pp),
        }


# =============================================================================================
# R_B — the same characters, re-laid out
# =============================================================================================


@dataclass(frozen=True, slots=True)
class EnumeratedWorkspaceRenderer(DeclarationDerivedRenderer):
    """``R_B``: hypotheses as an enumerated block, the goal under its own heading.

    A plausible interface (``I``) proposal, not a cosmetic token swap: it gives the context a
    declared length and stable per-goal ordinals, labels the case tag, and puts the target under a
    heading instead of leaving it to be found by scanning for ``⊢``.  Manual §10.9 lists exactly
    these dimensions — explicit labels, goal position, field ordering, delimiter family.

    Every hypothesis and the target keep Lean's own characters, so the rendering is a bijective
    re-encoding: :meth:`invert` reconstructs ``R_A``'s mapping byte-for-byte, including whitespace,
    and :meth:`present` verifies that before returning.  States whose pretty-print shape does not
    admit a deterministic decomposition raise :class:`UnrenderableStateError`; call
    :func:`refusal_reason` to filter a bank before any Solver call.
    """

    arm_id: str = "R_B"
    renderer_id: str = "hc-v0.6-R_B-enumerated-v1"

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return _declare_full(envelope)

    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        pp = str(information[InformationSlot.GOAL_TEXT])
        n_goals = int(information[InformationSlot.GOAL_COUNT])
        parsed = parse_tactic_state(pp, n_goals=n_goals)
        text = layout(parsed)
        if unlayout(text).unparse() != pp:
            raise UnrenderableStateError(
                RefusalReason.LAYOUT_NOT_ROUND_TRIPPABLE,
                "the layout did not invert to the state it came from",
            )
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": information[InformationSlot.BACKEND_KIND],
            "state_id": information[InformationSlot.BACKEND_STATE_ID],
            "goals_pp": text,
            "n_goals": n_goals,
            "pp_scope": _scope_dict(information[InformationSlot.PP_SCOPE]),
            "layout_id": LAYOUT_ID,
            "workspace_sha256": content_sha256(text),
        }

    def invert(self, rendered: Mapping[str, Any]) -> Mapping[str, Any]:
        """Reconstruct ``R_A``'s rendering exactly, by parsing the laid-out text back.

        Nothing of the original is carried in the rendered mapping — no hidden copy, no digest of
        it — so this genuinely re-derives the baseline bytes rather than replaying them.
        """

        pp = unlayout(str(rendered[RENDERED_STATE_FIELD])).unparse()
        return {
            "renderer_id": BASELINE_RENDERER_ID,
            "backend_kind": rendered["backend_kind"],
            "state_id": rendered["state_id"],
            "goals_pp": pp,
            "n_goals": rendered["n_goals"],
            "pp_scope": dict(rendered["pp_scope"]),
            "pp_sha256": content_sha256(pp),
        }


# =============================================================================================
# R_ABLATED — the positive control, which is not a representation
# =============================================================================================

#: The gene family a visibility ablation would belong to, and the point of this constant: it is
#: **not** in ``arena.evolution.record.GENE_INTERVENTION_CLASS``.  All fourteen declared families
#: are ``R_ONLY`` because the present genome is entirely surface/serialisation, so
#: ``classify_intervention`` cannot type ``R_ABLATED`` — it fails closed with
#: ``UnclassifiedGeneError``, which is the correct behaviour and is asserted in the tests.  Rather
#: than add a gene (this module does not own ``record.py``), :func:`derive_intervention_class`
#: derives the class from what the renderer *declares*, which is stronger anyway: it cannot be
#: mislabelled by writing a different gene name.
GOAL_VISIBILITY_GENE = "goal_visibility"


@dataclass(frozen=True, slots=True)
class GoalWithheldRenderer(DeclarationDerivedRenderer):
    """``R_ABLATED``: the goal text is withheld; the goal count and backend metadata remain.

    **Not a representation.**  It is control ``C2`` of design brief §4 — the sensitivity floor
    that shows the assay can detect the removal of information at all.  Reporting it beside
    ``Δ(R_A,R_B)`` as if it were a representation effect is precisely the confusion manual §26.3
    forbids.

    It declares a strict subset of the baseline's slots (no :attr:`InformationSlot.GOAL_TEXT`),
    which is what makes :func:`derive_intervention_class` return ``P_CHANGE`` for it from the
    declaration alone.  It has no ``invert`` — a lossy projection has none — so it does not satisfy
    :class:`BijectiveRenderer`.
    """

    arm_id: str = "R_ABLATED"
    renderer_id: str = "hc-v0.6-R_ABLATED-goal-withheld-v1"

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        declaration = _declare_full(envelope)
        del declaration[InformationSlot.GOAL_TEXT]
        return declaration

    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        n_goals = int(information[InformationSlot.GOAL_COUNT])
        text = f"{WITHHELD_MARKER}\n[GOALS REMAINING {n_goals}]"
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": information[InformationSlot.BACKEND_KIND],
            "state_id": information[InformationSlot.BACKEND_STATE_ID],
            "goals_pp": text,
            "n_goals": n_goals,
            "pp_scope": _scope_dict(information[InformationSlot.PP_SCOPE]),
            "goal_text_status": "WITHHELD",
        }


#: The four arms, by the id design brief §2 and §9.4 give them.  ``R_ABLATED`` is in the registry
#: because the assay must run it as control ``C2``; it is not a representation and the registry is
#: not a licence to report it as one.
ARMS: Mapping[str, DeclarationDerivedRenderer] = MappingProxyType(
    {
        "R_A": BaselineNative(),
        "R_A_PRIME": WhitespacePerturbedNative(),
        "R_B": EnumeratedWorkspaceRenderer(),
        "R_ABLATED": GoalWithheldRenderer(),
    }
)

#: The two arms whose difference is a representation difference, in the order Δ is defined:
#: ``Δ(R_A,R_B) = p_accept(R_B) − p_accept(R_A)``.
REPRESENTATION_ARM_IDS: tuple[str, str] = ("R_A", "R_B")

#: The arms that claim ``R_ONLY`` and must therefore satisfy the bijection contract at every state
#: in the bank.  ``R_ABLATED`` is absent because it has no inverse, which is the whole of what
#: distinguishes it from a representation.
BIJECTIVE_ARM_IDS: tuple[str, ...] = ("R_A", "R_A_PRIME", "R_B")

#: The null arm's pairing, in the order its Δ is defined: ``Δ(R_A,R_A′)``.  Reported *beside* the
#: headline number, never instead of it — see the module docstring for the two readings.
NULL_PERTURBATION_ARM_IDS: tuple[str, str] = ("R_A", "R_A_PRIME")


# =============================================================================================
# Checking the contract
# =============================================================================================


@dataclass(frozen=True, slots=True)
class BijectionCheck:
    """The result of ``invert(R.render(s)) == R_A.render(s)`` at one state."""

    state_id: str
    holds: bool
    refused: RefusalReason | None = None
    detail: str = ""

    @property
    def checked(self) -> bool:
        """``False`` when the state was refused, so it neither passes nor fails."""

        return self.refused is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "holds": self.holds,
            "checked": self.checked,
            "refused": None if self.refused is None else self.refused.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class BijectionReport:
    """Bank-wide round-trip evidence for one arm.  Report ``n`` and the failures, not a ratio."""

    arm_id: str
    baseline_arm_id: str
    checks: tuple[BijectionCheck, ...]

    @property
    def n_states(self) -> int:
        return len(self.checks)

    @property
    def n_checked(self) -> int:
        return sum(1 for check in self.checks if check.checked)

    @property
    def n_holds(self) -> int:
        return sum(1 for check in self.checks if check.checked and check.holds)

    @property
    def failures(self) -> tuple[BijectionCheck, ...]:
        return tuple(check for check in self.checks if check.checked and not check.holds)

    @property
    def refusals(self) -> tuple[BijectionCheck, ...]:
        return tuple(check for check in self.checks if not check.checked)

    @property
    def refusal_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for check in self.refusals:
            assert check.refused is not None
            counts[check.refused.value] = counts.get(check.refused.value, 0) + 1
        return dict(sorted(counts.items()))

    @property
    def holds_everywhere(self) -> bool:
        """``True`` iff every state that was checked round-tripped.  Refusals do not count."""

        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "baseline_arm_id": self.baseline_arm_id,
            "n_states": self.n_states,
            "n_checked": self.n_checked,
            "n_holds": self.n_holds,
            "n_failures": len(self.failures),
            "n_refused": len(self.refusals),
            "refusal_counts": self.refusal_counts,
            "holds_everywhere": self.holds_everywhere,
            "failures": [check.to_dict() for check in self.failures],
        }


def check_bijection(
    candidate: Any,
    envelope: BackendStateEnvelope,
    *,
    baseline: DeclarationDerivedRenderer | None = None,
) -> BijectionCheck:
    """Check ``invert(candidate.render(s)) == baseline.render(s)`` at one state."""

    reference = baseline if baseline is not None else ARMS["R_A"]
    if not isinstance(candidate, BijectiveRenderer):
        return BijectionCheck(
            state_id=envelope.state_id,
            holds=False,
            detail=f"{type(candidate).__name__} does not implement invert()",
        )
    try:
        rendered = candidate.render(envelope)
        recovered = dict(candidate.invert(rendered))
    except UnrenderableStateError as error:
        return BijectionCheck(
            state_id=envelope.state_id, holds=False, refused=error.reason, detail=error.detail
        )
    expected = dict(reference.render(envelope))
    if recovered == expected:
        return BijectionCheck(state_id=envelope.state_id, holds=True)
    differing = sorted(
        key for key in set(expected) | set(recovered) if expected.get(key) != recovered.get(key)
    )
    return BijectionCheck(
        state_id=envelope.state_id,
        holds=False,
        detail=f"recovered rendering differs from the baseline at {differing}",
    )


def bijection_report(
    candidate: Any,
    envelopes: Iterable[BackendStateEnvelope],
    *,
    baseline: DeclarationDerivedRenderer | None = None,
) -> BijectionReport:
    """Run :func:`check_bijection` over a bank and summarise it."""

    reference = baseline if baseline is not None else ARMS["R_A"]
    checks = tuple(
        check_bijection(candidate, envelope, baseline=reference) for envelope in envelopes
    )
    return BijectionReport(
        arm_id=str(getattr(candidate, "arm_id", getattr(candidate, "renderer_id", "?"))),
        baseline_arm_id=str(getattr(reference, "arm_id", reference.__class__.__name__)),
        checks=checks,
    )


# =============================================================================================
# Deriving the intervention class from the declaration
# =============================================================================================


@dataclass(frozen=True, slots=True)
class DerivedInterventionClass:
    """An :class:`InterventionClass` *computed* from two declarations, never asserted.

    The rule, stated once so it can be argued with:

    * declared slot sets equal **and** declared values equal → ``R_ONLY``.  Only the rendering can
      differ, which is manual §26.2's "hold visible mathematical information fixed".
    * anything else → ``P_CHANGE``.  The projection itself changed, so visible-information parity
      is not required and MUST NOT be asserted (manual §12.3, §26.3).

    It is deliberately coarse.  It cannot distinguish ``P_CHANGE`` from ``O_CHANGE`` — that needs
    an ontology declaration this genome does not have — so it names the weaker, safer class, and
    :attr:`permits_representation_claim` is ``False`` for both.  Erring toward "not a
    representation change" is the direction that cannot manufacture a representation result.
    """

    intervention_class: InterventionClass
    withheld_slots: tuple[str, ...]
    added_slots: tuple[str, ...]
    values_differ: bool
    basis: str

    @property
    def permits_representation_claim(self) -> bool:
        return self.intervention_class.permits_representation_claim

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervention_class": self.intervention_class.value,
            "withheld_slots": list(self.withheld_slots),
            "added_slots": list(self.added_slots),
            "values_differ": self.values_differ,
            "permits_representation_claim": self.permits_representation_claim,
            "basis": self.basis,
        }


def derive_intervention_class(
    baseline: WorkspaceProjectionIdentity, candidate: WorkspaceProjectionIdentity
) -> DerivedInterventionClass:
    """Type a comparison from the two projection identities, not from a label anyone wrote."""

    baseline_slots = set(baseline.exposed_slots)
    candidate_slots = set(candidate.exposed_slots)
    withheld = tuple(sorted(baseline_slots - candidate_slots))
    added = tuple(sorted(candidate_slots - baseline_slots))
    values_differ = baseline.information_digest != candidate.information_digest
    if not withheld and not added and not values_differ:
        return DerivedInterventionClass(
            intervention_class=InterventionClass.R_ONLY,
            withheld_slots=(),
            added_slots=(),
            values_differ=False,
            basis="identical declared slots and identical declared values: only rendering differs",
        )
    if withheld or added:
        basis = (
            f"declared slot set differs (withheld={list(withheld)}, added={list(added)}): the "
            "projection changed, so this is not a representation change (manual §12.3, §26.3)"
        )
    else:
        basis = (
            "declared slots agree but a declared value differs: the information exposed is not "
            "the same, so visible-information parity does not hold and must not be asserted"
        )
    return DerivedInterventionClass(
        intervention_class=InterventionClass.P_CHANGE,
        withheld_slots=withheld,
        added_slots=added,
        values_differ=values_differ,
        basis=basis,
    )


def derive_arm_intervention_class(
    candidate: DeclarationDerivedRenderer,
    envelopes: Sequence[BackendStateEnvelope],
    *,
    baseline: DeclarationDerivedRenderer | None = None,
    workspace_kind: str = LEAN_TACTIC_WORKSPACE,
) -> DerivedInterventionClass:
    """Derive one arm's class over a whole bank, failing closed.

    A single state at which the candidate declares something different is enough to make the arm
    ``P_CHANGE``: the class of a comparison is the weakest it is anywhere, never the strongest it
    is somewhere.  An empty bank raises rather than defaulting to ``R_ONLY`` — that default is the
    exact mistake ``classify_intervention`` refuses to make.
    """

    if not envelopes:
        raise ValueError("an intervention class cannot be derived from an empty bank")
    reference = baseline if baseline is not None else ARMS["R_A"]
    verdicts = [
        derive_intervention_class(
            _declaration_identity(reference, envelope, workspace_kind=workspace_kind),
            _declaration_identity(candidate, envelope, workspace_kind=workspace_kind),
        )
        for envelope in envelopes
    ]
    for verdict in verdicts:
        if verdict.intervention_class is not InterventionClass.R_ONLY:
            return verdict
    return verdicts[0]


def _declaration_identity(
    renderer: DeclarationDerivedRenderer,
    envelope: BackendStateEnvelope,
    *,
    workspace_kind: str,
) -> WorkspaceProjectionIdentity:
    """The projection identity of a declaration alone, without rendering.

    Used by the class derivation so that an arm which *refuses* a state can still be typed: the
    class follows from what the renderer declares, not from whether it managed to lay it out.
    """

    return WorkspaceProjectionIdentity.from_information(
        renderer.declare_information(envelope),
        workspace_kind=workspace_kind,
        renderer_id=str(getattr(renderer, "renderer_id", "")),
        slots_were_declared=True,
    )


def project_arm(
    renderer: DeclarationDerivedRenderer,
    envelope: BackendStateEnvelope,
    *,
    baseline: DeclarationDerivedRenderer | None = None,
    workspace_kind: str = LEAN_TACTIC_WORKSPACE,
) -> WorkspaceProjection:
    """Project a state through one arm, stamping the *derived* intervention class.

    The class written into the artefact is computed from the arm's declaration against the
    baseline's at this state.  No caller can pass a class in, so no artefact can carry a class its
    renderer did not earn.
    """

    reference = baseline if baseline is not None else ARMS["R_A"]
    derived = derive_intervention_class(
        _declaration_identity(reference, envelope, workspace_kind=workspace_kind),
        _declaration_identity(renderer, envelope, workspace_kind=workspace_kind),
    )
    return project_workspace(
        renderer,
        envelope,
        workspace_kind=workspace_kind,
        intervention_class=derived.intervention_class,
    )


def declared_gene_classes() -> dict[str, InterventionClass]:
    """A copy of the gene table, so a test can state what it does and does not contain.

    Read-only by construction: this module does not own ``arena/evolution/record.py`` and does not
    edit it.  See :data:`GOAL_VISIBILITY_GENE`.
    """

    return dict(GENE_INTERVENTION_CLASS)
