"""The unbiased eight-candidate Arena seed population."""

from __future__ import annotations

from typing import Any

from .genes import (
    ActionPolicy,
    Alphabet,
    BinderPolicy,
    CompositionPolicy,
    ErrorLocalityPolicy,
    EvidencePolicy,
    GrammarFamily,
    Morphology,
    ObligationPolicy,
    RedundancyPolicy,
    SerializationPolicy,
    StatePolicy,
    TokenPolicy,
    TypePolicy,
)
from .schema import LanguageGenome
from .validation import require_valid_genome


def _seed(candidate_id: str, **genes: Any) -> LanguageGenome:
    return require_valid_genome(LanguageGenome(candidate_id=candidate_id, parent_ids=(), **genes))


L0_STRUCTURED_ENGLISH = _seed(
    "L0_STRUCTURED_ENGLISH",
    alphabet=Alphabet.ASCII,
    token_policy=TokenPolicy.WORDLIKE,
    morphology=Morphology.PREFIX_ROLE,
    grammar=GrammarFamily.LABELLED_LINEAR,
    composition=CompositionPolicy.SPECIALIZED_FORMS,
    types=TypePolicy.DECLARATION_ONLY,
    binders=BinderPolicy.NAMED_LEXICAL,
    state=StatePolicy.TYPED_FRAME,
    actions=ActionPolicy.VERB_TARGET_ARGUMENTS,
    obligations=ObligationPolicy.SEPARATE_LIST,
    evidence=EvidencePolicy.EXPLICIT_STATE_MACHINE,
    serialization=SerializationPolicy.LINE_ORIENTED,
    redundancy=RedundancyPolicy.HIGH_EXPLICIT,
    error_locality=ErrorLocalityPolicy.EXPLICIT_DELIMITERS,
)

L1_CURRENT_HML = _seed(
    "L1_CURRENT_HML",
    alphabet=Alphabet.HYBRID,
    token_policy=TokenPolicy.SYMBOLIC,
    morphology=Morphology.TYPED_AFFIX,
    grammar=GrammarFamily.HYBRID,
    composition=CompositionPolicy.HYBRID,
    types=TypePolicy.REFINEMENT_SUPPORTED,
    binders=BinderPolicy.STRUCTURAL_ID,
    state=StatePolicy.DAG,
    actions=ActionPolicy.TYPED_ACTION,
    obligations=ObligationPolicy.SEPARATE_LIST,
    evidence=EvidencePolicy.PROOF_DAG,
    serialization=SerializationPolicy.TREE,
    redundancy=RedundancyPolicy.MEDIUM,
    error_locality=ErrorLocalityPolicy.STRUCTURAL_MARKERS,
)

L2_SEXPR = _seed(
    "L2_SEXPR",
    alphabet=Alphabet.ASCII,
    token_policy=TokenPolicy.SYMBOLIC,
    morphology=Morphology.NONE,
    grammar=GrammarFamily.S_EXPRESSION,
    composition=CompositionPolicy.GENERIC_APPLICATION,
    types=TypePolicy.EXPLICIT_EVERY_USE,
    binders=BinderPolicy.STRUCTURAL_ID,
    state=StatePolicy.DAG,
    actions=ActionPolicy.TYPED_ACTION,
    obligations=ObligationPolicy.INLINE,
    evidence=EvidencePolicy.EXPLICIT_STATE_MACHINE,
    serialization=SerializationPolicy.TREE,
    redundancy=RedundancyPolicy.MEDIUM,
    error_locality=ErrorLocalityPolicy.EXPLICIT_DELIMITERS,
)

L3_JSON_AST = _seed(
    "L3_JSON_AST",
    alphabet=Alphabet.UNICODE,
    token_policy=TokenPolicy.ROLE_LABELLED,
    morphology=Morphology.STRUCTURAL_ROLE,
    grammar=GrammarFamily.JSON_AST,
    composition=CompositionPolicy.TYPED_EXPRESSION_TREE,
    types=TypePolicy.EXPLICIT_EVERY_USE,
    binders=BinderPolicy.STRUCTURAL_ID,
    state=StatePolicy.DAG,
    actions=ActionPolicy.TYPED_ACTION,
    obligations=ObligationPolicy.ATTACHED_TO_EXPRESSION,
    evidence=EvidencePolicy.PROOF_DAG,
    serialization=SerializationPolicy.TREE,
    redundancy=RedundancyPolicy.HIGH_EXPLICIT,
    error_locality=ErrorLocalityPolicy.STRUCTURAL_MARKERS,
)

L4_TYPED_PREFIX = _seed(
    "L4_TYPED_PREFIX",
    alphabet=Alphabet.ASCII,
    token_policy=TokenPolicy.ROLE_LABELLED,
    morphology=Morphology.PREFIX_ROLE,
    grammar=GrammarFamily.PREFIX,
    composition=CompositionPolicy.TYPED_EXPRESSION_TREE,
    types=TypePolicy.EXPLICIT_EVERY_USE,
    binders=BinderPolicy.STRUCTURAL_ID,
    state=StatePolicy.TYPED_FRAME,
    actions=ActionPolicy.VERB_TARGET_ARGUMENTS,
    obligations=ObligationPolicy.ATTACHED_TO_ACTION,
    evidence=EvidencePolicy.EXPLICIT_STATE_MACHINE,
    serialization=SerializationPolicy.TREE,
    redundancy=RedundancyPolicy.MEDIUM,
    error_locality=ErrorLocalityPolicy.EXPLICIT_DELIMITERS,
)

L5_COMPACT_SYMBOLIC = _seed(
    "L5_COMPACT_SYMBOLIC",
    alphabet=Alphabet.UNICODE,
    token_policy=TokenPolicy.COMPACT,
    morphology=Morphology.NONE,
    grammar=GrammarFamily.SYMBOLIC,
    composition=CompositionPolicy.GENERIC_APPLICATION,
    types=TypePolicy.INFERRED,
    binders=BinderPolicy.LOCALLY_NAMELESS,
    state=StatePolicy.FLAT_LIST,
    actions=ActionPolicy.TYPED_ACTION,
    obligations=ObligationPolicy.INLINE,
    evidence=EvidencePolicy.MINIMAL,
    serialization=SerializationPolicy.COMPACT_CODE,
    redundancy=RedundancyPolicy.COMPRESSED,
    error_locality=ErrorLocalityPolicy.NONE,
)

L6_GRAPH_TRIPLES = _seed(
    "L6_GRAPH_TRIPLES",
    alphabet=Alphabet.ASCII,
    token_policy=TokenPolicy.ROLE_LABELLED,
    morphology=Morphology.STRUCTURAL_ROLE,
    grammar=GrammarFamily.GRAPH_TRIPLE,
    composition=CompositionPolicy.GENERIC_APPLICATION,
    types=TypePolicy.DECLARATION_ONLY,
    binders=BinderPolicy.STRUCTURAL_ID,
    state=StatePolicy.GRAPH,
    actions=ActionPolicy.RULE_PREMISE_CONCLUSION,
    obligations=ObligationPolicy.ATTACHED_TO_EXPRESSION,
    evidence=EvidencePolicy.PROOF_DAG,
    serialization=SerializationPolicy.GRAPH,
    redundancy=RedundancyPolicy.HIGH_EXPLICIT,
    error_locality=ErrorLocalityPolicy.STRUCTURAL_MARKERS,
)

L7_HYBRID_ROLE_LABELLED = _seed(
    "L7_HYBRID_ROLE_LABELLED",
    alphabet=Alphabet.HYBRID,
    token_policy=TokenPolicy.ROLE_LABELLED,
    morphology=Morphology.SUFFIX_ROLE,
    grammar=GrammarFamily.HYBRID,
    composition=CompositionPolicy.HYBRID,
    types=TypePolicy.REFINEMENT_SUPPORTED,
    binders=BinderPolicy.STRUCTURAL_ID,
    state=StatePolicy.DAG,
    actions=ActionPolicy.RULE_PREMISE_CONCLUSION,
    obligations=ObligationPolicy.SEPARATE_LIST,
    evidence=EvidencePolicy.PROOF_DAG,
    serialization=SerializationPolicy.TREE,
    redundancy=RedundancyPolicy.MEDIUM,
    error_locality=ErrorLocalityPolicy.STRUCTURAL_MARKERS,
)

SEED_GENOMES = (
    L0_STRUCTURED_ENGLISH,
    L1_CURRENT_HML,
    L2_SEXPR,
    L3_JSON_AST,
    L4_TYPED_PREFIX,
    L5_COMPACT_SYMBOLIC,
    L6_GRAPH_TRIPLES,
    L7_HYBRID_ROLE_LABELLED,
)

SEED_GENOME_BY_ID = {genome.candidate_id: genome for genome in SEED_GENOMES}
