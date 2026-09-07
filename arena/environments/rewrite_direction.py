"""Rewrite-direction task family v1: was an equation applied left-to-right or right-to-left?

Motivation.  A ``rw`` step in Lean applies an equation ``lhs = rhs`` in one of two
directions.  Forward replaces occurrences of ``lhs`` by ``rhs``; reverse (written ``←`` in
Lean surface syntax) replaces occurrences of ``rhs`` by ``lhs``.  Choosing the direction is a
real, small, decidable act of mathematical reading: you must see which side of the equation
actually matches somewhere in the state you are looking at.  The label is recorded by the
proof author and recovered deterministically from the tactic text, so it needs no Lean build,
no solver and no model call.

Item shape.  Each item shows

* the proof state *before* the tactic ran (hypotheses and goal),
* the identity of the equation being applied (its mathlib name),
* the equation's statement and its two sides, presented as neutral ``Side A`` / ``Side B``,
* where the rewrite acts (the goal, or a named hypothesis),

and asks for a binary choice between FORWARD (Side A becomes Side B) and REVERSE (Side B
becomes Side A).  The option order is permuted per item from the seed, so option position
carries no signal.

**The state after the tactic is deliberately not shown.**  Showing it would turn the family
into a diffing exercise and would reintroduce the "the goal got bigger, so it was a reverse
rewrite" shortcut.  Withholding it also makes the question the honest one: given only what
the prover could see at the moment of choosing, which side of the equation matches?

Leakage discipline.  The recorded tactic text, the ``←`` / ``<-`` tokens and the
``annotated_tactic`` ``<a>`` markup are the answer, so none of them is ever stored on a
rendered item.  :func:`leakage_violations` re-derives that guarantee from the actual rendered
strings, and the generator additionally discards any candidate whose state or statement text
contains an arrow token at all, so the invariant is exact rather than approximate.

Source discipline.  Only ``random/train.json`` and ``corpus.jsonl`` of LeanDojo Benchmark 4
are permitted.  ``novel_premises/{val,test}.json`` and ``random/{val,test}.json`` are sealed
promotion / OOD pools; :data:`SEALED_RELATIVE_PATHS` names them and
:func:`assert_source_permitted` refuses them.

Trust.  The direction label is Tier A: it is Lean surface syntax written by the proof author
and preserved verbatim by LeanDojo's tracer.  The equation sides are Tier B: Arena
re-derives them from the premise's recorded signature with the parser in this module, and
that parse is a heuristic over pretty-printed text, not an elaboration.  The difficulty level
is Tier D annotation.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

ENVIRONMENT_VERSION = "arena-rewrite-direction-v1.0.0"
GENERATOR_VERSION = "arena-rewrite-direction-generator-v1.0.0"
PARSER_VERSION = "arena-rw-signature-parser-v1.0.0"

DATASET_NAME = "LeanDojo Benchmark 4"
DATASET_VERSION = "2.0.0"
MATHLIB4_COMMIT = "29dcec074de168ac2bf835a77ef68bbe069194c5"
DATASET_LICENSE = "mathlib4 is Apache-2.0; LeanDojo Benchmark 4 redistributes it under CC-BY-4.0"

#: The only split of the benchmark this family is allowed to read.
PERMITTED_SPLIT = "train"
#: Sealed promotion / OOD pools.  Reading one invalidates the experiment.
SEALED_RELATIVE_PATHS = frozenset(
    {
        "novel_premises/val.json",
        "novel_premises/test.json",
        "random/val.json",
        "random/test.json",
    }
)

Direction = Literal["FORWARD", "REVERSE"]
FORWARD: Direction = "FORWARD"
REVERSE: Direction = "REVERSE"

#: Rewrite heads whose bracket elements are single-shot equation applications.  ``simp_rw``
#: (rewrites to a fixpoint) and ``nth_rw`` / ``nth_rewrite`` (occurrence-indexed) have
#: different operational semantics, so they are counted in the census but excluded from the
#: item population, which is kept semantically uniform.
ITEM_HEADS = frozenset({"rw", "rewrite", "erw", "rwa", "rw_mod_cast"})
#: Everything counted by the census, including the heads excluded from items.
CENSUS_HEADS = ITEM_HEADS | {"simp_rw", "nth_rw", "nth_rewrite", "transfer_rw"}

#: Surface spellings of the reverse marker.  Both appear in mathlib.
REVERSE_TOKENS = ("←", "<-")

_HEAD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_']*)")
_ANCHOR_RE = re.compile(r"</?a>")
_DECL_KEYWORD_RE = re.compile(r"(?:^|\s)(theorem|lemma|abbrev|def|instance|example)\s")
_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?₀-₉]*|\d+|[^\sA-Za-z0-9_]")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'₀-₉]*")

_OPENERS = "([{⟨⦃"
_CLOSERS = ")]}⟩⦄"

#: Name affixes a shallow reader might use as a direction cue.  Probed by the shortcut gate.
NAME_AFFIX_CUES = (
    "symm",
    "comm",
    "_eq_",
    "_def",
    "iff",
    "assoc",
    "succ",
    "cast",
    "_zero",
    "_one",
)


class SealedSplitError(RuntimeError):
    """Raised when a caller tries to read one of the sealed promotion / OOD pools."""


def assert_source_permitted(relative_path: str) -> None:
    """Refuse any sealed split.  Call this before opening a benchmark file."""

    normalised = relative_path.replace("\\", "/").lstrip("./")
    for sealed in SEALED_RELATIVE_PATHS:
        if normalised == sealed or normalised.endswith("/" + sealed):
            raise SealedSplitError(
                f"{relative_path!r} is a SEALED promotion/OOD pool; only "
                f"random/train.json and corpus.jsonl may be read"
            )


# ---------------------------------------------------------------------------
# balanced-bracket scanning
# ---------------------------------------------------------------------------
def _matching_bracket(text: str, open_index: int) -> int:
    """Index of the ``]`` matching the ``[`` at ``open_index``, or ``-1``."""

    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_top_level(body: str, separator: str = ",") -> list[str]:
    """Split on ``separator`` occurrences that are not nested inside brackets."""

    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
        if char == separator and depth <= 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _find_top_level(text: str, predicate: Any, start: int = 0) -> int:
    """First index at or after ``start`` where ``predicate(text, index)`` holds at depth 0."""

    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char in _OPENERS:
            depth += 1
            continue
        if char in _CLOSERS:
            depth -= 1
            continue
        if depth <= 0 and predicate(text, index):
            return index
    return -1


# ---------------------------------------------------------------------------
# tactic parsing
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ParsedRewrite:
    """The structure of one recorded rewrite tactic, before any item is built."""

    head: str
    #: Direction of every bracket element, in source order.
    element_directions: tuple[Direction, ...]
    #: Surface text of the first bracket element, arrow token already removed.
    first_element: str
    #: Resolved mathlib name of the first element's head, if the tracer resolved it.
    first_premise: str | None
    #: ``None`` for a goal rewrite, else the ``at`` location text, e.g. ``"hn"``.
    location: str | None

    @property
    def direction(self) -> Direction:
        """Direction of the first element: the only one that acts on the observed state."""

        return self.element_directions[0]

    @property
    def is_mixed(self) -> bool:
        """True when one bracket contains both a forward and a reverse rewrite."""

        return len(set(self.element_directions)) > 1


def tactic_head(tactic: str) -> str:
    """The leading identifier of a recorded tactic, or ``""`` if it has none."""

    match = _HEAD_RE.match(tactic.strip())
    return match.group(1) if match else ""


def strip_reverse_marker(element: str) -> tuple[str, Direction]:
    """Remove a leading ``←`` / ``<-`` and report the direction it encoded."""

    text = element.strip()
    for token in REVERSE_TOKENS:
        if text.startswith(token):
            return text[len(token) :].strip(), REVERSE
    return text, FORWARD


def parse_rewrite_tactic(tactic: str, annotated_tactic: str = "") -> ParsedRewrite | None:
    """Parse a recorded rewrite tactic, or return ``None`` if it is not one we handle.

    ``annotated_tactic`` is used only to recover the *resolved* mathlib name of the first
    bracket element (LeanDojo wraps resolved premises in ``<a>`` markup).  Neither string is
    ever carried onto a rendered item.
    """

    text = tactic.strip()
    head_match = _HEAD_RE.match(text)
    if head_match is None:
        return None
    head = head_match.group(1)
    if head not in CENSUS_HEADS:
        return None
    open_index = text.find("[")
    if open_index < 0:
        return None
    close_index = _matching_bracket(text, open_index)
    if close_index < 0:
        return None
    elements = split_top_level(text[open_index + 1 : close_index])
    if not elements:
        return None

    directions: list[Direction] = []
    first_surface = ""
    for position, element in enumerate(elements):
        stripped, direction = strip_reverse_marker(element)
        directions.append(direction)
        if position == 0:
            first_surface = stripped

    trailer = text[close_index + 1 :].strip()
    location: str | None = None
    if trailer:
        if not trailer.startswith("at "):
            # `rw [...] <;> simp`, `rw [...] |>.mp` and friends: the recorded state pair no
            # longer isolates the rewrite, so refuse rather than mislabel.
            return None
        location = trailer[3:].strip()
        if not location:
            return None

    return ParsedRewrite(
        head=head,
        element_directions=tuple(directions),
        first_element=first_surface,
        first_premise=_resolve_first_premise(annotated_tactic),
        location=location,
    )


def _resolve_first_premise(annotated_tactic: str) -> str | None:
    """The mathlib name the tracer attached to the first bracket element, if any.

    LeanDojo rewrites resolved constants as ``<a>Full.Name</a>`` inside the tactic text.  We
    take the first anchor that lies inside the first bracket element, which is exactly the
    head constant of the equation being applied.
    """

    if not annotated_tactic:
        return None
    open_index = annotated_tactic.find("[")
    if open_index < 0:
        return None
    close_index = _matching_bracket(annotated_tactic, open_index)
    if close_index < 0:
        return None
    elements = split_top_level(annotated_tactic[open_index + 1 : close_index])
    if not elements:
        return None
    first = elements[0]
    anchor = re.search(r"<a>(.*?)</a>", first)
    if anchor is None:
        return None
    return anchor.group(1).strip() or None


# ---------------------------------------------------------------------------
# equation extraction from a recorded premise signature
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LemmaEquation:
    """The two sides of an equation recovered from a premise's recorded signature."""

    #: The declaration's type as printed, quantifiers and hypotheses included.
    statement: str
    #: Text left of the top-level relation symbol.
    lhs: str
    #: Text right of it.
    rhs: str
    #: ``"="`` or ``"↔"``.
    relation: str
    #: Binder names stripped from the front of the statement; treated as wildcards.
    binders: tuple[str, ...]


def _is_eq_symbol(text: str, index: int) -> bool:
    if text[index] != "=":
        return False
    if index and text[index - 1] in "=<>!:≠+-*/^≤≥":
        return False
    # `==`, `=>` and friends are not the equation's relation symbol
    return not (index + 1 < len(text) and text[index + 1] in "=>")


def _is_iff_symbol(text: str, index: int) -> bool:
    return text[index] == "↔"


def _is_comma(text: str, index: int) -> bool:
    return text[index] == ","


def _is_arrow(text: str, index: int) -> bool:
    return text[index] == "→"


def _is_colon(text: str, index: int) -> bool:
    if text[index] != ":":
        return False
    return not (index + 1 < len(text) and text[index + 1] == "=")


def _is_assign(text: str, index: int) -> bool:
    return text[index] == ":" and index + 1 < len(text) and text[index + 1] == "="


def _strip_attributes(code: str) -> str:
    """Drop leading ``@[...]`` attribute blocks."""

    text = code.strip()
    while text.startswith("@["):
        close = _matching_bracket(text, text.index("["))
        if close < 0:
            return text
        text = text[close + 1 :].strip()
    return text


def parse_equation(code: str) -> LemmaEquation | None:
    """Recover ``lhs`` and ``rhs`` from a premise's recorded declaration signature.

    LeanDojo's ``corpus.jsonl`` stores the signature with the proof term already elided, e.g.
    ``theorem mul_add_mod (m x y : Nat) : (m * x + y) % m = y % m``.  The parse is textual:
    strip attributes and modifiers, skip the declaration name and binders to the top-level
    ``:``, drop leading ``∀`` quantifiers and any hypothesis arrows, then split on the
    top-level ``=`` or ``↔``.  Anything that does not end in a top-level equation or iff
    returns ``None`` and is discarded by the generator.
    """

    text = _strip_attributes(code)
    keyword = _DECL_KEYWORD_RE.search(" " + text)
    if keyword is None:
        return None
    cursor = keyword.end() - 1  # the search ran against a space-prefixed copy
    rest = text[cursor:].lstrip()
    # skip the declaration name
    name_match = _HEAD_RE.match(rest)
    if name_match is None:
        return None
    rest = rest[name_match.end() :]
    while rest[:1] == "." or rest[:1].isalnum() or rest[:1] in "_'":
        follow = _HEAD_RE.match(rest[1:]) if rest[:1] == "." else None
        if follow is None:
            break
        rest = rest[1 + follow.end() :]

    colon = _find_top_level(rest, _is_colon)
    if colon < 0:
        return None
    statement = rest[colon + 1 :].strip()
    # `corpus.jsonl` sometimes stores the whole declaration, proof term included.  The proof
    # body is not part of the statement and may itself contain rewrite tactic text, so cut it
    # at the top-level `:=` before anything else looks at the string.
    assign = _find_top_level(statement, _is_assign)
    if assign >= 0:
        statement = statement[:assign].strip()
    if not statement:
        return None

    binders: list[str] = []
    body = statement
    while body.startswith(("∀", "∃")):
        comma = _find_top_level(body, _is_comma)
        if comma < 0:
            break
        binders.extend(_WORD_RE.findall(body[1:comma]))
        body = body[comma + 1 :].strip()

    # a hypothesis arrow at the top level: the conclusion is what `rw` actually applies
    while True:
        arrow = _find_top_level(body, _is_arrow)
        if arrow < 0:
            break
        body = body[arrow + 1 :].strip()

    # `↔` binds looser than `=` in Lean, so `range f = ⊤ ↔ Surjective f` is an iff whose left
    # side is an equation.  Splitting on `=` first would silently mis-slice it, so the looser
    # relation is tried first.
    for predicate, relation in ((_is_iff_symbol, "↔"), (_is_eq_symbol, "=")):
        position = _find_top_level(body, predicate)
        if position < 0:
            continue
        lhs = body[:position].strip()
        rhs = body[position + len(relation) :].strip()
        if not lhs or not rhs:
            return None
        if _find_top_level(rhs, predicate) >= 0:
            # two top-level occurrences of the same non-associative relation: the slice is
            # not trustworthy, so refuse rather than emit a wrong equation.
            return None
        return LemmaEquation(
            statement=statement,
            lhs=lhs,
            rhs=rhs,
            relation=relation,
            binders=tuple(dict.fromkeys(binders)),
        )
    return None


# ---------------------------------------------------------------------------
# state helpers
# ---------------------------------------------------------------------------
def goal_target(state: str) -> str:
    """The text right of the last turnstile: the goal a tactic must act on."""

    if "⊢" in state:
        return state.rsplit("⊢", 1)[1].strip()
    return state.strip()


def hypothesis_block(state: str) -> str:
    """Everything left of the last turnstile: the local context."""

    if "⊢" in state:
        return state.rsplit("⊢", 1)[0].strip()
    return ""


def symbol_tokens(text: str) -> list[str]:
    return _SYMBOL_RE.findall(text)


def word_tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text))


def nesting_depth(text: str) -> int:
    """Maximum bracket nesting depth of a printed expression."""

    depth = best = 0
    for char in text:
        if char in _OPENERS:
            depth += 1
            best = max(best, depth)
        elif char in _CLOSERS:
            depth = max(0, depth - 1)
    return best


def count_context_equations(state: str) -> int:
    """Hypotheses whose type is an equation or iff: potential distractor rewrites."""

    total = 0
    for line in hypothesis_block(state).splitlines():
        if ":" not in line:
            continue
        _, _, tail = line.partition(":")
        if _find_top_level(tail, _is_eq_symbol) >= 0 or _find_top_level(tail, _is_iff_symbol) >= 0:
            total += 1
    return total


def _side_signature(side: str, binders: Iterable[str]) -> set[str]:
    """Word tokens of one side that are not binder-bound, i.e. the side's fixed vocabulary."""

    bound = set(binders)
    return {token for token in word_tokens(side) if token not in bound}


def side_occurrences(side: str, binders: Iterable[str], target: str) -> int:
    """How many of the side's distinctive tokens occur in ``target``.

    This is a proxy for higher-order matching, not a matcher: the sides are schematic terms
    whose variables are bound, so an exact substring test would almost never fire.  Counting
    the side's *non-binder* vocabulary against the target is the honest cheap approximation,
    and the shortcut gate measures exactly how far it gets.
    """

    signature = _side_signature(side, binders)
    if not signature:
        return 0
    present = word_tokens(target)
    return sum(1 for token in signature if token in present)


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


# ---------------------------------------------------------------------------
# item construction
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class DifficultyFeatures:
    """Structural facts used to place an item on the ladder.  Tier D annotation."""

    side_similarity: float
    lhs_signature_hits: int
    rhs_signature_hits: int
    decisive_side_margin: int
    target_depth: int
    plausible_sites: int
    context_equations: int
    length_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "side_similarity": round(self.side_similarity, 4),
            "lhs_signature_hits": self.lhs_signature_hits,
            "rhs_signature_hits": self.rhs_signature_hits,
            "decisive_side_margin": self.decisive_side_margin,
            "target_depth": self.target_depth,
            "plausible_sites": self.plausible_sites,
            "context_equations": self.context_equations,
            "length_ratio": round(self.length_ratio, 4),
        }


@dataclass(frozen=True, slots=True)
class RewriteDirectionItem:
    """One binary rewrite-direction question, with the answer held off the rendered text."""

    item_id: str
    #: Proof state as the prover saw it when choosing the direction.
    state: str
    #: The mathlib name of the equation being applied.
    premise_name: str
    #: The equation's recorded signature and its two sides.
    equation: LemmaEquation
    #: ``"the goal"`` or ``"hypothesis `h`"``.
    location_label: str
    #: Permuted option labels; ``answer_index`` says which is correct.
    options: tuple[str, str]
    answer_index: int
    #: The true direction, kept as a label and never rendered.
    direction: Direction
    level: int
    explicit_positive: bool
    features: DifficultyFeatures
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def answer(self) -> Direction:
        value = self.options[self.answer_index]
        return FORWARD if value == FORWARD else REVERSE

    def render(self) -> str:
        """The exact text a solver sees.  Must contain no arrow token and no tactic text."""

        lines = [
            "REWRITE DIRECTION",
            "",
            "A rewrite step applies an equation in one of two directions.",
            "Decide which direction was used here.",
            "",
            "Proof state:",
            self.state,
            "",
            f"Equation: {self.premise_name}",
            f"  statement : {self.equation.statement}",
            f"  Side A    : {self.equation.lhs}",
            f"  Side B    : {self.equation.rhs}",
            f"  relation  : {self.equation.relation}",
            "",
            f"The rewrite acts on: {self.location_label}.",
        ]
        if self.explicit_positive:
            lines.extend(["", self.decisive_statement()])
        lines.extend(
            [
                "",
                "FORWARD means occurrences of Side A were replaced by Side B.",
                "REVERSE means occurrences of Side B were replaced by Side A.",
                "",
                "Options:",
                f"  1. {self.options[0]}",
                f"  2. {self.options[1]}",
                "",
                "Answer with 1 or 2.",
            ]
        )
        return "\n".join(lines)

    def decisive_statement(self) -> str:
        """The L0 explicit-positive arm: state the deciding relation outright."""

        matched = "Side A" if self.direction == FORWARD else "Side B"
        return (
            f"Given fact: the subterm that was rewritten is an instance of {matched}, "
            f"which is the side that occurs in {self.location_label}."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "premise_name": self.premise_name,
            "statement": self.equation.statement,
            "side_a": self.equation.lhs,
            "side_b": self.equation.rhs,
            "relation": self.equation.relation,
            "location_label": self.location_label,
            "options": list(self.options),
            "answer_index": self.answer_index,
            "direction": self.direction,
            "level": self.level,
            "explicit_positive": self.explicit_positive,
            "features": self.features.to_dict(),
            "provenance": dict(self.provenance),
        }


#: Every discard reason the generator can record, so the manifest can report exact rates.
DISCARD_REASONS = (
    "not_a_rewrite_tactic",
    "head_excluded_from_item_population",
    "unparsable_bracket_or_trailer",
    "premise_not_resolved",
    "premise_signature_unavailable",
    "no_top_level_equation",
    "empty_state",
    "arrow_token_in_rendered_text",
    "degenerate_equation_sides",
    "leakage_guard_tripped",
)


def _location_label(location: str | None) -> str:
    if location is None:
        return "the goal"
    cleaned = location.replace("⊢", "the goal").strip()
    return f"hypothesis `{cleaned}`" if cleaned != "the goal" else "the goal"


def _contains_arrow(text: str) -> bool:
    return any(token in text for token in REVERSE_TOKENS)


def leakage_violations(item: RewriteDirectionItem) -> list[str]:
    """Every way the rendered item could betray the answer.  Empty list means clean.

    This is deliberately re-derived from :meth:`RewriteDirectionItem.render` rather than from
    the fields, because rendering is what a solver actually reads.
    """

    rendered = item.render()
    problems: list[str] = []
    for token in REVERSE_TOKENS:
        if token in rendered:
            problems.append(f"reverse marker {token!r} present in rendered item")
    if _ANCHOR_RE.search(rendered):
        problems.append("annotated_tactic <a> markup present in rendered item")
    for head in sorted(CENSUS_HEADS):
        if re.search(rf"\b{re.escape(head)}\s*\[", rendered):
            problems.append(f"tactic text for head {head!r} present in rendered item")
    if not item.explicit_positive and "Given fact:" in rendered:
        problems.append("explicit-positive hint leaked into a non-L0 item")
    return problems


def _difficulty(equation: LemmaEquation, state: str, target: str) -> DifficultyFeatures:
    lhs_hits = side_occurrences(equation.lhs, equation.binders, target)
    rhs_hits = side_occurrences(equation.rhs, equation.binders, target)
    lhs_signature = _side_signature(equation.lhs, equation.binders)
    rhs_signature = _side_signature(equation.rhs, equation.binders)
    distinctive = (lhs_signature ^ rhs_signature) or (lhs_signature | rhs_signature)
    present = word_tokens(target)
    return DifficultyFeatures(
        side_similarity=jaccard(lhs_signature, rhs_signature),
        lhs_signature_hits=lhs_hits,
        rhs_signature_hits=rhs_hits,
        decisive_side_margin=lhs_hits - rhs_hits,
        target_depth=nesting_depth(target),
        plausible_sites=sum(1 for token in distinctive if token in present),
        context_equations=count_context_equations(state),
        length_ratio=(len(equation.lhs) + 1) / (len(equation.rhs) + 1),
    )


#: Bin edges on :func:`difficulty_score`.  ``score <= LADDER_EDGES[0]`` is L1, ``<=
#: LADDER_EDGES[1]`` is L2, anything above is L3.
LADDER_EDGES = (2, 4)


def difficulty_score(features: DifficultyFeatures) -> int:
    """Additive 0-10 difficulty cost over five independent structural axes.

    Each axis contributes 0 (easy), 1 or 2 (hard).  The axes are the ones that actually make
    a direction hard to read, and none of them is item *size*:

    * **side similarity** - the more vocabulary the two sides share, the less a local look
      can tell them apart (``a * b = b * a`` shares everything);
    * **decisiveness** - how strongly one side's distinctive vocabulary out-votes the other's
      in the target;
    * **target nesting depth** - how deeply the rewrite site sits inside the goal;
    * **plausible rewrite sites** - how many candidate positions the reader must weigh;
    * **distractor equalities** - equations in the local context that are not the one being
      applied, any of which could plausibly have been rewritten instead.
    """

    score = 0
    similarity = features.side_similarity
    score += 0 if similarity <= 0.34 else (1 if similarity <= 0.74 else 2)
    margin = abs(features.decisive_side_margin)
    score += 0 if margin >= 2 else (1 if margin == 1 else 2)
    depth = features.target_depth
    score += 0 if depth <= 1 else (1 if depth <= 3 else 2)
    sites = features.plausible_sites
    score += 0 if sites <= 1 else (1 if sites <= 3 else 2)
    equations = features.context_equations
    score += 0 if equations == 0 else (1 if equations <= 2 else 2)
    return score


def difficulty_level(features: DifficultyFeatures) -> int:
    """Place an item on the ladder from structure alone, never from the answer.

    L1  the decisive relation is locally legible: the two sides look different, one side's
        vocabulary dominates the target, the site is shallow and little competes with it.
    L2  intermediate.
    L3  the sides are lexically near-identical or neither dominates, and the site is deep,
        crowded with candidates, or surrounded by distractor equalities.

    L0 is not produced here: it is the explicit-positive control arm, which restates the
    decisive relation outright and is requested separately.

    The bin edges were chosen for ladder occupancy on the controlled pool, not for any gate
    result - the shortcut gate never sees an item's level, so no choice here can move it.
    """

    score = difficulty_score(features)
    if score <= LADDER_EDGES[0]:
        return 1
    if score <= LADDER_EDGES[1]:
        return 2
    return 3


def _item_id(proof_id: str, step_index: int, premise_name: str, explicit_positive: bool) -> str:
    """Stable id.  The L0 arm is included in the digest: an explicit-positive twin is a
    different item from its base and must not collide with it."""

    arm = "L0" if explicit_positive else "core"
    digest = hashlib.sha256(
        f"{GENERATOR_VERSION}|{proof_id}|{step_index}|{premise_name}|{arm}".encode()
    ).hexdigest()
    return f"rwdir-{digest[:16]}"


def build_item(
    step: Mapping[str, Any],
    parsed: ParsedRewrite,
    equation: LemmaEquation,
    premise_name: str,
    *,
    seed: int,
    explicit_positive: bool = False,
) -> RewriteDirectionItem:
    """Assemble one item.  Deterministic in ``(seed, proof_id, step_index, premise_name)``."""

    state = str(step["state_before"])
    target = goal_target(state)
    features = _difficulty(equation, state, target)
    item_id = _item_id(
        str(step["proof_id"]), int(step["step_index"]), premise_name, explicit_positive
    )
    rng = random.Random(f"{seed}|{item_id}")
    options: tuple[str, str] = (FORWARD, REVERSE)
    if rng.random() < 0.5:
        options = (REVERSE, FORWARD)
    return RewriteDirectionItem(
        item_id=item_id,
        state=state,
        premise_name=premise_name,
        equation=equation,
        location_label=_location_label(parsed.location),
        options=options,
        answer_index=options.index(parsed.direction),
        direction=parsed.direction,
        level=0 if explicit_positive else difficulty_level(features),
        explicit_positive=explicit_positive,
        features=features,
        provenance={
            "dataset": DATASET_NAME,
            "dataset_version": DATASET_VERSION,
            "mathlib4_commit": MATHLIB4_COMMIT,
            "split": PERMITTED_SPLIT,
            "source_file": "random/train.json",
            "proof_id": step["proof_id"],
            "file_path": step["file_path"],
            "thm": step["thm"],
            "step_index": step["step_index"],
            "tactic_head": parsed.head,
            "bracket_elements": len(parsed.element_directions),
            "bracket_is_mixed": parsed.is_mixed,
            "environment_version": ENVIRONMENT_VERSION,
            "generator_version": GENERATOR_VERSION,
            "parser_version": PARSER_VERSION,
            "seed": seed,
        },
    )


def generate_items(
    steps: Iterable[Mapping[str, Any]],
    signatures: Mapping[str, str],
    *,
    seed: int = 20260907,
    explicit_positive_every: int = 0,
    discards: dict[str, int] | None = None,
) -> Iterator[RewriteDirectionItem]:
    """Turn recorded train steps into items, counting every discard by reason.

    ``signatures`` maps a mathlib full name to its recorded declaration signature (the
    ``code`` field of ``corpus.jsonl``).  ``explicit_positive_every`` > 0 additionally emits
    an L0 explicit-positive twin for every n-th accepted item.

    The population rule, fixed before any accuracy was measured: **one item per rewrite
    tactic, built from the first bracket element**.  Only the first element acts on the
    recorded ``state_before``; elements after it act on intermediate states LeanDojo does not
    record, so a per-element split would produce items whose question is not answerable from
    what is shown.  Mixed-direction brackets are therefore neither excluded nor split - they
    contribute exactly one item, labelled by their first element's direction.
    """

    tally = discards if discards is not None else {}
    for reason in DISCARD_REASONS:
        tally.setdefault(reason, 0)

    accepted = 0
    for step in steps:
        parsed = parse_rewrite_tactic(str(step["tactic"]), str(step.get("annotated_tactic", "")))
        if parsed is None:
            tally["not_a_rewrite_tactic"] += 1
            continue
        if parsed.head not in ITEM_HEADS:
            tally["head_excluded_from_item_population"] += 1
            continue
        if not parsed.first_element:
            tally["unparsable_bracket_or_trailer"] += 1
            continue
        premise_name = parsed.first_premise
        if premise_name is None:
            tally["premise_not_resolved"] += 1
            continue
        code = signatures.get(premise_name)
        if code is None:
            tally["premise_signature_unavailable"] += 1
            continue
        equation = parse_equation(code)
        if equation is None:
            tally["no_top_level_equation"] += 1
            continue
        if equation.lhs == equation.rhs or not equation.lhs or not equation.rhs:
            tally["degenerate_equation_sides"] += 1
            continue
        state = str(step["state_before"]).strip()
        if not state:
            tally["empty_state"] += 1
            continue
        if _contains_arrow(state) or _contains_arrow(equation.statement):
            # An arrow anywhere in the rendered text would make the leakage invariant
            # approximate instead of exact.  Refusing these keeps the test a hard assertion.
            tally["arrow_token_in_rendered_text"] += 1
            continue

        item = build_item(step, parsed, equation, premise_name, seed=seed)
        if leakage_violations(item):
            # The last line of defence: whatever the parser produced, an item that betrays
            # its own answer never leaves the generator.  Counted, not silently dropped.
            tally["leakage_guard_tripped"] += 1
            continue
        accepted += 1
        yield item
        if explicit_positive_every and accepted % explicit_positive_every == 0:
            yield build_item(
                step, parsed, equation, premise_name, seed=seed, explicit_positive=True
            )


# ---------------------------------------------------------------------------
# balancing
# ---------------------------------------------------------------------------
def balance_items(
    items: Sequence[RewriteDirectionItem], *, seed: int = 20260907
) -> list[RewriteDirectionItem]:
    """Downsample the majority direction so chance on the binary is exactly 0.50.

    Balancing is done by deterministic shuffle-then-truncate keyed on the seed, so the same
    seed reproduces the same subset byte for byte.
    """

    forward = [item for item in items if item.direction == FORWARD]
    reverse = [item for item in items if item.direction == REVERSE]
    keep = min(len(forward), len(reverse))
    rng = random.Random(f"balance|{seed}")
    rng.shuffle(forward)
    rng.shuffle(reverse)
    merged = forward[:keep] + reverse[:keep]
    merged.sort(key=lambda item: item.item_id)
    return merged


def balance_within_lemma(
    items: Sequence[RewriteDirectionItem], *, seed: int = 20260907
) -> list[RewriteDirectionItem]:
    """Balance direction *inside every lemma*, the control against lemma-level recall.

    The v1.0 shortcut gate was breached by predictors that never look at the proof state: a
    character n-gram model over the lemma's name reached 0.675 and the ratio of the two
    sides' printed lengths reached 0.626, because mathlib states a lemma with its "complex"
    side on the left and some lemmas are simply always used in one direction.

    Both are properties of the *lemma*, constant across every item that uses it.  Requiring
    each lemma to contribute exactly as many forward as reverse items therefore makes the
    lemma name, its n-grams, its affixes, its two sides' lengths, their ratio and their
    similarity all exactly uninformative by construction - no fitting can extract signal from
    a feature whose value is identical for both classes.  What survives can only depend on
    the proof state, which is what the family is meant to measure.

    Lemmas the corpus only ever uses in one direction are dropped entirely.
    """

    by_lemma: dict[str, dict[Direction, list[RewriteDirectionItem]]] = {}
    for item in items:
        bucket = by_lemma.setdefault(item.premise_name, {FORWARD: [], REVERSE: []})
        bucket[item.direction].append(item)
    rng = random.Random(f"within-lemma|{seed}")
    kept: list[RewriteDirectionItem] = []
    for name in sorted(by_lemma):
        bucket = by_lemma[name]
        take = min(len(bucket[FORWARD]), len(bucket[REVERSE]))
        if take == 0:
            continue
        for direction in (FORWARD, REVERSE):
            group = sorted(bucket[direction], key=lambda item: item.item_id)
            rng.shuffle(group)
            kept.extend(group[:take])
    kept.sort(key=lambda item: item.item_id)
    return kept


def split_dev(
    items: Sequence[RewriteDirectionItem], *, seed: int = 20260907, holdout_fraction: float = 0.3
) -> tuple[list[RewriteDirectionItem], list[RewriteDirectionItem]]:
    """Split by source file, so a shortcut cannot memorise a file it was fitted on."""

    files = sorted({str(item.provenance["file_path"]) for item in items})
    rng = random.Random(f"split|{seed}")
    rng.shuffle(files)
    cut = int(len(files) * (1.0 - holdout_fraction))
    train_files = set(files[:cut])
    dev_train = [item for item in items if str(item.provenance["file_path"]) in train_files]
    dev_held = [item for item in items if str(item.provenance["file_path"]) not in train_files]
    return dev_train, dev_held


def load_signatures(corpus_path: str) -> dict[str, str]:
    """Map mathlib full name -> recorded declaration signature, from ``corpus.jsonl``."""

    import json

    assert_source_permitted(corpus_path)
    signatures: dict[str, str] = {}
    with open(corpus_path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            for premise in record.get("premises", ()):
                name = premise.get("full_name")
                code = premise.get("code")
                if name and code and name not in signatures:
                    signatures[name] = code
    return signatures
