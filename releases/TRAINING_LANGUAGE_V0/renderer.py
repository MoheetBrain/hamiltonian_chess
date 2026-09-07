"""TL0 renderer: canonical structure -> model-facing text.

``render_state`` is a pure function of ``(state, config)``.  Three properties make that
claim checkable rather than aspirational, and ``tests/releases/test_determinism.py``
checks all three:

1. **No ambient input.**  This module imports no source of nondeterminism -- no ``random``,
   ``time``, ``uuid``, ``datetime``, ``os`` or ``secrets``.  A static scan over the whole
   package asserts it, mirroring the method used in ``docs/ROUTE_B_PARITY_AUDIT.md``.
2. **No dict-order dependence.**  The only mappings TL0 holds are attribute tuples, and
   :func:`core.normalise_attributes` sorts them at construction.  Everything else is an
   ordered tuple, so emission order is *data*, not iteration order.
3. **No hash-seed dependence.**  The test suite renders the same state in two subprocesses
   under different ``PYTHONHASHSEED`` values and compares bytes.

The renderer omits fields that carry no information (an empty warrant, an empty attribute
map, an empty sub-record list).  That is still a function of the state alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from .core import (
    DOCUMENT_MAGIC,
    Action,
    Attributes,
    Claim,
    Decl,
    Evidence,
    Extension,
    Goal,
    LibraryRef,
    Obligation,
    Scope,
    State,
    Term,
    Type,
    Value,
)
from .syntax import HOLE, atom_or_quote, quote


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """The renderer's entire configuration.  Small on purpose.

    Only the default is lossless.  Dropping actions or extensions produces a *view*, which
    is legitimate for prompting but cannot round-trip; :attr:`is_lossless` says so and the
    conformance tests only assert exact round-trip for lossless configurations.
    """

    include_actions: bool = True
    include_extensions: bool = True
    include_libraries: bool = True
    indent: str = "  "

    @property
    def is_lossless(self) -> bool:
        return self.include_actions and self.include_extensions and self.include_libraries

    def describe(self) -> tuple[tuple[str, str], ...]:
        return (
            ("include_actions", str(self.include_actions)),
            ("include_extensions", str(self.include_extensions)),
            ("include_libraries", str(self.include_libraries)),
            ("indent", repr(self.indent)),
        )


LOSSLESS = RenderConfig()
PROMPT_VIEW = RenderConfig(include_actions=False)


def render_value(value: Value | None) -> str:
    if value is None:
        return HOLE
    if isinstance(value, bool):
        return f"#b {'true' if value else 'false'}"
    if isinstance(value, int):
        return f"#i {value}"
    if isinstance(value, float):
        return f"#f {value!r}"
    return f"#s {quote(value)}"


def render_type(sort: Type) -> str:
    """Render a structured type.  This spelling is the canonical flat-string encoding too."""

    body = " ".join([atom_or_quote(sort.head), *(render_type(item) for item in sort.params)])
    return f"[{body}]"


def render_attributes(attributes: Attributes) -> str:
    pairs = " ".join(f"{atom_or_quote(key)}={quote(item)}" for key, item in attributes)
    return f"{{{pairs}}}"


def render_term(term: Term) -> str:
    parts = [atom_or_quote(term.op), render_type(term.sort), render_value(term.value)]
    parts.extend(render_term(item) for item in term.args)
    if term.attributes:
        parts.append(render_attributes(term.attributes))
    return f"({' '.join(parts)})"


def _optional_id(value: str | None) -> str:
    return HOLE if value is None else value


def _optional_text(value: str | None) -> str:
    return HOLE if value is None else quote(value)


def _tail(attributes: Attributes) -> list[str]:
    return [render_attributes(attributes)] if attributes else []


def _library_line(item: LibraryRef) -> str:
    return " ".join(["lib", item.library_id, atom_or_quote(item.version)])


def _scope_line(item: Scope) -> str:
    return " ".join(["scope", item.scope_id, _optional_id(item.parent_id)])


def _decl_line(item: Decl) -> str:
    parts = [
        "decl",
        item.decl_id,
        atom_or_quote(item.name),
        render_type(item.sort),
        item.scope_id,
        item.kind.value,
        HOLE if item.value is None else render_term(item.value),
        *_tail(item.attributes),
    ]
    return " ".join(parts)


def _claim_line(item: Claim) -> str:
    parts = [
        "claim",
        item.claim_id,
        item.role.value,
        item.scope_id,
        item.status.value,
        _optional_id(item.evidence_id),
        render_term(item.statement),
        *_tail(item.attributes),
    ]
    return " ".join(parts)


def _goal_line(item: Goal) -> str:
    parts = [
        "goal",
        item.goal_id,
        item.scope_id,
        item.status.value,
        "1" if item.focused else "0",
        _optional_id(item.evidence_id),
        render_term(item.statement),
        *_tail(item.attributes),
    ]
    return " ".join(parts)


def _obligation_line(item: Obligation, keyword: str = "oblig") -> str:
    parts = [
        keyword,
        item.obligation_id,
        item.scope_id,
        item.status.value,
        atom_or_quote(item.source),
        _optional_id(item.evidence_id),
        render_term(item.statement),
        *_tail(item.attributes),
    ]
    return " ".join(parts)


def _evidence_line(item: Evidence) -> str:
    parts = [
        "evid",
        item.evidence_id,
        item.status.value,
        quote(item.verifier),
        quote(item.verifier_version),
        _optional_text(item.certificate_hash),
        quote(item.details),
        *_tail(item.attributes),
    ]
    return " ".join(parts)


def _extension_line(item: Extension) -> str:
    return " ".join(["ext", item.owner_id, atom_or_quote(item.key), quote(item.payload)])


def _action_lines(item: Action, config: RenderConfig) -> list[str]:
    head = " ".join(
        [
            "act",
            item.action_id,
            atom_or_quote(item.operation),
            item.status.value,
            _optional_id(item.evidence_id),
            *_tail(item.attributes),
        ]
    )
    lines = [head]
    pad = config.indent
    lines.extend(f"{pad}target {target}" for target in item.targets)
    lines.extend(f"{pad}arg {render_term(argument)}" for argument in item.arguments)
    lines.extend(f"{pad}pre {render_term(condition)}" for condition in item.preconditions)
    if item.warrant:
        lines.append(f"{pad}warrant {quote(item.warrant)}")
    lines.extend(
        f"{pad}{_obligation_line(obligation, 'gen')}" for obligation in item.generated_obligations
    )
    lines.append("end")
    return lines


def render_state(state: State, config: RenderConfig = LOSSLESS) -> str:
    """Render a TL0 state.  Pure function of ``(state, config)``; ends with a newline."""

    lines: list[str] = [f"{DOCUMENT_MAGIC} {state.language_version} {state.state_id}"]
    if config.include_libraries:
        lines.extend(_library_line(item) for item in state.libraries)
    lines.extend(_scope_line(item) for item in state.scopes)
    lines.extend(_decl_line(item) for item in state.declarations)
    lines.extend(_claim_line(item) for item in state.claims)
    lines.extend(_goal_line(item) for item in state.goals)
    lines.extend(_obligation_line(item) for item in state.obligations)
    lines.extend(_evidence_line(item) for item in state.evidence)
    lines.extend(f"subst {name} {render_term(term)}" for name, term in state.substitution)
    lines.extend(
        f"dep {owner} {reference}"
        for owner, references in _dependency_lines(state)
        for reference in references
    )
    if config.include_actions:
        for action in state.actions:
            lines.extend(_action_lines(action, config))
    if config.include_extensions:
        lines.extend(_extension_line(item) for item in state.extensions)
    lines.append(f"status {atom_or_quote(state.terminal_status)}")
    return "\n".join(lines) + "\n"


def _dependency_lines(state: State) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (
        *((item.claim_id, item.depends_on) for item in state.claims if item.depends_on),
        *((item.evidence_id, item.depends_on) for item in state.evidence if item.depends_on),
    )


__all__ = [
    "LOSSLESS",
    "PROMPT_VIEW",
    "RenderConfig",
    "render_attributes",
    "render_state",
    "render_term",
    "render_type",
    "render_value",
]
