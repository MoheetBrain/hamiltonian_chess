"""Machine-readable gene vocabulary for Arena language candidates."""

from __future__ import annotations

from enum import StrEnum


class GeneFamily(StrEnum):
    ALPHABET = "alphabet"
    TOKEN_POLICY = "token_policy"
    MORPHOLOGY = "morphology"
    GRAMMAR = "grammar"
    COMPOSITION = "composition"
    TYPES = "types"
    BINDERS = "binders"
    STATE = "state"
    ACTIONS = "actions"
    OBLIGATIONS = "obligations"
    EVIDENCE = "evidence"
    SERIALIZATION = "serialization"
    REDUNDANCY = "redundancy"
    ERROR_LOCALITY = "error_locality"


class ImpactClass(StrEnum):
    """Evaluation cost of a change, ordered from cheapest to most governed."""

    SURFACE_ONLY = "surface-only"
    STRUCTURAL_SEMANTIC = "structural-semantic"
    CANONICAL_SEMANTIC_EXTENSION = "canonical-semantic-extension"


class Alphabet(StrEnum):
    ASCII = "ascii"
    UNICODE = "unicode"
    HYBRID = "hybrid"


class TokenPolicy(StrEnum):
    WORDLIKE = "wordlike"
    SYMBOLIC = "symbolic"
    ROLE_LABELLED = "role-labelled"
    COMPACT = "compact"


class Morphology(StrEnum):
    NONE = "none"
    PREFIX_ROLE = "prefix-role"
    SUFFIX_ROLE = "suffix-role"
    TYPED_AFFIX = "typed-affix"
    STRUCTURAL_ROLE = "structural-role"


class GrammarFamily(StrEnum):
    LABELLED_LINEAR = "labelled-linear"
    PREFIX = "prefix"
    S_EXPRESSION = "s-expression"
    POSTFIX = "postfix"
    JSON_AST = "json-ast"
    GRAPH_TRIPLE = "graph-triple"
    SYMBOLIC = "symbolic"
    HYBRID = "hybrid"


class CompositionPolicy(StrEnum):
    SPECIALIZED_FORMS = "specialized-forms"
    GENERIC_APPLICATION = "generic-application"
    TYPED_EXPRESSION_TREE = "typed-expression-tree"
    HYBRID = "hybrid"


class TypePolicy(StrEnum):
    EXPLICIT_EVERY_USE = "explicit-every-use"
    DECLARATION_ONLY = "declaration-only"
    INFERRED = "inferred"
    REFINEMENT_SUPPORTED = "refinement-supported"


class BinderPolicy(StrEnum):
    NAMED_LEXICAL = "named-lexical"
    STRUCTURAL_ID = "structural-id"
    LOCALLY_NAMELESS = "locally-nameless"
    OTHER_VALIDATED = "other-validated"


class StatePolicy(StrEnum):
    FLAT_LIST = "flat-list"
    TYPED_FRAME = "typed-frame"
    DAG = "dag"
    GRAPH = "graph"


class ActionPolicy(StrEnum):
    FREE_TEXT = "free-text"
    TYPED_ACTION = "typed-action"
    VERB_TARGET_ARGUMENTS = "verb-target-arguments"
    RULE_PREMISE_CONCLUSION = "rule-premise-conclusion"


class ObligationPolicy(StrEnum):
    INLINE = "inline"
    SEPARATE_LIST = "separate-list"
    ATTACHED_TO_ACTION = "attached-to-action"
    ATTACHED_TO_EXPRESSION = "attached-to-expression"


class EvidencePolicy(StrEnum):
    MINIMAL = "minimal"
    EXPLICIT_STATE_MACHINE = "explicit-state-machine"
    PROOF_DAG = "proof-dag"


class SerializationPolicy(StrEnum):
    LINE_ORIENTED = "line-oriented"
    TREE = "tree"
    COMPACT_CODE = "compact-code"
    GRAPH = "graph"


class RedundancyPolicy(StrEnum):
    HIGH_EXPLICIT = "high-explicit"
    MEDIUM = "medium"
    COMPRESSED = "compressed"


class ErrorLocalityPolicy(StrEnum):
    EXPLICIT_DELIMITERS = "explicit-delimiters"
    CHECKSUMS = "checksums"
    STRUCTURAL_MARKERS = "structural-markers"
    NONE = "none"


GENE_ENUMS = {
    GeneFamily.ALPHABET: Alphabet,
    GeneFamily.TOKEN_POLICY: TokenPolicy,
    GeneFamily.MORPHOLOGY: Morphology,
    GeneFamily.GRAMMAR: GrammarFamily,
    GeneFamily.COMPOSITION: CompositionPolicy,
    GeneFamily.TYPES: TypePolicy,
    GeneFamily.BINDERS: BinderPolicy,
    GeneFamily.STATE: StatePolicy,
    GeneFamily.ACTIONS: ActionPolicy,
    GeneFamily.OBLIGATIONS: ObligationPolicy,
    GeneFamily.EVIDENCE: EvidencePolicy,
    GeneFamily.SERIALIZATION: SerializationPolicy,
    GeneFamily.REDUNDANCY: RedundancyPolicy,
    GeneFamily.ERROR_LOCALITY: ErrorLocalityPolicy,
}

# Structural choices can alter what a solver must reconstruct even when the canonical
# state itself is unchanged. The remaining choices are cheap surface experiments.
GENE_IMPACT_CLASS = {
    GeneFamily.ALPHABET: ImpactClass.SURFACE_ONLY,
    GeneFamily.TOKEN_POLICY: ImpactClass.SURFACE_ONLY,
    GeneFamily.MORPHOLOGY: ImpactClass.SURFACE_ONLY,
    GeneFamily.GRAMMAR: ImpactClass.SURFACE_ONLY,
    GeneFamily.COMPOSITION: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.TYPES: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.BINDERS: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.STATE: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.ACTIONS: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.OBLIGATIONS: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.EVIDENCE: ImpactClass.STRUCTURAL_SEMANTIC,
    GeneFamily.SERIALIZATION: ImpactClass.SURFACE_ONLY,
    GeneFamily.REDUNDANCY: ImpactClass.SURFACE_ONLY,
    GeneFamily.ERROR_LOCALITY: ImpactClass.SURFACE_ONLY,
}

GENE_FAMILIES = tuple(GeneFamily)


def parse_gene_value(family: GeneFamily | str, value: StrEnum | str) -> StrEnum:
    """Coerce a serialized value using the declared family vocabulary."""

    parsed_family = GeneFamily(family)
    return GENE_ENUMS[parsed_family](value)
