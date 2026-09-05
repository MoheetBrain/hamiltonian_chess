"""Dependency validation and targeted evaluation planning for genomes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .genes import GENE_IMPACT_CLASS, GeneFamily, ImpactClass
from .schema import LanguageGenome


@dataclass(frozen=True, slots=True)
class DependencyConstraint:
    constraint_id: str
    when_gene: GeneFamily
    when_values: frozenset[str]
    requires_gene: GeneFamily
    allowed_values: frozenset[str]
    rationale: str

    def applies(self, genome: LanguageGenome) -> bool:
        return genome.gene(self.when_gene) in self.when_values

    def is_satisfied(self, genome: LanguageGenome) -> bool:
        return genome.gene(self.requires_gene) in self.allowed_values

    def to_dict(self) -> dict[str, object]:
        return {
            "constraint_id": self.constraint_id,
            "when": {
                "gene": self.when_gene.value,
                "values": sorted(self.when_values),
            },
            "requires": {
                "gene": self.requires_gene.value,
                "allowed_values": sorted(self.allowed_values),
            },
            "rationale": self.rationale,
        }


DEPENDENCY_CONSTRAINTS = (
    DependencyConstraint(
        "json-grammar-is-tree-serialized",
        GeneFamily.GRAMMAR,
        frozenset({"json-ast"}),
        GeneFamily.SERIALIZATION,
        frozenset({"tree"}),
        "A JSON/AST grammar must preserve explicit tree structure.",
    ),
    DependencyConstraint(
        "graph-grammar-has-graph-state",
        GeneFamily.GRAMMAR,
        frozenset({"graph-triple"}),
        GeneFamily.STATE,
        frozenset({"graph"}),
        "Triple syntax needs graph-addressable state nodes.",
    ),
    DependencyConstraint(
        "graph-grammar-is-graph-serialized",
        GeneFamily.GRAMMAR,
        frozenset({"graph-triple"}),
        GeneFamily.SERIALIZATION,
        frozenset({"graph"}),
        "Triple syntax must not be silently flattened by another serialization.",
    ),
    DependencyConstraint(
        "graph-serialization-has-graph-grammar",
        GeneFamily.SERIALIZATION,
        frozenset({"graph"}),
        GeneFamily.GRAMMAR,
        frozenset({"graph-triple", "hybrid"}),
        "Graph serialization requires a grammar with addressable edges.",
    ),
    DependencyConstraint(
        "proof-dag-has-addressable-state",
        GeneFamily.EVIDENCE,
        frozenset({"proof-dag"}),
        GeneFamily.STATE,
        frozenset({"dag", "graph"}),
        "Proof dependencies require stable addressable nodes.",
    ),
    DependencyConstraint(
        "structural-morphology-is-role-labelled",
        GeneFamily.MORPHOLOGY,
        frozenset({"structural-role"}),
        GeneFamily.TOKEN_POLICY,
        frozenset({"role-labelled"}),
        "Structural role morphology needs role-labelled tokens.",
    ),
    DependencyConstraint(
        "typed-affix-has-visible-types",
        GeneFamily.MORPHOLOGY,
        frozenset({"typed-affix"}),
        GeneFamily.TYPES,
        frozenset({"explicit-every-use", "declaration-only", "refinement-supported"}),
        "Typed affixes cannot be generated when all types are inferred.",
    ),
    DependencyConstraint(
        "attached-obligation-has-structured-action",
        GeneFamily.OBLIGATIONS,
        frozenset({"attached-to-action"}),
        GeneFamily.ACTIONS,
        frozenset({"typed-action", "verb-target-arguments", "rule-premise-conclusion"}),
        "An action attachment needs an addressable action structure.",
    ),
)


GENE_AFFECTED_TESTS: dict[GeneFamily, frozenset[str]] = {
    GeneFamily.ALPHABET: frozenset({"unicode_safety", "token_budget", "roundtrip"}),
    GeneFamily.TOKEN_POLICY: frozenset({"token_budget", "perturbation", "roundtrip"}),
    GeneFamily.MORPHOLOGY: frozenset({"tokenization", "parser_rejection", "roundtrip"}),
    GeneFamily.GRAMMAR: frozenset({"parser_rejection", "roundtrip", "semantic_collision"}),
    GeneFamily.COMPOSITION: frozenset({"compositionality", "nested_expression", "roundtrip"}),
    GeneFamily.TYPES: frozenset({"type_preservation", "type_confusion", "roundtrip"}),
    GeneFamily.BINDERS: frozenset({"alpha_equivalence", "scope_capture", "shadowing"}),
    GeneFamily.STATE: frozenset({"state_reconstruction", "ordering", "roundtrip"}),
    GeneFamily.ACTIONS: frozenset({"action_reconstruction", "invalid_action", "roundtrip"}),
    GeneFamily.OBLIGATIONS: frozenset({"obligation_laundering", "partiality", "roundtrip"}),
    GeneFamily.EVIDENCE: frozenset({"proof_cycle", "evidence_dependency", "roundtrip"}),
    GeneFamily.SERIALIZATION: frozenset({"malformed_input", "roundtrip", "determinism"}),
    GeneFamily.REDUNDANCY: frozenset({"perturbation", "token_budget", "roundtrip"}),
    GeneFamily.ERROR_LOCALITY: frozenset({"malformed_input", "perturbation", "error_location"}),
}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    constraint_id: str
    genes: tuple[GeneFamily, ...]
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "constraint_id": self.constraint_id,
            "genes": [gene.value for gene in self.genes],
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class GenomeValidation:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "issues": [issue.to_dict() for issue in self.issues]}


class GenomeValidationError(ValueError):
    def __init__(self, validation: GenomeValidation):
        self.validation = validation
        detail = "; ".join(issue.message for issue in validation.issues)
        super().__init__(detail or "invalid genome")


def validate_genome(genome: LanguageGenome) -> GenomeValidation:
    issues = tuple(
        ValidationIssue(
            constraint_id=constraint.constraint_id,
            genes=(constraint.when_gene, constraint.requires_gene),
            message=(
                f"{constraint.when_gene.value}={genome.gene(constraint.when_gene)!r} requires "
                f"{constraint.requires_gene.value} in {sorted(constraint.allowed_values)!r}"
            ),
        )
        for constraint in DEPENDENCY_CONSTRAINTS
        if constraint.applies(genome) and not constraint.is_satisfied(genome)
    )
    return GenomeValidation(issues)


def require_valid_genome(genome: LanguageGenome) -> LanguageGenome:
    validation = validate_genome(genome)
    if not validation.valid:
        raise GenomeValidationError(validation)
    return genome


def affected_tests(changed_genes: Iterable[GeneFamily | str]) -> tuple[str, ...]:
    tests: set[str] = set()
    for gene in changed_genes:
        tests.update(GENE_AFFECTED_TESTS[GeneFamily(gene)])
    return tuple(sorted(tests))


def required_impact_class(changed_genes: Iterable[GeneFamily | str]) -> ImpactClass:
    rank = {
        ImpactClass.SURFACE_ONLY: 0,
        ImpactClass.STRUCTURAL_SEMANTIC: 1,
        ImpactClass.CANONICAL_SEMANTIC_EXTENSION: 2,
    }
    impacts = [GENE_IMPACT_CLASS[GeneFamily(gene)] for gene in changed_genes]
    return max(impacts, key=rank.__getitem__, default=ImpactClass.SURFACE_ONLY)
