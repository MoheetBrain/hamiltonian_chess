"""Deterministic Architect player for auditable genome proposals."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from arena.genome.genes import GENE_ENUMS, GeneFamily, ImpactClass
from arena.genome.mutation import (
    EvaluationTier,
    MutationOperator,
    MutationProposal,
    MutationRecord,
    SoundnessRisk,
    apply_mutation,
)
from arena.genome.schema import LanguageGenome
from arena.genome.validation import GenomeValidationError

_OPERATOR_BY_GENE = {
    GeneFamily.ALPHABET: MutationOperator.CHANGE_TOKEN,
    GeneFamily.TOKEN_POLICY: MutationOperator.CHANGE_TOKEN,
    GeneFamily.MORPHOLOGY: MutationOperator.ADD_ROLE_MORPHOLOGY,
    GeneFamily.GRAMMAR: MutationOperator.PREFIX_TO_SEXPR,
    GeneFamily.COMPOSITION: MutationOperator.CANONICALIZE_ARGUMENT_ORDER,
    GeneFamily.TYPES: MutationOperator.ADD_TYPE_ANNOTATION,
    GeneFamily.BINDERS: MutationOperator.CHANGE_BINDER_ENCODING,
    GeneFamily.STATE: MutationOperator.CHANGE_STATEMENT_ORDER,
    GeneFamily.ACTIONS: MutationOperator.FACTOR_ACTION,
    GeneFamily.OBLIGATIONS: MutationOperator.MOVE_OBLIGATION_INLINE,
    GeneFamily.EVIDENCE: MutationOperator.COMPRESS_STATUS,
    GeneFamily.SERIALIZATION: MutationOperator.CHANGE_DELIMITER,
    GeneFamily.REDUNDANCY: MutationOperator.REMOVE_REDUNDANT_WRAPPER,
    GeneFamily.ERROR_LOCALITY: MutationOperator.CHANGE_DELIMITER,
}


@dataclass(frozen=True, slots=True)
class ArchitectProposal:
    genome: LanguageGenome
    mutation: MutationRecord


class Architect:
    """Explore legal one-gene neighbours in a reproducible pseudo-random order."""

    name = "deterministic-neighbour-architect-v0"

    def propose(
        self, parent: LanguageGenome, *, count: int = 20, seed: int = 0
    ) -> tuple[ArchitectProposal, ...]:
        if count < 0:
            raise ValueError("proposal count must be non-negative")
        digest = hashlib.sha256(f"{parent.candidate_hash}:{seed}".encode()).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        neighbours = [
            (family, value.value)
            for family in GeneFamily
            for value in GENE_ENUMS[family]
            if value.value != parent.gene(family)
        ]
        rng.shuffle(neighbours)
        proposals: list[ArchitectProposal] = []
        for family, value in neighbours:
            surface_only = family in {
                GeneFamily.ALPHABET,
                GeneFamily.TOKEN_POLICY,
                GeneFamily.MORPHOLOGY,
                GeneFamily.GRAMMAR,
                GeneFamily.SERIALIZATION,
                GeneFamily.REDUNDANCY,
                GeneFamily.ERROR_LOCALITY,
            }
            impact = ImpactClass.SURFACE_ONLY if surface_only else ImpactClass.STRUCTURAL_SEMANTIC
            proposal = MutationProposal.build(
                parent=parent,
                operator=_OPERATOR_BY_GENE[family],
                changes={family: value},
                hypothesis=f"Changing {family.value} isolates its effect on Arena fitness.",
                expected_benefit=f"Test whether {value} improves a Pareto objective.",
                soundness_risk=SoundnessRisk.LOW if surface_only else SoundnessRisk.MEDIUM,
                required_evaluation_tier=(
                    EvaluationTier.SURFACE if surface_only else EvaluationTier.STRUCTURAL
                ),
                impact_class=impact,
            )
            try:
                genome, mutation = apply_mutation(parent, proposal)
            except GenomeValidationError:
                continue
            proposals.append(ArchitectProposal(genome, mutation))
            if len(proposals) == count:
                break
        return tuple(proposals)


ArchitectPlayer = Architect
