"""TL0 parser: model-facing text -> canonical structure.

Deterministic and total.  Every record is read by a fail-closed cursor that rejects
missing *and* unknown fields, mirroring the strictness of ``arena/languages/_wire.py``.
The only tolerance is whitespace: leading/trailing spaces and whitespace-only lines are
ignored, because the parser is pointed at model output.  Everything else raises.

``parse_state(render_state(s)) == s`` for every state, under the default lossless
render configuration.
"""

from __future__ import annotations

from .core import (
    DOCUMENT_MAGIC,
    Action,
    Attributes,
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
    Value,
)
from .syntax import HOLE, Cursor, TL0SyntaxError, TokenKind, tokenize


def parse_type(cursor: Cursor) -> Type:
    cursor.expect_punct("[")
    head = cursor.read_text()
    params: list[Type] = []
    while not cursor.at_punct("]"):
        if not cursor.at_punct("["):
            token = cursor.peek()
            raise cursor.fail(f"expected a type parameter, got {token.text!r}" if token else "")
        params.append(parse_type(cursor))
    cursor.expect_punct("]")
    return Type(head, tuple(params))


def parse_value(cursor: Cursor) -> Value | None:
    token = cursor.next()
    if token.kind is TokenKind.ATOM and token.text == HOLE:
        return None
    if token.kind is not TokenKind.TAG:
        raise cursor.fail(f"expected a value slot, got {token.text!r}")
    if token.text == "#s":
        return cursor.read_quoted()
    literal = cursor.read_atom()
    if token.text == "#b":
        if literal not in ("true", "false"):
            raise cursor.fail(f"expected true/false, got {literal!r}")
        return literal == "true"
    try:
        return int(literal) if token.text == "#i" else float(literal)
    except ValueError as error:
        raise cursor.fail(f"malformed {token.text} literal {literal!r}") from error


def parse_attributes(cursor: Cursor) -> Attributes:
    cursor.expect_punct("{")
    pairs: list[tuple[str, str]] = []
    while not cursor.at_punct("}"):
        key = cursor.read_text()
        cursor.expect_punct("=")
        pairs.append((key, cursor.read_quoted()))
    cursor.expect_punct("}")
    return tuple(pairs)


def parse_term(cursor: Cursor) -> Term:
    cursor.expect_punct("(")
    op = cursor.read_text()
    sort = parse_type(cursor)
    value = parse_value(cursor)
    args: list[Term] = []
    attributes: Attributes = ()
    while not cursor.at_punct(")"):
        if cursor.at_punct("("):
            args.append(parse_term(cursor))
            continue
        if cursor.at_punct("{"):
            attributes = parse_attributes(cursor)
            break
        token = cursor.peek()
        raise cursor.fail(f"unexpected {token.text!r} inside a term" if token else "")
    cursor.expect_punct(")")
    return Term(op=op, sort=sort, value=value, args=tuple(args), attributes=attributes)


def _optional_attributes(cursor: Cursor) -> Attributes:
    return parse_attributes(cursor) if cursor.at_punct("{") else ()


def _optional_term(cursor: Cursor) -> Term | None:
    if cursor.at_punct("("):
        return parse_term(cursor)
    token = cursor.next()
    if token.kind is TokenKind.ATOM and token.text == HOLE:
        return None
    raise cursor.fail(f"expected a term or {HOLE!r}, got {token.text!r}")


def _read_obligation(cursor: Cursor) -> Obligation:
    obligation = Obligation(
        obligation_id=cursor.read_atom(),
        scope_id=cursor.read_atom(),
        status=Status(cursor.read_atom()),
        source=cursor.read_text(),
        evidence_id=cursor.read_optional_id(),
        statement=parse_term(cursor),
        attributes=_optional_attributes(cursor),
    )
    cursor.finish()
    return obligation


class _Builder:
    """Accumulates records in encounter order, then assembles one validated state."""

    def __init__(self) -> None:
        self.scopes: list[Scope] = []
        self.libraries: list[LibraryRef] = []
        self.declarations: list[Decl] = []
        self.claims: list[Claim] = []
        self.goals: list[Goal] = []
        self.obligations: list[Obligation] = []
        self.evidence: list[Evidence] = []
        self.substitution: list[tuple[str, Term]] = []
        self.actions: list[Action] = []
        self.extensions: list[Extension] = []
        self.dependencies: list[tuple[str, str]] = []
        self.terminal_status: str | None = None

    def attach_dependencies(self) -> None:
        edges: dict[str, list[str]] = {}
        for owner, reference in self.dependencies:
            edges.setdefault(owner, []).append(reference)
        claim_ids = {item.claim_id for item in self.claims}
        evidence_ids = {item.evidence_id for item in self.evidence}
        for owner in edges:
            if owner not in claim_ids and owner not in evidence_ids:
                raise TL0SyntaxError(f"dep names unknown owner {owner}")
        self.claims = [
            item
            if item.claim_id not in edges
            else Claim(
                claim_id=item.claim_id,
                role=item.role,
                scope_id=item.scope_id,
                statement=item.statement,
                status=item.status,
                evidence_id=item.evidence_id,
                depends_on=tuple(edges[item.claim_id]),
                attributes=item.attributes,
            )
            for item in self.claims
        ]
        self.evidence = [
            item
            if item.evidence_id not in edges
            else Evidence(
                evidence_id=item.evidence_id,
                status=item.status,
                verifier=item.verifier,
                verifier_version=item.verifier_version,
                certificate_hash=item.certificate_hash,
                details=item.details,
                depends_on=tuple(edges[item.evidence_id]),
                attributes=item.attributes,
            )
            for item in self.evidence
        ]

    def build(self, state_id: str, language_version: str) -> State:
        if self.terminal_status is None:
            raise TL0SyntaxError("document has no status record")
        self.attach_dependencies()
        return State(
            state_id=state_id,
            scopes=tuple(self.scopes),
            libraries=tuple(self.libraries),
            declarations=tuple(self.declarations),
            claims=tuple(self.claims),
            goals=tuple(self.goals),
            obligations=tuple(self.obligations),
            evidence=tuple(self.evidence),
            substitution=tuple(self.substitution),
            actions=tuple(self.actions),
            extensions=tuple(self.extensions),
            terminal_status=self.terminal_status,
            language_version=language_version,
        )


def _read_action(cursor: Cursor, lines: list[tuple[int, str]], index: int) -> tuple[Action, int]:
    action_id = cursor.read_atom()
    operation = cursor.read_text()
    status = Status(cursor.read_atom())
    evidence_id = cursor.read_optional_id()
    attributes = _optional_attributes(cursor)
    cursor.finish()

    targets: list[str] = []
    arguments: list[Term] = []
    preconditions: list[Term] = []
    generated: list[Obligation] = []
    warrant = ""
    while True:
        if index >= len(lines):
            raise TL0SyntaxError(f"action {action_id} is not closed by 'end'")
        number, text = lines[index]
        index += 1
        inner = Cursor(tokenize(text, line_number=number), line_number=number, line=text)
        keyword = inner.read_atom()
        if keyword == "end":
            inner.finish()
            break
        if keyword == "target":
            targets.append(inner.read_atom())
        elif keyword == "arg":
            arguments.append(parse_term(inner))
        elif keyword == "pre":
            preconditions.append(parse_term(inner))
        elif keyword == "warrant":
            warrant = inner.read_quoted()
        elif keyword == "gen":
            generated.append(_read_obligation(inner))
            continue
        else:
            raise inner.fail(f"unknown action sub-record {keyword!r}")
        inner.finish()
    action = Action(
        action_id=action_id,
        operation=operation,
        targets=tuple(targets),
        arguments=tuple(arguments),
        warrant=warrant,
        preconditions=tuple(preconditions),
        generated_obligations=tuple(generated),
        status=status,
        evidence_id=evidence_id,
        attributes=attributes,
    )
    return action, index


def _apply_record(builder: _Builder, keyword: str, cursor: Cursor) -> None:
    if keyword == "lib":
        builder.libraries.append(LibraryRef(cursor.read_atom(), cursor.read_text()))
    elif keyword == "scope":
        builder.scopes.append(Scope(cursor.read_atom(), cursor.read_optional_id()))
    elif keyword == "decl":
        builder.declarations.append(
            Decl(
                decl_id=cursor.read_atom(),
                name=cursor.read_text(),
                sort=parse_type(cursor),
                scope_id=cursor.read_atom(),
                kind=DeclKind(cursor.read_atom()),
                value=_optional_term(cursor),
                attributes=_optional_attributes(cursor),
            )
        )
    elif keyword == "claim":
        builder.claims.append(
            Claim(
                claim_id=cursor.read_atom(),
                role=ClaimRole(cursor.read_atom()),
                scope_id=cursor.read_atom(),
                status=Status(cursor.read_atom()),
                evidence_id=cursor.read_optional_id(),
                statement=parse_term(cursor),
                attributes=_optional_attributes(cursor),
            )
        )
    elif keyword == "goal":
        builder.goals.append(
            Goal(
                goal_id=cursor.read_atom(),
                scope_id=cursor.read_atom(),
                status=Status(cursor.read_atom()),
                focused=_read_flag(cursor),
                evidence_id=cursor.read_optional_id(),
                statement=parse_term(cursor),
                attributes=_optional_attributes(cursor),
            )
        )
    elif keyword == "oblig":
        builder.obligations.append(_read_obligation(cursor))
        return
    elif keyword == "evid":
        builder.evidence.append(
            Evidence(
                evidence_id=cursor.read_atom(),
                status=Status(cursor.read_atom()),
                verifier=cursor.read_quoted(),
                verifier_version=cursor.read_quoted(),
                certificate_hash=cursor.read_optional_quoted(),
                details=cursor.read_quoted(),
                attributes=_optional_attributes(cursor),
            )
        )
    elif keyword == "subst":
        builder.substitution.append((cursor.read_atom(), parse_term(cursor)))
    elif keyword == "dep":
        builder.dependencies.append((cursor.read_atom(), cursor.read_atom()))
    elif keyword == "ext":
        builder.extensions.append(
            Extension(cursor.read_atom(), cursor.read_text(), cursor.read_quoted())
        )
    elif keyword == "status":
        if builder.terminal_status is not None:
            raise cursor.fail("duplicate status record")
        builder.terminal_status = cursor.read_text()
    else:
        raise cursor.fail(f"unknown record {keyword!r}")
    cursor.finish()


def _read_flag(cursor: Cursor) -> bool:
    text = cursor.read_atom()
    if text not in ("0", "1"):
        raise cursor.fail(f"expected 0 or 1, got {text!r}")
    return text == "1"


def parse_state(source: str) -> State:
    """Parse a TL0 document.  Raises :class:`core.TL0Error` on anything malformed."""

    if not isinstance(source, str):
        raise TL0SyntaxError("TL0 source must be text")
    lines = [
        (number, text.strip())
        for number, text in enumerate(source.splitlines(), start=1)
        if text.strip()
    ]
    if not lines:
        raise TL0SyntaxError("empty TL0 document")
    number, header = lines[0]
    header_cursor = Cursor(tokenize(header, line_number=number), line_number=number, line=header)
    if header_cursor.read_atom() != DOCUMENT_MAGIC:
        raise header_cursor.fail(f"document must start with {DOCUMENT_MAGIC}")
    language_version = header_cursor.read_text()
    state_id = header_cursor.read_atom()
    header_cursor.finish()

    builder = _Builder()
    try:
        index = 1
        while index < len(lines):
            line_number, text = lines[index]
            index += 1
            cursor = Cursor(
                tokenize(text, line_number=line_number), line_number=line_number, line=text
            )
            keyword = cursor.read_atom()
            if keyword == "act":
                action, index = _read_action(cursor, lines, index)
                builder.actions.append(action)
                continue
            _apply_record(builder, keyword, cursor)
        return builder.build(state_id, language_version)
    except TL0Error:
        raise
    except ValueError as error:
        raise TL0SyntaxError(f"malformed TL0 document: {error}") from error


__all__ = [
    "parse_attributes",
    "parse_state",
    "parse_term",
    "parse_type",
    "parse_value",
]
