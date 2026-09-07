"""Domain vocabulary as data.

This module is the whole of TL0's extension story, and it is deliberately dull.  Adding
algebra, number theory, analysis, probability, topology or combinatorics to TL0 means
adding a :class:`Library` **value**: a list of type heads, operator symbols and operation
names, with one-line summaries.  It never means a new record kind, a new bracket, a new
parser branch or a new renderer branch.

That is the whole point of keeping the core at ten record kinds.  A grammar that grows a
production per domain becomes a moving target that no experiment can hold fixed; a
vocabulary that grows as data leaves the renderer, parser, adapter and their hashes
untouched.  ``tests/releases/test_libraries.py`` pins exactly that: registering a new
library changes what :func:`check_vocabulary` reports and changes **no rendered byte** of
an existing state.
"""

from __future__ import annotations

from dataclasses import dataclass

from arena.canonical.schema import stable_hash

from .core import LibraryRef, State, Term, Type


@dataclass(frozen=True, slots=True)
class OperatorSpec:
    """One term operator.  ``arity`` is ``None`` for variadic operators."""

    symbol: str
    arity: int | None
    result: str
    summary: str


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """One reasoning operation usable as :attr:`core.Action.operation`."""

    name: str
    summary: str


@dataclass(frozen=True, slots=True)
class Library:
    library_id: str
    version: str
    summary: str
    sorts: tuple[str, ...] = ()
    operators: tuple[OperatorSpec, ...] = ()
    operations: tuple[OperationSpec, ...] = ()

    @property
    def ref(self) -> LibraryRef:
        return LibraryRef(self.library_id, self.version)

    def to_dict(self) -> dict[str, object]:
        return {
            "library_id": self.library_id,
            "version": self.version,
            "summary": self.summary,
            "sorts": list(self.sorts),
            "operators": [
                {
                    "symbol": item.symbol,
                    "arity": item.arity,
                    "result": item.result,
                    "summary": item.summary,
                }
                for item in self.operators
            ],
            "operations": [
                {"name": item.name, "summary": item.summary} for item in self.operations
            ],
        }

    @property
    def content_hash(self) -> str:
        return stable_hash(self.to_dict())

    def extend(
        self,
        *,
        library_id: str,
        version: str,
        summary: str,
        sorts: tuple[str, ...] = (),
        operators: tuple[OperatorSpec, ...] = (),
        operations: tuple[OperationSpec, ...] = (),
    ) -> Library:
        """Derive a wider library.  This is the only sanctioned way to add a domain."""

        return Library(
            library_id=library_id,
            version=version,
            summary=summary,
            sorts=tuple(dict.fromkeys((*self.sorts, *sorts))),
            operators=(*self.operators, *operators),
            operations=(*self.operations, *operations),
        )


@dataclass(frozen=True, slots=True)
class VocabularyReport:
    unknown_sorts: tuple[str, ...]
    unknown_operators: tuple[str, ...]
    unknown_operations: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not (self.unknown_sorts or self.unknown_operators or self.unknown_operations)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "unknown_sorts": list(self.unknown_sorts),
            "unknown_operators": list(self.unknown_operators),
            "unknown_operations": list(self.unknown_operations),
        }


def _walk_types(sort: Type) -> tuple[str, ...]:
    return (sort.head, *[head for item in sort.params for head in _walk_types(item)])


def _state_terms(state: State) -> tuple[Term, ...]:
    roots: list[Term] = []
    roots.extend(item.value for item in state.declarations if item.value is not None)
    roots.extend(item.statement for item in state.claims)
    roots.extend(item.statement for item in state.goals)
    roots.extend(item.statement for item in state.obligations)
    for name, term in state.substitution:
        del name
        roots.append(term)
    for action in state.actions:
        roots.extend(action.arguments)
        roots.extend(action.preconditions)
        roots.extend(item.statement for item in action.generated_obligations)
    return tuple(node for root in roots for node in root.walk())


def check_vocabulary(state: State, libraries: tuple[Library, ...]) -> VocabularyReport:
    """Report symbols the declared libraries do not define.

    Vocabulary checking is advisory, not a parse gate: TL0 must be able to *represent* a
    state whose domain library has not been written yet, otherwise importing unfamiliar
    mathematics would be impossible.  Callers that want it to be fatal check
    :attr:`VocabularyReport.is_complete` themselves.
    """

    sorts = {head for library in libraries for head in library.sorts}
    operators = {item.symbol for library in libraries for item in library.operators}
    operations = {item.name for library in libraries for item in library.operations}

    seen_sorts: list[str] = []
    seen_ops: list[str] = []
    for term in _state_terms(state):
        seen_sorts.extend(_walk_types(term.sort))
        seen_ops.append(term.op)
    for declaration in state.declarations:
        seen_sorts.extend(_walk_types(declaration.sort))

    return VocabularyReport(
        unknown_sorts=tuple(sorted({item for item in seen_sorts if item not in sorts})),
        unknown_operators=tuple(sorted({item for item in seen_ops if item not in operators})),
        unknown_operations=tuple(
            sorted({item.operation for item in state.actions if item.operation not in operations})
        ),
    )


CORE_LIBRARY = Library(
    library_id="core",
    version="0.1.0",
    summary="Logic, equality, binding and the reasoning operations every domain reuses.",
    sorts=("Prop", "Bool", "Type", "Unknown", "Fun", "Forall", "Exists", "Set", "Nat"),
    operators=(
        OperatorSpec("var", 0, "Unknown", "reference to a declared name"),
        OperatorSpec("lit", 0, "Unknown", "literal value carried in the value slot"),
        OperatorSpec("mvar", 0, "Unknown", "metavariable reference"),
        OperatorSpec("lemma", 0, "Prop", "named external result"),
        OperatorSpec("true", 0, "Prop", "logical truth"),
        OperatorSpec("false", 0, "Prop", "logical falsity"),
        OperatorSpec("not", 1, "Prop", "negation"),
        OperatorSpec("and", None, "Prop", "conjunction"),
        OperatorSpec("or", None, "Prop", "disjunction"),
        OperatorSpec("implies", 2, "Prop", "implication"),
        OperatorSpec("iff", 2, "Prop", "biconditional"),
        OperatorSpec("eq", 2, "Prop", "equality"),
        OperatorSpec("ne", 2, "Prop", "disequality"),
        OperatorSpec("forall", 2, "Prop", "universal quantification over a declared binder"),
        OperatorSpec("exists", 2, "Prop", "existential quantification over a declared binder"),
        OperatorSpec("apply", None, "Unknown", "application of a function term"),
    ),
    operations=(
        OperationSpec("assume", "introduce an assumption into a scope"),
        OperationSpec("introduce", "introduce a binder and open a child scope"),
        OperationSpec("define", "add a definition or let-value"),
        OperationSpec("rewrite", "rewrite a target using an equality or lemma"),
        OperationSpec("apply", "apply a lemma or hypothesis to a goal"),
        OperationSpec("split", "split a goal into sub-goals in their own scopes"),
        OperationSpec("case", "case-split, generating one obligation per case"),
        OperationSpec("instantiate", "assign a metavariable"),
        OperationSpec("discharge", "discharge an obligation with evidence"),
        OperationSpec("close", "close a goal with evidence"),
    ),
)

#: A worked example of the extension rule.  Nothing outside this value changed to add it.
ALGEBRA_LIBRARY = CORE_LIBRARY.extend(
    library_id="algebra",
    version="0.1.0",
    summary="Ordered arithmetic and elementary algebraic structure.",
    sorts=("Int", "Rat", "Real", "Complex", "Matrix", "Group", "Ring", "Field", "Poly"),
    operators=(
        OperatorSpec("add", None, "Unknown", "addition"),
        OperatorSpec("sub", 2, "Unknown", "subtraction"),
        OperatorSpec("mul", None, "Unknown", "multiplication"),
        OperatorSpec("div", 2, "Unknown", "division"),
        OperatorSpec("neg", 1, "Unknown", "additive inverse"),
        OperatorSpec("pow", 2, "Unknown", "exponentiation"),
        OperatorSpec("le", 2, "Prop", "less than or equal"),
        OperatorSpec("lt", 2, "Prop", "strictly less than"),
        OperatorSpec("ge", 2, "Prop", "greater than or equal"),
        OperatorSpec("gt", 2, "Prop", "strictly greater than"),
        OperatorSpec("divides", 2, "Prop", "divisibility"),
        OperatorSpec("even", 1, "Prop", "evenness"),
        OperatorSpec("odd", 1, "Prop", "oddness"),
    ),
    operations=(
        OperationSpec("ring_normalise", "normalise both sides in a commutative ring"),
        OperationSpec("factor", "factor a polynomial expression"),
        OperationSpec("expand", "expand a product or power"),
    ),
)

STANDARD_LIBRARIES: tuple[Library, ...] = (CORE_LIBRARY, ALGEBRA_LIBRARY)

__all__ = [
    "ALGEBRA_LIBRARY",
    "CORE_LIBRARY",
    "STANDARD_LIBRARIES",
    "Library",
    "OperationSpec",
    "OperatorSpec",
    "VocabularyReport",
    "check_vocabulary",
]
