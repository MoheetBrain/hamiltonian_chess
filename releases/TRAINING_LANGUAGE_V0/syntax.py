"""TL0 lexical layer: the only place bytes and tokens meet.

The grammar is four bracket kinds and three token kinds.  Keeping it this small is what
makes the parser total and the renderer trivially deterministic::

    document := "TL0" SP version SP state_id NL record*
    record   := KEYWORD field* NL                     -- one physical line
    field    := ATOM | STRING | type | term | attrs
    type     := "[" ATOM type* "]"
    term     := "(" ATOM type value term* attrs? ")"
    value    := "_" | "#i" ATOM | "#f" ATOM | "#b" ATOM | "#s" STRING
    attrs    := "{" (ATOM "=" STRING)* "}"

``act`` is the one multi-line record; it is a block closed by ``end``.  Nothing else
spans a line, and no rendered token ever contains a raw newline, so a document may always
be split on ``\\n`` before tokenising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .core import TL0Error

#: Characters that may appear in a bare atom.  Deliberately excludes the six structural
#: characters, ``=``, ``#`` and ``"`` so that tokenisation never needs lookahead.
ATOM_RE = re.compile(r"^[A-Za-z0-9_.:\-+*/<>?!~^$%@']+$")
_ATOM_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:-+*/<>?!~^$%@'"
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_UNESCAPES = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}

HOLE = "_"
VALUE_TAGS = ("#s", "#i", "#f", "#b")


class TL0SyntaxError(TL0Error):
    """The text is not a well-formed TL0 document."""


class TokenKind(StrEnum):
    ATOM = "ATOM"
    STRING = "STRING"
    PUNCT = "PUNCT"
    TAG = "TAG"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    column: int


def quote(text: str) -> str:
    """Render text as a TL0 string literal.  Total: every ``str`` has a spelling."""

    out = ['"']
    for char in text:
        if char in _ESCAPES:
            out.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def atom_or_quote(text: str) -> str:
    """Emit a bare atom when the text is atom-shaped, otherwise a quoted string."""

    if text and ATOM_RE.match(text):
        return text
    return quote(text)


def tokenize(line: str, *, line_number: int = 0) -> tuple[Token, ...]:
    """Split one physical line into tokens.  Raises on any character TL0 cannot spell."""

    tokens: list[Token] = []
    index = 0
    size = len(line)
    while index < size:
        char = line[index]
        if char in " \t":
            index += 1
            continue
        if char in "()[]{}=":
            tokens.append(Token(TokenKind.PUNCT, char, index))
            index += 1
            continue
        if char == "#":
            tag = line[index : index + 2]
            if tag not in VALUE_TAGS:
                raise TL0SyntaxError(f"line {line_number}: unknown value tag {tag!r}")
            tokens.append(Token(TokenKind.TAG, tag, index))
            index += 2
            continue
        if char == '"':
            start = index
            text, index = _read_string(line, index, line_number)
            tokens.append(Token(TokenKind.STRING, text, start))
            continue
        if char in _ATOM_CHARS:
            start = index
            while index < size and line[index] in _ATOM_CHARS:
                index += 1
            tokens.append(Token(TokenKind.ATOM, line[start:index], start))
            continue
        raise TL0SyntaxError(f"line {line_number}: unexpected character {char!r} at {index}")
    return tuple(tokens)


def _read_string(line: str, start: int, line_number: int) -> tuple[str, int]:
    index = start + 1
    size = len(line)
    out: list[str] = []
    while index < size:
        char = line[index]
        if char == '"':
            return "".join(out), index + 1
        if char != "\\":
            out.append(char)
            index += 1
            continue
        index += 1
        if index >= size:
            break
        marker = line[index]
        if marker in _UNESCAPES:
            out.append(_UNESCAPES[marker])
            index += 1
            continue
        if marker == "u":
            digits = line[index + 1 : index + 5]
            if len(digits) != 4 or any(item not in "0123456789abcdefABCDEF" for item in digits):
                raise TL0SyntaxError(f"line {line_number}: malformed \\u escape")
            out.append(chr(int(digits, 16)))
            index += 5
            continue
        raise TL0SyntaxError(f"line {line_number}: unknown escape \\{marker}")
    raise TL0SyntaxError(f"line {line_number}: unterminated string literal")


class Cursor:
    """A fail-closed reader over one line's tokens."""

    def __init__(self, tokens: tuple[Token, ...], *, line_number: int, line: str) -> None:
        self._tokens = tokens
        self._index = 0
        self.line_number = line_number
        self.line = line

    def fail(self, message: str) -> TL0SyntaxError:
        return TL0SyntaxError(f"line {self.line_number}: {message} in {self.line.strip()!r}")

    @property
    def done(self) -> bool:
        return self._index >= len(self._tokens)

    def peek(self) -> Token | None:
        return None if self.done else self._tokens[self._index]

    def next(self) -> Token:
        if self.done:
            raise self.fail("unexpected end of record")
        token = self._tokens[self._index]
        self._index += 1
        return token

    def at_punct(self, char: str) -> bool:
        token = self.peek()
        return token is not None and token.kind is TokenKind.PUNCT and token.text == char

    def expect_punct(self, char: str) -> None:
        token = self.next()
        if token.kind is not TokenKind.PUNCT or token.text != char:
            raise self.fail(f"expected {char!r}, got {token.text!r}")

    def read_atom(self) -> str:
        token = self.next()
        if token.kind is not TokenKind.ATOM:
            raise self.fail(f"expected an atom, got {token.text!r}")
        return token.text

    def read_text(self) -> str:
        """Read a field that may be spelled either bare or quoted."""

        token = self.next()
        if token.kind not in (TokenKind.ATOM, TokenKind.STRING):
            raise self.fail(f"expected text, got {token.text!r}")
        return token.text

    def read_quoted(self) -> str:
        """Read a field the renderer always quotes, so ``"_"`` never collides with a hole."""

        token = self.next()
        if token.kind is not TokenKind.STRING:
            raise self.fail(f"expected a quoted string, got {token.text!r}")
        return token.text

    def read_optional_quoted(self) -> str | None:
        token = self.next()
        if token.kind is TokenKind.STRING:
            return token.text
        if token.kind is TokenKind.ATOM and token.text == HOLE:
            return None
        raise self.fail(f"expected a quoted string or {HOLE!r}, got {token.text!r}")

    def read_optional_id(self) -> str | None:
        text = self.read_atom()
        return None if text == HOLE else text

    def finish(self) -> None:
        token = self.peek()
        if token is not None:
            raise self.fail(f"unexpected trailing token {token.text!r}")


__all__ = [
    "ATOM_RE",
    "HOLE",
    "VALUE_TAGS",
    "Cursor",
    "TL0SyntaxError",
    "Token",
    "TokenKind",
    "atom_or_quote",
    "quote",
    "tokenize",
]
